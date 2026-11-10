from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import fraud_flow.service as service


@pytest.fixture
def gateway(monkeypatch):
    calls = []

    class Runner:
        model_service = SimpleNamespace(source="paysim", metadata={"val_end": 100})

        def bootstrap_online_history(self, rows=None):
            return 0

        def close(self):
            pass

        def process_event(self, event, actual_label=None, **kwargs):
            calls.append((event, actual_label))
            return SimpleNamespace(to_dict=lambda: {
                "event": event.to_dict(),
                "prediction": {"route": "medium", "score": 0.5},
                "final_action": "review",
                "actual_label": actual_label,
                "narrative": {"human_readable_explanation": "Review complete"},
            })

    monkeypatch.setattr(service, "FraudFlowRunner", Runner)
    with TestClient(service.create_app()) as client:
        yield client, calls


def test_single_gateway_returns_complete_medium_decision_and_preserves_label(gateway):
    client, calls = gateway
    response = client.post("/gateway/transaction", json=service.PAYSIM_EXAMPLE)
    assert response.status_code == 200
    result = response.json()
    assert result["prediction"]["route"] == "medium"
    assert result["final_action"] == "review"
    assert result["actual_label"] == 0
    assert result["narrative"]["human_readable_explanation"]
    assert len(calls) == 1 and calls[0][1] == 0


@pytest.mark.parametrize("field,value", [
    ("amount", "Infinity"), ("amount", "NaN"),
    ("oldbalanceOrg", "Infinity"), ("newbalanceOrig", "Infinity"),
    ("oldbalanceDest", "Infinity"), ("newbalanceDest", "Infinity"),
    ("is_fraud", 2), ("is_fraud", -1), ("is_flagged_fraud", 2),
])
def test_gateway_rejects_invalid_numbers_without_processing(gateway, field, value):
    client, calls = gateway
    response = client.post("/gateway/transaction", json={**service.PAYSIM_EXAMPLE, field: value})
    assert response.status_code == 422
    assert not calls


@pytest.mark.parametrize("literal", ["Infinity", "-Infinity", "NaN"])
def test_nonfinite_raw_json_returns_serializable_validation_error(gateway, literal):
    client, calls = gateway
    response = client.post(
        "/gateway/transaction",
        content='{"tx_type":"TRANSFER","amount":' + literal + '}',
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 422
    assert response.json()["detail"]
    assert not calls


@pytest.mark.parametrize("step", [None, 1])
def test_gateway_rejects_invalid_timestamp_even_with_explicit_step(gateway, step):
    client, calls = gateway
    payload = {**service.PAYSIM_EXAMPLE, "timestamp": "invalid", "step": step}
    assert client.post("/gateway/transaction", json=payload).status_code == 400
    assert not calls


def test_zero_bootstrap_does_not_load_entire_dataset():
    from fraud_flow.pipeline import FraudFlowRunner

    runner = FraudFlowRunner.__new__(FraudFlowRunner)
    # No dataset/Redis state is initialized: rows=0 must return before accessing it.
    assert runner.bootstrap_online_history(rows=0) == 0


def test_llm_status_reports_runtime_without_probe_or_secret(gateway, monkeypatch):
    from fraud_flow.agent import ReActInvestigator
    from fraud_flow.feature_store import FeatureStore

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    client, calls = gateway
    client.app.state.runner.agent = ReActInvestigator(FeatureStore())
    response = client.get("/llm/status")
    assert response.status_code == 200
    result = response.json()
    assert result["configuration"]["network_probe_performed"] is False
    assert result["decision_runtime"]["external_response_observed"] is False
    assert result["decision_runtime"]["heuristic_responses"] == 0
    assert "heuristic local" in result["label"]
    assert not calls


@pytest.mark.parametrize("upstream_status", [401, 402, 429])
def test_llm_api_errors_return_clear_message_without_raw_body(gateway, monkeypatch, upstream_status):
    import httpx
    APIStatusError = pytest.importorskip("openai").APIStatusError
    client, calls = gateway
    monkeypatch.setenv("FRAUD_LLM_PROVIDER", "deepseek")

    def unavailable(*args, **kwargs):
        raise APIStatusError("sensitive upstream detail", response=httpx.Response(
            upstream_status, request=httpx.Request("POST", "https://api.deepseek.com/chat/completions")),
            body={"error": "sensitive upstream detail"})

    monkeypatch.setattr(client.app.state.runner, "process_event", unavailable)
    response = client.post("/gateway/transaction", json=service.PAYSIM_EXAMPLE)
    assert response.status_code == 503
    body = response.json()
    assert body["provider"] == "deepseek" and body["upstream_status"] == upstream_status
    assert "sensitive upstream detail" not in response.text
    assert "DeepSeek" in body["detail"]
    if upstream_status == 402:
        assert "không đủ số dư" in body["detail"]
        assert body["error_code"] == "llm_insufficient_balance"
    assert "final_action" not in body and not calls
