from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from io import BytesIO
import json
import os
import re
from typing import Any, Literal
from uuid import uuid4
from zipfile import ZIP_DEFLATED, ZipFile

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .deployment import DeploymentManager
from .features import BASE_TIMESTAMP, join_parts, normalize_text, stable_bucket
from .ops import build_dashboard_data, build_research_data, read_pending_reviews, render_dashboard_html, submit_manual_review
from .pipeline import FraudFlowRunner
from .schema import TransactionEvent
from .web_ui import STATIC_DIR, UI_VERSION, render_template

SWAGGER_VI_JS_PATH = STATIC_DIR / "js" / "swagger_vi.js"
DEFAULT_STARTUP_BOOTSTRAP_ROWS = 25_000
XLSX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


PAYSIM_EXAMPLE = {
    "source": "paysim",
    "tx_type": "TRANSFER",
    "amount": 275000.0,
    "timestamp": "2025-01-01T14:00:00+00:00",
    "extras": {
        "card_id": "C123456789",
        "merchant_id": "merchant_12000",
        "device_id": "device_0801",
        "ip_address": "10.88.42.17",
        "location_id": "zone_041",
    },
    "oldbalanceOrg": 300000.0,
    "newbalanceOrig": 25000.0,
    "oldbalanceDest": 40000.0,
    "newbalanceDest": 315000.0,
    "is_fraud": 0,
}

IEEE_EXAMPLE = {
    "source": "ieee",
    "tx_type": "W",
    "amount": 120.5,
    "timestamp": "2025-01-01T00:00:00+00:00",
    "extras": {
        "ProductCD": "W",
        "card1": 13926,
        "card2": 321,
        "card3": 150,
        "card5": 142,
        "card6": "debit",
        "addr1": 315,
        "addr2": 87,
        "P_emaildomain": "gmail.com",
        "R_emaildomain": "gmail.com",
        "DeviceType": "desktop",
        "DeviceInfo": "Windows",
        "id_30": "Windows 10",
        "id_31": "chrome 80.0",
        "id_33": "1920x1080",
    },
}


def _derive_card_id(source: str, extras: dict[str, Any]) -> str:
    if source == "ieee":
        return join_parts(
            extras.get("card1"),
            extras.get("card2"),
            extras.get("card3"),
            extras.get("card5"),
            extras.get("card6"),
        )
    return normalize_text(extras.get("card_id")) or "unknown_card"


def _derive_merchant_id(source: str, tx_type: str, extras: dict[str, Any]) -> str:
    if source == "ieee":
        return join_parts(
            tx_type,
            extras.get("P_emaildomain"),
            extras.get("R_emaildomain"),
            extras.get("addr1"),
            extras.get("addr2"),
        )
    return normalize_text(extras.get("merchant_id")) or "unknown_merchant"


def _derive_device_id(source: str, extras: dict[str, Any]) -> str:
    if source == "ieee":
        return join_parts(
            extras.get("DeviceType"),
            extras.get("DeviceInfo"),
            extras.get("id_30"),
            extras.get("id_31"),
            extras.get("id_33"),
        )
    return normalize_text(extras.get("device_id")) or "unknown_device"


def _derive_location_id(source: str, extras: dict[str, Any]) -> str:
    if source == "ieee":
        return join_parts(
            extras.get("addr1"),
            extras.get("addr2"),
            extras.get("dist1"),
            extras.get("dist2"),
        )
    return normalize_text(extras.get("location_id")) or "unknown_location"


def _derive_ip_address(source: str, merchant_id: str, extras: dict[str, Any]) -> str:
    if source == "ieee":
        return (
            f"10."
            f"{stable_bucket(join_parts(extras.get('addr1'), extras.get('addr2')), 'ieee-ip-a', 250) + 1}."
            f"{stable_bucket(join_parts(extras.get('id_31'), extras.get('DeviceType')), 'ieee-ip-b', 250) + 1}."
            f"{stable_bucket(join_parts(extras.get('ProductCD'), extras.get('P_emaildomain'), merchant_id), 'ieee-ip-c', 250) + 1}"
        )
    return normalize_text(extras.get("ip_address")) or "10.0.0.1"


class TransactionIn(BaseModel):
    tx_id: str | None = None
    step: int | None = Field(default=None, ge=0)
    timestamp: str | None = None
    tx_type: str
    amount: float = Field(ge=0.0)
    card_id: str | None = None
    merchant_id: str | None = None
    device_id: str | None = None
    ip_address: str | None = None
    location_id: str | None = None
    oldbalanceOrg: float = Field(default=0.0, ge=0.0)
    newbalanceOrig: float = Field(default=0.0, ge=0.0)
    oldbalanceDest: float = Field(default=0.0, ge=0.0)
    newbalanceDest: float = Field(default=0.0, ge=0.0)
    is_fraud: int | None = None
    is_flagged_fraud: int | None = None
    source: Literal["paysim", "ieee"] | None = None
    extras: dict[str, Any] = Field(default_factory=dict)

    model_config = {"json_schema_extra": {"examples": [PAYSIM_EXAMPLE, IEEE_EXAMPLE]}}

    def to_event(self, default_source: str = "paysim") -> TransactionEvent:
        timestamp = self.timestamp or datetime.now(timezone.utc).isoformat()
        if self.step is None:
            try:
                dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            except ValueError as exc:
                raise ValueError("timestamp must be ISO-8601, for example 2025-01-01T14:00:00+00:00") from exc
            step = max(0, int((dt - BASE_TIMESTAMP.replace(tzinfo=dt.tzinfo)).total_seconds() // 3600))
        else:
            step = self.step

        source = self.source or default_source
        extras = dict(self.extras)
        extras["source"] = source
        if source == "ieee":
            extras.setdefault("ProductCD", self.tx_type)

        card_id = self.card_id or _derive_card_id(source, extras)
        merchant_id = self.merchant_id or _derive_merchant_id(source, self.tx_type, extras)
        device_id = self.device_id or _derive_device_id(source, extras)
        location_id = self.location_id or _derive_location_id(source, extras)
        ip_address = self.ip_address or _derive_ip_address(source, merchant_id, extras)

        return TransactionEvent(
            tx_id=self.tx_id or f"live_{uuid4().hex[:12]}",
            step=step,
            timestamp=timestamp,
            tx_type=self.tx_type,
            amount=self.amount,
            card_id=card_id,
            merchant_id=merchant_id,
            device_id=device_id,
            ip_address=ip_address,
            location_id=location_id,
            oldbalanceOrg=self.oldbalanceOrg,
            newbalanceOrig=self.newbalanceOrig,
            oldbalanceDest=self.oldbalanceDest,
            newbalanceDest=self.newbalanceDest,
            is_fraud=self.is_fraud,
            is_flagged_fraud=self.is_flagged_fraud,
            extras=extras,
        )


class ReviewDecisionIn(BaseModel):
    action: Literal["approve", "review", "block"]
    reviewer: str = Field(default="analyst")
    note: str
    actual_label: int | None = Field(default=None, ge=0, le=1)

    model_config = {
        "json_schema_extra": {
            "example": {
                "action": "review",
                "reviewer": "risk_analyst_01",
                "note": "Thiết bị mới, cần xác minh thêm với người dùng.",
                "actual_label": 0,
            }
        }
    }


def _render_home_html(app: FastAPI) -> str:
    dashboard_data = build_dashboard_data()
    bootstrapped_rows = getattr(app.state, "bootstrapped_rows", 0)
    return render_template(
        "home.html",
        current_page="home",
        default_source="paysim",
        version=app.version,
        profile=dashboard_data["profile"],
        deployment=dashboard_data["deployment"],
        live_metrics=dashboard_data["live_metrics"],
        totals=dashboard_data["totals"],
        dashboard_report=dashboard_data["dashboard_report"],
        product_story=dashboard_data["product_story"],
        bootstrapped_rows=bootstrapped_rows,
        bootstrapped_rows_label=_format_bootstrapped_rows_label(bootstrapped_rows),
    )


def _render_docs_portal(app: FastAPI) -> str:
    quickstart = """curl -X POST "http://127.0.0.1:8000/gateway/transaction" \\
  -H "Content-Type: application/json" \\
  -d @payload.json"""
    dashboard_data = build_dashboard_data()
    bootstrapped_rows = getattr(app.state, "bootstrapped_rows", 0)
    return render_template(
        "docs_portal.html",
        current_page="docs",
        version=app.version,
        quickstart=quickstart,
        paysim_example=json.dumps(PAYSIM_EXAMPLE, ensure_ascii=False, indent=2),
        ieee_example=json.dumps(IEEE_EXAMPLE, ensure_ascii=False, indent=2),
        profile=dashboard_data["profile"],
        deployment=dashboard_data["deployment"],
        offline_metrics=dashboard_data["offline_metrics"],
        validation_metrics=dashboard_data["validation_metrics"],
        test_confusion_matrix=dashboard_data["test_confusion_matrix"],
        validation_confusion_matrix=dashboard_data["validation_confusion_matrix"],
        live_metrics=dashboard_data["live_metrics"],
        totals=dashboard_data["totals"],
        dashboard_report=dashboard_data["dashboard_report"],
        dataset_preview=json.dumps(dashboard_data.get("dataset_preview", []), ensure_ascii=False, indent=2),
        dataset_preview_rows=dashboard_data.get("dataset_preview", []),
        dataset_preview_columns=dashboard_data.get("dataset_preview_columns", []),
        selected_params=dashboard_data.get("selected_params", {}),
        product_story=dashboard_data["product_story"],
        bootstrapped_rows=bootstrapped_rows,
        bootstrapped_rows_label=_format_bootstrapped_rows_label(bootstrapped_rows),
    )


def _render_research_html(app: FastAPI) -> str:
    dashboard_data = build_dashboard_data()
    research_data = build_research_data()
    bootstrapped_rows = getattr(app.state, "bootstrapped_rows", 0)
    return render_template(
        "research.html",
        current_page="research",
        version=app.version,
        profile=dashboard_data["profile"],
        deployment=dashboard_data["deployment"],
        product_story=dashboard_data["product_story"],
        bootstrapped_rows=bootstrapped_rows,
        bootstrapped_rows_label=_format_bootstrapped_rows_label(bootstrapped_rows),
        **research_data,
    )


def _render_transaction_form_html(app: FastAPI) -> str:
    dashboard_data = build_dashboard_data()
    bootstrapped_rows = getattr(app.state, "bootstrapped_rows", 0)
    return render_template(
        "transaction_form.html",
        current_page="form",
        version=app.version,
        example=PAYSIM_EXAMPLE,
        example_json=json.dumps(PAYSIM_EXAMPLE, ensure_ascii=False, indent=2),
        profile=dashboard_data["profile"],
        deployment=dashboard_data["deployment"],
        live_metrics=dashboard_data["live_metrics"],
        totals=dashboard_data["totals"],
        product_story=dashboard_data["product_story"],
        bootstrapped_rows=bootstrapped_rows,
        bootstrapped_rows_label=_format_bootstrapped_rows_label(bootstrapped_rows),
    )


def _render_pending_reviews_html(app: FastAPI, *, queue_limit: int | None = None) -> str:
    dashboard_data = build_dashboard_data(queue_limit=queue_limit)
    bootstrapped_rows = getattr(app.state, "bootstrapped_rows", 0)
    return render_template(
        "review_queue.html",
        current_page="reviews",
        version=app.version,
        profile=dashboard_data["profile"],
        deployment=dashboard_data["deployment"],
        live_metrics=dashboard_data["live_metrics"],
        totals=dashboard_data["totals"],
        product_story=dashboard_data["product_story"],
        review_queue_cards=dashboard_data["review_queue_cards"],
        queue_overview=dashboard_data["queue_overview"],
        bootstrapped_rows=bootstrapped_rows,
        bootstrapped_rows_label=_format_bootstrapped_rows_label(bootstrapped_rows),
    )


def _render_method_help_html(
    app: FastAPI,
    *,
    endpoint_path: str,
    method: str,
    title: str,
    subtitle: str,
    example_payload: dict[str, Any] | list[dict[str, Any]],
) -> str:
    dashboard_data = build_dashboard_data()
    bootstrapped_rows = getattr(app.state, "bootstrapped_rows", 0)
    return render_template(
        "method_help.html",
        current_page="help",
        version=app.version,
        endpoint_path=endpoint_path,
        method=method,
        title=title,
        subtitle=subtitle,
        example_payload=json.dumps(example_payload, ensure_ascii=False, indent=2),
        profile=dashboard_data["profile"],
        deployment=dashboard_data["deployment"],
        live_metrics=dashboard_data["live_metrics"],
        product_story=dashboard_data["product_story"],
        bootstrapped_rows=bootstrapped_rows,
        bootstrapped_rows_label=_format_bootstrapped_rows_label(bootstrapped_rows),
    )


def _render_swagger_ui_html(app: FastAPI) -> HTMLResponse:
    base = get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title="Tài liệu API tương tác Fraud Flow",
        swagger_ui_parameters={
            "docExpansion": "list",
            "defaultModelsExpandDepth": 1,
            "displayRequestDuration": True,
            "deepLinking": True,
            "tryItOutEnabled": True,
            "filter": True,
        },
    )
    html = base.body.decode("utf-8")
    html = html.replace(
        "</body>",
        f'<script src="/swagger-vi.js?v={app.version}"></script>\n</body>',
    )
    return HTMLResponse(html)


def _startup_bootstrap_rows(metadata: dict[str, Any]) -> int:
    val_end = int(metadata.get("val_end", 0) or 0)
    configured = os.getenv("FRAUD_FLOW_BOOTSTRAP_ROWS", "").strip()
    if configured:
        try:
            requested = max(0, int(configured))
        except ValueError:
            requested = DEFAULT_STARTUP_BOOTSTRAP_ROWS
    else:
        requested = DEFAULT_STARTUP_BOOTSTRAP_ROWS
    if val_end <= 0:
        return requested
    return min(val_end, requested)


def _format_bootstrapped_rows_label(rows: int | None) -> str:
    value = int(rows or 0)
    if value <= 0:
        return ""
    if value >= 1000 and value % 1000 == 0:
        return f"{value // 1000}k rows"
    if value >= 1000:
        return f"{value / 1000:.1f}k rows"
    return f"{value:,} rows"


def _json_cell(value: Any) -> str:
    if value is None:
        return ""
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _compact_explanation(items: Any) -> str:
    if not isinstance(items, list):
        return ""
    parts = []
    for item in items[:5]:
        if not isinstance(item, dict):
            continue
        feature = item.get("feature", "N/A")
        impact = item.get("impact", "")
        weight = item.get("weight", "")
        parts.append(f"{feature}: impact={impact}, weight={weight}")
    return " | ".join(parts)


def _pending_review_export_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    export_rows: list[dict[str, Any]] = []
    for index, row in enumerate(rows, start=1):
        event = row.get("event", {})
        prediction = row.get("prediction", {})
        agent = row.get("agent") or {}
        agent_output = agent.get("agent_output") or {}
        structured_output = agent_output.get("structured_output") or {}
        action = row.get("final_action") or agent.get("action") or structured_output.get("recommended_action") or "review"
        export_rows.append(
            {
                "stt": index,
                "tx_id": event.get("tx_id", ""),
                "timestamp": event.get("timestamp", ""),
                "step": event.get("step", ""),
                "source": (event.get("extras") or {}).get("source", ""),
                "tx_type": event.get("tx_type", ""),
                "amount": event.get("amount", ""),
                "card_id": event.get("card_id", ""),
                "merchant_id": event.get("merchant_id", ""),
                "device_id": event.get("device_id", ""),
                "ip_address": event.get("ip_address", ""),
                "location_id": event.get("location_id", ""),
                "oldbalanceOrg": event.get("oldbalanceOrg", ""),
                "newbalanceOrig": event.get("newbalanceOrig", ""),
                "oldbalanceDest": event.get("oldbalanceDest", ""),
                "newbalanceDest": event.get("newbalanceDest", ""),
                "is_fraud": event.get("is_fraud", ""),
                "is_flagged_fraud": event.get("is_flagged_fraud", ""),
                "score": prediction.get("score", ""),
                "raw_probability": prediction.get("raw_probability", ""),
                "route": prediction.get("route", ""),
                "latency_ms": prediction.get("latency_ms", ""),
                "priority_bucket": _pending_priority_bucket(row),
                "action": action,
                "reviewer_note": agent.get("reviewer_note") or row.get("reason", ""),
                "fallback_used": agent.get("fallback_used", ""),
                "validation_attempts": agent.get("validation_attempts", ""),
                "human_readable_explanation": agent.get("human_readable_explanation", ""),
                "analyst_report": agent.get("analyst_report", ""),
                "dashboard_summary": agent.get("dashboard_summary", ""),
                "top_model_features": _compact_explanation(prediction.get("explanation")),
                "tool_results_json": _json_cell(agent.get("tool_results")),
                "structured_output_json": _json_cell(structured_output),
                "agent_output_json": _json_cell(agent_output),
                "extras_json": _json_cell(event.get("extras")),
            }
        )
    return export_rows


def _pending_priority_bucket(row: dict[str, Any]) -> str:
    prediction = row.get("prediction", {})
    route = str(prediction.get("route", ""))
    score = float(prediction.get("score", 0.0) or 0.0)
    raw_probability = float(prediction.get("raw_probability", 0.0) or 0.0)
    if route == "high" or score >= 0.65 or raw_probability >= 0.5:
        return "high"
    if score >= 0.5:
        return "watch"
    return "normal"


def _xml_text(value: Any) -> str:
    text = "" if value is None else str(value)
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _xlsx_col(index: int) -> str:
    letters = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        letters = chr(65 + remainder) + letters
    return letters


def _xlsx_cell(row_index: int, col_index: int, value: Any) -> str:
    ref = f"{_xlsx_col(col_index)}{row_index}"
    if value is None or value == "":
        return f'<c r="{ref}"/>'
    if isinstance(value, bool):
        return f'<c r="{ref}" t="b"><v>{1 if value else 0}</v></c>'
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return f'<c r="{ref}"><v>{value}</v></c>'
    return f'<c r="{ref}" t="inlineStr"><is><t>{_xml_text(value)}</t></is></c>'


def _build_xlsx_bytes(rows: list[dict[str, Any]], *, sheet_name: str = "Pending Reviews") -> bytes:
    headers = list(rows[0].keys()) if rows else ["message"]
    data_rows = rows or [{"message": "Không có pending review."}]

    output = BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        archive.writestr(
            "[Content_Types].xml",
            """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
</Types>""",
        )
        archive.writestr(
            "_rels/.rels",
            """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>""",
        )
        archive.writestr(
            "xl/workbook.xml",
            f"""<?xml version="1.0" encoding="UTF-8"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets>
    <sheet name="{_xml_text(sheet_name)[:31]}" sheetId="1" r:id="rId1"/>
  </sheets>
</workbook>""",
        )
        archive.writestr(
            "xl/_rels/workbook.xml.rels",
            """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
</Relationships>""",
        )
        with archive.open("xl/worksheets/sheet1.xml", "w") as sheet:
            sheet.write(
                b'<?xml version="1.0" encoding="UTF-8"?>'
                b'<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                b'<sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>'
                b'<sheetData>'
            )
            header_xml = "".join(_xlsx_cell(1, col_index, header) for col_index, header in enumerate(headers, start=1))
            sheet.write(f'<row r="1">{header_xml}</row>'.encode("utf-8"))
            for row_index, row in enumerate(data_rows, start=2):
                row_xml = "".join(
                    _xlsx_cell(row_index, col_index, row.get(header, ""))
                    for col_index, header in enumerate(headers, start=1)
                )
                sheet.write(f'<row r="{row_index}">{row_xml}</row>'.encode("utf-8"))
            sheet.write(b"</sheetData><autoFilter ref=\"A1:")
            sheet.write(f"{_xlsx_col(len(headers))}{len(data_rows) + 1}".encode("utf-8"))
            sheet.write(b'"/></worksheet>')
    return output.getvalue()


def _pending_reviews_xlsx_response() -> Response:
    rows = read_pending_reviews()
    export_rows = _pending_review_export_rows(rows)
    content = _build_xlsx_bytes(export_rows)
    filename = f"pending_reviews_full_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.xlsx"
    return Response(
        content=content,
        media_type=XLSX_MEDIA_TYPE,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _event_from_payload_or_400(payload: TransactionIn, default_source: str) -> TransactionEvent:
    try:
        return payload.to_event(default_source=default_source)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def create_app() -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        runner = FraudFlowRunner()
        bootstrapped_rows = runner.bootstrap_online_history(
            rows=_startup_bootstrap_rows(runner.model_service.metadata)
        )
        app.state.runner = runner
        app.state.bootstrapped_rows = bootstrapped_rows
        try:
            yield
        finally:
            runner.close()

    tag_metadata = [
        {
            "name": "Cổng giao dịch",
            "description": "Nhận giao dịch mới và trả về score, route, explanation, final action.",
        },
        {
            "name": "Xác minh",
            "description": "Đọc hàng đợi review và ghi quyết định xác minh thủ công.",
        },
        {
            "name": "Giám sát",
            "description": "Health check, dashboard, metrics và trạng thái hệ thống.",
        },
        {
            "name": "Triển khai",
            "description": "Kiểm tra model active, promote candidate và rollback version.",
        },
    ]

    app = FastAPI(
        title="Cổng Gian Lận Fraud Flow",
        version=UI_VERSION,
        summary="Cổng phát hiện gian lận ưu tiên PaySim với XGBoost, Redis lookup, SHAP và lớp điều tra ReAct ở nhánh trung bình.",
        description=(
            "API cho hệ thống phát hiện gian lận theo 4 giai đoạn: huấn luyện offline, "
            "xử lý realtime, điều tra ở nhánh trung bình và feedback/retrain."
        ),
        docs_url=None,
        redoc_url=None,
        openapi_tags=tag_metadata,
        lifespan=lifespan,
    )
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    def home() -> str:
        return _render_home_html(app)

    @app.get("/favicon.ico", include_in_schema=False)
    def favicon() -> Response:
        return Response(status_code=204)

    @app.get("/transaction/form", response_class=HTMLResponse, include_in_schema=False)
    def transaction_form() -> str:
        return _render_transaction_form_html(app)

    @app.get("/docs", response_class=HTMLResponse, include_in_schema=False)
    def docs_portal() -> str:
        return _render_docs_portal(app)

    @app.get("/research", response_class=HTMLResponse, include_in_schema=False)
    def research() -> str:
        return _render_research_html(app)

    @app.get("/swagger-ui", include_in_schema=False)
    def swagger_ui() -> HTMLResponse:
        return _render_swagger_ui_html(app)

    @app.get("/swagger-vi.js", include_in_schema=False)
    def swagger_vi_js() -> Response:
        return Response(
            SWAGGER_VI_JS_PATH.read_text(encoding="utf-8"),
            media_type="application/javascript",
            headers={"Cache-Control": "no-store, max-age=0"},
        )

    @app.get(
        "/health",
        tags=["Giám sát"],
        summary="Kiểm tra service health",
        description="Trả về trạng thái service và số dòng lịch sử đã bootstrap vào online feature store.",
    )
    def health() -> dict[str, Any]:
        return {"status": "ok", "bootstrapped_rows": app.state.bootstrapped_rows}

    @app.get("/gateway/transaction", response_class=HTMLResponse, include_in_schema=False)
    def gateway_transaction_help() -> str:
        return _render_method_help_html(
            app,
            endpoint_path="/gateway/transaction",
            method="POST",
            title="Endpoint này dùng để chấm 1 giao dịch, không phải để mở trực tiếp trên trình duyệt.",
            subtitle=(
                "Bạn vừa mở endpoint bằng trình duyệt nên trình duyệt gửi GET, trong khi hệ thống chỉ nhận POST. "
                "Hãy dùng /docs hoặc Swagger để gửi JSON đúng cách."
            ),
            example_payload=PAYSIM_EXAMPLE,
        )

    @app.post(
        "/gateway/transaction",
        tags=["Cổng giao dịch"],
        summary="Chấm một giao dịch realtime",
        description=(
            "Nhận một transaction event, lookup đặc trưng online, tính score, route thấp/trung bình/cao "
            "và trả về quyết định cuối cùng. Endpoint này phải được gọi bằng POST qua /docs, Swagger hoặc curl."
        ),
    )
    def ingest_transaction(payload: TransactionIn, background_tasks: BackgroundTasks) -> dict[str, Any]:
        event = _event_from_payload_or_400(payload, app.state.runner.model_service.source)
        runner: FraudFlowRunner = app.state.runner

        lookup, prediction = runner.quick_predict(event)

        if prediction.route == "medium":
            # Trả về ngay lập tức, đẩy agent sang background
            runner.feature_store.observe_activity(event)
            runner.review_events[event.tx_id] = event
            background_tasks.add_task(runner.run_medium_agent_task, event, lookup, prediction)
            return {
                "tx_id": event.tx_id,
                "route": "medium",
                "final_action": "pending_review",
                "message": "Đang chuyển LLM Agent điều tra",
            }

        # Low / high: xử lý đồng bộ bình thường (không có agent)
        result = runner.process_event(
            event,
            actual_label=event.is_fraud,
            apply_feedback_immediately=False,
        )
        return result.to_dict()

    @app.get("/gateway/transactions", response_class=HTMLResponse, include_in_schema=False)
    def gateway_transactions_help() -> str:
        return _render_method_help_html(
            app,
            endpoint_path="/gateway/transactions",
            method="POST",
            title="Endpoint này dùng để chấm nhiều giao dịch cùng lúc.",
            subtitle=(
                "Đây là endpoint batch. Nếu mở trực tiếp trên trình duyệt, bạn sẽ dùng sai phương thức. "
                "Hãy gửi POST với một mảng JSON qua /docs hoặc curl."
            ),
            example_payload=[PAYSIM_EXAMPLE],
        )

    @app.post(
        "/gateway/transactions",
        tags=["Cổng giao dịch"],
        summary="Chấm nhiều giao dịch trong một request",
        description=(
            "Phiên bản batch của gateway dùng để thử nghiệm hoặc backfill số lượng nhỏ. "
            "Endpoint này phải được gọi bằng POST với một mảng JSON."
        ),
    )
    def ingest_transactions(payload: list[TransactionIn]) -> dict[str, Any]:
        results = []
        for index, item in enumerate(payload):
            try:
                event = _event_from_payload_or_400(item, app.state.runner.model_service.source)
            except HTTPException as exc:
                raise HTTPException(status_code=exc.status_code, detail={"index": index, "error": exc.detail}) from exc
            results.append(
                app.state.runner.process_event(
                    event,
                    actual_label=event.is_fraud,
                    apply_feedback_immediately=False,
                ).to_dict()
            )
        return {"count": len(results), "results": results}

    @app.get(
        "/reviews/pending",
        tags=["Xác minh"],
        summary="Đọc hàng đợi manual review",
        description="Trả về các giao dịch đang chờ analyst xác minh sau khi đi qua nhánh trung bình.",
        response_model=None,
    )
    def pending_reviews(
        request: Request,
        limit: int | None = 50,
        format: Literal["html", "json", "xlsx"] | None = None,
    ) -> HTMLResponse | dict[str, Any]:
        if format == "xlsx":
            return _pending_reviews_xlsx_response()

        accept = request.headers.get("accept", "")
        wants_json = format == "json" or ("application/json" in accept and format != "html")
        if not wants_json:
            return HTMLResponse(_render_pending_reviews_html(app, queue_limit=limit))

        rows = read_pending_reviews()
        if limit is not None:
            limit = max(1, min(int(limit), 1000))
            rows = rows[:limit]
        return {"count": len(rows), "items": rows}

    @app.get(
        "/reviews/pending.xlsx",
        tags=["Xác minh"],
        summary="Xuất toàn bộ review queue ra XLSX",
        description="Tải file Excel đầy đủ tất cả giao dịch đang nằm trong hàng đợi manual review.",
        response_model=None,
    )
    def pending_reviews_xlsx() -> Response:
        return _pending_reviews_xlsx_response()

    @app.post(
        "/reviews/{tx_id}",
        tags=["Xác minh"],
        summary="Ghi quyết định review thủ công",
        description="Người phân tích xác nhận approve, review tiếp hoặc block cho một giao dịch đang nằm trong review queue.",
    )
    def review_transaction(tx_id: str, payload: ReviewDecisionIn) -> dict[str, Any]:
        pending = {row["event"]["tx_id"] for row in read_pending_reviews()}
        if tx_id not in pending:
            raise HTTPException(status_code=404, detail="Giao dịch này hiện không nằm trong hàng đợi review.")
        response = submit_manual_review(
            tx_id=tx_id,
            action=payload.action,
            reviewer=payload.reviewer,
            note=payload.note,
            actual_label=payload.actual_label,
        )
        response["runtime_feedback_applied"] = app.state.runner.apply_feedback(tx_id, payload.actual_label)
        return response

    @app.get(
        "/dashboard",
        tags=["Giám sát"],
        summary="Lấy dashboard data ở dạng JSON",
        description="Dữ liệu tổng hợp cho dashboard: metrics offline, route share, review queue, drift alerts và deployment state.",
    )
    def dashboard_json(tx_id: str | None = None, queue_limit: int | None = None) -> dict[str, Any]:
        data = build_dashboard_data(focus_tx_id=tx_id, queue_limit=queue_limit)
        bootstrapped_rows = getattr(app.state, "bootstrapped_rows", 0)
        data["bootstrapped_rows"] = bootstrapped_rows
        data["bootstrapped_rows_label"] = _format_bootstrapped_rows_label(bootstrapped_rows)
        return data

    @app.get(
        "/dashboard/html",
        tags=["Giám sát"],
        summary="Xem dashboard HTML",
        description="Bản dashboard trực quan để theo dõi model active, metrics, route split, predictions gần nhất và queue review.",
        response_class=HTMLResponse,
    )
    def dashboard_html(tx_id: str | None = None, queue_limit: int | None = None) -> str:
        data = build_dashboard_data(focus_tx_id=tx_id, queue_limit=queue_limit)
        bootstrapped_rows = getattr(app.state, "bootstrapped_rows", 0)
        data["bootstrapped_rows"] = bootstrapped_rows
        data["bootstrapped_rows_label"] = _format_bootstrapped_rows_label(bootstrapped_rows)
        return render_dashboard_html(data)

    @app.get(
        "/deployment/status",
        tags=["Triển khai"],
        summary="Xem trạng thái deploy",
        description="Trả về active version, candidate version, rollback version và deployment strategy hiện tại.",
    )
    def deployment_status() -> dict[str, Any]:
        return DeploymentManager().status()

    @app.post(
        "/deployment/promote",
        tags=["Triển khai"],
        summary="Promote candidate thành active",
        description="Dùng khi muốn đẩy model candidate hiện tại lên active version qua API.",
    )
    def deployment_promote(reason: str = "Promote thủ công qua API.") -> dict[str, Any]:
        return DeploymentManager().promote_candidate(reason=reason)

    @app.post(
        "/deployment/rollback",
        tags=["Triển khai"],
        summary="Rollback về version trước",
        description="Trả hệ thống về rollback version gần nhất nếu cần khôi phục model cũ.",
    )
    def deployment_rollback(reason: str = "Rollback thủ công qua API.") -> dict[str, Any]:
        return DeploymentManager().rollback(reason=reason)

    return app
