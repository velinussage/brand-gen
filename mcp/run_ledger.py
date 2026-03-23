from __future__ import annotations

import json
import time
from hashlib import sha256
from pathlib import Path
from typing import Any


def run_ledger_dir(brand_dir: Path) -> Path:
    path = Path(brand_dir).expanduser().resolve() / "runs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def run_ledger_path(brand_dir: Path, workflow_id: str) -> Path:
    return run_ledger_dir(brand_dir) / f"{str(workflow_id or 'unknown')}.jsonl"


def prompt_hash(prompt: str | None) -> str:
    text = str(prompt or "").strip()
    if not text:
        return ""
    return sha256(text.encode("utf-8")).hexdigest()[:16]


def append_run_event(
    brand_dir: Path,
    workflow_id: str,
    *,
    stage: str,
    event_type: str | None = None,
    attempt_id: str | None = None,
    material_type: str | None = None,
    mode: str | None = None,
    recommended_route: str | None = None,
    chosen_route: str | None = None,
    route_scores: dict[str, float] | None = None,
    selected_reference_paths: list[str] | None = None,
    selected_reference_ids: list[str] | None = None,
    model: str | None = None,
    provider: str | None = None,
    prompt: str | None = None,
    source_version: str | None = None,
    output_version: str | None = None,
    cost: float | int | None = None,
    duration_ms: int | None = None,
    status: str | None = None,
    notes: str | None = None,
    warnings: list[str] | None = None,
    branch_id: str | None = None,
    parent_branch_id: str | None = None,
    branch_status: str | None = None,
    selected_direction_id: str | None = None,
    override_reason: str | None = None,
    override_actor: str | None = None,
    data: dict[str, Any] | None = None,
    timestamp: str | None = None,
) -> Path:
    record = {
        "schema_type": "run_event",
        "schema_version": 1,
        "timestamp": timestamp or time.strftime("%Y-%m-%dT%H:%M:%S"),
        "workflow_id": str(workflow_id or ""),
        "stage": str(stage or ""),
        "event_type": str(event_type or stage or ""),
        "attempt_id": str(attempt_id or ""),
        "material_type": str(material_type or ""),
        "mode": str(mode or ""),
        "recommended_route": str(recommended_route or ""),
        "chosen_route": str(chosen_route or ""),
        "route_scores": dict(route_scores or {}),
        "selected_reference_paths": [str(item) for item in (selected_reference_paths or []) if str(item).strip()],
        "selected_reference_ids": [str(item) for item in (selected_reference_ids or []) if str(item).strip()],
        "model": str(model or ""),
        "provider": str(provider or ""),
        "prompt_hash": prompt_hash(prompt),
        "source_version": str(source_version or ""),
        "output_version": str(output_version or ""),
        "cost": cost,
        "duration_ms": duration_ms,
        "status": str(status or ""),
        "notes": str(notes or ""),
        "warnings": [str(item) for item in (warnings or []) if str(item).strip()],
        "branch_id": str(branch_id or ""),
        "parent_branch_id": str(parent_branch_id or ""),
        "branch_status": str(branch_status or ""),
        "selected_direction_id": str(selected_direction_id or ""),
        "override_reason": str(override_reason or ""),
        "override_actor": str(override_actor or ""),
        "data": dict(data or {}),
    }
    path = run_ledger_path(brand_dir, workflow_id)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, default=str) + "\n")
    return path


def load_run_events(brand_dir: Path, workflow_id: str) -> list[dict[str, Any]]:
    path = run_ledger_path(brand_dir, workflow_id)
    if not path.exists():
        return []
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
    return events


def load_all_run_events(brand_dir: Path, *, limit: int | None = None) -> list[dict[str, Any]]:
    root = run_ledger_dir(brand_dir)
    events: list[dict[str, Any]] = []
    for path in sorted(root.glob("*.jsonl")):
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
    events.sort(key=lambda item: str(item.get("timestamp") or ""))
    if limit is not None and limit > 0:
        events = events[-limit:]
    return events
