"""Runtime evidence for model execution; never stores prompts or credentials."""
from __future__ import annotations

from threading import Lock
from typing import Any
from urllib.parse import urlsplit

from langchain_core.callbacks import BaseCallbackHandler


def describe_model(model: Any) -> dict[str, str]:
    kind = str(getattr(model, "_llm_type", "unknown"))
    backend = "heuristic_local" if kind.startswith("heuristic") else "unknown"
    if kind == "openai-chat":
        base_url = getattr(model, "openai_api_base", None) or "https://api.openai.com/v1"
        host = urlsplit(str(base_url)).hostname
        backend = "deepseek" if host == "api.deepseek.com" else "openai" if host == "api.openai.com" else "openai_compatible"
        if host in {"127.0.0.1", "localhost", "::1"} and (getattr(model, "metadata", None) or {}).get("fraud_provider") == "ds2api":
            backend = "ds2api"
    return {"backend": backend, "model": str(getattr(model, "model_name", None) or kind)}


class ModelCallRecorder(BaseCallbackHandler):
    run_inline = True

    def __init__(self, model: Any) -> None:
        self.description = describe_model(model)
        self._lock = Lock()
        self.attempts = self.successes = self.failures = 0

    def on_llm_start(self, *args: Any, **kwargs: Any) -> None:
        with self._lock:
            self.attempts += 1

    def on_chat_model_start(self, *args: Any, **kwargs: Any) -> None:
        self.on_llm_start()

    def on_llm_end(self, *args: Any, **kwargs: Any) -> None:
        with self._lock:
            self.successes += 1

    def on_llm_error(self, *args: Any, **kwargs: Any) -> None:
        with self._lock:
            self.failures += 1

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {**self.description, "attempts": self.attempts,
                    "successful_responses": self.successes, "failures": self.failures}


def execution_summary(recorders: dict[str, ModelCallRecorder]) -> dict[str, Any]:
    stages = {name: recorder.snapshot() for name, recorder in recorders.items()}
    external_backends = {"openai", "deepseek", "openai_compatible", "ds2api"}
    external = sum(row["successful_responses"] for row in stages.values() if row["backend"] in external_backends)
    providers = sorted({row["backend"] for row in stages.values() if row["backend"] in external_backends and row["successful_responses"] > 0})
    local = sum(row["successful_responses"] for row in stages.values() if row["backend"] == "heuristic_local")
    return {"stages": stages, "external_responses": external, "heuristic_responses": local,
            "external_response_observed": external > 0, "providers_observed": providers}


def execution_label(agent: dict[str, Any] | None) -> str:
    if not agent:
        return "Không dùng ReAct để ra quyết định"
    execution = agent.get("execution") or {}
    if execution.get("external_response_observed"):
        providers = ", ".join(execution.get("providers_observed", []))
        return f"{providers + ' · ' if providers else ''}LLM qua API: đã nhận phản hồi trong giao dịch này"
    if execution.get("heuristic_responses", 0) > 0:
        return "ReAct heuristic local: đã chạy, không gọi LLM ngoài"
    return "Log chưa có bằng chứng thực thi LLM"
