"""Phase 6 invariant: blackboard state survives save/load via services.

This is the foundation for the eventual ledger-rebuild path (Phase 6b):
for now, blackboard.json remains the primary storage and the run ledger
is a side channel. This test locks in the invariant that the service
facade's save/load cycle is lossless, so when we later rewire the read
path to be a projection-over-ledger the service-level guarantee won't
change.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path


class BlackboardRoundtripTests(unittest.TestCase):
    def setUp(self) -> None:
        from brand_gen.services import OrchestrationService

        self.OrchestrationService = OrchestrationService

    def test_load_empty_blackboard_returns_shaped_dict(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            orch = self.OrchestrationService(Path(tmpdir))
            board = orch.load_blackboard()
            self.assertIsInstance(board, dict)
            # The default shape has these keys even on empty workspaces
            for key in ("decisions",):
                self.assertIn(key, board)

    def test_append_decision_then_save_then_reload(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            orch = self.OrchestrationService(Path(tmpdir))
            board = orch.load_blackboard()
            board = orch.append_decision(
                board,
                agent="test-critic",
                decision="approve",
                data={"note": "roundtrip smoke"},
            )
            orch.save(board)

            # Reload from disk through a fresh service instance.
            orch2 = self.OrchestrationService(Path(tmpdir))
            reloaded = orch2.load_blackboard()
            decisions = reloaded.get("decisions") or []
            self.assertGreaterEqual(len(decisions), 1)
            latest = decisions[-1]
            self.assertEqual(latest.get("agent"), "test-critic")
            self.assertEqual(latest.get("decision"), "approve")

    def test_summarize_matches_blackboard_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            orch = self.OrchestrationService(Path(tmpdir))
            board = orch.load_blackboard()
            board = orch.append_decision(board, agent="agent-a", decision="first")
            board = orch.append_decision(board, agent="agent-b", decision="second")
            orch.save(board)

            summary = orch.summarize()
            self.assertIn("latest_decisions", summary)
            self.assertEqual(len(summary["latest_decisions"]), 2)
            self.assertEqual(summary["latest_decisions"][-1].get("agent"), "agent-b")

    def test_rotation_state_is_empty_on_fresh_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            orch = self.OrchestrationService(Path(tmpdir))
            state = orch.rotation_state("concept-illustration")
            self.assertEqual(state["material_type"], "concept-illustration")
            self.assertEqual(state["recent_style_anchors"], [])
            self.assertEqual(state["recent_archetypes"], [])

    def test_rotation_record_then_state_shows_it(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            orch = self.OrchestrationService(Path(tmpdir))
            orch.record_style_anchor(
                material_type="concept-illustration",
                anchor_version="v012",
                anchor_set_size=5,
            )
            state = orch.rotation_state("concept-illustration")
            self.assertEqual(state["last_style_anchor"], "v012")
            self.assertIn("v012", state["recent_style_anchors"])

    def test_emit_stage_event_appends_to_ledger(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            brand_dir = Path(tmpdir)
            orch = self.OrchestrationService(brand_dir)
            workflow_id = "roundtrip-workflow"
            orch.emit_stage_event(
                workflow_id=workflow_id,
                stage="prepare_run",
                event_type="prepare_run_started",
                status="ok",
                notes="smoke-test",
            )
            ledger_path = brand_dir / "runs" / f"{workflow_id}.jsonl"
            self.assertTrue(ledger_path.exists(), f"Ledger file not created at {ledger_path}")
            events = [json.loads(line) for line in ledger_path.read_text().splitlines() if line.strip()]
            self.assertGreaterEqual(len(events), 1)
            self.assertEqual(events[-1].get("event_type"), "prepare_run_started")


if __name__ == "__main__":
    unittest.main()
