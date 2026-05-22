"""Unit tests for the PR-0 harness control plane event/run schema and operations."""

import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

from brand_gen.harness import RunEvent, BrandRun, BrandSession, RunPolicy, ApprovalTrigger, run_async
from brand_gen.harness.run import RunRegistry
from brand_gen.commands.harness import (
    cmd_run_list,
    cmd_run_show,
    cmd_run_replay,
    cmd_rebuild_run_index,
)


class HarnessPr0Tests(unittest.TestCase):
    def test_run_event_serialization_deserialization(self):
        """Test that RunEvent to_dict and from_dict serialize and deserialize properly."""
        event = RunEvent(
            run_id="run-1",
            campaign_id="campaign-1",
            workflow_id="wf-1",
            stage="route",
            event_type="route_selected",
            attempt_id="v001",
            material_type="social",
            mode="hybrid",
            recommended_route="reference_translate",
            chosen_route="generative_explore",
            route_scores={"reference_translate": 0.9, "generative_explore": 0.2},
            selected_reference_paths=["/path/1", "/path/2"],
            selected_reference_ids=["ref-1", "ref-2"],
            model="flux-2-pro",
            provider="replicate",
            prompt_hash="xyz",
            source_version="v0",
            output_version="v1",
            cost=0.15,
            duration_ms=1200,
            status="completed",
            notes="this is a test",
            warnings=["warning-1"],
            branch_id="branch-1",
            parent_branch_id="parent-1",
            branch_status="active",
            selected_direction_id="direction-1",
            override_reason="manual override",
            override_actor="user",
            data={"custom_key": "custom_value"},
        )

        d = event.to_dict()
        self.assertEqual(d["schema_type"], "run_event")
        self.assertEqual(d["schema_version"], 1)
        self.assertEqual(d["run_id"], "run-1")
        self.assertEqual(d["campaign_id"], "campaign-1")
        self.assertEqual(d["workflow_id"], "wf-1")
        self.assertEqual(d["stage"], "route")
        self.assertEqual(d["event_type"], "route_selected")
        self.assertEqual(d["attempt_id"], "v001")
        self.assertEqual(d["material_type"], "social")
        self.assertEqual(d["mode"], "hybrid")
        self.assertEqual(d["recommended_route"], "reference_translate")
        self.assertEqual(d["chosen_route"], "generative_explore")
        self.assertEqual(d["route_scores"], {"reference_translate": 0.9, "generative_explore": 0.2})
        self.assertEqual(d["selected_reference_paths"], ["/path/1", "/path/2"])
        self.assertEqual(d["selected_reference_ids"], ["ref-1", "ref-2"])
        self.assertEqual(d["model"], "flux-2-pro")
        self.assertEqual(d["provider"], "replicate")
        self.assertEqual(d["prompt_hash"], "xyz")
        self.assertEqual(d["source_version"], "v0")
        self.assertEqual(d["output_version"], "v1")
        self.assertEqual(d["cost"], 0.15)
        self.assertEqual(d["duration_ms"], 1200)
        self.assertEqual(d["status"], "completed")
        self.assertEqual(d["notes"], "this is a test")
        self.assertEqual(d["warnings"], ["warning-1"])
        self.assertEqual(d["branch_id"], "branch-1")
        self.assertEqual(d["parent_branch_id"], "parent-1")
        self.assertEqual(d["branch_status"], "active")
        self.assertEqual(d["selected_direction_id"], "direction-1")
        self.assertEqual(d["override_reason"], "manual override")
        self.assertEqual(d["override_actor"], "user")
        self.assertEqual(d["data"], {"custom_key": "custom_value"})

        # Deserialize back
        deserialized = RunEvent.from_dict(d)
        self.assertEqual(deserialized.run_id, "run-1")
        self.assertEqual(deserialized.campaign_id, "campaign-1")
        self.assertEqual(deserialized.workflow_id, "wf-1")
        self.assertEqual(deserialized.stage, "route")
        self.assertEqual(deserialized.event_type, "route_selected")
        self.assertEqual(deserialized.route_scores, {"reference_translate": 0.9, "generative_explore": 0.2})
        self.assertEqual(deserialized.selected_reference_paths, ["/path/1", "/path/2"])
        self.assertEqual(deserialized.selected_reference_ids, ["ref-1", "ref-2"])
        self.assertEqual(deserialized.cost, 0.15)
        self.assertEqual(deserialized.warnings, ["warning-1"])
        self.assertEqual(deserialized.data, {"custom_key": "custom_value"})

    def test_run_event_deserialization_defaults(self):
        """Test that from_dict provides safe fallback defaults for missing/empty/None fields."""
        d = {"schema_type": "run_event", "schema_version": 2}
        event = RunEvent.from_dict(d)
        self.assertEqual(event.schema_type, "run_event")
        self.assertEqual(event.schema_version, 2)
        self.assertEqual(event.run_id, "")
        self.assertEqual(event.route_scores, {})
        self.assertEqual(event.selected_reference_paths, [])
        self.assertEqual(event.warnings, [])
        self.assertEqual(event.data, {})
        self.assertIsNone(event.cost)

    def test_brand_run_empty_replay(self):
        """Test replaying an empty BrandRun."""
        with tempfile.TemporaryDirectory() as tmp:
            run = BrandRun(
                run_id="run-1",
                campaign_id="camp-1",
                workflow_id="wf-1",
                brand_dir=Path(tmp),
            )
            state = run.replay()
            self.assertEqual(state["run_id"], "run-1")
            self.assertEqual(state["campaign_id"], "camp-1")
            self.assertEqual(state["workflow_id"], "wf-1")
            self.assertEqual(state["status"], "unknown")
            self.assertEqual(state["event_count"], 0)
            self.assertEqual(state["cost"], 0.0)

    def test_brand_run_replay_aggregation(self):
        """Test replaying events sequentially to aggregate status, cost, warnings, etc."""
        with tempfile.TemporaryDirectory() as tmp:
            events = [
                RunEvent(timestamp="2026-05-01T10:00:00", stage="route", event_type="started", status="in_progress", cost=0.01, warnings=["w1"], material_type="social"),
                RunEvent(timestamp="2026-05-01T10:01:00", stage="generate", event_type="gen_complete", status="completed", cost=0.05, warnings=["w2"], material_type="social"),
            ]
            run = BrandRun(
                run_id="run-1",
                campaign_id="camp-1",
                workflow_id="wf-1",
                brand_dir=Path(tmp),
                events=events,
            )
            state = run.replay()
            self.assertEqual(state["run_id"], "run-1")
            self.assertEqual(state["campaign_id"], "camp-1")
            self.assertEqual(state["workflow_id"], "wf-1")
            self.assertEqual(state["created_at"], "2026-05-01T10:00:00")
            self.assertEqual(state["last_updated_at"], "2026-05-01T10:01:00")
            self.assertEqual(state["status"], "completed")
            self.assertEqual(state["stage"], "generate")
            self.assertAlmostEqual(state["cost"], 0.06)
            self.assertEqual(state["event_count"], 2)
            self.assertEqual(sorted(state["warnings"]), ["w1", "w2"])
            self.assertEqual(state["material_type"], "social")

    def test_brand_run_load(self):
        """Test that BrandRun.load reads events correctly from a jsonl file."""
        with tempfile.TemporaryDirectory() as tmp:
            brand_dir = Path(tmp)
            runs_dir = brand_dir / "runs"
            runs_dir.mkdir()
            wf_file = runs_dir / "wf-1.jsonl"
            
            event1 = RunEvent(run_id="r1", campaign_id="c1", workflow_id="wf-1", stage="route", event_type="started")
            event2 = RunEvent(run_id="r1", campaign_id="c1", workflow_id="wf-1", stage="generate", event_type="completed")
            
            with wf_file.open("w", encoding="utf-8") as f:
                f.write(json.dumps(event1.to_dict()) + "\n")
                f.write("\n")  # Blank line check
                f.write("invalid json line\n")  # Parsing error resilience check
                f.write(json.dumps(event2.to_dict()) + "\n")

            run = BrandRun.load(brand_dir, "wf-1")
            self.assertEqual(run.run_id, "r1")
            self.assertEqual(run.campaign_id, "c1")
            self.assertEqual(run.workflow_id, "wf-1")
            self.assertEqual(len(run.events), 2)
            self.assertEqual(run.events[0].stage, "route")
            self.assertEqual(run.events[1].stage, "generate")

    def test_run_registry_rebuild_and_list_runs(self):
        """Test that RunRegistry lists and rebuilds index_entries cleanly."""
        with tempfile.TemporaryDirectory() as tmp:
            brand_dir = Path(tmp)
            runs_dir = brand_dir / "runs"
            runs_dir.mkdir()
            
            # Rebuild on empty dir
            entries = RunRegistry.rebuild_index(brand_dir)
            self.assertEqual(len(entries), 0)
            
            # Create a mock run file
            wf_file = runs_dir / "wf-mock.jsonl"
            event = RunEvent(run_id="run-mock", campaign_id="camp-mock", workflow_id="wf-mock", stage="generate", status="completed", cost=0.5, material_type="social")
            with wf_file.open("w", encoding="utf-8") as f:
                f.write(json.dumps(event.to_dict()) + "\n")

            # Rebuild index
            entries = RunRegistry.rebuild_index(brand_dir)
            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0]["run_id"], "run-mock")
            self.assertEqual(entries[0]["campaign_id"], "camp-mock")
            self.assertEqual(entries[0]["cost"], 0.5)

            # Test list_runs (should read from index.jsonl)
            listed = RunRegistry.list_runs(brand_dir)
            self.assertEqual(len(listed), 1)
            self.assertEqual(listed[0]["run_id"], "run-mock")

            # Test update_run_index
            updated_event = RunEvent(run_id="run-mock", campaign_id="camp-mock", workflow_id="wf-mock", stage="review", status="completed", cost=1.0, material_type="social")
            updated_run = BrandRun(run_id="run-mock", campaign_id="camp-mock", workflow_id="wf-mock", brand_dir=brand_dir, events=[updated_event])
            RunRegistry.update_run_index(brand_dir, updated_run)

            listed_after = RunRegistry.list_runs(brand_dir)
            self.assertEqual(len(listed_after), 1)
            self.assertEqual(listed_after[0]["cost"], 1.0)
            self.assertEqual(listed_after[0]["stage"], "review")

            # Test missing index triggers auto-rebuild in list_runs
            index_path = RunRegistry.get_index_path(brand_dir)
            index_path.unlink()
            
            listed_missing = RunRegistry.list_runs(brand_dir)
            self.assertEqual(len(listed_missing), 1)
            self.assertEqual(listed_missing[0]["run_id"], "run-mock")
            self.assertTrue(index_path.exists())

    def test_brand_session_run_lifecycle(self):
        """Test BrandSession run creation and automatic event logging/index updates."""
        with tempfile.TemporaryDirectory() as tmp:
            brand_dir = Path(tmp)
            policy = RunPolicy(max_generations=10, allowed_models=["flux"])
            session = BrandSession(brand_dir=brand_dir, run_policy=policy)

            self.assertIsNone(session.get_active_run())

            run = session.create_run(campaign_id="campaign-session", workflow_id="wf-session")
            self.assertEqual(session.get_active_run(), run)
            self.assertEqual(run.run_id, "wf-session")
            self.assertEqual(run.campaign_id, "campaign-session")

            # Log event through session
            event = RunEvent(stage="route", event_type="started", status="in_progress")
            session.log_event(event)

            # Assert event properties were auto-filled from active run context
            self.assertEqual(event.workflow_id, "wf-session")
            self.assertEqual(event.campaign_id, "campaign-session")
            self.assertEqual(event.run_id, "wf-session")

            # Verify saved run file
            wf_file = brand_dir / "runs" / "wf-session.jsonl"
            self.assertTrue(wf_file.exists())
            
            events = BrandRun.load(brand_dir, "wf-session").events
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0].stage, "route")

            # Verify index got updated
            runs = RunRegistry.list_runs(brand_dir)
            self.assertEqual(len(runs), 1)
            self.assertEqual(runs[0]["workflow_id"], "wf-session")
            self.assertEqual(runs[0]["stage"], "route")

            # Log event with no active run matching the event's workflow_id
            session._active_run = None
            event_orphan = RunEvent(workflow_id="wf-orphan", stage="orphan", status="completed")
            session.log_event(event_orphan)
            
            runs = RunRegistry.list_runs(brand_dir)
            self.assertEqual(len(runs), 2)
            self.assertEqual(sorted([r["workflow_id"] for r in runs]), ["wf-orphan", "wf-session"])

    def test_policy_definitions(self):
        """Test structure of RunPolicy and ApprovalTrigger dataclasses."""
        trigger = ApprovalTrigger(name="pre_paid_generation", mode="sync", budget_threshold=1.5)
        self.assertEqual(trigger.name, "pre_paid_generation")
        self.assertEqual(trigger.mode, "sync")
        self.assertEqual(trigger.budget_threshold, 1.5)

        policy = RunPolicy(
            max_generations=5,
            max_cost_estimate=2.0,
            allowed_models=["kling"],
            approval_triggers=[trigger],
        )
        self.assertEqual(policy.max_generations, 5)
        self.assertEqual(policy.max_cost_estimate, 2.0)
        self.assertEqual(policy.allowed_models, ["kling"])
        self.assertEqual(policy.approval_triggers, [trigger])

    def test_run_async_concurrency_helper(self):
        """Test run_async helper in standard sync context and when nested loop is mocked."""
        async def sample_coro():
            return 42

        # 1. Sync context with no event loop
        result = run_async(sample_coro())
        self.assertEqual(result, 42)

        # 2. Nested event loop mock context
        mock_loop = MagicMock()
        mock_loop.is_running.return_value = True
        with patch("asyncio.get_running_loop", return_value=mock_loop):
            result_nested = run_async(sample_coro())
            self.assertEqual(result_nested, 42)

    @patch("brand_gen.commands.harness.get_brand_dir")
    def test_cli_run_list(self, mock_get_brand_dir):
        """Test cmd_run_list execution and outputs for both text and json formatting."""
        with tempfile.TemporaryDirectory() as tmp:
            brand_dir = Path(tmp)
            mock_get_brand_dir.return_value = brand_dir
            
            # Setup some run logs with explicit timestamps
            session = BrandSession(brand_dir)
            session.create_run(campaign_id="camp-a", workflow_id="wf-a")
            session.log_event(RunEvent(timestamp="2026-05-22T00:00:00", stage="route", status="in_progress", cost=0.1, material_type="social"))
            session.log_event(RunEvent(timestamp="2026-05-22T00:00:01", stage="generate", status="completed", cost=0.2, material_type="social"))
            
            session.create_run(campaign_id="camp-b", workflow_id="wf-b")
            session.log_event(RunEvent(timestamp="2026-05-22T00:00:02", stage="route", status="failed", cost=0.5, material_type="video"))

            # Test JSON format
            args_json = MagicMock(status=None, material_type=None, limit=None, format="json")
            with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
                cmd_run_list(args_json)
                output = json.loads(mock_stdout.getvalue())
                self.assertEqual(output["count"], 2)
                self.assertEqual(output["runs"][0]["workflow_id"], "wf-b")  # default sorted newest first
                self.assertEqual(output["runs"][1]["workflow_id"], "wf-a")

            # Test Text format and filters
            args_text = MagicMock(status="completed", material_type="social", limit=1, format="text")
            with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
                cmd_run_list(args_text)
                txt = mock_stdout.getvalue()
                self.assertIn("wf-a", txt)
                self.assertNotIn("wf-b", txt)

    @patch("brand_gen.commands.harness.get_brand_dir")
    def test_cli_run_show(self, mock_get_brand_dir):
        """Test cmd_run_show displays detailed timeline for an existing run."""
        with tempfile.TemporaryDirectory() as tmp:
            brand_dir = Path(tmp)
            mock_get_brand_dir.return_value = brand_dir
            
            session = BrandSession(brand_dir)
            session.create_run(campaign_id="camp-a", workflow_id="wf-a")
            session.log_event(RunEvent(stage="route", event_type="started", status="in_progress", cost=0.1))
            session.log_event(RunEvent(stage="generate", event_type="done", status="completed", cost=0.2, warnings=["w1"]))

            # Test show JSON
            args_json = MagicMock(run_id="wf-a", format="json")
            with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
                cmd_run_show(args_json)
                output = json.loads(mock_stdout.getvalue())
                self.assertEqual(output["status"], "ok")
                self.assertEqual(output["workflow_id"], "wf-a")
                self.assertEqual(len(output["events"]), 2)

            # Test show Text
            args_text = MagicMock(run_id="wf-a", format="text")
            with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
                cmd_run_show(args_text)
                txt = mock_stdout.getvalue()
                self.assertIn("Workflow ID:   wf-a", txt)
                self.assertIn("started", txt)
                self.assertIn("done", txt)
                self.assertIn("- w1", txt)

            # Test run show not found
            args_missing = MagicMock(run_id="wf-missing", format="json")
            with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
                cmd_run_show(args_missing)
                output = json.loads(mock_stdout.getvalue())
                self.assertEqual(output["status"], "not_found")

    @patch("brand_gen.commands.harness.get_brand_dir")
    def test_cli_run_replay(self, mock_get_brand_dir):
        """Test cmd_run_replay constructs full cumulative state steps."""
        with tempfile.TemporaryDirectory() as tmp:
            brand_dir = Path(tmp)
            mock_get_brand_dir.return_value = brand_dir
            
            session = BrandSession(brand_dir)
            session.create_run(campaign_id="camp-a", workflow_id="wf-a")
            session.log_event(RunEvent(stage="route", event_type="started", status="in_progress", cost=0.1))
            session.log_event(RunEvent(stage="generate", event_type="done", status="completed", cost=0.2, warnings=["w1"]))

            args_json = MagicMock(run_id="wf-a", format="json")
            with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
                cmd_run_replay(args_json)
                output = json.loads(mock_stdout.getvalue())
                self.assertEqual(output["workflow_id"], "wf-a")
                self.assertEqual(len(output["steps"]), 2)
                self.assertAlmostEqual(output["steps"][0]["accumulated_cost"], 0.1)
                self.assertAlmostEqual(output["steps"][1]["accumulated_cost"], 0.3)

            args_text = MagicMock(run_id="wf-a", format="text")
            with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
                cmd_run_replay(args_text)
                txt = mock_stdout.getvalue()
                self.assertIn("Replaying Campaign Run: wf-a", txt)
                self.assertIn("Accumulated Cost: $0.30", txt)

    @patch("brand_gen.commands.harness.get_brand_dir")
    def test_cli_rebuild_run_index(self, mock_get_brand_dir):
        """Test cmd_rebuild_run_index successfully rebuilds Runs index."""
        with tempfile.TemporaryDirectory() as tmp:
            brand_dir = Path(tmp)
            mock_get_brand_dir.return_value = brand_dir
            
            session = BrandSession(brand_dir)
            session.create_run(campaign_id="camp-a", workflow_id="wf-a")
            session.log_event(RunEvent(stage="route", event_type="started", status="in_progress"))

            # Delete the index to make sure rebuild works
            index_path = RunRegistry.get_index_path(brand_dir)
            if index_path.exists():
                index_path.unlink()

            args_json = MagicMock(format="json")
            with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
                cmd_rebuild_run_index(args_json)
                output = json.loads(mock_stdout.getvalue())
                self.assertEqual(output["status"], "ok")
                self.assertEqual(output["entries_count"], 1)

            self.assertTrue(index_path.exists())


if __name__ == "__main__":
    unittest.main()
