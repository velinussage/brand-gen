import argparse
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mcp.commands.generation import cmd_derive_mockup


class MockupDerivativeTests(unittest.TestCase):
    def test_cmd_derive_mockup_builds_payload_from_source_still(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            brand_dir = Path(tmpdir).resolve()
            source_image = brand_dir / "v001-social.png"
            source_image.write_bytes(b"fake-image")
            (brand_dir / "v001.prompts.json").write_text(json.dumps({"execution_prompt": "Original still prompt."}))

            manifest = {
                "versions": {
                    "v001": {
                        "files": [source_image.name],
                        "material_type": "social",
                        "mode": "hybrid",
                        "aspect_ratio": "1:1",
                        "workflow_id": "wf-source",
                        "branch_id": "wf-source",
                        "selected_reference_ids": ["ref-1"],
                        "selected_inspiration_ids": ["insp-1"],
                    }
                }
            }
            args = argparse.Namespace(
                source_version="v001",
                material_type="device-mockup",
                prompt=None,
                model=None,
                aspect_ratio=None,
                tag=None,
                negative_prompt="no clutter",
                profile=None,
                identity=None,
                format="json",
            )

            with patch("mcp.commands.generation.get_brand_dir", return_value=brand_dir), \
                 patch("mcp.commands.generation.load_manifest", return_value=manifest), \
                 patch("mcp.commands.generation.load_brand_memory", return_value=(brand_dir / "brand-profile.json", brand_dir / "brand-identity.json", {}, {})), \
                 patch("mcp.commands.generation.persist_generation_scratchpad_to_blackboard"), \
                 patch("mcp.commands.generation.append_run_event"), \
                 patch("mcp.commands.generation.execute_generation_scratchpad", return_value="v002") as execute_mock, \
                 patch("sys.stdout.write") as stdout_write:
                cmd_derive_mockup(args)

            payload = execute_mock.call_args.args[0]
            self.assertEqual(payload["source_version"], "v001")
            self.assertEqual(payload["material_type"], "device-mockup")
            self.assertEqual(payload["generation_mode"], "image")
            self.assertEqual(payload["derivative_mode"], "generated_mockup_scene")
            self.assertEqual(payload["reference_context"]["passed_reference_paths"], [str(source_image)])
            self.assertEqual(payload["execution"]["negative_prompt"], "no clutter")
            self.assertIn("Original still prompt.", payload["execution_prompt"])
            printed = "".join(call.args[0] for call in stdout_write.call_args_list)
            self.assertIn('"version_id": "v002"', printed)
            self.assertIn('"mockup_mode": "generated_scene_not_precise_composite"', printed)


if __name__ == "__main__":
    unittest.main()
