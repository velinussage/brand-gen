import tempfile
import unittest
from pathlib import Path

from mcp.run_ledger import append_run_event, load_all_run_events, load_run_events, prompt_hash


class RunLedgerTests(unittest.TestCase):
    def test_append_and_load_run_events(self):
        with tempfile.TemporaryDirectory() as tmp:
            brand_dir = Path(tmp)
            append_run_event(
                brand_dir,
                "wf-123",
                stage="route",
                event_type="route_selected",
                material_type="social",
                mode="hybrid",
                recommended_route="reference_translate",
                chosen_route="generative_explore",
                route_scores={"reference_translate": 0.9, "generative_explore": 0.2},
                notes="agent override",
            )
            append_run_event(
                brand_dir,
                "wf-123",
                stage="generate",
                event_type="generation_completed",
                attempt_id="v001",
                material_type="social",
                mode="hybrid",
                model="recraft-v4",
                prompt="hello world",
                output_version="v001",
                status="ok",
            )

            events = load_run_events(brand_dir, "wf-123")
            self.assertEqual(len(events), 2)
            self.assertEqual(events[0]["event_type"], "route_selected")
            self.assertEqual(events[1]["output_version"], "v001")
            self.assertEqual(events[1]["prompt_hash"], prompt_hash("hello world"))

    def test_branch_fields_persist_in_events(self):
        with tempfile.TemporaryDirectory() as tmp:
            brand_dir = Path(tmp)
            append_run_event(
                brand_dir,
                "wf-branch",
                stage="generate",
                event_type="generation_completed",
                attempt_id="v001",
                status="ok",
                branch_id="wf-branch",
                parent_branch_id="wf-parent",
                branch_status="active",
                selected_direction_id="dir-abc",
            )
            events = load_run_events(brand_dir, "wf-branch")
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0]["branch_id"], "wf-branch")
            self.assertEqual(events[0]["parent_branch_id"], "wf-parent")
            self.assertEqual(events[0]["branch_status"], "active")
            self.assertEqual(events[0]["selected_direction_id"], "dir-abc")

    def test_override_fields_persist_in_events(self):
        with tempfile.TemporaryDirectory() as tmp:
            brand_dir = Path(tmp)
            append_run_event(
                brand_dir,
                "wf-override",
                stage="route",
                event_type="route_selected",
                recommended_route="reference_translate",
                chosen_route="generative_explore",
                override_reason="user_explicit",
                override_actor="agent",
                status="ok",
            )
            events = load_run_events(brand_dir, "wf-override")
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0]["override_reason"], "user_explicit")
            self.assertEqual(events[0]["override_actor"], "agent")
            self.assertEqual(events[0]["recommended_route"], "reference_translate")
            self.assertEqual(events[0]["chosen_route"], "generative_explore")

    def test_load_all_run_events_respects_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            brand_dir = Path(tmp)
            append_run_event(brand_dir, "wf-1", stage="route", event_type="route_selected", status="ok")
            append_run_event(brand_dir, "wf-2", stage="route", event_type="route_selected", status="ok")

            events = load_all_run_events(brand_dir, limit=1)
            self.assertEqual(len(events), 1)


if __name__ == "__main__":
    unittest.main()
