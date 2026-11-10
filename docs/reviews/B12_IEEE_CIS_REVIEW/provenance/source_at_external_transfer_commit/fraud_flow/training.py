from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
    roc_curve,
)
import xgboost as xgb
from xgboost import XGBClassifier

from .anomaly import AnomalySidecar
from .calibration import build_routing_calibration
from .config import APP_CONFIG, PAYSIM_FEATURE_COLUMNS
from .deployment import DeploymentManager
from .features import (
    build_feature_frame,
    align_ieee_dataset_to_paysim_features,
    detect_data_source,
    enrich_transactions,
    feature_columns_for_source,
    load_filtered_frame,
    resolve_ieee_identity_path,
    resolve_ieee_transaction_path,
)


@dataclass
class TrainingArtifacts:
    metrics: dict[str, float | dict[str, float]]
    params: dict[str, float | int]
    threshold: float
    sample_size_used: int
    total_rows: int
    train_end: int
    val_end: int


@dataclass
class TransferLearningArtifacts:
    base_model_source: str
    adapt_rows: int
    test_rows: int
    adapt_fraction: float
    num_boost_round: int
    params: dict[str, object]
    adapt_metrics: dict[str, float]
    test_metrics: dict[str, float]
    adapted_model_path: str
    adaptation_report_path: str


@dataclass
class DatasetBundle:
    dataset: pd.DataFrame
    source: str
    feature_columns: list[str]
    data_path: str
    identity_data_path: str | None = None


@dataclass(frozen=True)
class TrainingRunOutputs:
    model_path: Path
    anomaly_model_path: Path
    metadata_path: Path
    training_report_path: Path
    evaluation_report_path: Path
    evaluation_markdown_path: Path
    validation_roc_curve_path: Path
    validation_pr_curve_path: Path
    test_roc_curve_path: Path
    test_pr_curve_path: Path
    threshold_sweep_path: Path
    register_candidate: bool
    artifact_scope: str


def resolve_training_outputs(sample_size: int | None) -> TrainingRunOutputs:
    if sample_size is None:
        outputs = APP_CONFIG.outputs
        return TrainingRunOutputs(
            model_path=outputs.model_path,
            anomaly_model_path=outputs.anomaly_model_path,
            metadata_path=outputs.metadata_path,
            training_report_path=outputs.training_report_path,
            evaluation_report_path=outputs.evaluation_report_path,
            evaluation_markdown_path=outputs.evaluation_markdown_path,
            validation_roc_curve_path=outputs.validation_roc_curve_path,
            validation_pr_curve_path=outputs.validation_pr_curve_path,
            test_roc_curve_path=outputs.test_roc_curve_path,
            test_pr_curve_path=outputs.test_pr_curve_path,
            threshold_sweep_path=outputs.threshold_sweep_path,
            register_candidate=True,
            artifact_scope="production",
        )

    base_dir = APP_CONFIG.outputs.experiments_dir / f"sample_{sample_size}" / "training"
    model_dir = base_dir / "models"
    report_dir = base_dir / "reports"
    return TrainingRunOutputs(
        model_path=model_dir / APP_CONFIG.outputs.model_path.name,
        anomaly_model_path=model_dir / APP_CONFIG.outputs.anomaly_model_path.name,
        metadata_path=model_dir / APP_CONFIG.outputs.metadata_path.name,
        training_report_path=report_dir / APP_CONFIG.outputs.training_report_path.name,
        evaluation_report_path=report_dir / APP_CONFIG.outputs.evaluation_report_path.name,
        evaluation_markdown_path=report_dir / APP_CONFIG.outputs.evaluation_markdown_path.name,
        validation_roc_curve_path=report_dir / APP_CONFIG.outputs.validation_roc_curve_path.name,
        validation_pr_curve_path=report_dir / APP_CONFIG.outputs.validation_pr_curve_path.name,
        test_roc_curve_path=report_dir / APP_CONFIG.outputs.test_roc_curve_path.name,
        test_pr_curve_path=report_dir / APP_CONFIG.outputs.test_pr_curve_path.name,
        threshold_sweep_path=report_dir / APP_CONFIG.outputs.threshold_sweep_path.name,
        register_candidate=False,
        artifact_scope=f"sample_{sample_size}",
    )


def split_strategy_for_source(source: str) -> str:
    if source == "ieee":
        return "chronological_by_TransactionDT_then_TransactionID"
    return "chronological_by_step_after_TRANSFER_CASH_OUT_filter"


def split_indices(total_rows: int) -> tuple[int, int]:
    train_end = int(total_rows * APP_CONFIG.training.train_frac)
    val_end = int(total_rows * (APP_CONFIG.training.train_frac + APP_CONFIG.training.val_frac))
    return train_end, val_end


def classification_metrics(y_true: pd.Series, proba: np.ndarray, threshold: float) -> dict[str, float]:
    pred = (proba >= threshold).astype(int)
    return {
        "auc": float(roc_auc_score(y_true, proba)) if len(set(y_true)) > 1 else 0.0,
        "f1": float(f1_score(y_true, pred, zero_division=0)),
        "precision": float(precision_score(y_true, pred, zero_division=0)),
        "recall": float(recall_score(y_true, pred, zero_division=0)),
    }


def confusion_payload(y_true: pd.Series, proba: np.ndarray, threshold: float) -> dict[str, int]:
    pred = (proba >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, pred, labels=[0, 1]).ravel()
    return {
        "true_negative": int(tn),
        "false_positive": int(fp),
        "false_negative": int(fn),
        "true_positive": int(tp),
    }


def curve_frames(y_true: pd.Series, proba: np.ndarray) -> tuple[pd.DataFrame, pd.DataFrame, float, float]:
    if len(set(y_true)) < 2:
        roc_frame = pd.DataFrame({"fpr": [0.0, 1.0], "tpr": [0.0, 1.0], "threshold": [np.inf, -np.inf]})
        pr_frame = pd.DataFrame({"precision": [0.0], "recall": [0.0], "threshold": [np.nan]})
        return roc_frame, pr_frame, 0.0, 0.0

    roc_fpr, roc_tpr, roc_thresholds = roc_curve(y_true, proba)
    precision, recall, pr_thresholds = precision_recall_curve(y_true, proba)

    roc_auc = float(roc_auc_score(y_true, proba))
    pr_auc = float(average_precision_score(y_true, proba))

    roc_frame = pd.DataFrame(
        {
            "fpr": roc_fpr,
            "tpr": roc_tpr,
            "threshold": roc_thresholds,
        }
    )

    pr_frame = pd.DataFrame(
        {
            "precision": precision,
            "recall": recall,
            "threshold": [np.nan, *pr_thresholds.tolist()],
        }
    )
    return roc_frame, pr_frame, roc_auc, pr_auc


def threshold_sweep_frame(y_true: pd.Series, proba: np.ndarray) -> pd.DataFrame:
    rows: list[dict[str, float | int]] = []
    for threshold in APP_CONFIG.training.threshold_grid:
        metrics = classification_metrics(y_true, proba, threshold=threshold)
        confusion = confusion_payload(y_true, proba, threshold=threshold)
        rows.append(
            {
                "threshold": threshold,
                "auc": metrics["auc"],
                "f1": metrics["f1"],
                "precision": metrics["precision"],
                "recall": metrics["recall"],
                **confusion,
            }
        )
    return pd.DataFrame(rows)


def write_csv_artifact(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)


def build_evaluation_markdown(report: dict[str, object]) -> str:
    split = report["split"]
    validation = report["validation"]
    test = report["test"]
    validation_metrics = validation["metrics"]
    test_metrics = test["metrics"]
    validation_confusion = validation["confusion_matrix"]
    test_confusion = test["confusion_matrix"]
    anomaly = report.get("anomaly_sidecar") or {}
    anomaly_threshold = report.get("anomaly_flag_threshold", anomaly.get("flag_threshold", "N/A"))
    anomaly_lines: list[str] = []
    if anomaly:
        val_eval = anomaly.get("val_eval", {})
        test_eval = anomaly.get("test_eval", {})
        anomaly_lines = [
            "",
            "## Anomaly Sidecar",
            "",
            f"- Model: `{anomaly.get('model', 'N/A')}`",
            f"- Adaptive flag threshold: `{anomaly_threshold}`",
            f"- Threshold method: `{anomaly.get('flag_threshold_method', 'N/A')}`",
            (
                "- Validation flags: "
                f"total={val_eval.get('flagged_total', 'N/A')}, "
                f"fraud={val_eval.get('flagged_fraud', 'N/A')}, "
                f"legit={val_eval.get('flagged_legit', 'N/A')}"
            ),
            (
                "- Test flags: "
                f"total={test_eval.get('flagged_total', 'N/A')}, "
                f"fraud={test_eval.get('flagged_fraud', 'N/A')}, "
                f"legit={test_eval.get('flagged_legit', 'N/A')}"
            ),
        ]

    return "\n".join(
        [
            "# Fraud Model Evaluation Report",
            "",
            f"- Source: `{report['source']}`",
            f"- Data path: `{report['data_path']}`",
            f"- Identity path: `{report['identity_data_path'] or 'N/A'}`",
            f"- Split strategy: `{report['split_strategy']}`",
            f"- Random seed: `{report['random_state']}`",
            f"- Selected threshold: `{report['selected_threshold']}`",
            "",
            "## Split Summary",
            "",
            f"- Total rows: {split['total_rows']}",
            f"- Train rows: {split['train_rows']}",
            f"- Validation rows: {split['validation_rows']}",
            f"- Test rows: {split['test_rows']}",
            "",
            "## Validation Metrics",
            "",
            f"- AUC: {validation_metrics['auc']:.6f}",
            f"- PR AUC: {validation['pr_auc']:.6f}",
            f"- F1: {validation_metrics['f1']:.6f}",
            f"- Precision: {validation_metrics['precision']:.6f}",
            f"- Recall: {validation_metrics['recall']:.6f}",
            (
                "- Confusion matrix: "
                f"TN={validation_confusion['true_negative']}, "
                f"FP={validation_confusion['false_positive']}, "
                f"FN={validation_confusion['false_negative']}, "
                f"TP={validation_confusion['true_positive']}"
            ),
            "",
            "## Test Metrics",
            "",
            f"- AUC: {test_metrics['auc']:.6f}",
            f"- PR AUC: {test['pr_auc']:.6f}",
            f"- F1: {test_metrics['f1']:.6f}",
            f"- Precision: {test_metrics['precision']:.6f}",
            f"- Recall: {test_metrics['recall']:.6f}",
            (
                "- Confusion matrix: "
                f"TN={test_confusion['true_negative']}, "
                f"FP={test_confusion['false_positive']}, "
                f"FN={test_confusion['false_negative']}, "
                f"TP={test_confusion['true_positive']}"
            ),
            "",
            "## Curve Artifacts",
            "",
            f"- Validation ROC: `{report['artifacts']['validation_roc_curve']}`",
            f"- Validation PR: `{report['artifacts']['validation_pr_curve']}`",
            f"- Test ROC: `{report['artifacts']['test_roc_curve']}`",
            f"- Test PR: `{report['artifacts']['test_pr_curve']}`",
            f"- Threshold sweep: `{report['artifacts']['threshold_sweep']}`",
            *anomaly_lines,
        ]
    )


def find_best_threshold(y_true: pd.Series, proba: np.ndarray) -> tuple[float, dict[str, float]]:
    best_threshold = 0.5
    best_metrics = classification_metrics(y_true, proba, threshold=best_threshold)
    best_f1 = best_metrics["f1"]

    for threshold in APP_CONFIG.training.threshold_grid:
        metrics = classification_metrics(y_true, proba, threshold=threshold)
        if metrics["f1"] > best_f1:
            best_threshold = threshold
            best_metrics = metrics
            best_f1 = metrics["f1"]

    return best_threshold, best_metrics


def build_dataset(data_path: str | None = None, sample_size: int | None = None, source: str | None = None) -> DatasetBundle:
    source = detect_data_source(data_path, source=source)
    feature_columns = feature_columns_for_source(source)
    raw = load_filtered_frame(data_path, sample_size=sample_size, source=source)
    enriched = enrich_transactions(raw, source=source).reset_index(drop=True)

    # Split enriched BEFORE building features to prevent label leakage:
    # val/test rows must not see fraud labels from other val/test rows via risk-rate features.
    train_end, val_end = split_indices(len(enriched))
    enriched_train = enriched.iloc[:train_end]
    enriched_eval = enriched.iloc[train_end:]

    # Build train features with full label observation (updates fraud rates)
    train_feature_frame, _, trained_store = build_feature_frame(enriched_train, source=source)

    # Build val/test features using the store frozen at end of train (no fraud-rate updates)
    eval_feature_frame, _, _ = build_feature_frame(
        enriched_eval, source=source, freeze_risk_labels=True, store=trained_store
    )

    feature_frame = pd.concat([train_feature_frame, eval_feature_frame], ignore_index=True)
    dataset = pd.concat([enriched, feature_frame], axis=1)
    dataset = dataset.loc[:, ~dataset.columns.duplicated()].copy()

    if source == "ieee":
        transaction_path = resolve_ieee_transaction_path(data_path)
        resolved_data_path = str(transaction_path)
        identity_data_path = str(resolve_ieee_identity_path(transaction_path))
    else:
        resolved_data_path = str(Path(data_path) if data_path else APP_CONFIG.data_path)
        identity_data_path = None
    return DatasetBundle(
        dataset=dataset,
        source=source,
        feature_columns=feature_columns,
        data_path=resolved_data_path,
        identity_data_path=identity_data_path,
    )


def build_train_profile(train_df: pd.DataFrame, source: str) -> dict[str, float]:
    amount_feature = "transaction_amt_log1p" if source == "ieee" else "amount_log1p"
    return {
        "amount_log1p_mean": float(train_df[amount_feature].mean()),
        "tx_count_24h_mean": float(train_df["tx_count_24h"].mean()),
        "device_tx_count_24h_mean": float(train_df["device_tx_count_24h"].mean()),
        "merchant_fraud_rate_mean": float(train_df["merchant_fraud_rate"].mean()),
        "fraud_rate": float(train_df["isFraud"].mean()),
    }


def build_class_balance(y_train: pd.Series) -> dict[str, float | int]:
    positive_count = int((y_train == 1).sum())
    negative_count = int((y_train == 0).sum())
    scale_pos_weight = max(1.0, float(negative_count / max(positive_count, 1)))
    return {
        "positive_count": positive_count,
        "negative_count": negative_count,
        "scale_pos_weight": scale_pos_weight,
    }


def train_model(data_path: str | None = None, sample_size: int | None = None, source: str | None = None) -> TrainingArtifacts:
    dataset_bundle = build_dataset(data_path=data_path, sample_size=sample_size, source=source)
    run_outputs = resolve_training_outputs(sample_size)
    dataset = dataset_bundle.dataset
    feature_columns = dataset_bundle.feature_columns
    train_end, val_end = split_indices(len(dataset))

    train_df = dataset.iloc[:train_end].copy()
    val_df = dataset.iloc[train_end:val_end].copy()
    test_df = dataset.iloc[val_end:].copy()

    X_train = train_df[feature_columns]
    y_train = train_df["isFraud"]
    X_val = val_df[feature_columns]
    y_val = val_df["isFraud"]
    X_test = test_df[feature_columns]
    y_test = test_df["isFraud"]

    class_balance = build_class_balance(y_train)
    scale_pos_weight = float(class_balance["scale_pos_weight"])
    best_score = -1.0
    best_model: XGBClassifier | None = None
    best_params: dict[str, float | int] | None = None
    best_threshold = 0.5
    best_val_metrics: dict[str, float] = {}

    for params in APP_CONFIG.training.candidate_params:
        model = XGBClassifier(
            objective="binary:logistic",
            eval_metric="logloss",
            random_state=APP_CONFIG.training.random_state,
            n_jobs=APP_CONFIG.training.n_jobs,
            scale_pos_weight=scale_pos_weight,
            max_delta_step=APP_CONFIG.training.max_delta_step,
            tree_method="hist",
            **params,
        )
        model.fit(X_train, y_train)
        val_proba = model.predict_proba(X_val)[:, 1]
        threshold, val_metrics = find_best_threshold(y_val, val_proba)

        ranking_score = val_metrics["auc"] + val_metrics["f1"]
        if ranking_score > best_score:
            best_score = ranking_score
            best_model = model
            best_params = params
            best_threshold = threshold
            best_val_metrics = val_metrics

    if best_model is None or best_params is None:
        raise RuntimeError("Training failed: no model candidate completed.")

    val_proba = best_model.predict_proba(X_val)[:, 1]
    test_proba = best_model.predict_proba(X_test)[:, 1]
    test_metrics = classification_metrics(y_test, test_proba, threshold=best_threshold)
    validation_confusion = confusion_payload(y_val, val_proba, threshold=best_threshold)
    test_confusion = confusion_payload(y_test, test_proba, threshold=best_threshold)
    validation_roc_frame, validation_pr_frame, validation_roc_auc, validation_pr_auc = curve_frames(y_val, val_proba)
    test_roc_frame, test_pr_frame, test_roc_auc, test_pr_auc = curve_frames(y_test, test_proba)
    threshold_sweep = threshold_sweep_frame(y_val, val_proba)
    routing_calibration = build_routing_calibration(
        val_proba,
        low_quantile=APP_CONFIG.training.calibration_low_quantile,
        high_quantile=APP_CONFIG.training.calibration_high_quantile,
        low_threshold=APP_CONFIG.routing.low,
        high_threshold=APP_CONFIG.routing.high,
    )

    train_profile = build_train_profile(train_df, dataset_bundle.source)

    run_outputs.model_path.parent.mkdir(parents=True, exist_ok=True)
    run_outputs.anomaly_model_path.parent.mkdir(parents=True, exist_ok=True)
    run_outputs.training_report_path.parent.mkdir(parents=True, exist_ok=True)

    best_model.save_model(run_outputs.model_path)
    write_csv_artifact(validation_roc_frame, run_outputs.validation_roc_curve_path)
    write_csv_artifact(validation_pr_frame, run_outputs.validation_pr_curve_path)
    write_csv_artifact(test_roc_frame, run_outputs.test_roc_curve_path)
    write_csv_artifact(test_pr_frame, run_outputs.test_pr_curve_path)
    write_csv_artifact(threshold_sweep, run_outputs.threshold_sweep_path)

    metadata = {
        "source": dataset_bundle.source,
        "data_path": dataset_bundle.data_path,
        "identity_data_path": dataset_bundle.identity_data_path,
        "artifact_scope": run_outputs.artifact_scope,
        "anomaly_model_path": str(run_outputs.anomaly_model_path),
        "sample_size_used": len(dataset),
        "feature_columns": feature_columns,
        "routing_thresholds": {
            "low": APP_CONFIG.routing.low,
            "high": APP_CONFIG.routing.high,
        },
        "train_end": train_end,
        "val_end": val_end,
        "selected_threshold": best_threshold,
        "selected_params": best_params,
        "training_controls": {
            "max_delta_step": APP_CONFIG.training.max_delta_step,
        },
        "class_balance": class_balance,
        "routing_calibration": routing_calibration,
        "validation_metrics": best_val_metrics,
        "test_metrics": test_metrics,
        "train_profile": train_profile,
        "split": {
            "total_rows": len(dataset),
            "train_rows": len(train_df),
            "validation_rows": len(val_df),
            "test_rows": len(test_df),
        },
    }

    evaluation_report = {
        **metadata,
        "random_state": APP_CONFIG.training.random_state,
        "split_strategy": split_strategy_for_source(dataset_bundle.source),
        "split": {
            "total_rows": len(dataset),
            "train_rows": len(train_df),
            "validation_rows": len(val_df),
            "test_rows": len(test_df),
            "train_end": train_end,
            "val_end": val_end,
        },
        "validation": {
            "metrics": best_val_metrics,
            "confusion_matrix": validation_confusion,
            "roc_auc": validation_roc_auc,
            "pr_auc": validation_pr_auc,
        },
        "test": {
            "metrics": test_metrics,
            "confusion_matrix": test_confusion,
            "roc_auc": test_roc_auc,
            "pr_auc": test_pr_auc,
        },
        "artifacts": {
            "validation_roc_curve": str(run_outputs.validation_roc_curve_path),
            "validation_pr_curve": str(run_outputs.validation_pr_curve_path),
            "test_roc_curve": str(run_outputs.test_roc_curve_path),
            "test_pr_curve": str(run_outputs.test_pr_curve_path),
            "threshold_sweep": str(run_outputs.threshold_sweep_path),
            "anomaly_sidecar_model": str(run_outputs.anomaly_model_path),
        },
    }

    with run_outputs.metadata_path.open("w", encoding="utf-8") as fh:
        json.dump(metadata, fh, indent=2)

    with run_outputs.training_report_path.open("w", encoding="utf-8") as fh:
        json.dump(evaluation_report, fh, indent=2)

    with run_outputs.evaluation_report_path.open("w", encoding="utf-8") as fh:
        json.dump(evaluation_report, fh, indent=2)

    run_outputs.evaluation_markdown_path.write_text(
        build_evaluation_markdown(evaluation_report),
        encoding="utf-8",
    )

    # --- Anomaly Sidecar ---
    anomaly_sidecar = AnomalySidecar(
        contamination=APP_CONFIG.anomaly.contamination,
        n_estimators=APP_CONFIG.anomaly.n_estimators,
        random_state=APP_CONFIG.training.random_state,
    )
    anomaly_train_stats = anomaly_sidecar.train(train_df)

    # Auto-calibrate: dùng P95 của val scores thay vì hardcode 0.70
    adaptive_threshold = anomaly_sidecar.compute_adaptive_threshold(val_df, percentile=95.0)

    anomaly_val_eval = anomaly_sidecar.evaluate(val_df, threshold=adaptive_threshold)
    anomaly_test_eval = anomaly_sidecar.evaluate(test_df, threshold=adaptive_threshold)
    anomaly_model_path = run_outputs.anomaly_model_path
    anomaly_sidecar.save(anomaly_model_path)

    evaluation_report["anomaly_sidecar"] = {
        "model": "IsolationForest",
        "feature_count": len(__import__("fraud_flow.anomaly", fromlist=["ANOMALY_FEATURE_COLUMNS"]).ANOMALY_FEATURE_COLUMNS),
        "flag_threshold": adaptive_threshold,
        "flag_threshold_method": "percentile_95_val",
        "flag_threshold_hardcoded_fallback": APP_CONFIG.anomaly.flag_threshold,
        "train_stats": anomaly_train_stats,
        "val_eval": anomaly_val_eval,
        "test_eval": anomaly_test_eval,
        "model_path": str(anomaly_model_path),
    }

    # Lưu adaptive_threshold vào model_metadata.json
    metadata["anomaly_flag_threshold"] = adaptive_threshold
    evaluation_report["anomaly_flag_threshold"] = adaptive_threshold
    with run_outputs.metadata_path.open("w", encoding="utf-8") as fh:
        json.dump(metadata, fh, indent=2)

    with run_outputs.evaluation_report_path.open("w", encoding="utf-8") as fh:
        json.dump(evaluation_report, fh, indent=2)
    with run_outputs.training_report_path.open("w", encoding="utf-8") as fh:
        json.dump(evaluation_report, fh, indent=2)
    run_outputs.evaluation_markdown_path.write_text(
        build_evaluation_markdown(evaluation_report),
        encoding="utf-8",
    )
    # --- End Anomaly Sidecar ---

    if run_outputs.register_candidate:
        DeploymentManager().register_candidate()

    return TrainingArtifacts(
        metrics={"validation": best_val_metrics, "test": test_metrics},
        params=best_params,
        threshold=best_threshold,
        sample_size_used=len(dataset),
        total_rows=len(dataset),
        train_end=train_end,
        val_end=val_end,
    )


def adapt_model_to_ieee(
    ieee_data_path: str | None = None,
    adapt_fraction: float = 0.10,
    num_boost_round_candidates: tuple[int, ...] = (25, 50, 75, 100),
) -> TransferLearningArtifacts:
    """
    Transfer Learning: cập nhật PaySim model trên `adapt_fraction` đầu của dữ liệu IEEE-CIS.
    Dùng xgb.train(xgb_model=paysim_booster) để thêm cây mới trên nền cây cũ.
    Đánh giá kết quả trên (1 - adapt_fraction) còn lại của IEEE-CIS.
    """
    # 1. Load toàn bộ IEEE dataset rồi align sang đúng 25 PaySim features.
    # PaySim booster không thể train tiếp trực tiếp trên 42 IEEE-native features.
    dataset_bundle = build_dataset(data_path=ieee_data_path, source="ieee")
    paysim_bundle = build_dataset(source="paysim")
    paysim_train_end, _ = split_indices(len(paysim_bundle.dataset))
    paysim_train_df = paysim_bundle.dataset.iloc[:paysim_train_end].copy()
    aligned_features = align_ieee_dataset_to_paysim_features(dataset_bundle.dataset, paysim_train_df)
    dataset = dataset_bundle.dataset.copy()
    for column in PAYSIM_FEATURE_COLUMNS:
        dataset[column] = aligned_features[column].to_numpy()
    feature_columns = list(PAYSIM_FEATURE_COLUMNS)

    # 2. Tách 10% đầu để adapt, 90% còn lại để test
    adapt_end = max(2, int(len(dataset) * adapt_fraction))
    adapt_df = dataset.iloc[:adapt_end].copy()
    test_df = dataset.iloc[adapt_end:].copy()

    # Trong adapt_df: 80% train, 20% val để chọn num_boost_round
    inner_split = max(1, int(len(adapt_df) * 0.80))
    adapt_train_df = adapt_df.iloc[:inner_split]
    adapt_val_df = adapt_df.iloc[inner_split:]

    X_adapt_train = adapt_train_df[feature_columns].values
    y_adapt_train = adapt_train_df["isFraud"].values
    X_adapt_val = adapt_val_df[feature_columns].values
    y_adapt_val = adapt_val_df["isFraud"].values
    X_test = test_df[feature_columns].values
    y_test = test_df["isFraud"]

    # 3. Load PaySim base model
    base_model_path = APP_CONFIG.outputs.model_path
    if not base_model_path.exists():
        raise FileNotFoundError(
            f"Base model không tìm thấy tại {base_model_path}. "
            "Hãy chạy 'train' trên PaySim trước."
        )
    paysim_booster = xgb.Booster()
    paysim_booster.load_model(str(base_model_path))

    # 4. Lấy params tham khảo từ metadata PaySim
    base_params: dict[str, object] = {}
    if APP_CONFIG.outputs.metadata_path.exists():
        with APP_CONFIG.outputs.metadata_path.open(encoding="utf-8") as fh:
            base_meta = json.load(fh)
        base_params = base_meta.get("selected_params", {})

    class_balance = build_class_balance(adapt_train_df["isFraud"])
    adapt_params: dict[str, object] = {
        "objective": "binary:logistic",
        "eval_metric": "logloss",
        "seed": APP_CONFIG.training.random_state,
        "tree_method": "hist",
        "scale_pos_weight": float(class_balance["scale_pos_weight"]),
        "max_delta_step": APP_CONFIG.training.max_delta_step,
        "max_depth": base_params.get("max_depth", 6),
        "learning_rate": base_params.get("learning_rate", 0.05),
        "subsample": base_params.get("subsample", 0.90),
        "colsample_bytree": base_params.get("colsample_bytree", 0.85),
    }

    dtrain = xgb.DMatrix(X_adapt_train, label=y_adapt_train, feature_names=feature_columns)
    dval = xgb.DMatrix(X_adapt_val, label=y_adapt_val, feature_names=feature_columns)
    dtest = xgb.DMatrix(X_test, feature_names=feature_columns)

    # 5. Thử từng num_boost_round, chọn tốt nhất theo val AUC
    best_round = num_boost_round_candidates[0]
    best_val_auc = -1.0
    best_booster: xgb.Booster | None = None

    for n_rounds in num_boost_round_candidates:
        candidate = xgb.train(
            adapt_params,
            dtrain,
            num_boost_round=n_rounds,
            xgb_model=paysim_booster,
            verbose_eval=False,
        )
        val_proba = candidate.predict(dval)
        val_auc = float(roc_auc_score(y_adapt_val, val_proba)) if len(set(y_adapt_val)) > 1 else 0.0
        if val_auc > best_val_auc:
            best_val_auc = val_auc
            best_round = n_rounds
            best_booster = candidate

    if best_booster is None:
        raise RuntimeError("Adaptation thất bại: không có candidate nào hoàn thành.")

    # 6. Chọn threshold tốt nhất trên adapt val, đánh giá trên 90% test
    val_proba_final = best_booster.predict(dval)
    best_threshold = 0.5
    if len(set(y_adapt_val)) > 1:
        best_threshold, _ = find_best_threshold(pd.Series(y_adapt_val), val_proba_final)

    adapt_val_metrics = classification_metrics(pd.Series(y_adapt_val), val_proba_final, threshold=best_threshold)
    adapt_val_pr_auc = float(average_precision_score(y_adapt_val, val_proba_final)) if len(set(y_adapt_val)) > 1 else 0.0
    adapt_val_confusion = confusion_payload(pd.Series(y_adapt_val), val_proba_final, threshold=best_threshold)

    test_proba = best_booster.predict(dtest)
    test_metrics = classification_metrics(y_test, test_proba, threshold=best_threshold)
    test_pr_auc = float(average_precision_score(y_test, test_proba)) if len(set(y_test)) > 1 else 0.0
    test_confusion = confusion_payload(y_test, test_proba, threshold=best_threshold)

    # 7. Lưu adapted model
    adapted_model_path = APP_CONFIG.outputs.adapted_model_path
    adapted_model_path.parent.mkdir(parents=True, exist_ok=True)
    best_booster.save_model(str(adapted_model_path))

    # 8. Lưu báo cáo transfer learning
    report_path = APP_CONFIG.outputs.transfer_learning_report_path
    report_path.parent.mkdir(parents=True, exist_ok=True)
    tl_report = {
        "base_model": str(base_model_path),
        "base_model_source": "paysim",
        "ieee_data_path": dataset_bundle.data_path,
        "adapt_fraction": adapt_fraction,
        "adapt_rows": len(adapt_df),
        "test_rows": len(test_df),
        "feature_alignment": {
            "method": "semantic_proxy_with_mfield_balance_diff",
            "target_feature_count": len(PAYSIM_FEATURE_COLUMNS),
            "target_features": list(PAYSIM_FEATURE_COLUMNS),
            "source_feature_count": len(dataset_bundle.feature_columns),
        },
        "feature_columns": feature_columns,
        "feature_count": len(feature_columns),
        "best_num_boost_round": best_round,
        "adapt_params": {k: v for k, v in adapt_params.items()},
        "adapt_val": {
            "metrics": adapt_val_metrics,
            "pr_auc": adapt_val_pr_auc,
            "confusion_matrix": adapt_val_confusion,
        },
        "test": {
            "metrics": test_metrics,
            "pr_auc": test_pr_auc,
            "confusion_matrix": test_confusion,
        },
        "adapt_val_metrics": adapt_val_metrics,
        "test_metrics": test_metrics,
        "selected_threshold": best_threshold,
        "adapted_model_path": str(adapted_model_path),
        "class_balance": class_balance,
    }
    with report_path.open("w", encoding="utf-8") as fh:
        json.dump(tl_report, fh, indent=2)

    return TransferLearningArtifacts(
        base_model_source="paysim",
        adapt_rows=len(adapt_df),
        test_rows=len(test_df),
        adapt_fraction=adapt_fraction,
        num_boost_round=best_round,
        params=adapt_params,
        adapt_metrics=adapt_val_metrics,
        test_metrics=test_metrics,
        adapted_model_path=str(adapted_model_path),
        adaptation_report_path=str(report_path),
    )
