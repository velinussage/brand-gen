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
from brand_gen.commands import identity as identity_commands
from brand_gen.commands import state as state_commands
from brand_gen.mcp_bridge_registry import BRIDGE_BY_TOOL
from brand_gen.run_ledger import load_all_run_events


class AppendCustomScratchpadNoteTests(unittest.TestCase):
    def test_append_note_writes_section_and_ledger(self):
        with tempfile.TemporaryDirectory() as tmp:
            brand_dir = Path(tmp)
            args = argparse.Namespace(section="global", text="No floating proof panels", dry_run=False, format="json")
            out = io.StringIO()
            with mock.patch.object(state_commands, "get_brand_dir", return_value=brand_dir), contextlib.redirect_stdout(out):
                state_commands.cmd_append_custom_scratchpad_note(args)

            payload = json.loads(out.getvalue())
            self.assertEqual(payload["status"], "appended")
            md = (brand_dir / "custom-scratchpad.md").read_text()
            self.assertIn("## Global bans", md)
            self.assertIn("- No floating proof panels", md)
            events = load_all_run_events(brand_dir)
            self.assertEqual(events[0]["event_type"], "scratchpad_note_appended")

    def test_append_note_dry_run_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            brand_dir = Path(tmp)
            args = argparse.Namespace(section="motion", text="No crash zooms", dry_run=True, format="json")
            out = io.StringIO()
            with mock.patch.object(state_commands, "get_brand_dir", return_value=brand_dir), contextlib.redirect_stdout(out):
                state_commands.cmd_append_custom_scratchpad_note(args)
            payload = json.loads(out.getvalue())
            self.assertEqual(payload["status"], "would_append")
            self.assertFalse((brand_dir / "custom-scratchpad.md").exists())
            self.assertEqual(load_all_run_events(brand_dir), [])


class UpdatePaletteTests(unittest.TestCase):
    def test_update_palette_writes_identity_and_audit(self):
        with tempfile.TemporaryDirectory() as tmp:
            brand_dir = Path(tmp)
            (brand_dir / "brand-identity.json").write_text(json.dumps({"schema_version": 3}) + "\n")
            args = argparse.Namespace(role="primary", hex="#B85C38", identity=None, dry_run=False, format="json")
            out = io.StringIO()
            with mock.patch.object(identity_commands, "get_brand_dir", return_value=brand_dir), contextlib.redirect_stdout(out):
                identity_commands.cmd_update_palette(args)
            payload = json.loads(out.getvalue())
            self.assertEqual(payload["status"], "updated")
            self.assertEqual(payload["role"], "primary")
            saved = json.loads((brand_dir / "brand-identity.json").read_text())
            self.assertEqual(saved["brand_colors"]["primary"], "#B85C38")
            self.assertIn("#B85C38", saved["identity_core"]["must_preserve"]["palette_direction"])
            self.assertIn("primary: #B85C38", saved["design_language"]["semantic_palette_roles"])
            events = load_all_run_events(brand_dir)
            self.assertEqual(events[0]["event_type"], "palette_updated")

    def test_update_palette_dry_run_does_not_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            brand_dir = Path(tmp)
            original = {"schema_version": 3}
            (brand_dir / "brand-identity.json").write_text(json.dumps(original) + "\n")
            args = argparse.Namespace(role="primary", hex="#B85C38", identity=None, dry_run=True, format="json")
            out = io.StringIO()
            with mock.patch.object(identity_commands, "get_brand_dir", return_value=brand_dir), contextlib.redirect_stdout(out):
                identity_commands.cmd_update_palette(args)
            payload = json.loads(out.getvalue())
            self.assertEqual(payload["status"], "would_update")
            saved = json.loads((brand_dir / "brand-identity.json").read_text())
            self.assertEqual(saved, original)


class UpdateTypographyAndDevicesTests(unittest.TestCase):
    def test_update_typography_writes_roles_and_cues(self):
        with tempfile.TemporaryDirectory() as tmp:
            brand_dir = Path(tmp)
            (brand_dir / "brand-identity.json").write_text(json.dumps({"schema_version": 3}) + "\n")
            args = argparse.Namespace(role="display", family="Fraunces", fallback="Georgia, serif", identity=None, dry_run=False, format="json")
            out = io.StringIO()
            with mock.patch.object(identity_commands, "get_brand_dir", return_value=brand_dir), contextlib.redirect_stdout(out):
                identity_commands.cmd_update_typography(args)
            payload = json.loads(out.getvalue())
            self.assertEqual(payload["role"], "display")
            saved = json.loads((brand_dir / "brand-identity.json").read_text())
            self.assertEqual(saved["typography"]["headings"], "Fraunces")
            self.assertEqual(saved["typography"]["fallbacks"]["display"], "Georgia, serif")
            self.assertEqual(saved["identity_core"]["must_preserve"]["typography_roles"]["display"], "Fraunces")

    def test_update_devices_adds_and_removes(self):
        with tempfile.TemporaryDirectory() as tmp:
            brand_dir = Path(tmp)
            seed = {"schema_version": 3, "identity_core": {"approved_graphic_devices": ["one decisive mark", "pattern atmosphere"]}}
            (brand_dir / "brand-identity.json").write_text(json.dumps(seed) + "\n")
            args = argparse.Namespace(add=["quiet editorial fields"], remove=["pattern atmosphere"], identity=None, dry_run=False, format="json")
            out = io.StringIO()
            with mock.patch.object(identity_commands, "get_brand_dir", return_value=brand_dir), contextlib.redirect_stdout(out):
                identity_commands.cmd_update_devices(args)
            payload = json.loads(out.getvalue())
            self.assertEqual(payload["status"], "updated")
            saved = json.loads((brand_dir / "brand-identity.json").read_text())
            self.assertEqual(saved["identity_core"]["approved_graphic_devices"], ["one decisive mark", "quiet editorial fields"])


class RegistrationTests(unittest.TestCase):
    def test_phase1b_commands_registered_for_cli_and_mcp(self):
        for command in [
            "append-custom-scratchpad-note",
            "update-palette",
            "update-typography",
            "update-devices",
        ]:
            self.assertIn(command, COMMAND_HANDLERS)
        for tool_name in [
            "brand_append_custom_scratchpad_note",
            "brand_update_palette",
            "brand_update_typography",
            "brand_update_devices",
        ]:
            self.assertIn(tool_name, BRIDGE_BY_TOOL)


if __name__ == "__main__":
    unittest.main()
