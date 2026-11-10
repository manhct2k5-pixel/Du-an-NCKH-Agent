#!/usr/bin/env python3
"""B11 fixed-fit timing and component-level local latency benchmark."""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.metadata
import json
import os
import platform
import shlex
import shutil
import statistics
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import psutil
import shap
from xgboost import XGBClassifier


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fraud_flow.anomaly import AnomalySidecar  # noqa: E402
from fraud_flow.calibration import calibrate_operational_score, route_score  # noqa: E402
from fraud_flow.config import APP_CONFIG, PAYSIM_FEATURE_COLUMNS  # noqa: E402
from fraud_flow.report_paths import existing_report_path  # noqa: E402
from fraud_flow.feature_store import FeatureStore  # noqa: E402
from fraud_flow.features import assemble_feature_row, event_from_row  # noqa: E402
from fraud_flow.research import replay_medium_agent  # noqa: E402
from fraud_flow.schema import ModelPrediction  # noqa: E402
from fraud_flow.training import build_dataset, split_indices  # noqa: E402


OUTPUT_DIR = ROOT / "artifacts" / "reports" / "b11_final"
TRAINING_PATH = OUTPUT_DIR / "b11_training_time.json"
COMPONENT_JSON_PATH = OUTPUT_DIR / "b11_latency_components.json"
COMPONENT_CSV_PATH = OUTPUT_DIR / "b11_latency_components.csv"
ROUTE_PATH = OUTPUT_DIR / "b11_route_latency.json"
ENVIRONMENT_PATH = OUTPUT_DIR / "b11_environment.json"
SUMMARY_PATH = OUTPUT_DIR / "b11_efficiency_summary.md"
AUDIT_PATH = OUTPUT_DIR / "B11_FINAL_AUDIT.md"

MODEL_PATH = ROOT / "artifacts" / "models" / "xgboost_fraud.json"
METADATA_PATH = ROOT / "artifacts" / "models" / "model_metadata.json"
ANOMALY_PATH = ROOT / "artifacts" / "models" / "anomaly_sidecar.joblib"
EVALUATION_PATH = ROOT / "artifacts" / "reports" / "evaluation_report.json"
OLD_BENCHMARK_PATH = existing_report_path(ROOT / "artifacts" / "reports" / "latency_report.json")
OLD_BENCHMARK_CODE_PATH = ROOT / "scripts" / "benchmark_latency.py"

EXPECTED_SPLIT = {
    "total_rows": 460_394,
    "train_rows": 322_275,
    "validation_rows": 69_059,
    "test_rows": 69_060,
    "train_end": 322_275,
    "val_end": 391_334,
}
FIXED_PARAMETERS: dict[str, int | float | str] = {
    "n_estimators": 260,
    "max_depth": 6,
    "learning_rate": 0.06,
    "subsample": 0.90,
    "colsample_bytree": 0.85,
    "max_delta_step": 1,
    "tree_method": "hist",
    "random_state": 42,
    "n_jobs": 4,
}
COMPONENTS = (
    "feature_store_lookup_ms",
    "feature_assembly_ms",
    "xgboost_predict_proba_ms",
    "shap_explanation_ms",
    "calibration_and_routing_ms",
    "anomaly_sidecar_ms",
    "model_service_total_ms",
    "deterministic_medium_investigation_ms",
    "activity_state_update_ms",
    "local_end_to_end_ms",
)
TIMING_BOUNDARY = (
    "For each measured transaction, local_end_to_end_ms starts immediately before the in-memory "
    "FeatureStore lookup and stops immediately after activity-only state update. It includes feature lookup, "
    "feature assembly, one-row DataFrame construction, raw XGBoost predict_proba, TreeSHAP explanation, "
    "calibration/routing, anomaly-sidecar scoring, deterministic offline investigation replay for medium "
    "routes, and observe_activity. Event parsing, dataset loading, model/explainer loading, training, external "
    "LLM/API calls, Redis, network, logging, and concurrency are outside this boundary."
)
CODE_FILES = (
    Path("scripts/run_b11_efficiency.py"),
    Path("scripts/benchmark_latency.py"),
    Path("fraud_flow/pipeline.py"),
    Path("fraud_flow/features.py"),
    Path("fraud_flow/feature_store.py"),
    Path("fraud_flow/research.py"),
    Path("fraud_flow/anomaly.py"),
    Path("fraud_flow/calibration.py"),
    Path("fraud_flow/config.py"),
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def code_provenance() -> tuple[str, dict[str, str]]:
    aggregate = hashlib.sha256()
    hashes: dict[str, str] = {}
    for relative_path in CODE_FILES:
        path = ROOT / relative_path
        if not path.is_file():
            raise FileNotFoundError(f"Required benchmark code is missing: {path}")
        digest = sha256_file(path)
        relative_text = relative_path.as_posix()
        hashes[relative_text] = digest
        aggregate.update(relative_text.encode("utf-8"))
        aggregate.update(b"\0")
        aggregate.update(digest.encode("ascii"))
        aggregate.update(b"\n")
    return aggregate.hexdigest(), hashes


def git_value(*args: str) -> str | None:
    result = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def package_version(name: str) -> str:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return "not installed"


def gpu_environment() -> dict[str, Any]:
    executable = shutil.which("nvidia-smi")
    if executable is None:
        return {"available": False, "devices": [], "detection": "nvidia-smi not found"}
    try:
        result = subprocess.run(
            [executable, "--query-gpu=name", "--format=csv,noheader"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"available": False, "devices": [], "detection": f"nvidia-smi failed: {type(exc).__name__}"}
    devices = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    return {
        "available": result.returncode == 0 and bool(devices),
        "devices": devices,
        "detection": "nvidia-smi query",
    }


def cpu_model() -> str:
    cpuinfo = Path("/proc/cpuinfo")
    if cpuinfo.is_file():
        for line in cpuinfo.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.lower().startswith("model name") and ":" in line:
                return line.split(":", 1)[1].strip()
    return platform.processor() or "not available"


def collect_environment() -> dict[str, Any]:
    virtual_memory = psutil.virtual_memory()
    return {
        "cpu_model": cpu_model(),
        "physical_cores": psutil.cpu_count(logical=False),
        "logical_cores": psutil.cpu_count(logical=True),
        "ram_total_bytes": int(virtual_memory.total),
        "ram_total_gib": float(virtual_memory.total / (1024**3)),
        "operating_system": platform.platform(),
        "python_version": platform.python_version(),
        "python_executable": sys.executable,
        "packages": {
            "xgboost": package_version("xgboost"),
            "scikit-learn": package_version("scikit-learn"),
            "pandas": package_version("pandas"),
            "numpy": package_version("numpy"),
            "shap": package_version("shap"),
        },
        "gpu": gpu_environment(),
        "xgboost_benchmark_device": "CPU; tree_method=hist and no device=cuda parameter",
        "redis_mode": "not used; in-memory FeatureStore; Redis/network overhead excluded",
        "external_llm_backend_configured": bool(os.getenv("OPENAI_API_KEY")),
        "external_llm_react_latency": "NOT MEASURED",
        "external_llm_reason": "External network/API execution was excluded to avoid dependency and cost.",
        "clock": "time.perf_counter",
    }


def refuse_overwrite() -> None:
    targets = (
        TRAINING_PATH,
        COMPONENT_JSON_PATH,
        COMPONENT_CSV_PATH,
        ROUTE_PATH,
        ENVIRONMENT_PATH,
        SUMMARY_PATH,
        AUDIT_PATH,
    )
    existing = [path for path in targets if path.exists()]
    if existing:
        details = "\n".join(f"- {path}" for path in existing)
        raise FileExistsError(f"B11 final output exists; refusing to overwrite:\n{details}")


def latency_stats(values: list[float], *, throughput: bool = False) -> dict[str, Any]:
    if not values:
        return {
            "n": 0,
            "mean_ms": None,
            "p50_ms": None,
            "p95_ms": None,
            "p99_ms": None,
            "max_ms": None,
            **({"throughput_tx_per_second": None} if throughput else {}),
        }
    array = np.asarray(values, dtype=np.float64)
    mean = float(np.mean(array))
    payload: dict[str, Any] = {
        "n": len(values),
        "mean_ms": mean,
        "p50_ms": float(np.quantile(array, 0.50)),
        "p95_ms": float(np.quantile(array, 0.95)),
        "p99_ms": float(np.quantile(array, 0.99)),
        "max_ms": float(np.max(array)),
    }
    if throughput:
        payload["throughput_tx_per_second"] = 1000.0 / mean if mean > 0 else None
        payload["throughput_label"] = "sequential single-process local throughput"
    return payload


def training_time_stats(values: list[float]) -> dict[str, Any]:
    return {
        "individual_seconds": values,
        "mean_seconds": float(statistics.mean(values)),
        "median_seconds": float(statistics.median(values)),
        "min_seconds": float(min(values)),
        "max_seconds": float(max(values)),
    }


def benchmark_fixed_training(
    x_train: pd.DataFrame,
    y_train: pd.Series,
    repetitions: int,
    scale_pos_weight: float,
) -> list[float]:
    times: list[float] = []
    for repetition in range(repetitions):
        temporary_model = XGBClassifier(
            objective="binary:logistic",
            eval_metric="logloss",
            n_estimators=260,
            max_depth=6,
            learning_rate=0.06,
            subsample=0.90,
            colsample_bytree=0.85,
            max_delta_step=1,
            tree_method="hist",
            random_state=42,
            n_jobs=4,
            scale_pos_weight=scale_pos_weight,
        )
        started = time.perf_counter()
        temporary_model.fit(x_train, y_train)
        elapsed = time.perf_counter() - started
        times.append(float(elapsed))
        print(f"training_repetition_{repetition + 1}_seconds = {elapsed!r}", flush=True)
        del temporary_model
    return times


def top_shap_explanation(
    explainer: shap.TreeExplainer,
    vector: pd.DataFrame,
    feature_columns: list[str],
) -> list[dict[str, float | str]]:
    shap_values = explainer.shap_values(vector)[0]
    items: list[dict[str, float | str]] = []
    for feature_name, impact in zip(feature_columns, shap_values, strict=True):
        items.append({"feature": feature_name, "impact": float(impact), "weight": abs(float(impact))})
    top_items = sorted(items, key=lambda item: item["weight"], reverse=True)[:3]
    max_weight = max((float(item["weight"]) for item in top_items), default=1.0) or 1.0
    for item in top_items:
        item["weight"] = round(float(item["weight"]) / max_weight, 4)
    return top_items


def score_event(
    *,
    event: Any,
    store: FeatureStore,
    model: XGBClassifier,
    explainer: shap.TreeExplainer,
    anomaly_sidecar: AnomalySidecar,
    metadata: dict[str, Any],
    timed: bool,
) -> tuple[str, dict[str, float]]:
    durations: dict[str, float] = {}
    local_started = time.perf_counter()

    started = time.perf_counter()
    lookup = store.lookup(event)
    if timed:
        durations["feature_store_lookup_ms"] = (time.perf_counter() - started) * 1000.0

    started = time.perf_counter()
    feature_row = assemble_feature_row(event, lookup)
    if timed:
        durations["feature_assembly_ms"] = (time.perf_counter() - started) * 1000.0

    model_service_started = time.perf_counter()
    vector = pd.DataFrame([feature_row], columns=PAYSIM_FEATURE_COLUMNS)

    started = time.perf_counter()
    raw_probability = float(model.predict_proba(vector)[0, 1])
    if timed:
        durations["xgboost_predict_proba_ms"] = (time.perf_counter() - started) * 1000.0

    started = time.perf_counter()
    explanation = top_shap_explanation(explainer, vector, list(PAYSIM_FEATURE_COLUMNS))
    if timed:
        durations["shap_explanation_ms"] = (time.perf_counter() - started) * 1000.0

    started = time.perf_counter()
    score = calibrate_operational_score(raw_probability, metadata["routing_calibration"])
    route = route_score(
        score,
        low_threshold=float(metadata["routing_thresholds"]["low"]),
        high_threshold=float(metadata["routing_thresholds"]["high"]),
    )
    if timed:
        durations["calibration_and_routing_ms"] = (time.perf_counter() - started) * 1000.0

    started = time.perf_counter()
    anomaly_score = float(anomaly_sidecar.score(feature_row))
    anomaly_flag = anomaly_score >= float(metadata["anomaly_flag_threshold"])
    if timed:
        durations["anomaly_sidecar_ms"] = (time.perf_counter() - started) * 1000.0
        durations["model_service_total_ms"] = (time.perf_counter() - model_service_started) * 1000.0

    prediction = ModelPrediction(
        score=score,
        raw_probability=raw_probability,
        route=route,
        explanation=explanation,
        latency_ms=(time.perf_counter() - model_service_started) * 1000.0,
        anomaly_score=round(anomaly_score, 6),
        anomaly_flag=anomaly_flag,
    )

    if route == "medium":
        started = time.perf_counter()
        replay_medium_agent(store, event, lookup, prediction)
        if timed:
            durations["deterministic_medium_investigation_ms"] = (time.perf_counter() - started) * 1000.0

    started = time.perf_counter()
    store.observe_activity(event)
    if timed:
        durations["activity_state_update_ms"] = (time.perf_counter() - started) * 1000.0
        durations["local_end_to_end_ms"] = (time.perf_counter() - local_started) * 1000.0

    return route, durations


def build_history_store(dataset: pd.DataFrame, train_end: int, val_end: int) -> FeatureStore:
    store = FeatureStore()
    train_frame = dataset.iloc[:train_end]
    validation_frame = dataset.iloc[train_end:val_end]
    for row in train_frame.itertuples(index=False):
        event = event_from_row(row, source="paysim")
        store.observe(event, event.is_fraud)
    for row in validation_frame.itertuples(index=False):
        event = event_from_row(row, source="paysim")
        lookup = store.lookup(event)
        assemble_feature_row(event, lookup)
        store.observe_activity(event)
    return store


def benchmark_latency(
    *,
    dataset: pd.DataFrame,
    train_end: int,
    val_end: int,
    metadata: dict[str, Any],
    warmup_count: int,
    min_measured: int,
    min_low: int,
    min_medium: int,
    min_high: int,
) -> dict[str, Any]:
    model = XGBClassifier()
    model.load_model(MODEL_PATH)
    anomaly_sidecar = AnomalySidecar.load(ANOMALY_PATH)
    explainer = shap.TreeExplainer(model)
    store = build_history_store(dataset, train_end, val_end)
    test_frame = dataset.iloc[val_end:].reset_index(drop=True)

    if warmup_count < 100 or min_measured < 1000:
        raise ValueError("B11 requires warmup >= 100 and measured transactions >= 1000.")
    if warmup_count + min_measured > len(test_frame):
        raise ValueError("Warmup plus minimum measured count exceeds the held-out test set.")

    print(f"latency_warmup_transactions = {warmup_count}", flush=True)
    for row in test_frame.iloc[:warmup_count].itertuples(index=False):
        event = event_from_row(row, source="paysim")
        score_event(
            event=event,
            store=store,
            model=model,
            explainer=explainer,
            anomaly_sidecar=anomaly_sidecar,
            metadata=metadata,
            timed=False,
        )

    overall_values: dict[str, list[float]] = {component: [] for component in COMPONENTS}
    route_values: dict[str, dict[str, list[float]]] = {
        route: {component: [] for component in COMPONENTS}
        for route in ("low", "medium", "high")
    }
    route_counts: Counter[str] = Counter()

    measured_frame = test_frame.iloc[warmup_count:]
    for measured_index, row in enumerate(measured_frame.itertuples(index=False), start=1):
        event = event_from_row(row, source="paysim")
        route, durations = score_event(
            event=event,
            store=store,
            model=model,
            explainer=explainer,
            anomaly_sidecar=anomaly_sidecar,
            metadata=metadata,
            timed=True,
        )
        route_counts[route] += 1
        for component, duration in durations.items():
            overall_values[component].append(duration)
            route_values[route][component].append(duration)

        enough = (
            measured_index >= min_measured
            and route_counts["low"] >= min_low
            and route_counts["medium"] >= min_medium
            and route_counts["high"] >= min_high
        )
        if enough:
            break

    measured_count = int(sum(route_counts.values()))
    overall_stats = {
        component: latency_stats(values, throughput=component == "local_end_to_end_ms")
        for component, values in overall_values.items()
    }
    by_route_stats = {
        route: {
            component: latency_stats(values, throughput=component == "local_end_to_end_ms")
            for component, values in components.items()
        }
        for route, components in route_values.items()
    }
    return {
        "warmup_count": warmup_count,
        "measured_count": measured_count,
        "route_counts": {route: int(route_counts[route]) for route in ("low", "medium", "high")},
        "route_targets": {
            "minimum_total": min_measured,
            "minimum_low": min_low,
            "minimum_medium": min_medium,
            "minimum_high": min_high,
        },
        "test_rows_consumed_including_warmup": warmup_count + measured_count,
        "chronological_no_shuffle": True,
        "overall": overall_stats,
        "by_route": by_route_stats,
        "timing_boundary": TIMING_BOUNDARY,
        "external_llm_react_latency": "NOT MEASURED",
        "redis_network_overhead": "excluded; in-memory FeatureStore",
        "throughput_interpretation": "sequential single-process local throughput; not production capacity",
    }


def audit_old_benchmark() -> dict[str, Any]:
    old = json.loads(OLD_BENCHMARK_PATH.read_text(encoding="utf-8"))
    source = OLD_BENCHMARK_CODE_PATH.read_text(encoding="utf-8")
    measured_loop = source[source.index("for ev in benchmark_events:"):source.index("# --- Report ---")]
    lookup_position = measured_loop.index("lookup = store.lookup(ev)")
    assembly_position = measured_loop.index("feature_row = assemble_feature_row(ev, lookup)")
    timer_position = measured_loop.index("t0 = time.perf_counter()")
    timing_boundary_verified = lookup_position < assembly_position < timer_position

    warmup_loop = source[source.index("for ev in events[:warmup]:"):source.index("# --- Benchmark ---")]
    warmup_advances_state = "store.observe_activity(ev)" in warmup_loop
    old_numbers_verified = (
        old["config"]["n_benchmark"] == 1000
        and old["route_distribution"] == {"low": 887, "medium": 113, "high": 0}
        and round(float(old["overall"]["mean_ms"]), 2) == 35.72
        and round(float(old["overall"]["p50_ms"]), 2) == 35.80
        and round(float(old["overall"]["p95_ms"]), 2) == 44.46
        and round(float(old["overall"]["p99_ms"]), 2) == 51.55
    )
    reusable = False
    return {
        "OLD_BENCHMARK_REUSABLE": "YES" if reusable else "NO",
        "old_numbers_verified": old_numbers_verified,
        "old_report_values": {
            "sample": old["config"]["n_benchmark"],
            "mean_ms": old["overall"]["mean_ms"],
            "p50_ms": old["overall"]["p50_ms"],
            "p95_ms": old["overall"]["p95_ms"],
            "p99_ms": old["overall"]["p99_ms"],
            "route_distribution": old["route_distribution"],
        },
        "timing_boundary_verified": timing_boundary_verified,
        "timer_starts_after_lookup_and_assembly": timing_boundary_verified,
        "feature_store_lookup_included": False,
        "feature_assembly_included": False,
        "activity_state_update_included": False,
        "warmup_advances_feature_store_state": warmup_advances_state,
        "reason": (
            "The old timer begins after lookup and feature assembly, warmup events do not advance FeatureStore "
            "state, and the 1,000-event sample contains no high route. It is not reusable as local end-to-end latency."
        ),
    }


def write_component_csv(latency: dict[str, Any]) -> None:
    fields = ("scope", "route", "component", "n", "mean_ms", "p50_ms", "p95_ms", "p99_ms", "max_ms", "throughput_tx_per_second")
    with COMPONENT_CSV_PATH.open("x", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for component, stats in latency["overall"].items():
            writer.writerow(
                {
                    "scope": "overall",
                    "route": "all",
                    "component": component,
                    **{name: stats.get(name) for name in fields if name not in {"scope", "route", "component"}},
                }
            )
        for route, components in latency["by_route"].items():
            for component, stats in components.items():
                writer.writerow(
                    {
                        "scope": "route",
                        "route": route,
                        "component": component,
                        **{name: stats.get(name) for name in fields if name not in {"scope", "route", "component"}},
                    }
                )


def build_summary_markdown(
    training: dict[str, Any],
    latency: dict[str, Any],
    environment: dict[str, Any],
    old_audit: dict[str, Any],
) -> str:
    lines = [
        "# B11 Computational Efficiency and Deployment Feasibility",
        "",
        "## Environment",
        "",
        f"- CPU: `{environment['cpu_model']}`",
        f"- Cores: physical={environment['physical_cores']}, logical={environment['logical_cores']}",
        f"- RAM: {environment['ram_total_gib']!r} GiB",
        f"- OS: `{environment['operating_system']}`",
        f"- Python: `{environment['python_version']}`",
        f"- XGBoost: `{environment['packages']['xgboost']}`; scikit-learn: `{environment['packages']['scikit-learn']}`; pandas: `{environment['packages']['pandas']}`; NumPy: `{environment['packages']['numpy']}`; SHAP: `{environment['packages']['shap']}`",
        f"- GPU available: `{str(environment['gpu']['available']).lower()}` ({', '.join(environment['gpu']['devices']) or 'none'})",
        f"- Redis mode: `{environment['redis_mode']}`",
        "",
        "## Fixed-configuration model fitting time",
        "",
        "This is fixed-configuration model fitting time, not full hyperparameter-search time. Models were temporary in-memory objects and were not saved.",
        "",
        f"- Training rows: {training['train_rows']}; features: {training['feature_count']}; repetitions: {training['repetitions']}",
        f"- Individual seconds: `{training['timing']['individual_seconds']}`",
        f"- Mean/median/min/max seconds: {training['timing']['mean_seconds']!r} / {training['timing']['median_seconds']!r} / {training['timing']['min_seconds']!r} / {training['timing']['max_seconds']!r}",
        "",
        "## Local component latency",
        "",
        f"Measured {latency['measured_count']} sequential held-out test transactions after {latency['warmup_count']} stateful warm-up transactions. Route counts: `{latency['route_counts']}`.",
        "",
        "| Component | n | Mean ms | p50 ms | p95 ms | p99 ms | Max ms |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for component, stats in latency["overall"].items():
        lines.append(
            f"| {component} | {stats['n']} | {stats['mean_ms']} | {stats['p50_ms']} | "
            f"{stats['p95_ms']} | {stats['p99_ms']} | {stats['max_ms']} |"
        )

    local_stats = latency["overall"]["local_end_to_end_ms"]
    lines.extend(
        [
            "",
            f"Sequential single-process local throughput: **{local_stats['throughput_tx_per_second']!r} tx/s**. This is not production capacity.",
            "",
            "## Local end-to-end latency by route",
            "",
            "| Route | n | Mean ms | p50 ms | p95 ms | p99 ms | Max ms |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for route in ("low", "medium", "high"):
        stats = latency["by_route"][route]["local_end_to_end_ms"]
        lines.append(
            f"| {route} | {stats['n']} | {stats['mean_ms']} | {stats['p50_ms']} | "
            f"{stats['p95_ms']} | {stats['p99_ms']} | {stats['max_ms']} |"
        )

    medium_stats = latency["overall"]["deterministic_medium_investigation_ms"]
    lines.extend(
        [
            "",
            "## Medium branch and deployment boundary",
            "",
            f"Deterministic offline investigation replay takes mean={medium_stats['mean_ms']!r} ms locally (n={medium_stats['n']}, p95={medium_stats['p95_ms']!r} ms). This is not a measurement of external LLM-backed ReAct latency.",
            "",
            "```ini",
            "external_llm_react_latency = NOT MEASURED",
            "Redis/network overhead = excluded",
            "```",
            "",
            "## Timing boundary",
            "",
            TIMING_BOUNDARY,
            "",
            "## Old benchmark audit",
            "",
            f"The old report is reproduced as mean={old_audit['old_report_values']['mean_ms']} ms, p50={old_audit['old_report_values']['p50_ms']} ms, p95={old_audit['old_report_values']['p95_ms']} ms, p99={old_audit['old_report_values']['p99_ms']} ms, sample={old_audit['old_report_values']['sample']}, routes={old_audit['old_report_values']['route_distribution']}.",
            "",
            "Its timer starts after FeatureStore lookup and feature assembly; warm-up events do not advance FeatureStore state. It therefore cannot support a local end-to-end claim.",
            "",
            "```ini",
            f"OLD_BENCHMARK_REUSABLE = {old_audit['OLD_BENCHMARK_REUSABLE']}",
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def build_audit_markdown(checks: dict[str, bool], latency: dict[str, Any], status: str) -> str:
    yes_no = lambda value: "YES" if value else "NO"
    return "\n".join(
        [
            "# B11 Final Audit",
            "",
            "```ini",
            f"production model overwritten = {yes_no(checks['production_model_overwritten'])}",
            f"B1-B10 rerun = {yes_no(checks['b1_b10_rerun'])}",
            f"fixed training configuration benchmarked = {yes_no(checks['fixed_training_configuration_benchmarked'])}",
            f"XGBoost inference separated from SHAP = {yes_no(checks['xgboost_separated_from_shap'])}",
            f"feature lookup measured separately = {yes_no(checks['feature_lookup_separate'])}",
            f"feature assembly measured separately = {yes_no(checks['feature_assembly_separate'])}",
            f"deterministic medium replay measured separately = {yes_no(checks['medium_replay_separate'])}",
            f"external LLM latency claimed = {yes_no(checks['external_llm_latency_claimed'])}",
            f"Redis/network overhead clearly identified = {yes_no(checks['redis_boundary_clear'])}",
            f"sequential throughput clearly labeled = {yes_no(checks['sequential_throughput_labeled'])}",
            f"old 35.72/51.55 ms timing boundary verified = {yes_no(checks['old_boundary_verified'])}",
            "```",
            "",
            f"- Measured transactions: `{latency['measured_count']}` after `{latency['warmup_count']}` warm-up events.",
            f"- Route counts: `{latency['route_counts']}`.",
            f"- High-route sample count: `{latency['route_counts']['high']}`; no cases were fabricated or shuffled.",
            "- Training labels were used only to initialize train historical fraud-rate state. Validation and test labels were not used in feature construction or online state updates.",
            "- Deterministic medium replay was measured locally and is not labeled as ReAct API latency.",
            "- Production model, metadata, evaluation report, old latency report, and anomaly sidecar hashes were checked before and after the run.",
            "",
            "```ini",
            f"B11_STATUS = {status}",
            "```",
            "",
        ]
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="B11 final efficiency benchmark")
    parser.add_argument("--training-repetitions", type=int, default=3)
    parser.add_argument("--warmup", type=int, default=100)
    parser.add_argument("--min-measured", type=int, default=1000)
    parser.add_argument("--min-low", type=int, default=800)
    parser.add_argument("--min-medium", type=int, default=100)
    parser.add_argument("--min-high", type=int, default=1)
    args = parser.parse_args()
    if args.training_repetitions < 3:
        raise ValueError("B11 final requires at least three fixed-fit repetitions.")

    refuse_overwrite()
    protected_paths = (MODEL_PATH, METADATA_PATH, EVALUATION_PATH, OLD_BENCHMARK_PATH, ANOMALY_PATH)
    for path in protected_paths:
        if not path.is_file():
            raise FileNotFoundError(f"Required B11 input is missing: {path}")
    protected_hashes_before = {str(path.relative_to(ROOT)): sha256_file(path) for path in protected_paths}

    metadata = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
    if metadata.get("source") != "paysim":
        raise ValueError("B11 requires the PaySim production model.")
    if metadata.get("feature_columns") != list(PAYSIM_FEATURE_COLUMNS) or len(PAYSIM_FEATURE_COLUMNS) != 25:
        raise ValueError("Production metadata does not contain the ordered 25-feature schema.")
    metadata_parameters = {
        **metadata.get("selected_params", {}),
        "max_delta_step": metadata.get("training_controls", {}).get("max_delta_step"),
        "tree_method": "hist",
        "random_state": APP_CONFIG.training.random_state,
        "n_jobs": APP_CONFIG.training.n_jobs,
    }
    if metadata_parameters != FIXED_PARAMETERS:
        raise ValueError(f"Production metadata does not match the fixed B11 configuration: {metadata_parameters}")

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
        raise ValueError(f"B11 split mismatch: expected {EXPECTED_SPLIT}, got {actual_split}")

    x_train = bundle.dataset.iloc[:train_end][PAYSIM_FEATURE_COLUMNS].astype(np.float32)
    y_train = bundle.dataset.iloc[:train_end]["isFraud"].astype(int)
    positive_count = int(np.sum(y_train == 1))
    negative_count = int(np.sum(y_train == 0))
    scale_pos_weight = max(1.0, float(negative_count / max(positive_count, 1)))
    if scale_pos_weight != float(metadata["class_balance"]["scale_pos_weight"]):
        raise ValueError("Computed scale_pos_weight differs from production metadata.")

    print("benchmark_scope = B11 only", flush=True)
    print("training_benchmark = fixed-configuration model fitting time", flush=True)
    training_times = benchmark_fixed_training(
        x_train,
        y_train,
        repetitions=args.training_repetitions,
        scale_pos_weight=scale_pos_weight,
    )
    latency = benchmark_latency(
        dataset=bundle.dataset,
        train_end=train_end,
        val_end=val_end,
        metadata=metadata,
        warmup_count=args.warmup,
        min_measured=args.min_measured,
        min_low=args.min_low,
        min_medium=args.min_medium,
        min_high=args.min_high,
    )
    environment = collect_environment()
    old_audit = audit_old_benchmark()

    protected_hashes_after = {str(path.relative_to(ROOT)): sha256_file(path) for path in protected_paths}
    production_model_overwritten = protected_hashes_before != protected_hashes_after
    code_sha256, code_file_sha256 = code_provenance()
    git_status = git_value("status", "--porcelain")
    generated_at = datetime.now(timezone.utc).isoformat()
    command = " ".join([shlex.quote(sys.executable), *[shlex.quote(item) for item in sys.argv]])
    provenance = {
        "generated_at": generated_at,
        "git_commit": git_value("rev-parse", "HEAD") or "not available",
        "git_dirty": "not available" if git_status is None else bool(git_status),
        "code_sha256": code_sha256,
        "code_file_sha256": code_file_sha256,
        "dataset_path": bundle.data_path,
        "dataset_sha256": sha256_file(Path(bundle.data_path)),
        "model_path": str(MODEL_PATH.resolve()),
        "model_sha256": protected_hashes_after[str(MODEL_PATH.relative_to(ROOT))],
        "metadata_path": str(METADATA_PATH.resolve()),
        "metadata_sha256": protected_hashes_after[str(METADATA_PATH.relative_to(ROOT))],
        "anomaly_sidecar_sha256": protected_hashes_after[str(ANOMALY_PATH.relative_to(ROOT))],
        "evaluation_report_sha256": protected_hashes_after[str(EVALUATION_PATH.relative_to(ROOT))],
        "old_latency_report_sha256": protected_hashes_after[str(OLD_BENCHMARK_PATH.relative_to(ROOT))],
        "protected_hashes_before": protected_hashes_before,
        "protected_hashes_after": protected_hashes_after,
        "benchmark_command": command,
        "sample_count": latency["measured_count"],
        "warmup_count": latency["warmup_count"],
        "timing_boundary": TIMING_BOUNDARY,
        "machine_environment": environment,
    }

    training_payload = {
        "schema_version": "b11-fixed-training-time-v1",
        "description": "fixed-configuration model fitting time; not full hyperparameter-search time",
        "source": "PaySim",
        "split": actual_split,
        "train_rows": train_end,
        "feature_count": len(PAYSIM_FEATURE_COLUMNS),
        "feature_columns": list(PAYSIM_FEATURE_COLUMNS),
        "class_balance": {
            "positive_count": positive_count,
            "negative_count": negative_count,
            "scale_pos_weight": scale_pos_weight,
        },
        "fixed_parameters": {**FIXED_PARAMETERS, "scale_pos_weight": scale_pos_weight},
        "repetitions": args.training_repetitions,
        "timing_boundary": "time.perf_counter immediately before and after temporary_model.fit(X_train, y_train)",
        "timing": training_time_stats(training_times),
        "temporary_models_saved": False,
        "candidate_search": False,
        "provenance": provenance,
    }
    component_payload = {
        "schema_version": "b11-latency-components-v1",
        "source": "PaySim held-out chronological test stream",
        **latency,
        "provenance": provenance,
    }
    route_payload = {
        "schema_version": "b11-route-latency-v1",
        "route_counts": latency["route_counts"],
        "measured_count": latency["measured_count"],
        "warmup_count": latency["warmup_count"],
        "chronological_no_shuffle": True,
        "by_route": latency["by_route"],
        "high_route_note": (
            f"All high routes encountered before the stopping conditions were met are reported; n={latency['route_counts']['high']}. "
            "No transactions were shuffled or fabricated."
        ),
        "provenance": provenance,
    }
    environment_payload = {
        "schema_version": "b11-environment-v1",
        "generated_at": generated_at,
        **environment,
        "benchmark_command": command,
        "provenance_hashes": {
            "code_sha256": code_sha256,
            "dataset_sha256": provenance["dataset_sha256"],
            "model_sha256": provenance["model_sha256"],
            "metadata_sha256": provenance["metadata_sha256"],
        },
    }

    checks = {
        "production_model_overwritten": production_model_overwritten,
        "b1_b10_rerun": False,
        "fixed_training_configuration_benchmarked": args.training_repetitions >= 3,
        "xgboost_separated_from_shap": (
            latency["overall"]["xgboost_predict_proba_ms"]["n"] == latency["measured_count"]
            and latency["overall"]["shap_explanation_ms"]["n"] == latency["measured_count"]
        ),
        "feature_lookup_separate": latency["overall"]["feature_store_lookup_ms"]["n"] == latency["measured_count"],
        "feature_assembly_separate": latency["overall"]["feature_assembly_ms"]["n"] == latency["measured_count"],
        "medium_replay_separate": (
            latency["overall"]["deterministic_medium_investigation_ms"]["n"] == latency["route_counts"]["medium"]
        ),
        "external_llm_latency_claimed": False,
        "redis_boundary_clear": environment["redis_mode"].startswith("not used"),
        "sequential_throughput_labeled": (
            latency["overall"]["local_end_to_end_ms"].get("throughput_label")
            == "sequential single-process local throughput"
        ),
        "old_boundary_verified": old_audit["timing_boundary_verified"] and old_audit["old_numbers_verified"],
        "route_targets_met": (
            latency["measured_count"] >= args.min_measured
            and latency["route_counts"]["low"] >= args.min_low
            and latency["route_counts"]["medium"] >= args.min_medium
            and latency["route_counts"]["high"] >= args.min_high
        ),
        "warmup_sufficient": latency["warmup_count"] >= 100,
        "old_benchmark_not_reused": old_audit["OLD_BENCHMARK_REUSABLE"] == "NO",
    }
    pass_checks = [
        not checks["production_model_overwritten"],
        not checks["b1_b10_rerun"],
        checks["fixed_training_configuration_benchmarked"],
        checks["xgboost_separated_from_shap"],
        checks["feature_lookup_separate"],
        checks["feature_assembly_separate"],
        checks["medium_replay_separate"],
        not checks["external_llm_latency_claimed"],
        checks["redis_boundary_clear"],
        checks["sequential_throughput_labeled"],
        checks["old_boundary_verified"],
        checks["route_targets_met"],
        checks["warmup_sufficient"],
        checks["old_benchmark_not_reused"],
    ]
    status = "PASS" if all(pass_checks) else "FAIL"

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    TRAINING_PATH.write_text(json.dumps(training_payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    COMPONENT_JSON_PATH.write_text(json.dumps(component_payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    ROUTE_PATH.write_text(json.dumps(route_payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    ENVIRONMENT_PATH.write_text(json.dumps(environment_payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_component_csv(latency)
    SUMMARY_PATH.write_text(build_summary_markdown(training_payload, latency, environment, old_audit), encoding="utf-8")
    AUDIT_PATH.write_text(build_audit_markdown(checks, latency, status), encoding="utf-8")

    print(f"B11_STATUS = {status}")
    print(f"training benchmark repetitions = {args.training_repetitions}")
    print("XGBoost raw inference measured = YES")
    print("SHAP measured = YES")
    print("local end-to-end measured = YES")
    print("medium deterministic replay measured = YES")
    print("external LLM latency = NOT MEASURED")
    print(f"high-route sample count = {latency['route_counts']['high']}")
    print(f"output directory = {OUTPUT_DIR}")
    if status != "PASS":
        failed = [name for name, value in checks.items() if (name not in {"production_model_overwritten", "b1_b10_rerun", "external_llm_latency_claimed"} and not value) or (name in {"production_model_overwritten", "b1_b10_rerun", "external_llm_latency_claimed"} and value)]
        raise RuntimeError(f"B11 failed checks: {failed}")


if __name__ == "__main__":
    main()
