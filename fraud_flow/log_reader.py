"""Append-aware JSONL indexes for dashboard reads, without changing log files."""
from __future__ import annotations

import json
import os
from collections import OrderedDict
from collections.abc import Mapping, Sequence
from pathlib import Path
from threading import RLock
from typing import Any


class LogChangedError(OSError):
    """A log was replaced while a dashboard snapshot was being read."""


class ReviewRow(Mapping):
    def __init__(self, snapshot: LogSnapshot, index: int, summary: dict) -> None:
        self.snapshot, self.index, self.summary = snapshot, index, summary

    def __getitem__(self, key):
        if key in self.summary:
            return self.summary[key]
        return self.snapshot[self.index][key]

    def __iter__(self):
        return iter(self.snapshot[self.index])

    def __len__(self):
        return len(self.snapshot[self.index])


class LogSnapshot(Sequence):
    def __init__(self, log: _LogIndex) -> None:
        self.log = log
        self.identity = log.identity
        self.revision = log.revision
        self.end = log.position
        self.offsets = tuple(log.offsets)
        self.tx_ids = log.tx_ids.copy()
        self.latest_agent = log.latest_agent
        self.reviews = tuple(log.reviews)

    def __len__(self):
        return len(self.offsets)

    def __getitem__(self, index):
        if isinstance(index, slice):
            indices = range(*index.indices(len(self)))
            return self._read(indices)
        return self._read([range(len(self))[index]])[0]

    def _read(self, indices):
        rows = []
        if not indices:
            return rows
        with self.log.lock:
            if self.revision != self.log.revision:
                raise LogChangedError(self.log.path)
            try:
                handle = self.log.path.open("rb")
            except FileNotFoundError as exc:
                raise LogChangedError(self.log.path) from exc
            with handle:
                stat = os.fstat(handle.fileno())
                if (stat.st_dev, stat.st_ino) != self.identity or stat.st_size < self.end:
                    raise LogChangedError(self.log.path)
                for index in indices:
                    offset = self.offsets[index]
                    cached = self.log.rows.get(offset)
                    if cached is None:
                        handle.seek(offset)
                        line = handle.readline()
                        if not line.endswith(b"\n"):
                            raise LogChangedError(self.log.path)
                        cached = json.loads(line)
                        self.log.rows[offset] = cached
                        if len(self.log.rows) > 8192:
                            self.log.rows.popitem(last=False)
                    else:
                        self.log.rows.move_to_end(offset)
                    rows.append(cached)
        return rows

    def find(self, tx_id: str):
        index = self.tx_ids.get(tx_id)
        return self[index] if index is not None else None

    def review_rows(self, decided_ids: set[str]):
        return [
            ReviewRow(self, index, summary)
            for index, summary in enumerate(self.reviews)
            if summary["event"]["tx_id"] not in decided_ids
        ]


class _LogIndex:
    def __init__(self, path: Path, kind: str) -> None:
        self.path, self.kind = path, kind
        self.lock = RLock()
        self._reset()

    def _reset(self):
        self.revision = getattr(self, "revision", 0) + 1
        self.identity = None
        self.signature = None
        self.position = 0
        self.anchor = b""
        self.offsets = []
        self.tx_ids = {}
        self.latest_agent = None
        self.reviews = []
        self.rows = OrderedDict()

    def snapshot(self):
        with self.lock:
            try:
                handle = self.path.open("rb")
            except FileNotFoundError:
                self._reset()
                return LogSnapshot(self)
            with handle:
                stat = os.fstat(handle.fileno())
                identity = (stat.st_dev, stat.st_ino)
                signature = (identity, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)
                if signature == self.signature:
                    return LogSnapshot(self)
                handle.seek(max(0, self.position - len(self.anchor)))
                anchor_matches = handle.read(len(self.anchor)) == self.anchor
                if (identity != self.identity or stat.st_size < self.position
                        or not anchor_matches
                        or (stat.st_size == self.position and self.signature is not None)):
                    self._reset()
                self.identity = identity
                handle.seek(self.position)
                while handle.tell() < stat.st_size:
                    offset = handle.tell()
                    line = handle.readline(stat.st_size - offset)
                    # A concurrent writer may not have finished its last record yet.
                    if not line.endswith(b"\n"):
                        break
                    if not line.strip():
                        self.position = handle.tell()
                        continue
                    index = len(self.offsets)
                    if self.kind in {"predictions", "reviews"}:
                        row = json.loads(line)
                        self.tx_ids[row["event"]["tx_id"]] = index
                        if self.kind == "predictions" and row.get("agent"):
                            self.latest_agent = index
                        if self.kind == "reviews":
                            # Sorting/filtering needs these fields; large agent traces stay on disk.
                            event, prediction = row["event"], row["prediction"]
                            score = float(prediction.get("score", 0.0) or 0.0)
                            raw = float(prediction.get("raw_probability", 0.0) or 0.0)
                            bucket = 2 if prediction.get("route") == "high" or score >= 0.65 or raw >= 0.5 else (1 if score >= 0.5 else 0)
                            self.reviews.append({
                                "event": event,
                                "prediction": prediction,
                                "_priority": (bucket, score, str(event.get("timestamp", "")), str(event.get("tx_id", ""))),
                            })
                    self.offsets.append(offset)
                    self.position = handle.tell()
                handle.seek(max(0, self.position - 64))
                self.anchor = handle.read(min(64, self.position))
                self.signature = signature
            return LogSnapshot(self)


_indexes: OrderedDict[tuple[Path, str], _LogIndex] = OrderedDict()
_indexes_lock = RLock()


def log_snapshot(path: Path, kind: str = "plain") -> LogSnapshot:
    key = (path.resolve(), kind)
    with _indexes_lock:
        if key not in _indexes:
            _indexes[key] = _LogIndex(*key)
            if len(_indexes) > 32:
                _indexes.popitem(last=False)
        index = _indexes[key]
        _indexes.move_to_end(key)
    return index.snapshot()


def clear_log_cache() -> None:
    with _indexes_lock:
        _indexes.clear()
