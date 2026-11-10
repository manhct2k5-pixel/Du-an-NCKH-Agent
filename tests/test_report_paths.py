from pathlib import Path

import pytest

import fraud_flow.report_paths as report_paths


@pytest.mark.parametrize("current_exists, archived_exists", [(True, True), (False, True), (False, False)])
def test_current_reports_take_precedence_over_archived_snapshots(
    tmp_path, monkeypatch, current_exists, archived_exists,
) -> None:
    current_dir = tmp_path / "artifacts" / "reports"
    archive_dir = tmp_path / "archive" / "artifacts" / "reports"
    current_dir.mkdir(parents=True)
    archive_dir.mkdir(parents=True)
    current = current_dir / "baseline_comparison.json"
    archived = archive_dir / current.name
    if current_exists:
        current.write_text('{"run": "current"}')
    if archived_exists:
        archived.write_text('{"run": "archived"}')
    monkeypatch.setattr(report_paths, "ROOT_DIR", tmp_path)
    monkeypatch.setattr(report_paths, "REPORT_DIR", current_dir)
    monkeypatch.setattr(report_paths, "ARCHIVE_REPORT_DIR", archive_dir)
    expected = archived if archived_exists and not current_exists else current
    assert report_paths.existing_report_path(current) == expected
    assert report_paths.existing_report_path(Path("artifacts/reports") / current.name) == expected
