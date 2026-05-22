"""Phase A: Run projection over the append-only run ledger.

Verifies:
  1. An empty ledger dir returns an empty list.
  2. A single-event ledger projects into a coherent Run object.
  3. Multi-stage events derive current_stage, status, artifact_ids, lineage.
  4. blocking_issues from event.data.blocking_issues and non-empty warnings
     flip the derived status to "blocked".
  5. A review stage with awaiting decision flips status to "awaiting_review".
  6. get_run returns None for an unknown workflow_id.
  7. list_all_runs sorts newest-first and applies filters + limit.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from brand_gen.run_ledger import append_run_event
from brand_gen.run_state import (
    Run,
    get_run,
    list_all_runs,
    list_pending_reviews,
    project_run,
)


class RunProjectionTests(unittest.TestCase):
    def test_empty_ledger_returns_empty_list(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(list_all_runs(Path(tmp)), [])

    def test_single_event_projection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            brand = Path(tmp)
            append_run_event(
                brand,
                workflow_id="abc123",
                stage="prepare_run",
                material_type="x-feed",
                mode="hybrid",
                status="in_progress",
                timestamp="2026-04-22T10:00:00",
            )
            runs = list_all_runs(brand)
            self.assertEqual(len(runs), 1)
            run = runs[0]
            self.assertEqual(run.run_id, "abc123")
            self.assertEqual(run.material_type, "x-feed")
            self.assertEqual(run.mode, "hybrid")
            self.assertEqual(run.current_stage, "prepare_run")
            self.assertEqual(run.status, "in_progress")
            self.assertEqual(run.event_count, 1)
            self.assertEqual(run.created_at, "2026-04-22T10:00:00")
            self.assertEqual(run.last_updated_at, "2026-04-22T10:00:00")

    def test_multi_stage_derives_current_stage_and_lineage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            brand = Path(tmp)
            append_run_event(
                brand,
                workflow_id="wf42",
                stage="prepare_run",
                material_type="concept-illustration",
                timestamp="2026-04-22T10:00:00",
                data={"goal": "hero for launch"},
            )
            append_run_event(
                brand,
                workflow_id="wf42",
                stage="plan_run",
                material_type="concept-illustration",
                timestamp="2026-04-22T10:01:00",
                data={"plan_path": "/tmp/plan-draft.json"},
            )
            append_run_event(
                brand,
                workflow_id="wf42",
                stage="execute_run",
                material_type="concept-illustration",
                timestamp="2026-04-22T10:02:00",
                output_version="v7",
                data={"scratchpad_path": "/tmp/scratchpad.json"},
            )
            run = get_run(brand, "wf42")
            self.assertIsNotNone(run)
            assert run is not None  # for type-checker
            self.assertEqual(run.current_stage, "execute_run")
            self.assertEqual(
                run.stages_completed,
                ["prepare_run", "plan_run", "execute_run"],
            )
            self.assertEqual(run.event_count, 3)
            self.assertEqual(run.lineage, ["v7"])
            self.assertEqual(run.requested_goal, "hero for launch")
            self.assertEqual(run.artifact_ids.get("plan_path"), "/tmp/plan-draft.json")
            self.assertEqual(run.artifact_ids.get("scratchpad_path"), "/tmp/scratchpad.json")
            self.assertEqual(run.artifact_ids.get("version_id"), "v7")
            # In-progress because last stage is execute, not evolve/review.
            self.assertEqual(run.status, "in_progress")

    def test_blocking_issues_flip_status_to_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            brand = Path(tmp)
            append_run_event(
                brand,
                workflow_id="wf-block",
                stage="validate_run",
                material_type="logo",
                timestamp="2026-04-22T11:00:00",
                status="blocked",
                warnings=["palette missing"],
                data={"blocking_issues": ["no reference role"]},
            )
            run = get_run(brand, "wf-block")
            assert run is not None
            self.assertEqual(run.status, "blocked")
            self.assertIn("no reference role", run.blocking_issues)
            self.assertIn("palette missing", run.warnings)

    def test_review_with_awaiting_decision(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            brand = Path(tmp)
            append_run_event(
                brand,
                workflow_id="wf-review",
                stage="execute_run",
                timestamp="2026-04-22T12:00:00",
                output_version="v3",
            )
            append_run_event(
                brand,
                workflow_id="wf-review",
                stage="review_run",
                timestamp="2026-04-22T12:01:00",
                data={"decision": "needs_refinement"},
            )
            run = get_run(brand, "wf-review")
            assert run is not None
            self.assertEqual(run.status, "awaiting_review")
            self.assertEqual(run.current_stage, "review_run")

    def test_evolve_terminal_stage_marks_completed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            brand = Path(tmp)
            append_run_event(brand, workflow_id="wf-done", stage="prepare_run", timestamp="2026-04-22T09:00:00")
            append_run_event(brand, workflow_id="wf-done", stage="evolve_run", timestamp="2026-04-22T09:05:00")
            run = get_run(brand, "wf-done")
            assert run is not None
            self.assertEqual(run.status, "completed")

    def test_get_run_returns_none_for_unknown(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(get_run(Path(tmp), "nonexistent"))

    def test_list_all_runs_filters_and_limit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            brand = Path(tmp)
            append_run_event(brand, workflow_id="wf-1", stage="prepare_run", material_type="x-feed", status="in_progress", timestamp="2026-04-22T10:00:00")
            append_run_event(brand, workflow_id="wf-2", stage="evolve_run", material_type="logo", timestamp="2026-04-22T11:00:00")
            append_run_event(brand, workflow_id="wf-3", stage="validate_run", material_type="logo", status="blocked", warnings=["x"], timestamp="2026-04-22T12:00:00", data={"blocking_issues": ["y"]})
            # Newest first by default.
            all_runs = list_all_runs(brand)
            self.assertEqual([r.run_id for r in all_runs], ["wf-3", "wf-2", "wf-1"])
            # Filter by status.
            completed = list_all_runs(brand, status="completed")
            self.assertEqual([r.run_id for r in completed], ["wf-2"])
            # Filter by material_type.
            logos = list_all_runs(brand, material_type="logo")
            self.assertEqual(sorted(r.run_id for r in logos), ["wf-2", "wf-3"])
            # Limit.
            top1 = list_all_runs(brand, limit=1)
            self.assertEqual(len(top1), 1)
            self.assertEqual(top1[0].run_id, "wf-3")

    def test_pending_reviews_helper(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            brand = Path(tmp)
            append_run_event(brand, workflow_id="wf-a", stage="review_run", timestamp="2026-04-22T10:00:00", data={"decision": "needs_refinement"})
            append_run_event(brand, workflow_id="wf-b", stage="evolve_run", timestamp="2026-04-22T11:00:00")
            pending = list_pending_reviews(brand)
            self.assertEqual([r.run_id for r in pending], ["wf-a"])


class CanonicalRegistrationTests(unittest.TestCase):
    """Phase A additions must be wired through the canonical registry."""

    def test_brand_list_runs_and_get_run_are_canonical(self) -> None:
        registry_path = Path(__file__).resolve().parents[1] / "packages" / "brand-gen-core" / "src" / "tool-registry.ts"
        text = registry_path.read_text(encoding="utf-8")
        self.assertIn('name: "brand_list_runs"', text)
        self.assertIn('name: "brand_get_run"', text)

    def test_inspection_allowlist_includes_run_verbs(self) -> None:
        from brand_gen.agent_specialization import AGENT_BY_ID

        strategist = AGENT_BY_ID["strategist"]
        self.assertIn("brand_list_runs", strategist.canonical_tools)
        self.assertIn("brand_get_run", strategist.canonical_tools)

    def test_bridges_registered(self) -> None:
        from brand_gen.mcp_bridge_registry import BRIDGE_BY_TOOL

        self.assertIn("brand_list_runs", BRIDGE_BY_TOOL)
        self.assertIn("brand_get_run", BRIDGE_BY_TOOL)
        self.assertTrue(BRIDGE_BY_TOOL["brand_list_runs"].read_only)


if __name__ == "__main__":
    unittest.main()
