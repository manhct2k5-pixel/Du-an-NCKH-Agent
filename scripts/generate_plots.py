"""
Tạo các biểu đồ kết quả: ROC curve, PR curve, threshold sweep, và
bảng so sánh baseline — từ các CSV artifact đã có sẵn.

Output:  artifacts/reports/plots/
    - roc_curve.png
    - pr_curve.png
    - threshold_sweep.png
    - baseline_comparison.png
    - leakage_comparison.png  (nếu artifacts/reports/leakage_comparison.json tồn tại)

Chạy:
    python scripts/generate_plots.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import matplotlib
matplotlib.use("Agg")  # no display needed
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


REPORT_DIR = Path("artifacts/reports")
PLOT_DIR = REPORT_DIR / "plots"


def save(fig: plt.Figure, name: str) -> None:
    PLOT_DIR.mkdir(parents=True, exist_ok=True)
    path = PLOT_DIR / name
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {path}")


def plot_roc_curves():
    val_path = REPORT_DIR / "validation_roc_curve.csv"
    test_path = REPORT_DIR / "test_roc_curve.csv"
    if not val_path.exists() or not test_path.exists():
        print("  [skip] ROC curve CSVs not found")
        return

    val_df = pd.read_csv(val_path)
    test_df = pd.read_csv(test_path)

    with open(REPORT_DIR / "evaluation_report.json", encoding="utf-8") as fh:
        report = json.load(fh)
    val_auc = report["validation"]["roc_auc"]
    test_auc = report["test"]["roc_auc"]

    fig, ax = plt.subplots(figsize=(7, 6))
    ax.plot(val_df["fpr"], val_df["tpr"],
            label=f"Validation (AUC = {val_auc:.4f})", color="#1f77b4", linewidth=2)
    ax.plot(test_df["fpr"], test_df["tpr"],
            label=f"Test (AUC = {test_auc:.4f})", color="#ff7f0e", linewidth=2)
    ax.plot([0, 1], [0, 1], "k--", linewidth=1, label="Random baseline")
    ax.set_xlabel("False Positive Rate")
    ax.set_ylabel("True Positive Rate")
    ax.set_title("ROC Curve — FraudFlow XGBoost (post leakage fix)")
    ax.legend(loc="lower right")
    ax.grid(alpha=0.3)
    save(fig, "roc_curve.png")


def plot_pr_curves():
    val_path = REPORT_DIR / "validation_pr_curve.csv"
    test_path = REPORT_DIR / "test_pr_curve.csv"
    if not val_path.exists() or not test_path.exists():
        print("  [skip] PR curve CSVs not found")
        return

    val_df = pd.read_csv(val_path).dropna()
    test_df = pd.read_csv(test_path).dropna()

    with open(REPORT_DIR / "evaluation_report.json", encoding="utf-8") as fh:
        report = json.load(fh)
    val_pr_auc = report["validation"]["pr_auc"]
    test_pr_auc = report["test"]["pr_auc"]

    fig, ax = plt.subplots(figsize=(7, 6))
    ax.plot(val_df["recall"], val_df["precision"],
            label=f"Validation (PR-AUC = {val_pr_auc:.4f})", color="#1f77b4", linewidth=2)
    ax.plot(test_df["recall"], test_df["precision"],
            label=f"Test (PR-AUC = {test_pr_auc:.4f})", color="#ff7f0e", linewidth=2)
    ax.set_xlabel("Recall")
    ax.set_ylabel("Precision")
    ax.set_title("Precision-Recall Curve — FraudFlow XGBoost (post leakage fix)")
    ax.legend(loc="upper right")
    ax.grid(alpha=0.3)
    save(fig, "pr_curve.png")


def plot_threshold_sweep():
    path = REPORT_DIR / "validation_threshold_sweep.csv"
    if not path.exists():
        print("  [skip] Threshold sweep CSV not found")
        return

    df = pd.read_csv(path)
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(df["threshold"], df["f1"], label="F1", color="#2ca02c", linewidth=2, marker="o", markersize=4)
    ax.plot(df["threshold"], df["precision"], label="Precision", color="#1f77b4", linewidth=2, marker="s", markersize=4)
    ax.plot(df["threshold"], df["recall"], label="Recall", color="#d62728", linewidth=2, marker="^", markersize=4)
    ax.set_xlabel("Decision Threshold")
    ax.set_ylabel("Score")
    ax.set_title("Threshold Sweep on Validation Set")
    ax.legend()
    ax.grid(alpha=0.3)
    ax.set_ylim(0, 1.05)
    save(fig, "threshold_sweep.png")


def plot_baseline_comparison():
    path = REPORT_DIR / "baseline_comparison.json"
    if not path.exists():
        print("  [skip] baseline_comparison.json not found")
        return

    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)

    models = [m for m in data["models"] if m["model_name"] != "dummy_prior"]
    names = [m["model_name"] for m in models]
    metrics = ["auc", "f1", "precision", "recall"]
    colors = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728"]

    x = np.arange(len(names))
    width = 0.2
    fig, ax = plt.subplots(figsize=(10, 6))
    for i, (metric, color) in enumerate(zip(metrics, colors)):
        vals = [m["test"]["metrics"][metric] for m in models]
        bars = ax.bar(x + i * width, vals, width, label=metric.upper(), color=color, alpha=0.85)
        for bar, val in zip(bars, vals):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.002,
                    f"{val:.3f}", ha="center", va="bottom", fontsize=8)

    ax.set_xlabel("Model")
    ax.set_ylabel("Test Score")
    ax.set_title("Baseline Comparison — Test Set (post leakage fix)")
    ax.set_xticks(x + width * 1.5)
    ax.set_xticklabels(names, rotation=15)
    ax.legend()
    ax.set_ylim(0, 1.08)
    ax.grid(axis="y", alpha=0.3)
    save(fig, "baseline_comparison.png")


def plot_leakage_comparison():
    path = REPORT_DIR / "leakage_comparison.json"
    if not path.exists():
        print("  [skip] leakage_comparison.json not found — run scripts/compute_leakage_comparison.py first")
        return

    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)

    metrics = ["auc", "pr_auc", "f1", "precision", "recall"]
    leaky_vals = [data["leaky_pipeline"]["test_metrics"][m] for m in metrics]
    fixed_vals = [data["fixed_pipeline"]["test_metrics"][m] for m in metrics]

    x = np.arange(len(metrics))
    width = 0.35
    fig, ax = plt.subplots(figsize=(9, 5))
    b1 = ax.bar(x - width / 2, leaky_vals, width, label="Pre-fix (leaky)", color="#d62728", alpha=0.85)
    b2 = ax.bar(x + width / 2, fixed_vals, width, label="Post-fix (correct)", color="#2ca02c", alpha=0.85)
    for bars in (b1, b2):
        for bar in bars:
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.002,
                    f"{bar.get_height():.4f}", ha="center", va="bottom", fontsize=8)

    ax.set_xlabel("Metric")
    ax.set_ylabel("Test Score")
    ax.set_title(f"Leakage Fix Impact (n={data['sample_size']:,})")
    ax.set_xticks(x)
    ax.set_xticklabels([m.upper().replace("_", "-") for m in metrics])
    ax.legend()
    ax.set_ylim(0.8, 1.05)
    ax.grid(axis="y", alpha=0.3)
    save(fig, "leakage_comparison.png")


def plot_feature_ablation():
    path = REPORT_DIR / "feature_ablation.json"
    if not path.exists():
        print("  [skip] feature_ablation.json not found")
        return

    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)

    ablations = data["ablations"]
    names = [a["name"].replace("_", "\n") for a in ablations]
    f1_vals = [a["test_metrics"]["f1"] for a in ablations]
    auc_vals = [a["test_metrics"]["auc"] for a in ablations]

    x = np.arange(len(names))
    width = 0.35
    fig, ax = plt.subplots(figsize=(10, 5))
    b1 = ax.bar(x - width / 2, f1_vals, width, label="Test F1", color="#1f77b4", alpha=0.85)
    b2 = ax.bar(x + width / 2, auc_vals, width, label="Test AUC", color="#ff7f0e", alpha=0.85)
    for bars in (b1, b2):
        for bar in bars:
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.002,
                    f"{bar.get_height():.3f}", ha="center", va="bottom", fontsize=8)

    ax.set_xlabel("Feature Group")
    ax.set_ylabel("Test Score")
    ax.set_title("Feature Ablation Study")
    ax.set_xticks(x)
    ax.set_xticklabels(names, fontsize=9)
    ax.legend()
    ax.set_ylim(0.7, 1.05)
    ax.grid(axis="y", alpha=0.3)
    save(fig, "feature_ablation.png")


def main():
    print("[generate_plots] Generating plots...")
    plot_roc_curves()
    plot_pr_curves()
    plot_threshold_sweep()
    plot_baseline_comparison()
    plot_feature_ablation()
    plot_leakage_comparison()
    print(f"[generate_plots] Done. Plots saved to {PLOT_DIR}")


if __name__ == "__main__":
    main()
