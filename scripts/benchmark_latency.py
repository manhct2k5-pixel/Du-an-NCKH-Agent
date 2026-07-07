"""
Benchmark latency & throughput cua FraudFlow pipeline.

Do rieng ba nhanh: low, medium, high -- de thay overhead cua agent.
Dung FeatureStore in-memory (khong can Redis).

Chay:
    python scripts/benchmark_latency.py
    python scripts/benchmark_latency.py --n 500 --warmup 50
"""
from __future__ import annotations

import argparse
import json
import statistics
import time
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from fraud_flow.feature_store import FeatureStore
from fraud_flow.features import (
    assemble_feature_row,
    enrich_transactions,
    event_from_row,
    load_filtered_frame,
)
from fraud_flow.pipeline import FraudModelService
from fraud_flow.research import replay_medium_agent


REPORT_PATH = Path("artifacts/reports/latency_report.json")


def percentile(sorted_data: list[float], p: float) -> float:
    idx = int(p * len(sorted_data))
    return sorted_data[min(idx, len(sorted_data) - 1)]


def latency_stats(ms_list: list[float]) -> dict:
    if not ms_list:
        return {"n": 0, "note": "no samples"}
    s = sorted(ms_list)
    mean = statistics.mean(s)
    return {
        "n": len(s),
        "mean_ms": round(mean, 3),
        "p50_ms": round(percentile(s, 0.50), 3),
        "p95_ms": round(percentile(s, 0.95), 3),
        "p99_ms": round(percentile(s, 0.99), 3),
        "max_ms": round(max(s), 3),
        "throughput_tps": round(1000 / mean, 1) if mean > 0 else 0.0,
    }


def run_benchmark(n: int = 1000, warmup: int = 100) -> dict:
    print("[benchmark] Loading model service...")
    model_service = FraudModelService()
    source = model_service.source
    data_path = model_service.metadata["data_path"]
    sample_size = model_service.metadata["sample_size_used"]
    val_end = int(model_service.metadata["val_end"])

    print("[benchmark] Loading dataset and enriching...")
    raw = load_filtered_frame(data_path, sample_size=sample_size, source=source)
    enriched = enrich_transactions(raw, source=source).reset_index(drop=True)

    # Warm the in-memory feature store with train+val history
    store = FeatureStore()
    warmup_frame = enriched.iloc[:val_end]
    print(f"[benchmark] Warming feature store with {len(warmup_frame)} rows...")
    for row in warmup_frame.itertuples(index=False):
        ev = event_from_row(row, source=source)
        store.observe_activity(ev)

    # Live frame = after val_end
    live_frame = enriched.iloc[val_end:].reset_index(drop=True)
    total_needed = min(n + warmup, len(live_frame))
    live_frame = live_frame.iloc[:total_needed]
    events = [event_from_row(row, source=source) for row in live_frame.itertuples(index=False)]

    # --- Warmup (JIT + cache) ---
    print(f"[benchmark] Warmup {warmup} transactions (not measured)...")
    for ev in events[:warmup]:
        lookup = store.lookup(ev)
        feature_row = assemble_feature_row(ev, lookup)
        model_service.predict(feature_row)

    # --- Benchmark ---
    benchmark_events = events[warmup:warmup + n]
    if len(benchmark_events) < n:
        print(f"  [warn] Only {len(benchmark_events)} available (requested {n})")

    print(f"[benchmark] Measuring {len(benchmark_events)} transactions...")

    all_ms: list[float] = []
    by_route: dict[str, list[float]] = {"low": [], "medium": [], "high": []}

    for ev in benchmark_events:
        lookup = store.lookup(ev)
        feature_row = assemble_feature_row(ev, lookup)

        t0 = time.perf_counter()
        prediction = model_service.predict(feature_row)
        elapsed_ms = (time.perf_counter() - t0) * 1000

        # Medium nhanh: them agent overhead
        if prediction.route == "medium":
            t1 = time.perf_counter()
            try:
                replay_medium_agent(store, ev, lookup, prediction)
            except Exception:
                pass
            elapsed_ms = (time.perf_counter() - t0) * 1000

        all_ms.append(elapsed_ms)
        if prediction.route in by_route:
            by_route[prediction.route].append(elapsed_ms)

        store.observe_activity(ev)

    # --- Report ---
    route_counts = {k: len(v) for k, v in by_route.items()}
    report = {
        "description": "FraudFlow pipeline latency benchmark (post leakage fix)",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "config": {
            "n_benchmark": len(all_ms),
            "warmup": warmup,
            "source": source,
        },
        "route_distribution": route_counts,
        "overall": latency_stats(all_ms),
        "by_route": {
            route: latency_stats(ms_list)
            for route, ms_list in by_route.items()
        },
    }

    # Print summary
    print("\n=== Benchmark Results ===")
    o = report["overall"]
    print(f"Full pipeline ({len(all_ms)} tx): "
          f"p50={o['p50_ms']}ms  p95={o['p95_ms']}ms  p99={o['p99_ms']}ms  "
          f"mean={o['mean_ms']}ms  max={o['max_ms']}ms  {o['throughput_tps']} TPS")
    print(f"Route distribution: {route_counts}")
    for route, stats in report["by_route"].items():
        if stats.get("n", 0) == 0:
            print(f"  [{route}] no samples")
            continue
        print(f"  [{route}] ({stats['n']} tx): "
              f"p50={stats['p50_ms']}ms  p95={stats['p95_ms']}ms  "
              f"p99={stats['p99_ms']}ms  {stats['throughput_tps']} TPS")

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n[benchmark] Saved: {REPORT_PATH}")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark FraudFlow pipeline latency")
    parser.add_argument("--n", type=int, default=1000, help="Number of benchmark transactions (default: 1000)")
    parser.add_argument("--warmup", type=int, default=100, help="JIT warmup transactions (default: 100)")
    args = parser.parse_args()
    run_benchmark(n=args.n, warmup=args.warmup)


if __name__ == "__main__":
    main()
