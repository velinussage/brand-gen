import tempfile
import unittest
from pathlib import Path

from brand_gen.brand_prompt_pack import ensure_brand_prompt_pack, render_pi_full_pipeline_prompt


class BrandPromptPackTests(unittest.TestCase):
    def test_rendered_prompt_is_brand_specific_not_sage_specific(self):
        prompt = render_pi_full_pipeline_prompt(
            brand_key="orbit-ops",
            profile={
                "brand_name": "Orbit Ops",
                "description": "Operational intelligence for distributed teams.",
                "keywords": ["operations", "distributed systems"],
                "messaging": {"value_propositions": ["Clear operational visibility"]},
            },
            identity={},
        )
        self.assertIn("Orbit Ops brand-gen full pipeline", prompt)
        self.assertIn("brand_switch_brand` for `orbit-ops`", prompt)
        self.assertIn("Clear operational visibility", prompt)
        self.assertNotIn("Sage visuals", prompt)
        self.assertNotIn("governed skill network", prompt)

    def test_ensure_prompt_pack_preserves_custom_prompt_without_force(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            brand_dir = Path(tmpdir) / "brands" / "acme"
            prompt_dir = brand_dir / "prompts"
            prompt_dir.mkdir(parents=True)
            prompt_path = prompt_dir / "pi-full-pipeline.md"
            prompt_path.write_text("custom prompt\n")

            ensure_brand_prompt_pack(brand_dir, profile={"brand_name": "Acme"}, identity={})
            self.assertEqual(prompt_path.read_text(), "custom prompt\n")

            ensure_brand_prompt_pack(brand_dir, profile={"brand_name": "Acme"}, identity={}, force=True)
            self.assertIn("Acme brand-gen full pipeline", prompt_path.read_text())


if __name__ == "__main__":
    unittest.main()
