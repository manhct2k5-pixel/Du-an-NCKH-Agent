from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from fraud_flow.research import run_research_suite
import fraud_flow.research as research_module


@pytest.mark.integration
def test_research_suite_small_sample_generates_new_reports(tmp_path, monkeypatch) -> None:
    config = research_module.APP_CONFIG
    monkeypatch.setattr(research_module, "APP_CONFIG", replace(
        config,
        outputs=replace(config.outputs, experiments_dir=tmp_path / "experiments"),
    ))
    report = run_research_suite(
        sample_size=20000,
        seeds=[42, 43],
        bootstrap_iterations=25,
    )

    assert "robustness" in report
    assert "external_validation" in report
    assert report["robustness"]["multi_seed_summary"]
    assert "confidence_intervals" in report["robustness"]
    assert report["artifacts"]["robustness_validation_json"].endswith("robustness_validation.json")

    robustness_path = Path(report["artifacts"]["robustness_validation_json"])
    external_path = Path(report["artifacts"]["external_validation_json"])
    assert robustness_path.exists()
    assert external_path.exists()
    assert robustness_path.is_relative_to(tmp_path)
    assert external_path.is_relative_to(tmp_path)
