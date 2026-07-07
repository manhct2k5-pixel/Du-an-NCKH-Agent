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
    "velocity_spike": "tần suất giao dịch tăng đột biến",
    "amount_anomaly": "số tiền giao dịch bất thường so với lịch sử",
    "balance_drain": "tài khoản nguồn bị rút cạn sau giao dịch",
    "night_transaction": "giao dịch thực hiện trong khung giờ đêm bất thường",
    "new_recipient": "người nhận chưa từng xuất hiện trong lịch sử",
    "medium_branch_review": "giao dịch nằm trong vùng cần đánh giá thêm",
    # device_risk
    "new_device": "thiết bị mới chưa có lịch sử giao dịch",
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


def _top_feature_lines(prediction: dict[str, Any]) -> list[str]:
    rows = prediction.get("explanation", []) or []
    lines: list[str] = []
    for item in rows[:3]:
        feature = _friendly_feature(str(item.get("feature", "unknown_feature")))
        impact = float(item.get("impact", 0.0))
        direction = "tăng" if impact >= 0 else "giảm"
        lines.append(f"{feature} đang {direction} điểm rủi ro ({impact:+.4f}).")
    return lines


def _lookup_lines(lookup: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    if lookup.get("tx_count_24h", 0) >= 3:
        lines.append(f"Tần suất theo thẻ đạt {lookup['tx_count_24h']} giao dịch trong 24 giờ.")
    if lookup.get("device_tx_count_24h", 0) == 0:
        lines.append("Thiết bị hiện tại chưa có lịch sử giao dịch trong 24 giờ gần nhất.")
    if lookup.get("location_fraud_rate", 0.0) >= 0.03:
        lines.append(f"Khu vực đang có tỷ lệ fraud khoảng {lookup['location_fraud_rate']:.2%}.")
    if lookup.get("ip_fraud_rate", 0.0) >= 0.03:
        lines.append(f"IP đang có tỷ lệ fraud khoảng {lookup['ip_fraud_rate']:.2%}.")
    if lookup.get("merchant_fraud_rate", 0.0) >= 0.02:
        lines.append(f"Merchant đang có tỷ lệ fraud khoảng {lookup['merchant_fraud_rate']:.2%}.")
    return lines


def build_transaction_narrative(
    *,
    event: dict[str, Any],
    lookup: dict[str, Any],
    prediction: dict[str, Any],
    final_action: str,
    final_note: str,
    agent: dict[str, Any] | None = None,
) -> dict[str, str]:
    tx_id = str(event.get("tx_id", "unknown"))
    tx_type = str(event.get("tx_type", "unknown"))
    amount = float(event.get("amount", 0.0))
    score = float(prediction.get("score", 0.0))
    route = str(prediction.get("route", "unknown"))
    anomaly_score = float(prediction.get("anomaly_score") or 0.0)
    anomaly_flag = bool(prediction.get("anomaly_flag", False))

    reason_codes: list[str] = []
    evidence: list[str] = []
    if agent:
        structured = agent.get("agent_output", {}).get("structured_output", {})
        reason_codes = list(structured.get("reason_codes", []) or [])
        evidence = list(structured.get("evidence", []) or [])

    # Tự động thêm anomaly reason code nếu flag bật
    if anomaly_flag and "anomaly_high_score" not in reason_codes:
        reason_codes.append("anomaly_high_score")
    if anomaly_score >= 0.5 and not anomaly_flag and "anomaly_detected" not in reason_codes:
        reason_codes.append("anomaly_detected")

    top_feature_lines = _top_feature_lines(prediction)
    lookup_lines = _lookup_lines(lookup)
    friendly_reasons = [_friendly_reason(code) for code in reason_codes[:4]]
    grouped_codes = group_reason_codes(reason_codes)

    if route == "low":
        headline = (
            f"Giao dịch {tx_id} ({tx_type}, {amount:,.2f}) được xếp vào vùng rủi ro thấp "
            f"với score {score:.6f}, nên hệ thống tự động thông qua."
        )
    elif route == "high":
        headline = (
            f"Giao dịch {tx_id} ({tx_type}, {amount:,.2f}) rơi vào vùng rủi ro cao "
            f"với score {score:.6f}, nên hệ thống chặn ngay để bảo toàn an toàn giao dịch."
        )
    elif final_action == "step_up":
        headline = (
            f"Giao dịch {tx_id} ({tx_type}, {amount:,.2f}) ở vùng trung gian "
            f"với score {score:.6f} và có tín hiệu bất thường — yêu cầu xác minh tăng cường. "
            "Đây KHÔNG phải xác nhận gian lận."
        )
    else:
        headline = (
            f"Giao dịch {tx_id} ({tx_type}, {amount:,.2f}) nằm ở vùng rủi ro trung gian "
            f"với score {score:.6f}, nên được chuyển sang tác tử điều tra để xem xét thêm."
        )

    detail_parts = []
    if friendly_reasons:
        detail_parts.append("Các lý do chính gồm: " + ", ".join(friendly_reasons) + ".")
    if lookup_lines:
        detail_parts.append("Tín hiệu từ feature store: " + " ".join(lookup_lines[:2]))
    if top_feature_lines:
        detail_parts.append("Tín hiệu từ mô hình: " + " ".join(top_feature_lines[:2]))

    human_explanation = " ".join([headline, *detail_parts, final_note]).strip()

    analyst_lines = [
        f"Tx {tx_id}: route={route}, final_action={final_action}, score={score:.6f}.",
        f"Loại giao dịch: {tx_type}; số tiền: {amount:,.2f}.",
        f"Anomaly score: {anomaly_score:.4f} | Flagged: {anomaly_flag}.",
    ]
    if grouped_codes:
        for group, codes in grouped_codes.items():
            labels = ", ".join(_friendly_reason(c) for c in codes)
            analyst_lines.append(f"[{group}] {labels}.")
    if evidence:
        analyst_lines.append("Evidence: " + " | ".join(evidence[:3]))
    elif top_feature_lines:
        analyst_lines.append("Model signals: " + " | ".join(top_feature_lines[:3]))
    analyst_report = " ".join(analyst_lines)

    anomaly_tag = f" | anomaly {anomaly_score:.3f}{'⚠' if anomaly_flag else ''}" if anomaly_score > 0 else ""
    action_display = f"{final_action.upper()}🔐" if final_action == "step_up" else final_action.upper()
    dashboard_summary = (
        f"{tx_id}: {route.upper()} -> {action_display} | "
        f"{tx_type} {amount:,.2f} | score {score:.3f}{anomaly_tag}"
    )

    return {
        "human_readable_explanation": human_explanation,
        "analyst_report": analyst_report,
        "dashboard_summary": dashboard_summary,
        "reason_codes": reason_codes,
        "reason_codes_grouped": grouped_codes,
        "anomaly_score": anomaly_score,
        "anomaly_flag": anomaly_flag,
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
