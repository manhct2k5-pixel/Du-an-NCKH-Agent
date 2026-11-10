import json
from dataclasses import fields, replace

import pytest

import fraud_flow.log_reader as log_reader
import fraud_flow.ops as ops
from fraud_flow.config import APP_CONFIG


def write_rows(path, rows, mode="w"):
    with path.open(mode, encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def prediction(tx_id, score=0.5, agent=True):
    return {
        "event": {"tx_id": tx_id, "tx_type": "TRANSFER", "amount": 100,
                  "timestamp": "2025-01-01T00:00:00+00:00", "is_fraud": 0},
        "prediction": {"route": "medium" if agent else "low", "score": score,
                       "raw_probability": 0.01, "latency_ms": 2},
        "final_action": "review" if agent else "approve",
        "final_note": "Complete",
        "actual_label": 0,
        "agent": {"action": "review", "reviewer_note": "Check"} if agent else None,
        "narrative": {"human_readable_explanation": "Done", "analyst_report": "Done", "dashboard_summary": "Done"},
    }


def test_append_only_refresh_and_count_only_logs_do_not_decode_old_records(tmp_path, monkeypatch):
    path = tmp_path / "predictions.jsonl"
    write_rows(path, [prediction("a"), prediction("b")])
    loads = json.loads
    decoded = []

    def track(line):
        decoded.append(line)
        return loads(line)

    monkeypatch.setattr(log_reader.json, "loads", track)
    first = log_reader.log_snapshot(path, "predictions")
    assert len(first) == 2 and len(decoded) == 2
    decoded.clear()
    assert len(log_reader.log_snapshot(path, "predictions")) == 2
    assert not decoded
    write_rows(path, [prediction("c")], "a")
    assert len(log_reader.log_snapshot(path, "predictions")) == 3
    assert len(decoded) == 1
    decoded.clear()
    feedback = tmp_path / "feedback.jsonl"
    write_rows(feedback, [{"tx_id": str(i), "actual_label": 0} for i in range(100)])
    assert len(log_reader.log_snapshot(feedback)) == 100
    assert not decoded


def test_partial_lines_unicode_and_latest_duplicate_focus(tmp_path):
    path = tmp_path / "predictions.jsonl"
    write_rows(path, [prediction("giao_dịch")])
    with path.open("a") as handle:
        handle.write(" \n" + json.dumps(prediction("pending"))[:30])
    snapshot = log_reader.log_snapshot(path, "predictions")
    assert len(snapshot) == 1
    assert snapshot.find("giao_dịch")["event"]["tx_id"] == "giao_dịch"
    with path.open("a") as handle:
        handle.write(json.dumps(prediction("pending"))[30:] + "\n")
    write_rows(path, [prediction("giao_dịch", score=0.9)], "a")
    snapshot = log_reader.log_snapshot(path, "predictions")
    assert len(snapshot) == 3
    assert snapshot.find("giao_dịch")["prediction"]["score"] == 0.9
    assert snapshot[-2]["event"]["tx_id"] == "pending"


@pytest.mark.parametrize("change", ["truncate", "rewrite", "replace", "delete"])
def test_rotated_or_rewritten_logs_invalidate_cached_rows(tmp_path, change):
    path = tmp_path / "log.jsonl"
    write_rows(path, [{"id": "old"}])
    old = log_reader.log_snapshot(path)
    assert old[-1] == {"id": "old"}
    if change == "delete":
        path.unlink()
    elif change == "truncate":
        path.write_text("")
    elif change == "replace":
        replacement = tmp_path / "replacement.jsonl"
        write_rows(replacement, [{"id": "new"}])
        replacement.replace(path)
    else:
        write_rows(path, [{"id": "new"}])
    current = log_reader.log_snapshot(path)
    assert list(current) == ([] if change in {"delete", "truncate"} else [{"id": "new"}])
    with pytest.raises(log_reader.LogChangedError):
        old[-1]


class EagerSnapshot:
    """Reference reader which decodes every complete line on every request."""
    def __init__(self, path, kind="plain"):
        self.rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()] if path.exists() else []

    def __len__(self):
        return len(self.rows)

    def __getitem__(self, index):
        return self.rows[index]

    def review_rows(self, decided_ids):
        return [row for row in self.rows if row["event"]["tx_id"] not in decided_ids]


@pytest.fixture
def dashboard_files(tmp_path, monkeypatch):
    outputs = replace(APP_CONFIG.outputs, **{
        field.name: tmp_path / field.name for field in fields(APP_CONFIG.outputs)
    })
    monkeypatch.setattr(ops, "APP_CONFIG", replace(APP_CONFIG, outputs=outputs))
    outputs.training_report_path.write_text(json.dumps({"source": "paysim", "data_path": str(tmp_path / "missing.csv")}))
    outputs.simulation_report_path.write_text('{"processed_transactions":3}')
    rows = [prediction("old-focus", 0.9)] + [prediction(f"tx-{i}") for i in range(510)]
    write_rows(outputs.prediction_log_path, rows)
    write_rows(outputs.manual_review_queue_path, [rows[0], rows[-1]])
    write_rows(outputs.feedback_log_path, [{"tx_id": "old-focus"}])
    return outputs


@pytest.mark.parametrize("focus,limit", [(None, None), ("old-focus", 1), ("tx-509", 1), ("not-found", 100)])
def test_dashboard_matches_full_reader_after_append_review_and_rotation(dashboard_files, monkeypatch, focus, limit):
    paths = dashboard_files
    indexed_reader = ops.log_snapshot

    def compare():
        monkeypatch.setattr(ops, "log_snapshot", EagerSnapshot)
        expected = ops.build_dashboard_data(focus_tx_id=focus, queue_limit=limit)
        monkeypatch.setattr(ops, "log_snapshot", indexed_reader)
        actual = ops.build_dashboard_data(focus_tx_id=focus, queue_limit=limit)
        expected.pop("generated_at")
        actual.pop("generated_at")
        assert actual == expected
        if focus == "tx-509" and actual["totals"]["pending_reviews"]:
            assert actual["review_queue_cards"][0]["tx_id"] == focus

    compare()
    compare()
    newest = prediction("newest", 0.99)
    write_rows(paths.prediction_log_path, [newest], "a")
    write_rows(paths.manual_review_queue_path, [newest], "a")
    write_rows(paths.feedback_log_path, [{"tx_id": "newest"}], "a")
    compare()
    write_rows(paths.manual_review_decisions_path, [{"tx_id": "newest", "action": "approve"}])
    compare()
    write_rows(paths.prediction_log_path, [prediction("low-only", agent=False)])
    write_rows(paths.manual_review_queue_path, [])
    compare()
