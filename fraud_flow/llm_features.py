from __future__ import annotations

from typing import Any

from .schema import FeatureLookup, TransactionEvent


def build_transaction_llm_analysis(event: TransactionEvent, lookup: FeatureLookup) -> dict[str, Any]:
    """Deterministic LLM-style transaction analysis used for reproducible features.

    The project plan emphasizes an LLM analysis layer that returns a transaction risk score,
    reasons, and a semantic category. For the research pipeline we keep this stage fully
    reproducible and offline-friendly by synthesizing the same outputs from transaction context.
    """

    source = event.extras.get("source", "paysim")
    reasons: list[str] = []
    score = 0.03

    if event.tx_type.upper() == "TRANSFER":
        score += 0.16
        reasons.append("transfer_channel")
    elif event.tx_type.upper() == "CASH_OUT":
        score += 0.12
        reasons.append("cashout_channel")

    if lookup.tx_count_24h >= 3:
        score += min(0.25, 0.06 * lookup.tx_count_24h)
        reasons.append("velocity_spike")

    if lookup.device_tx_count_24h == 0:
        score += 0.10
        reasons.append("new_device")

    if lookup.location_tx_count_24h == 0:
        score += 0.05
        reasons.append("new_location")

    if lookup.merchant_tx_count_24h <= 1:
        score += 0.05
        reasons.append("new_counterparty")

    avg_amount = max(lookup.avg_amount_7d, 1.0)
    relative_amount = event.amount / avg_amount
    if relative_amount >= 5:
        score += 0.20
        reasons.append("amount_spike")
    elif relative_amount >= 2:
        score += 0.10
        reasons.append("amount_above_pattern")

    if source == "paysim":
        if event.oldbalanceDest == 0 and event.tx_type.upper() in {"TRANSFER", "CASH_OUT"}:
            score += 0.08
            reasons.append("new_recipient")
        if event.newbalanceOrig == 0 and event.amount > 0:
            score += 0.05
            reasons.append("balance_drained")
        if event.oldbalanceOrg > 0 and event.amount / max(event.oldbalanceOrg, 1.0) >= 0.9:
            score += 0.08
            reasons.append("near_full_balance_transfer")
    else:
        if event.extras.get("DeviceType", "").lower() == "mobile":
            score += 0.04
            reasons.append("mobile_risk_context")
        if event.extras.get("P_emaildomain") and event.extras.get("P_emaildomain") != event.extras.get("R_emaildomain"):
            score += 0.03
            reasons.append("email_mismatch")

    if lookup.location_fraud_rate >= 0.02:
        score += min(0.18, lookup.location_fraud_rate * 2.5)
        reasons.append("risky_location")

    if lookup.ip_fraud_rate >= 0.02:
        score += min(0.18, lookup.ip_fraud_rate * 2.5)
        reasons.append("risky_ip")

    if lookup.merchant_fraud_rate >= 0.015:
        score += min(0.16, lookup.merchant_fraud_rate * 3.0)
        reasons.append("risky_merchant")

    score = round(min(score, 0.99), 6)

    if score >= 0.75:
        category = "critical_fraud_pattern"
    elif "velocity_spike" in reasons:
        category = "velocity_anomaly"
    elif "amount_spike" in reasons or "near_full_balance_transfer" in reasons:
        category = "amount_anomaly"
    elif "new_device" in reasons or "new_location" in reasons or "new_counterparty" in reasons:
        category = "entity_shift"
    elif "risky_location" in reasons or "risky_ip" in reasons or "risky_merchant" in reasons:
        category = "contextual_risk"
    else:
        category = "normal_pattern"

    if not reasons:
        reasons.append("normal_pattern")

    return {
        "risk_score": score,
        "reason_codes": reasons,
        "reason_count": len(reasons),
        "category": category,
        "high_risk_flag": int(score >= 0.70),
        "review_flag": int(0.30 <= score < 0.70),
    }
