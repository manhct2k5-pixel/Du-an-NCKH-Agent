from __future__ import annotations

from collections import Counter
from typing import Any


FEATURE_LABELS = {
    "amount_log1p": "log số tiền giao dịch",
    "oldbalanceOrg": "số dư tài khoản nguồn trước giao dịch",
    "newbalanceOrig": "số dư tài khoản nguồn sau giao dịch",
    "oldbalanceDest": "số dư tài khoản đích trước giao dịch",
    "newbalanceDest": "số dư tài khoản đích sau giao dịch",
    "balance_diff": "độ lệch biến động số dư",
    "amount_ratio": "tỷ lệ số tiền trên số dư",
    "org_balance_delta_ratio": "tỷ lệ thay đổi số dư tài khoản nguồn",
    "hour_of_day": "khung giờ giao dịch",
    "is_night_tx": "cờ giao dịch ban đêm",
    "recipient_new_flag": "cờ người nhận mới",
    "tx_count_24h": "tần suất giao dịch 24 giờ",
    "avg_amount_7d": "mức chi tiêu trung bình 7 ngày",
    "device_tx_count_24h": "tần suất giao dịch theo thiết bị",
    "location_tx_count_24h": "tần suất giao dịch theo khu vực",
    "merchant_tx_count_24h": "tần suất giao dịch theo merchant",
    "location_fraud_rate": "tỷ lệ gian lận của khu vực",
    "ip_fraud_rate": "tỷ lệ gian lận của IP",
    "merchant_fraud_rate": "tỷ lệ gian lận của merchant",
    "llm_risk_score": "điểm phân tích rủi ro kiểu LLM",
    "llm_reason_count": "số lượng lý do rủi ro do lớp LLM-style tạo ra",
    "llm_high_risk_flag": "cờ nguy cơ cao từ lớp LLM-style",
    "llm_review_flag": "cờ cần review từ lớp LLM-style",
    "llm_category_hash": "nhóm mẫu rủi ro do lớp LLM-style gán",
}

# Reason codes theo 5 nhóm nghiệp vụ
REASON_GROUPS = {
    "transaction_risk": [
        "velocity_spike",
        "amount_anomaly",
        "balance_drain",
        "night_transaction",
        "new_recipient",
        "medium_branch_review",
    ],
    "device_risk": [
        "new_device",
        "device_step_up",
        "device_reuse",
    ],
    "ip_risk": [
        "ip_risk",
        "ip_blacklisted",
        "ip_high_fraud_rate",
    ],
    "merchant_risk": [
        "merchant_risk",
        "merchant_high_risk",
        "card_history_risk",
        "risky_location",
    ],
    "anomaly_risk": [
        "anomaly_detected",
        "anomaly_high_score",
    ],
}

REASON_LABELS = {
    # transaction_risk
    "velocity_spike": "tần suất giao dịch 24 giờ đạt ngưỡng cảnh báo",
    "amount_anomaly": "số tiền giao dịch bất thường so với lịch sử",
    "balance_drain": "tài khoản nguồn bị rút cạn sau giao dịch",
    "night_transaction": "giao dịch thực hiện trong khung giờ đêm bất thường",
    "new_recipient": "người nhận chưa từng xuất hiện trong lịch sử",
    "medium_branch_review": "giao dịch nằm trong vùng cần đánh giá thêm",
    # device_risk
    "new_device": "thiết bị chưa có giao dịch trong cửa sổ 24 giờ",
    "device_step_up": "thiết bị cần xác minh tăng cường",
    "device_reuse": "thiết bị có dấu hiệu dùng chung bất thường",
    # ip_risk
    "ip_risk": "IP có mức rủi ro đáng chú ý",
    "ip_blacklisted": "IP nằm trong danh sách đen nội bộ",
    "ip_high_fraud_rate": "IP có tỷ lệ gian lận lịch sử cao",
    # merchant_risk
    "merchant_risk": "merchant có tín hiệu rủi ro",
    "merchant_high_risk": "merchant có tỷ lệ gian lận cao",
    "card_history_risk": "lịch sử thẻ từng có gian lận",
    "risky_location": "khu vực có lịch sử gian lận cao",
    # anomaly_risk
    "anomaly_detected": "giao dịch lệch chuẩn so với phân bố bình thường",
    "anomaly_high_score": "điểm bất thường vượt ngưỡng cảnh báo của anomaly sidecar",
    # system
    "parser_fallback": "hệ thống chuyển sang review để đảm bảo an toàn khi parser không chắc chắn",
}


def group_reason_codes(codes: list[str]) -> dict[str, list[str]]:
    """Nhóm reason codes theo 5 nhóm nghiệp vụ để hiển thị có cấu trúc."""
    code_set = set(codes)
    grouped: dict[str, list[str]] = {}
    for group, members in REASON_GROUPS.items():
        matched = [c for c in members if c in code_set]
        if matched:
            grouped[group] = matched
    # Các code không thuộc nhóm nào
    known = {c for members in REASON_GROUPS.values() for c in members}
    others = [c for c in codes if c not in known]
    if others:
        grouped["other"] = others
    return grouped


def _friendly_feature(name: str) -> str:
    return FEATURE_LABELS.get(name, name.replace("_", " "))


def _friendly_reason(code: str) -> str:
    return REASON_LABELS.get(code, code.replace("_", " "))


def build_transaction_narrative(
    *, event: dict[str, Any], lookup: dict[str, Any], prediction: dict[str, Any],
    final_action: str, final_note: str, agent: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Render observed facts after the final policy decision, without a model call."""
    tx_id = str(event.get("tx_id", "unknown"))
    route = str(prediction.get("route", "unknown"))
    score = float(prediction.get("score", 0.0))
    raw = prediction.get("raw_probability")
    anomaly_score = float(prediction.get("anomaly_score") or 0.0)
    anomaly_flag = bool(prediction.get("anomaly_flag", False))
    structured = (agent or {}).get("agent_output", {}).get("structured_output", {})
    reason_codes = list(dict.fromkeys(structured.get("reason_codes", []) or []))
    if anomaly_flag and "anomaly_high_score" not in reason_codes:
        reason_codes.append("anomaly_high_score")
    tools = (agent or {}).get("tool_results") or {}
    supporting: list[dict[str, str]] = []
    mitigating: list[dict[str, str]] = []

    def add(target: list[dict[str, str]], text: str, source: str) -> None:
        target.append({"text": text, "source": source})

    device = tools.get("verify_device_id") or {}
    if lookup.get("device_tx_count_24h") == 0:
        detail = "Thiết bị chưa có giao dịch trong cửa sổ 24 giờ"
        source = "lookup.device_tx_count_24h"
        if device.get("needs_step_up") is True:
            detail += "; công cụ thiết bị đề nghị xác minh bổ sung"
            source += ", tool_results.verify_device_id.needs_step_up"
        add(supporting, detail + ".", source)
    elif device.get("needs_step_up") is True:
        add(supporting, "Công cụ thiết bị đề nghị xác minh bổ sung.", "tool_results.verify_device_id.needs_step_up")
    if lookup.get("tx_count_24h", 0) >= 3:
        add(supporting, f"Thẻ có {lookup['tx_count_24h']} giao dịch trong 24 giờ.", "lookup.tx_count_24h")
    for key, label, threshold in [("location_fraud_rate", "Khu vực", .03), ("ip_fraud_rate", "IP", .03), ("merchant_fraud_rate", "Đơn vị nhận", .02)]:
        if lookup.get(key, 0) >= threshold:
            add(supporting, f"{label} có tỷ lệ gian lận lịch sử {lookup[key]:.2%}.", "lookup." + key)
    ip = tools.get("check_ip_blacklist") or {}
    if ip.get("blacklisted") is True:
        add(supporting, "IP nằm trong danh sách đen nội bộ.", "tool_results.check_ip_blacklist.blacklisted")
    elif ip.get("blacklisted") is False:
        add(mitigating, "IP không nằm trong danh sách đen nội bộ; điều này chưa chứng minh giao dịch an toàn.", "tool_results.check_ip_blacklist.blacklisted")
    card = tools.get("get_card_history") or {}
    if card.get("historical_fraud_rate", 0) >= .05:
        add(supporting, f"Thẻ có tỷ lệ gian lận lịch sử {card['historical_fraud_rate']:.2%}.", "tool_results.get_card_history.historical_fraud_rate")
    merchant = tools.get("query_merchant_risk") or {}
    if merchant.get("merchant_fraud_rate", 0) >= .1 and lookup.get("merchant_fraud_rate", 0) < .02:
        add(supporting, f"Công cụ ghi nhận tỷ lệ gian lận lịch sử của đơn vị nhận {merchant['merchant_fraud_rate']:.2%}.", "tool_results.query_merchant_risk.merchant_fraud_rate")
    if anomaly_flag:
        add(supporting, "Bộ phát hiện bất thường đã bật cảnh báo; đây chưa phải nhãn gian lận.", "prediction.anomaly_flag")

    actions = {"approve": "Thông qua", "review": "Giữ để xác minh", "block": "Chặn", "step_up": "Yêu cầu xác minh tăng cường"}
    routes = {"low": "thấp", "medium": "trung bình", "high": "cao"}
    headline = f"{actions.get(final_action, final_action)}. Điểm vận hành {score:.3f} thuộc nhánh {routes.get(route, route)}"
    headline += f"; xác suất gốc XGBoost {float(raw):.4%}." if raw is not None else "; chưa có xác suất gốc trong log."
    if final_action == "review" and route == "high":
        decision_reason = "Chốt xác minh theo chính sách bảo vệ khi điểm phân luồng cao nhưng xác suất gốc chưa đủ để tự động chặn."
    elif final_action == "review":
        decision_reason = "Chốt xác minh sau điều tra để analyst kiểm tra thêm trước khi kết luận."
    elif final_action == "step_up":
        decision_reason = "Chốt xác minh tăng cường theo chính sách xử lý tín hiệu bất thường."
    elif final_action == "block":
        decision_reason = "Chốt chặn theo chính sách rủi ro; quyết định này chưa xác nhận nhãn gian lận thực tế."
    elif route == "low":
        decision_reason = "Chính sách nhánh thấp cho phép tự động thông qua, bỏ qua điều tra ReAct."
    else:
        decision_reason = "Chốt thông qua sau điều tra và kiểm tra chính sách."
    facts = " ".join(item["text"] for item in supporting[:2])
    human = " ".join(part for part in [headline, facts, decision_reason] if part)
    model_evidence = [
        {"feature": item.get("feature", "unknown"), "label": _friendly_feature(str(item.get("feature", "unknown"))),
         "impact": float(item.get("impact", 0)),
         "direction": "tăng" if float(item.get("impact", 0)) > 0 else "giảm" if float(item.get("impact", 0)) < 0 else "trung tính"}
        for item in (prediction.get("explanation") or [])[:3]
    ]
    analyst = [human, f"Mã giao dịch: {tx_id}."]
    analyst += [f"{item['text']} [Nguồn: {item['source']}]" for item in supporting + mitigating]
    if model_evidence:
        analyst.append("SHAP mô tả đóng góp trên thang đầu ra mô hình, không phải phần trăm xác suất.")
    if agent:
        analyst.append("Confidence của agent chưa được hiệu chuẩn; không phải độ chính xác hay xác suất gian lận.")
    return {
        "human_readable_explanation": human,
        "analyst_report": " ".join(analyst),
        "dashboard_summary": f"{tx_id}: {route.upper()} → {final_action.upper()} | điểm vận hành {score:.3f}",
        "reason_codes": reason_codes, "reason_codes_grouped": group_reason_codes(reason_codes),
        "anomaly_score": anomaly_score, "anomaly_flag": anomaly_flag,
        "supporting_evidence": supporting, "mitigating_evidence": mitigating, "model_evidence": model_evidence,
        "decision_reason": decision_reason, "policy_note": final_note, "explanation_source": "grounded_template_v2",
    }


def build_dashboard_report(
    *,
    profile: dict[str, Any],
    deployment: dict[str, Any],
    offline_metrics: dict[str, Any],
    live_metrics: dict[str, Any],
    routes: dict[str, int],
    actions: dict[str, int],
    pending_reviews: list[dict[str, Any]],
    drift_alerts: list[dict[str, Any]],
    recent_predictions: list[dict[str, Any]],
) -> dict[str, str]:
    source = str(profile.get("source", "unknown")).upper()
    active_version = deployment.get("active_version", "N/A")
    total_route = sum(routes.values()) or 1
    dominant_route = max(routes.items(), key=lambda item: item[1])[0] if routes else "unknown"
    dominant_share = (routes.get(dominant_route, 0) / total_route) * 100 if routes else 0.0

    executive_summary = (
        f"Hệ thống hiện đang chạy trên nguồn dữ liệu {source} với model active {active_version}. "
        f"Trên tập test offline, mô hình đạt AUC {offline_metrics.get('auc', 'N/A')} và F1 {offline_metrics.get('f1', 'N/A')}. "
        f"Trong cửa sổ giao dịch gần nhất, nhánh {dominant_route} chiếm ưu thế khoảng {dominant_share:.1f}%."
    )

    analyst_summary = (
        f"Pending review hiện có {len(pending_reviews)} giao dịch; drift alerts mới là {len(drift_alerts)}; "
        f"lượt mô phỏng gần nhất xử lý {live_metrics.get('processed_transactions', 0)} giao dịch với latency trung bình "
        f"{live_metrics.get('avg_ms', 'N/A')}."
    )

    action_counter = Counter(actions)
    action_phrase = ", ".join(f"{label}={count}" for label, count in action_counter.items()) if action_counter else "chưa có dữ liệu action"
    nckh_summary = (
        f"Ở góc nhìn báo cáo NCKH, pipeline cho thấy mô hình lõi hoạt động ổn định trên {source}, "
        f"trong khi lớp route và agent giữ vai trò chuyển kết quả kỹ thuật thành quyết định vận hành. "
        f"Phân bổ quyết định gần đây gồm {action_phrase}."
    )

    recent_story = (
        " | ".join(row.get("dashboard_summary", "") for row in recent_predictions[:3]) if recent_predictions else "Chưa có giao dịch gần nhất để tóm tắt."
    )

    return {
        "executive_summary": executive_summary,
        "analyst_summary": analyst_summary,
        "nckh_summary": nckh_summary,
        "recent_story": recent_story,
    }
