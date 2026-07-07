"""
Chạy so sánh metrics trước và sau khi fix data leakage trong feature pipeline.

Leakage bug (trước fix):
    build_feature_frame() được gọi trên TOÀN BỘ dataset trước khi split.
    Khi đó, các feature fraud-rate (location_fraud_rate, ip_fraud_rate,
    merchant_fraud_rate) của val/test rows được tính với store đã nhận labels
    từ các val/test row trước đó.

Fix (sau fix):
    Split enriched TRƯỚC khi build features.
    Val/test features được build với freeze_risk_labels=True — store không
    nhận fraud labels từ val/test, chỉ cập nhật activity counts.

Chạy:
    python scripts/compute_leakage_comparison.py
    python scripts/compute_leakage_comparison.py --sample-size 50000
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
from sklearn.metrics import (
    average_precision_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from xgboost import XGBClassifier

from fraud_flow.config import APP_CONFIG
from fraud_flow.feature_store import FeatureStore
from fraud_flow.features import (
    build_feature_frame,
    detect_data_source,
    enrich_transactions,
    feature_columns_for_source,
    load_filtered_frame,
)
from fraud_flow.training import (
    build_class_balance,
    find_best_threshold,
    split_indices,
)


REPORT_PATH = Path("artifacts/reports/leakage_comparison.json")

XGB_PARAMS = {
    "n_estimators": 260,
    "max_depth": 6,
    "learning_rate": 0.06,
    "subsample": 0.9,
    "colsample_bytree": 0.85,
}


def compute_metrics(y_true, proba, threshold):
    pred = (proba >= threshold).astype(int)
    auc = float(roc_auc_score(y_true, proba)) if len(set(y_true)) > 1 else 0.0
    pr_auc = float(average_precision_score(y_true, proba)) if len(set(y_true)) > 1 else 0.0
    return {
        "auc": round(auc, 6),
        "pr_auc": round(pr_auc, 6),
        "f1": round(float(f1_score(y_true, pred, zero_division=0)), 6),
        "precision": round(float(precision_score(y_true, pred, zero_division=0)), 6),
        "recall": round(float(recall_score(y_true, pred, zero_division=0)), 6),
    }


def train_and_eval(X_train, y_train, X_val, y_val, X_test, y_test):
    cb = build_class_balance(y_train)
    model = XGBClassifier(
        objective="binary:logistic",
        eval_metric="logloss",
        random_state=APP_CONFIG.training.random_state,
        n_jobs=APP_CONFIG.training.n_jobs,
        scale_pos_weight=float(cb["scale_pos_weight"]),
        max_delta_step=APP_CONFIG.training.max_delta_step,
        tree_method="hist",
        **XGB_PARAMS,
    )
    t0 = time.perf_counter()
    model.fit(X_train, y_train)
    train_sec = time.perf_counter() - t0

    val_proba = model.predict_proba(X_val)[:, 1]
    test_proba = model.predict_proba(X_test)[:, 1]
    threshold, _ = find_best_threshold(y_val, val_proba)
    return (
        compute_metrics(y_val, val_proba, threshold),
        compute_metrics(y_test, test_proba, threshold),
        threshold,
        round(train_sec, 2),
    )


def run_leaky_pipeline(enriched, source, feature_columns):
    """
    Mô phỏng pipeline TRƯỚC fix: build features trên TOÀN BỘ data,
    sau đó mới split. Store được cập nhật với TOÀN BỘ labels bao gồm val/test.
    """
    feature_frame, _, _ = build_feature_frame(enriched, source=source)  # full observe
    train_end, val_end = split_indices(len(enriched))

    X_train = feature_frame.iloc[:train_end][feature_columns]
    y_train = enriched.iloc[:train_end]["isFraud"]
    X_val = feature_frame.iloc[train_end:val_end][feature_columns]
    y_val = enriched.iloc[train_end:val_end]["isFraud"]
    X_test = feature_frame.iloc[val_end:][feature_columns]
    y_test = enriched.iloc[val_end:]["isFraud"]

    return train_and_eval(X_train, y_train, X_val, y_val, X_test, y_test)


def run_fixed_pipeline(enriched, source, feature_columns):
    """
    Pipeline SAU fix: split trước, freeze_risk_labels=True cho val/test.
    """
    train_end, val_end = split_indices(len(enriched))
    enriched_train = enriched.iloc[:train_end]
    enriched_eval = enriched.iloc[train_end:]

    train_feature_frame, _, trained_store = build_feature_frame(enriched_train, source=source)
    eval_feature_frame, _, _ = build_feature_frame(
        enriched_eval, source=source, freeze_risk_labels=True, store=trained_store
    )
    feature_frame_all = __import__("pandas").concat(
        [train_feature_frame, eval_feature_frame], ignore_index=True
    )

    X_train = feature_frame_all.iloc[:train_end][feature_columns]
    y_train = enriched.iloc[:train_end]["isFraud"]
    X_val = feature_frame_all.iloc[train_end:val_end][feature_columns]
    y_val = enriched.iloc[train_end:val_end]["isFraud"]
    X_test = feature_frame_all.iloc[val_end:][feature_columns]
    y_test = enriched.iloc[val_end:]["isFraud"]

    return train_and_eval(X_train, y_train, X_val, y_val, X_test, y_test)


def main():
    parser = argparse.ArgumentParser(description="Before/after data leakage comparison")
    parser.add_argument("--sample-size", type=int, default=None,
                        help="Limit rows for quick smoke test (default: full dataset)")
    args = parser.parse_args()

    source = detect_data_source()
    feature_columns = feature_columns_for_source(source)

    print(f"[leakage_comparison] Loading data (source={source}, sample={args.sample_size})...")
    raw = load_filtered_frame(sample_size=args.sample_size, source=source)
    enriched = enrich_transactions(raw, source=source).reset_index(drop=True)
    print(f"[leakage_comparison] Total rows: {len(enriched)}")

    print("[leakage_comparison] Running LEAKY pipeline (pre-fix)...")
    t0 = time.perf_counter()
    leaky_val, leaky_test, leaky_thr, leaky_train_s = run_leaky_pipeline(enriched, source, feature_columns)
    leaky_total_s = time.perf_counter() - t0
    print(f"  Done in {leaky_total_s:.1f}s  |  test AUC={leaky_test['auc']:.6f}  F1={leaky_test['f1']:.6f}")

    print("[leakage_comparison] Running FIXED pipeline (post-fix)...")
    t0 = time.perf_counter()
    fixed_val, fixed_test, fixed_thr, fixed_train_s = run_fixed_pipeline(enriched, source, feature_columns)
    fixed_total_s = time.perf_counter() - t0
    print(f"  Done in {fixed_total_s:.1f}s  |  test AUC={fixed_test['auc']:.6f}  F1={fixed_test['f1']:.6f}")

    # Compute deltas (leaky - fixed; positive = leaky was inflated)
    delta = {
        "test_auc": round(leaky_test["auc"] - fixed_test["auc"], 6),
        "test_f1": round(leaky_test["f1"] - fixed_test["f1"], 6),
        "test_pr_auc": round(leaky_test["pr_auc"] - fixed_test["pr_auc"], 6),
        "test_precision": round(leaky_test["precision"] - fixed_test["precision"], 6),
        "test_recall": round(leaky_test["recall"] - fixed_test["recall"], 6),
    }

    print("\n=== Leakage Comparison Results ===")
    print(f"{'Metric':<22} {'LEAKY (pre-fix)':>18} {'FIXED (post-fix)':>18} {'Delta (leaky-fixed)':>22}")
    print("-" * 84)
    for key in ["auc", "pr_auc", "f1", "precision", "recall"]:
        leaky_v = leaky_test[key]
        fixed_v = fixed_test[key]
        d = delta[f"test_{key}"]
        flag = "  ← inflated" if d > 0.001 else ""
        print(f"  Test {key:<17} {leaky_v:>18.6f} {fixed_v:>18.6f} {d:>+22.6f}{flag}")
    print("-" * 84)
    print(f"\nConclusion: leakage {'DID inflate' if any(v > 0.001 for v in delta.values()) else 'did NOT significantly inflate'} metrics.")

    report = {
        "description": "Before vs. after data leakage fix comparison",
        "sample_size": len(enriched),
        "source": source,
        "leaky_pipeline": {
            "val_metrics": leaky_val,
            "test_metrics": leaky_test,
            "selected_threshold": leaky_thr,
            "train_seconds": leaky_train_s,
        },
        "fixed_pipeline": {
            "val_metrics": fixed_val,
            "test_metrics": fixed_test,
            "selected_threshold": fixed_thr,
            "train_seconds": fixed_train_s,
        },
        "delta_leaky_minus_fixed": delta,
    }

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n[leakage_comparison] Report saved: {REPORT_PATH}")


if __name__ == "__main__":
    main()
