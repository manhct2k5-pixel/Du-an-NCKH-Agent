import json

import pytest
from langchain_core.language_models.fake import FakeListLLM
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage

import fraud_flow.agent as agent_module
import fraud_flow.llm_provider as provider
from fraud_flow.agent import ReActInvestigator
from fraud_flow.feature_store import FeatureStore
from fraud_flow.langchain_models import build_decision_payload
from fraud_flow.llm_runtime import ModelCallRecorder, execution_label, execution_summary
from fraud_flow.narratives import build_transaction_narrative
from fraud_flow.schema import ModelPrediction, TransactionEvent


@pytest.fixture
def context(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    event = TransactionEvent("test", 14, "2025-01-01T14:00:00+00:00", "TRANSFER", 10,
                             "card", "merchant", "device", "ip", "location", 0, 0, 40000, 40010)
    store = FeatureStore()
    prediction = ModelPrediction(.700115, .0006879878, "medium", [{"feature": "amount_log1p", "impact": -.2}], 1)
    return event, store, prediction


def test_local_investigation_observes_actual_calls_and_tools(context):
    event, store, prediction = context
    investigator = ReActInvestigator(store)
    assert investigator.runtime_status()["heuristic_responses"] == 0
    result = investigator.investigate(event, store.lookup(event), prediction)
    assert result.action == "review"
    assert result.execution["heuristic_responses"] == 6  # 4 tool turns + final + structured decision
    assert result.execution["external_responses"] == 0
    assert result.execution["external_response_observed"] is False
    assert set(result.execution["tools_executed"]) == set(result.tool_results)
    assert len(result.tool_results) == 4
    assert investigator.runtime_status()["heuristic_responses"] == 6
    again = investigator.investigate(event, store.lookup(event), prediction)
    assert again.execution["heuristic_responses"] == 6
    assert investigator.runtime_status()["heuristic_responses"] == 12
    assert "heuristic local" in execution_label(result.to_dict())
    assert "chưa có bằng chứng" in execution_label({"agent_output": {}})


def test_chat_message_is_parsed_and_retry_is_observed(context, monkeypatch):
    event, store, prediction = context
    payload = build_decision_payload({"event": event.to_dict(), "lookup": store.lookup(event).to_dict(),
                                      "prediction": prediction.to_dict(), "tool_results": {}})
    # Chat-shaped responses, entirely local: no external service called by this test.
    monkeypatch.setattr(agent_module, "build_decision_llm", lambda: FakeMessagesListChatModel(responses=[AIMessage(content="invalid")]))
    monkeypatch.setattr(agent_module, "build_retry_llm", lambda: FakeMessagesListChatModel(responses=[AIMessage(content=json.dumps(payload))]))
    result = ReActInvestigator(store).investigate(event, store.lookup(event), prediction)
    assert result.validation_attempts == 2
    assert result.fallback_used is False
    assert result.execution["stages"]["decision"]["successful_responses"] == 1
    assert result.execution["stages"]["retry"]["successful_responses"] == 1
    assert result.execution["external_response_observed"] is False


def test_exhausted_parser_uses_review_fallback_without_dataclass_error(context, monkeypatch):
    event, store, prediction = context
    monkeypatch.setattr(agent_module, "build_decision_llm", lambda: FakeListLLM(responses=["invalid"]))
    monkeypatch.setattr(agent_module, "build_retry_llm", lambda: FakeListLLM(responses=["invalid"]))
    result = ReActInvestigator(store).investigate(event, store.lookup(event), prediction)
    assert result.action == "review" and result.fallback_used
    assert result.execution["stages"]["retry"]["successful_responses"] == 3


def test_configuration_does_not_claim_success_and_chat_options_are_correct(monkeypatch):
    monkeypatch.setenv("FRAUD_LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "test-placeholder-do-not-use")
    monkeypatch.setattr(provider, "ChatOpenAI", None)
    assert provider.provider_configuration()["state"] == "dependency_missing"
    with pytest.raises(RuntimeError, match="not installed"):
        provider.build_decision_llm()
    options = {}

    def fake_chat(**kwargs):
        options.update(kwargs)
        return "configured-model"

    monkeypatch.setattr(provider, "ChatOpenAI", fake_chat)
    monkeypatch.setenv("FRAUD_DECISION_MODEL", "test-chat-model")
    assert provider.build_decision_llm() == "configured-model"
    assert options == {"model": "test-chat-model", "temperature": 0, "timeout": 30, "max_retries": 1, "cache": False,
                       "api_key": "test-placeholder-do-not-use", "base_url": "https://api.openai.com/v1",
                       "disable_streaming": True, "use_responses_api": False}
    assert provider.provider_configuration()["state"] == "configured_unverified"


def test_external_recorder_requires_success_callback_and_counts_failure():
    class ExternalStub:
        _llm_type = "openai-chat"
        model_name = "test-stub"

    recorder = ModelCallRecorder(ExternalStub())
    recorder.on_chat_model_start()
    recorder.on_llm_error(RuntimeError("test"))
    assert execution_summary({"decision": recorder})["external_response_observed"] is False
    recorder.on_chat_model_start()
    recorder.on_llm_end(None)
    result = execution_summary({"decision": recorder})
    assert result["external_responses"] == 1
    assert result["stages"]["decision"]["attempts"] == 2
    assert result["stages"]["decision"]["failures"] == 1


def test_parser_recovery_is_traced_but_not_counted_as_a_tool():
    from types import SimpleNamespace

    results, trace = ReActInvestigator._collect_tool_results([
        (SimpleNamespace(tool="verify_device_id", tool_input="device"), '{"needs_step_up": true}'),
        (SimpleNamespace(tool="_Exception", tool_input="Invalid format"), "Invalid format"),
    ])
    assert list(results) == ["verify_device_id"]
    assert len(trace) == 2 and trace[1]["tool"] == "_Exception"


def test_explanation_deduplicates_device_and_never_turns_score_into_probability(context):
    event, store, prediction = context
    result = ReActInvestigator(store).investigate(event, store.lookup(event), prediction)
    narrative = build_transaction_narrative(event=event.to_dict(), lookup=store.lookup(event).to_dict(),
        prediction=prediction.to_dict(), final_action="review", final_note="final", agent=result.to_dict())
    text = narrative["human_readable_explanation"]
    assert "0.700" in text and "0.0688%" in text
    assert "70%" not in text and text.count("Thiết bị") == 1
    assert "Tools completed" not in text
    assert len([item for item in narrative["supporting_evidence"] if "device" in item["source"]]) == 1
    assert narrative["mitigating_evidence"]
    assert narrative["model_evidence"][0]["direction"] == "giảm"


def test_missing_history_does_not_invent_device_evidence_or_block_high_review():
    narrative = build_transaction_narrative(event={}, lookup={}, prediction={"route": "high", "score": .9, "raw_probability": .01},
                                           final_action="review", final_note="guard")
    assert narrative["supporting_evidence"] == []
    assert narrative["human_readable_explanation"].startswith("Giữ để xác minh.")
    assert "chặn ngay" not in narrative["human_readable_explanation"]


def test_async_high_risk_generation_is_recorded_separately(tmp_path, monkeypatch):
    from fraud_flow.pipeline import AsyncHighRiskLogger, JsonlLogger

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    path = tmp_path / "high.jsonl"
    logger = AsyncHighRiskLogger(JsonlLogger(path))
    try:
        logger.submit({"event": {"tx_id": "high"}, "prediction": {"score": .99}})
        logger.drain()
        record = json.loads(path.read_text())
        assert record["status"] == "ok"
        assert record["purpose"] == "post_decision_log_only"
        assert record["execution"]["heuristic_responses"] == 1
        assert logger.runtime_status()["external_response_observed"] is False
    finally:
        logger.close()
