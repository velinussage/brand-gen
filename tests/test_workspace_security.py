import argparse
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mcp.commands.generation import cmd_generate
from mcp.generation_flow import execute_generation_scratchpad
from mcp.runtime_brand import ensure_path_within_root, validate_brand_workspace_dir


class WorkspaceSecurityTests(unittest.TestCase):
    def test_ensure_path_within_root_accepts_descendant(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir).resolve()
            child = root / "nested" / "file.json"

            resolved = ensure_path_within_root(child, root, label="scratchpad")

            self.assertEqual(resolved, child.resolve())

    def test_validate_brand_workspace_dir_rejects_non_active_workspace(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir).resolve()
            active_brand_dir = root / ".brand-gen" / "brands" / "active"
            rogue_brand_dir = root / ".brand-gen" / "brands" / "other"

            with patch("mcp.runtime_brand.get_brand_dir", return_value=active_brand_dir):
                with self.assertRaises(SystemExit) as exc:
                    validate_brand_workspace_dir(rogue_brand_dir, label="scratchpad brand_dir")

            self.assertIn(str(active_brand_dir.resolve()), str(exc.exception))
            self.assertIn(str(rogue_brand_dir.resolve()), str(exc.exception))

    def test_cmd_generate_rejects_scratchpad_brand_dir_outside_active_workspace(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir).resolve()
            active_brand_dir = root / ".brand-gen" / "brands" / "active"
            rogue_brand_dir = root / "escape"
            scratchpad_path = root / "scratchpad.json"
            scratchpad_path.write_text(json.dumps({"brand_dir": str(rogue_brand_dir)}))

            args = argparse.Namespace(
                scratchpad=str(scratchpad_path),
                max_iterations=1,
                skip_vlm=False,
                internal_vlm_critique=False,
                vlm_critique=None,
            )

            with patch("mcp.runtime_brand.get_brand_dir", return_value=active_brand_dir), \
                 patch("mcp.commands.generation.execute_generation_scratchpad") as execute_mock:
                with self.assertRaises(SystemExit):
                    cmd_generate(args)

            execute_mock.assert_not_called()

    def test_execute_generation_scratchpad_rejects_brand_dir_outside_active_workspace(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir).resolve()
            active_brand_dir = root / ".brand-gen" / "brands" / "active"
            rogue_brand_dir = root / "escape"
            payload = {
                "schema_type": "generation_scratchpad",
                "brand_dir": str(rogue_brand_dir),
                "checks": {"blocking": [], "warnings": []},
            }

            with patch("mcp.runtime_brand.get_brand_dir", return_value=active_brand_dir):
                with self.assertRaises(SystemExit) as exc:
                    execute_generation_scratchpad(payload)

            self.assertIn(str(active_brand_dir.resolve()), str(exc.exception))
            self.assertIn(str(rogue_brand_dir.resolve()), str(exc.exception))


if __name__ == "__main__":
    unittest.main()
