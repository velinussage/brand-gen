"""Campaign-scoped runs management, event replay, and index rebuild operations."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from brand_gen.harness.events import RunEvent


class BrandRun:
    """Manages campaign-scoped runs, run event history, and state projection."""

    def __init__(
        self,
        run_id: str,
        campaign_id: str,
        workflow_id: str,
        brand_dir: Path,
        events: list[RunEvent] | None = None,
    ):
        self.run_id = run_id
        self.campaign_id = campaign_id
        self.workflow_id = workflow_id
        self.brand_dir = Path(brand_dir)
        self.events = events or []

    @classmethod
    def load(cls, brand_dir: Path, workflow_id: str) -> BrandRun:
        """Load a run and parse its events from runs/<workflow_id>.jsonl."""
        brand_dir = Path(brand_dir)
        runs_dir = brand_dir / "runs"
        jsonl_path = runs_dir / f"{workflow_id}.jsonl"
        events: list[RunEvent] = []
        run_id = ""
        campaign_id = ""

        if jsonl_path.exists():
            with jsonl_path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        event = RunEvent.from_dict(data)
                        events.append(event)
                        if not run_id and event.run_id:
                            run_id = event.run_id
                        if not campaign_id and event.campaign_id:
                            campaign_id = event.campaign_id
                    except Exception:
                        continue

        if not run_id:
            run_id = workflow_id

        return cls(
            run_id=run_id,
            campaign_id=campaign_id,
            workflow_id=workflow_id,
            brand_dir=brand_dir,
            events=events,
        )

    def replay(self) -> dict[str, Any]:
        """Fold/replay event history to reconstruct and project the run's latest index metadata."""
        if not self.events:
            return {
                "run_id": self.run_id,
                "campaign_id": self.campaign_id,
                "workflow_id": self.workflow_id,
                "created_at": "",
                "last_updated_at": "",
                "status": "unknown",
                "stage": "",
                "cost": 0.0,
                "event_count": 0,
                "warnings": [],
                "timestamp": "",
                "material_type": "",
            }

        sorted_events = sorted(self.events, key=lambda e: e.timestamp)
        first_event = sorted_events[0]
        last_event = sorted_events[-1]

        total_cost = 0.0
        warnings: list[str] = []
        material_type = ""
        for e in sorted_events:
            if e.cost is not None:
                total_cost += float(e.cost)
            if e.warnings:
                for w in e.warnings:
                    if w and w not in warnings:
                        warnings.append(w)
            if not material_type and e.material_type:
                material_type = e.material_type

        # Update run_id and campaign_id if they are present in events
        for e in reversed(sorted_events):
            if e.run_id:
                self.run_id = e.run_id
            if e.campaign_id:
                self.campaign_id = e.campaign_id

        return {
            "run_id": self.run_id,
            "campaign_id": self.campaign_id,
            "workflow_id": self.workflow_id,
            "created_at": first_event.timestamp,
            "last_updated_at": last_event.timestamp,
            "status": last_event.status or "in_progress",
            "stage": last_event.stage,
            "cost": total_cost,
            "event_count": len(self.events),
            "warnings": warnings,
            "timestamp": first_event.timestamp,
            "material_type": material_type,
        }


class RunRegistry:
    """Index layer registry for reading, writing, and rebuilding runs/_index.jsonl."""

    @classmethod
    def get_index_path(cls, brand_dir: Path) -> Path:
        """Get the absolute path to the runs/_index.jsonl file."""
        return Path(brand_dir).expanduser().resolve() / "runs" / "_index.jsonl"

    @classmethod
    def read_index(cls, brand_dir: Path) -> list[dict[str, Any]]:
        """Read all run summaries from the _index.jsonl file."""
        index_path = cls.get_index_path(brand_dir)
        if not index_path.exists():
            return []

        entries: list[dict[str, Any]] = []
        with index_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entries.append(json.loads(line))
                except Exception:
                    continue
        return entries

    @classmethod
    def write_index(cls, brand_dir: Path, index_entries: list[dict[str, Any]]) -> None:
        """Write all run summaries to the _index.jsonl file."""
        index_path = cls.get_index_path(brand_dir)
        index_path.parent.mkdir(parents=True, exist_ok=True)
        with index_path.open("w", encoding="utf-8") as f:
            for entry in index_entries:
                f.write(json.dumps(entry) + "\n")

    @classmethod
    def update_run_index(cls, brand_dir: Path, run: BrandRun) -> None:
        """Insert or update a single run's summary in the index layer."""
        summary = run.replay()
        entries = cls.read_index(brand_dir)

        updated = False
        for idx, entry in enumerate(entries):
            if entry.get("workflow_id") == run.workflow_id:
                entries[idx] = summary
                updated = True
                break

        if not updated:
            entries.append(summary)

        cls.write_index(brand_dir, entries)

    @classmethod
    def list_runs(cls, brand_dir: Path) -> list[dict[str, Any]]:
        """List campaign runs via the index layer. Rebuilds the index if it is missing."""
        index_path = cls.get_index_path(brand_dir)
        if not index_path.exists():
            return cls.rebuild_index(brand_dir)
        return cls.read_index(brand_dir)

    @classmethod
    def rebuild_index(cls, brand_dir: Path) -> list[dict[str, Any]]:
        """Rebuild the runs/_index.jsonl index layer from all runs/*.jsonl source files."""
        brand_dir = Path(brand_dir)
        runs_dir = brand_dir / "runs"
        if not runs_dir.exists():
            return []

        entries: list[dict[str, Any]] = []
        for path in sorted(runs_dir.glob("*.jsonl")):
            if path.name == "_index.jsonl":
                continue
            workflow_id = path.stem
            run = BrandRun.load(brand_dir, workflow_id)
            if run.events:
                entries.append(run.replay())

        cls.write_index(brand_dir, entries)
        return entries
