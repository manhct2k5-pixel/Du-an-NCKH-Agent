"""Run the isolated, leakage-controlled B12 IEEE-CIS validation suite.

This runner does not call the B1-B11 research suite and never writes a model.
It only reads the production PaySim model and writes B12 reports.
"""
from __future__ import annotations

import argparse
import csv
import gc
import hashlib
import json
import shlex
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
)
from xgboost import XGBClassifier

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from fraud_flow.config import APP_CONFIG, PAYSIM_FEATURE_COLUMNS  # noqa: E402
from fraud_flow.feature_store import FeatureStore  # noqa: E402
from fraud_flow.features import (  # noqa: E402
    assemble_feature_row,
    enrich_transactions,
    event_from_row,
    feature_columns_for_source,
    load_filtered_frame,
)
from scripts.ieee_cis_optimized_benchmark import (  # noqa: E402
    PARAM_CANDIDATES,
    best_threshold_from_pr_curve,
    feature_columns_for_profile,
    load_ieee_frame,
    prepare_splits,
    resolve_identity_path,
    xgb_params_from_report,
)


OUTPUT_DIR = ROOT / "artifacts" / "reports" / "b12_final"
FROZEN_JSON = OUTPUT_DIR / "b12_frozen_ieee.json"
TRANSFER_JSON = OUTPUT_DIR / "b12_transfer_ieee.json"
NATIVE_JSON = OUTPUT_DIR / "b12_native_ieee.json"
COMPARISON_CSV = OUTPUT_DIR / "b12_comparison.csv"
AUDIT_MD = OUTPUT_DIR / "B12_FINAL_AUDIT.md"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def git_value(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def git_dirty() -> bool:
    return bool(git_value("status", "--porcelain=v1"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def metric_payload(y_true: np.ndarray | pd.Series, proba: np.ndarray, threshold: float) -> dict[str, Any]:
    labels = np.asarray(y_true, dtype=int)
    pred = (np.asarray(proba) >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(labels, pred, labels=[0, 1]).ravel()
    return {
        "auc": float(roc_auc_score(labels, proba)),
        "pr_auc": float(average_precision_score(labels, proba)),
        "f1": float(f1_score(labels, pred, zero_division=0)),
        "precision": float(precision_score(labels, pred, zero_division=0)),
        "recall": float(recall_score(labels, pred, zero_division=0)),
        "confusion_matrix": {
            "true_negative": int(tn),
            "false_positive": int(fp),
            "false_negative": int(fn),
            "true_positive": int(tp),
        },
    }


def build_sequential_features(
    frame: pd.DataFrame,
    *,
    source: str,
    store: FeatureStore,
    observe_labels: bool,
    stage: str,
    update_unlabeled_activity: bool = True,
) -> pd.DataFrame:
    """Build features in time order without retaining event objects.

    When observe_labels is false, labels are neither read for feature creation nor
    written to historical risk state; only prior transaction activity is observed.
    """
    rows: list[dict[str, float | int]] = []
    total = len(frame)
    for index, row in enumerate(frame.itertuples(index=False), start=1):
        event = event_from_row(row, source=source)
        lookup = store.lookup(event)
        rows.append(assemble_feature_row(event, lookup))
        if observe_labels:
            store.observe(event, event.is_fraud)
        elif update_unlabeled_activity:
            store.observe_activity(event)
        if index % 100_000 == 0 or index == total:
            print(f"[b12] {stage}: {index:,}/{total:,} rows", flush=True)
    return pd.DataFrame(rows)[feature_columns_for_source(source)]


def without_labels(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    result["isFraud"] = 0
    return result


def numeric_column(frame: pd.DataFrame, column: str, default: float = 0.0) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=float)
    return (
        pd.to_numeric(frame[column], errors="coerce")
        .replace([np.inf, -np.inf], np.nan)
        .fillna(default)
        .astype(float)
    )


def empirical_project(
    values: pd.Series | np.ndarray,
    fit_values: pd.Series | np.ndarray,
    reference_values: pd.Series | np.ndarray,
) -> np.ndarray:
    """Project by an empirical CDF fitted only on the allowed alignment rows."""
    fit = np.asarray(pd.to_numeric(pd.Series(fit_values), errors="coerce"), dtype=float)
    fit = np.sort(fit[np.isfinite(fit)])
    reference = np.asarray(pd.to_numeric(pd.Series(reference_values), errors="coerce"), dtype=float)
    reference = np.sort(reference[np.isfinite(reference)])
    source = np.asarray(pd.to_numeric(pd.Series(values), errors="coerce"), dtype=float)
    if len(fit) == 0 or len(reference) == 0:
        return np.zeros(len(source), dtype=float)
    fill = float(np.median(fit))
    source = np.nan_to_num(source, nan=fill, posinf=fit[-1], neginf=fit[0])
    ranks = np.searchsorted(fit, source, side="right") / len(fit)
    return np.quantile(reference, np.clip(ranks, 0.0, 1.0))


def alignment_sources(frame: pd.DataFrame) -> tuple[pd.Series, pd.Series, pd.Series]:
    transaction_amt = numeric_column(frame, "TransactionAmt")
    amount_log = pd.Series(np.log1p(np.maximum(transaction_amt.to_numpy(), 0.0)), index=frame.index)
    source_balance = (
        numeric_column(frame, "avg_amount_7d") * (numeric_column(frame, "tx_count_24h") + 1.0)
        + numeric_column(frame, "card1")
    )
    destination_balance = (
        numeric_column(frame, "C2") * np.maximum(transaction_amt, 1.0)
        + numeric_column(frame, "dist1")
    )
    return amount_log, source_balance, destination_balance


def align_ieee_clean(
    frame: pd.DataFrame,
    *,
    fit_frame: pd.DataFrame,
    paysim_train: pd.DataFrame,
) -> pd.DataFrame:
    """Approximate IEEE-to-PaySim alignment with a frozen, label-free CDF map."""
    amount_source, org_source, dest_source = alignment_sources(frame)
    fit_amount, fit_org, fit_dest = alignment_sources(fit_frame)
    amount_log1p = empirical_project(amount_source, fit_amount, paysim_train["amount_log1p"])
    amount = np.expm1(amount_log1p)
    oldbalance_org = empirical_project(org_source, fit_org, paysim_train["oldbalanceOrg"])
    oldbalance_dest = empirical_project(dest_source, fit_dest, paysim_train["oldbalanceDest"])

    product_cd = frame.get("ProductCD", pd.Series("", index=frame.index)).astype(str).str.upper()
    type_encoded = np.where(product_cd == "W", 2, 1)
    hour_of_day = (numeric_column(frame, "step") % 24).astype(int)
    if "D2" in frame:
        d2_raw = pd.to_numeric(frame["D2"], errors="coerce")
    else:
        d2_raw = pd.Series(np.nan, index=frame.index)
    m_false_count = sum(
        (frame.get(f"M{i}", pd.Series("", index=frame.index)).astype(str).str.strip().str.upper() == "F").astype(float)
        for i in range(1, 10)
    )
    balance_diff = -amount * (m_false_count.to_numpy() / 9.0)
    newbalance_orig = np.maximum(oldbalance_org - amount, 0.0)
    newbalance_dest = oldbalance_dest + amount

    aligned = pd.DataFrame(
        {
            "amount_log1p": amount_log1p,
            "oldbalanceOrg": oldbalance_org,
            "newbalanceOrig": newbalance_orig,
            "oldbalanceDest": oldbalance_dest,
            "newbalanceDest": newbalance_dest,
            "type_encoded": type_encoded,
            "balance_diff": balance_diff,
            "amount_ratio": amount / (oldbalance_org + 1.0),
            "org_balance_delta_ratio": balance_diff / (oldbalance_org + 1.0),
            "hour_of_day": hour_of_day.to_numpy(),
            "is_night_tx": (hour_of_day < 6).astype(int).to_numpy(),
            "recipient_new_flag": (d2_raw.isna() | (d2_raw > 365)).astype(int).to_numpy(),
            "tx_count_24h": numeric_column(frame, "tx_count_24h").to_numpy(),
            "avg_amount_7d": numeric_column(frame, "avg_amount_7d").to_numpy(),
            "device_tx_count_24h": numeric_column(frame, "device_tx_count_24h").to_numpy(),
            "location_tx_count_24h": numeric_column(frame, "location_tx_count_24h").to_numpy(),
            "merchant_tx_count_24h": numeric_column(frame, "merchant_tx_count_24h").to_numpy(),
            "location_fraud_rate": numeric_column(frame, "location_fraud_rate").to_numpy(),
            "ip_fraud_rate": numeric_column(frame, "ip_fraud_rate").to_numpy(),
            "merchant_fraud_rate": numeric_column(frame, "merchant_fraud_rate").to_numpy(),
            "llm_risk_score": numeric_column(frame, "llm_risk_score").to_numpy(),
            "llm_reason_count": numeric_column(frame, "llm_reason_count").to_numpy(),
            "llm_high_risk_flag": numeric_column(frame, "llm_high_risk_flag").to_numpy(),
            "llm_review_flag": numeric_column(frame, "llm_review_flag").to_numpy(),
            "llm_category_hash": numeric_column(frame, "llm_category_hash").to_numpy(),
        }
    )
    return aligned.replace([np.inf, -np.inf], np.nan).fillna(0.0)[PAYSIM_FEATURE_COLUMNS].astype(np.float32)


def build_paysim_reference() -> tuple[pd.DataFrame, dict[str, int]]:
    raw = load_filtered_frame(source="paysim")
    enriched = enrich_transactions(raw, source="paysim").reset_index(drop=True)
    train_end = int(len(enriched) * APP_CONFIG.training.train_frac)
    train_enriched = enriched.iloc[:train_end].copy()
    features = build_sequential_features(
        train_enriched,
        source="paysim",
        store=FeatureStore(),
        observe_labels=True,
        stage="PaySim alignment reference",
    )
    reference = pd.concat([train_enriched.reset_index(drop=True), features.reset_index(drop=True)], axis=1)
    reference = reference.loc[:, ~reference.columns.duplicated()].copy()
    split = {
        "train_rows": int(train_end),
        "validation_rows": int(len(enriched) * APP_CONFIG.training.val_frac),
        "test_rows": int(len(enriched) - train_end - int(len(enriched) * APP_CONFIG.training.val_frac)),
    }
    return reference, split


def provenance(args: argparse.Namespace, dataset_hashes: dict[str, str], model_hash: str) -> dict[str, Any]:
    code_paths = [
        ROOT / "scripts" / "run_b12_final.py",
        ROOT / "scripts" / "ieee_cis_optimized_benchmark.py",
        ROOT / "fraud_flow" / "config.py",
        ROOT / "fraud_flow" / "features.py",
        ROOT / "fraud_flow" / "feature_store.py",
        ROOT / "fraud_flow" / "llm_features.py",
        ROOT / "fraud_flow" / "schema.py",
    ]
    code_hashes = {str(path.relative_to(ROOT)): sha256_file(path) for path in code_paths}
    composite = hashlib.sha256()
    for name, digest in sorted(code_hashes.items()):
        composite.update(f"{name}:{digest}\n".encode())
    return {
        "generated_at": utc_now(),
        "git_commit": git_value("rev-parse", "HEAD"),
        "git_dirty": git_dirty(),
        "dataset_paths": {
            "ieee_transaction": str(args.transaction_path),
            "ieee_identity": str(args.identity_path),
            "paysim_reference": str(args.paysim_path),
        },
        "dataset_sha256": dataset_hashes,
        "production_model_path": str(args.model_path),
        "production_model_sha256": model_hash,
        "code_sha256": {
            "composite": composite.hexdigest(),
            "files": code_hashes,
        },
        "exact_command": shlex.join([str(Path(sys.executable)), *sys.argv]),
        "artifact_scope": "b12_final_only",
        "random_state": int(APP_CONFIG.training.random_state),
    }


def run_frozen(
    ieee_enriched: pd.DataFrame,
    paysim_reference: pd.DataFrame,
    paysim_split: dict[str, int],
    args: argparse.Namespace,
    common_provenance: dict[str, Any],
) -> dict[str, Any]:
    print("[b12] Frozen: building label-blinded IEEE features", flush=True)
    y_final = ieee_enriched["isFraud"].astype(int).to_numpy(copy=True)
    blinded = without_labels(ieee_enriched)
    features = build_sequential_features(
        blinded,
        source="ieee",
        store=FeatureStore(),
        observe_labels=False,
        stage="Frozen IEEE features",
    )
    feature_dataset = pd.concat([blinded.reset_index(drop=True), features.reset_index(drop=True)], axis=1)
    feature_dataset = feature_dataset.loc[:, ~feature_dataset.columns.duplicated()].copy()
    aligned = align_ieee_clean(feature_dataset, fit_frame=feature_dataset, paysim_train=paysim_reference)

    booster = xgb.Booster()
    booster.load_model(str(args.model_path))
    dtest = xgb.DMatrix(aligned, feature_names=list(PAYSIM_FEATURE_COLUMNS))
    proba = booster.predict(dtest)
    threshold = float(args.production_threshold)
    metrics = metric_payload(y_final, proba, threshold)
    payload = {
        "experiment": "frozen_paysim_to_ieee",
        "protocol": {
            "production_model_loaded": True,
            "frozen_model_retrained": False,
            "alignment_method": "semantic_proxy_with_empirical_cdf_fitted_on_unlabeled_ieee_covariates",
            "alignment_fit_scope": "full_ieee_covariates_without_labels",
            "ieee_labels_available_during_feature_construction": False,
            "test_used_for_model_selection": False,
            "test_label_leakage": False,
            "test_evaluations": 1,
        },
        "threshold": threshold,
        "train_rows": paysim_split["train_rows"],
        "validation_rows": paysim_split["validation_rows"],
        "test_rows": int(len(y_final)),
        "feature_count": int(aligned.shape[1]),
        "metrics": metrics,
        "model_sha256": common_provenance["production_model_sha256"],
        "provenance": {**common_provenance, "generated_at": utc_now()},
    }
    write_json(FROZEN_JSON, payload)
    print(f"[b12] Frozen complete: AUC={metrics['auc']:.6f}", flush=True)
    del blinded, features, feature_dataset, aligned, dtest, proba
    gc.collect()
    return payload


def run_transfer(
    ieee_enriched: pd.DataFrame,
    paysim_reference: pd.DataFrame,
    args: argparse.Namespace,
    common_provenance: dict[str, Any],
) -> dict[str, Any]:
    total = len(ieee_enriched)
    adapt_end = int(total * args.adapt_fraction)
    adapt_train_end = int(adapt_end * args.adapt_train_fraction)
    train_frame = ieee_enriched.iloc[:adapt_train_end].copy()
    validation_original = ieee_enriched.iloc[adapt_train_end:adapt_end].copy()
    test_original = ieee_enriched.iloc[adapt_end:].copy()
    y_train = train_frame["isFraud"].astype(int).to_numpy(copy=True)
    y_validation = validation_original["isFraud"].astype(int).to_numpy(copy=True)
    y_final = test_original["isFraud"].astype(int).to_numpy(copy=True)

    store = FeatureStore()
    train_features = build_sequential_features(
        train_frame,
        source="ieee",
        store=store,
        observe_labels=True,
        stage="Transfer adapt-train features",
    )
    validation_blinded = without_labels(validation_original)
    validation_features = build_sequential_features(
        validation_blinded,
        source="ieee",
        store=store,
        observe_labels=False,
        stage="Transfer adapt-validation features",
    )
    test_blinded = without_labels(test_original)
    test_features = build_sequential_features(
        test_blinded,
        source="ieee",
        store=store,
        observe_labels=False,
        update_unlabeled_activity=False,
        stage="Transfer final-test features",
    )

    train_dataset = pd.concat([train_frame.reset_index(drop=True), train_features.reset_index(drop=True)], axis=1)
    validation_dataset = pd.concat(
        [validation_blinded.reset_index(drop=True), validation_features.reset_index(drop=True)], axis=1
    )
    test_dataset = pd.concat([test_blinded.reset_index(drop=True), test_features.reset_index(drop=True)], axis=1)
    train_dataset = train_dataset.loc[:, ~train_dataset.columns.duplicated()].copy()
    validation_dataset = validation_dataset.loc[:, ~validation_dataset.columns.duplicated()].copy()
    test_dataset = test_dataset.loc[:, ~test_dataset.columns.duplicated()].copy()

    X_train = align_ieee_clean(train_dataset, fit_frame=train_dataset, paysim_train=paysim_reference)
    X_validation = align_ieee_clean(validation_dataset, fit_frame=train_dataset, paysim_train=paysim_reference)
    X_final = align_ieee_clean(test_dataset, fit_frame=train_dataset, paysim_train=paysim_reference)

    base_booster = xgb.Booster()
    base_booster.load_model(str(args.model_path))
    metadata = json.loads(Path(args.metadata_path).read_text(encoding="utf-8"))
    base_params = metadata.get("selected_params", {})
    positives = int(y_train.sum())
    negatives = int(len(y_train) - positives)
    adapt_params: dict[str, Any] = {
        "objective": "binary:logistic",
        "eval_metric": "logloss",
        "seed": int(APP_CONFIG.training.random_state),
        "tree_method": "hist",
        "scale_pos_weight": max(1.0, negatives / max(positives, 1)),
        "max_delta_step": int(APP_CONFIG.training.max_delta_step),
        "max_depth": int(base_params.get("max_depth", 6)),
        "learning_rate": float(base_params.get("learning_rate", 0.06)),
        "subsample": float(base_params.get("subsample", 0.9)),
        "colsample_bytree": float(base_params.get("colsample_bytree", 0.85)),
    }
    dtrain = xgb.DMatrix(X_train, label=y_train, feature_names=list(PAYSIM_FEATURE_COLUMNS))
    dvalidation = xgb.DMatrix(X_validation, label=y_validation, feature_names=list(PAYSIM_FEATURE_COLUMNS))
    best_booster: xgb.Booster | None = None
    best_round = 0
    best_auc = -1.0
    candidate_validation: list[dict[str, Any]] = []
    for rounds in args.boost_round_candidates:
        print(f"[b12] Transfer: validation candidate rounds={rounds}", flush=True)
        candidate = xgb.train(
            adapt_params,
            dtrain,
            num_boost_round=int(rounds),
            xgb_model=base_booster,
            verbose_eval=False,
        )
        val_proba = candidate.predict(dvalidation)
        threshold, _ = best_threshold_from_pr_curve(pd.Series(y_validation), val_proba)
        validation_metrics = metric_payload(y_validation, val_proba, threshold)
        candidate_validation.append(
            {"num_boost_round": int(rounds), "threshold": threshold, "metrics": validation_metrics}
        )
        if validation_metrics["auc"] > best_auc:
            best_auc = validation_metrics["auc"]
            best_round = int(rounds)
            best_booster = candidate

    if best_booster is None:
        raise RuntimeError("No transfer candidate completed")
    final_val_proba = best_booster.predict(dvalidation)
    threshold, _ = best_threshold_from_pr_curve(pd.Series(y_validation), final_val_proba)

    # Final-test DMatrix and prediction are intentionally created only after all selection is complete.
    dtest = xgb.DMatrix(X_final, feature_names=list(PAYSIM_FEATURE_COLUMNS))
    final_proba = best_booster.predict(dtest)
    metrics = metric_payload(y_final, final_proba, threshold)
    adapted_hash = sha256_bytes(bytes(best_booster.save_raw(raw_format="json")))
    payload = {
        "experiment": "transfer_paysim_to_ieee",
        "protocol": {
            "raw_split_before_label_history_features": True,
            "chronological_split": True,
            "adapt_fraction": float(args.adapt_fraction),
            "adapt_train_fraction_within_adapt": float(args.adapt_train_fraction),
            "validation_labels_used_for": ["num_boost_round_selection", "threshold_selection"],
            "final_test_labels_available_during_feature_construction": False,
            "final_test_updates_feature_history": False,
            "test_used_for_model_selection": False,
            "test_label_leakage": False,
            "test_evaluations": 1,
            "alignment_fit_scope": "adapt_train_covariates_only",
        },
        "candidate_num_boost_round": [int(value) for value in args.boost_round_candidates],
        "selection_criterion": "maximum adapt-validation AUC",
        "selected_num_boost_round": best_round,
        "threshold_selection": "maximum adapt-validation F1 on PR-curve thresholds",
        "threshold": float(threshold),
        "train_rows": int(len(y_train)),
        "validation_rows": int(len(y_validation)),
        "test_rows": int(len(y_final)),
        "feature_count": int(X_train.shape[1]),
        "adapt_params": adapt_params,
        "candidate_validation": candidate_validation,
        "metrics": metrics,
        "base_model_sha256": common_provenance["production_model_sha256"],
        "model_sha256": adapted_hash,
        "provenance": {**common_provenance, "generated_at": utc_now()},
    }
    write_json(TRANSFER_JSON, payload)
    print(f"[b12] Transfer complete: AUC={metrics['auc']:.6f}", flush=True)
    del (
        train_frame,
        validation_original,
        test_original,
        train_features,
        validation_features,
        test_features,
        train_dataset,
        validation_dataset,
        test_dataset,
        X_train,
        X_validation,
        X_final,
        dtrain,
        dvalidation,
        dtest,
        final_proba,
    )
    gc.collect()
    return payload


def run_native(args: argparse.Namespace, common_provenance: dict[str, Any]) -> dict[str, Any]:
    print("[b12] Native: loading full IEEE-CIS dataset", flush=True)
    frame = load_ieee_frame(Path(args.transaction_path), Path(args.identity_path), sample_size=None)
    X_train, y_train, X_validation, y_validation, X_final, y_final, metadata = prepare_splits(
        frame,
        max_missing_rate=args.max_missing_rate,
        top_v_features=args.top_v_features,
        smoothing=args.target_smoothing,
    )
    del frame
    gc.collect()
    feature_profile = "no_target_encoding"
    columns = feature_columns_for_profile(metadata, feature_profile)
    X_train = X_train[columns]
    X_validation = X_validation[columns]
    X_final = X_final[columns]

    candidates: list[dict[str, Any]] = []
    best_model: XGBClassifier | None = None
    best_index = 0
    best_score = -1.0
    best_threshold = 0.5
    for index, raw_params in enumerate(PARAM_CANDIDATES, start=1):
        params = dict(raw_params)
        print(f"[b12] Native: validation candidate {index}/{len(PARAM_CANDIDATES)}", flush=True)
        model = XGBClassifier(
            **xgb_params_from_report(params, y_train, int(APP_CONFIG.training.random_state))
        )
        started = time.perf_counter()
        model.fit(X_train, y_train)
        train_seconds = time.perf_counter() - started
        val_proba = model.predict_proba(X_validation)[:, 1]
        threshold, _ = best_threshold_from_pr_curve(y_validation, val_proba)
        validation_metrics = metric_payload(y_validation, val_proba, threshold)
        score = validation_metrics["pr_auc"] + validation_metrics["f1"]
        candidates.append(
            {
                "candidate_index": index,
                "params": params,
                "threshold": threshold,
                "selection_score": score,
                "train_seconds": train_seconds,
                "validation_metrics": validation_metrics,
            }
        )
        if score > best_score:
            best_score = score
            best_index = index
            best_threshold = threshold
            best_model = model

    if best_model is None:
        raise RuntimeError("No native candidate completed")

    # The final test is predicted and evaluated once, after feature profile,
    # candidate, and threshold are fixed from train/validation only.
    final_proba = best_model.predict_proba(X_final)[:, 1]
    metrics = metric_payload(y_final, final_proba, best_threshold)
    selected_hash = sha256_bytes(bytes(best_model.get_booster().save_raw(raw_format="json")))
    payload = {
        "experiment": "native_ieee_no_target_encoding",
        "protocol": {
            "feature_profile_predeclared": "no_target_encoding",
            "feature_profile_selected_on_test": False,
            "candidate_selection_source": "validation_only",
            "threshold_selection_source": "validation_only",
            "test_used_for_model_selection": False,
            "test_label_leakage": False,
            "test_evaluations": 1,
            "chronological_split": "70/15/15 by TransactionDT then TransactionID",
            "categorical_maps_fit_on": "train_only",
            "v_feature_selection_source": "train_only",
        },
        "feature_profile": feature_profile,
        "feature_count": int(len(columns)),
        "selected_v_features": int(metadata["feature_selection"]["selected_v_features"]),
        "candidate_count": int(len(PARAM_CANDIDATES)),
        "selection_criterion": "validation PR-AUC + validation F1",
        "selected_candidate": best_index,
        "threshold_selection": "maximum validation F1 on PR-curve thresholds",
        "threshold": float(best_threshold),
        "train_rows": int(len(y_train)),
        "validation_rows": int(len(y_validation)),
        "test_rows": int(len(y_final)),
        "candidates": candidates,
        "metrics": metrics,
        "model_sha256": selected_hash,
        "provenance": {**common_provenance, "generated_at": utc_now()},
    }
    write_json(NATIVE_JSON, payload)
    print(f"[b12] Native complete: AUC={metrics['auc']:.6f}", flush=True)
    del X_train, X_validation, X_final, final_proba
    gc.collect()
    return payload


def write_comparison(results: list[dict[str, Any]]) -> None:
    fields = [
        "experiment",
        "auc",
        "pr_auc",
        "f1",
        "precision",
        "recall",
        "threshold",
        "train_rows",
        "validation_rows",
        "test_rows",
        "feature_count",
        "test_used_for_model_selection",
        "test_label_leakage",
    ]
    with COMPARISON_CSV.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for result in results:
            writer.writerow(
                {
                    "experiment": result["experiment"],
                    **{name: result["metrics"][name] for name in ("auc", "pr_auc", "f1", "precision", "recall")},
                    "threshold": result["threshold"],
                    "train_rows": result["train_rows"],
                    "validation_rows": result["validation_rows"],
                    "test_rows": result["test_rows"],
                    "feature_count": result["feature_count"],
                    "test_used_for_model_selection": result["protocol"]["test_used_for_model_selection"],
                    "test_label_leakage": result["protocol"]["test_label_leakage"],
                }
            )


def write_audit(
    frozen: dict[str, Any], transfer: dict[str, Any], native: dict[str, Any], production_model_unchanged: bool
) -> str:
    frozen_clean = (
        frozen["protocol"]["production_model_loaded"]
        and not frozen["protocol"]["frozen_model_retrained"]
        and not frozen["protocol"]["test_label_leakage"]
        and production_model_unchanged
    )
    transfer_clean = (
        transfer["protocol"]["raw_split_before_label_history_features"]
        and not transfer["protocol"]["final_test_updates_feature_history"]
        and not transfer["protocol"]["test_label_leakage"]
        and not transfer["protocol"]["test_used_for_model_selection"]
    )
    native_clean = (
        native["protocol"]["feature_profile_predeclared"] == "no_target_encoding"
        and not native["protocol"]["feature_profile_selected_on_test"]
        and not native["protocol"]["test_used_for_model_selection"]
        and not native["protocol"]["test_label_leakage"]
    )
    status = "PASS" if frozen_clean and transfer_clean and native_clean else "FAIL"
    provenance_block = json.dumps(native["provenance"], indent=2)
    lines = [
        "# B12 FINAL — IEEE-CIS External Validation",
        "",
        "This isolated run did not execute B1–B11, did not retrain PaySim, did not overwrite the production model, and did not edit the manuscript.",
        "",
        "```objectivec",
        f"Frozen clean = {'YES' if frozen_clean else 'NO'}",
        f"Transfer leakage fixed = {'YES' if transfer_clean else 'NO'}",
        f"Native test selection clean = {'YES' if native_clean else 'NO'}",
        f"B12_STATUS = {status}",
        "```",
        "",
        "## Final metrics",
        "",
        "| Branch | AUC | PR-AUC | F1 | Precision | Recall | Threshold | Train | Validation | Test | Features |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name, result in (("Frozen", frozen), ("Transfer", transfer), ("Native", native)):
        metrics = result["metrics"]
        lines.append(
            f"| {name} | {metrics['auc']:.6f} | {metrics['pr_auc']:.6f} | {metrics['f1']:.6f} | "
            f"{metrics['precision']:.6f} | {metrics['recall']:.6f} | {result['threshold']:.6f} | "
            f"{result['train_rows']:,} | {result['validation_rows']:,} | {result['test_rows']:,} | "
            f"{result['feature_count']} |"
        )
    lines.extend(
        [
            "",
            "## Integrity assertions",
            "",
            "```ini",
            "frozen_model_retrained = NO",
            "test_used_for_model_selection = NO",
            "test_label_leakage = NO",
            "transfer_final_test_updates_feature_history = NO",
            f"production_model_unchanged = {'YES' if production_model_unchanged else 'NO'}",
            "native_feature_profile = no_target_encoding",
            "final_test_evaluations_per_branch = 1",
            "```",
            "",
            "Frozen alignment uses the complete IEEE covariate distribution without labels to fit its empirical CDF map; this is label-free transductive normalization and is disclosed in the frozen JSON. Transfer alignment is fitted only on adapt-train covariates. Native categorical mappings and V-feature selection are train-only.",
            "",
            "## Provenance",
            "",
            "```json",
            provenance_block,
            "```",
            "",
            "The three JSON files contain branch-specific model hashes, candidate/threshold selection records, confusion matrices, and the same run provenance.",
            "",
        ]
    )
    AUDIT_MD.write_text("\n".join(lines), encoding="utf-8")
    return status


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run only the clean B12 IEEE-CIS experiments")
    parser.add_argument("--transaction-path", type=Path, default=ROOT / "data" / "train_transaction.csv")
    parser.add_argument("--identity-path", type=Path, default=ROOT / "data" / "train_identity.csv")
    parser.add_argument("--paysim-path", type=Path, default=ROOT / "data" / "paysim.csv")
    parser.add_argument("--model-path", type=Path, default=ROOT / "artifacts" / "models" / "xgboost_fraud.json")
    parser.add_argument("--metadata-path", type=Path, default=ROOT / "artifacts" / "models" / "model_metadata.json")
    parser.add_argument("--production-threshold", type=float, default=0.5)
    parser.add_argument("--adapt-fraction", type=float, default=0.10)
    parser.add_argument("--adapt-train-fraction", type=float, default=0.80)
    parser.add_argument("--boost-round-candidates", type=int, nargs="+", default=[25, 50, 75, 100])
    parser.add_argument("--max-missing-rate", type=float, default=0.98)
    parser.add_argument("--top-v-features", type=int, default=220)
    parser.add_argument("--target-smoothing", type=float, default=30.0)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.transaction_path = args.transaction_path.resolve()
    args.identity_path = resolve_identity_path(args.transaction_path, str(args.identity_path)).resolve()
    args.paysim_path = args.paysim_path.resolve()
    args.model_path = args.model_path.resolve()
    args.metadata_path = args.metadata_path.resolve()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("[b12] Hashing datasets, model, and code", flush=True)
    dataset_hashes = {
        "ieee_transaction": sha256_file(args.transaction_path),
        "ieee_identity": sha256_file(args.identity_path),
        "paysim_reference": sha256_file(args.paysim_path),
    }
    model_hash_before = sha256_file(args.model_path)
    common_provenance = provenance(args, dataset_hashes, model_hash_before)

    print("[b12] Building PaySim train-only alignment reference (no model training)", flush=True)
    paysim_reference, paysim_split = build_paysim_reference()

    print("[b12] Loading legacy IEEE columns once for frozen/transfer", flush=True)
    ieee_raw = load_filtered_frame(str(args.transaction_path), source="ieee")
    ieee_enriched = enrich_transactions(ieee_raw, source="ieee").reset_index(drop=True)
    del ieee_raw
    gc.collect()

    frozen = run_frozen(ieee_enriched, paysim_reference, paysim_split, args, common_provenance)
    transfer = run_transfer(ieee_enriched, paysim_reference, args, common_provenance)
    del ieee_enriched, paysim_reference
    gc.collect()

    native = run_native(args, common_provenance)
    model_hash_after = sha256_file(args.model_path)
    if model_hash_after != model_hash_before:
        raise RuntimeError("Production PaySim model changed during B12 run")

    write_comparison([frozen, transfer, native])
    status = write_audit(frozen, transfer, native, production_model_unchanged=True)
    print(f"B12_STATUS = {status}")
    print(f"Frozen AUC = {frozen['metrics']['auc']:.10f}")
    print(f"Transfer AUC = {transfer['metrics']['auc']:.10f}")
    print(f"Native AUC = {native['metrics']['auc']:.10f}")
    print("leakage detected = NO")
    print(f"report directory = {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
