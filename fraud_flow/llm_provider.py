from __future__ import annotations

import os
from urllib.parse import urlsplit

from langchain_core.language_models import BaseLanguageModel

try:
    from langchain_openai import ChatOpenAI
except ImportError:  # Optional dependency for online OpenAI-backed runs.
    ChatOpenAI = None

from .langchain_models import (
    HeuristicDecisionLLM,
    HeuristicHighRiskLLM,
    HeuristicReActLLM,
    HeuristicRetryLLM,
)


def _provider_settings() -> dict[str, str]:
    provider = os.getenv("FRAUD_LLM_PROVIDER", "openai").strip().lower()
    if provider == "ds2api":
        base_url = os.getenv("DS2API_API_BASE", "http://127.0.0.1:5001/v1").strip().rstrip("/")
        parsed = urlsplit(base_url)
        if (parsed.scheme not in {"http", "https"} or parsed.hostname not in {"localhost", "127.0.0.1", "::1"}
                or parsed.username or parsed.password or parsed.query or parsed.fragment):
            raise RuntimeError("DS2API_API_BASE phải là địa chỉ HTTP/HTTPS local (127.0.0.1 hoặc localhost).")
        return {"provider": provider, "key_env": "DS2API_API_KEY", "default_model": "deepseek-v4-flash",
                "base_url": base_url}
    if provider == "deepseek":
        return {"provider": provider, "key_env": "DEEPSEEK_API_KEY", "default_model": "deepseek-flash",
                "base_url": "https://api.deepseek.com"}
    if provider == "openai":
        return {"provider": provider, "key_env": "OPENAI_API_KEY", "default_model": "gpt-4.1-mini",
                "base_url": "https://api.openai.com/v1"}
    raise RuntimeError("FRAUD_LLM_PROVIDER phải là openai, deepseek hoặc ds2api.")


def _build_api_llm(model_env_var: str) -> BaseLanguageModel | None:
    settings = _provider_settings()
    api_key = os.getenv(settings["key_env"], "").strip()
    if not api_key:
        return None
    if ChatOpenAI is None:
        raise RuntimeError(
            "API key is set but `langchain_openai` is not installed. "
            "Install requirements-openai.txt to enable the API backend."
        )
    return ChatOpenAI(
        model=os.getenv(model_env_var) or os.getenv("FRAUD_LLM_MODEL") or settings["default_model"],
        api_key=api_key,
        base_url=settings["base_url"],
        temperature=0,
        timeout=120 if settings["provider"] == "ds2api" else 30,
        max_retries=0 if settings["provider"] == "ds2api" else 1,
        cache=False,
        disable_streaming=True,
        use_responses_api=False,
        **({"extra_body": {"thinking": {"type": "disabled"}}} if settings["provider"] in {"deepseek", "ds2api"} else {}),
        **({"metadata": {"fraud_provider": "ds2api"}} if settings["provider"] == "ds2api" else {}),
    )


def provider_configuration() -> dict[str, object]:
    settings = _provider_settings()
    has_key = bool(os.getenv(settings["key_env"], "").strip())
    installed = ChatOpenAI is not None
    return {
        "provider": settings["provider"],
        "key_env": settings["key_env"],
        "model": os.getenv("FRAUD_LLM_MODEL") or settings["default_model"],
        "base_url": settings["base_url"],
        "api_key_configured": has_key,
        "dependency_installed": installed,
        "configured_mode": settings["provider"] if has_key and installed else "heuristic_local" if not has_key else "unavailable",
        "state": "configured_unverified" if has_key and installed else "dependency_missing" if has_key else "not_configured",
        "network_probe_performed": False,
    }


def build_react_llm() -> BaseLanguageModel:
    api_llm = _build_api_llm("FRAUD_REACT_MODEL")
    if api_llm is not None:
        return api_llm
    return HeuristicReActLLM()


def build_decision_llm() -> BaseLanguageModel:
    api_llm = _build_api_llm("FRAUD_DECISION_MODEL")
    if api_llm is not None:
        return api_llm
    return HeuristicDecisionLLM(invalid_first_response=False)


def build_retry_llm() -> BaseLanguageModel:
    api_llm = _build_api_llm("FRAUD_RETRY_MODEL")
    if api_llm is not None:
        return api_llm
    return HeuristicRetryLLM()


def build_high_risk_llm() -> BaseLanguageModel:
    api_llm = _build_api_llm("FRAUD_HIGH_RISK_MODEL")
    if api_llm is not None:
        return api_llm
    return HeuristicHighRiskLLM()
