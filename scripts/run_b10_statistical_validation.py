#!/usr/bin/env python3
"""Run B10 bootstrap validation using one persisted production model.

The model is loaded from disk, inference is performed once, and every
bootstrap replicate reuses that immutable held-out probability vector.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.metrics import average_precision_score, f1_score, precision_score, recall_score, roc_auc_score
from xgboost import XGBClassifier


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fraud_flow.config import PAYSIM_FEATURE_COLUMNS  # noqa: E402
from fraud_flow.training import build_dataset, split_indices  # noqa: E402


OUTPUT_DIR = ROOT / "artifacts" / "reports" / "b10_final"
CI_JSON_PATH = OUTPUT_DIR / "b10_bootstrap_ci.json"
CI_CSV_PATH = OUTPUT_DIR / "b10_bootstrap_ci.csv"
CI_MARKDOWN_PATH = OUTPUT_DIR / "b10_bootstrap_ci.md"
PROVENANCE_PATH = OUTPUT_DIR / "b10_prediction_provenance.json"
AUDIT_PATH = OUTPUT_DIR / "B10_FINAL_AUDIT.md"

MODEL_PATH = ROOT / "artifacts" / "models" / "xgboost_fraud.json"
METADATA_PATH = ROOT / "artifacts" / "models" / "model_metadata.json"
B9_PATH = ROOT / "artifacts" / "reports" / "b9_final" / "b9_repeated_seed_robustness.json"

BOOTSTRAP_ITERATIONS = 2_000
BOOTSTRAP_RANDOM_SEED = 42
THRESHOLD = 0.50
CI_INTERPRETATION = (
    "nonparametric stratified percentile bootstrap confidence intervals conditional on the fixed fitted "
    "production model and the observed held-out test-set class composition"
)

EXPECTED_SPLIT = {
    "total_rows": 460_394,
    "train_rows": 322_275,
    "validation_rows": 69_059,
    "test_rows": 69_060,
    "train_end": 322_275,
    "val_end": 391_334,
}
EXPECTED_FRAUD_ROWS = 650
EXPECTED_LEGITIMATE_ROWS = 68_410
EXPECTED_MODEL_PARAMETERS: dict[str, int | float | str] = {
    "n_estimators": 260,
    "max_depth": 6,
    "learning_rate": 0.06,
    "subsample": 0.90,
    "colsample_bytree": 0.85,
    "max_delta_step": 1,
    "tree_method": "hist",
    "scale_pos_weight": 750.2237762237762,
}
EXPECTED_METRICS = {
    "auc": 0.9983827150776428,
    "pr_auc": 0.9970017406400512,
    "f1": 0.993103448275862,
    "precision": 0.9893129770992366,
    "recall": 0.9969230769230769,
}
EXPECTED_CONFUSION = {"TN": 68_403, "FP": 7, "FN": 2, "TP": 648}
EXPECTED_B9_SUMMARY = {
    "auc": {"mean": 0.9986486156244964, "population_sd": 0.00018867515739557264},
    "pr_auc": {"mean": 0.9972164003632829, "population_sd": 0.00023828619201725262},
    "f1": {"mean": 0.9913326303746312, "population_sd": 0.0012897245272231583},
    "precision": {"mean": 0.9858078170662660, "population_sd": 0.002552503327425876},
    "recall": {"mean": 0.9969230769230769, "population_sd": 0.0},
}
CODE_FILES = (
    Path("scripts/run_b10_statistical_validation.py"),
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


def sha256_array(values: np.ndarray, dtype: str) -> tuple[str, dict[str, Any]]:
    canonical = np.ascontiguousarray(values, dtype=np.dtype(dtype))
    digest = hashlib.sha256(canonical.tobytes(order="C")).hexdigest()
    return digest, {
        "dtype": canonical.dtype.str,
        "shape": list(canonical.shape),
        "byte_order": "little-endian canonical array bytes in C order",
    }


def code_provenance() -> tuple[str, dict[str, str]]:
    aggregate = hashlib.sha256()
    file_hashes: dict[str, str] = {}
    for relative_path in CODE_FILES:
        absolute_path = ROOT / relative_path
        if not absolute_path.is_file():
            raise FileNotFoundError(f"Required code file is missing: {absolute_path}")
        file_hash = sha256_file(absolute_path)
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
    return result.stdout.strip() if result.returncode == 0 else None


def refuse_overwrite() -> None:
    targets = (CI_JSON_PATH, CI_CSV_PATH, CI_MARKDOWN_PATH, PROVENANCE_PATH, AUDIT_PATH)
    existing = [path for path in targets if path.exists()]
    if existing:
        details = "\n".join(f"- {path}" for path in existing)
        raise FileExistsError(f"B10 final output exists; refusing to overwrite:\n{details}")


def fixed_threshold_metrics(y_true: np.ndarray, probabilities: np.ndarray) -> tuple[dict[str, float], dict[str, int]]:
    predictions = (probabilities >= THRESHOLD).astype(np.int8)
    true_positive = int(np.sum((y_true == 1) & (predictions == 1)))
    true_negative = int(np.sum((y_true == 0) & (predictions == 0)))
    false_positive = int(np.sum((y_true == 0) & (predictions == 1)))
    false_negative = int(np.sum((y_true == 1) & (predictions == 0)))
    metrics = {
        "auc": float(roc_auc_score(y_true, probabilities)),
        "pr_auc": float(average_precision_score(y_true, probabilities)),
        "f1": float(f1_score(y_true, predictions, zero_division=0)),
        "precision": float(precision_score(y_true, predictions, zero_division=0)),
        "recall": float(recall_score(y_true, predictions, zero_division=0)),
    }
    confusion = {
        "TN": true_negative,
        "FP": false_positive,
        "FN": false_negative,
        "TP": true_positive,
    }
    return metrics, confusion


def metric_mismatches(actual_metrics: dict[str, float], actual_confusion: dict[str, int]) -> list[str]:
    mismatches: list[str] = []
    for name, expected in EXPECTED_METRICS.items():
        actual = actual_metrics[name]
        if not math.isclose(actual, expected, rel_tol=0.0, abs_tol=1e-12):
            mismatches.append(f"{name}: expected {expected!r}, got {actual!r}")
    for name, expected in EXPECTED_CONFUSION.items():
        actual = actual_confusion[name]
        if actual != expected:
            mismatches.append(f"{name}: expected {expected}, got {actual}")
    return mismatches


def load_and_validate_b9() -> dict[str, dict[str, float]]:
    if not B9_PATH.is_file():
        raise FileNotFoundError(f"B9 final artifact is missing: {B9_PATH}")
    payload = json.loads(B9_PATH.read_text(encoding="utf-8"))
    if payload.get("audit", {}).get("B9_STATUS") != "PASS":
        raise ValueError("B9 final artifact does not have PASS status.")
    if payload.get("protocol", {}).get("seeds") != [42, 43, 44]:
        raise ValueError("B9 seed list is not [42, 43, 44].")

    metric_mapping = {
        "auc": "test_auc",
        "pr_auc": "test_pr_auc",
        "f1": "test_f1",
        "precision": "test_precision",
        "recall": "test_recall",
    }
    recomputed: dict[str, dict[str, float]] = {}
    for output_name, b9_name in metric_mapping.items():
        values = np.asarray([run[b9_name] for run in payload["runs"]], dtype=np.float64)
        stats = {
            "mean": float(np.mean(values)),
            "population_sd": float(np.std(values, ddof=0)),
        }
        expected = EXPECTED_B9_SUMMARY[output_name]
        if stats != expected:
            raise ValueError(f"B9 {output_name} mean/SD mismatch: expected {expected}, got {stats}")
        recomputed[output_name] = stats
    return recomputed


def metric_groups(y_true: np.ndarray, probabilities: np.ndarray) -> dict[str, Any]:
    _, group_ids = np.unique(probabilities, return_inverse=True)
    positive_indices = np.flatnonzero(y_true == 1)
    negative_indices = np.flatnonzero(y_true == 0)
    return {
        "group_count": int(group_ids.max()) + 1,
        "positive_indices": positive_indices,
        "negative_indices": negative_indices,
        "positive_group_ids": group_ids[positive_indices],
        "negative_group_ids": group_ids[negative_indices],
        "positive_predicted_positive": probabilities[positive_indices] >= THRESHOLD,
        "negative_predicted_positive": probabilities[negative_indices] >= THRESHOLD,
    }


def weighted_metrics_from_class_counts(
    positive_counts: np.ndarray,
    negative_counts: np.ndarray,
    groups: dict[str, Any],
) -> dict[str, float]:
    group_count = groups["group_count"]
    positive_by_score = np.bincount(
        groups["positive_group_ids"], weights=positive_counts, minlength=group_count
    ).astype(np.float64, copy=False)
    negative_by_score = np.bincount(
        groups["negative_group_ids"], weights=negative_counts, minlength=group_count
    ).astype(np.float64, copy=False)

    total_positive = float(np.sum(positive_counts))
    total_negative = float(np.sum(negative_counts))

    cumulative_negative_below = np.cumsum(negative_by_score) - negative_by_score
    auc = float(
        np.sum(positive_by_score * (cumulative_negative_below + 0.5 * negative_by_score))
        / (total_positive * total_negative)
    )

    positive_descending = positive_by_score[::-1]
    negative_descending = negative_by_score[::-1]
    cumulative_positive = np.cumsum(positive_descending)
    cumulative_total = cumulative_positive + np.cumsum(negative_descending)
    precision_at_score = np.divide(
        cumulative_positive,
        cumulative_total,
        out=np.zeros_like(cumulative_positive),
        where=cumulative_total > 0,
    )
    pr_auc = float(np.sum((positive_descending / total_positive) * precision_at_score))

    true_positive = float(np.sum(positive_counts[groups["positive_predicted_positive"]]))
    false_positive = float(np.sum(negative_counts[groups["negative_predicted_positive"]]))
    false_negative = total_positive - true_positive
    precision = true_positive / (true_positive + false_positive) if true_positive + false_positive else 0.0
    recall = true_positive / total_positive if total_positive else 0.0
    f1 = 2.0 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "auc": auc,
        "pr_auc": pr_auc,
        "f1": f1,
        "precision": precision,
        "recall": recall,
    }


def validate_weighted_implementation(
    y_true: np.ndarray,
    probabilities: np.ndarray,
    groups: dict[str, Any],
    point_metrics: dict[str, float],
) -> None:
    positive_counts = np.ones(len(groups["positive_indices"]), dtype=np.int64)
    negative_counts = np.ones(len(groups["negative_indices"]), dtype=np.int64)
    weighted = weighted_metrics_from_class_counts(positive_counts, negative_counts, groups)
    for name, expected in point_metrics.items():
        if not math.isclose(weighted[name], expected, rel_tol=0.0, abs_tol=1e-12):
            raise RuntimeError(
                f"Weighted bootstrap metric implementation mismatch for {name}: "
                f"expected {expected!r}, got {weighted[name]!r}"
            )


def run_stratified_bootstrap(
    y_true: np.ndarray,
    probabilities: np.ndarray,
    iterations: int,
    random_seed: int,
) -> tuple[dict[str, np.ndarray], dict[str, int]]:
    groups = metric_groups(y_true, probabilities)
    validate_weighted_implementation(y_true, probabilities, groups, fixed_threshold_metrics(y_true, probabilities)[0])

    positive_indices = groups["positive_indices"]
    negative_indices = groups["negative_indices"]
    positive_count = len(positive_indices)
    negative_count = len(negative_indices)
    rng = np.random.default_rng(random_seed)
    metric_names = ("auc", "pr_auc", "f1", "precision", "recall")
    samples = {name: np.empty(iterations, dtype=np.float64) for name in metric_names}

    for iteration in range(iterations):
        positive_draw_positions = rng.integers(0, positive_count, size=positive_count)
        negative_draw_positions = rng.integers(0, negative_count, size=negative_count)
        positive_counts = np.bincount(positive_draw_positions, minlength=positive_count)
        negative_counts = np.bincount(negative_draw_positions, minlength=negative_count)
        replicate = weighted_metrics_from_class_counts(positive_counts, negative_counts, groups)

        if iteration == 0:
            sampled_indices = np.concatenate(
                (positive_indices[positive_draw_positions], negative_indices[negative_draw_positions])
            )
            direct, _ = fixed_threshold_metrics(y_true[sampled_indices], probabilities[sampled_indices])
            for name in metric_names:
                if not math.isclose(replicate[name], direct[name], rel_tol=0.0, abs_tol=1e-12):
                    raise RuntimeError(
                        f"First-replicate equivalence check failed for {name}: "
                        f"weighted={replicate[name]!r}, direct={direct[name]!r}"
                    )

        if int(np.sum(positive_counts)) != positive_count or int(np.sum(negative_counts)) != negative_count:
            raise RuntimeError("A stratified bootstrap replicate changed its class counts.")
        for name in metric_names:
            samples[name][iteration] = replicate[name]

        if (iteration + 1) % 250 == 0:
            print(f"bootstrap_progress = {iteration + 1}/{iterations}", flush=True)

    class_counts = {
        "fraud_per_replicate": positive_count,
        "legitimate_per_replicate": negative_count,
        "total_per_replicate": positive_count + negative_count,
    }
    return samples, class_counts


def summarize_bootstrap(
    point_metrics: dict[str, float],
    samples: dict[str, np.ndarray],
) -> dict[str, dict[str, float]]:
    summary: dict[str, dict[str, float]] = {}
    for name, values in samples.items():
        summary[name] = {
            "point_estimate": point_metrics[name],
            "bootstrap_mean": float(np.mean(values)),
            "bootstrap_population_sd": float(np.std(values, ddof=0)),
            "ci95_low": float(np.quantile(values, 0.025)),
            "ci95_high": float(np.quantile(values, 0.975)),
        }
    return summary


def write_ci_csv(summary: dict[str, dict[str, float]]) -> None:
    fields = (
        "metric",
        "point_estimate",
        "bootstrap_mean",
        "bootstrap_population_sd",
        "ci95_low",
        "ci95_high",
    )
    with CI_CSV_PATH.open("x", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for name, values in summary.items():
            writer.writerow({"metric": name, **values})


def build_ci_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# B10 Final Statistical Validation",
        "",
        f"CI interpretation: **{CI_INTERPRETATION}**.",
        "",
        "The intervals do not quantify uncertainty of the training or hyperparameter-selection pipeline.",
        "",
        "## Fixed Production Test Result and Bootstrap CI",
        "",
        "| Metric | Point estimate | Bootstrap mean | Population SD | 2.5th percentile | 97.5th percentile |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    display_names = {"auc": "AUC", "pr_auc": "PR-AUC", "f1": "F1", "precision": "Precision", "recall": "Recall"}
    for name, values in payload["metrics"].items():
        lines.append(
            f"| {display_names[name]} | {values['point_estimate']!r} | {values['bootstrap_mean']!r} | "
            f"{values['bootstrap_population_sd']!r} | {values['ci95_low']!r} | {values['ci95_high']!r} |"
        )

    lines.extend(
        [
            "",
            "## B9 Across-seed Results (kept separate)",
            "",
            "B9 mean+/-SD is across-seed stochastic variation. B10 bootstrap CI is held-out test-sample uncertainty conditional on one fitted model. These uncertainty sources are not pooled.",
            "",
            "| Metric | B9 mean | B9 population SD |",
            "| --- | ---: | ---: |",
        ]
    )
    for name, values in payload["b9_across_seed_mean_population_sd"].items():
        lines.append(f"| {display_names[name]} | {values['mean']!r} | {values['population_sd']!r} |")

    lines.extend(
        [
            "",
            "## Protocol",
            "",
            f"- Bootstrap: {payload['bootstrap']['type']}",
            f"- Iterations: {payload['bootstrap']['iterations']}",
            f"- Random seed: {payload['bootstrap']['random_seed']}",
            f"- Per replicate: fraud={payload['bootstrap']['class_counts_per_replicate']['fraud_per_replicate']}, legitimate={payload['bootstrap']['class_counts_per_replicate']['legitimate_per_replicate']}, total={payload['bootstrap']['class_counts_per_replicate']['total_per_replicate']}",
            "- CI: empirical percentile, 2.5th and 97.5th percentiles; no normal approximation",
            "- Threshold: 0.50 for F1, precision, and recall",
            "- Model inference calls: 1",
            "- Model refits: 0",
            "- McNemar final use: NO",
            "",
        ]
    )
    return "\n".join(lines)


def build_audit_markdown(provenance: dict[str, Any], payload: dict[str, Any], status: str) -> str:
    return "\n".join(
        [
            "# B10 Final Audit",
            "",
            "```ini",
            "production model loaded = YES",
            "model retrained = NO",
            "test probability vector fixed = YES",
            "production metrics reproduced = YES",
            f"test rows = {provenance['test_rows']}",
            f"fraud rows = {provenance['fraud_rows']}",
            f"legitimate rows = {provenance['legitimate_rows']}",
            f"threshold = {provenance['threshold']:.2f}",
            "bootstrap type = stratified nonparametric bootstrap",
            f"bootstrap iterations = {payload['bootstrap']['iterations']}",
            f"bootstrap random seed = {payload['bootstrap']['random_seed']}",
            "model refit inside bootstrap = NO",
            "percentile CI = YES",
            "B9 SD kept separate from bootstrap uncertainty = YES",
            "McNemar final use = NO",
            "```",
            "",
            "The production model was loaded from the persisted XGBoost JSON. Test probabilities were generated once, hashed, and then held fixed. Each bootstrap replicate resampled 650 fraud and 68,410 legitimate test indices with replacement and applied identical multiplicities to labels and probabilities.",
            "",
            f"CI interpretation: **{CI_INTERPRETATION}**.",
            "",
            "B9 mean+/-SD remains across-seed stochastic variation. B10 bootstrap intervals remain held-out test-sample uncertainty conditional on one fitted model. They are not combined.",
            "",
            "No baseline model, IEEE-CIS model, training pipeline, candidate search, latency benchmark, McNemar test, or p-value was run.",
            "",
            "```ini",
            f"B10_STATUS = {status}",
            "```",
            "",
        ]
    )


def write_failure_audit(reasons: list[str], provenance: dict[str, Any] | None = None) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    if provenance is not None and not PROVENANCE_PATH.exists():
        PROVENANCE_PATH.write_text(json.dumps(provenance, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    text = "\n".join(
        [
            "# B10 Final Audit",
            "",
            "Production metric reproduction failed; bootstrap was not started.",
            "",
            *[f"- {reason}" for reason in reasons],
            "",
            "```ini",
            "B10_STATUS = FAIL",
            "```",
            "",
        ]
    )
    AUDIT_PATH.write_text(text, encoding="utf-8")


def main() -> None:
    refuse_overwrite()
    for required_path in (MODEL_PATH, METADATA_PATH, B9_PATH):
        if not required_path.is_file():
            raise FileNotFoundError(f"Required B10 input is missing: {required_path}")

    metadata = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
    if metadata.get("source") != "paysim":
        raise ValueError("Production metadata is not for PaySim.")
    if metadata.get("feature_columns") != list(PAYSIM_FEATURE_COLUMNS) or len(PAYSIM_FEATURE_COLUMNS) != 25:
        raise ValueError("Production metadata does not contain the expected ordered 25-feature schema.")
    if float(metadata.get("selected_threshold")) != THRESHOLD:
        raise ValueError("Production metadata threshold is not 0.50.")
    if metadata.get("split") != {key: EXPECTED_SPLIT[key] for key in ("total_rows", "train_rows", "validation_rows", "test_rows")}:
        raise ValueError("Production metadata split does not match B10 requirements.")

    metadata_parameters = {
        **metadata["selected_params"],
        "max_delta_step": metadata["training_controls"]["max_delta_step"],
        "tree_method": "hist",
        "scale_pos_weight": metadata["class_balance"]["scale_pos_weight"],
    }
    if metadata_parameters != EXPECTED_MODEL_PARAMETERS:
        raise ValueError(f"Production parameter mismatch: {metadata_parameters}")

    b9_summary = load_and_validate_b9()
    bundle = build_dataset(data_path=None, sample_size=None, source="paysim")
    train_end, val_end = split_indices(len(bundle.dataset))
    actual_split = {
        "total_rows": len(bundle.dataset),
        "train_rows": train_end,
        "validation_rows": val_end - train_end,
        "test_rows": len(bundle.dataset) - val_end,
        "train_end": train_end,
        "val_end": val_end,
    }
    if actual_split != EXPECTED_SPLIT:
        raise ValueError(f"Reconstructed split mismatch: expected {EXPECTED_SPLIT}, got {actual_split}")
    if bundle.feature_columns != list(PAYSIM_FEATURE_COLUMNS):
        raise ValueError("Reconstructed feature order differs from production metadata.")

    test_frame = bundle.dataset.iloc[val_end:].copy()
    x_test = test_frame[bundle.feature_columns].astype(np.float32)
    y_test = test_frame["isFraud"].to_numpy(dtype=np.int8, copy=True)
    fraud_rows = int(np.sum(y_test == 1))
    legitimate_rows = int(np.sum(y_test == 0))
    if fraud_rows != EXPECTED_FRAUD_ROWS or legitimate_rows != EXPECTED_LEGITIMATE_ROWS:
        raise ValueError(
            f"Test class-count mismatch: fraud={fraud_rows}, legitimate={legitimate_rows}"
        )

    production_model = XGBClassifier()
    production_model.load_model(MODEL_PATH)
    if production_model.get_booster().num_features() != 25:
        raise ValueError("Loaded production model does not have 25 input features.")
    if production_model.get_booster().num_boosted_rounds() != 260:
        raise ValueError("Loaded production model does not have 260 boosted rounds.")

    test_probability_vector = np.asarray(production_model.predict_proba(x_test)[:, 1], dtype=np.float32)
    point_metrics, confusion = fixed_threshold_metrics(y_test, test_probability_vector)
    mismatches = metric_mismatches(point_metrics, confusion)

    dataset_path = Path(bundle.data_path).resolve()
    y_test_sha256, y_test_encoding = sha256_array(y_test, "<i1")
    probability_sha256, probability_encoding = sha256_array(test_probability_vector, "<f4")
    code_sha256, code_file_sha256 = code_provenance()
    git_status = git_value("status", "--porcelain")
    provenance: dict[str, Any] = {
        "schema_version": "b10-fixed-production-predictions-v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": git_value("rev-parse", "HEAD") or "not available",
        "git_dirty": "not available" if git_status is None else bool(git_status),
        "dataset_path": str(dataset_path),
        "dataset_sha256": sha256_file(dataset_path),
        "model_path": str(MODEL_PATH.resolve()),
        "model_sha256": sha256_file(MODEL_PATH),
        "metadata_path": str(METADATA_PATH.resolve()),
        "metadata_sha256": sha256_file(METADATA_PATH),
        "code_sha256": code_sha256,
        "code_file_sha256": code_file_sha256,
        "y_test_sha256": y_test_sha256,
        "y_test_hash_encoding": y_test_encoding,
        "test_probability_vector_sha256": probability_sha256,
        "test_probability_vector_hash_encoding": probability_encoding,
        "test_rows": len(y_test),
        "fraud_rows": fraud_rows,
        "legitimate_rows": legitimate_rows,
        "feature_count": len(bundle.feature_columns),
        "feature_columns": bundle.feature_columns,
        "threshold": THRESHOLD,
        "model_parameters": metadata_parameters,
        "model_runtime": {
            "objective": production_model.get_xgb_params().get("objective", "binary:logistic"),
            "num_features": production_model.get_booster().num_features(),
            "num_boosted_rounds": production_model.get_booster().num_boosted_rounds(),
        },
        "split_strategy": "chronological_by_step_after_TRANSFER_CASH_OUT_filter",
        "shuffle": False,
        "split": actual_split,
        "leakage_control": (
            "Training rows update historical activity and fraud-rate state. Validation/test rows use the "
            "state frozen after training and do not contribute labels during feature construction."
        ),
        "prediction_inference_calls": 1,
        "test_probability_vector_fixed_before_bootstrap": True,
        "production_metrics": point_metrics,
        "confusion_matrix": confusion,
        "production_metrics_reproduced": not mismatches,
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    PROVENANCE_PATH.write_text(json.dumps(provenance, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if mismatches:
        write_failure_audit(mismatches, provenance)
        print("B10_STATUS = FAIL")
        for mismatch in mismatches:
            print(f"reason = {mismatch}")
        return

    print("production_metrics_reproduced = YES", flush=True)
    print(f"test_probability_vector_sha256 = {probability_sha256}", flush=True)
    bootstrap_samples, replicate_class_counts = run_stratified_bootstrap(
        y_test,
        test_probability_vector,
        iterations=BOOTSTRAP_ITERATIONS,
        random_seed=BOOTSTRAP_RANDOM_SEED,
    )
    bootstrap_summary = summarize_bootstrap(point_metrics, bootstrap_samples)

    interval_checks = {
        name: (
            0.0 <= values["ci95_low"] <= values["point_estimate"] <= values["ci95_high"] <= 1.0
        )
        for name, values in bootstrap_summary.items()
    }
    b10_status = "PASS" if all(interval_checks.values()) else "FAIL"

    payload: dict[str, Any] = {
        "schema_version": "b10-stratified-bootstrap-v1",
        "B10_STATUS": b10_status,
        "ci_interpretation": CI_INTERPRETATION,
        "training_pipeline_uncertainty": False,
        "prediction_provenance_path": str(PROVENANCE_PATH.resolve()),
        "prediction_provenance_sha256": sha256_file(PROVENANCE_PATH),
        "bootstrap": {
            "type": "stratified nonparametric bootstrap",
            "iterations": BOOTSTRAP_ITERATIONS,
            "random_seed": BOOTSTRAP_RANDOM_SEED,
            "sampling": "within-class sampling with replacement",
            "class_counts_per_replicate": replicate_class_counts,
            "probability_vector_regenerated_per_replicate": False,
            "model_refit_inside_bootstrap": False,
            "ci_method": "percentile bootstrap",
            "ci_percentiles": [2.5, 97.5],
            "quantile_interpolation": "NumPy default linear method",
            "normal_approximation": False,
        },
        "metrics": bootstrap_summary,
        "interval_checks": {
            name: {
                "point_estimate_inside_ci": passed,
                "ci_inside_unit_interval": (
                    0.0 <= bootstrap_summary[name]["ci95_low"] <= bootstrap_summary[name]["ci95_high"] <= 1.0
                ),
            }
            for name, passed in interval_checks.items()
        },
        "b9_across_seed_mean_population_sd": b9_summary,
        "uncertainty_separation": {
            "B9": "across-seed stochastic variation",
            "B10": "held-out test-sample uncertainty conditional on one fitted model",
            "pooled": False,
        },
        "MCNEMAR_FINAL_USE": "NO",
        "p_values_created": False,
    }

    CI_JSON_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_ci_csv(bootstrap_summary)
    CI_MARKDOWN_PATH.write_text(build_ci_markdown(payload), encoding="utf-8")
    AUDIT_PATH.write_text(build_audit_markdown(provenance, payload, b10_status), encoding="utf-8")

    print(f"B10_STATUS = {b10_status}")
    print(f"bootstrap_iterations = {BOOTSTRAP_ITERATIONS}")
    print("bootstrap_type = stratified nonparametric bootstrap")
    print("model_retrained = NO")
    print("McNemar_final_use = NO")
    if b10_status != "PASS":
        raise RuntimeError("One or more B10 interval checks failed.")


if __name__ == "__main__":
    main()
