"""Read the final experiment artifacts used in the NCKH presentation."""
from __future__ import annotations

import json
from pathlib import Path

from .config import REPORT_DIR


def build_research_evidence(report_dir: Path = REPORT_DIR) -> dict:
    def load(name):
        try:
            return json.loads((report_dir / name).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    evaluation = load("evaluation_report.json")
    medium = load("b8_final/medium_branch_ablation_b8.json")
    policies = {row["policy"]: row for row in medium.get("policies", [])}
    before = policies.get("all_medium_manual_review", {})
    replay = policies.get("deterministic_offline_investigation_replay", {})
    bootstrap = load("b10_final/b10_bootstrap_ci.json")
    latency = load("b11_final/b11_latency_components.json")
    ablation = load("b8_final/feature_ablation_b8.json")
    external = []
    for branch, label in [("frozen", "PaySim đóng băng"), ("transfer", "Thích nghi trên IEEE-CIS"), ("native", "Huấn luyện trong miền IEEE-CIS")]:
        report = load(f"b12_final/b12_{branch}_ieee.json")
        if report:
            external.append({"label": label, "metrics": report.get("metrics", {}), "source": f"b12_final/b12_{branch}_ieee.json"})
    test = evaluation.get("test", {})
    return {
        "available": bool(test),
        "split": evaluation.get("split", {}),
        "test": {**test.get("metrics", {}), "auc": test.get("roc_auc"), "pr_auc": test.get("pr_auc")},
        "confusion_matrix": test.get("confusion_matrix", {}),
        "medium": {
            "before": before.get("review_count"), "after": replay.get("review_count"),
            "reduction_rate": replay.get("manual_review_reduction_rate"),
            "full_react_runtime_executed": medium.get("full_react_runtime_executed"),
        },
        "ablations": ablation.get("ablations", []),
        "bootstrap": {"iterations": bootstrap.get("bootstrap", {}).get("iterations"), "metrics": bootstrap.get("metrics", {})},
        "latency": latency.get("overall", {}).get("local_end_to_end_ms", {}),
        "external": external,
        "sources": ["evaluation_report.json", "b8_final/feature_ablation_b8.json", "b8_final/medium_branch_ablation_b8.json", "b10_final/b10_bootstrap_ci.json", "b11_final/b11_latency_components.json"],
    }
