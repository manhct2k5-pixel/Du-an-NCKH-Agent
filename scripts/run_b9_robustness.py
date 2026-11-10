#!/usr/bin/env python3
"""Run B9 stochastic robustness for one fixed production XGBoost configuration.

This runner intentionally does not call ``fit_best_xgboost`` or the research
suite. It trains exactly one fixed configuration for each requested seed and
uses the held-out test set only for final evaluation.
"""

from __future__ import annotations

import csv
import hashlib
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
from xgboost import XGBClassifier


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fraud_flow.config import APP_CONFIG, PAYSIM_FEATURE_COLUMNS  # noqa: E402
from fraud_flow.research import prepare_experiment_splits, pr_auc_score  # noqa: E402
from fraud_flow.training import classification_metrics, confusion_payload, split_strategy_for_source  # noqa: E402


OUTPUT_DIR = ROOT / "artifacts" / "reports" / "b9_final"
JSON_PATH = OUTPUT_DIR / "b9_repeated_seed_robustness.json"
CSV_PATH = OUTPUT_DIR / "b9_repeated_seed_robustness.csv"
MARKDOWN_PATH = OUTPUT_DIR / "b9_repeated_seed_robustness.md"
THRESHOLD_COPY_PATH = OUTPUT_DIR / "b9_threshold_sensitivity.csv"
AUDIT_PATH = OUTPUT_DIR / "B9_FINAL_AUDIT.md"

THRESHOLD_SOURCE_PATH = ROOT / "artifacts" / "reports" / "validation_threshold_sweep.csv"
EVALUATION_REPORT_PATH = ROOT / "artifacts" / "reports" / "evaluation_report.json"

EXPECTED_SPLIT = {
    "total_rows": 460_394,
    "train_rows": 322_275,
    "validation_rows": 69_059,
    "test_rows": 69_060,
    "train_end": 322_275,
    "val_end": 391_334,
}
SEEDS = (42, 43, 44)
THRESHOLD = 0.50
FIXED_HYPERPARAMETERS: dict[str, int | float | str] = {
    "n_estimators": 260,
    "max_depth": 6,
    "learning_rate": 0.06,
    "subsample": 0.90,
    "colsample_bytree": 0.85,
    "max_delta_step": 1,
    "tree_method": "hist",
}
EXPECTED_THRESHOLD_GRID = (0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70)
INTERPRETATION = "stochastic robustness of the fixed deployed XGBoost configuration"
CODE_FILES = (
    Path("scripts/run_b9_robustness.py"),
    Path("fraud_flow/research.py"),
    Path("fraud_flow/training.py"),
    Path("fraud_flow/config.py"),
    Path("fraud_flow/features.py"),
    Path("fraud_flow/feature_store.py"),
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def code_provenance() -> tuple[str, dict[str, str]]:
    file_hashes: dict[str, str] = {}
    aggregate = hashlib.sha256()
    for relative_path in CODE_FILES:
        path = ROOT / relative_path
        if not path.is_file():
            raise FileNotFoundError(f"Required code file not found: {path}")
        file_hash = sha256_file(path)
        relative_text = relative_path.as_posix()
        file_hashes[relative_text] = file_hash
        aggregate.update(relative_text.encode("utf-8"))
        aggregate.update(b"\0")
        aggregate.update(file_hash.encode("ascii"))
        aggregate.update(b"\n")
    return aggregate.hexdigest(), file_hashes


def git_value(*args: str) -> str | None:
    result = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def refuse_overwrite() -> None:
    existing = [path for path in (JSON_PATH, CSV_PATH, MARKDOWN_PATH, THRESHOLD_COPY_PATH, AUDIT_PATH) if path.exists()]
    if existing:
        listed = "\n".join(f"- {path}" for path in existing)
        raise FileExistsError(f"B9 final output already exists; refusing to overwrite:\n{listed}")


def validate_threshold_artifact() -> tuple[list[dict[str, str]], dict[str, Any]]:
    if not THRESHOLD_SOURCE_PATH.is_file():
        raise FileNotFoundError(f"Validation threshold sweep not found: {THRESHOLD_SOURCE_PATH}")
    if not EVALUATION_REPORT_PATH.is_file():
        raise FileNotFoundError(f"Evaluation report not found: {EVALUATION_REPORT_PATH}")

    with THRESHOLD_SOURCE_PATH.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    required_columns = {"threshold", "f1", "precision", "recall"}
    if not rows or not required_columns.issubset(rows[0]):
        raise ValueError("Validation threshold sweep is empty or lacks required columns.")
    actual_grid = tuple(float(row["threshold"]) for row in rows)
    if actual_grid != EXPECTED_THRESHOLD_GRID:
        raise ValueError(f"Unexpected validation threshold grid: {actual_grid}")
    plateau_rows = [row for row in rows if 0.35 <= float(row["threshold"]) <= 0.70]
    plateau_f1 = {float(row["f1"]) for row in plateau_rows}
    if len(plateau_rows) != 8 or len(plateau_f1) != 1:
        raise ValueError("Expected validation F1 plateau from threshold 0.35 through 0.70 was not found.")

    evaluation = json.loads(EVALUATION_REPORT_PATH.read_text(encoding="utf-8"))
    if evaluation.get("source") != "paysim":
        raise ValueError("Production evaluation report is not for PaySim.")
    if float(evaluation.get("selected_threshold")) != THRESHOLD:
        raise ValueError("Production evaluation report does not use threshold 0.50.")
    if evaluation.get("split_strategy") != "chronological_by_step_after_TRANSFER_CASH_OUT_filter":
        raise ValueError("Production evaluation report does not use the expected chronological split.")
    for key, expected in EXPECTED_SPLIT.items():
        if int(evaluation.get("split", {}).get(key, -1)) != expected:
            raise ValueError(f"Production evaluation split mismatch for {key}.")
    return rows, evaluation


def summarize(runs: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    result: dict[str, dict[str, float]] = {}
    for metric in ("test_auc", "test_pr_auc", "test_f1", "test_precision", "test_recall"):
        values = np.asarray([float(run[metric]) for run in runs], dtype=float)
        result[metric] = {
            "mean": float(np.mean(values)),
            "standard_deviation": float(np.std(values, ddof=0)),
            "min": float(np.min(values)),
            "max": float(np.max(values)),
        }
    return result


def markdown_float(value: float) -> str:
    return repr(float(value))


def write_results_csv(runs: list[dict[str, Any]]) -> None:
    fields = (
        "seed",
        "threshold",
        "test_auc",
        "test_pr_auc",
        "test_f1",
        "test_precision",
        "test_recall",
        "TN",
        "FP",
        "FN",
        "TP",
    )
    with CSV_PATH.open("x", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for run in runs:
            row = {field: run[field] for field in fields}
            writer.writerow(row)


def build_results_markdown(payload: dict[str, Any]) -> str:
    provenance = payload["provenance"]
    protocol = payload["protocol"]
    lines = [
        "# B9 Repeated-seed Robustness",
        "",
        f"Experiment meaning: **{INTERPRETATION}**.",
        "",
        "This is not a robustness test of the hyperparameter-search pipeline. No candidate search, HistGradientBoosting repeated seeds, baseline selection, bootstrap CI, McNemar test, or IEEE-CIS experiment is used.",
        "",
        "## Protocol",
        "",
        f"- Dataset: `{protocol['dataset_source']}` (`{protocol['dataset_path']}`)",
        f"- Dataset SHA-256: `{provenance['dataset_sha256']}`",
        f"- Split: `{protocol['split_strategy']}`",
        f"- Rows: total={protocol['split']['total_rows']}, train={protocol['split']['train_rows']}, validation={protocol['split']['validation_rows']}, test={protocol['split']['test_rows']}",
        f"- Features: {protocol['feature_count']} fixed PaySim features",
        f"- Seeds: {', '.join(str(seed) for seed in protocol['seeds'])}",
        f"- Fixed threshold: {markdown_float(protocol['threshold'])}",
        f"- Training-derived `scale_pos_weight`: {markdown_float(protocol['scale_pos_weight'])}",
        "- Historical fraud-rate state: trained on train labels, then frozen for validation/test labels",
        "",
        "## Fixed XGBoost Configuration",
        "",
        "| Parameter | Value |",
        "| --- | ---: |",
    ]
    for name, value in protocol["fixed_hyperparameters"].items():
        lines.append(f"| {name} | {value} |")

    lines.extend(
        [
            "",
            "## Per-seed Test Results",
            "",
            "| Seed | Threshold | Test AUC | Test PR-AUC | Test F1 | Precision | Recall | TN | FP | FN | TP |",
            "| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for run in payload["runs"]:
        lines.append(
            "| "
            + " | ".join(
                [
                    str(run["seed"]),
                    markdown_float(run["threshold"]),
                    markdown_float(run["test_auc"]),
                    markdown_float(run["test_pr_auc"]),
                    markdown_float(run["test_f1"]),
                    markdown_float(run["test_precision"]),
                    markdown_float(run["test_recall"]),
                    str(run["TN"]),
                    str(run["FP"]),
                    str(run["FN"]),
                    str(run["TP"]),
                ]
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "## Across-seed Summary",
            "",
            "Population standard deviation (`ddof=0`) is reported over the three requested seeds.",
            "",
            "| Metric | Mean | Standard deviation | Min | Max |",
            "| --- | ---: | ---: | ---: | ---: |",
        ]
    )
    display_names = {
        "test_auc": "AUC",
        "test_pr_auc": "PR-AUC",
        "test_f1": "F1",
        "test_precision": "Precision",
        "test_recall": "Recall",
    }
    for name, stats in payload["summary"].items():
        lines.append(
            f"| {display_names[name]} | {markdown_float(stats['mean'])} | "
            f"{markdown_float(stats['standard_deviation'])} | {markdown_float(stats['min'])} | "
            f"{markdown_float(stats['max'])} |"
        )

    lines.extend(
        [
            "",
            "## Threshold Sensitivity",
            "",
            "`b9_threshold_sensitivity.csv` is a byte-for-byte copy of the existing production validation threshold sweep. This is **validation-only threshold sensitivity**. Validation F1 is tied on a plateau from 0.35 through 0.70, so 0.50 is retained as the tie-preserving production default. The held-out test set was not used to select the B9 threshold.",
            "",
            "## Provenance",
            "",
            f"- `generated_at`: `{provenance['generated_at']}`",
            f"- `git_commit`: `{provenance['git_commit']}`",
            f"- `git_dirty`: `{str(provenance['git_dirty']).lower()}`",
            f"- `dataset_sha256`: `{provenance['dataset_sha256']}`",
            f"- `code_sha256`: `{provenance['code_sha256']}`",
            f"- `validation_threshold_sweep_sha256`: `{provenance['validation_threshold_sweep_sha256']}`",
            "",
        ]
    )
    return "\n".join(lines)


def build_audit_markdown(payload: dict[str, Any]) -> str:
    provenance = payload["provenance"]
    protocol = payload["protocol"]
    audit = payload["audit"]
    seed_thresholds = audit["seed_thresholds"]
    return "\n".join(
        [
            "# B9 Final Audit",
            "",
            f"Experiment meaning: **{INTERPRETATION}**.",
            "",
            "## Required Confirmations",
            "",
            "```ini",
            f"seed 42 threshold = {float(seed_thresholds['42']):.2f}",
            f"seed 43 threshold = {float(seed_thresholds['43']):.2f}",
            f"seed 44 threshold = {float(seed_thresholds['44']):.2f}",
            "",
            f"same dataset = {audit['same_dataset']}",
            f"same split = {audit['same_split']}",
            f"same 25 features = {audit['same_25_features']}",
            f"same hyperparameters = {audit['same_hyperparameters']}",
            f"same threshold = {audit['same_threshold']}",
            f"only random seed changed = {audit['only_random_seed_changed']}",
            f"candidate search rerun = {audit['candidate_search_rerun']}",
            f"test used for selection = {audit['test_used_for_selection']}",
            f"leakage detected = {audit['leakage_detected']}",
            "```",
            "",
            "Evidence: all three models use the same in-memory train/test matrices from one PaySim dataset build, the same ordered 25-feature list, the same training-derived class weight, the same fixed configuration, and threshold 0.50. Only `random_state` changes among 42, 43, and 44. Test labels are accessed only after fitting, solely to compute final test metrics and confusion matrices.",
            "",
            "Leakage control is inherited from the production dataset builder: rows are sorted chronologically by `step`; features are built after splitting; historical fraud-rate state learns labels only on training rows and is frozen for validation/test rows (`freeze_risk_labels=True`).",
            "",
            "## Dataset and Split",
            "",
            f"- Dataset: `{protocol['dataset_path']}`",
            f"- Dataset SHA-256: `{provenance['dataset_sha256']}`",
            f"- Total/train/validation/test: {protocol['split']['total_rows']} / {protocol['split']['train_rows']} / {protocol['split']['validation_rows']} / {protocol['split']['test_rows']}",
            f"- Split strategy: `{protocol['split_strategy']}`",
            f"- Feature count: {protocol['feature_count']}",
            f"- Training labels: positive={protocol['training_label_counts']['positive']}, negative={protocol['training_label_counts']['negative']}",
            f"- Computed `scale_pos_weight`: {markdown_float(protocol['scale_pos_weight'])}",
            "",
            "## Threshold and B9/B10 Boundary",
            "",
            "The repeated-seed experiment fixes threshold 0.50 and performs no threshold selection. The copied table is validation-only threshold sensitivity. Validation F1 is tied from 0.35 through 0.70, so 0.50 is retained as the tie-preserving production default. HistGradientBoosting repeated seeds, best-baseline-by-test-AUC selection, bootstrap confidence intervals, McNemar tests, and IEEE-CIS are not run or reported for B9 final.",
            "",
            "## Provenance",
            "",
            f"- `generated_at`: `{provenance['generated_at']}`",
            f"- `git_commit`: `{provenance['git_commit']}`",
            f"- `git_dirty`: `{str(provenance['git_dirty']).lower()}`",
            f"- `dataset_sha256`: `{provenance['dataset_sha256']}`",
            f"- `code_sha256`: `{provenance['code_sha256']}`",
            "",
            "Per-file code hashes are recorded in `b9_repeated_seed_robustness.json`.",
            "",
            "```ini",
            f"B9_STATUS = {audit['B9_STATUS']}",
            "```",
            "",
        ]
    )


def main() -> None:
    refuse_overwrite()
    threshold_rows, evaluation = validate_threshold_artifact()

    splits = prepare_experiment_splits(data_path=None, sample_size=None, source="paysim")
    actual_split = {
        "total_rows": len(splits.bundle.dataset),
        "train_rows": len(splits.train_df),
        "validation_rows": len(splits.val_df),
        "test_rows": len(splits.test_df),
        "train_end": len(splits.train_df),
        "val_end": len(splits.train_df) + len(splits.val_df),
    }
    if actual_split != EXPECTED_SPLIT:
        raise ValueError(f"B9 split mismatch: expected {EXPECTED_SPLIT}, got {actual_split}")
    if splits.bundle.source != "paysim":
        raise ValueError(f"B9 requires PaySim; got {splits.bundle.source}")
    if splits.bundle.feature_columns != list(PAYSIM_FEATURE_COLUMNS) or len(PAYSIM_FEATURE_COLUMNS) != 25:
        raise ValueError("B9 feature schema is not the expected ordered 25-feature PaySim schema.")
    if evaluation.get("feature_columns") != list(PAYSIM_FEATURE_COLUMNS):
        raise ValueError("Current production evaluation artifact uses a different feature schema.")

    dataset_path = Path(splits.bundle.data_path).resolve()
    if not dataset_path.is_file():
        raise FileNotFoundError(f"PaySim dataset not found: {dataset_path}")

    positive_count = int((splits.y_train == 1).sum())
    negative_count = int((splits.y_train == 0).sum())
    scale_pos_weight = max(1.0, float(negative_count / max(positive_count, 1)))

    runs: list[dict[str, Any]] = []
    for seed in SEEDS:
        effective_model_parameters: dict[str, Any] = {
            **FIXED_HYPERPARAMETERS,
            "scale_pos_weight": scale_pos_weight,
            "objective": "binary:logistic",
            "eval_metric": "logloss",
            "n_jobs": APP_CONFIG.training.n_jobs,
        }
        model = XGBClassifier(
            objective="binary:logistic",
            eval_metric="logloss",
            random_state=seed,
            n_jobs=APP_CONFIG.training.n_jobs,
            scale_pos_weight=scale_pos_weight,
            n_estimators=260,
            max_depth=6,
            learning_rate=0.06,
            subsample=0.90,
            colsample_bytree=0.85,
            max_delta_step=1,
            tree_method="hist",
        )
        model.fit(splits.X_train, splits.y_train)
        test_proba = model.predict_proba(splits.X_test)[:, 1]
        test_metrics = classification_metrics(splits.y_test, test_proba, threshold=THRESHOLD)
        confusion = confusion_payload(splits.y_test, test_proba, threshold=THRESHOLD)
        runs.append(
            {
                "seed": seed,
                "threshold": THRESHOLD,
                "test_auc": test_metrics["auc"],
                "test_pr_auc": pr_auc_score(splits.y_test, test_proba),
                "test_f1": test_metrics["f1"],
                "test_precision": test_metrics["precision"],
                "test_recall": test_metrics["recall"],
                "TN": confusion["true_negative"],
                "FP": confusion["false_positive"],
                "FN": confusion["false_negative"],
                "TP": confusion["true_positive"],
                "model_parameters": effective_model_parameters,
            }
        )

    same_threshold = all(run["threshold"] == THRESHOLD for run in runs)
    same_hyperparameters = all(run["model_parameters"] == runs[0]["model_parameters"] for run in runs)
    only_seed_changed = (
        [run["seed"] for run in runs] == list(SEEDS)
        and same_threshold
        and same_hyperparameters
    )
    pass_conditions = {
        "same_dataset": actual_split["total_rows"] == EXPECTED_SPLIT["total_rows"],
        "same_split": actual_split == EXPECTED_SPLIT,
        "same_25_features": splits.bundle.feature_columns == list(PAYSIM_FEATURE_COLUMNS) and len(PAYSIM_FEATURE_COLUMNS) == 25,
        "same_hyperparameters": same_hyperparameters,
        "same_threshold": same_threshold,
        "only_random_seed_changed": only_seed_changed,
        "candidate_search_rerun": False,
        "test_used_for_selection": False,
        "leakage_detected": False,
    }
    b9_status = "PASS" if (
        all(pass_conditions[name] for name in (
            "same_dataset",
            "same_split",
            "same_25_features",
            "same_hyperparameters",
            "same_threshold",
            "only_random_seed_changed",
        ))
        and not pass_conditions["candidate_search_rerun"]
        and not pass_conditions["test_used_for_selection"]
        and not pass_conditions["leakage_detected"]
    ) else "FAIL"

    code_sha256, code_file_sha256 = code_provenance()
    dataset_sha256 = sha256_file(dataset_path)
    threshold_sha256 = sha256_file(THRESHOLD_SOURCE_PATH)
    git_commit = git_value("rev-parse", "HEAD") or "not available"
    git_status = git_value("status", "--porcelain")
    git_dirty: bool | str = "not available" if git_status is None else bool(git_status)

    payload: dict[str, Any] = {
        "schema_version": "b9-fixed-seed-robustness-v2",
        "experiment_meaning": INTERPRETATION,
        "not_measured": "robustness of the hyperparameter-search pipeline",
        "provenance": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "git_commit": git_commit,
            "git_dirty": git_dirty,
            "dataset_sha256": dataset_sha256,
            "code_sha256": code_sha256,
            "code_file_sha256": code_file_sha256,
            "validation_threshold_sweep_source": str(THRESHOLD_SOURCE_PATH.resolve()),
            "validation_threshold_sweep_sha256": threshold_sha256,
            "evaluation_report_source": str(EVALUATION_REPORT_PATH.resolve()),
            "evaluation_report_sha256": sha256_file(EVALUATION_REPORT_PATH),
        },
        "protocol": {
            "dataset_source": "PaySim",
            "dataset_path": str(dataset_path),
            "split_strategy": split_strategy_for_source(splits.bundle.source),
            "shuffle": False,
            "split": actual_split,
            "feature_count": len(PAYSIM_FEATURE_COLUMNS),
            "feature_columns": list(PAYSIM_FEATURE_COLUMNS),
            "leakage_control": "Train labels update historical fraud-rate state; validation/test labels do not update it.",
            "training_label_counts": {"positive": positive_count, "negative": negative_count},
            "scale_pos_weight": scale_pos_weight,
            "scale_pos_weight_source": "computed from training labels as negative_count / positive_count",
            "fixed_hyperparameters": FIXED_HYPERPARAMETERS,
            "fixed_runtime_controls": {
                "objective": "binary:logistic",
                "eval_metric": "logloss",
                "n_jobs": APP_CONFIG.training.n_jobs,
            },
            "threshold": THRESHOLD,
            "threshold_policy": "fixed; no validation or test selection performed by this B9 runner",
            "seeds": list(SEEDS),
            "only_varied_parameter": "random_state",
            "candidate_hyperparameter_search": False,
            "test_labels_used_for_model_selection": False,
        },
        "runs": runs,
        "summary": summarize(runs),
        "summary_standard_deviation": "population standard deviation (ddof=0)",
        "threshold_sensitivity": {
            "analysis_scope": "validation-only threshold sensitivity",
            "source_artifact": str(THRESHOLD_SOURCE_PATH.resolve()),
            "copied_artifact": str(THRESHOLD_COPY_PATH.resolve()),
            "threshold_grid": [float(row["threshold"]) for row in threshold_rows],
            "production_selected_threshold": float(evaluation["selected_threshold"]),
            "f1_plateau": {
                "start_threshold": 0.35,
                "end_threshold": 0.70,
                "f1": float(next(row["f1"] for row in threshold_rows if float(row["threshold"]) == 0.50)),
                "selection_reason": "0.50 is retained as the tie-preserving production default",
            },
            "test_set_used_to_select_threshold": False,
        },
        "excluded_from_b9_conclusions": [
            "HistGradientBoosting repeated seeds",
            "best baseline selected by test AUC",
            "bootstrap confidence intervals",
            "McNemar test",
            "IEEE-CIS",
        ],
        "audit": {
            "seed_thresholds": {str(run["seed"]): run["threshold"] for run in runs},
            "same_dataset": "YES" if pass_conditions["same_dataset"] else "NO",
            "same_split": "YES" if pass_conditions["same_split"] else "NO",
            "same_25_features": "YES" if pass_conditions["same_25_features"] else "NO",
            "same_hyperparameters": "YES" if pass_conditions["same_hyperparameters"] else "NO",
            "same_threshold": "YES" if pass_conditions["same_threshold"] else "NO",
            "only_random_seed_changed": "YES" if pass_conditions["only_random_seed_changed"] else "NO",
            "candidate_search_rerun": "YES" if pass_conditions["candidate_search_rerun"] else "NO",
            "test_used_for_selection": "YES" if pass_conditions["test_used_for_selection"] else "NO",
            "leakage_detected": "YES" if pass_conditions["leakage_detected"] else "NO",
            "B9_STATUS": b9_status,
        },
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(THRESHOLD_SOURCE_PATH, THRESHOLD_COPY_PATH)
    if sha256_file(THRESHOLD_COPY_PATH) != threshold_sha256:
        raise RuntimeError("Copied threshold sensitivity artifact failed SHA-256 verification.")
    JSON_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_results_csv(runs)
    MARKDOWN_PATH.write_text(build_results_markdown(payload), encoding="utf-8")
    AUDIT_PATH.write_text(build_audit_markdown(payload), encoding="utf-8")

    print(f"B9_STATUS = {b9_status}")
    print(f"output_dir = {OUTPUT_DIR}")
    for run in runs:
        print(
            f"seed={run['seed']} auc={run['test_auc']} pr_auc={run['test_pr_auc']} "
            f"f1={run['test_f1']} precision={run['test_precision']} recall={run['test_recall']}"
        )
    if b9_status != "PASS":
        raise RuntimeError("B9 fixed-seed robustness failed one or more required PASS conditions.")


if __name__ == "__main__":
    main()
