import json

import httpx
import pytest

import run_fraud_flow as cli
import fraud_flow.llm_provider as provider_module
from fraud_flow.agent import ReActInvestigator
from fraud_flow.feature_store import FeatureStore
from fraud_flow.langchain_models import build_decision_payload
from fraud_flow.schema import ModelPrediction, TransactionEvent


def test_api_mode_requires_key_without_falling_back(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    config = tmp_path / ".env"
    config.write_text("OPENAI_API_KEY=\n")
    with pytest.raises(SystemExit, match="Chưa có OPENAI_API_KEY"):
        cli.configure_api_environment(str(config))


def test_explicit_env_file_cannot_be_missing(tmp_path):
    with pytest.raises(SystemExit, match="Không tìm thấy"):
        cli.configure_api_environment(str(tmp_path / "missing"))


def test_api_environment_honors_exported_credentials(tmp_path, monkeypatch):
    monkeypatch.setattr(provider_module, "ChatOpenAI", object())
    monkeypatch.setenv("OPENAI_API_KEY", "exported-test-placeholder")
    config = tmp_path / ".env"
    config.write_text("OPENAI_API_KEY=file-test-placeholder\n")
    cli.configure_api_environment(str(config))
    import os
    assert os.environ["OPENAI_API_KEY"] == "exported-test-placeholder"


@pytest.mark.parametrize("provider_name", ["openai", "deepseek", "ds2api"])
def test_real_chat_sdk_handles_react_and_decision_with_mock_http(monkeypatch, provider_name):
    ChatOpenAI = pytest.importorskip("langchain_openai").ChatOpenAI
    # Exercise installed SDK, HTTP serialization and callbacks; no external request.
    event = TransactionEvent("sdk-test", 14, "2025-01-01T14:00:00+00:00", "TRANSFER", 10,
                             "card", "merchant", "device", "ip", "location", 0, 0, 40000, 40010)
    store = FeatureStore()
    prediction = ModelPrediction(.700115, .0006879878, "medium", [], 1)
    decision = build_decision_payload({"event": event.to_dict(), "lookup": store.lookup(event).to_dict(),
                                       "prediction": prediction.to_dict(), "tool_results": {}})
    replies = iter([
        "Thought: Check card history.\nAction: get_card_history\nAction Input: card",
        "Thought: Check IP.\nAction: check_ip_blacklist\nAction Input: ip",
        "Thought: Check device.\nAction: verify_device_id\nAction Input: device",
        "Thought: Check merchant.\nAction: query_merchant_risk\nAction Input: merchant",
        "Final Answer: Cần xác minh thiết bị trước khi kết luận.",
        json.dumps(decision),
    ])
    requests = []
    monkeypatch.setenv("FRAUD_LLM_PROVIDER", provider_name)
    monkeypatch.setenv("OPENAI_API_KEY", "mock-openai-placeholder")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "mock-deepseek-placeholder")
    monkeypatch.setenv("DS2API_API_KEY", "mock-ds2api-placeholder")
    monkeypatch.delenv("DS2API_API_BASE", raising=False)
    for variable in ["FRAUD_LLM_MODEL", "FRAUD_REACT_MODEL", "FRAUD_DECISION_MODEL", "FRAUD_RETRY_MODEL"]:
        monkeypatch.delenv(variable, raising=False)
    host, path, model_name = {
        "openai": ("api.openai.com", "/v1/chat/completions", "gpt-4.1-mini"),
        "deepseek": ("api.deepseek.com", "/chat/completions", "deepseek-flash"),
        "ds2api": ("127.0.0.1", "/v1/chat/completions", "deepseek-v4-flash"),
    }[provider_name]

    def handle(request):
        assert request.url.host == host
        assert request.url.path == path
        assert request.headers["authorization"] == f"Bearer mock-{provider_name}-placeholder"
        requests.append(json.loads(request.content))
        return httpx.Response(200, json={
            "id": "mock-chat-response", "object": "chat.completion", "created": 1,
            "model": model_name,
            "choices": [{"index": 0, "message": {"role": "assistant", "content": next(replies)}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        })

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        monkeypatch.setattr(provider_module, "ChatOpenAI", lambda **kwargs: ChatOpenAI(http_client=client, **kwargs))
        result = ReActInvestigator(store).investigate(event, store.lookup(event), prediction)
    assert result.action == "review"
    assert len(result.tool_results) == 4 and len(requests) == 6
    assert all(row["model"] == model_name for row in requests)
    assert all(not row.get("stream") for row in requests)
    if provider_name in {"deepseek", "ds2api"}:
        assert all(row["thinking"] == {"type": "disabled"} for row in requests)
    assert "stop" in requests[0]  # Classic ReAct stop sequences reach Chat Completions.
    assert result.execution["external_responses"] == 6  # SDK callbacks from the mocked HTTP transport.
    assert result.execution["providers_observed"] == [provider_name]
    assert result.execution["stages"]["react"]["backend"] == provider_name


def test_deepseek_requires_its_own_key_and_does_not_reuse_openai(tmp_path, monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "mock-openai-placeholder")
    monkeypatch.setenv("FRAUD_LLM_PROVIDER", "deepseek")
    config = tmp_path / ".env"
    config.write_text("DEEPSEEK_API_KEY=\n")
    with pytest.raises(SystemExit, match="Chưa có DEEPSEEK_API_KEY"):
        cli.configure_api_environment(str(config))
    assert provider_module.provider_configuration()["state"] == "not_configured"


def test_invalid_provider_fails_instead_of_silently_selecting_one(monkeypatch):
    monkeypatch.setenv("FRAUD_LLM_PROVIDER", "typo")
    with pytest.raises(RuntimeError, match="FRAUD_LLM_PROVIDER"):
        provider_module.build_react_llm()


@pytest.mark.parametrize("base_url", ["https://example.com/v1", "file:///tmp/key", "http://user:secret@localhost:5001/v1"])
def test_ds2api_requires_local_endpoint_without_embedded_credentials(monkeypatch, base_url):
    monkeypatch.setenv("FRAUD_LLM_PROVIDER", "ds2api")
    monkeypatch.setenv("DS2API_API_BASE", base_url)
    with pytest.raises(RuntimeError, match="DS2API_API_BASE"):
        provider_module.provider_configuration()
