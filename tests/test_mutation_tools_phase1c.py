from __future__ import annotations

import argparse
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from brand_gen.command_registry import COMMAND_HANDLERS
from brand_gen.commands import state as state_commands
from brand_gen.mcp_bridge_registry import BRIDGE_BY_TOOL, build_tool_schema
from brand_gen.run_ledger import load_all_run_events


class MotionGrammarCommandTests(unittest.TestCase):
    def test_set_motion_grammar_writes_json_and_markdown(self):
        with tempfile.TemporaryDirectory() as tmp:
            brand_dir = Path(tmp)
            args = argparse.Namespace(
                director="monumental-compression",
                favored=["slow dolly", "calm reveal"],
                banned=["crash zoom"],
                intensity="steady",
                dry_run=False,
                format="json",
            )
            out = io.StringIO()
            with mock.patch.object(state_commands, "get_brand_dir", return_value=brand_dir), contextlib.redirect_stdout(out):
                state_commands.cmd_set_motion_grammar(args)

            payload = json.loads(out.getvalue())
            self.assertEqual(payload["status"], "set")
            scratch_json = json.loads((brand_dir / "custom-scratchpad.json").read_text())
            self.assertEqual(scratch_json["motion_grammar"]["director"], "monumental-compression")
            md = (brand_dir / "custom-scratchpad.md").read_text()
            self.assertIn("## Motion grammar", md)
            self.assertIn("Director token: monumental-compression", md)
            self.assertIn("Favored moves: slow dolly; calm reveal", md)
            events = load_all_run_events(brand_dir)
            self.assertEqual(events[0]["event_type"], "motion_grammar_set")

    def test_set_motion_grammar_dry_run_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            brand_dir = Path(tmp)
            args = argparse.Namespace(
                director="monumental-compression",
                favored=["slow dolly"],
                banned=["crash zoom"],
                intensity="steady",
                dry_run=True,
                format="json",
            )
            out = io.StringIO()
            with mock.patch.object(state_commands, "get_brand_dir", return_value=brand_dir), contextlib.redirect_stdout(out):
                state_commands.cmd_set_motion_grammar(args)
            payload = json.loads(out.getvalue())
            self.assertEqual(payload["status"], "would_set")
            self.assertFalse((brand_dir / "custom-scratchpad.json").exists())
            self.assertFalse((brand_dir / "custom-scratchpad.md").exists())

    def test_set_motion_grammar_recovers_from_malformed_sidecar_shapes(self):
        with tempfile.TemporaryDirectory() as tmp:
            brand_dir = Path(tmp)
            (brand_dir / "custom-scratchpad.json").write_text(
                json.dumps(
                    {
                        "model_overrides_by_material": "bad-shape",
                        "forbidden_patterns": "also-bad",
                        "motion_grammar": "legacy-string",
                    }
                )
            )
            args = argparse.Namespace(
                director="monumental-compression",
                favored=["slow dolly"],
                banned=["crash zoom"],
                intensity="steady",
                dry_run=False,
                format="json",
            )
            out = io.StringIO()
            with mock.patch.object(state_commands, "get_brand_dir", return_value=brand_dir), contextlib.redirect_stdout(out):
                state_commands.cmd_set_motion_grammar(args)

            payload = json.loads(out.getvalue())
            self.assertEqual(payload["status"], "set")
            scratch_json = json.loads((brand_dir / "custom-scratchpad.json").read_text())
            self.assertEqual(scratch_json["motion_grammar"]["director"], "monumental-compression")
            self.assertEqual(scratch_json["forbidden_patterns"], [])


class PromoteStylePolicyCommandTests(unittest.TestCase):
    def test_promote_style_policy_writes_structured_entry(self):
        with tempfile.TemporaryDirectory() as tmp:
            brand_dir = Path(tmp)
            args = argparse.Namespace(
                material_type="concept-illustration",
                anchor=["v012", "v021"],
                apply_to=["concept-illustration"],
                reference_policy="rotating_anchor_set",
                style_anchor_role="style",
                text="Rotate style anchors across accepted versions",
                evidence_version=["v012"],
                must_carry_forward=["warm palette discipline"],
                failure_mode_if_missing="style drift",
                model_behavior_note="Do not reuse the prior anchor",
                correction_note="Pick exactly one anchor per run",
                source="typed_mutation_tool",
                dry_run=False,
                format="json",
            )
            out = io.StringIO()
            with mock.patch.object(state_commands, "get_brand_dir", return_value=brand_dir), contextlib.redirect_stdout(out):
                state_commands.cmd_promote_style_policy(args)

            payload = json.loads(out.getvalue())
            self.assertEqual(payload["status"], "promoted")
            learnings = json.loads((brand_dir / "learnings.json").read_text())
            entry = learnings["styleReferencePolicies"][0]
            self.assertEqual(entry["material_type"], "concept-illustration")
            self.assertEqual(entry["required_style_reference_versions"], ["v012", "v021"])
            self.assertEqual(entry["reference_policy"], "rotating_anchor_set")
            self.assertEqual(entry["must_carry_forward"], ["warm palette discipline"])
            events = load_all_run_events(brand_dir)
            self.assertEqual(events[0]["event_type"], "style_policy_promoted")

    def test_promote_style_policy_dry_run_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            brand_dir = Path(tmp)
            args = argparse.Namespace(
                material_type="concept-illustration",
                anchor=["v012"],
                apply_to=["concept-illustration"],
                reference_policy="single_style_anchor",
                style_anchor_role="style",
                text="Keep one style anchor",
                evidence_version=[],
                must_carry_forward=[],
                failure_mode_if_missing="",
                model_behavior_note="",
                correction_note="",
                source="typed_mutation_tool",
                dry_run=True,
                format="json",
            )
            out = io.StringIO()
            with mock.patch.object(state_commands, "get_brand_dir", return_value=brand_dir), contextlib.redirect_stdout(out):
                state_commands.cmd_promote_style_policy(args)
            payload = json.loads(out.getvalue())
            self.assertEqual(payload["status"], "would_promote")
            self.assertFalse((brand_dir / "learnings.json").exists())

    def test_promote_style_policy_dry_run_matches_text_dedupe_behavior(self):
        with tempfile.TemporaryDirectory() as tmp:
            brand_dir = Path(tmp)
            (brand_dir / "learnings.json").write_text(
                json.dumps(
                    {
                        "styleReferencePolicies": [
                            {
                                "text": "Keep one style anchor",
                                "material_type": "concept-illustration",
                                "required_style_reference_versions": ["v001"],
                                "reference_policy": "single_style_anchor",
                            }
                        ]
                    }
                )
            )
            args = argparse.Namespace(
                material_type="concept-illustration",
                anchor=["v012"],
                apply_to=["concept-illustration"],
                reference_policy="rotating_anchor_set",
                style_anchor_role="style",
                text="Keep one style anchor",
                evidence_version=[],
                must_carry_forward=[],
                failure_mode_if_missing="",
                model_behavior_note="",
                correction_note="",
                source="typed_mutation_tool",
                dry_run=True,
                format="json",
            )
            out = io.StringIO()
            with mock.patch.object(state_commands, "get_brand_dir", return_value=brand_dir), contextlib.redirect_stdout(out):
                state_commands.cmd_promote_style_policy(args)
            payload = json.loads(out.getvalue())
            self.assertEqual(payload["status"], "duplicate")
            self.assertTrue(payload["duplicate"])


class RegistrationTests(unittest.TestCase):
    def test_phase1c_commands_registered_for_cli_and_mcp(self):
        for command in ["set-motion-grammar", "promote-style-policy"]:
            self.assertIn(command, COMMAND_HANDLERS)
        for tool_name in ["brand_set_motion_grammar", "brand_promote_style_policy"]:
            self.assertIn(tool_name, BRIDGE_BY_TOOL)

    def test_promote_style_policy_schema_requires_anchor(self):
        bridge = BRIDGE_BY_TOOL["brand_promote_style_policy"]
        schema = build_tool_schema(bridge)
        self.assertIn("anchor", schema.get("required", []))


if __name__ == "__main__":
    unittest.main()
