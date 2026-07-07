"""End-to-end fraud detection flow that mirrors the provided system diagram."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

__all__ = ["FraudFlowRunner", "train_model"]

if TYPE_CHECKING:
    from .pipeline import FraudFlowRunner
    from .training import train_model


def __getattr__(name: str) -> Any:
    if name == "FraudFlowRunner":
        from .pipeline import FraudFlowRunner

        return FraudFlowRunner
    if name == "train_model":
        from .training import train_model

        return train_model
    raise AttributeError(f"module 'fraud_flow' has no attribute {name!r}")
