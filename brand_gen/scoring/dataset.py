"""Disagreement dataset I/O — append-safe, deterministic partition.

The disagreement dataset captures every scored run where both an agent
score and a user score exist, so v2's GEPA optimizer has a training set
and v1's `bgen scoring-status` can report agreement statistics.

Key primitives (v3 plan §4):

- `append_disagreement()` uses `fcntl.flock(LOCK_EX)` around the JSONL
  append so concurrent writes don't interleave at the line level. The
  existing run_ledger has gotten away with naked `open("a")` because
  events are small; disagreement records include the full critique
  packet and routinely exceed the POSIX 4KB atomic-write limit, so
  locking is required here.

- `compute_partition(version_id)` uses `hashlib.sha256` not Python's
  built-in `hash()`. Built-in `hash()` is PYTHONHASHSEED-randomized
  across processes, which would silently drift the 50/50 partition
  between runs. Every record carries the algorithm name in
  `partition_algo` so future algorithm swaps are auditable.

- Single-file with tag (not dual-write). GEPA filters by
  `partition_tag == "scorer_training"`. The generator's iteration_memory
  is untouched — it continues to read its own existing store via
  `auto_capture_generation_feedback`.
"""
from __future__ import annotations

import fcntl
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Iterator

_PARTITION_ALGO = "sha256-mod2"
_DATASET_RELATIVE_PATH = ("scoring", "disagreement_dataset.jsonl")
_SCHEMA_VERSION = 1


def disagreement_dataset_path(brand_dir: Path) -> Path:
    """Resolve the disagreement dataset path for a brand."""
    return brand_dir.joinpath(*_DATASET_RELATIVE_PATH)


def compute_partition(version_id: str) -> str:
    """Deterministically assign a version_id to a partition.

    Returns "scorer_training" or "iteration_memory". GEPA (v2) reads only
    records tagged `scorer_training`; the `iteration_memory` tag is for
    auditability — it marks records that GEPA should ignore even though
    they are in the same file.

    Uses sha256 instead of Python's built-in hash() so the assignment is
    stable across processes, machines, and Python versions.
    """
    if not version_id:
        return "scorer_training"
    digest = hashlib.sha256(version_id.encode("utf-8")).hexdigest()
    return "scorer_training" if int(digest, 16) % 2 == 0 else "iteration_memory"


def agreement_bucket(delta: int) -> str:
    """Classify an agent-user score delta into a named bucket."""
    if delta <= 0:
        return "strong_agreement"
    if delta == 1:
        return "mild_disagreement"
    if delta == 2:
        return "strong_disagreement"
    return "calibration_failure"


def append_disagreement(brand_dir: Path, record: dict[str, Any]) -> Path:
    """Append a disagreement record to the brand's dataset.

    `fcntl.flock(LOCK_EX)` holds an exclusive lock across the append
    so concurrent submit-critique + cmd_feedback calls don't interleave
    partial lines. Adds `schema_version` and `partition_algo` if missing.
    """
    record = dict(record)  # shallow copy, do not mutate caller's dict
    record.setdefault("schema_version", _SCHEMA_VERSION)
    record.setdefault("partition_algo", _PARTITION_ALGO)

    path = disagreement_dataset_path(brand_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            handle.write(json.dumps(record, default=str) + "\n")
            handle.flush()
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    return path


def load_disagreements(
    brand_dir: Path,
    *,
    partition_tag: str | None = None,
    material_type: str | None = None,
    bucket: str | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """Load records from the disagreement dataset with optional filters.

    Returns a list (most recent first). JSONL reading tolerates malformed
    lines by skipping them rather than raising, so a partial-write
    crash doesn't render the dataset unreadable.
    """
    path = disagreement_dataset_path(brand_dir)
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(parsed, dict):
            continue
        if partition_tag is not None and parsed.get("partition_tag") != partition_tag:
            continue
        if material_type is not None and parsed.get("material_type") != material_type:
            continue
        if bucket is not None and parsed.get("agreement_bucket") != bucket:
            continue
        records.append(parsed)
    # Return most recent first (records written in order)
    records.reverse()
    if limit is not None and limit >= 0:
        records = records[:limit]
    return records


def iter_disagreements(brand_dir: Path) -> Iterator[dict[str, Any]]:
    """Stream records as an iterator (oldest first). Useful for backfill
    scripts that want to process without loading the whole file."""
    path = disagreement_dataset_path(brand_dir)
    if not path.exists():
        return
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                parsed = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                yield parsed


def partition_split_observed(records: Iterable[dict[str, Any]]) -> dict[str, int]:
    """Count how many records landed in each partition. Used by scoring-status."""
    counts = {"scorer_training": 0, "iteration_memory": 0, "unknown": 0}
    for r in records:
        tag = r.get("partition_tag")
        if tag in counts:
            counts[tag] += 1
        else:
            counts["unknown"] += 1
    return counts
