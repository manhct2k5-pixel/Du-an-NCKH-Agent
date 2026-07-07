from __future__ import annotations

import os

from langchain_core.language_models import BaseLanguageModel

try:
    from langchain_openai import OpenAI
except ImportError:  # Optional dependency for online OpenAI-backed runs.
    OpenAI = None

from .langchain_models import (
    HeuristicDecisionLLM,
    HeuristicHighRiskLLM,
    HeuristicReActLLM,
    HeuristicRetryLLM,
)


def _openai_available() -> bool:
    return OpenAI is not None and bool(os.getenv("OPENAI_API_KEY"))


def _build_openai_llm(model_env_var: str) -> BaseLanguageModel | None:
    if not os.getenv("OPENAI_API_KEY"):
        return None
    if OpenAI is None:
        raise RuntimeError(
            "OPENAI_API_KEY is set but `langchain_openai` is not installed. "
            "Install `langchain-openai` or unset OPENAI_API_KEY to use the local heuristic LLM fallback."
        )
    return OpenAI(
        model=os.getenv(model_env_var, os.getenv("FRAUD_LLM_MODEL", "gpt-4.1-mini")),
        temperature=0,
    )


def build_react_llm() -> BaseLanguageModel:
    openai_llm = _build_openai_llm("FRAUD_REACT_MODEL")
    if openai_llm is not None:
        return openai_llm
    return HeuristicReActLLM()


def build_decision_llm() -> BaseLanguageModel:
    openai_llm = _build_openai_llm("FRAUD_DECISION_MODEL")
    if openai_llm is not None:
        return openai_llm
    return HeuristicDecisionLLM(invalid_first_response=False)


def build_retry_llm() -> BaseLanguageModel:
    openai_llm = _build_openai_llm("FRAUD_RETRY_MODEL")
    if openai_llm is not None:
        return openai_llm
    return HeuristicRetryLLM()


def build_high_risk_llm() -> BaseLanguageModel:
    openai_llm = _build_openai_llm("FRAUD_HIGH_RISK_MODEL")
    if openai_llm is not None:
        return openai_llm
    return HeuristicHighRiskLLM()
