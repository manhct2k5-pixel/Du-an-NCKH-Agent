from __future__ import annotations

import numpy as np
import pandas as pd

from fraud_flow.features import resolve_ieee_identity_path
from fraud_flow.config import PAYSIM_FEATURE_COLUMNS
from fraud_flow.research import (
    align_ieee_dataset_to_paysim_features,
    bootstrap_confidence_intervals,
    mcnemar_error_test,
    quantile_project_to_reference,
    resolve_external_validation_data_path,
    summarize_seed_runs,
)


def test_bootstrap_confidence_intervals_produce_ordered_bounds() -> None:
    y_true = pd.Series([0, 1, 0, 1, 0, 1, 0, 1])
    proba = np.array([0.05, 0.95, 0.15, 0.85, 0.25, 0.75, 0.35, 0.65], dtype=float)

    report = bootstrap_confidence_intervals(
        y_true,
        proba,
        threshold=0.5,
        iterations=25,
        random_state=42,
    )

    assert set(report) == {"auc", "pr_auc", "f1", "precision", "recall"}
    for metric_name, stats in report.items():
        assert stats["ci95_low"] <= stats["mean"] <= stats["ci95_high"], metric_name
        assert stats["std"] >= 0.0, metric_name


def test_bootstrap_confidence_intervals_single_class_returns_deterministic_bounds() -> None:
    y_true = pd.Series([0, 0, 0, 0])
    proba = np.array([0.05, 0.15, 0.25, 0.35], dtype=float)

    report = bootstrap_confidence_intervals(
        y_true,
        proba,
        threshold=0.5,
        iterations=25,
        random_state=42,
    )

    assert set(report) == {"auc", "pr_auc", "f1", "precision", "recall"}
    for stats in report.values():
        assert stats["std"] == 0.0
        assert stats["ci95_low"] == stats["mean"] == stats["ci95_high"]


def test_mcnemar_error_test_is_neutral_for_identical_predictions() -> None:
    y_true = pd.Series([0, 1, 0, 1, 1, 0, 1, 0])
    proba = np.array([0.1, 0.9, 0.2, 0.8, 0.75, 0.05, 0.7, 0.1], dtype=float)

    report = mcnemar_error_test(y_true, proba, 0.5, proba, 0.5)

    assert report["discordant"] == 0
    assert report["p_value"] == 1.0


def test_summarize_seed_runs_returns_mean_and_std() -> None:
    runs = [
        {
            "model_name": "xgboost",
            "family": "XGBClassifier",
            "random_state": 42,
            "test_metrics": {"auc": 0.90, "f1": 0.80, "precision": 0.78, "recall": 0.82, "pr_auc": 0.81},
        },
        {
            "model_name": "xgboost",
            "family": "XGBClassifier",
            "random_state": 43,
            "test_metrics": {"auc": 0.92, "f1": 0.82, "precision": 0.80, "recall": 0.84, "pr_auc": 0.83},
        },
        {
            "model_name": "hist_gradient_boosting",
            "family": "HistGradientBoostingClassifier",
            "random_state": 42,
            "test_metrics": {"auc": 0.91, "f1": 0.79, "precision": 0.77, "recall": 0.81, "pr_auc": 0.80},
        },
    ]

    summary = summarize_seed_runs(runs)
    xgb = next(item for item in summary if item["model_name"] == "xgboost")

    assert xgb["test_metrics"]["auc"]["mean"] == 0.91
    assert xgb["test_metrics"]["f1"]["mean"] == 0.81
    assert xgb["test_metrics"]["auc"]["std"] > 0.0


def test_resolve_external_validation_path_prefers_explicit_override() -> None:
    assert resolve_external_validation_data_path("paysim", "/tmp/external.csv") == "/tmp/external.csv"


def test_resolve_external_validation_path_discovers_ieee_for_paysim() -> None:
    discovered = resolve_external_validation_data_path("paysim")
    assert discovered is not None
    assert "train_transaction" in discovered


def test_resolve_ieee_identity_path_prefers_transaction_sibling(tmp_path) -> None:
    dataset_dir = tmp_path / "ieee-fraud-detection"
    dataset_dir.mkdir()
    transaction_path = dataset_dir / "train_transaction.csv"
    identity_path = dataset_dir / "train_identity.csv"
    transaction_path.touch()
    identity_path.touch()

    assert resolve_ieee_identity_path(transaction_path) == identity_path


def test_quantile_projection_uses_reference_scale() -> None:
    projected = quantile_project_to_reference(
        pd.Series([10.0, 20.0, 30.0]),
        pd.Series([100.0, 200.0, 300.0]),
    )

    assert len(projected) == 3
    assert projected[0] >= 100.0
    assert projected[-1] <= 300.0
    assert projected[0] < projected[-1]


def test_align_ieee_dataset_to_paysim_features_returns_frozen_model_schema() -> None:
    paysim_train = pd.DataFrame(
        {
            column: np.linspace(1.0, 10.0, 4)
            for column in PAYSIM_FEATURE_COLUMNS
        }
    )
    paysim_train["amount_log1p"] = np.log1p([50.0, 100.0, 200.0, 400.0])
    paysim_train["oldbalanceOrg"] = [500.0, 1000.0, 2000.0, 4000.0]
    paysim_train["oldbalanceDest"] = [100.0, 200.0, 300.0, 400.0]

    ieee_dataset = pd.DataFrame(
        {
            "TransactionAmt": [25.0, 250.0],
            "ProductCD": ["W", "H"],
            "step": [1, 25],
            "card1": [1000.0, 2000.0],
            "card2": [100.0, 200.0],
            "card3": [150.0, 150.0],
            "card5": [100.0, 200.0],
            "tx_count_24h": [0, 2],
            "avg_amount_7d": [0.0, 25.0],
            "device_tx_count_24h": [0, 1],
            "location_tx_count_24h": [0, 1],
            "merchant_tx_count_24h": [0, 1],
            "llm_risk_score": [0.2, 0.4],
        }
    )

    aligned = align_ieee_dataset_to_paysim_features(ieee_dataset, paysim_train)

    assert list(aligned.columns) == list(PAYSIM_FEATURE_COLUMNS)
    assert aligned.shape == (2, len(PAYSIM_FEATURE_COLUMNS))
    assert not aligned.isna().any().any()
