from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import fraud_flow.deployment as deployment_module
from fraud_flow.config import APP_CONFIG
from fraud_flow.deployment import DeploymentManager


def _write_training_artifacts(tag: str, model_path: Path, anomaly_path: Path, metadata_path: Path) -> None:
    model_path.parent.mkdir(parents=True, exist_ok=True)
    model_path.write_text(f"model-{tag}", encoding="utf-8")
    anomaly_path.write_bytes(f"anomaly-{tag}".encode("utf-8"))
    metadata_path.write_text(
        json.dumps(
            {
                "artifact_tag": tag,
                "anomaly_model_path": str(anomaly_path),
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def test_deployment_versions_anomaly_sidecar_for_promote_and_rollback(tmp_path, monkeypatch) -> None:
    outputs = replace(
        APP_CONFIG.outputs,
        model_path=tmp_path / "models" / "xgboost_fraud.json",
        anomaly_model_path=tmp_path / "models" / "anomaly_sidecar.joblib",
        metadata_path=tmp_path / "models" / "model_metadata.json",
        model_versions_dir=tmp_path / "versions",
        deployment_state_path=tmp_path / "deployment" / "deployment_state.json",
        deployment_history_path=tmp_path / "deployment" / "deployment_history.jsonl",
        rollout_plan_path=tmp_path / "deployment" / "rollout_plan.json",
    )
    config = replace(APP_CONFIG, outputs=outputs)
    monkeypatch.setattr(deployment_module, "APP_CONFIG", config)

    manager = DeploymentManager()

    _write_training_artifacts("v1", outputs.model_path, outputs.anomaly_model_path, outputs.metadata_path)
    first_state = manager.register_candidate()
    first_active_anomaly = first_state["active_anomaly_model_path"]
    assert first_active_anomaly is not None
    assert Path(first_active_anomaly).exists()

    _write_training_artifacts("v2", outputs.model_path, outputs.anomaly_model_path, outputs.metadata_path)
    second_state = manager.register_candidate()
    second_candidate_anomaly = second_state["candidate_anomaly_model_path"]
    assert second_candidate_anomaly is not None
    assert second_candidate_anomaly != first_active_anomaly
    assert Path(second_candidate_anomaly).exists()

    promoted_state = manager.promote_candidate(reason="test promote")
    assert promoted_state["active_anomaly_model_path"] == second_candidate_anomaly

    rolled_back_state = manager.rollback(reason="test rollback")
    assert rolled_back_state["active_anomaly_model_path"] == first_active_anomaly

    copied_metadata = json.loads(Path(second_state["candidate_metadata_path"]).read_text(encoding="utf-8"))
    assert copied_metadata["anomaly_model_path"] == second_candidate_anomaly
