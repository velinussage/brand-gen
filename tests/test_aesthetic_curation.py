from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from brand_gen.aesthetic_curation import (
    build_aesthetic_direction_brief,
    get_aesthetic_capsule,
    list_aesthetic_capsules,
    promote_aesthetic_learning,
    render_capsule_prompt,
    select_aesthetic_capsule,
)
from brand_gen.plan_builder import create_material_plan
from brand_gen.pipeline_request import PipelineRequest
from brand_gen.prompt_assembly import build_execution_prompt


class AestheticCapsuleRegistryTests(unittest.TestCase):
    def test_social_has_multiple_capsules(self):
        capsules = list_aesthetic_capsules("social")
        ids = {item["id"] for item in capsules}
        self.assertIn("warm-editorial-system-illustration", ids)
        self.assertIn("screenprinted-proof-poster", ids)

    def test_style_handle_maps_ghibli_to_safe_capsule(self):
        selection = select_aesthetic_capsule(
            material_type="concept-illustration",
            style_text="make it feel like a ghibli aesthetic",
        )
        self.assertEqual(selection["capsule_id"], "pastoral-storybook-animation")
        self.assertEqual(selection["source"], "style_handle")
        rendered = render_capsule_prompt(selection["capsule"])
        self.assertIn("pastoral storybook animation", rendered.lower())
        self.assertIn("Style strength", rendered)
        self.assertIn("Reference roles", rendered)
        self.assertNotIn("Ghibli", rendered)

    def test_direction_brief_returns_contrasting_moodboard_branches(self):
        brief = build_aesthetic_direction_brief(
            material_type="social",
            style_text="screenprinted poster",
            count=3,
        )
        self.assertEqual(brief["schema_type"], "aesthetic_direction_brief")
        self.assertGreaterEqual(len(brief["variants"]), 2)
        self.assertEqual(brief["variants"][0]["capsule_id"], "screenprinted-proof-poster")
        self.assertTrue(brief["variants"][0]["difference_axes"])
        self.assertIn("reference_roles", brief["variants"][0])

    def test_prompt_injects_capsule_block(self):
        capsule = get_aesthetic_capsule("screenprinted-proof-poster")
        result = build_execution_prompt(
            "Create a proof poster with one evidence payload.",
            {
                "material_prompt_key": "campaign_poster",
                "material_prompt_snippet": "Proof poster policy.",
                "reference_role_pack": [],
                "aesthetic_capsule": capsule,
                "aesthetic_capsule_id": capsule["id"],
            },
            material_type="proof-poster",
            generation_mode="image",
        )
        sections = result.get("execution_prompt_sections") or {}
        self.assertIn("aesthetic_capsule_block", sections)
        self.assertIn("Screenprinted proof poster", sections["aesthetic_capsule_block"])
        self.assertIn("large proof payload", result.get("execution_prompt") or "")


class AestheticCapsulePlanningTests(unittest.TestCase):
    def test_pipeline_request_preserves_style_fields(self):
        request = PipelineRequest.from_mapping(
            {
                "material_type": "social",
                "style_handle": "screenprinted poster",
                "aesthetic_capsule": "screenprinted-proof-poster",
            }
        )
        ns = request.to_namespace()
        self.assertEqual(ns.style_handle, "screenprinted poster")
        self.assertEqual(ns.aesthetic_capsule, "screenprinted-proof-poster")

    def test_plan_selects_capsule_from_style_handle(self):
        with tempfile.TemporaryDirectory() as td:
            brand_dir = Path(td)
            identity_path = brand_dir / "brand-identity.json"
            identity_path.write_text(json.dumps({"brand": {"name": "Test"}}))
            plan, missing = create_material_plan(
                brand_dir=brand_dir,
                identity_path=identity_path,
                identity={"brand": {"name": "Test"}},
                material_type="system-explainer-illustration",
                mode="hybrid",
                mechanic="",
                preserve=[],
                push=[],
                ban=[],
                picks={},
                prompt_seed="Show a warm product system without DAO assumptions.",
                purpose="explain reusable skills",
                target_surface="social",
                style_handle="ghibli aesthetic",
                accept_inspiration_recommendations=False,
            )
        self.assertEqual(missing, [])
        self.assertEqual(plan["aesthetic_capsule_id"], "pastoral-storybook-animation")
        self.assertEqual(plan["aesthetic_capsule_selection"]["source"], "style_handle")
        self.assertEqual(plan["aesthetic_direction_brief"]["schema_type"], "aesthetic_direction_brief")
        self.assertEqual(plan["aesthetic_reference_roles"]["style"], "hand-painted pastoral storybook warmth")

    def test_promote_aesthetic_learning_selects_material_preference(self):
        with tempfile.TemporaryDirectory() as td:
            brand_dir = Path(td)
            result = promote_aesthetic_learning(
                brand_dir,
                capsule_id="warm-editorial-system-illustration",
                material_type="social",
                sentiment="like",
                note="Worked better than DAO theater.",
            )
            self.assertEqual(result["status"], "positive_recorded")
            selection = select_aesthetic_capsule(brand_dir=brand_dir, material_type="social")
            self.assertEqual(selection["capsule_id"], "warm-editorial-system-illustration")
            self.assertIn("brand_selected_for_material", selection["reasons"])


if __name__ == "__main__":
    unittest.main()
