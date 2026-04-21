from __future__ import annotations

import argparse
import contextlib
import io
import json
import tempfile
import unittest
import warnings
from pathlib import Path
from unittest import mock

from brand_gen.command_registry import COMMAND_HANDLERS
from brand_gen.commands import review as review_commands
from brand_gen.commands import state as state_commands
from brand_gen.custom_scratchpad import append_forbidden_pattern, load_custom_scratchpad_json
from brand_gen.learnings_memory import load_learnings_memory
from brand_gen.mcp_bridge_registry import BRIDGE_BY_TOOL
from brand_gen.run_ledger import load_all_run_events


class AppendForbiddenPatternCommandTests(unittest.TestCase):
    def test_append_writes_scratchpad_and_ledger_event(self):
        with tempfile.TemporaryDirectory() as tmp:
            brand_dir = Path(tmp)
            args = argparse.Namespace(
                pattern="purple gradients",
                reason="slop tell",
                source_version="v032",
                dry_run=False,
                format="json",
            )
            out = io.StringIO()
            with mock.patch.object(state_commands, "get_brand_dir", return_value=brand_dir), contextlib.redirect_stdout(out):
                state_commands.cmd_append_forbidden_pattern(args)

            payload = json.loads(out.getvalue())
            self.assertEqual(payload["status"], "appended")
            self.assertFalse(payload["duplicate"])
            scratchpad = load_custom_scratchpad_json(brand_dir)
            self.assertEqual(scratchpad["forbidden_patterns"][0]["pattern"], "purple gradients")
            events = load_all_run_events(brand_dir)
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0]["event_type"], "forbidden_pattern_appended")
            self.assertEqual(events[0]["data"]["pattern"], "purple gradients")

    def test_append_duplicate_is_noop_but_audited(self):
        with tempfile.TemporaryDirectory() as tmp:
            brand_dir = Path(tmp)
            append_forbidden_pattern(brand_dir, pattern="purple gradients", via_cli=True)
            args = argparse.Namespace(
                pattern="purple gradients",
                reason="still banned",
                source_version="v033",
                dry_run=False,
                format="json",
            )
            out = io.StringIO()
            with mock.patch.object(state_commands, "get_brand_dir", return_value=brand_dir), contextlib.redirect_stdout(out):
                state_commands.cmd_append_forbidden_pattern(args)

            payload = json.loads(out.getvalue())
            self.assertEqual(payload["status"], "duplicate")
            scratchpad = load_custom_scratchpad_json(brand_dir)
            self.assertEqual(len(scratchpad["forbidden_patterns"]), 1)
            events = load_all_run_events(brand_dir)
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0]["status"], "duplicate")

    def test_append_dry_run_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            brand_dir = Path(tmp)
            args = argparse.Namespace(
                pattern="purple gradients",
                reason="slop tell",
                source_version="v032",
                dry_run=True,
                format="json",
            )
            out = io.StringIO()
            with mock.patch.object(state_commands, "get_brand_dir", return_value=brand_dir), contextlib.redirect_stdout(out):
                state_commands.cmd_append_forbidden_pattern(args)

            payload = json.loads(out.getvalue())
            self.assertEqual(payload["status"], "would_append")
            self.assertEqual(load_custom_scratchpad_json(brand_dir)["forbidden_patterns"], [])
            self.assertEqual(load_all_run_events(brand_dir), [])

    def test_direct_helper_emits_deprecation_warning(self):
        with tempfile.TemporaryDirectory() as tmp:
            brand_dir = Path(tmp)
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                append_forbidden_pattern(brand_dir, pattern="purple gradients")
            self.assertTrue(any(item.category is DeprecationWarning for item in caught))

    def test_append_handles_legacy_string_entries(self):
        with tempfile.TemporaryDirectory() as tmp:
            brand_dir = Path(tmp)
            (brand_dir / "custom-scratchpad.json").write_text(json.dumps({"forbidden_patterns": ["purple gradients"]}))
            args = argparse.Namespace(
                pattern="purple gradients",
                reason="still banned",
                source_version="v040",
                dry_run=False,
                format="json",
            )
            out = io.StringIO()
            with mock.patch.object(state_commands, "get_brand_dir", return_value=brand_dir), contextlib.redirect_stdout(out):
                state_commands.cmd_append_forbidden_pattern(args)

            payload = json.loads(out.getvalue())
            self.assertEqual(payload["status"], "duplicate")
            self.assertEqual(payload["total_forbidden_patterns"], 1)

    def test_direct_helper_handles_legacy_string_entries(self):
        with tempfile.TemporaryDirectory() as tmp:
            brand_dir = Path(tmp)
            (brand_dir / "custom-scratchpad.json").write_text(json.dumps({"forbidden_patterns": ["purple gradients"]}))
            append_forbidden_pattern(brand_dir, pattern="green halos", via_cli=True)
            scratchpad = load_custom_scratchpad_json(brand_dir)
            patterns = [item["pattern"] for item in scratchpad["forbidden_patterns"]]
            self.assertEqual(patterns, ["purple gradients", "green halos"])


class PromoteLearningCommandTests(unittest.TestCase):
    def test_promote_learning_writes_memory_and_ledger_event(self):
        with tempfile.TemporaryDirectory() as tmp:
            brand_dir = Path(tmp)
            args = argparse.Namespace(
                bucket="failurePatterns",
                text="Avoid flat neutral backgrounds",
                material_type="concept-illustration",
                evidence_version=["v032"],
                dry_run=False,
                format="json",
            )
            out = io.StringIO()
            with mock.patch.object(state_commands, "get_brand_dir", return_value=brand_dir), contextlib.redirect_stdout(out):
                state_commands.cmd_promote_learning(args)

            payload = json.loads(out.getvalue())
            self.assertEqual(payload["status"], "promoted")
            memory = load_learnings_memory(brand_dir)
            self.assertEqual(memory["failurePatterns"][0]["text"], "Avoid flat neutral backgrounds")
            events = load_all_run_events(brand_dir)
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0]["event_type"], "learning_promoted")
            self.assertEqual(events[0]["data"]["bucket"], "failurePatterns")

    def test_promote_learning_dry_run_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            brand_dir = Path(tmp)
            args = argparse.Namespace(
                bucket="failurePatterns",
                text="Avoid flat neutral backgrounds",
                material_type="concept-illustration",
                evidence_version=["v032"],
                dry_run=True,
                format="json",
            )
            out = io.StringIO()
            with mock.patch.object(state_commands, "get_brand_dir", return_value=brand_dir), contextlib.redirect_stdout(out):
                state_commands.cmd_promote_learning(args)

            payload = json.loads(out.getvalue())
            self.assertEqual(payload["status"], "would_promote")
            self.assertEqual(load_learnings_memory(brand_dir)["failurePatterns"], [])
            self.assertEqual(load_all_run_events(brand_dir), [])

    def test_promote_learning_detects_duplicate_legacy_string_entries(self):
        with tempfile.TemporaryDirectory() as tmp:
            brand_dir = Path(tmp)
            (brand_dir / "learnings.json").write_text(json.dumps({"failurePatterns": ["Avoid flat neutral backgrounds"]}))
            args = argparse.Namespace(
                bucket="failurePatterns",
                text="Avoid flat neutral backgrounds",
                material_type="concept-illustration",
                evidence_version=["v032"],
                dry_run=False,
                format="json",
            )
            out = io.StringIO()
            with mock.patch.object(state_commands, "get_brand_dir", return_value=brand_dir), contextlib.redirect_stdout(out):
                state_commands.cmd_promote_learning(args)

            payload = json.loads(out.getvalue())
            self.assertEqual(payload["status"], "duplicate")
            self.assertTrue(payload["duplicate"])
            self.assertEqual(payload["total_in_bucket"], 1)
            events = load_all_run_events(brand_dir)
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0]["status"], "duplicate")


class SubmitReviewCommandTests(unittest.TestCase):
    def test_submit_review_dry_run_previews_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            brand_dir = Path(tmp)
            critique_path = brand_dir / "critique.json"
            critique_path.write_text(json.dumps({"p1": ["bad text"], "p2": ["spacing"]}))
            args = argparse.Namespace(
                version="v012",
                critique_json=str(critique_path),
                dry_run=True,
                format="json",
            )
            manifest = {"versions": {"v012": {"material_type": "social"}}}
            out = io.StringIO()
            with (
                mock.patch.object(review_commands, "get_brand_dir", return_value=brand_dir),
                mock.patch.object(review_commands, "load_manifest", return_value=manifest),
                contextlib.redirect_stdout(out),
            ):
                review_commands.cmd_submit_review(args)

            payload = json.loads(out.getvalue())
            self.assertEqual(payload["status"], "dry_run")
            self.assertFalse(payload["approved"])
            self.assertEqual(payload["p1_count"], 1)
            self.assertFalse((brand_dir / "reviews" / "v012-vlm-critique.json").exists())

    def test_submit_review_live_delegates_to_submit_critique(self):
        args = argparse.Namespace(version="v012", critique_json="{}", dry_run=False, format="json")
        with mock.patch.object(review_commands, "cmd_submit_critique", return_value={"ok": True}) as patched:
            result = review_commands.cmd_submit_review(args)
        self.assertEqual(result, {"ok": True})
        patched.assert_called_once_with(args)


class RegistrationTests(unittest.TestCase):
    def test_new_commands_are_registered_for_cli_and_mcp(self):
        self.assertIn("append-forbidden-pattern", COMMAND_HANDLERS)
        self.assertIn("promote-learning", COMMAND_HANDLERS)
        self.assertIn("submit-review", COMMAND_HANDLERS)
        self.assertIn("brand_append_forbidden_pattern", BRIDGE_BY_TOOL)
        self.assertIn("brand_promote_learning", BRIDGE_BY_TOOL)
        self.assertIn("brand_submit_review", BRIDGE_BY_TOOL)


if __name__ == "__main__":
    unittest.main()
