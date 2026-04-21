"""Projected Run state over the append-only run ledger.

The run ledger (``run_ledger.py``) stores one JSONL file per workflow_id,
one event per stage transition. This module folds those events into a
stable ``Run`` object that agents can query via ``brand_list_runs`` and
``brand_get_run`` without reconstructing state from scattered files.

Design notes:

* This is a projection, not a source of truth. Events are append-only;
  the Run object is derived every call. If two writers race a stage
  transition, the ledger records both and the projection reflects the
  last-wins timestamp order.
* ``status`` is derived, not stored. Mapping:
    - any event carrying ``status=="blocked"`` **and** non-empty
      ``warnings`` or ``data.blocking_issues`` → ``"blocked"``
    - last event stage == ``"evolve"`` → ``"completed"``
    - last event stage == ``"review"`` with ``data.decision == "needs_refinement"``
      or ``data.decision == "awaiting_human_review"`` → ``"awaiting_review"``
    - otherwise → ``"in_progress"``
* ``artifact_ids`` is a dict of {plan_path, critique_path,
  scratchpad_path, version_id, review_packet_path} assembled from event
  data payloads.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

from .run_ledger import load_run_events, run_ledger_dir


_COMPLETED_STAGES = {"evolve", "evolve_run"}
_REVIEW_STAGES = {"review", "review_run"}
_AWAITING_DECISIONS = {"needs_refinement", "awaiting_human_review", "pending"}


@dataclass
class Run:
    """Projected state for a single workflow run.

    All fields are populated by folding the run ledger. ``artifact_ids``
    is a best-effort collection of artifact pointers the agent can use
    to fetch the typed payload via the Phase B inspection verbs.
    """

    run_id: str
    brand_key: str = ""
    material_type: str = ""
    mode: str = ""
    requested_goal: str = ""
    current_stage: str = ""
    status: str = "unknown"
    blocking_issues: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    artifact_ids: dict[str, str] = field(default_factory=dict)
    lineage: list[str] = field(default_factory=list)
    stages_completed: list[str] = field(default_factory=list)
    created_at: str = ""
    last_updated_at: str = ""
    event_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _coerce_str(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def _merge_artifact_pointers(pointers: dict[str, str], event: dict[str, Any]) -> None:
    """Harvest any known artifact pointers from the event payload."""
    data = event.get("data") or {}
    if not isinstance(data, dict):
        data = {}
    pointer_map = {
        "plan_path": ["plan_path", "plan_draft_path", "plan_id"],
        "critique_path": ["critique_path", "critique_id"],
        "scratchpad_path": ["scratchpad_path", "scratchpad_id"],
        "review_packet_path": ["review_packet_path", "packet_id", "auto_review_path"],
    }
    for artifact_key, candidates in pointer_map.items():
        for candidate in candidates:
            for source in (event, data):
                value = _coerce_str(source.get(candidate))
                if value:
                    pointers[artifact_key] = value
                    break
            if artifact_key in pointers:
                break
    output_version = _coerce_str(event.get("output_version"))
    if output_version:
        pointers["version_id"] = output_version
    source_version = _coerce_str(event.get("source_version"))
    if source_version and "source_version" not in pointers:
        pointers["source_version"] = source_version


def project_run(workflow_id: str, events: list[dict[str, Any]]) -> Run:
    """Fold a sequence of ledger events into a Run projection."""
    run = Run(run_id=str(workflow_id or ""))
    if not events:
        return run
    events_sorted = sorted(events, key=lambda item: _coerce_str(item.get("timestamp")))
    run.event_count = len(events_sorted)
    run.created_at = _coerce_str(events_sorted[0].get("timestamp"))
    last = events_sorted[-1]
    run.last_updated_at = _coerce_str(last.get("timestamp"))
    run.current_stage = _coerce_str(last.get("stage") or last.get("event_type"))

    stages_seen: list[str] = []
    warnings: list[str] = []
    blocking: list[str] = []
    lineage: list[str] = []
    final_review_decision = ""

    for event in events_sorted:
        stage = _coerce_str(event.get("stage"))
        if stage and stage not in stages_seen:
            stages_seen.append(stage)
        if not run.brand_key:
            data = event.get("data") or {}
            brand_key_candidate = _coerce_str((data or {}).get("brand_key") if isinstance(data, dict) else "")
            if brand_key_candidate:
                run.brand_key = brand_key_candidate
        if not run.material_type:
            run.material_type = _coerce_str(event.get("material_type"))
        if not run.mode:
            run.mode = _coerce_str(event.get("mode"))
        if not run.requested_goal:
            data = event.get("data") or {}
            if isinstance(data, dict):
                run.requested_goal = _coerce_str(data.get("goal") or data.get("requested_goal") or data.get("request"))
        for item in (event.get("warnings") or []):
            text = _coerce_str(item)
            if text and text not in warnings:
                warnings.append(text)
        data = event.get("data") or {}
        if isinstance(data, dict):
            for item in (data.get("blocking_issues") or []):
                text = _coerce_str(item)
                if text and text not in blocking:
                    blocking.append(text)
            decision_candidate = _coerce_str(data.get("decision"))
            if decision_candidate and stage in _REVIEW_STAGES:
                final_review_decision = decision_candidate
        version = _coerce_str(event.get("output_version"))
        if version and version not in lineage:
            lineage.append(version)
        _merge_artifact_pointers(run.artifact_ids, event)

    run.stages_completed = stages_seen
    run.warnings = warnings
    run.blocking_issues = blocking
    run.lineage = lineage

    last_status = _coerce_str(last.get("status"))
    last_stage = _coerce_str(last.get("stage"))
    if last_status == "blocked" or (blocking and last_status != "completed"):
        run.status = "blocked"
    elif last_stage in _COMPLETED_STAGES:
        run.status = "completed"
    elif last_stage in _REVIEW_STAGES and final_review_decision in _AWAITING_DECISIONS:
        run.status = "awaiting_review"
    elif last_status:
        run.status = last_status
    else:
        run.status = "in_progress"

    return run


def get_run(brand_dir: Path, workflow_id: str) -> Run | None:
    """Fetch a projected Run object by workflow_id, or None if no events."""
    events = load_run_events(brand_dir, workflow_id)
    if not events:
        return None
    return project_run(workflow_id, events)


def list_all_runs(
    brand_dir: Path,
    *,
    status: str | None = None,
    material_type: str | None = None,
    limit: int | None = None,
) -> list[Run]:
    """List projected Runs under brand_dir/runs/, newest first.

    Filter by status (``blocked``, ``awaiting_review``, ``in_progress``,
    ``completed``) and/or material_type. ``limit`` applies after sorting.
    """
    root = run_ledger_dir(brand_dir)
    runs: list[Run] = []
    for path in root.glob("*.jsonl"):
        workflow_id = path.stem
        events: list[dict[str, Any]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                parsed = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                events.append(parsed)
        if not events:
            continue
        run = project_run(workflow_id, events)
        if status and run.status != status:
            continue
        if material_type and run.material_type != material_type:
            continue
        runs.append(run)
    runs.sort(key=lambda item: item.last_updated_at or item.created_at, reverse=True)
    if limit is not None and limit > 0:
        runs = runs[:limit]
    return runs


def list_pending_reviews(brand_dir: Path, *, limit: int | None = None) -> list[Run]:
    """Runs currently awaiting human review. Used by brand_get_pending_reviews."""
    return list_all_runs(brand_dir, status="awaiting_review", limit=limit)
