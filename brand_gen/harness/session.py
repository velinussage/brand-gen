"""Brand active session context, run logging, and state registry management."""

from __future__ import annotations

import json
from pathlib import Path

from brand_gen.harness.events import RunEvent
from brand_gen.harness.policy import RunPolicy
from brand_gen.harness.run import BrandRun, RunRegistry


class BrandSession:
    """Manages the active campaign-scoped run context and logs run events."""

    def __init__(self, brand_dir: Path, run_policy: RunPolicy | None = None):
        self.brand_dir = Path(brand_dir).expanduser().resolve()
        self.run_policy = run_policy or RunPolicy()
        self._active_run: BrandRun | None = None

    def get_active_run(self) -> BrandRun | None:
        """Retrieve the currently active BrandRun context, or None if none is active."""
        return self._active_run

    def create_run(self, campaign_id: str, workflow_id: str) -> BrandRun:
        """Create and register a new active campaign-scoped run in this session."""
        run = BrandRun(
            run_id=workflow_id,  # Default run_id to workflow_id
            campaign_id=campaign_id,
            workflow_id=workflow_id,
            brand_dir=self.brand_dir,
        )
        self._active_run = run
        return run

    def log_event(self, event: RunEvent) -> None:
        """Log a RunEvent to runs/<workflow_id>.jsonl and update the registry index layer."""
        # Supply active run contexts to event if they are not specified
        if not event.workflow_id and self._active_run:
            event.workflow_id = self._active_run.workflow_id
        if not event.campaign_id and self._active_run:
            event.campaign_id = self._active_run.campaign_id
        if not event.run_id and self._active_run:
            event.run_id = self._active_run.run_id

        workflow_id = event.workflow_id or "unknown"

        # Ensure directory exists
        runs_dir = self.brand_dir / "runs"
        runs_dir.mkdir(parents=True, exist_ok=True)
        jsonl_path = runs_dir / f"{workflow_id}.jsonl"

        # Append to jsonl file
        with jsonl_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event.to_dict(), default=str) + "\n")

        # Update the active run or reload/update the registry
        if self._active_run and self._active_run.workflow_id == workflow_id:
            self._active_run.events.append(event)
            RunRegistry.update_run_index(self.brand_dir, self._active_run)
        else:
            run = BrandRun.load(self.brand_dir, workflow_id)
            RunRegistry.update_run_index(self.brand_dir, run)
