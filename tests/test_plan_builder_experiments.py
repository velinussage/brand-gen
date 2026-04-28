from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from brand_gen.plan_builder import create_material_plan


class PlanBuilderExperimentTests(unittest.TestCase):
    def test_create_material_plan_preserves_aesthetic_variants(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            brand_dir = Path(td)
            identity_path = brand_dir / "brand-identity.json"
            identity_path.write_text(json.dumps({"brand": {"name": "Test"}}))
            plan, missing = create_material_plan(
                brand_dir=brand_dir,
                identity_path=identity_path,
                identity={"brand": {"name": "Test"}},
                material_type="social",
                mode="hybrid",
                mechanic="",
                preserve=[],
                push=[],
                ban=[],
                picks={},
                prompt_seed="Show three reusable capability paths.",
                purpose="explain reusable skills",
                target_surface="social",
                style_handle="screenprinted poster",
                accept_inspiration_recommendations=False,
            )
        self.assertEqual(missing, [])
        experiment = plan["experiment"]
        self.assertTrue(experiment["branch_id"].startswith("br_"))
        self.assertGreaterEqual(len(experiment["variants"]), 2)
        self.assertEqual(plan["branch_id"], experiment["branch_id"])
        selected = experiment["variants"][experiment["selected_variant_index"]]
        self.assertEqual(plan["selected_direction_id"], selected["variant_id"])

    def test_explicit_branch_parent_are_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            brand_dir = Path(td)
            identity_path = brand_dir / "brand-identity.json"
            identity_path.write_text(json.dumps({"brand": {"name": "Test"}}))
            plan, _ = create_material_plan(
                brand_dir=brand_dir,
                identity_path=identity_path,
                identity={"brand": {"name": "Test"}},
                material_type="social",
                mode="hybrid",
                mechanic="",
                preserve=[],
                push=[],
                ban=[],
                picks={},
                prompt_seed="One branch",
                branch_id="br_explicit",
                parent_branch_id="br_parent",
            )
        self.assertEqual(plan["branch_id"], "br_explicit")
        self.assertEqual(plan["experiment"]["parent_branch_id"], "br_parent")


if __name__ == "__main__":
    unittest.main()
