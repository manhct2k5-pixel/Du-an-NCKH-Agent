"""
Train an IEEE-CIS optimized benchmark for paper reporting.

This script is intentionally separate from the PaySim-first FraudFlow pipeline.
It uses IEEE-CIS native columns, including V1..V339, train-only encodings for
categorical features, chronological 70/15/15 split, and validation PR-curve
threshold tuning.

Run:
    .venv/bin/python scripts/ieee_cis_optimized_benchmark.py
    .venv/bin/python scripts/ieee_cis_optimized_benchmark.py --sample-size 100000
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_curve,
    roc_auc_score,
)
from sklearn.ensemble import IsolationForest
from xgboost import XGBClassifier

from fraud_flow.config import APP_CONFIG
from fraud_flow.features import deterministic_time_sample

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


REPORT_JSON = Path("artifacts/reports/ieee_optimized_report.json")
REPORT_CSV = Path("artifacts/reports/ieee_optimized_report.csv")
ABLATION_JSON = Path("artifacts/reports/ieee_optimized_ablation.json")
ABLATION_CSV = Path("artifacts/reports/ieee_optimized_ablation.csv")
ROBUSTNESS_JSON = Path("artifacts/reports/ieee_optimized_robustness.json")
ROBUSTNESS_CSV = Path("artifacts/reports/ieee_optimized_robustness.csv")
SIDECAR_JSON = Path("artifacts/reports/ieee_optimized_sidecar.json")
SIDECAR_CSV = Path("artifacts/reports/ieee_optimized_sidecar.csv")
PLOT_DIR = Path("artifacts/reports/plots")

BASE_DROP_COLUMNS = {"TransactionID", "isFraud"}
CATEGORICAL_INTERACTIONS = {
    "card1_addr1": ("card1", "addr1"),
    "card1_product": ("card1", "ProductCD"),
    "card1_email": ("card1", "P_emaildomain"),
    "addr_product": ("addr1", "ProductCD"),
    "email_pair": ("P_emaildomain", "R_emaildomain"),
    "device_browser": ("DeviceType", "id_31"),
}

PARAM_CANDIDATES: tuple[dict[str, Any], ...] = (
    {
        "n_estimators": 500,
        "max_depth": 5,
        "learning_rate": 0.04,
        "subsample": 0.90,
        "colsample_bytree": 0.80,
        "min_child_weight": 20,
        "reg_lambda": 5.0,
        "scale_pos_weight_multiplier": 1.0,
    },
    {
        "n_estimators": 650,
        "max_depth": 6,
        "learning_rate": 0.03,
        "subsample": 0.90,
        "colsample_bytree": 0.75,
        "min_child_weight": 10,
        "reg_lambda": 4.0,
        "scale_pos_weight_multiplier": 0.75,
    },
    {
        "n_estimators": 800,
        "max_depth": 4,
        "learning_rate": 0.025,
        "subsample": 0.95,
        "colsample_bytree": 0.70,
        "min_child_weight": 30,
        "reg_alpha": 0.5,
        "reg_lambda": 8.0,
        "scale_pos_weight_multiplier": 1.0,
    },
    {
        "n_estimators": 450,
        "max_depth": 7,
        "learning_rate": 0.035,
        "subsample": 0.85,
        "colsample_bytree": 0.70,
        "min_child_weight": 8,
        "reg_alpha": 0.25,
        "reg_lambda": 3.0,
        "scale_pos_weight_multiplier": 0.60,
    },
)


def resolve_identity_path(transaction_path: Path, identity_path: str | None) -> Path:
    if identity_path:
        return Path(identity_path)
    return transaction_path.with_name("train_identity.csv")


def split_positions(total_rows: int) -> tuple[int, int]:
    train_end = int(total_rows * APP_CONFIG.training.train_frac)
    val_end = int(total_rows * (APP_CONFIG.training.train_frac + APP_CONFIG.training.val_frac))
    return train_end, val_end


def load_ieee_frame(transaction_path: Path, identity_path: Path, sample_size: int | None) -> pd.DataFrame:
    start = time.perf_counter()
    transaction = pd.read_csv(transaction_path, low_memory=False)
    identity = pd.read_csv(identity_path, low_memory=False)
    frame = transaction.merge(identity, on="TransactionID", how="left")
    frame = frame.sort_values(["TransactionDT", "TransactionID"]).reset_index(drop=True)
    if sample_size and sample_size < len(frame):
        frame = deterministic_time_sample(frame, sample_size)

    elapsed = time.perf_counter() - start
    print(f"[ieee-opt] Loaded {len(frame):,} rows x {len(frame.columns):,} cols in {elapsed:.1f}s")
    return frame


def add_native_features(frame: pd.DataFrame) -> pd.DataFrame:
    features = frame.copy()
    features["transaction_amt_log1p"] = np.log1p(features["TransactionAmt"].clip(lower=0))
    features["tx_hour"] = (features["TransactionDT"] // 3600) % 24
    features["tx_day"] = features["TransactionDT"] // (3600 * 24)
    features["tx_week"] = features["tx_day"] // 7
    features["amount_cents"] = np.round((features["TransactionAmt"] % 1) * 100).astype("float32")

    p_email = features.get("P_emaildomain", pd.Series("", index=features.index)).fillna("").astype(str)
    r_email = features.get("R_emaildomain", pd.Series("", index=features.index)).fillna("").astype(str)
    features["email_match"] = ((p_email != "") & (p_email == r_email)).astype("int8")

    if "DeviceType" in features.columns:
        features["is_mobile"] = features["DeviceType"].fillna("").astype(str).str.lower().eq("mobile").astype("int8")

    candidate_feature_columns = [col for col in features.columns if col not in BASE_DROP_COLUMNS]
    features["missing_count"] = features[candidate_feature_columns].isna().sum(axis=1).astype("int16")
    features["missing_ratio"] = (features["missing_count"] / max(len(candidate_feature_columns), 1)).astype("float32")

    for new_column, parts in CATEGORICAL_INTERACTIONS.items():
        values = []
        for part in parts:
            if part in features.columns:
                values.append(features[part].fillna("__missing__").astype(str))
            else:
                values.append(pd.Series("__missing__", index=features.index))
        combined = values[0]
        for value in values[1:]:
            combined = combined + "|" + value
        features[new_column] = combined

    return features


def downcast_numeric(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    for column in result.select_dtypes(include=["float64"]).columns:
        result[column] = pd.to_numeric(result[column], downcast="float")
    for column in result.select_dtypes(include=["int64"]).columns:
        if column not in ("TransactionID", "isFraud"):
            result[column] = pd.to_numeric(result[column], downcast="integer")
    return result


def select_v_columns(
    train_features: pd.DataFrame,
    y_train: pd.Series,
    max_missing_rate: float,
    top_v_features: int | None,
) -> list[str]:
    v_columns = [column for column in train_features.columns if column.startswith("V")]
    if not v_columns:
        return []

    missing_rate = train_features[v_columns].isna().mean()
    kept = missing_rate[missing_rate <= max_missing_rate].index.tolist()
    if top_v_features and top_v_features < len(kept):
        correlations = train_features[kept].corrwith(y_train).abs().fillna(0.0)
        kept = correlations.sort_values(ascending=False).head(top_v_features).index.tolist()
    return kept


def encode_categorical_splits(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    X_val: pd.DataFrame,
    X_test: pd.DataFrame,
    smoothing: float,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    categorical_columns = X_train.select_dtypes(include=["object", "category", "bool"]).columns.tolist()
    global_rate = float(y_train.mean())
    encoded_columns: list[str] = []
    metadata: dict[str, Any] = {
        "categorical_columns": categorical_columns,
        "smoothing": smoothing,
        "global_fraud_rate": global_rate,
    }

    train_encoded = X_train.copy()
    val_encoded = X_val.copy()
    test_encoded = X_test.copy()
    target_frame = pd.DataFrame({"target": y_train.to_numpy()}, index=train_encoded.index)

    for column in categorical_columns:
        train_values = train_encoded[column].fillna("__missing__").astype(str)
        stats = target_frame.groupby(train_values)["target"].agg(["sum", "count"])
        target_map = (stats["sum"] + global_rate * smoothing) / (stats["count"] + smoothing)
        freq_map = stats["count"] / max(len(train_values), 1)

        for frame in (train_encoded, val_encoded, test_encoded):
            values = frame[column].fillna("__missing__").astype(str)
            frame[f"{column}_freq"] = values.map(freq_map).fillna(0.0).astype("float32")
            frame[f"{column}_target"] = values.map(target_map).fillna(global_rate).astype("float32")

        encoded_columns.extend([f"{column}_freq", f"{column}_target"])

    train_encoded = train_encoded.drop(columns=categorical_columns)
    val_encoded = val_encoded.drop(columns=categorical_columns)
    test_encoded = test_encoded.drop(columns=categorical_columns)
    metadata["encoded_columns"] = encoded_columns
    return train_encoded, val_encoded, test_encoded, metadata


def best_threshold_from_pr_curve(y_true: pd.Series, proba: np.ndarray) -> tuple[float, dict[str, float]]:
    precision, recall, thresholds = precision_recall_curve(y_true, proba)
    if len(thresholds) == 0:
        threshold = 0.5
    else:
        f1_scores = (2 * precision[:-1] * recall[:-1]) / np.maximum(precision[:-1] + recall[:-1], 1e-12)
        threshold = float(thresholds[int(np.nanargmax(f1_scores))])
    return threshold, metrics_at_threshold(y_true, proba, threshold)


def metrics_at_threshold(y_true: pd.Series, proba: np.ndarray, threshold: float) -> dict[str, float]:
    pred = (proba >= threshold).astype(int)
    return {
        "accuracy": float(accuracy_score(y_true, pred)),
        "auc": float(roc_auc_score(y_true, proba)) if len(set(y_true)) > 1 else 0.0,
        "pr_auc": float(average_precision_score(y_true, proba)) if len(set(y_true)) > 1 else 0.0,
        "f1": float(f1_score(y_true, pred, zero_division=0)),
        "precision": float(precision_score(y_true, pred, zero_division=0)),
        "recall": float(recall_score(y_true, pred, zero_division=0)),
    }


def metrics_from_predictions(y_true: pd.Series, pred: np.ndarray, proba: np.ndarray | None = None) -> dict[str, float]:
    metrics = {
        "accuracy": float(accuracy_score(y_true, pred)),
        "f1": float(f1_score(y_true, pred, zero_division=0)),
        "precision": float(precision_score(y_true, pred, zero_division=0)),
        "recall": float(recall_score(y_true, pred, zero_division=0)),
    }
    if proba is not None and len(set(y_true)) > 1:
        metrics["auc"] = float(roc_auc_score(y_true, proba))
        metrics["pr_auc"] = float(average_precision_score(y_true, proba))
    return metrics


def confusion_payload(y_true: pd.Series, proba: np.ndarray, threshold: float) -> dict[str, int]:
    pred = (proba >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, pred, labels=[0, 1]).ravel()
    return {
        "true_negative": int(tn),
        "false_positive": int(fp),
        "false_negative": int(fn),
        "true_positive": int(tp),
    }


def confusion_from_predictions(y_true: pd.Series, pred: np.ndarray) -> dict[str, int]:
    tn, fp, fn, tp = confusion_matrix(y_true, pred, labels=[0, 1]).ravel()
    return {
        "true_negative": int(tn),
        "false_positive": int(fp),
        "false_negative": int(fn),
        "true_positive": int(tp),
    }


def build_prediction_report(
    model_name: str,
    family: str,
    candidate_index: int | str,
    params: dict[str, Any],
    train_seconds: float,
    y_val: pd.Series,
    val_proba: np.ndarray,
    y_test: pd.Series,
    test_proba: np.ndarray,
    feature_importance: dict[str, float] | None = None,
) -> dict[str, Any]:
    threshold, val_metrics = best_threshold_from_pr_curve(y_val, val_proba)
    test_metrics = metrics_at_threshold(y_test, test_proba, threshold)

    report = {
        "candidate_index": candidate_index,
        "model_name": model_name,
        "family": family,
        "params": params,
        "selected_threshold": threshold,
        "train_seconds": round(train_seconds, 4),
        "validation": {
            "metrics": val_metrics,
            "confusion_matrix": confusion_payload(y_val, val_proba, threshold),
        },
        "test": {
            "metrics": test_metrics,
            "confusion_matrix": confusion_payload(y_test, test_proba, threshold),
        },
        "ranking_score": val_metrics["pr_auc"] + val_metrics["f1"],
    }
    if feature_importance:
        report["top_feature_importance"] = feature_importance
    return report


def prepare_splits(
    frame: pd.DataFrame,
    max_missing_rate: float,
    top_v_features: int | None,
    smoothing: float,
) -> tuple[pd.DataFrame, pd.Series, pd.DataFrame, pd.Series, pd.DataFrame, pd.Series, dict[str, Any]]:
    engineered = downcast_numeric(add_native_features(frame))
    train_end, val_end = split_positions(len(engineered))

    train_df = engineered.iloc[:train_end].copy()
    val_df = engineered.iloc[train_end:val_end].copy()
    test_df = engineered.iloc[val_end:].copy()

    y_train = train_df["isFraud"].astype(int)
    y_val = val_df["isFraud"].astype(int)
    y_test = test_df["isFraud"].astype(int)

    X_train_all = train_df.drop(columns=list(BASE_DROP_COLUMNS))
    X_val_all = val_df.drop(columns=list(BASE_DROP_COLUMNS))
    X_test_all = test_df.drop(columns=list(BASE_DROP_COLUMNS))

    v_columns = select_v_columns(X_train_all, y_train, max_missing_rate=max_missing_rate, top_v_features=top_v_features)
    non_v_columns = [column for column in X_train_all.columns if not column.startswith("V")]
    selected_columns = non_v_columns + v_columns

    X_train = X_train_all[selected_columns]
    X_val = X_val_all[selected_columns]
    X_test = X_test_all[selected_columns]

    X_train, X_val, X_test, encoding_meta = encode_categorical_splits(
        X_train,
        y_train,
        X_val,
        X_test,
        smoothing=smoothing,
    )

    numeric_columns = X_train.columns.tolist()
    for frame_part in (X_train, X_val, X_test):
        for column in numeric_columns:
            if frame_part[column].dtype == "bool":
                frame_part[column] = frame_part[column].astype("int8")

    metadata = {
        "split": {
            "total_rows": len(engineered),
            "train_rows": len(X_train),
            "validation_rows": len(X_val),
            "test_rows": len(X_test),
            "train_fraud_rate": float(y_train.mean()),
            "validation_fraud_rate": float(y_val.mean()),
            "test_fraud_rate": float(y_test.mean()),
        },
        "feature_selection": {
            "max_missing_rate": max_missing_rate,
            "top_v_features": top_v_features,
            "selected_v_features": len(v_columns),
            "raw_selected_columns": len(selected_columns),
            "final_feature_count": len(numeric_columns),
        },
        "encoding": encoding_meta,
        "feature_columns": numeric_columns,
        "feature_groups": {
            "v_features": [column for column in numeric_columns if column.startswith("V")],
            "target_encoded": [column for column in numeric_columns if column.endswith("_target")],
            "frequency_encoded": [column for column in numeric_columns if column.endswith("_freq")],
            "interaction_encoded": [
                column
                for column in numeric_columns
                if any(column.startswith(f"{name}_") for name in CATEGORICAL_INTERACTIONS)
            ],
        },
    }
    return X_train, y_train, X_val, y_val, X_test, y_test, metadata


def feature_columns_for_profile(metadata: dict[str, Any], profile: str) -> list[str]:
    feature_columns = list(metadata["feature_columns"])
    feature_groups = metadata["feature_groups"]
    if profile == "full":
        return feature_columns
    if profile == "no_target_encoding":
        target_encoded = set(feature_groups["target_encoded"])
        return [column for column in feature_columns if column not in target_encoded]
    if profile == "no_frequency_encoding":
        frequency_encoded = set(feature_groups["frequency_encoded"])
        return [column for column in feature_columns if column not in frequency_encoded]
    if profile == "no_interaction_encoding":
        interaction_encoded = set(feature_groups["interaction_encoded"])
        return [column for column in feature_columns if column not in interaction_encoded]
    if profile == "top_120_v_features":
        v_features = set(feature_groups["v_features"])
        top_120_v = set(feature_groups["v_features"][:120])
        return [column for column in feature_columns if column not in v_features or column in top_120_v]
    raise ValueError(f"Unknown feature profile: {profile}")


def xgb_params_from_report(params: dict[str, Any], y_train: pd.Series, random_state: int) -> dict[str, Any]:
    xgb_params = dict(params)
    multiplier = float(xgb_params.pop("scale_pos_weight_multiplier", 1.0))
    if "scale_pos_weight" not in xgb_params:
        ratio = max(1.0, float((y_train == 0).sum() / max((y_train == 1).sum(), 1)))
        xgb_params["scale_pos_weight"] = ratio * multiplier
    return {
        "objective": "binary:logistic",
        "eval_metric": "aucpr",
        "random_state": random_state,
        "n_jobs": APP_CONFIG.training.n_jobs,
        "tree_method": "hist",
        "max_delta_step": APP_CONFIG.training.max_delta_step,
        **xgb_params,
    }


def train_fixed_xgboost(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    X_val: pd.DataFrame,
    y_val: pd.Series,
    X_test: pd.DataFrame,
    y_test: pd.Series,
    feature_columns: list[str],
    params: dict[str, Any],
    random_state: int,
    model_name: str,
    candidate_index: int | str,
) -> tuple[dict[str, Any], np.ndarray, np.ndarray]:
    start = time.perf_counter()
    model = XGBClassifier(**xgb_params_from_report(params, y_train, random_state))
    model.fit(X_train[feature_columns], y_train)
    train_seconds = time.perf_counter() - start
    val_proba = model.predict_proba(X_val[feature_columns])[:, 1]
    test_proba = model.predict_proba(X_test[feature_columns])[:, 1]
    report = build_prediction_report(
        model_name=model_name,
        family="XGBClassifier",
        candidate_index=candidate_index,
        params={
            **params,
            "random_state": random_state,
            "feature_count": len(feature_columns),
        },
        train_seconds=train_seconds,
        y_val=y_val,
        val_proba=val_proba,
        y_test=y_test,
        test_proba=test_proba,
        feature_importance=dict(
            sorted(
                zip(feature_columns, model.feature_importances_.tolist(), strict=False),
                key=lambda item: item[1],
                reverse=True,
            )[:25]
        ),
    )
    return report, val_proba, test_proba


def fit_xgboost_candidates(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    X_val: pd.DataFrame,
    y_val: pd.Series,
    X_test: pd.DataFrame,
    y_test: pd.Series,
    quick: bool,
) -> tuple[dict[str, Any], list[dict[str, Any]], np.ndarray, np.ndarray, dict[str, Any]]:
    ratio = max(1.0, float((y_train == 0).sum() / max((y_train == 1).sum(), 1)))
    candidates = PARAM_CANDIDATES[:1] if quick else PARAM_CANDIDATES
    reports: list[dict[str, Any]] = []
    best_report: dict[str, Any] | None = None
    best_val_proba: np.ndarray | None = None
    best_test_proba: np.ndarray | None = None
    best_single_report: dict[str, Any] | None = None
    ensemble_val_probas: list[np.ndarray] = []
    ensemble_test_probas: list[np.ndarray] = []

    for index, raw_params in enumerate(candidates, start=1):
        params = dict(raw_params)
        multiplier = float(params.pop("scale_pos_weight_multiplier", 1.0))
        model = XGBClassifier(
            objective="binary:logistic",
            eval_metric="aucpr",
            random_state=APP_CONFIG.training.random_state,
            n_jobs=APP_CONFIG.training.n_jobs,
            tree_method="hist",
            max_delta_step=APP_CONFIG.training.max_delta_step,
            scale_pos_weight=ratio * multiplier,
            **params,
        )

        print(f"[ieee-opt] Training candidate {index}/{len(candidates)}: {params}")
        start = time.perf_counter()
        model.fit(X_train, y_train)
        train_seconds = time.perf_counter() - start

        val_proba = model.predict_proba(X_val)[:, 1]
        test_proba = model.predict_proba(X_test)[:, 1]
        report = build_prediction_report(
            model_name="xgboost_ieee_optimized",
            family="XGBClassifier",
            candidate_index=index,
            params={
                **params,
                "scale_pos_weight": ratio * multiplier,
                "scale_pos_weight_multiplier": multiplier,
            },
            train_seconds=train_seconds,
            y_val=y_val,
            val_proba=val_proba,
            y_test=y_test,
            test_proba=test_proba,
            feature_importance=dict(
                sorted(
                    zip(X_train.columns, model.feature_importances_.tolist(), strict=False),
                    key=lambda item: item[1],
                    reverse=True,
                )[:25]
            ),
        )
        val_metrics = report["validation"]["metrics"]
        test_metrics = report["test"]["metrics"]
        reports.append(report)
        ensemble_val_probas.append(val_proba)
        ensemble_test_probas.append(test_proba)
        if best_report is None or report["ranking_score"] > best_report["ranking_score"]:
            best_report = report
            best_val_proba = val_proba
            best_test_proba = test_proba
        if best_single_report is None or report["ranking_score"] > best_single_report["ranking_score"]:
            best_single_report = report

        print(
            "[ieee-opt] "
            f"val F1={val_metrics['f1']:.4f}, val PR-AUC={val_metrics['pr_auc']:.4f}, "
            f"test F1={test_metrics['f1']:.4f}, test AUC={test_metrics['auc']:.4f}"
        )

    if len(ensemble_val_probas) >= 2:
        val_mean = np.mean(np.vstack(ensemble_val_probas), axis=0)
        test_mean = np.mean(np.vstack(ensemble_test_probas), axis=0)
        ensemble_report = build_prediction_report(
            model_name="xgboost_soft_voting_ensemble",
            family="ProbabilityAveragingEnsemble",
            candidate_index="ensemble_mean",
            params={
                "member_count": len(ensemble_val_probas),
                "aggregation": "mean_probability",
                "selection_metric": "validation_pr_auc_plus_f1",
            },
            train_seconds=sum(float(report["train_seconds"]) for report in reports),
            y_val=y_val,
            val_proba=val_mean,
            y_test=y_test,
            test_proba=test_mean,
        )
        reports.append(ensemble_report)
        if best_report is None or ensemble_report["ranking_score"] > best_report["ranking_score"]:
            best_report = ensemble_report
            best_val_proba = val_mean
            best_test_proba = test_mean
        val_metrics = ensemble_report["validation"]["metrics"]
        test_metrics = ensemble_report["test"]["metrics"]
        print(
            "[ieee-opt] Ensemble "
            f"val F1={val_metrics['f1']:.4f}, val PR-AUC={val_metrics['pr_auc']:.4f}, "
            f"test F1={test_metrics['f1']:.4f}, test AUC={test_metrics['auc']:.4f}"
        )

    if best_report is None or best_val_proba is None or best_test_proba is None or best_single_report is None:
        raise RuntimeError("No IEEE-CIS optimized candidate finished.")
    return best_report, reports, best_val_proba, best_test_proba, best_single_report


def run_ablation_suite(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    X_val: pd.DataFrame,
    y_val: pd.Series,
    X_test: pd.DataFrame,
    y_test: pd.Series,
    metadata: dict[str, Any],
    base_params: dict[str, Any],
) -> dict[str, Any]:
    feature_columns = list(metadata["feature_columns"])
    feature_groups = metadata["feature_groups"]
    v_features = set(feature_groups["v_features"])
    target_encoded = set(feature_groups["target_encoded"])
    frequency_encoded = set(feature_groups["frequency_encoded"])
    interaction_encoded = set(feature_groups["interaction_encoded"])
    top_120_v = set(feature_groups["v_features"][:120])

    ablation_sets = [
        ("full_optimized", feature_columns, "Full 365-feature optimized IEEE-CIS feature set."),
        ("no_v_features", [c for c in feature_columns if c not in v_features], "Remove V1-V339 features."),
        (
            "top_120_v_features",
            [c for c in feature_columns if c not in v_features or c in top_120_v],
            "Keep only the strongest 120 V features.",
        ),
        (
            "no_target_encoding",
            [c for c in feature_columns if c not in target_encoded],
            "Remove train-only target encoding columns.",
        ),
        (
            "no_frequency_encoding",
            [c for c in feature_columns if c not in frequency_encoded],
            "Remove frequency encoding columns.",
        ),
        (
            "no_interaction_encoding",
            [c for c in feature_columns if c not in interaction_encoded],
            "Remove encoded interaction features.",
        ),
    ]

    rows: list[dict[str, Any]] = []
    best_f1 = None
    for index, (name, columns, description) in enumerate(ablation_sets, start=1):
        print(f"[ieee-opt] Ablation {index}/{len(ablation_sets)}: {name} ({len(columns)} features)")
        report, _, _ = train_fixed_xgboost(
            X_train,
            y_train,
            X_val,
            y_val,
            X_test,
            y_test,
            columns,
            base_params,
            APP_CONFIG.training.random_state,
            "xgboost_ieee_ablation",
            name,
        )
        test_metrics = report["test"]["metrics"]
        if name == "full_optimized":
            best_f1 = test_metrics["f1"]
        rows.append(
            {
                "name": name,
                "description": description,
                "feature_count": len(columns),
                "selected_threshold": report["selected_threshold"],
                "test": report["test"],
                "validation": report["validation"],
                "delta_f1_vs_full": (
                    0.0 if best_f1 is None or name == "full_optimized" else test_metrics["f1"] - best_f1
                ),
            }
        )

    payload = {
        "source": "ieee",
        "validation_mode": "ieee_optimized_feature_ablation",
        "base_params": base_params,
        "ablations": rows,
    }
    ABLATION_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    pd.DataFrame(
        [
            {
                "name": row["name"],
                "feature_count": row["feature_count"],
                "threshold": row["selected_threshold"],
                "test_auc": row["test"]["metrics"]["auc"],
                "test_pr_auc": row["test"]["metrics"]["pr_auc"],
                "test_f1": row["test"]["metrics"]["f1"],
                "test_precision": row["test"]["metrics"]["precision"],
                "test_recall": row["test"]["metrics"]["recall"],
                "delta_f1_vs_full": row["delta_f1_vs_full"],
            }
            for row in rows
        ]
    ).to_csv(ABLATION_CSV, index=False)
    return payload


def run_robustness_suite(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    X_val: pd.DataFrame,
    y_val: pd.Series,
    X_test: pd.DataFrame,
    y_test: pd.Series,
    feature_columns: list[str],
    base_params: dict[str, Any],
    seeds: tuple[int, ...],
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for index, seed in enumerate(seeds, start=1):
        print(f"[ieee-opt] Robustness seed {index}/{len(seeds)}: {seed}")
        report, _, _ = train_fixed_xgboost(
            X_train,
            y_train,
            X_val,
            y_val,
            X_test,
            y_test,
            feature_columns,
            base_params,
            seed,
            "xgboost_ieee_optimized_seed",
            seed,
        )
        rows.append(report)

    metric_names = ["accuracy", "auc", "pr_auc", "f1", "precision", "recall"]
    summary = {}
    for metric in metric_names:
        values = np.array([row["test"]["metrics"][metric] for row in rows], dtype=float)
        summary[metric] = {
            "mean": float(values.mean()),
            "std": float(values.std(ddof=0)),
            "min": float(values.min()),
            "max": float(values.max()),
        }

    payload = {
        "source": "ieee",
        "validation_mode": "ieee_optimized_seed_robustness",
        "seeds": list(seeds),
        "base_params": base_params,
        "feature_count": len(feature_columns),
        "runs": rows,
        "summary": summary,
    }
    ROBUSTNESS_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    pd.DataFrame(
        [
            {
                "seed": row["candidate_index"],
                "threshold": row["selected_threshold"],
                **{f"test_{key}": value for key, value in row["test"]["metrics"].items()},
                **{f"validation_{key}": value for key, value in row["validation"]["metrics"].items()},
            }
            for row in rows
        ]
    ).to_csv(ROBUSTNESS_CSV, index=False)
    return payload


def evaluate_sidecar_policy(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    X_val: pd.DataFrame,
    y_val: pd.Series,
    X_test: pd.DataFrame,
    y_test: pd.Series,
    val_proba: np.ndarray,
    test_proba: np.ndarray,
    classifier_threshold: float,
    feature_importance: dict[str, float] | None,
) -> dict[str, Any]:
    if feature_importance:
        sidecar_features = [column for column in feature_importance if column in X_train.columns][:40]
    else:
        sidecar_features = X_train.columns[:40].tolist()

    print(f"[ieee-opt] Training anomaly sidecar on {len(sidecar_features)} features")
    model = IsolationForest(
        contamination=0.01,
        n_estimators=150,
        random_state=APP_CONFIG.training.random_state,
        n_jobs=-1,
    )
    train_legit = X_train.loc[y_train == 0, sidecar_features].fillna(0.0)
    model.fit(train_legit)

    train_scores_raw = model.score_samples(X_train[sidecar_features].fillna(0.0))
    score_min = float(train_scores_raw.min())
    score_max = float(train_scores_raw.max())

    def normalize(raw: np.ndarray) -> np.ndarray:
        span = score_max - score_min
        if span == 0:
            return np.zeros_like(raw)
        return 1.0 - np.clip((raw - score_min) / span, 0.0, 1.0)

    val_scores = normalize(model.score_samples(X_val[sidecar_features].fillna(0.0)))
    test_scores = normalize(model.score_samples(X_test[sidecar_features].fillna(0.0)))
    sidecar_threshold = float(np.percentile(val_scores, 95.0))

    def split_report(name: str, y_true: pd.Series, proba: np.ndarray, scores: np.ndarray) -> dict[str, Any]:
        classifier_pred = proba >= classifier_threshold
        sidecar_flag = scores >= sidecar_threshold
        combined_pred = classifier_pred | sidecar_flag
        fraud_mask = y_true.to_numpy(dtype=int) == 1
        false_negative_mask = fraud_mask & ~classifier_pred
        caught_fn = false_negative_mask & sidecar_flag
        return {
            "split": name,
            "classifier_threshold": classifier_threshold,
            "sidecar_threshold": sidecar_threshold,
            "classifier_only": {
                "metrics": metrics_from_predictions(y_true, classifier_pred.astype(int), proba),
                "confusion_matrix": confusion_from_predictions(y_true, classifier_pred.astype(int)),
            },
            "sidecar_flags": {
                "flagged_total": int(sidecar_flag.sum()),
                "flagged_fraud": int((sidecar_flag & fraud_mask).sum()),
                "flagged_legit": int((sidecar_flag & ~fraud_mask).sum()),
                "fraud_catch_rate": float((sidecar_flag & fraud_mask).sum() / max(fraud_mask.sum(), 1)),
                "false_flag_rate": float((sidecar_flag & ~fraud_mask).sum() / max((~fraud_mask).sum(), 1)),
                "classifier_false_negatives": int(false_negative_mask.sum()),
                "false_negatives_caught_by_sidecar": int(caught_fn.sum()),
            },
            "classifier_or_sidecar": {
                "metrics": metrics_from_predictions(y_true, combined_pred.astype(int), proba),
                "confusion_matrix": confusion_from_predictions(y_true, combined_pred.astype(int)),
            },
        }

    payload = {
        "source": "ieee",
        "validation_mode": "ieee_optimized_anomaly_sidecar_policy",
        "sidecar_model": "IsolationForest",
        "sidecar_features": sidecar_features,
        "sidecar_feature_count": len(sidecar_features),
        "validation": split_report("validation", y_val, val_proba, val_scores),
        "test": split_report("test", y_test, test_proba, test_scores),
    }
    SIDECAR_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    pd.DataFrame(
        [
            {
                "split": payload[split]["split"],
                "sidecar_threshold": payload[split]["sidecar_threshold"],
                "classifier_f1": payload[split]["classifier_only"]["metrics"]["f1"],
                "classifier_precision": payload[split]["classifier_only"]["metrics"]["precision"],
                "classifier_recall": payload[split]["classifier_only"]["metrics"]["recall"],
                "or_policy_f1": payload[split]["classifier_or_sidecar"]["metrics"]["f1"],
                "or_policy_precision": payload[split]["classifier_or_sidecar"]["metrics"]["precision"],
                "or_policy_recall": payload[split]["classifier_or_sidecar"]["metrics"]["recall"],
                **payload[split]["sidecar_flags"],
            }
            for split in ("validation", "test")
        ]
    ).to_csv(SIDECAR_CSV, index=False)
    return payload


def save_plot(fig: plt.Figure, name: str) -> None:
    PLOT_DIR.mkdir(parents=True, exist_ok=True)
    path = PLOT_DIR / name
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"[ieee-opt] Saved plot: {path}")


def threshold_sweep_rows(y_true: pd.Series, proba: np.ndarray, num_thresholds: int = 120) -> pd.DataFrame:
    thresholds = np.linspace(0.01, 0.99, num_thresholds)
    return pd.DataFrame(
        [
            {
                "threshold": float(threshold),
                **metrics_at_threshold(y_true, proba, float(threshold)),
            }
            for threshold in thresholds
        ]
    )


def generate_ieee_plots(
    report: dict[str, Any],
    y_val: pd.Series,
    val_proba: np.ndarray,
    y_test: pd.Series,
    test_proba: np.ndarray,
    ablation_report: dict[str, Any] | None,
    robustness_report: dict[str, Any] | None,
) -> dict[str, str]:
    artifacts: dict[str, str] = {}
    best = report["best_model"]

    fpr, tpr, _ = roc_curve(y_test, test_proba)
    fig, ax = plt.subplots(figsize=(7, 6))
    ax.plot(fpr, tpr, label=f"Test AUC = {best['test']['metrics']['auc']:.4f}", color="#1f77b4", linewidth=2)
    ax.plot([0, 1], [0, 1], "k--", linewidth=1, label="Random baseline")
    ax.set_xlabel("False Positive Rate")
    ax.set_ylabel("True Positive Rate")
    ax.set_title("IEEE-CIS ROC Curve - Optimized XGBoost")
    ax.legend(loc="lower right")
    ax.grid(alpha=0.3)
    save_plot(fig, "ieee_optimized_roc_curve.png")
    artifacts["roc_curve"] = str(PLOT_DIR / "ieee_optimized_roc_curve.png")

    precision, recall, _ = precision_recall_curve(y_test, test_proba)
    fig, ax = plt.subplots(figsize=(7, 6))
    ax.plot(
        recall,
        precision,
        label=f"Test PR-AUC = {best['test']['metrics']['pr_auc']:.4f}",
        color="#2ca02c",
        linewidth=2,
    )
    ax.set_xlabel("Recall")
    ax.set_ylabel("Precision")
    ax.set_title("IEEE-CIS Precision-Recall Curve")
    ax.legend(loc="upper right")
    ax.grid(alpha=0.3)
    save_plot(fig, "ieee_optimized_pr_curve.png")
    artifacts["pr_curve"] = str(PLOT_DIR / "ieee_optimized_pr_curve.png")

    sweep = threshold_sweep_rows(y_val, val_proba)
    sweep_path = Path("artifacts/reports/ieee_optimized_threshold_sweep.csv")
    sweep.to_csv(sweep_path, index=False)
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(sweep["threshold"], sweep["f1"], label="F1", color="#2ca02c", linewidth=2)
    ax.plot(sweep["threshold"], sweep["precision"], label="Precision", color="#1f77b4", linewidth=2)
    ax.plot(sweep["threshold"], sweep["recall"], label="Recall", color="#d62728", linewidth=2)
    ax.axvline(best["selected_threshold"], color="#111111", linestyle="--", linewidth=1, label="Selected threshold")
    ax.set_xlabel("Decision Threshold")
    ax.set_ylabel("Validation Score")
    ax.set_title("IEEE-CIS Threshold Sweep")
    ax.set_ylim(0, 1.05)
    ax.legend()
    ax.grid(alpha=0.3)
    save_plot(fig, "ieee_optimized_threshold_sweep.png")
    artifacts["threshold_sweep"] = str(PLOT_DIR / "ieee_optimized_threshold_sweep.png")
    artifacts["threshold_sweep_csv"] = str(sweep_path)

    importance = best.get("top_feature_importance")
    if not importance:
        importance = next(
            (candidate.get("top_feature_importance") for candidate in report["candidates"] if candidate.get("top_feature_importance")),
            None,
        )
    if importance:
        items = list(importance.items())[:20]
        labels = [item[0] for item in items][::-1]
        values = [item[1] for item in items][::-1]
        fig, ax = plt.subplots(figsize=(9, 7))
        ax.barh(labels, values, color="#1f77b4", alpha=0.85)
        ax.set_xlabel("XGBoost Feature Importance")
        ax.set_title("IEEE-CIS Top Feature Importance")
        ax.grid(axis="x", alpha=0.3)
        save_plot(fig, "ieee_optimized_feature_importance.png")
        artifacts["feature_importance"] = str(PLOT_DIR / "ieee_optimized_feature_importance.png")

    candidate_rows = report["candidates"]
    names = [str(row["candidate_index"]) for row in candidate_rows]
    fig, ax = plt.subplots(figsize=(9, 5))
    x = np.arange(len(names))
    width = 0.25
    for offset, metric, color in [
        (-width, "f1", "#2ca02c"),
        (0.0, "pr_auc", "#ff7f0e"),
        (width, "auc", "#1f77b4"),
    ]:
        values = [row["test"]["metrics"][metric] for row in candidate_rows]
        ax.bar(x + offset, values, width, label=metric.upper(), color=color, alpha=0.85)
    ax.set_xticks(x)
    ax.set_xticklabels(names)
    ax.set_xlabel("Candidate")
    ax.set_ylabel("Test Score")
    ax.set_title("IEEE-CIS Candidate Comparison")
    ax.set_ylim(0, 1.05)
    ax.legend()
    ax.grid(axis="y", alpha=0.3)
    save_plot(fig, "ieee_optimized_candidate_comparison.png")
    artifacts["candidate_comparison"] = str(PLOT_DIR / "ieee_optimized_candidate_comparison.png")

    if ablation_report:
        rows = ablation_report["ablations"]
        labels = [row["name"].replace("_", "\n") for row in rows]
        f1_values = [row["test"]["metrics"]["f1"] for row in rows]
        fig, ax = plt.subplots(figsize=(10, 5))
        bars = ax.bar(labels, f1_values, color="#9467bd", alpha=0.85)
        for bar, value in zip(bars, f1_values, strict=False):
            ax.text(bar.get_x() + bar.get_width() / 2, value + 0.005, f"{value:.3f}", ha="center", fontsize=8)
        ax.set_ylabel("Test F1")
        ax.set_title("IEEE-CIS Feature Ablation")
        ax.set_ylim(0, max(f1_values) + 0.08)
        ax.grid(axis="y", alpha=0.3)
        save_plot(fig, "ieee_optimized_feature_ablation.png")
        artifacts["feature_ablation"] = str(PLOT_DIR / "ieee_optimized_feature_ablation.png")

    if robustness_report:
        metrics = ["auc", "pr_auc", "f1", "precision", "recall"]
        means = [robustness_report["summary"][metric]["mean"] for metric in metrics]
        stds = [robustness_report["summary"][metric]["std"] for metric in metrics]
        fig, ax = plt.subplots(figsize=(8, 5))
        ax.bar([metric.upper() for metric in metrics], means, yerr=stds, color="#17becf", alpha=0.85, capsize=4)
        ax.set_ylabel("Test Score")
        ax.set_title("IEEE-CIS Robustness Across Seeds")
        ax.set_ylim(0, 1.05)
        ax.grid(axis="y", alpha=0.3)
        save_plot(fig, "ieee_optimized_robustness.png")
        artifacts["robustness"] = str(PLOT_DIR / "ieee_optimized_robustness.png")

    return artifacts


def write_reports(report: dict[str, Any]) -> None:
    REPORT_JSON.parent.mkdir(parents=True, exist_ok=True)
    REPORT_JSON.write_text(json.dumps(report, indent=2), encoding="utf-8")

    rows = []
    for item in report["candidates"]:
        rows.append(
            {
                "model": item["model_name"],
                "candidate_index": item["candidate_index"],
                "selected_as_best": item is report["best_model"],
                "mode": f"ieee_native_optimized_{report['feature_selection']['feature_profile']}",
                "feature_count": report["feature_selection"]["final_feature_count"],
                "selected_v_features": report["feature_selection"]["selected_v_features"],
                "threshold": item["selected_threshold"],
                **{f"test_{key}": value for key, value in item["test"]["metrics"].items()},
                **{f"validation_{key}": value for key, value in item["validation"]["metrics"].items()},
            }
        )
    pd.DataFrame(rows).to_csv(REPORT_CSV, index=False)


def run(args: argparse.Namespace) -> dict[str, Any]:
    transaction_path = Path(args.transaction_path)
    identity_path = resolve_identity_path(transaction_path, args.identity_path)
    frame = load_ieee_frame(transaction_path, identity_path, sample_size=args.sample_size)
    X_train, y_train, X_val, y_val, X_test, y_test, metadata = prepare_splits(
        frame,
        max_missing_rate=args.max_missing_rate,
        top_v_features=args.top_v_features,
        smoothing=args.target_smoothing,
    )
    primary_feature_columns = feature_columns_for_profile(metadata, args.feature_profile)
    primary_metadata = {
        **metadata,
        "feature_columns": primary_feature_columns,
        "feature_selection": {
            **metadata["feature_selection"],
            "feature_profile": args.feature_profile,
            "final_feature_count": len(primary_feature_columns),
        },
    }
    print(
        "[ieee-opt] Primary feature profile: "
        f"{args.feature_profile} ({len(primary_feature_columns)} features)"
    )
    best, candidates, best_val_proba, best_test_proba, best_single = fit_xgboost_candidates(
        X_train[primary_feature_columns],
        y_train,
        X_val[primary_feature_columns],
        y_val,
        X_test[primary_feature_columns],
        y_test,
        quick=args.quick,
    )

    base_params = dict(best_single["params"])
    base_params.pop("feature_count", None)
    base_params.pop("random_state", None)
    feature_columns = list(primary_metadata["feature_columns"])

    ablation_report = None
    robustness_report = None
    sidecar_report = None

    if not args.skip_ablation:
        ablation_report = run_ablation_suite(
            X_train,
            y_train,
            X_val,
            y_val,
            X_test,
            y_test,
            metadata,
            base_params,
        )

    if not args.skip_robustness:
        robustness_report = run_robustness_suite(
            X_train,
            y_train,
            X_val,
            y_val,
            X_test,
            y_test,
            feature_columns,
            base_params,
            seeds=tuple(args.robustness_seeds),
        )

    if not args.skip_sidecar:
        sidecar_report = evaluate_sidecar_policy(
            X_train,
            y_train,
            X_val,
            y_val,
            X_test,
            y_test,
            best_val_proba,
            best_test_proba,
            best["selected_threshold"],
            best.get("top_feature_importance") or best_single.get("top_feature_importance"),
        )

    report = {
        "available": True,
        "source": "ieee",
        "validation_mode": "ieee_native_optimized_chronological",
        "data_path": str(transaction_path),
        "identity_data_path": str(identity_path),
        "random_state": APP_CONFIG.training.random_state,
        "split_strategy": "chronological_70_15_15_by_TransactionDT_then_TransactionID",
        "sample_size": args.sample_size,
        **primary_metadata,
        "full_feature_metadata": metadata,
        "best_model": best,
        "candidates": candidates,
        "best_single_model": best_single,
        "ablation_summary": None if ablation_report is None else {
            "json": str(ABLATION_JSON),
            "csv": str(ABLATION_CSV),
            "best_drop": min(
                (row["delta_f1_vs_full"] for row in ablation_report["ablations"]),
                default=0.0,
            ),
        },
        "robustness_summary": None if robustness_report is None else robustness_report["summary"],
        "sidecar_summary": None if sidecar_report is None else {
            "json": str(SIDECAR_JSON),
            "csv": str(SIDECAR_CSV),
            "test": sidecar_report["test"],
        },
        "artifacts": {
            "json": str(REPORT_JSON),
            "csv": str(REPORT_CSV),
            "ablation_json": str(ABLATION_JSON) if ablation_report is not None else None,
            "ablation_csv": str(ABLATION_CSV) if ablation_report is not None else None,
            "robustness_json": str(ROBUSTNESS_JSON) if robustness_report is not None else None,
            "robustness_csv": str(ROBUSTNESS_CSV) if robustness_report is not None else None,
            "sidecar_json": str(SIDECAR_JSON) if sidecar_report is not None else None,
            "sidecar_csv": str(SIDECAR_CSV) if sidecar_report is not None else None,
        },
    }

    if not args.skip_plots:
        plot_artifacts = generate_ieee_plots(
            report,
            y_val,
            best_val_proba,
            y_test,
            best_test_proba,
            ablation_report,
            robustness_report,
        )
        report["artifacts"]["plots"] = plot_artifacts

    write_reports(report)
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run an IEEE-CIS optimized benchmark.")
    parser.add_argument(
        "--transaction-path",
        default=str(APP_CONFIG.transaction_data_path),
        help="Path to IEEE-CIS train_transaction.csv.",
    )
    parser.add_argument(
        "--identity-path",
        default=None,
        help="Path to IEEE-CIS train_identity.csv. Defaults to the transaction file directory.",
    )
    parser.add_argument("--sample-size", type=int, default=None, help="Optional deterministic time sample size.")
    parser.add_argument(
        "--max-missing-rate",
        type=float,
        default=0.98,
        help="Drop V columns whose train missing rate is above this value.",
    )
    parser.add_argument(
        "--top-v-features",
        type=int,
        default=220,
        help="Keep only the top V columns by absolute train correlation. Use 0 to keep all selected V columns.",
    )
    parser.add_argument(
        "--target-smoothing",
        type=float,
        default=30.0,
        help="Smoothing strength for train-only target encodings.",
    )
    parser.add_argument(
        "--feature-profile",
        choices=["full", "no_target_encoding", "no_frequency_encoding", "no_interaction_encoding", "top_120_v_features"],
        default="no_target_encoding",
        help="Primary IEEE feature profile used for candidate, robustness, sidecar, and plots.",
    )
    parser.add_argument("--quick", action="store_true", help="Train only the first candidate.")
    parser.add_argument("--skip-ablation", action="store_true", help="Skip IEEE feature ablation suite.")
    parser.add_argument("--skip-robustness", action="store_true", help="Skip repeated-seed robustness suite.")
    parser.add_argument("--skip-sidecar", action="store_true", help="Skip anomaly sidecar policy analysis.")
    parser.add_argument("--skip-plots", action="store_true", help="Skip IEEE plot generation.")
    parser.add_argument(
        "--robustness-seeds",
        type=int,
        nargs="+",
        default=[42, 43, 44],
        help="Random seeds for robustness validation.",
    )
    args = parser.parse_args()
    if args.top_v_features == 0:
        args.top_v_features = None
    return args


def main() -> None:
    report = run(parse_args())
    best = report["best_model"]
    metrics = best["test"]["metrics"]
    print("[ieee-opt] Done")
    print(f"[ieee-opt] Report JSON: {REPORT_JSON}")
    print(f"[ieee-opt] Report CSV : {REPORT_CSV}")
    print(
        "[ieee-opt] Best test: "
        f"AUC={metrics['auc']:.6f}, PR-AUC={metrics['pr_auc']:.6f}, "
        f"F1={metrics['f1']:.6f}, Precision={metrics['precision']:.6f}, "
        f"Recall={metrics['recall']:.6f}, Accuracy={metrics['accuracy']:.6f}"
    )


if __name__ == "__main__":
    main()
