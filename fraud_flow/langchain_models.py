from __future__ import annotations

import json
import re
from hashlib import sha256
from typing import Any

from langchain_core.language_models.llms import LLM
from pydantic import PrivateAttr

from .narratives import build_transaction_narrative


def extract_json_block(prompt: str, start_marker: str, end_marker: str) -> dict[str, Any]:
    pattern = re.compile(re.escape(start_marker) + r"\s*(.*?)\s*" + re.escape(end_marker), re.DOTALL)
    match = pattern.search(prompt)
    if not match:
        return {}
    return json.loads(match.group(1))


def build_decision_payload(context: dict[str, Any]) -> dict[str, Any]:
    event = context.get("event", {})
    lookup = context.get("lookup", {})
    prediction = context.get("prediction", {})
    tool_results = context.get("tool_results", {})
    agent_summary = context.get("agent_summary", "")

    score = float(prediction.get("score", 0.0))
    explanation = prediction.get("explanation", [])

    reason_codes: list[str] = []
    evidence: list[str] = []

    if lookup.get("tx_count_24h", 0) >= 3:
        reason_codes.append("velocity_spike")
        evidence.append(f"Card velocity is {lookup['tx_count_24h']} tx in 24h.")
    if lookup.get("device_tx_count_24h", 0) == 0:
        reason_codes.append("new_device")
        evidence.append("Device has no prior transactions in the 24h window.")
    if lookup.get("location_fraud_rate", 0.0) >= 0.05:
        reason_codes.append("risky_location")
        evidence.append(f"Location prior fraud rate is {lookup['location_fraud_rate']:.2%}.")
    if lookup.get("ip_fraud_rate", 0.0) >= 0.05:
        reason_codes.append("ip_risk")
        evidence.append(f"IP prior fraud rate is {lookup['ip_fraud_rate']:.2%}.")
    if lookup.get("merchant_fraud_rate", 0.0) >= 0.03:
        reason_codes.append("merchant_risk")
        evidence.append(f"Merchant prior fraud rate is {lookup['merchant_fraud_rate']:.2%}.")

    ip_result = tool_results.get("check_ip_blacklist", {})
    if ip_result.get("blacklisted"):
        reason_codes.append("ip_blacklisted")
        evidence.append("IP is on the internal blacklist based on historical fraud feedback.")

    device_result = tool_results.get("verify_device_id", {})
    if device_result.get("needs_step_up"):
        reason_codes.append("device_step_up")
        evidence.append("Device verification suggests step-up authentication.")

    merchant_result = tool_results.get("query_merchant_risk", {})
    if merchant_result.get("merchant_fraud_rate", 0.0) >= 0.1:
        reason_codes.append("merchant_high_risk")
        evidence.append("Merchant historical fraud rate is above 10%.")

    card_history = tool_results.get("get_card_history", {})
    if card_history.get("historical_fraud_rate", 0.0) >= 0.05:
        reason_codes.append("card_history_risk")
        evidence.append("Card history shows elevated fraud rate.")

    for item in explanation[:3]:
        evidence.append(
            f"SHAP signal: {item['feature']} impact {float(item['impact']):+.4f}."
        )

    if prediction.get("raw_probability", 0.0) >= 0.9 or (
        score >= 0.62 and ("ip_blacklisted" in reason_codes or "merchant_high_risk" in reason_codes)
    ):
        action = "block"
    elif len(set(reason_codes)) >= 2 or score >= 0.45:
        action = "review"
    else:
        action = "approve"

    if not reason_codes:
        reason_codes.append("medium_branch_review")
    if not evidence:
        evidence.append("No strong contradictory evidence was found beyond the model score.")

    if agent_summary:
        summary = agent_summary
    else:
        summary = (
            f"Transaction {event.get('tx_id', 'unknown')} was reviewed on the medium path with "
            f"score={score:.3f}."
        )

    payload = {
        "recommended_action": action,
        "confidence": round(max(0.35, min(0.95, score + 0.15)), 4),
        "summary": summary,
        "reason_codes": sorted(set(reason_codes)),
        "evidence": evidence[:8],
    }
    narrative = build_transaction_narrative(
        event=event,
        lookup=lookup,
        prediction=prediction,
        final_action=action,
        final_note=summary,
        agent={"agent_output": {"structured_output": payload}},
    )
    payload.update(narrative)
    return payload


class HeuristicReActLLM(LLM):
    @property
    def _llm_type(self) -> str:
        return "heuristic-react-llm"

    @property
    def _identifying_params(self) -> dict[str, Any]:
        return {"mode": "react"}

    def _call(
        self,
        prompt: str,
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> str:
        context = extract_json_block(
            prompt,
            "INVESTIGATION_CONTEXT_JSON_START",
            "INVESTIGATION_CONTEXT_JSON_END",
        )
        score = float(context.get("prediction", {}).get("score", 0.0))
        lookup = context.get("lookup", {})
        explanation = context.get("prediction", {}).get("explanation", [])

        tail = prompt.split("INVESTIGATION_CONTEXT_JSON_END", 1)[-1]
        executed_actions = re.findall(r"\nAction:\s*([^\n]+)", tail)

        plan: list[tuple[str, str]] = []
        if lookup.get("tx_count_24h", 0) >= 2 or score >= 0.40:
            plan.append(("get_card_history", context.get("event", {}).get("card_id", "")))
        if lookup.get("ip_fraud_rate", 0.0) >= 0.05 or lookup.get("location_fraud_rate", 0.0) >= 0.05 or score >= 0.55:
            plan.append(("check_ip_blacklist", context.get("event", {}).get("ip_address", "")))
        if lookup.get("device_tx_count_24h", 0) == 0 or any(item.get("feature") == "device_tx_count_24h" for item in explanation):
            plan.append(("verify_device_id", context.get("event", {}).get("device_id", "")))
        if lookup.get("merchant_fraud_rate", 0.0) >= 0.03 or lookup.get("merchant_tx_count_24h", 0) <= 1:
            plan.append(("query_merchant_risk", context.get("event", {}).get("merchant_id", "")))

        if not plan:
            plan.append(("get_card_history", context.get("event", {}).get("card_id", "")))

        for tool_name, tool_input in plan:
            if tool_name not in executed_actions:
                return (
                    "Thought: I should gather one more piece of evidence before deciding.\n"
                    f"Action: {tool_name}\n"
                    f"Action Input: {tool_input}"
                )

        summary = build_decision_payload(
            {
                "event": context.get("event", {}),
                "lookup": lookup,
                "prediction": context.get("prediction", {}),
                "tool_results": {},
                "agent_summary": "Tools completed; consolidating evidence.",
            }
        )["summary"]

        return (
            "Thought: I now know the final answer.\n"
            f"Final Answer: {summary}"
        )


class HeuristicDecisionLLM(LLM):
    invalid_first_response: bool = False
    _seen: set[str] = PrivateAttr(default_factory=set)

    @property
    def _llm_type(self) -> str:
        return "heuristic-decision-llm"

    @property
    def _identifying_params(self) -> dict[str, Any]:
        return {"mode": "decision", "invalid_first_response": self.invalid_first_response}

    def _call(
        self,
        prompt: str,
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> str:
        context = extract_json_block(
            prompt,
            "DECISION_CONTEXT_JSON_START",
            "DECISION_CONTEXT_JSON_END",
        )
        payload = build_decision_payload(context)

        prompt_hash = sha256(prompt.encode("utf-8")).hexdigest()
        if self.invalid_first_response and prompt_hash not in self._seen:
            self._seen.add(prompt_hash)
            return str(payload)

        return json.dumps(payload, ensure_ascii=False)


class HeuristicRetryLLM(LLM):
    @property
    def _llm_type(self) -> str:
        return "heuristic-retry-llm"

    @property
    def _identifying_params(self) -> dict[str, Any]:
        return {"mode": "retry"}

    def _call(
        self,
        prompt: str,
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> str:
        original_prompt_match = re.search(
            r"ORIGINAL_PROMPT_START\s*(.*?)\s*ORIGINAL_PROMPT_END",
            prompt,
            re.DOTALL,
        )
        original_prompt = original_prompt_match.group(1) if original_prompt_match else prompt
        context = extract_json_block(
            original_prompt,
            "DECISION_CONTEXT_JSON_START",
            "DECISION_CONTEXT_JSON_END",
        )
        payload = build_decision_payload(context)
        return json.dumps(payload, ensure_ascii=False)


class HeuristicHighRiskLLM(LLM):
    @property
    def _llm_type(self) -> str:
        return "heuristic-high-risk-llm"

    @property
    def _identifying_params(self) -> dict[str, Any]:
        return {"mode": "high-risk-log"}

    def _call(
        self,
        prompt: str,
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> str:
        context = extract_json_block(
            prompt,
            "HIGH_RISK_CONTEXT_JSON_START",
            "HIGH_RISK_CONTEXT_JSON_END",
        )
        decision = build_decision_payload(context)
        event = context.get("event", {})
        return (
            f"tx_id={event.get('tx_id')} "
            f"auto_block score={context.get('prediction', {}).get('score', 0.0):.3f} "
            f"reasons={','.join(decision['reason_codes'])} "
            f"summary={decision['summary']}"
        )
