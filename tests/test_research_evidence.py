import json

from fastapi.testclient import TestClient

import fraud_flow.service as service
from fraud_flow.research_evidence import build_research_evidence


def test_evidence_uses_final_artifacts_and_keeps_experiment_boundaries(tmp_path):
    def save(name, value):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value))

    save("evaluation_report.json", {"split": {"test_rows": 100}, "test": {
        "roc_auc": 0.9, "pr_auc": 0.8, "metrics": {"f1": 0.7},
    }})
    save("b8_final/medium_branch_ablation_b8.json", {
        "full_react_runtime_executed": False,
        "policies": [
            {"policy": "all_medium_manual_review", "review_count": 10},
            {"policy": "deterministic_offline_investigation_replay", "review_count": 4, "manual_review_reduction_rate": 0.6},
        ],
    })
    save("b10_final/b10_bootstrap_ci.json", {"bootstrap": {"iterations": 2000}, "metrics": {"f1": {"ci95_low": 0.6, "ci95_high": 0.8}}})
    save("b11_final/b11_latency_components.json", {"overall": {"local_end_to_end_ms": {"mean_ms": 12}}})
    save("b12_final/b12_frozen_ieee.json", {"metrics": {"auc": 0.55}})
    # A legacy artifact must never override the final evidence section.
    save("external_validation.json", {"metrics": {"auc": 0.99}})
    evidence = build_research_evidence(tmp_path)
    assert evidence["test"] == {"f1": 0.7, "auc": 0.9, "pr_auc": 0.8}
    assert evidence["medium"] == {"before": 10, "after": 4, "reduction_rate": 0.6, "full_react_runtime_executed": False}
    assert evidence["bootstrap"]["iterations"] == 2000
    assert evidence["latency"]["mean_ms"] == 12
    assert evidence["external"][0]["metrics"]["auc"] == 0.55


def test_missing_artifacts_are_not_presented_as_zero_results(tmp_path):
    evidence = build_research_evidence(tmp_path)
    assert evidence["available"] is False
    assert evidence["test"]["auc"] is None
    assert evidence["medium"]["reduction_rate"] is None
    assert evidence["latency"] == {}


def test_evidence_endpoint_exposes_the_same_presentation_data(monkeypatch):
    expected = {"available": True, "test": {"f1": 0.7}, "sources": ["evaluation_report.json"]}
    monkeypatch.setattr(service, "build_research_evidence", lambda: expected)
    client = TestClient(service.create_app())
    try:
        response = client.get("/research/evidence")
        assert response.status_code == 200
        assert response.json() == expected
    finally:
        client.close()
