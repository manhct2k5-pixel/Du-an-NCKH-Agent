from __future__ import annotations

import json
import math
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, f1_score, precision_score, recall_score, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from xgboost import DMatrix, XGBClassifier

from .calibration import build_routing_calibration, calibrate_operational_score, route_score
from .config import APP_CONFIG, PAYSIM_FEATURE_COLUMNS
from .feature_store import FeatureStore
from .features import (
    build_feature_frame,
    enrich_transactions,
    event_from_row,
    load_filtered_frame,
    resolve_ieee_identity_path,
)
from .langchain_models import build_decision_payload
from .schema import AgentDecision, ModelPrediction
from .training import (
    DatasetBundle,
    build_dataset,
    classification_metrics,
    confusion_payload,
    find_best_threshold,
    split_indices,
    split_strategy_for_source,
)


@dataclass
class ExperimentSplits:
    bundle: DatasetBundle
    train_df: pd.DataFrame
    val_df: pd.DataFrame
    test_df: pd.DataFrame
    X_train: pd.DataFrame
    X_val: pd.DataFrame
    X_test: pd.DataFrame
    y_train: pd.Series
    y_val: pd.Series
    y_test: pd.Series


@dataclass
class ModelRunArtifact:
    model_name: str
    model: Any
    threshold: float
    validation_proba: np.ndarray
    test_proba: np.ndarray
    report: dict[str, Any]
    params: dict[str, Any]


@dataclass(frozen=True)
class ResearchRunOutputs:
    baseline_comparison_path: Path
    baseline_comparison_csv_path: Path
    baseline_comparison_markdown_path: Path
    feature_ablation_path: Path
    feature_ablation_csv_path: Path
    feature_ablation_markdown_path: Path
    medium_branch_ablation_path: Path
    medium_branch_ablation_csv_path: Path
    medium_branch_ablation_markdown_path: Path
    robustness_validation_path: Path
    robustness_validation_csv_path: Path
    robustness_validation_markdown_path: Path
    external_validation_path: Path
    external_validation_csv_path: Path
    external_validation_markdown_path: Path
    research_suite_path: Path
    research_suite_markdown_path: Path
    artifact_scope: str


def resolve_research_outputs(sample_size: int | None) -> ResearchRunOutputs:
    if sample_size is None:
        outputs = APP_CONFIG.outputs
        return ResearchRunOutputs(
            baseline_comparison_path=outputs.baseline_comparison_path,
            baseline_comparison_csv_path=outputs.baseline_comparison_csv_path,
            baseline_comparison_markdown_path=outputs.baseline_comparison_markdown_path,
            feature_ablation_path=outputs.feature_ablation_path,
            feature_ablation_csv_path=outputs.feature_ablation_csv_path,
            feature_ablation_markdown_path=outputs.feature_ablation_markdown_path,
            medium_branch_ablation_path=outputs.medium_branch_ablation_path,
            medium_branch_ablation_csv_path=outputs.medium_branch_ablation_csv_path,
            medium_branch_ablation_markdown_path=outputs.medium_branch_ablation_markdown_path,
            robustness_validation_path=outputs.robustness_validation_path,
            robustness_validation_csv_path=outputs.robustness_validation_csv_path,
            robustness_validation_markdown_path=outputs.robustness_validation_markdown_path,
            external_validation_path=outputs.external_validation_path,
            external_validation_csv_path=outputs.external_validation_csv_path,
            external_validation_markdown_path=outputs.external_validation_markdown_path,
            research_suite_path=outputs.research_suite_path,
            research_suite_markdown_path=outputs.research_suite_markdown_path,
            artifact_scope="production",
        )

    base_dir = APP_CONFIG.outputs.experiments_dir / f"sample_{sample_size}" / "research" / "reports"
    return ResearchRunOutputs(
        baseline_comparison_path=base_dir / APP_CONFIG.outputs.baseline_comparison_path.name,
        baseline_comparison_csv_path=base_dir / APP_CONFIG.outputs.baseline_comparison_csv_path.name,
        baseline_comparison_markdown_path=base_dir / APP_CONFIG.outputs.baseline_comparison_markdown_path.name,
        feature_ablation_path=base_dir / APP_CONFIG.outputs.feature_ablation_path.name,
        feature_ablation_csv_path=base_dir / APP_CONFIG.outputs.feature_ablation_csv_path.name,
        feature_ablation_markdown_path=base_dir / APP_CONFIG.outputs.feature_ablation_markdown_path.name,
        medium_branch_ablation_path=base_dir / APP_CONFIG.outputs.medium_branch_ablation_path.name,
        medium_branch_ablation_csv_path=base_dir / APP_CONFIG.outputs.medium_branch_ablation_csv_path.name,
        medium_branch_ablation_markdown_path=base_dir / APP_CONFIG.outputs.medium_branch_ablation_markdown_path.name,
        robustness_validation_path=base_dir / APP_CONFIG.outputs.robustness_validation_path.name,
        robustness_validation_csv_path=base_dir / APP_CONFIG.outputs.robustness_validation_csv_path.name,
        robustness_validation_markdown_path=base_dir / APP_CONFIG.outputs.robustness_validation_markdown_path.name,
        external_validation_path=base_dir / APP_CONFIG.outputs.external_validation_path.name,
        external_validation_csv_path=base_dir / APP_CONFIG.outputs.external_validation_csv_path.name,
        external_validation_markdown_path=base_dir / APP_CONFIG.outputs.external_validation_markdown_path.name,
        research_suite_path=base_dir / APP_CONFIG.outputs.research_suite_path.name,
        research_suite_markdown_path=base_dir / APP_CONFIG.outputs.research_suite_markdown_path.name,
        artifact_scope=f"sample_{sample_size}",
    )


def prepare_experiment_splits(data_path: str | None = None, sample_size: int | None = None, source: str | None = None) -> ExperimentSplits:
    bundle = build_dataset(data_path=data_path, sample_size=sample_size, source=source)
    dataset = bundle.dataset.copy()
    train_end, val_end = split_indices(len(dataset))

    train_df = dataset.iloc[:train_end].copy()
    val_df = dataset.iloc[train_end:val_end].copy()
    test_df = dataset.iloc[val_end:].copy()

    feature_columns = bundle.feature_columns
    X_train = train_df[feature_columns].astype(np.float32)
    X_val = val_df[feature_columns].astype(np.float32)
    X_test = test_df[feature_columns].astype(np.float32)
    y_train = train_df["isFraud"].astype(int)
    y_val = val_df["isFraud"].astype(int)
    y_test = test_df["isFraud"].astype(int)
    return ExperimentSplits(bundle, train_df, val_df, test_df, X_train, X_val, X_test, y_train, y_val, y_test)


def resolve_random_state(random_state: int | None = None) -> int:
    return APP_CONFIG.training.random_state if random_state is None else int(random_state)


def build_model_specs(random_state: int | None = None) -> list[dict[str, Any]]:
    resolved_random_state = resolve_random_state(random_state)
    return [
        {
            "name": "dummy_prior",
            "family": "DummyClassifier",
            "params": {"strategy": "prior"},
            "builder": lambda: DummyClassifier(strategy="prior"),
        },
        {
            "name": "logistic_regression",
            "family": "LogisticRegression",
            "params": {
                "scaler": "StandardScaler",
                "solver": "lbfgs",
                "class_weight": "balanced",
                "max_iter": 500,
                "tol": 1e-4,
            },
            "builder": lambda: Pipeline(
                steps=[
                    ("imputer", SimpleImputer(strategy="median")),
                    ("scaler", StandardScaler()),
                    (
                        "model",
                        LogisticRegression(
                            solver="lbfgs",
                            class_weight="balanced",
                            max_iter=500,
                            tol=1e-4,
                            random_state=resolved_random_state,
                        ),
                    ),
                ]
            ),
        },
        {
            "name": "hist_gradient_boosting",
            "family": "HistGradientBoostingClassifier",
            "params": {
                "learning_rate": 0.08,
                "max_iter": 220,
                "max_depth": 6,
                "min_samples_leaf": 80,
            },
            "builder": lambda: HistGradientBoostingClassifier(
                learning_rate=0.08,
                max_iter=220,
                max_depth=6,
                min_samples_leaf=80,
                random_state=resolved_random_state,
            ),
        },
        {
            "name": "random_forest",
            "family": "RandomForestClassifier",
            "params": {
                "n_estimators": 120,
                "max_depth": 12,
                "min_samples_leaf": 40,
                "class_weight": "balanced_subsample",
                "imputer": "median",
            },
            "builder": lambda: Pipeline(
                steps=[
                    ("imputer", SimpleImputer(strategy="median")),
                    (
                        "model",
                        RandomForestClassifier(
                            n_estimators=120,
                            max_depth=12,
                            min_samples_leaf=40,
                            class_weight="balanced_subsample",
                            n_jobs=APP_CONFIG.training.n_jobs,
                            random_state=resolved_random_state,
                        ),
                    ),
                ]
            ),
        },
    ]


def pr_auc_score(y_true: pd.Series, proba: np.ndarray) -> float:
    if len(set(y_true)) < 2:
        return 0.0
    return float(average_precision_score(y_true, proba))


def metric_snapshot(y_true: pd.Series, proba: np.ndarray, threshold: float) -> dict[str, float]:
    metrics = classification_metrics(y_true, proba, threshold)
    metrics["pr_auc"] = pr_auc_score(y_true, proba)
    return metrics


def summarize_seed_runs(runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in runs:
        grouped.setdefault(item["model_name"], []).append(item)

    summaries: list[dict[str, Any]] = []
    for model_name, items in grouped.items():
        metrics = ["auc", "f1", "precision", "recall", "pr_auc"]
        summary_metrics = {}
        for metric_name in metrics:
            values = [float(item["test_metrics"][metric_name]) for item in items]
            summary_metrics[metric_name] = {
                "mean": round(float(np.mean(values)), 6),
                "std": round(float(np.std(values, ddof=0)), 6),
                "min": round(float(np.min(values)), 6),
                "max": round(float(np.max(values)), 6),
            }
        summaries.append(
            {
                "model_name": model_name,
                "family": items[0]["family"],
                "seeds": [item["random_state"] for item in items],
                "test_metrics": summary_metrics,
            }
        )
    summaries.sort(key=lambda item: (item["test_metrics"]["auc"]["mean"], item["test_metrics"]["f1"]["mean"]), reverse=True)
    return summaries


def bootstrap_confidence_intervals(
    y_true: pd.Series,
    proba: np.ndarray,
    threshold: float,
    iterations: int,
    random_state: int,
) -> dict[str, dict[str, float]]:
    if iterations <= 0:
        raise ValueError("bootstrap iterations must be greater than 0.")

    metric_names = ("auc", "pr_auc", "f1", "precision", "recall")

    def _deterministic_intervals(snapshot: dict[str, float]) -> dict[str, dict[str, float]]:
        report: dict[str, dict[str, float]] = {}
        for metric_name in metric_names:
            value = round(float(snapshot.get(metric_name, 0.0)), 6)
            report[metric_name] = {
                "mean": value,
                "std": 0.0,
                "ci95_low": value,
                "ci95_high": value,
            }
        return report

    rng = np.random.default_rng(random_state)
    y_true_array = y_true.to_numpy(dtype=int)
    proba_array = np.asarray(proba, dtype=float)
    if len(y_true_array) == 0:
        return _deterministic_intervals({metric_name: 0.0 for metric_name in metric_names})
    if len(np.unique(y_true_array)) < 2:
        return _deterministic_intervals(metric_snapshot(y_true, proba_array, threshold))

    metric_values: dict[str, list[float]] = {name: [] for name in metric_names}

    while len(metric_values["auc"]) < iterations:
        sample_indices = rng.integers(0, len(y_true_array), len(y_true_array))
        sampled_y = y_true_array[sample_indices]
        if len(np.unique(sampled_y)) < 2:
            continue
        sampled_proba = proba_array[sample_indices]
        sampled_metrics = metric_snapshot(pd.Series(sampled_y), sampled_proba, threshold)
        for metric_name, value in sampled_metrics.items():
            metric_values[metric_name].append(float(value))

    intervals: dict[str, dict[str, float]] = {}
    for metric_name, values in metric_values.items():
        intervals[metric_name] = {
            "mean": round(float(np.mean(values)), 6),
            "std": round(float(np.std(values, ddof=0)), 6),
            "ci95_low": round(float(np.quantile(values, 0.025)), 6),
            "ci95_high": round(float(np.quantile(values, 0.975)), 6),
        }
    return intervals


def mcnemar_error_test(
    y_true: pd.Series,
    proba_a: np.ndarray,
    threshold_a: float,
    proba_b: np.ndarray,
    threshold_b: float,
) -> dict[str, float | int]:
    y_true_array = y_true.to_numpy(dtype=int)
    pred_a = (np.asarray(proba_a, dtype=float) >= threshold_a).astype(int)
    pred_b = (np.asarray(proba_b, dtype=float) >= threshold_b).astype(int)

    correct_a = pred_a == y_true_array
    correct_b = pred_b == y_true_array
    b_count = int(np.sum(correct_a & ~correct_b))
    c_count = int(np.sum(~correct_a & correct_b))
    discordant = b_count + c_count

    if discordant == 0:
        return {
            "better_for_a": b_count,
            "better_for_b": c_count,
            "discordant": discordant,
            "chi_square": 0.0,
            "p_value": 1.0,
        }

    chi_square = (abs(b_count - c_count) - 1) ** 2 / discordant
    p_value = math.erfc(math.sqrt(chi_square / 2.0))
    return {
        "better_for_a": b_count,
        "better_for_b": c_count,
        "discordant": discordant,
        "chi_square": round(float(chi_square), 6),
        "p_value": round(float(p_value), 6),
    }


def resolve_external_validation_data_path(primary_source: str, external_data_path: str | None = None) -> str | None:
    if external_data_path:
        return external_data_path
    if primary_source == "paysim":
        transaction_candidates = [
            APP_CONFIG.transaction_data_path,
            APP_CONFIG.data_path.parent / "ieee-fraud-detection" / "train_transaction.csv",
        ]
        for transaction_path in transaction_candidates:
            if transaction_path.exists() and resolve_ieee_identity_path(transaction_path).exists():
                return str(transaction_path)
    if primary_source == "ieee" and APP_CONFIG.data_path.exists():
        return str(APP_CONFIG.data_path)
    return None


def numeric_column(frame: pd.DataFrame, column: str, default: float = 0.0) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=float)
    return pd.to_numeric(frame[column], errors="coerce").replace([np.inf, -np.inf], np.nan).fillna(default).astype(float)


def quantile_project_to_reference(source: pd.Series, reference: pd.Series) -> np.ndarray:
    source_values = pd.to_numeric(source, errors="coerce").replace([np.inf, -np.inf], np.nan)
    if source_values.isna().all():
        source_values = pd.Series(0.0, index=source.index)
    else:
        source_values = source_values.fillna(float(source_values.median()))

    reference_values = pd.to_numeric(reference, errors="coerce").replace([np.inf, -np.inf], np.nan).dropna().to_numpy(dtype=float)
    if len(reference_values) == 0:
        return np.zeros(len(source_values), dtype=float)
    if len(reference_values) == 1 or float(np.nanstd(reference_values)) == 0.0:
        return np.full(len(source_values), float(reference_values[0]), dtype=float)

    ranks = source_values.rank(method="average", pct=True).to_numpy(dtype=float)
    quantiles = np.clip(ranks, 0.0, 1.0)
    return np.quantile(reference_values, quantiles)


def build_unlabeled_ieee_external_dataset(data_path: str, sample_size: int | None = None) -> DatasetBundle:
    raw = load_filtered_frame(data_path, sample_size=sample_size, source="ieee")
    enriched = enrich_transactions(raw, source="ieee").reset_index(drop=True)
    feature_frame, _, _ = build_feature_frame(
        enriched,
        source="ieee",
        freeze_risk_labels=True,
        store=FeatureStore(),
    )
    dataset = pd.concat([enriched, feature_frame], axis=1)
    dataset = dataset.loc[:, ~dataset.columns.duplicated()].copy()
    identity_data_path = str(resolve_ieee_identity_path(data_path))
    return DatasetBundle(
        dataset=dataset,
        source="ieee",
        feature_columns=list(PAYSIM_FEATURE_COLUMNS),
        data_path=str(data_path),
        identity_data_path=identity_data_path,
    )


def align_ieee_dataset_to_paysim_features(ieee_dataset: pd.DataFrame, paysim_train_df: pd.DataFrame) -> pd.DataFrame:
    # Amount: direct semantic match — log1p(TransactionAmt) → log1p(amount)
    transaction_amt = numeric_column(ieee_dataset, "TransactionAmt")
    amount_log_proxy = np.log1p(np.maximum(transaction_amt.to_numpy(dtype=float), 0.0))
    amount_log1p = quantile_project_to_reference(pd.Series(amount_log_proxy, index=ieee_dataset.index), paysim_train_df["amount_log1p"])
    amount = np.expm1(amount_log1p)

    # Type encoding: W (withdrawal) → CASH_OUT=2; all others → TRANSFER=1
    product_cd = ieee_dataset.get("ProductCD", pd.Series("", index=ieee_dataset.index)).astype(str).str.upper()
    type_encoded = np.where(product_cd == "W", 2, 1)

    # Time features
    hour_of_day = (numeric_column(ieee_dataset, "step") % 24).astype(int)

    # Source balance proxy: account velocity history ≈ account balance tier
    # avg_amount_7d × (tx_count_24h + 1) captures account spend level better than card numbers
    avg_amount_7d_col = numeric_column(ieee_dataset, "avg_amount_7d")
    tx_count_24h_col = numeric_column(ieee_dataset, "tx_count_24h")
    source_balance_proxy = avg_amount_7d_col * (tx_count_24h_col + 1.0) + numeric_column(ieee_dataset, "card1")
    oldbalance_org = quantile_project_to_reference(source_balance_proxy, paysim_train_df["oldbalanceOrg"])

    newbalance_orig = np.maximum(oldbalance_org - amount, 0.0)

    # Destination balance proxy: C2 (address-count feature) × amount + dist1
    c2 = numeric_column(ieee_dataset, "C2")
    dist1 = numeric_column(ieee_dataset, "dist1")
    dest_proxy = c2 * np.maximum(transaction_amt, 1.0) + dist1
    oldbalance_dest = quantile_project_to_reference(dest_proxy, paysim_train_df["oldbalanceDest"])
    newbalance_dest = oldbalance_dest + amount

    # Balance discrepancy proxy via M-field mismatches:
    # In PaySim, TRANSFER fraud yields balance_diff = -amount (balance frozen despite transfer).
    # M-fields in IEEE-CIS are billing/address match indicators (T=match, F=mismatch).
    # More mismatches → accounting anomaly → maps to the PaySim TRANSFER-fraud pattern.
    m_false_count = sum(
        (ieee_dataset.get(f"M{i}", pd.Series("", index=ieee_dataset.index))
         .astype(str).str.strip().str.upper() == "F").astype(float)
        for i in range(1, 10)
    )
    balance_diff = -amount * (m_false_count / 9.0)  # range [-amount, 0]

    amount_ratio = amount / (oldbalance_org + 1.0)
    org_balance_delta_ratio = balance_diff / (oldbalance_org + 1.0)

    # Recipient new flag: D2 (days since last transaction on card) missing or > 365 → unknown destination
    if "D2" in ieee_dataset.columns:
        d2_raw = pd.to_numeric(ieee_dataset["D2"], errors="coerce")
    else:
        d2_raw = pd.Series(np.nan, index=ieee_dataset.index)
    recipient_new_flag = (d2_raw.isna() | (d2_raw > 365)).astype(int)

    aligned = pd.DataFrame(
        {
            "amount_log1p": amount_log1p,
            "oldbalanceOrg": oldbalance_org,
            "newbalanceOrig": newbalance_orig,
            "oldbalanceDest": oldbalance_dest,
            "newbalanceDest": newbalance_dest,
            "type_encoded": type_encoded,
            "balance_diff": balance_diff,
            "amount_ratio": amount_ratio,
            "org_balance_delta_ratio": org_balance_delta_ratio,
            "hour_of_day": hour_of_day,
            "is_night_tx": (hour_of_day < 6).astype(int),
            "recipient_new_flag": recipient_new_flag,
            "tx_count_24h": tx_count_24h_col,
            "avg_amount_7d": avg_amount_7d_col,
            "device_tx_count_24h": numeric_column(ieee_dataset, "device_tx_count_24h"),
            "location_tx_count_24h": numeric_column(ieee_dataset, "location_tx_count_24h"),
            "merchant_tx_count_24h": numeric_column(ieee_dataset, "merchant_tx_count_24h"),
            "location_fraud_rate": numeric_column(ieee_dataset, "location_fraud_rate"),
            "ip_fraud_rate": numeric_column(ieee_dataset, "ip_fraud_rate"),
            "merchant_fraud_rate": numeric_column(ieee_dataset, "merchant_fraud_rate"),
            "llm_risk_score": numeric_column(ieee_dataset, "llm_risk_score"),
            "llm_reason_count": numeric_column(ieee_dataset, "llm_reason_count"),
            "llm_high_risk_flag": numeric_column(ieee_dataset, "llm_high_risk_flag"),
            "llm_review_flag": numeric_column(ieee_dataset, "llm_review_flag"),
            "llm_category_hash": numeric_column(ieee_dataset, "llm_category_hash"),
        },
        index=ieee_dataset.index,
    )
    aligned = aligned.replace([np.inf, -np.inf], np.nan).fillna(0.0)
    return aligned[PAYSIM_FEATURE_COLUMNS].astype(np.float32)


def summarize_model_run(
    model_name: str,
    family: str,
    threshold: float,
    params: dict[str, Any],
    train_seconds: float,
    inference_ms_per_1k: float,
    y_val: pd.Series,
    val_proba: np.ndarray,
    y_test: pd.Series,
    test_proba: np.ndarray,
    feature_columns: list[str],
) -> dict[str, Any]:
    validation_metrics = classification_metrics(y_val, val_proba, threshold)
    test_metrics = classification_metrics(y_test, test_proba, threshold)
    return {
        "model_name": model_name,
        "family": family,
        "feature_count": len(feature_columns),
        "selected_threshold": threshold,
        "params": params,
        "train_seconds": round(train_seconds, 4),
        "inference_ms_per_1k_rows": round(inference_ms_per_1k, 4),
        "validation": {
            "metrics": validation_metrics,
            "pr_auc": pr_auc_score(y_val, val_proba),
            "confusion_matrix": confusion_payload(y_val, val_proba, threshold),
        },
        "test": {
            "metrics": test_metrics,
            "pr_auc": pr_auc_score(y_test, test_proba),
            "confusion_matrix": confusion_payload(y_test, test_proba, threshold),
        },
    }


def fit_generic_baseline(
    spec: dict[str, Any],
    splits: ExperimentSplits,
    feature_columns: list[str],
    random_state: int | None = None,
) -> ModelRunArtifact:
    model = spec["builder"]()
    start = time.perf_counter()
    model.fit(splits.X_train[feature_columns], splits.y_train)
    train_seconds = time.perf_counter() - start

    val_proba = model.predict_proba(splits.X_val[feature_columns])[:, 1]
    threshold, _ = find_best_threshold(splits.y_val, val_proba)

    infer_start = time.perf_counter()
    test_proba = model.predict_proba(splits.X_test[feature_columns])[:, 1]
    infer_seconds = time.perf_counter() - infer_start
    inference_ms_per_1k = (infer_seconds / max(len(splits.X_test), 1)) * 1_000_000

    report = summarize_model_run(
        model_name=spec["name"],
        family=spec["family"],
        threshold=threshold,
        params=spec["params"],
        train_seconds=train_seconds,
        inference_ms_per_1k=inference_ms_per_1k,
        y_val=splits.y_val,
        val_proba=val_proba,
        y_test=splits.y_test,
        test_proba=test_proba,
        feature_columns=feature_columns,
    )
    return ModelRunArtifact(spec["name"], model, threshold, val_proba, test_proba, report, spec["params"])


def fit_best_xgboost(
    splits: ExperimentSplits,
    feature_columns: list[str],
    fixed_params: dict[str, Any] | None = None,
    random_state: int | None = None,
) -> ModelRunArtifact:
    resolved_random_state = resolve_random_state(random_state)
    scale_pos_weight = max(1.0, float((splits.y_train == 0).sum() / max((splits.y_train == 1).sum(), 1)))

    if fixed_params is None:
        candidates = APP_CONFIG.training.candidate_params
    else:
        candidates = (fixed_params,)

    best_artifact: ModelRunArtifact | None = None
    overall_start = time.perf_counter()

    for params in candidates:
        model = XGBClassifier(
            objective="binary:logistic",
            eval_metric="logloss",
            random_state=resolved_random_state,
            n_jobs=APP_CONFIG.training.n_jobs,
            scale_pos_weight=scale_pos_weight,
            max_delta_step=APP_CONFIG.training.max_delta_step,
            tree_method="hist",
            **params,
        )
        model.fit(splits.X_train[feature_columns], splits.y_train)
        val_proba = model.predict_proba(splits.X_val[feature_columns])[:, 1]
        threshold, val_metrics = find_best_threshold(splits.y_val, val_proba)
        ranking_score = val_metrics["auc"] + val_metrics["f1"]

        infer_start = time.perf_counter()
        test_proba = model.predict_proba(splits.X_test[feature_columns])[:, 1]
        infer_seconds = time.perf_counter() - infer_start
        inference_ms_per_1k = (infer_seconds / max(len(splits.X_test), 1)) * 1_000_000

        report = summarize_model_run(
            model_name="xgboost",
            family="XGBClassifier",
            threshold=threshold,
            params=params,
            train_seconds=0.0,
            inference_ms_per_1k=inference_ms_per_1k,
            y_val=splits.y_val,
            val_proba=val_proba,
            y_test=splits.y_test,
            test_proba=test_proba,
            feature_columns=feature_columns,
        )
        report["validation"]["ranking_score"] = ranking_score

        artifact = ModelRunArtifact("xgboost", model, threshold, val_proba, test_proba, report, dict(params))
        if best_artifact is None or ranking_score > best_artifact.report["validation"]["ranking_score"]:
            best_artifact = artifact

    if best_artifact is None:
        raise RuntimeError("No XGBoost candidate finished during the research experiment.")

    best_artifact.report["train_seconds"] = round(time.perf_counter() - overall_start, 4)
    best_artifact.report["search_mode"] = "candidate_grid" if fixed_params is None else "fixed_params"
    return best_artifact


def ieee_feature_groups() -> dict[str, list[str]]:
    return {
        "transaction_core": [
            "transaction_amt_log1p",
            "tx_hour",
            "tx_day",
            "product_cd_hash",
            "card1",
            "card2",
            "card3",
            "card5",
            "addr1",
            "addr2",
            "dist1",
            "dist2",
            "card4_hash",
            "card6_hash",
            "p_email_hash",
            "r_email_hash",
        ],
        "identity": [
            "device_type_hash",
            "device_info_hash",
            "id30_hash",
            "id31_hash",
            "id33_hash",
            "is_mobile",
        ],
        "contextual_aggregates": [
            "card_id_hash",
            "merchant_id_hash",
            "location_id_hash",
            "c_sum",
            "d_sum",
            "missing_ratio",
            "email_match",
        ],
        "online_behavior": [
            "tx_count_24h",
            "avg_amount_7d",
            "device_tx_count_24h",
            "location_tx_count_24h",
            "merchant_tx_count_24h",
            "location_fraud_rate",
            "ip_fraud_rate",
            "merchant_fraud_rate",
        ],
        "llm_analysis": [
            "llm_risk_score",
            "llm_reason_count",
            "llm_high_risk_flag",
            "llm_review_flag",
            "llm_category_hash",
        ],
    }


def paysim_feature_groups() -> dict[str, list[str]]:
    return {
        "transaction_core": [
            "amount_log1p",
            "oldbalanceOrg",
            "newbalanceOrig",
            "oldbalanceDest",
            "newbalanceDest",
            "type_encoded",
        ],
        "identity": [],
        "contextual_aggregates": [
            "balance_diff",
            "amount_ratio",
            "org_balance_delta_ratio",
            "hour_of_day",
            "is_night_tx",
            "recipient_new_flag",
        ],
        "online_behavior": [
            "tx_count_24h",
            "avg_amount_7d",
            "device_tx_count_24h",
            "location_tx_count_24h",
            "merchant_tx_count_24h",
            "location_fraud_rate",
            "ip_fraud_rate",
            "merchant_fraud_rate",
        ],
        "llm_analysis": [
            "llm_risk_score",
            "llm_reason_count",
            "llm_high_risk_flag",
            "llm_review_flag",
            "llm_category_hash",
        ],
    }


def feature_group_map(source: str) -> dict[str, list[str]]:
    return ieee_feature_groups() if source == "ieee" else paysim_feature_groups()


def feature_ablation_sets(source: str, full_feature_columns: list[str]) -> list[dict[str, Any]]:
    groups = feature_group_map(source)
    transaction_core = groups["transaction_core"]
    identity = groups["identity"]
    contextual = groups["contextual_aggregates"]
    online = groups["online_behavior"]
    llm_analysis = groups.get("llm_analysis", [])

    configs = [
        {"name": "full_feature_set", "feature_columns": full_feature_columns, "note": "Full engineered feature set."},
        {
            "name": "no_identity",
            "feature_columns": [feature for feature in full_feature_columns if feature not in set(identity)],
            "note": "Removes device and identity-derived fields.",
        },
        {
            "name": "no_online_behavior",
            "feature_columns": [feature for feature in full_feature_columns if feature not in set(online)],
            "note": "Removes velocity and historical risk lookup features.",
        },
        {
            "name": "no_llm_analysis",
            "feature_columns": [feature for feature in full_feature_columns if feature not in set(llm_analysis)],
            "note": "Removes the LLM-style risk, review, and semantic category features.",
        },
        {
            "name": "no_contextual_aggregates",
            "feature_columns": [feature for feature in full_feature_columns if feature not in set(contextual)],
            "note": "Removes aggregate context and entity-hash context features.",
        },
        {
            "name": "transaction_core_only",
            "feature_columns": [feature for feature in transaction_core if feature in set(full_feature_columns)],
            "note": "Keeps only direct transaction-side features.",
        },
    ]

    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, ...]] = set()
    for config in configs:
        key = tuple(config["feature_columns"])
        if key and key not in seen:
            seen.add(key)
            deduped.append(config)
    return deduped


def prediction_from_artifact(
    artifact: ModelRunArtifact,
    feature_columns: list[str],
    X_frame: pd.DataFrame,
) -> tuple[np.ndarray, list[list[dict[str, float | str]]]]:
    proba = artifact.model.predict_proba(X_frame[feature_columns])[:, 1]
    contribs = artifact.model.get_booster().predict(DMatrix(X_frame[feature_columns]), pred_contribs=True)
    explanations: list[list[dict[str, float | str]]] = []

    for row in contribs:
        impacts = row[:-1]
        top_indices = np.argsort(np.abs(impacts))[-3:][::-1]
        items: list[dict[str, float | str]] = []
        max_weight = max((abs(float(impacts[index])) for index in top_indices), default=1.0) or 1.0
        for index in top_indices:
            impact = float(impacts[index])
            items.append(
                {
                    "feature": feature_columns[index],
                    "impact": impact,
                    "weight": round(abs(impact) / max_weight, 4),
                }
            )
        explanations.append(items)
    return proba, explanations


def review_and_finalize(validated: AgentDecision, tool_results: dict[str, Any], prediction: ModelPrediction) -> tuple[str, str]:
    ip_result = tool_results.get("check_ip_blacklist", {})
    device_result = tool_results.get("verify_device_id", {})
    merchant_result = tool_results.get("query_merchant_risk", {})

    if ip_result.get("blacklisted") and prediction.score >= 0.55:
        return "block", "Offline replay blocked because the IP is blacklisted and the score stayed elevated."

    if merchant_result.get("merchant_fraud_rate", 0.0) >= 0.1 and device_result.get("needs_step_up"):
        return "block", "Offline replay blocked due to risky merchant history plus suspicious device behavior."

    if validated.recommended_action == "approve" and (
        device_result.get("needs_step_up") or ip_result.get("ip_fraud_rate", 0.0) >= 0.05
    ):
        return "review", "Offline replay upgraded approval to manual review because external checks still showed moderate risk."

    if validated.recommended_action == "block" and prediction.score < 0.55:
        return "review", "Offline replay softened the block to review because the transaction stayed in the medium band."

    reviewer_note = {
        "approve": "Offline replay confirmed approve.",
        "review": "Offline replay placed the transaction on hold.",
        "block": "Offline replay confirmed block.",
    }[validated.recommended_action]
    return validated.recommended_action, reviewer_note


def replay_medium_agent(
    store: FeatureStore,
    event: Any,
    lookup: Any,
    prediction: ModelPrediction,
) -> dict[str, Any]:
    tool_results: dict[str, Any] = {}
    explanation = prediction.explanation

    if lookup.tx_count_24h >= 2 or prediction.score >= 0.40:
        tool_results["get_card_history"] = store.card_summary(event.card_id, event.step)
    if lookup.ip_fraud_rate >= 0.05 or lookup.location_fraud_rate >= 0.05 or prediction.score >= 0.55:
        tool_results["check_ip_blacklist"] = store.ip_summary(event.ip_address)
    if lookup.device_tx_count_24h == 0 or any(item["feature"] == "device_tx_count_24h" for item in explanation):
        tool_results["verify_device_id"] = store.device_summary(event.device_id, event.step)
    if lookup.merchant_fraud_rate >= 0.03 or lookup.merchant_tx_count_24h <= 1:
        tool_results["query_merchant_risk"] = store.merchant_summary(event.merchant_id, event.step)
    if not tool_results:
        tool_results["get_card_history"] = store.card_summary(event.card_id, event.step)

    structured = build_decision_payload(
        {
            "event": event.to_dict(),
            "lookup": lookup.to_dict(),
            "prediction": prediction.to_dict(),
            "tool_results": tool_results,
            "agent_summary": "Offline investigator replay consolidated the tool evidence.",
        }
    )
    agent_fields = {f.name for f in AgentDecision.__dataclass_fields__.values()}
    validated = AgentDecision(**{k: v for k, v in structured.items() if k in agent_fields})
    final_action, reviewer_note = review_and_finalize(validated, tool_results, prediction)
    return {
        "action": final_action,
        "reviewer_note": reviewer_note,
        "tool_results": tool_results,
        "structured_output": structured,
    }


def action_policy_report(actions: list[str], y_true: pd.Series, medium_routes: list[bool]) -> dict[str, Any]:
    pred_block = np.array([1 if action == "block" else 0 for action in actions], dtype=int)
    y_true_array = y_true.to_numpy(dtype=int)

    block_precision = float(precision_score(y_true_array, pred_block, zero_division=0))
    block_recall = float(recall_score(y_true_array, pred_block, zero_division=0))
    block_f1 = float(f1_score(y_true_array, pred_block, zero_division=0))

    positives = int((y_true_array == 1).sum())
    negatives = int((y_true_array == 0).sum())
    review_count = sum(action == "review" for action in actions)
    block_count = int(pred_block.sum())
    approve_count = sum(action == "approve" for action in actions)
    fraud_in_review = sum(action == "review" and label == 1 for action, label in zip(actions, y_true_array, strict=True))
    normal_in_block = sum(action == "block" and label == 0 for action, label in zip(actions, y_true_array, strict=True))

    return {
        "approve_count": approve_count,
        "review_count": review_count,
        "block_count": block_count,
        "approve_rate": round(approve_count / max(len(actions), 1), 6),
        "review_rate": round(review_count / max(len(actions), 1), 6),
        "block_rate": round(block_count / max(len(actions), 1), 6),
        "block_precision": block_precision,
        "block_recall": block_recall,
        "block_f1": block_f1,
        "fraud_review_rate": round(fraud_in_review / max(positives, 1), 6),
        "review_fraud_share": round(fraud_in_review / max(review_count, 1), 6),
        "false_positive_block_rate": round(normal_in_block / max(negatives, 1), 6),
        "medium_case_count": int(sum(medium_routes)),
        "medium_case_share": round(sum(medium_routes) / max(len(actions), 1), 6),
    }


def markdown_table(headers: list[str], rows: list[list[Any]]) -> str:
    header_line = "| " + " | ".join(headers) + " |"
    divider = "| " + " | ".join(["---"] * len(headers)) + " |"
    body = ["| " + " | ".join(str(item) for item in row) + " |" for row in rows]
    return "\n".join([header_line, divider, *body])


def write_report(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix == ".json":
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    else:
        path.write_text(str(payload), encoding="utf-8")


def write_csv_report(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)


def build_baseline_markdown(report: dict[str, Any]) -> str:
    rows = []
    for item in report["models"]:
        rows.append(
            [
                item["model_name"],
                item["family"],
                item["selected_threshold"],
                f"{item['validation']['metrics']['auc']:.4f}",
                f"{item['test']['metrics']['auc']:.4f}",
                f"{item['test']['pr_auc']:.4f}",
                f"{item['test']['metrics']['f1']:.4f}",
                f"{item['test']['metrics']['precision']:.4f}",
                f"{item['test']['metrics']['recall']:.4f}",
                f"{item['train_seconds']:.2f}",
            ]
        )

    return "\n".join(
        [
            "# Baseline Comparison",
            "",
            f"- Source: `{report['source']}`",
            f"- Random seed: `{report['random_state']}`",
            f"- Split strategy: `{report['split_strategy']}`",
            "",
            markdown_table(
                ["Model", "Family", "Threshold", "Val AUC", "Test AUC", "Test PR AUC", "Test F1", "Precision", "Recall", "Train s"],
                rows,
            ),
        ]
    )


def build_feature_ablation_markdown(report: dict[str, Any]) -> str:
    rows = []
    for item in report["ablations"]:
        rows.append(
            [
                item["name"],
                item["feature_count"],
                f"{item['test_metrics']['auc']:.4f}",
                f"{item['test_pr_auc']:.4f}",
                f"{item['test_metrics']['f1']:.4f}",
                f"{item['delta_vs_full']['auc']:+.4f}",
                f"{item['delta_vs_full']['f1']:+.4f}",
                item["note"],
            ]
        )

    return "\n".join(
        [
            "# Feature Ablation",
            "",
            f"- Source: `{report['source']}`",
            f"- Fixed XGBoost params: `{json.dumps(report['fixed_xgboost_params'], ensure_ascii=False)}`",
            "",
            markdown_table(
                ["Ablation", "Features", "Test AUC", "Test PR AUC", "Test F1", "Delta AUC", "Delta F1", "Note"],
                rows,
            ),
        ]
    )


def build_medium_branch_markdown(report: dict[str, Any]) -> str:
    rows = []
    for item in report["policies"]:
        rows.append(
            [
                item["policy_name"],
                f"{item['approve_rate']:.4f}",
                f"{item['review_rate']:.4f}",
                f"{item['block_rate']:.4f}",
                f"{item['block_precision']:.4f}",
                f"{item['block_recall']:.4f}",
                f"{item['block_f1']:.4f}",
                f"{item['fraud_review_rate']:.4f}",
                f"{item['review_fraud_share']:.4f}",
                item["note"],
            ]
        )

    return "\n".join(
        [
            "# Medium Branch Ablation",
            "",
            f"- Source: `{report['source']}`",
            f"- Selected threshold for score-only baseline: `{report['selected_threshold']}`",
            f"- Medium cases on test split: `{report['medium_case_count']}`",
            "",
            markdown_table(
                [
                    "Policy",
                    "Approve Rate",
                    "Review Rate",
                    "Block Rate",
                    "Block Precision",
                    "Block Recall",
                    "Block F1",
                    "Fraud Review Rate",
                    "Review Fraud Share",
                    "Note",
                ],
                rows,
            ),
        ]
    )


def run_baseline_comparison(
    splits: ExperimentSplits,
    outputs: ResearchRunOutputs,
    random_state: int | None = None,
) -> tuple[dict[str, Any], ModelRunArtifact, dict[str, ModelRunArtifact]]:
    feature_columns = splits.bundle.feature_columns
    results: list[dict[str, Any]] = []
    artifacts: dict[str, ModelRunArtifact] = {}

    resolved_random_state = resolve_random_state(random_state)
    xgb_artifact = fit_best_xgboost(splits, feature_columns, random_state=resolved_random_state)
    results.append(xgb_artifact.report)
    artifacts[xgb_artifact.model_name] = xgb_artifact

    for spec in build_model_specs(random_state=resolved_random_state):
        artifact = fit_generic_baseline(spec, splits, feature_columns, random_state=resolved_random_state)
        results.append(artifact.report)
        artifacts[artifact.model_name] = artifact

    results.sort(key=lambda item: (item["test"]["metrics"]["auc"], item["test"]["metrics"]["f1"]), reverse=True)
    report = {
        "source": splits.bundle.source,
        "data_path": splits.bundle.data_path,
        "identity_data_path": splits.bundle.identity_data_path,
        "artifact_scope": outputs.artifact_scope,
        "random_state": resolved_random_state,
        "split_strategy": split_strategy_for_source(splits.bundle.source),
        "split": {
            "total_rows": len(splits.bundle.dataset),
            "train_rows": len(splits.train_df),
            "validation_rows": len(splits.val_df),
            "test_rows": len(splits.test_df),
        },
        "models": results,
    }

    write_csv_report(
        pd.DataFrame(
        [
            {
                "model_name": item["model_name"],
                "family": item["family"],
                "selected_threshold": item["selected_threshold"],
                "validation_auc": item["validation"]["metrics"]["auc"],
                "test_auc": item["test"]["metrics"]["auc"],
                "test_pr_auc": item["test"]["pr_auc"],
                "test_f1": item["test"]["metrics"]["f1"],
                "test_precision": item["test"]["metrics"]["precision"],
                "test_recall": item["test"]["metrics"]["recall"],
                "train_seconds": item["train_seconds"],
            }
            for item in results
        ]
        ),
        outputs.baseline_comparison_csv_path,
    )
    write_report(outputs.baseline_comparison_path, report)
    write_report(outputs.baseline_comparison_markdown_path, build_baseline_markdown(report))
    return report, xgb_artifact, artifacts


def run_feature_ablation(
    splits: ExperimentSplits,
    xgb_params: dict[str, Any],
    outputs: ResearchRunOutputs,
) -> dict[str, Any]:
    full_feature_columns = splits.bundle.feature_columns
    ablations = feature_ablation_sets(splits.bundle.source, full_feature_columns)
    items: list[dict[str, Any]] = []
    full_test_metrics: dict[str, float] | None = None

    for config in ablations:
        artifact = fit_best_xgboost(splits, config["feature_columns"], fixed_params=xgb_params)
        test_metrics = artifact.report["test"]["metrics"]
        test_pr_auc = artifact.report["test"]["pr_auc"]
        item = {
            "name": config["name"],
            "feature_count": len(config["feature_columns"]),
            "feature_columns": config["feature_columns"],
            "note": config["note"],
            "selected_threshold": artifact.threshold,
            "validation_metrics": artifact.report["validation"]["metrics"],
            "validation_pr_auc": artifact.report["validation"]["pr_auc"],
            "test_metrics": test_metrics,
            "test_pr_auc": test_pr_auc,
            "train_seconds": artifact.report["train_seconds"],
        }
        if config["name"] == "full_feature_set":
            full_test_metrics = {"auc": test_metrics["auc"], "f1": test_metrics["f1"], "pr_auc": test_pr_auc}
        items.append(item)

    if full_test_metrics is None:
        raise RuntimeError("Feature ablation did not produce the full feature set result.")

    for item in items:
        item["delta_vs_full"] = {
            "auc": round(item["test_metrics"]["auc"] - full_test_metrics["auc"], 6),
            "f1": round(item["test_metrics"]["f1"] - full_test_metrics["f1"], 6),
            "pr_auc": round(item["test_pr_auc"] - full_test_metrics["pr_auc"], 6),
        }

    report = {
        "source": splits.bundle.source,
        "data_path": splits.bundle.data_path,
        "identity_data_path": splits.bundle.identity_data_path,
        "artifact_scope": outputs.artifact_scope,
        "random_state": APP_CONFIG.training.random_state,
        "split_strategy": split_strategy_for_source(splits.bundle.source),
        "fixed_xgboost_params": xgb_params,
        "ablations": items,
    }

    write_csv_report(
        pd.DataFrame(
        [
            {
                "name": item["name"],
                "feature_count": item["feature_count"],
                "test_auc": item["test_metrics"]["auc"],
                "test_pr_auc": item["test_pr_auc"],
                "test_f1": item["test_metrics"]["f1"],
                "delta_auc": item["delta_vs_full"]["auc"],
                "delta_f1": item["delta_vs_full"]["f1"],
                "delta_pr_auc": item["delta_vs_full"]["pr_auc"],
                "note": item["note"],
            }
            for item in items
        ]
        ),
        outputs.feature_ablation_csv_path,
    )
    write_report(outputs.feature_ablation_path, report)
    write_report(outputs.feature_ablation_markdown_path, build_feature_ablation_markdown(report))
    return report


def run_medium_branch_ablation(
    splits: ExperimentSplits,
    xgb_artifact: ModelRunArtifact,
    outputs: ResearchRunOutputs,
) -> dict[str, Any]:
    calibration = build_routing_calibration(
        xgb_artifact.validation_proba,
        low_quantile=APP_CONFIG.training.calibration_low_quantile,
        high_quantile=APP_CONFIG.training.calibration_high_quantile,
        low_threshold=APP_CONFIG.routing.low,
        high_threshold=APP_CONFIG.routing.high,
    )
    test_proba, explanations = prediction_from_artifact(xgb_artifact, splits.bundle.feature_columns, splits.X_test)

    store = FeatureStore()
    history_df = splits.bundle.dataset.iloc[:split_indices(len(splits.bundle.dataset))[1]].copy()
    for row in history_df.itertuples(index=False):
        event = event_from_row(row, source=splits.bundle.source)
        store.observe(event, event.is_fraud)

    policy_actions: dict[str, list[str]] = {
        "score_threshold_block": [],
        "route_without_agent": [],
        "route_medium_auto_approve": [],
        "route_with_medium_agent": [],
    }
    medium_routes: list[bool] = []

    for index, row in enumerate(splits.test_df.itertuples(index=False)):
        event = event_from_row(row, source=splits.bundle.source)
        lookup = store.lookup(event)
        raw_probability = float(test_proba[index])
        score = calibrate_operational_score(raw_probability, calibration)
        route = route_score(score, low_threshold=APP_CONFIG.routing.low, high_threshold=APP_CONFIG.routing.high)
        medium_routes.append(route == "medium")

        prediction = ModelPrediction(
            score=score,
            raw_probability=raw_probability,
            route=route,
            explanation=explanations[index],
            latency_ms=0.0,
        )

        policy_actions["score_threshold_block"].append("block" if raw_probability >= xgb_artifact.threshold else "approve")
        policy_actions["route_without_agent"].append("approve" if route == "low" else "block" if route == "high" else "review")
        policy_actions["route_medium_auto_approve"].append("block" if route == "high" else "approve")

        if route == "medium":
            replay = replay_medium_agent(store, event, lookup, prediction)
            policy_actions["route_with_medium_agent"].append(replay["action"])
        else:
            policy_actions["route_with_medium_agent"].append("approve" if route == "low" else "block")

        store.observe_activity(event)

    notes = {
        "score_threshold_block": "Binary threshold baseline with no routing and no manual review state.",
        "route_without_agent": "Original routing but every medium case is held for human review.",
        "route_medium_auto_approve": "Routing with the medium band auto-approved to show the risk of removing investigation.",
        "route_with_medium_agent": "Routing with the offline replay of the current investigator logic on medium cases.",
    }

    policy_reports = []
    for policy_name, actions in policy_actions.items():
        metrics = action_policy_report(actions, splits.y_test, medium_routes)
        policy_reports.append({"policy_name": policy_name, "note": notes[policy_name], **metrics})

    policy_reports.sort(key=lambda item: (item["block_f1"], item["block_recall"]), reverse=True)
    report = {
        "source": splits.bundle.source,
        "data_path": splits.bundle.data_path,
        "identity_data_path": splits.bundle.identity_data_path,
        "artifact_scope": outputs.artifact_scope,
        "selected_threshold": xgb_artifact.threshold,
        "routing_calibration": calibration,
        "medium_case_count": int(sum(medium_routes)),
        "policies": policy_reports,
    }

    write_csv_report(pd.DataFrame(policy_reports), outputs.medium_branch_ablation_csv_path)
    write_report(outputs.medium_branch_ablation_path, report)
    write_report(outputs.medium_branch_ablation_markdown_path, build_medium_branch_markdown(report))
    return report


def build_robustness_markdown(report: dict[str, Any]) -> str:
    rows = []
    for item in report["multi_seed_summary"]:
        rows.append(
            [
                item["model_name"],
                ",".join(str(seed) for seed in item["seeds"]),
                f"{item['test_metrics']['auc']['mean']:.4f} +/- {item['test_metrics']['auc']['std']:.4f}",
                f"{item['test_metrics']['f1']['mean']:.4f} +/- {item['test_metrics']['f1']['std']:.4f}",
                f"{item['test_metrics']['precision']['mean']:.4f} +/- {item['test_metrics']['precision']['std']:.4f}",
                f"{item['test_metrics']['recall']['mean']:.4f} +/- {item['test_metrics']['recall']['std']:.4f}",
                f"{item['test_metrics']['pr_auc']['mean']:.4f} +/- {item['test_metrics']['pr_auc']['std']:.4f}",
            ]
        )

    xgb_ci = report["confidence_intervals"]["xgboost"]
    baseline_name = report["best_baseline"]["model_name"]
    baseline_ci = report["confidence_intervals"][baseline_name]
    mcnemar = report["mcnemar_test"]
    return "\n".join(
        [
            "# Robustness Validation",
            "",
            f"- Source: `{report['source']}`",
            f"- Seeds: `{report['seeds']}`",
            f"- Bootstrap iterations: `{report['bootstrap_iterations']}`",
            f"- Best single-seed baseline: `{baseline_name}`",
            "",
            markdown_table(
                ["Model", "Seeds", "AUC mean+/-std", "F1 mean+/-std", "Precision mean+/-std", "Recall mean+/-std", "PR AUC mean+/-std"],
                rows,
            ),
            "",
            "## XGBoost 95% Bootstrap CI",
            "",
            f"- AUC: `{xgb_ci['auc']['ci95_low']:.6f}` to `{xgb_ci['auc']['ci95_high']:.6f}`",
            f"- F1: `{xgb_ci['f1']['ci95_low']:.6f}` to `{xgb_ci['f1']['ci95_high']:.6f}`",
            f"- Precision: `{xgb_ci['precision']['ci95_low']:.6f}` to `{xgb_ci['precision']['ci95_high']:.6f}`",
            f"- Recall: `{xgb_ci['recall']['ci95_low']:.6f}` to `{xgb_ci['recall']['ci95_high']:.6f}`",
            "",
            f"## McNemar Test vs {baseline_name}",
            "",
            f"- better_for_xgboost: `{mcnemar['better_for_xgboost']}`",
            f"- better_for_baseline: `{mcnemar['better_for_baseline']}`",
            f"- discordant: `{mcnemar['discordant']}`",
            f"- chi_square: `{mcnemar['chi_square']}`",
            f"- p_value: `{mcnemar['p_value']}`",
            "",
            f"## {baseline_name} 95% Bootstrap CI",
            "",
            f"- AUC: `{baseline_ci['auc']['ci95_low']:.6f}` to `{baseline_ci['auc']['ci95_high']:.6f}`",
            f"- F1: `{baseline_ci['f1']['ci95_low']:.6f}` to `{baseline_ci['f1']['ci95_high']:.6f}`",
        ]
    )


def run_robustness_validation(
    splits: ExperimentSplits,
    xgb_artifact: ModelRunArtifact,
    baseline_artifacts: dict[str, ModelRunArtifact],
    outputs: ResearchRunOutputs,
    seeds: list[int] | None = None,
    bootstrap_iterations: int | None = None,
) -> dict[str, Any]:
    resolved_seeds = list(seeds or APP_CONFIG.research.repeated_seed_values)
    resolved_bootstrap_iterations = bootstrap_iterations or APP_CONFIG.research.bootstrap_iterations
    baseline_candidates = [artifact for name, artifact in baseline_artifacts.items() if name != "xgboost"]
    best_baseline_artifact = max(
        baseline_candidates,
        key=lambda item: (item.report["test"]["metrics"]["auc"], item.report["test"]["metrics"]["f1"]),
    )

    seed_runs: list[dict[str, Any]] = []
    for seed in resolved_seeds:
        xgb_seed_artifact = fit_best_xgboost(splits, splits.bundle.feature_columns, random_state=seed)
        baseline_spec = next(
            spec for spec in build_model_specs(random_state=seed)
            if spec["name"] == best_baseline_artifact.model_name
        )
        baseline_seed_artifact = fit_generic_baseline(
            baseline_spec,
            splits,
            splits.bundle.feature_columns,
            random_state=seed,
        )
        for artifact in (xgb_seed_artifact, baseline_seed_artifact):
            snapshot = metric_snapshot(splits.y_test, artifact.test_proba, artifact.threshold)
            seed_runs.append(
                {
                    "model_name": artifact.model_name,
                    "family": artifact.report["family"],
                    "random_state": seed,
                    "selected_threshold": artifact.threshold,
                    "test_metrics": snapshot,
                }
            )

    confidence_intervals = {
        "xgboost": bootstrap_confidence_intervals(
            splits.y_test,
            xgb_artifact.test_proba,
            xgb_artifact.threshold,
            iterations=resolved_bootstrap_iterations,
            random_state=resolved_seeds[0],
        ),
        best_baseline_artifact.model_name: bootstrap_confidence_intervals(
            splits.y_test,
            best_baseline_artifact.test_proba,
            best_baseline_artifact.threshold,
            iterations=resolved_bootstrap_iterations,
            random_state=resolved_seeds[0] + 1000,
        ),
    }
    mcnemar = mcnemar_error_test(
        splits.y_test,
        xgb_artifact.test_proba,
        xgb_artifact.threshold,
        best_baseline_artifact.test_proba,
        best_baseline_artifact.threshold,
    )

    report = {
        "source": splits.bundle.source,
        "data_path": splits.bundle.data_path,
        "identity_data_path": splits.bundle.identity_data_path,
        "artifact_scope": outputs.artifact_scope,
        "seeds": resolved_seeds,
        "bootstrap_iterations": resolved_bootstrap_iterations,
        "best_baseline": {
            "model_name": best_baseline_artifact.model_name,
            "family": best_baseline_artifact.report["family"],
        },
        "multi_seed_runs": seed_runs,
        "multi_seed_summary": summarize_seed_runs(seed_runs),
        "confidence_intervals": confidence_intervals,
        "mcnemar_test": {
            "baseline_model": best_baseline_artifact.model_name,
            "better_for_xgboost": mcnemar["better_for_a"],
            "better_for_baseline": mcnemar["better_for_b"],
            "discordant": mcnemar["discordant"],
            "chi_square": mcnemar["chi_square"],
            "p_value": mcnemar["p_value"],
        },
    }

    csv_rows = []
    for item in report["multi_seed_summary"]:
        csv_rows.append(
            {
                "model_name": item["model_name"],
                "seeds": ",".join(str(seed) for seed in item["seeds"]),
                "auc_mean": item["test_metrics"]["auc"]["mean"],
                "auc_std": item["test_metrics"]["auc"]["std"],
                "f1_mean": item["test_metrics"]["f1"]["mean"],
                "f1_std": item["test_metrics"]["f1"]["std"],
                "precision_mean": item["test_metrics"]["precision"]["mean"],
                "precision_std": item["test_metrics"]["precision"]["std"],
                "recall_mean": item["test_metrics"]["recall"]["mean"],
                "recall_std": item["test_metrics"]["recall"]["std"],
                "pr_auc_mean": item["test_metrics"]["pr_auc"]["mean"],
                "pr_auc_std": item["test_metrics"]["pr_auc"]["std"],
            }
        )
    write_csv_report(pd.DataFrame(csv_rows), outputs.robustness_validation_csv_path)
    write_report(outputs.robustness_validation_path, report)
    write_report(outputs.robustness_validation_markdown_path, build_robustness_markdown(report))
    return report


def build_external_validation_markdown(report: dict[str, Any]) -> str:
    if not report.get("available", False):
        return "\n".join(
            [
                "# External Validation",
                "",
                f"- Status: `{report['status']}`",
                f"- Reason: `{report['reason']}`",
            ]
        )

    validation_mode = report.get("validation_mode", "secondary_dataset_benchmark")

    if validation_mode == "frozen_vs_native_benchmark":
        models = report.get("models", [])
        frozen = next((m for m in models if m.get("evaluation_mode") == "frozen_model_external_validation"), None)
        native = next((m for m in models if m.get("evaluation_mode") == "ieee_native_retrained"), None)

        def _row(item: dict[str, Any], mode_label: str) -> list[str]:
            return [
                item["model_name"],
                item["family"],
                f"{item['test']['metrics']['auc']:.4f}",
                f"{item['test']['pr_auc']:.4f}",
                f"{item['test']['metrics']['f1']:.4f}",
                f"{item['test']['metrics']['precision']:.4f}",
                f"{item['test']['metrics']['recall']:.4f}",
                mode_label,
            ]

        rows = []
        if native:
            rows.append(_row(native, f"native ({native['feature_count']} IEEE features)"))
        if frozen:
            rows.append(_row(frozen, f"frozen ({frozen['feature_count']} PaySim features, aligned)"))
        native_feature_count = native["feature_count"] if native else "native"

        return "\n".join(
            [
                "# External Validation — IEEE-CIS Dual Benchmark",
                "",
                f"- Source: `{report['source']}`",
                f"- Data path: `{report['data_path']}`",
                f"- Alignment method: `{report['feature_alignment']['method']}`",
                f"- Frozen eval rows: `{report['split']['evaluation_rows']}`",
                f"- Native train / val / test: `{report['split']['train_rows']}` / `{report['split']['validation_rows']}` / `{report['split']['test_rows']}`",
                "",
                "## Benchmark legend",
                "",
                "| Model | Description |",
                "| --- | --- |",
                f"| `xgboost_ieee_retrained` | XGBoost trained from scratch on 70% IEEE-CIS ({native_feature_count} native features, chronological split) |",
                "| `xgboost_frozen_paysim` | PaySim-trained weights frozen, applied to IEEE-CIS via semantic feature alignment |",
                "",
                markdown_table(
                    ["Model", "Family", "Test AUC", "PR AUC", "F1", "Precision", "Recall", "Mode"],
                    rows,
                ),
                "",
                "## Interpretation",
                "",
                "- High `xgboost_ieee_retrained` AUC confirms IEEE-CIS features discriminate fraud when trained in-distribution.",
                "- Lower `xgboost_frozen_paysim` AUC reflects cross-dataset distribution shift — expected: PaySim fraud",
                "  relies on balance-drain patterns; IEEE-CIS fraud relies on card/device fingerprints.",
                "- Improved alignment (M-field balance_diff proxy, velocity-based account proxy) raises frozen AUC",
                "  versus the prior rank-quantile-only projection.",
            ]
        )

    rows = []
    for item in report["models"]:
        rows.append(
            [
                item["model_name"],
                item["family"],
                f"{item['test']['metrics']['auc']:.4f}",
                f"{item['test']['pr_auc']:.4f}",
                f"{item['test']['metrics']['f1']:.4f}",
                f"{item['test']['metrics']['precision']:.4f}",
                f"{item['test']['metrics']['recall']:.4f}",
            ]
        )

    return "\n".join(
        [
            "# External Validation",
            "",
            f"- Validation mode: `{validation_mode}`",
            f"- External source: `{report['source']}`",
            f"- Data path: `{report['data_path']}`",
            f"- Identity path: `{report['identity_data_path'] or 'N/A'}`",
            f"- Split strategy: `{report['split_strategy']}`",
            f"- Random seed: `{report['random_state']}`",
            f"- Purpose: `out-of-distribution check against overfitting on the primary dataset`",
            (
                "- Freeze protocol: `PaySim model weights and threshold are reused; IEEE-CIS labels are used only for final metrics.`"
                if validation_mode == "frozen_model_external_validation" else
                "- Protocol: `secondary dataset benchmark`"
            ),
            (
                f"- Feature alignment: `{report['feature_alignment']['method']}`"
                if report.get("feature_alignment") else
                ""
            ),
            "",
            markdown_table(
                ["Model", "Family", "Test AUC", "Test PR AUC", "Test F1", "Precision", "Recall"],
                rows,
            ),
        ]
    )


def run_external_validation(
    primary_source: str,
    outputs: ResearchRunOutputs,
    sample_size: int | None = None,
    random_state: int | None = None,
    external_data_path: str | None = None,
    frozen_xgb_artifact: ModelRunArtifact | None = None,
    primary_splits: ExperimentSplits | None = None,
) -> dict[str, Any]:
    resolved_data_path = resolve_external_validation_data_path(primary_source, external_data_path)
    if resolved_data_path is None:
        report = {
            "available": False,
            "status": "skipped",
            "reason": "No secondary dataset was found for external validation.",
        }
        write_report(outputs.external_validation_path, report)
        write_report(outputs.external_validation_markdown_path, build_external_validation_markdown(report))
        return report

    resolved_random_state = resolve_random_state(random_state)

    if primary_source == "paysim" and frozen_xgb_artifact is not None and primary_splits is not None:
        # --- Part 1: frozen PaySim model evaluated on full IEEE-CIS (no retraining) ---
        external_bundle = build_unlabeled_ieee_external_dataset(resolved_data_path, sample_size=sample_size)
        aligned_features = align_ieee_dataset_to_paysim_features(
            external_bundle.dataset,
            primary_splits.train_df,
        )
        y_external = external_bundle.dataset["isFraud"].astype(int)
        external_proba = frozen_xgb_artifact.model.predict_proba(aligned_features[PAYSIM_FEATURE_COLUMNS])[:, 1]
        frozen_metrics = classification_metrics(y_external, external_proba, frozen_xgb_artifact.threshold)
        frozen_model_report = {
            "model_name": "xgboost_frozen_paysim",
            "family": "XGBClassifier",
            "feature_count": len(PAYSIM_FEATURE_COLUMNS),
            "selected_threshold": frozen_xgb_artifact.threshold,
            "frozen_model_source": primary_source,
            "frozen_model_train_rows": len(primary_splits.train_df),
            "evaluation_mode": "frozen_model_external_validation",
            "params": frozen_xgb_artifact.params,
            "test": {
                "metrics": frozen_metrics,
                "pr_auc": pr_auc_score(y_external, external_proba),
                "confusion_matrix": confusion_payload(y_external, external_proba, frozen_xgb_artifact.threshold),
            },
        }

        # --- Part 2: IEEE-native benchmark — retrain XGBoost from scratch on IEEE-CIS ---
        ieee_native_splits = prepare_experiment_splits(
            data_path=resolved_data_path, sample_size=sample_size, source="ieee"
        )
        ieee_native_feature_columns = ieee_native_splits.bundle.feature_columns
        ieee_xgb_artifact = fit_best_xgboost(
            ieee_native_splits, ieee_native_feature_columns, random_state=resolved_random_state
        )
        ieee_native_metrics = classification_metrics(
            ieee_native_splits.y_test, ieee_xgb_artifact.test_proba, ieee_xgb_artifact.threshold
        )
        ieee_native_report = {
            "model_name": "xgboost_ieee_retrained",
            "family": "XGBClassifier",
            "feature_count": len(ieee_native_feature_columns),
            "selected_threshold": ieee_xgb_artifact.threshold,
            "frozen_model_source": "ieee_native",
            "evaluation_mode": "ieee_native_retrained",
            "params": ieee_xgb_artifact.params,
            "test": {
                "metrics": ieee_native_metrics,
                "pr_auc": pr_auc_score(ieee_native_splits.y_test, ieee_xgb_artifact.test_proba),
                "confusion_matrix": confusion_payload(
                    ieee_native_splits.y_test, ieee_xgb_artifact.test_proba, ieee_xgb_artifact.threshold
                ),
            },
        }

        # Sort descending by AUC so the best model is models[0] (used by summary markdown)
        models = sorted(
            [frozen_model_report, ieee_native_report],
            key=lambda m: m["test"]["metrics"]["auc"],
            reverse=True,
        )

        report = {
            "available": True,
            "validation_mode": "frozen_vs_native_benchmark",
            "source": external_bundle.source,
            "data_path": external_bundle.data_path,
            "identity_data_path": external_bundle.identity_data_path,
            "artifact_scope": outputs.artifact_scope,
            "random_state": resolved_random_state,
            "split_strategy": "external_all_rows_no_ieee_fit (frozen) / ieee_chronological_70_15_15 (native)",
            "split": {
                "evaluation_rows": len(external_bundle.dataset),
                "train_rows": len(ieee_native_splits.train_df),
                "validation_rows": len(ieee_native_splits.val_df),
                "test_rows": len(ieee_native_splits.test_df),
            },
            "feature_alignment": {
                "method": "semantic_proxy_with_mfield_balance_diff",
                "target_feature_count": len(PAYSIM_FEATURE_COLUMNS),
                "target_features": list(PAYSIM_FEATURE_COLUMNS),
                "ieee_label_usage": "labels_used_only_after_prediction_for_metrics",
            },
            "models": models,
        }
        write_csv_report(
            pd.DataFrame(
                [
                    {
                        "model_name": m["model_name"],
                        "family": m["family"],
                        "validation_mode": m["evaluation_mode"],
                        "selected_threshold": m["selected_threshold"],
                        "test_auc": m["test"]["metrics"]["auc"],
                        "test_pr_auc": m["test"]["pr_auc"],
                        "test_f1": m["test"]["metrics"]["f1"],
                        "test_precision": m["test"]["metrics"]["precision"],
                        "test_recall": m["test"]["metrics"]["recall"],
                    }
                    for m in models
                ]
            ),
            outputs.external_validation_csv_path,
        )
        write_report(outputs.external_validation_path, report)
        write_report(outputs.external_validation_markdown_path, build_external_validation_markdown(report))
        return report

    external_splits = prepare_experiment_splits(data_path=resolved_data_path, sample_size=sample_size)
    feature_columns = external_splits.bundle.feature_columns
    xgb_artifact = fit_best_xgboost(external_splits, feature_columns, random_state=resolved_random_state)
    hgb_spec = next(
        spec for spec in build_model_specs(random_state=resolved_random_state)
        if spec["name"] == "hist_gradient_boosting"
    )
    hgb_artifact = fit_generic_baseline(hgb_spec, external_splits, feature_columns, random_state=resolved_random_state)
    models = sorted(
        [xgb_artifact.report, hgb_artifact.report],
        key=lambda item: (item["test"]["metrics"]["auc"], item["test"]["metrics"]["f1"]),
        reverse=True,
    )

    report = {
        "available": True,
        "validation_mode": "secondary_dataset_benchmark_refit",
        "source": external_splits.bundle.source,
        "data_path": external_splits.bundle.data_path,
        "identity_data_path": external_splits.bundle.identity_data_path,
        "artifact_scope": outputs.artifact_scope,
        "random_state": resolved_random_state,
        "split_strategy": split_strategy_for_source(external_splits.bundle.source),
        "split": {
            "total_rows": len(external_splits.bundle.dataset),
            "train_rows": len(external_splits.train_df),
            "validation_rows": len(external_splits.val_df),
            "test_rows": len(external_splits.test_df),
        },
        "models": models,
    }

    write_csv_report(
        pd.DataFrame(
            [
                {
                    "model_name": item["model_name"],
                    "family": item["family"],
                    "validation_mode": report["validation_mode"],
                    "selected_threshold": item["selected_threshold"],
                    "test_auc": item["test"]["metrics"]["auc"],
                    "test_pr_auc": item["test"]["pr_auc"],
                    "test_f1": item["test"]["metrics"]["f1"],
                    "test_precision": item["test"]["metrics"]["precision"],
                    "test_recall": item["test"]["metrics"]["recall"],
                }
                for item in models
            ]
        ),
        outputs.external_validation_csv_path,
    )
    write_report(outputs.external_validation_path, report)
    write_report(outputs.external_validation_markdown_path, build_external_validation_markdown(report))
    return report


def build_research_suite_markdown(report: dict[str, Any]) -> str:
    best_baseline = report["baseline"]["models"][0]
    best_feature = max(report["feature_ablation"]["ablations"], key=lambda item: item["test_metrics"]["auc"])
    best_policy = max(report["medium_branch"]["policies"], key=lambda item: item["block_f1"])
    robustness_best = report["robustness"]["multi_seed_summary"][0]
    external_models = report["external_validation"].get("models", [])
    external_best = external_models[0] if external_models else None
    native_external = next(
        (item for item in external_models if item.get("evaluation_mode") == "ieee_native_retrained"),
        None,
    )
    frozen_external = next(
        (item for item in external_models if item.get("evaluation_mode") == "frozen_model_external_validation"),
        None,
    )
    full_feature = next(
        item for item in report["feature_ablation"]["ablations"]
        if item["name"] == "full_feature_set"
    )
    llm_free_feature = next(
        (item for item in report["feature_ablation"]["ablations"] if item["name"] == "no_llm_analysis"),
        None,
    )
    return "\n".join(
        [
            "# Research Experiment Suite",
            "",
            f"- Source: `{report['source']}`",
            f"- Split strategy: `{report['split_strategy']}`",
            f"- Total rows: `{report['split']['total_rows']}`",
            "",
            "## Dataset Strategy",
            "",
            "- PaySim is the primary dataset for architecture performance: training, routing, agent replay, and monitoring/deploy flow.",
            "- IEEE-CIS is the external validation dataset for out-of-distribution evidence against overfitting on PaySim.",
            "",
            "## Best Baseline",
            "",
            f"- Model: `{best_baseline['model_name']}`",
            f"- Test AUC: `{best_baseline['test']['metrics']['auc']:.6f}`",
            f"- Test F1: `{best_baseline['test']['metrics']['f1']:.6f}`",
            f"- Test PR AUC: `{best_baseline['test']['pr_auc']:.6f}`",
            "",
            "## Best Feature Configuration",
            "",
            f"- Ablation: `{best_feature['name']}`",
            f"- Test AUC: `{best_feature['test_metrics']['auc']:.6f}`",
            f"- Test F1: `{best_feature['test_metrics']['f1']:.6f}`",
            (
                ""
                if llm_free_feature is None else
                f"- LLM feature delta vs no-LLM: AUC `{full_feature['test_metrics']['auc'] - llm_free_feature['test_metrics']['auc']:+.6f}`, "
                f"F1 `{full_feature['test_metrics']['f1'] - llm_free_feature['test_metrics']['f1']:+.6f}`"
            ),
            "",
            "## Best Medium-Branch Policy",
            "",
            f"- Policy: `{best_policy['policy_name']}`",
            f"- Block F1: `{best_policy['block_f1']:.6f}`",
            f"- Block Recall: `{best_policy['block_recall']:.6f}`",
            f"- Review Rate: `{best_policy['review_rate']:.6f}`",
            "",
            "## Robustness",
            "",
            f"- Multi-seed best mean AUC model: `{robustness_best['model_name']}`",
            f"- Mean test AUC: `{robustness_best['test_metrics']['auc']['mean']:.6f}` +/- `{robustness_best['test_metrics']['auc']['std']:.6f}`",
            f"- Mean test F1: `{robustness_best['test_metrics']['f1']['mean']:.6f}` +/- `{robustness_best['test_metrics']['f1']['std']:.6f}`",
            f"- XGBoost 95% AUC CI: `{report['robustness']['confidence_intervals']['xgboost']['auc']['ci95_low']:.6f}` to `{report['robustness']['confidence_intervals']['xgboost']['auc']['ci95_high']:.6f}`",
            f"- McNemar p-value vs best baseline: `{report['robustness']['mcnemar_test']['p_value']}`",
            "",
            "## External Validation",
            "",
            (
                "- External validation: `skipped`"
                if external_best is None else
                f"- External source: `{report['external_validation']['source']}`"
            ),
            (
                ""
                if external_best is None else
                f"- Validation mode: `{report['external_validation'].get('validation_mode', 'secondary_dataset_benchmark')}`"
            ),
            *([
                f"- IEEE-native XGBoost AUC: `{native_external['test']['metrics']['auc']:.6f}` (trained on IEEE-CIS train split, {native_external['feature_count']} native features)",
                f"- Frozen PaySim AUC on IEEE-CIS: `{frozen_external['test']['metrics']['auc']:.6f}` (cross-dataset, expected lower due to distribution shift)",
            ] if (
                external_best is not None
                and native_external is not None
                and frozen_external is not None
                and report["external_validation"].get("validation_mode") == "frozen_vs_native_benchmark"
            ) else [
                (
                    ""
                    if external_best is None else
                    f"- Best external model: `{external_best['model_name']}` with external AUC `{external_best['test']['metrics']['auc']:.6f}`"
                ),
            ]),
            "",
            "## Artifacts",
            "",
            f"- Baseline comparison: `{report['artifacts']['baseline_comparison_json']}`",
            f"- Feature ablation: `{report['artifacts']['feature_ablation_json']}`",
            f"- Medium branch ablation: `{report['artifacts']['medium_branch_ablation_json']}`",
            f"- Robustness validation: `{report['artifacts']['robustness_validation_json']}`",
            f"- External validation: `{report['artifacts']['external_validation_json']}`",
        ]
    )


def run_research_suite(
    data_path: str | None = None,
    sample_size: int | None = None,
    seeds: list[int] | None = None,
    bootstrap_iterations: int | None = None,
    external_data_path: str | None = None,
    source: str | None = None,
) -> dict[str, Any]:
    outputs = resolve_research_outputs(sample_size)
    splits = prepare_experiment_splits(data_path=data_path, sample_size=sample_size, source=source)
    baseline_report, xgb_artifact, baseline_artifacts = run_baseline_comparison(splits, outputs)
    feature_ablation_report = run_feature_ablation(splits, xgb_artifact.params, outputs)
    medium_branch_report = run_medium_branch_ablation(splits, xgb_artifact, outputs)
    robustness_report = run_robustness_validation(
        splits,
        xgb_artifact,
        baseline_artifacts,
        outputs,
        seeds=seeds,
        bootstrap_iterations=bootstrap_iterations,
    )
    external_validation_report = run_external_validation(
        splits.bundle.source,
        outputs,
        sample_size=sample_size,
        random_state=APP_CONFIG.training.random_state,
        external_data_path=external_data_path,
        frozen_xgb_artifact=xgb_artifact,
        primary_splits=splits,
    )

    report = {
        "source": splits.bundle.source,
        "data_path": splits.bundle.data_path,
        "identity_data_path": splits.bundle.identity_data_path,
        "artifact_scope": outputs.artifact_scope,
        "random_state": APP_CONFIG.training.random_state,
        "split_strategy": split_strategy_for_source(splits.bundle.source),
        "split": {
            "total_rows": len(splits.bundle.dataset),
            "train_rows": len(splits.train_df),
            "validation_rows": len(splits.val_df),
            "test_rows": len(splits.test_df),
        },
        "baseline": baseline_report,
        "feature_ablation": feature_ablation_report,
        "medium_branch": medium_branch_report,
        "robustness": robustness_report,
        "external_validation": external_validation_report,
        "artifacts": {
            "baseline_comparison_json": str(outputs.baseline_comparison_path),
            "feature_ablation_json": str(outputs.feature_ablation_path),
            "medium_branch_ablation_json": str(outputs.medium_branch_ablation_path),
            "robustness_validation_json": str(outputs.robustness_validation_path),
            "external_validation_json": str(outputs.external_validation_path),
        },
    }
    write_report(outputs.research_suite_path, report)
    write_report(outputs.research_suite_markdown_path, build_research_suite_markdown(report))
    return report
