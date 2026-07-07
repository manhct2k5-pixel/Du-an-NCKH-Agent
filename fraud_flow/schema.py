from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from pydantic import BaseModel, Field


RouteName = Literal["low", "medium", "high"]
ActionName = Literal["approve", "review", "block"]
# Pipeline-level action — bao gồm step_up (agent không tự sinh ra action này)
PipelineActionName = Literal["approve", "review", "block", "step_up"]


@dataclass(slots=True)
class TransactionEvent:
    tx_id: str
    step: int
    timestamp: str
    tx_type: str
    amount: float
    card_id: str
    merchant_id: str
    device_id: str
    ip_address: str
    location_id: str
    oldbalanceOrg: float
    newbalanceOrig: float
    oldbalanceDest: float
    newbalanceDest: float
    is_fraud: int | None = None
    is_flagged_fraud: int | None = None
    extras: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class FeatureLookup:
    tx_count_24h: int
    avg_amount_7d: float
    device_tx_count_24h: int
    location_tx_count_24h: int
    merchant_tx_count_24h: int
    location_fraud_rate: float
    ip_fraud_rate: float
    merchant_fraud_rate: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ModelPrediction:
    score: float
    raw_probability: float
    route: RouteName
    explanation: list[dict[str, float | str]]
    latency_ms: float
    anomaly_score: float = 0.0
    anomaly_flag: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class AgentDecision:
    recommended_action: ActionName
    confidence: float
    summary: str
    reason_codes: list[str]
    evidence: list[str]
    human_readable_explanation: str
    analyst_report: str
    dashboard_summary: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class InvestigationResult:
    action: ActionName
    reviewer_note: str
    tool_results: dict[str, Any]
    agent_output: dict[str, Any]
    validation_attempts: int
    fallback_used: bool
    human_readable_explanation: str
    analyst_report: str
    dashboard_summary: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class PipelineResult:
    event: dict[str, Any]
    lookup: dict[str, Any]
    prediction: dict[str, Any]
    final_action: PipelineActionName
    final_note: str
    agent: dict[str, Any] | None = None
    narrative: dict[str, Any] | None = None
    actual_label: int | None = None
    correct: bool | None = None
    feedback_logged: bool = False
    end_to_end_latency_ms: float = 0.0
    monitoring_flags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class AgentDecisionModel(BaseModel):
    recommended_action: ActionName
    confidence: float = Field(ge=0.0, le=1.0)
    summary: str
    reason_codes: list[str] = Field(min_length=1)
    evidence: list[str] = Field(min_length=1)
    human_readable_explanation: str
    analyst_report: str
    dashboard_summary: str


class OutputValidationError(ValueError):
    """Raised when the structured agent output is invalid."""


class PydanticStyleOutputParser:
    """Small validator that mirrors the image's PydanticOutputParser stage."""

    valid_actions = {"approve", "review", "block"}

    def parse(self, payload: dict[str, Any]) -> AgentDecision:
        if not isinstance(payload, dict):
            raise OutputValidationError("Agent output must be a dictionary.")

        required = {
            "recommended_action",
            "confidence",
            "summary",
            "reason_codes",
            "evidence",
            "human_readable_explanation",
            "analyst_report",
            "dashboard_summary",
        }
        missing = required.difference(payload)
        if missing:
            raise OutputValidationError(f"Missing keys: {sorted(missing)}")

        action = payload["recommended_action"]
        if action not in self.valid_actions:
            raise OutputValidationError(f"Invalid action: {action}")

        confidence = payload["confidence"]
        if not isinstance(confidence, (int, float)) or not 0.0 <= float(confidence) <= 1.0:
            raise OutputValidationError("confidence must be between 0 and 1.")

        summary = payload["summary"]
        if not isinstance(summary, str) or not summary.strip():
            raise OutputValidationError("summary must be a non-empty string.")

        reason_codes = payload["reason_codes"]
        if not isinstance(reason_codes, list) or not all(isinstance(item, str) and item for item in reason_codes):
            raise OutputValidationError("reason_codes must be a non-empty list of strings.")

        evidence = payload["evidence"]
        if not isinstance(evidence, list) or not all(isinstance(item, str) and item for item in evidence):
            raise OutputValidationError("evidence must be a list of strings.")

        human_readable_explanation = payload["human_readable_explanation"]
        if not isinstance(human_readable_explanation, str) or not human_readable_explanation.strip():
            raise OutputValidationError("human_readable_explanation must be a non-empty string.")

        analyst_report = payload["analyst_report"]
        if not isinstance(analyst_report, str) or not analyst_report.strip():
            raise OutputValidationError("analyst_report must be a non-empty string.")

        dashboard_summary = payload["dashboard_summary"]
        if not isinstance(dashboard_summary, str) or not dashboard_summary.strip():
            raise OutputValidationError("dashboard_summary must be a non-empty string.")

        return AgentDecision(
            recommended_action=action,
            confidence=float(confidence),
            summary=summary.strip(),
            reason_codes=reason_codes,
            evidence=evidence,
            human_readable_explanation=human_readable_explanation.strip(),
            analyst_report=analyst_report.strip(),
            dashboard_summary=dashboard_summary.strip(),
        )
