from __future__ import annotations

from collections import Counter
from typing import Any

import numpy as np


def summarize_numeric_distribution(values: np.ndarray) -> dict[str, float]:
    if values.size == 0:
        return {
            "min": 0.0,
            "max": 0.0,
            "mean": 0.0,
            "std": 0.0,
            "p50": 0.0,
            "p90": 0.0,
            "p95": 0.0,
            "p99": 0.0,
        }

    return {
        "min": float(np.min(values)),
        "max": float(np.max(values)),
        "mean": float(np.mean(values)),
        "std": float(np.std(values)),
        "p50": float(np.quantile(values, 0.50)),
        "p90": float(np.quantile(values, 0.90)),
        "p95": float(np.quantile(values, 0.95)),
        "p99": float(np.quantile(values, 0.99)),
    }


def calibrate_operational_score(raw_probability: float, calibration: dict[str, float]) -> float:
    low_quantile = float(calibration.get("low_quantile_score", 0.3))
    high_quantile = float(calibration.get("high_quantile_score", 0.7))

    if high_quantile <= low_quantile:
        high_quantile = low_quantile + 1e-6

    if raw_probability <= low_quantile:
        return float(round(0.3 * (raw_probability / max(low_quantile, 1e-6)), 6))

    if raw_probability <= high_quantile:
        scaled = (raw_probability - low_quantile) / max(high_quantile - low_quantile, 1e-6)
        return float(round(0.3 + 0.4 * scaled, 6))

    scaled = (raw_probability - high_quantile) / max(1.0 - high_quantile, 1e-6)
    return float(round(min(0.999, 0.7 + 0.3 * scaled), 6))


def route_score(score: float, low_threshold: float, high_threshold: float) -> str:
    if score < low_threshold:
        return "low"
    if score > high_threshold:
        return "high"
    return "medium"


def build_routing_calibration(
    validation_proba: np.ndarray,
    *,
    low_quantile: float,
    high_quantile: float,
    low_threshold: float,
    high_threshold: float,
) -> dict[str, Any]:
    low_quantile_score = float(np.quantile(validation_proba, low_quantile))
    high_quantile_score = float(np.quantile(validation_proba, high_quantile))
    calibration = {
        "low_quantile": float(low_quantile),
        "high_quantile": float(high_quantile),
        "low_quantile_score": low_quantile_score,
        "high_quantile_score": high_quantile_score,
    }
    operational_scores = np.array(
        [calibrate_operational_score(float(probability), calibration) for probability in validation_proba],
        dtype=float,
    )
    route_counts = Counter(
        route_score(float(score), low_threshold=low_threshold, high_threshold=high_threshold)
        for score in operational_scores
    )
    route_total = max(int(len(operational_scores)), 1)
    calibration["raw_probability_summary"] = summarize_numeric_distribution(validation_proba)
    calibration["operational_score_summary"] = summarize_numeric_distribution(operational_scores)
    calibration["validation_route_share"] = {
        route: round(route_counts.get(route, 0) / route_total, 6)
        for route in ("low", "medium", "high")
    }
    return calibration
