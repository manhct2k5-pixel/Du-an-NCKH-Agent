from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from .config import APP_CONFIG
from .narratives import FEATURE_LABELS, REASON_LABELS, build_dashboard_report, build_transaction_narrative
from .web_ui import UI_VERSION, render_template


ROUTE_LABELS = {
    "low": "Thấp",
    "medium": "Trung bình",
    "high": "Cao",
}

ACTION_LABELS = {
    "approve": "Thông qua",
    "review": "Xem xét",
    "block": "Chặn",
    "step_up": "Xác minh tăng cường",
}

ACTION_TONES = {
    "approve": "success",
    "review": "warning",
    "block": "danger",
    "step_up": "info",
}

ROUTE_TONES = {
    "low": "success",
    "medium": "warning",
    "high": "danger",
}

TOOL_LABELS = {
    "get_card_history": "Card History",
    "check_ip_blacklist": "IP Blacklist",
    "verify_device_id": "Device Verification",
    "query_merchant_risk": "Merchant Risk",
}

DEFAULT_REVIEW_QUEUE_CARD_LIMIT = 6
MAX_REVIEW_QUEUE_CARD_LIMIT = 100


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _load_json(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _display_label(label: str, label_type: str) -> str:
    if label_type == "route":
        return ROUTE_LABELS.get(label, label)
    if label_type == "action":
        return ACTION_LABELS.get(label, label)
    return label


def _build_breakdown(counter: Counter[str], palette: dict[str, str], *, label_type: str) -> list[dict[str, Any]]:
    total = sum(counter.values())
    if total == 0:
        return []

    rows: list[dict[str, Any]] = []
    for label, count in counter.items():
        rows.append(
            {
                "label": label,
                "display_label": _display_label(label, label_type),
                "count": count,
                "share": round((count / total) * 100, 1),
                "color": palette.get(label, "#74c7ff"),
            }
        )
    rows.sort(key=lambda row: row["count"], reverse=True)
    return rows


def _friendly_reason(code: str) -> str:
    return REASON_LABELS.get(code, code.replace("_", " "))


def _friendly_feature(name: str) -> str:
    return FEATURE_LABELS.get(name, name.replace("_", " "))


def _action_tone(action: str) -> str:
    return ACTION_TONES.get(action, "neutral")


def _route_tone(route: str) -> str:
    return ROUTE_TONES.get(route, "neutral")


def _review_priority_bucket(row: dict[str, Any]) -> int:
    prediction = row.get("prediction", {})
    route = str(prediction.get("route", ""))
    score = float(prediction.get("score", 0.0) or 0.0)
    raw_probability = float(prediction.get("raw_probability", 0.0) or 0.0)
    if route == "high" or score >= 0.65 or raw_probability >= 0.5:
        return 2
    if score >= 0.5:
        return 1
    return 0


def _review_priority_key(row: dict[str, Any]) -> tuple[int, float, str, str]:
    prediction = row.get("prediction", {})
    event = row.get("event", {})
    return (
        _review_priority_bucket(row),
        float(prediction.get("score", 0.0) or 0.0),
        str(event.get("timestamp", "")),
        str(event.get("tx_id", "")),
    )


def _format_share(part: int, total: int) -> str:
    if total <= 0:
        return "N/A"
    return f"{(part / total) * 100:.1f}%"


def _safe_ratio(numerator: int, denominator: int) -> float | None:
    if denominator < 0:
        return None
    if denominator == 0:
        return 0.0
    return numerator / denominator


def _safe_f1_from_rates(precision: float | None, recall: float | None) -> float | None:
    if precision is None or recall is None:
        return None
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def _format_metric_value(value: float | None) -> str:
    return f"{value:.4f}" if value is not None else "N/A"


def _format_amount(value: Any) -> str:
    try:
        return f"{float(value):,.2f}"
    except (TypeError, ValueError):
        return "N/A"


def _format_probability(value: Any) -> str:
    try:
        return f"{float(value) * 100:.4f}%"
    except (TypeError, ValueError):
        return "N/A"


def _format_trace_value(key: str, value: Any) -> str:
    if isinstance(value, bool):
        return "Có" if value else "Không"
    if isinstance(value, float):
        if "rate" in key:
            return f"{value:.2%}"
        if value >= 1000:
            return f"{value:,.2f}"
        return f"{value:.4f}".rstrip("0").rstrip(".")
    return str(value)


def _summarize_observation(observation: dict[str, Any]) -> str:
    if not observation:
        return "Không có observation bổ sung từ tool."

    labels = {
        "blacklisted": "Blacklist",
        "is_new_device": "Thiết bị mới",
        "needs_step_up": "Step-up",
        "tx_count_24h": "Tx 24h",
        "device_tx_count_24h": "Device tx 24h",
        "historical_tx_count": "Lịch sử",
        "historical_fraud_rate": "Fraud rate lịch sử",
        "merchant_fraud_rate": "Merchant fraud rate",
        "ip_fraud_rate": "IP fraud rate",
        "location_fraud_rate": "Zone fraud rate",
        "avg_amount_7d": "Avg amount 7d",
    }
    priority_keys = [
        "blacklisted",
        "is_new_device",
        "needs_step_up",
        "tx_count_24h",
        "device_tx_count_24h",
        "historical_tx_count",
        "historical_fraud_rate",
        "merchant_fraud_rate",
        "ip_fraud_rate",
        "location_fraud_rate",
        "avg_amount_7d",
    ]

    parts: list[str] = []
    for key in priority_keys:
        if key in observation:
            parts.append(f"{labels.get(key, key)}: {_format_trace_value(key, observation[key])}")
        if len(parts) == 3:
            break
    if parts:
        return " | ".join(parts)

    fallback: list[str] = []
    for key, value in observation.items():
        if key in {"tool", "labeled_tx_count", "historical_fraud_count"}:
            continue
        fallback.append(f"{key}: {_format_trace_value(key, value)}")
        if len(fallback) == 3:
            break
    return " | ".join(fallback) if fallback else "Tool chạy xong nhưng chưa có tín hiệu nổi bật để hiển thị."


def _build_signal_lists(
    prediction: dict[str, Any],
    reason_labels: list[str],
    evidence: list[str],
) -> tuple[list[str], list[str]]:
    strengths: list[str] = []
    concerns: list[str] = []

    for label in reason_labels[:2]:
        concerns.append(f"Agent flag: {label}.")

    for item in prediction.get("explanation", [])[:5]:
        feature = _friendly_feature(str(item.get("feature", "unknown_feature")))
        impact = float(item.get("impact", 0.0))
        line = f"{feature} {'giảm' if impact < 0 else 'tăng'} score rủi ro ({impact:+.4f})."
        if impact < 0 and len(strengths) < 3:
            strengths.append(line)
        elif impact > 0 and len(concerns) < 4:
            concerns.append(line)

    filtered_evidence = [item for item in evidence if not str(item).startswith("SHAP signal:")]
    for item in filtered_evidence[:3]:
        if len(concerns) >= 4:
            break
        concerns.append(item)

    if not strengths:
        strengths.append("Chưa có feature nào đẩy score rủi ro tăng mạnh trong top tín hiệu.")
    if not concerns:
        concerns.append("Chưa xuất hiện cờ cảnh báo nổi bật ngoài score tổng hợp.")
    return strengths[:3], concerns[:3]


def _build_workflow_nodes(row: dict[str, Any]) -> list[dict[str, str]]:
    event = row["event"]
    prediction = row["prediction"]
    route = prediction.get("route", "unknown")
    final_action = row.get("final_action") or row.get("agent", {}).get("action", "review")
    final_note = row.get("final_note") or row.get("agent", {}).get("reviewer_note", "")
    structured = row.get("agent", {}).get("agent_output", {}).get("structured_output", {})
    monitoring_flags = row.get("monitoring_flags", []) or []

    nodes = [
        {
            "title": "Input Signals",
            "detail": f"{event.get('tx_type', 'N/A')} | {_format_amount(event.get('amount', 0.0))}",
            "state": "neutral",
        },
        {
            "title": "Model Scoring",
            "detail": f"score {float(prediction.get('score', 0.0)):.3f} | route {str(route).upper()}",
            "state": _route_tone(str(route)),
        },
    ]

    if row.get("agent"):
        nodes.append(
            {
                "title": "Agent Review",
                "detail": structured.get("summary") or row["agent"].get("reviewer_note", "Đã gom evidence từ tools."),
                "state": "warning",
            }
        )
    else:
        nodes.append(
            {
                "title": "Agent Review",
                "detail": "Bypass vì route này không cần điều tra thêm.",
                "state": "muted",
            }
        )

    nodes.append(
        {
            "title": "Final Decision",
            "detail": final_note or ACTION_LABELS.get(final_action, final_action),
            "state": _action_tone(str(final_action)),
        }
    )
    nodes.append(
        {
            "title": "Monitoring",
            "detail": (
                " | ".join(flag.replace("_", " ") for flag in monitoring_flags[:2])
                if monitoring_flags else "Không có drift/flag mới trong case này."
            ),
            "state": "danger" if monitoring_flags else "neutral",
        }
    )
    return nodes


def _build_llm_trace(row: dict[str, Any], narrative: dict[str, str]) -> list[dict[str, str]]:
    prediction = row["prediction"]
    route = str(prediction.get("route", "unknown"))
    final_action = row.get("final_action") or row.get("agent", {}).get("action", "review")
    final_note = row.get("final_note") or row.get("agent", {}).get("reviewer_note", "")
    agent = row.get("agent") or {}
    structured = agent.get("agent_output", {}).get("structured_output", {})
    intermediate_steps = list(agent.get("intermediate_steps") or agent.get("agent_output", {}).get("intermediate_steps", []) or [])
    confidence = structured.get("confidence")
    confidence_text = f"Confidence {float(confidence):.1%}" if confidence is not None else "Confidence N/A"

    trace = [
        {
            "kind": "llm",
            "label": "LLM THOUGHT",
            "title": "Reasoning summary",
            "body": narrative.get("human_readable_explanation", "Chưa có giải thích tự nhiên cho case này."),
            "meta": (
                f"Score {float(prediction.get('score', 0.0)):.3f} | "
                f"Raw prob {_format_probability(prediction.get('raw_probability'))} | "
                f"Route {route.upper()}"
            ),
        }
    ]

    for step in intermediate_steps[:4]:
        trace.append(
            {
                "kind": "done",
                "label": "DONE",
                "title": TOOL_LABELS.get(step.get("tool", ""), step.get("tool", "Tool")),
                "body": _summarize_observation(step.get("observation", {})),
                "meta": f"Input: {step.get('tool_input', 'N/A')}",
            }
        )

    evidence = list(structured.get("evidence", []) or [])
    if evidence:
        trace.append(
            {
                "kind": "note",
                "label": "EVIDENCE",
                "title": "Merged signals",
                "body": " | ".join(evidence[:3]),
                "meta": confidence_text,
            }
        )

    trace.append(
        {
            "kind": _action_tone(str(final_action)),
            "label": "FINAL",
            "title": ACTION_LABELS.get(final_action, final_action),
            "body": final_note or structured.get("summary") or narrative.get("analyst_report", "Hệ thống đã hoàn tất quyết định."),
            "meta": f"Route {route.upper()} -> {str(final_action).upper()}",
        }
    )
    return trace


def _adapt_queue_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "event": row["event"],
        "lookup": {},
        "prediction": row["prediction"],
        "final_action": row.get("agent", {}).get("action", "review"),
        "final_note": row.get("agent", {}).get("reviewer_note", ""),
        "agent": row.get("agent"),
        "narrative": {
            "human_readable_explanation": row.get("human_readable_explanation", ""),
            "analyst_report": row.get("analyst_report", ""),
            "dashboard_summary": row.get("dashboard_summary", ""),
        },
        "actual_label": row["event"].get("is_fraud"),
        "monitoring_flags": [],
        "end_to_end_latency_ms": row["prediction"].get("latency_ms"),
    }


def _queue_note(row: dict[str, Any]) -> str:
    agent = row.get("agent") or {}
    if agent.get("reviewer_note"):
        return str(agent["reviewer_note"])
    if row.get("reason") == "high_score_low_raw_probability":
        return "Score cao nhưng raw probability chưa đủ chắc, nên tạm giữ để analyst xác minh trước khi block."
    return "Case đang nằm trong review queue và chờ analyst xử lý."


def _build_review_queue_cards(
    pending_reviews: list[dict[str, Any]],
    *,
    focus_tx_id: str,
    limit: int = DEFAULT_REVIEW_QUEUE_CARD_LIMIT,
) -> list[dict[str, Any]]:
    cards: list[dict[str, Any]] = []
    for row in sorted(pending_reviews, key=_review_priority_key, reverse=True)[:limit]:
        prediction = row.get("prediction", {})
        event = row.get("event", {})
        action = row.get("agent", {}).get("action", "review")
        bucket = _review_priority_bucket(row)
        cards.append(
            {
                "tx_id": event.get("tx_id", "N/A"),
                "tx_type": event.get("tx_type", "N/A"),
                "amount": _format_amount(event.get("amount", 0.0)),
                "timestamp": event.get("timestamp", "N/A"),
                "score": f"{float(prediction.get('score', 0.0)):.3f}",
                "route_label": ROUTE_LABELS.get(str(prediction.get("route", "")), str(prediction.get("route", "N/A"))),
                "route_tone": _route_tone(str(prediction.get("route", ""))),
                "action_label": ACTION_LABELS.get(action, action),
                "action_tone": _action_tone(action),
                "note": _queue_note(row),
                "priority_label": "Ưu tiên cao" if bucket == 2 else ("Theo dõi sớm" if bucket == 1 else "Theo thứ tự"),
                "priority_tone": "danger" if bucket == 2 else ("warning" if bucket == 1 else "neutral"),
                "is_focus": event.get("tx_id") == focus_tx_id,
            }
        )
    return cards


def _coerce_queue_limit(limit: int | None) -> int:
    if limit is None:
        return DEFAULT_REVIEW_QUEUE_CARD_LIMIT
    return max(1, min(int(limit), MAX_REVIEW_QUEUE_CARD_LIMIT))


def _next_queue_limit(current_limit: int, total: int) -> int:
    if total <= current_limit:
        return current_limit
    return min(total, max(current_limit * 2, 20), MAX_REVIEW_QUEUE_CARD_LIMIT)


def _build_queue_overview(
    pending_reviews: list[dict[str, Any]],
    *,
    focus_tx_id: str,
    displayed_count: int,
    display_limit: int,
) -> dict[str, Any]:
    priority_cases = sum(1 for row in pending_reviews if _review_priority_bucket(row) == 2)
    monitored_cases = sum(1 for row in pending_reviews if _review_priority_bucket(row) >= 1)
    total = len(pending_reviews)
    hidden_cases = max(total - displayed_count, 0)
    return {
        "total": total,
        "priority": priority_cases,
        "watchlist": monitored_cases,
        "displayed": displayed_count,
        "hidden": hidden_cases,
        "limit": display_limit,
        "next_limit": _next_queue_limit(display_limit, total),
        "can_show_more": hidden_cases > 0 and display_limit < min(total, MAX_REVIEW_QUEUE_CARD_LIMIT),
        "reached_dashboard_cap": hidden_cases > 0 and display_limit >= MAX_REVIEW_QUEUE_CARD_LIMIT,
        "other_cases": max(total - (1 if focus_tx_id and focus_tx_id != "Không có dữ liệu" else 0), 0),
    }


def _find_focus_row_by_tx_id(
    predictions: list[dict[str, Any]],
    pending_reviews: list[dict[str, Any]],
    *,
    focus_tx_id: str | None,
) -> dict[str, Any] | None:
    if not focus_tx_id:
        return None

    for row in reversed(predictions):
        if row["event"]["tx_id"] == focus_tx_id:
            return row

    for row in reversed(pending_reviews):
        if row["event"]["tx_id"] == focus_tx_id:
            return _adapt_queue_row(row)

    return None


def _select_focus_row(
    predictions: list[dict[str, Any]],
    pending_reviews: list[dict[str, Any]],
    *,
    focus_tx_id: str | None = None,
) -> dict[str, Any] | None:
    explicit_focus = _find_focus_row_by_tx_id(predictions, pending_reviews, focus_tx_id=focus_tx_id)
    if explicit_focus is not None:
        return explicit_focus

    if pending_reviews:
        target = max(pending_reviews, key=_review_priority_key)
        target_id = target["event"]["tx_id"]
        for row in reversed(predictions):
            if row["event"]["tx_id"] == target_id:
                return row
        return _adapt_queue_row(target)

    for row in reversed(predictions):
        if row.get("agent"):
            return row
    return predictions[-1] if predictions else None


def _build_product_story(
    *,
    recent_predictions: list[dict[str, Any]],
    action_counter: Counter[str],
    pending_reviews: list[dict[str, Any]],
    focus_case: dict[str, Any],
    deployment: dict[str, Any],
    live_metrics: dict[str, Any],
    route_window: int,
    requested_focus_tx_id: str | None,
) -> dict[str, Any]:
    automated_count = int(action_counter.get("approve", 0)) + int(action_counter.get("block", 0))
    review_count = int(action_counter.get("review", 0))
    pending_count = len(pending_reviews)

    if pending_count == 0:
        queue_health_label = "Queue trống"
        queue_health_tone = "success"
        queue_health_note = "Analyst không có backlog tồn đọng."
    elif pending_count <= 25:
        queue_health_label = "Ổn định"
        queue_health_tone = "success"
        queue_health_note = "Backlog còn trong vùng kiểm soát, có thể demo analyst flow mà không gây quá tải."
    elif pending_count <= 150:
        queue_health_label = "Cần theo dõi"
        queue_health_tone = "warning"
        queue_health_note = "Review queue đang dày lên, nên sản phẩm cần cho thấy rõ cơ chế ưu tiên case."
    else:
        queue_health_label = "Tồn đọng cao"
        queue_health_tone = "danger"
        queue_health_note = "Backlog analyst đang cao, rất phù hợp để kể câu chuyện queue và spotlight case."

    latest_case = recent_predictions[0] if recent_predictions else None
    latest_case_label = latest_case["tx_id"] if latest_case else "Chưa có dữ liệu"
    latest_case_note = (
        f"{latest_case.get('action_label', 'N/A')} • {latest_case.get('route_label', 'N/A')} • {latest_case.get('timestamp', 'N/A')}"
        if latest_case else "Hãy gửi một transaction để tạo case thật cho live demo."
    )

    system_status_label = "Demo live" if recent_predictions else "Chờ dữ liệu"
    system_status_tone = "success" if recent_predictions else "neutral"
    if recent_predictions and pending_count > 150:
        system_status_label = "Queue dày"
        system_status_tone = "warning"

    direct_focus = bool(requested_focus_tx_id and focus_case.get("tx_id") == requested_focus_tx_id)
    operator_prompt = (
        f"Đang spotlight trực tiếp case {focus_case.get('tx_id', 'N/A')} vừa mở từ live demo."
        if direct_focus else
        "Dashboard đang tự chọn case quan trọng nhất để kể câu chuyện vận hành."
    )

    return {
        "system_status_label": system_status_label,
        "system_status_tone": system_status_tone,
        "operations_mode": "Realtime scoring + analyst queue",
        "automation_rate": _format_share(automated_count, route_window),
        "review_share": _format_share(review_count, route_window),
        "queue_health_label": queue_health_label,
        "queue_health_tone": queue_health_tone,
        "queue_health_note": queue_health_note,
        "latest_case_label": latest_case_label,
        "latest_case_note": latest_case_note,
        "active_version": deployment.get("active_version") or "N/A",
        "avg_latency": live_metrics.get("avg_ms", "N/A"),
        "pending_reviews": pending_count,
        "focus_tx_id": focus_case.get("tx_id", "Không có dữ liệu"),
        "direct_focus": direct_focus,
        "operator_prompt": operator_prompt,
        "demo_playbook": [
            {
                "step": "01",
                "title": "Gửi một transaction thật",
                "detail": "Tạo score, route và final action ngay từ transaction form.",
            },
            {
                "step": "02",
                "title": "Mở đúng case trên dashboard",
                "detail": "Dashboard nên nhảy thẳng tới case vừa chạy để người xem theo được end-to-end flow.",
            },
            {
                "step": "03",
                "title": "Chứng minh API và backlog",
                "detail": "Docs và review queue giúp chứng minh đây là sản phẩm có gateway thật và analyst flow thật.",
            },
        ],
        "proof_points": [
            {
                "label": "Automation gần đây",
                "value": _format_share(automated_count, route_window),
                "tone": "success" if route_window and automated_count else "neutral",
                "detail": "Tỷ lệ case được approve hoặc block tự động trong cửa sổ recent.",
            },
            {
                "label": "Queue health",
                "value": queue_health_label,
                "tone": queue_health_tone,
                "detail": queue_health_note,
            },
            {
                "label": "Case gần nhất",
                "value": latest_case_label,
                "tone": "neutral",
                "detail": latest_case_note,
            },
        ],
    }


def _build_focus_case(row: dict[str, Any] | None) -> dict[str, Any]:
    if row is None:
        return {
            "tx_id": "Không có dữ liệu",
            "title": "Chưa có giao dịch gần đây để spotlight",
            "tx_type": "N/A",
            "amount": "N/A",
            "summary": "Hãy chạy mô phỏng hoặc gửi một giao dịch qua form để dashboard có case để trình bày.",
            "analyst_report": "",
            "action_label": "Chờ dữ liệu",
            "action_tone": "neutral",
            "route_label": "N/A",
            "route_tone": "neutral",
            "score": "N/A",
            "raw_probability": "N/A",
            "reason_badges": [],
            "fields": [],
            "key_strengths": [],
            "key_concerns": [],
            "workflow_nodes": [],
            "llm_trace": [],
            "llm_mode": "Chưa có reasoning trace",
            "monitoring_flags": [],
        }

    event = row["event"]
    prediction = row["prediction"]
    route = str(prediction.get("route", "unknown"))
    final_action = row.get("final_action") or row.get("agent", {}).get("action", "review")
    final_note = row.get("final_note") or row.get("agent", {}).get("reviewer_note", "")
    narrative = row.get("narrative") or build_transaction_narrative(
        event=event,
        lookup=row.get("lookup", {}),
        prediction=prediction,
        final_action=final_action,
        final_note=final_note,
        agent=row.get("agent"),
    )
    structured = row.get("agent", {}).get("agent_output", {}).get("structured_output", {})
    reason_labels = [_friendly_reason(code) for code in list(structured.get("reason_codes", []) or [])]
    evidence = list(structured.get("evidence", []) or [])
    key_strengths, key_concerns = _build_signal_lists(prediction, reason_labels, evidence)

    return {
        "tx_id": event.get("tx_id", "N/A"),
        "title": f"{event.get('tx_type', 'N/A')} {_format_amount(event.get('amount', 0.0))}",
        "tx_type": event.get("tx_type", "N/A"),
        "amount": _format_amount(event.get("amount", 0.0)),
        "summary": narrative.get("human_readable_explanation", "Chưa có summary cho case này."),
        "analyst_report": narrative.get("analyst_report", ""),
        "source": event.get("extras", {}).get("source", "N/A"),
        "timestamp": event.get("timestamp", "N/A"),
        "score": f"{float(prediction.get('score', 0.0)):.3f}",
        "raw_probability": _format_probability(prediction.get("raw_probability")),
        "route": route,
        "route_label": ROUTE_LABELS.get(route, route),
        "route_tone": _route_tone(route),
        "action": final_action,
        "action_label": ACTION_LABELS.get(final_action, final_action),
        "action_tone": _action_tone(str(final_action)),
        "latency": (
            f"{float(row.get('end_to_end_latency_ms', prediction.get('latency_ms', 0.0))):.2f} ms"
            if row.get("end_to_end_latency_ms") is not None or prediction.get("latency_ms") is not None else "N/A"
        ),
        "reason_badges": reason_labels[:4],
        "fields": [
            {"label": "Card ID", "value": event.get("card_id", "N/A")},
            {"label": "Device", "value": event.get("device_id", "N/A")},
            {"label": "Merchant", "value": event.get("merchant_id", "N/A")},
            {"label": "Location", "value": event.get("location_id", "N/A")},
            {"label": "Timestamp", "value": event.get("timestamp", "N/A")},
        ],
        "key_strengths": key_strengths,
        "key_concerns": key_concerns,
        "workflow_nodes": _build_workflow_nodes(row),
        "llm_trace": _build_llm_trace(row, narrative),
        "llm_mode": "ReAct / agent reasoning trace" if row.get("agent") else "Auto decision trace",
        "monitoring_flags": row.get("monitoring_flags", []) or [],
    }


_dataset_preview_cache: dict[tuple[str, str], tuple[list[str], list[dict[str, Any]]]] = {}


def _build_dataset_preview(source: str, data_path: str, limit: int = 5) -> tuple[list[str], list[dict[str, Any]]]:
    cache_key = (source, data_path)
    if cache_key in _dataset_preview_cache:
        return _dataset_preview_cache[cache_key]

    path = Path(data_path)
    if not path.exists():
        return [], []

    if source == "paysim":
        frame = pd.read_csv(path, nrows=80)
        frame = frame[frame["type"].isin(["TRANSFER", "CASH_OUT"])].head(limit).copy()
        columns = ["step", "type", "amount", "nameOrig", "nameDest", "isFraud"]
        for column in columns:
            if column in frame.columns and column == "amount":
                frame[column] = frame[column].map(lambda value: f"{float(value):,.2f}")
        result = columns, frame.to_dict(orient="records")
    else:
        frame = pd.read_csv(path, nrows=limit)
        columns = [
            column for column in ["TransactionID", "TransactionDT", "TransactionAmt", "ProductCD", "isFraud"]
            if column in frame.columns
        ]
        result = columns, frame[columns].to_dict(orient="records")

    _dataset_preview_cache[cache_key] = result
    return result


def _format_latency(latency: dict[str, Any], key: str) -> str:
    value = latency.get(key)
    if value is None:
        return "N/A"
    return f"{float(value):.2f} ms"


def _prediction_row_for_dashboard(row: dict[str, Any]) -> dict[str, Any]:
    narrative = row.get("narrative") or build_transaction_narrative(
        event=row["event"],
        lookup=row.get("lookup", {}),
        prediction=row["prediction"],
        final_action=row["final_action"],
        final_note=row.get("final_note", ""),
        agent=row.get("agent"),
    )
    route = row["prediction"]["route"]
    action = row["final_action"]
    return {
        "tx_id": row["event"]["tx_id"],
        "tx_type": row["event"]["tx_type"],
        "amount": f"{row['event']['amount']:,.2f}",
        "score": f"{row['prediction']['score']:.6f}",
        "raw_probability": f"{row['prediction'].get('raw_probability', 0.0):.6f}",
        "route": route,
        "route_label": ROUTE_LABELS.get(route, route),
        "action": action,
        "action_label": ACTION_LABELS.get(action, action),
        "actual_label": row.get("actual_label", "N/A"),
        "dashboard_summary": narrative["dashboard_summary"],
    }


def read_pending_reviews() -> list[dict[str, Any]]:
    queued = load_jsonl(APP_CONFIG.outputs.manual_review_queue_path)
    decided = load_jsonl(APP_CONFIG.outputs.manual_review_decisions_path)
    decided_ids = {row["tx_id"] for row in decided}
    return [row for row in queued if row["event"]["tx_id"] not in decided_ids]


def submit_manual_review(
    tx_id: str,
    action: str,
    reviewer: str,
    note: str,
    actual_label: int | None = None,
) -> dict[str, Any]:
    payload = {
        "tx_id": tx_id,
        "action": action,
        "reviewer": reviewer,
        "note": note,
        "actual_label": actual_label,
        "reviewed_at": datetime.now(timezone.utc).isoformat(),
    }
    append_jsonl(APP_CONFIG.outputs.manual_review_decisions_path, payload)
    if actual_label is not None:
        append_jsonl(
            APP_CONFIG.outputs.feedback_log_path,
            {
                "tx_id": tx_id,
                "actual_label": actual_label,
                "predicted_action": action,
                "score": None,
                "source": "manual_review",
            },
        )
    return payload


def build_dashboard_data(*, focus_tx_id: str | None = None, queue_limit: int | None = None) -> dict[str, Any]:
    training = _load_json(APP_CONFIG.outputs.training_report_path)
    simulation = _load_json(APP_CONFIG.outputs.simulation_report_path)
    deployment = _load_json(APP_CONFIG.outputs.deployment_state_path)
    active_metadata_path = Path(deployment["active_metadata_path"]) if deployment.get("active_metadata_path") else None
    active_metadata = _load_json(active_metadata_path)

    predictions = load_jsonl(APP_CONFIG.outputs.prediction_log_path)
    feedback = load_jsonl(APP_CONFIG.outputs.feedback_log_path)
    pending_reviews = read_pending_reviews()
    review_decisions = load_jsonl(APP_CONFIG.outputs.manual_review_decisions_path)
    high_risk = load_jsonl(APP_CONFIG.outputs.high_risk_log_path)
    drift_alerts = load_jsonl(APP_CONFIG.outputs.drift_alert_log_path)[-10:]

    route_counter = Counter(row["prediction"]["route"] for row in predictions[-500:])
    action_counter = Counter(row["final_action"] for row in predictions[-500:])
    route_palette = {"low": "#7bdd8c", "medium": "#f6bf57", "high": "#ff8176"}
    action_palette = {"approve": "#7bdd8c", "review": "#f6bf57", "block": "#ff8176"}

    simulation_window = int(simulation.get("processed_transactions", 0) or 0)
    latest_simulation_rows = predictions[-simulation_window:] if simulation_window > 0 else []
    labeled_simulation_rows = [row for row in latest_simulation_rows if row.get("actual_label") is not None]
    fraud_rows = [row for row in labeled_simulation_rows if int(row.get("actual_label", 0)) == 1]
    normal_rows = [row for row in labeled_simulation_rows if int(row.get("actual_label", 0)) == 0]
    true_positive_blocks = sum(
        1 for row in labeled_simulation_rows
        if int(row.get("actual_label", 0)) == 1 and row.get("final_action") == "block"
    )
    false_positive_blocks = sum(
        1 for row in labeled_simulation_rows
        if int(row.get("actual_label", 0)) == 0 and row.get("final_action") == "block"
    )
    true_negative_passes = sum(
        1 for row in labeled_simulation_rows
        if int(row.get("actual_label", 0)) == 0 and row.get("final_action") != "block"
    )
    false_negative_misses = sum(
        1 for row in labeled_simulation_rows
        if int(row.get("actual_label", 0)) == 1 and row.get("final_action") != "block"
    )
    fallback_precision_block = (
        _safe_ratio(true_positive_blocks, true_positive_blocks + false_positive_blocks)
        if labeled_simulation_rows else None
    )
    fallback_recall_block = (
        _safe_ratio(true_positive_blocks, true_positive_blocks + false_negative_misses)
        if labeled_simulation_rows else None
    )
    fallback_f1_block = (
        _safe_f1_from_rates(fallback_precision_block, fallback_recall_block)
        if labeled_simulation_rows else None
    )

    recent_predictions = [_prediction_row_for_dashboard(row) for row in reversed(predictions[-12:])]
    recent_fraud_transactions = [_prediction_row_for_dashboard(row) for row in reversed(fraud_rows[-12:])]
    recent_false_positive_blocks = [
        _prediction_row_for_dashboard(row)
        for row in reversed(
            [
                row for row in labeled_simulation_rows
                if int(row.get("actual_label", 0)) == 0 and row.get("final_action") == "block"
            ][-12:]
        )
    ]
    focus_case = _build_focus_case(_select_focus_row(predictions, pending_reviews, focus_tx_id=focus_tx_id))
    review_queue_limit = _coerce_queue_limit(queue_limit)
    review_queue_cards = _build_review_queue_cards(
        pending_reviews,
        focus_tx_id=focus_case["tx_id"],
        limit=review_queue_limit,
    )
    queue_overview = _build_queue_overview(
        pending_reviews,
        focus_tx_id=focus_case["tx_id"],
        displayed_count=len(review_queue_cards),
        display_limit=review_queue_limit,
    )
    recent_case_cards = [
        {
            **row,
            "is_focus": row["tx_id"] == focus_case["tx_id"],
            "action_tone": _action_tone(row["action"]),
            "route_tone": _route_tone(row["route"]),
        }
        for row in recent_predictions[:4]
    ]

    drift_summary = simulation.get("drift_flags", {})
    drift_summary_text = ", ".join(f"{key}: {value}" for key, value in drift_summary.items()) if drift_summary else "không có"
    model_profile = active_metadata or training
    _model_trained = bool(model_profile)
    source = model_profile.get("source", simulation.get("source", "unknown"))
    data_path = model_profile.get("data_path", "")
    routing_thresholds = model_profile.get("routing_thresholds", {})
    low_threshold = routing_thresholds.get("low", APP_CONFIG.routing.low)
    high_threshold = routing_thresholds.get("high", APP_CONFIG.routing.high)
    split = model_profile.get("split", {})
    test_metrics = model_profile.get("test_metrics", {})

    evaluation_report = _load_json(APP_CONFIG.outputs.evaluation_report_path)
    _eval_test = evaluation_report.get("test", {})
    _eval_val = evaluation_report.get("validation", {})
    test_confusion_matrix = _eval_test.get("confusion_matrix", {})
    validation_confusion_matrix = _eval_val.get("confusion_matrix", {})
    test_pr_auc = round(_eval_test.get("pr_auc", 0.0), 6) if _eval_test.get("pr_auc") is not None else "N/A"
    validation_pr_auc = round(_eval_val.get("pr_auc", 0.0), 6) if _eval_val.get("pr_auc") is not None else "N/A"
    validation_metrics_raw = model_profile.get("validation_metrics", {})
    dataset_preview_columns, dataset_preview = _build_dataset_preview(source, data_path)

    dashboard_report = build_dashboard_report(
        profile={"source": source, "data_path": data_path or "N/A"},
        deployment=deployment,
        offline_metrics={
            "auc": round(test_metrics.get("auc", 0.0), 4) if model_profile else "N/A",
            "precision": round(test_metrics.get("precision", 0.0), 4) if model_profile else "N/A",
            "recall": round(test_metrics.get("recall", 0.0), 4) if model_profile else "N/A",
            "f1": round(test_metrics.get("f1", 0.0), 4) if model_profile else "N/A",
        },
        live_metrics={
            "processed_transactions": simulation.get("processed_transactions", 0),
            "avg_ms": _format_latency(simulation.get("latency", {}), "avg_ms") if simulation.get("latency") else "N/A",
        },
        routes=dict(route_counter),
        actions=dict(action_counter),
        pending_reviews=pending_reviews,
        drift_alerts=drift_alerts,
        recent_predictions=recent_predictions,
    )
    spotlight_metrics = [
        {"label": "Tổng prediction", "value": len(predictions)},
        {"label": "Pending review", "value": len(pending_reviews)},
        {"label": "High-risk async", "value": len(high_risk)},
        {
            "label": "Latency trung bình",
            "value": _format_latency(simulation.get("latency", {}), "avg_ms") if simulation.get("latency") else "N/A",
        },
    ]
    simulation_metrics = simulation.get("metrics", {})
    precision_block = simulation_metrics.get("precision_block")
    recall_block = simulation_metrics.get("recall_block")
    f1_block = simulation_metrics.get("f1_block")
    if precision_block is None:
        precision_block = fallback_precision_block
    if recall_block is None:
        recall_block = fallback_recall_block
    if f1_block is None:
        f1_block = fallback_f1_block

    evaluation_status = "sẵn sàng" if labeled_simulation_rows else "chưa sẵn sàng"
    if labeled_simulation_rows and simulation_metrics.get("auc") is None and len({row.get("actual_label") for row in labeled_simulation_rows}) < 2:
        evaluation_status = "1 lớp nhãn"

    live_metrics = {
        "processed_transactions": simulation.get("processed_transactions", 0),
        "avg_ms": _format_latency(simulation.get("latency", {}), "avg_ms") if simulation.get("latency") else "N/A",
        "p95_ms": _format_latency(simulation.get("latency", {}), "p95_ms") if simulation.get("latency") else "N/A",
        "model_avg_ms": _format_latency(simulation.get("latency", {}), "model_avg_ms") if simulation.get("latency") else "N/A",
        "model_p95_ms": _format_latency(simulation.get("latency", {}), "model_p95_ms") if simulation.get("latency") else "N/A",
        "evaluation_status": evaluation_status,
        "positive_count": simulation_metrics.get("positive_count", len(fraud_rows)),
        "negative_count": simulation_metrics.get("negative_count", len(normal_rows)),
        "precision_block": _format_metric_value(precision_block),
        "recall_block": _format_metric_value(recall_block),
        "f1_block": _format_metric_value(f1_block),
        "drift_summary": drift_summary_text,
    }
    route_window = min(len(predictions), 500)
    product_story = _build_product_story(
        recent_predictions=recent_predictions,
        action_counter=action_counter,
        pending_reviews=pending_reviews,
        focus_case=focus_case,
        deployment=deployment,
        live_metrics=live_metrics,
        route_window=route_window,
        requested_focus_tx_id=focus_tx_id,
    )

    return {
        "ui_version": UI_VERSION,
        "current_page": "dashboard",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "totals": {
            "predictions": len(predictions),
            "feedback": len(feedback),
            "pending_reviews": len(pending_reviews),
            "high_risk": len(high_risk),
        },
        "profile": {
            "source": source,
            "data_path": data_path or "N/A",
            "feature_count": len(model_profile.get("feature_columns", [])),
            "sample_size": model_profile.get("sample_size_used", "N/A"),
            "selected_threshold": model_profile.get("selected_threshold", "N/A"),
            "low_threshold": low_threshold,
            "high_threshold": high_threshold,
            "high_raw_probability_floor": APP_CONFIG.routing.high_raw_probability_floor,
            "train_rows": split.get("train_rows", "N/A"),
            "validation_rows": split.get("validation_rows", "N/A"),
            "test_rows": split.get("test_rows", "N/A"),
        },
        "offline_metrics": {
            "auc": round(test_metrics["auc"], 6) if _model_trained and test_metrics.get("auc") is not None else "Chưa train",
            "precision": round(test_metrics["precision"], 6) if _model_trained and test_metrics.get("precision") is not None else "Chưa train",
            "recall": round(test_metrics["recall"], 6) if _model_trained and test_metrics.get("recall") is not None else "Chưa train",
            "f1": round(test_metrics["f1"], 6) if _model_trained and test_metrics.get("f1") is not None else "Chưa train",
            "pr_auc": test_pr_auc if _model_trained else "Chưa train",
        },
        "validation_metrics": {
            "auc": round(validation_metrics_raw["auc"], 6) if validation_metrics_raw and validation_metrics_raw.get("auc") is not None else "Chưa train",
            "precision": round(validation_metrics_raw["precision"], 6) if validation_metrics_raw and validation_metrics_raw.get("precision") is not None else "Chưa train",
            "recall": round(validation_metrics_raw["recall"], 6) if validation_metrics_raw and validation_metrics_raw.get("recall") is not None else "Chưa train",
            "f1": round(validation_metrics_raw["f1"], 6) if validation_metrics_raw and validation_metrics_raw.get("f1") is not None else "Chưa train",
            "pr_auc": validation_pr_auc if validation_metrics_raw else "Chưa train",
        },
        "test_confusion_matrix": test_confusion_matrix,
        "validation_confusion_matrix": validation_confusion_matrix,
        "live_metrics": live_metrics,
        "simulation_summary": {
            "processed_transactions": simulation_window,
            "labeled_transactions": len(labeled_simulation_rows),
            "fraud_transactions": len(fraud_rows),
            "normal_transactions": len(normal_rows),
            "true_positive_blocks": true_positive_blocks,
            "false_positive_blocks": false_positive_blocks,
            "true_negative_passes": true_negative_passes,
            "false_negative_misses": false_negative_misses,
        },
        "route_window": route_window,
        "route_breakdown": _build_breakdown(route_counter, route_palette, label_type="route"),
        "action_breakdown": _build_breakdown(action_counter, action_palette, label_type="action"),
        "focus_case": focus_case,
        "recent_case_cards": recent_case_cards,
        "review_queue_cards": review_queue_cards,
        "queue_overview": queue_overview,
        "spotlight_metrics": spotlight_metrics,
        "product_story": product_story,
        "deployment": deployment,
        "selected_params": model_profile.get("selected_params", {}),
        "pending_reviews": [
            {
                **row,
                "agent": (
                    {
                        **row["agent"],
                        "action_label": ACTION_LABELS.get(
                            row["agent"].get("action", "review"),
                            row["agent"].get("action", "review"),
                        ),
                    }
                    if row.get("agent") else None
                ),
            }
            for row in pending_reviews[-8:]
        ],
        "review_decisions": [
            {**row, "action_label": ACTION_LABELS.get(row.get("action", ""), row.get("action", ""))}
            for row in reversed(review_decisions[-8:])
        ],
        "recent_predictions": recent_predictions,
        "recent_fraud_transactions": recent_fraud_transactions,
        "recent_false_positive_blocks": recent_false_positive_blocks,
        "drift_alerts": drift_alerts,
        "recent_high_risk": list(reversed(high_risk[-8:])),
        "dataset_preview_columns": dataset_preview_columns,
        "dataset_preview": dataset_preview,
        "dashboard_report": dashboard_report,
    }


def build_research_data() -> dict[str, Any]:
    def _fmt(v: float | None, decimals: int = 4) -> str:
        return f"{v:.{decimals}f}" if v is not None else "N/A"

    def _fmt_rows(v: int | float | None) -> str:
        if v is None:
            return "N/A"
        try:
            return f"{int(v):,}"
        except (TypeError, ValueError):
            return "N/A"

    def _fmt_delta(v: float | None) -> str:
        if v is None:
            return "—"
        sign = "+" if v > 0 else ""
        return f"{sign}{v:.4f}"

    baseline_raw = _load_json(APP_CONFIG.outputs.baseline_comparison_path)
    ablation_raw = _load_json(APP_CONFIG.outputs.feature_ablation_path)
    robustness_raw = _load_json(APP_CONFIG.outputs.robustness_validation_path)
    external_raw = _load_json(APP_CONFIG.outputs.external_validation_path)

    research_ready = bool(
        baseline_raw.get("models")
        or ablation_raw.get("ablations")
        or robustness_raw.get("multi_seed_summary")
    )

    # ── Baseline comparison ──────────────────────────────────────
    baseline_rows = []
    for m in baseline_raw.get("models", []):
        t = m.get("test", {})
        tm = t.get("metrics", {})
        baseline_rows.append({
            "name": m.get("model_name", "N/A"),
            "family": m.get("family", ""),
            "features": m.get("feature_count", "N/A"),
            "threshold": m.get("selected_threshold", "N/A"),
            "auc": _fmt(tm.get("auc")),
            "pr_auc": _fmt(t.get("pr_auc"), 4),
            "f1": _fmt(tm.get("f1")),
            "precision": _fmt(tm.get("precision")),
            "recall": _fmt(tm.get("recall")),
            "train_s": f"{m.get('train_seconds', 0):.2f}s",
        })

    # ── Feature ablation ─────────────────────────────────────────
    ablation_rows = []
    for a in ablation_raw.get("ablations", []):
        d = a.get("delta_vs_full", {})
        ablation_rows.append({
            "name": a.get("name", "N/A"),
            "note": a.get("note", ""),
            "features": a.get("feature_count", "N/A"),
            "auc": _fmt(a.get("test_metrics", {}).get("auc")),
            "pr_auc": _fmt(a.get("test_pr_auc"), 4),
            "f1": _fmt(a.get("test_metrics", {}).get("f1")),
            "delta_auc": _fmt_delta(d.get("auc")),
            "delta_f1": _fmt_delta(d.get("f1")),
            "delta_pr_auc": _fmt_delta(d.get("pr_auc")),
            "is_baseline": a.get("name") == "full_feature_set",
        })

    # ── Robustness (multi-seed) ───────────────────────────────────
    robustness_rows = []
    for s in robustness_raw.get("multi_seed_summary", []):
        tm = s.get("test_metrics", {})
        robustness_rows.append({
            "name": s.get("model_name", "N/A"),
            "seeds": ", ".join(str(x) for x in s.get("seeds", [])),
            "auc_mean": _fmt(tm.get("auc", {}).get("mean"), 6),
            "auc_std": _fmt(tm.get("auc", {}).get("std"), 6),
            "f1_mean": _fmt(tm.get("f1", {}).get("mean"), 6),
            "f1_std": _fmt(tm.get("f1", {}).get("std"), 6),
            "recall_mean": _fmt(tm.get("recall", {}).get("mean"), 6),
            "recall_std": _fmt(tm.get("recall", {}).get("std"), 6),
        })

    ci = robustness_raw.get("confidence_intervals", {}).get("xgboost", {})
    xgb_ci = {
        "auc": f"{_fmt(ci.get('auc', {}).get('ci95_low'), 4)} – {_fmt(ci.get('auc', {}).get('ci95_high'), 4)}",
        "f1":  f"{_fmt(ci.get('f1', {}).get('ci95_low'), 4)} – {_fmt(ci.get('f1', {}).get('ci95_high'), 4)}",
        "pr_auc": f"{_fmt(ci.get('pr_auc', {}).get('ci95_low'), 4)} – {_fmt(ci.get('pr_auc', {}).get('ci95_high'), 4)}",
    }

    mcnemar = robustness_raw.get("mcnemar", {})

    # ── External validation ───────────────────────────────────────
    ext_available = bool(external_raw.get("available"))
    ext_source = external_raw.get("source", "N/A")
    ext_validation_mode = external_raw.get("validation_mode", "N/A")
    ext_rows = []
    if ext_available:
        for m in external_raw.get("models", []):
            t = m.get("test", {})
            tm = t.get("metrics", {})
            ext_rows.append({
                "name": m.get("model_name", "N/A"),
                "auc": _fmt(tm.get("auc")),
                "pr_auc": _fmt(t.get("pr_auc"), 4),
                "f1": _fmt(tm.get("f1")),
                "precision": _fmt(tm.get("precision")),
                "recall": _fmt(tm.get("recall")),
            })

    split_raw = baseline_raw.get("split", {})
    total = split_raw.get("total_rows") or 1
    split = {
        **split_raw,
        "train_pct": round(split_raw.get("train_rows", 0) / total * 100, 1),
        "val_pct": round(split_raw.get("validation_rows", 0) / total * 100, 1),
        "test_pct": round(split_raw.get("test_rows", 0) / total * 100, 1),
    }

    ext_split_raw = external_raw.get("split", {})
    ext_total = ext_split_raw.get("total_rows") or ext_split_raw.get("evaluation_rows") or ext_split_raw.get("test_rows") or 1
    ext_split = {
        **ext_split_raw,
        "evaluation_rows_display": _fmt_rows(ext_split_raw.get("evaluation_rows") or ext_total),
        "train_rows_display": _fmt_rows(ext_split_raw.get("train_rows")),
        "validation_rows_display": _fmt_rows(ext_split_raw.get("validation_rows")),
        "test_rows_display": _fmt_rows(ext_split_raw.get("test_rows")),
        "train_pct": round(ext_split_raw.get("train_rows", 0) / ext_total * 100, 1),
        "val_pct": round(ext_split_raw.get("validation_rows", 0) / ext_total * 100, 1),
        "test_pct": round(ext_split_raw.get("test_rows", 0) / ext_total * 100, 1),
    }

    return {
        "research_ready": research_ready,
        "source": baseline_raw.get("source", "N/A"),
        "split": split,
        "baseline_rows": baseline_rows,
        "ablation_rows": ablation_rows,
        "ablation_params": ablation_raw.get("fixed_xgboost_params", {}),
        "robustness_rows": robustness_rows,
        "xgb_ci": xgb_ci,
        "mcnemar": mcnemar,
        "ext_available": ext_available,
        "ext_source": ext_source,
        "ext_validation_mode": ext_validation_mode,
        "ext_rows": ext_rows,
        "ext_split": ext_split,
    }


def render_dashboard_html(data: dict[str, Any]) -> str:
    html = render_template("dashboard.html", version=data.get("ui_version", UI_VERSION), **data)
    APP_CONFIG.outputs.dashboard_html_path.parent.mkdir(parents=True, exist_ok=True)
    APP_CONFIG.outputs.dashboard_html_path.write_text(html, encoding="utf-8")
    return html
