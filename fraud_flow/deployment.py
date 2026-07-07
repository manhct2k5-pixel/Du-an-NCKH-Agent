from __future__ import annotations

import json
import platform
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import APP_CONFIG, ROOT_DIR


def _normalise_path(value: Any) -> Any:
    """Normalise a stored path to match the current OS.

    Stored as Windows (D:\\...)  → on Linux/WSL convert to /mnt/d/...
    Stored as POSIX  (/mnt/d/...) → on Windows convert to D:\\...
    """
    if not isinstance(value, str):
        return value
    _sep = "\\"
    normalised = value
    if platform.system() == "Windows":
        # /mnt/d/foo/bar  →  D:\foo\bar
        m = re.match(r"^/mnt/([a-z])/(.+)$", value)
        if m:
            rest = m.group(2).replace("/", _sep)
            normalised = f"{m.group(1).upper()}:{_sep}{rest}"
    else:
        # D:\foo\bar  →  /mnt/d/foo/bar
        m = re.match(r"^([A-Za-z]):" + _sep + _sep + r"(.*)$", value)
        if m:
            rest = m.group(2).replace(_sep, "/")
            normalised = f"/mnt/{m.group(1).lower()}/{rest}"
    return _relocate_repo_path(normalised)


def _relocate_repo_path(value: str) -> str:
    """Map copied project paths from another machine back into this repo.

    Model metadata/deployment state can contain absolute paths from Windows or
    WSL exports. If that old absolute path does not exist, keep the part below
    data/ or artifacts/ and resolve it relative to the current checkout.
    """
    if Path(value).exists():
        return value

    portable = value.replace("\\", "/")
    for marker in ("artifacts/", "data/"):
        marker_index = portable.find(marker)
        if marker_index >= 0:
            return str(ROOT_DIR / portable[marker_index:])
    return value


def _load_json_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _copy_optional_artifact(source: Path, dest: Path) -> Path | None:
    if not source.exists():
        return None
    shutil.copy2(source, dest)
    return dest


def _rewrite_metadata_artifact_paths(metadata_path: Path, *, anomaly_model_path: Path | None = None) -> None:
    metadata = _load_json_file(metadata_path)
    if not metadata:
        return
    if anomaly_model_path is not None:
        metadata["anomaly_model_path"] = str(anomaly_model_path)
    metadata_path.write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def _resolve_version_anomaly_path(version_dir: Path, metadata_path: Path) -> str | None:
    sidecar_path = version_dir / APP_CONFIG.outputs.anomaly_model_path.name
    if sidecar_path.exists():
        return str(sidecar_path)

    metadata = _load_json_file(metadata_path)
    stored_path = _normalise_path(metadata.get("anomaly_model_path"))
    if stored_path and Path(stored_path).exists():
        return str(Path(stored_path))

    if APP_CONFIG.outputs.anomaly_model_path.exists():
        return str(APP_CONFIG.outputs.anomaly_model_path)
    return None


class DeploymentManager:
    def __init__(self) -> None:
        APP_CONFIG.outputs.model_versions_dir.mkdir(parents=True, exist_ok=True)
        APP_CONFIG.outputs.deployment_state_path.parent.mkdir(parents=True, exist_ok=True)

    def register_candidate(self) -> dict[str, Any]:
        version_id = datetime.now(timezone.utc).strftime("v%Y%m%dT%H%M%S%fZ")
        version_dir = APP_CONFIG.outputs.model_versions_dir / version_id
        version_dir.mkdir(parents=True, exist_ok=True)

        model_copy = version_dir / APP_CONFIG.outputs.model_path.name
        metadata_copy = version_dir / APP_CONFIG.outputs.metadata_path.name
        anomaly_copy = _copy_optional_artifact(
            APP_CONFIG.outputs.anomaly_model_path,
            version_dir / APP_CONFIG.outputs.anomaly_model_path.name,
        )
        shutil.copy2(APP_CONFIG.outputs.model_path, model_copy)
        shutil.copy2(APP_CONFIG.outputs.metadata_path, metadata_copy)
        _rewrite_metadata_artifact_paths(metadata_copy, anomaly_model_path=anomaly_copy)

        state = self._load_state()
        previous_active = state.get("active_version")
        state.update(
            {
                "last_trained_version": version_id,
                "candidate_version": version_id,
                "candidate_model_path": str(model_copy),
                "candidate_metadata_path": str(metadata_copy),
                "candidate_anomaly_model_path": str(anomaly_copy) if anomaly_copy else None,
                "rollback_version": previous_active,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        if previous_active is None:
            state["active_version"] = version_id
            state["active_model_path"] = str(model_copy)
            state["active_metadata_path"] = str(metadata_copy)
            state["active_anomaly_model_path"] = state.get("candidate_anomaly_model_path")
            state["deployment_strategy"] = "bootstrap"

        self._write_state(state)
        self._append_history(
            {
                "event": "register_candidate",
                "version_id": version_id,
                "timestamp": state["updated_at"],
                "previous_active": previous_active,
            }
        )
        self._write_rollout_plan(state)
        return state

    def promote_candidate(self, reason: str) -> dict[str, Any]:
        state = self._load_state()
        candidate = state.get("candidate_version")
        if not candidate:
            raise RuntimeError("No candidate version available for promotion.")

        previous_active = state.get("active_version")
        candidate_metadata_path = state.get("candidate_metadata_path")
        candidate_anomaly_path = state.get("candidate_anomaly_model_path")
        if not candidate_anomaly_path and candidate_metadata_path:
            metadata_path = Path(candidate_metadata_path)
            candidate_anomaly_path = _resolve_version_anomaly_path(metadata_path.parent, metadata_path)
        state.update(
            {
                "active_version": candidate,
                "active_model_path": state.get("candidate_model_path"),
                "active_metadata_path": state.get("candidate_metadata_path"),
                "active_anomaly_model_path": candidate_anomaly_path,
                "rollback_version": previous_active,
                "deployment_strategy": "canary_then_full_rollout",
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "promotion_reason": reason,
            }
        )
        self._write_state(state)
        self._append_history(
            {
                "event": "promote_candidate",
                "version_id": candidate,
                "timestamp": state["updated_at"],
                "reason": reason,
                "rollback_version": previous_active,
            }
        )
        self._write_rollout_plan(state)
        return state

    def rollback(self, reason: str) -> dict[str, Any]:
        state = self._load_state()
        rollback_version = state.get("rollback_version")
        if not rollback_version:
            raise RuntimeError("No rollback target is available.")

        rollback_dir = APP_CONFIG.outputs.model_versions_dir / rollback_version
        rollback_metadata_path = rollback_dir / APP_CONFIG.outputs.metadata_path.name
        rollback_anomaly_path = _resolve_version_anomaly_path(rollback_dir, rollback_metadata_path)
        state.update(
            {
                "active_version": rollback_version,
                "active_model_path": str(rollback_dir / APP_CONFIG.outputs.model_path.name),
                "active_metadata_path": str(rollback_metadata_path),
                "active_anomaly_model_path": rollback_anomaly_path,
                "deployment_strategy": "rollback",
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "rollback_reason": reason,
            }
        )
        self._write_state(state)
        self._append_history(
            {
                "event": "rollback",
                "version_id": rollback_version,
                "timestamp": state["updated_at"],
                "reason": reason,
            }
        )
        self._write_rollout_plan(state)
        return state

    def status(self) -> dict[str, Any]:
        return self._load_state()

    def _write_rollout_plan(self, state: dict[str, Any]) -> None:
        rollout = {
            "active_version": state.get("active_version"),
            "candidate_version": state.get("candidate_version"),
            "strategy": state.get("deployment_strategy", "canary_then_full_rollout"),
            "canary_percent": 10,
            "ab_test_plan": {
                "control_version": state.get("rollback_version"),
                "candidate_version": state.get("candidate_version"),
                "primary_metric": "AUC",
                "guardrails": ["precision", "recall", "false_positive_rate", "latency_p95_ms"],
            },
            "rollback_target": state.get("rollback_version"),
        }
        APP_CONFIG.outputs.rollout_plan_path.write_text(
            json.dumps(rollout, indent=2),
            encoding="utf-8",
        )

    def _append_history(self, payload: dict[str, Any]) -> None:
        with APP_CONFIG.outputs.deployment_history_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, ensure_ascii=False) + "\n")

    def _load_state(self) -> dict[str, Any]:
        if not APP_CONFIG.outputs.deployment_state_path.exists():
            return {}
        state = _load_json_file(APP_CONFIG.outputs.deployment_state_path)
        return {k: _normalise_path(v) for k, v in state.items()}

    def _write_state(self, state: dict[str, Any]) -> None:
        APP_CONFIG.outputs.deployment_state_path.write_text(
            json.dumps(state, indent=2),
            encoding="utf-8",
        )
