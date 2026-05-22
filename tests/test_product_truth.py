from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from brand_gen.plan_builder import create_material_plan
from brand_gen.product_truth import (
    build_product_truth_metadata,
    is_sage_capability_context,
    render_product_truth_contract,
    sage_product_truth_prompt_moves,
    validate_product_truth_plan,
)
from brand_gen.runtime_models import MATERIAL_CONFIG
from brand_gen.material_prompt_profiles import get_material_prompt_profile


class ProductTruthCompatibilityTests(unittest.TestCase):
    def test_global_sage_detection_is_disabled(self):
        identity = {
            "brand": {
                "name": "Sage",
                "summary": "Governed skill network for AI agents.",
            }
        }
        plan = {
            "brand_dir": "/tmp/sage",
            "material_type": "social",
            "prompt_seed": "Sage libraries, MCP tools, and agents.",
        }

        self.assertFalse(is_sage_capability_context(identity=identity, plan=plan))
        self.assertEqual(render_product_truth_contract(plan, identity=identity), "")
        self.assertEqual(sage_product_truth_prompt_moves(plan, identity=identity), {"push": [], "ban": []})
        self.assertEqual(validate_product_truth_plan(plan, identity=identity)["errors"], [])
        self.assertFalse(build_product_truth_metadata(plan, identity=identity)["applies"])

    def test_non_sage_negative_guardrails_do_not_inject_other_brand_context(self):
        identity = {
            "brand": {
                "name": "Boon",
                "summary": "USDC gratitude tipping for GitHub and X public identities.",
            },
            "messaging": {"value_propositions": ["Turn praise into proof"]},
        }
        plan = {
            "brand_dir": "/tmp/boon",
            "material_type": "x-banner",
            "prompt_seed": "Create a Boon X profile header. No Sage, no MCP, no CLI, no libraries.",
            "ban": ["Sage", "MCP", "CLI", "libraries"],
        }
        self.assertFalse(is_sage_capability_context(identity=identity, plan=plan))
        self.assertEqual(render_product_truth_contract(plan, identity=identity), "")

    def test_x_banner_material_has_profile_header_dimensions(self):
        self.assertEqual(MATERIAL_CONFIG["x-banner"]["default_aspect_ratio"], "match_input_image")
        self.assertEqual(MATERIAL_CONFIG["x-banner"]["output_width"], 1500)
        self.assertEqual(MATERIAL_CONFIG["x-banner"]["output_height"], 500)
        profile = get_material_prompt_profile("x-banner")
        self.assertIsNotNone(profile)
        self.assertEqual(profile["web_delivery"]["display_width"], 1500)
        self.assertEqual(profile["web_delivery"]["display_height"], 500)

    def test_plan_creation_does_not_add_sage_contract_fields(self):
        with tempfile.TemporaryDirectory() as td:
            brand_dir = Path(td) / "boon"
            brand_dir.mkdir()
            identity_path = brand_dir / "brand-identity.json"
            identity_path.write_text("{}")
            identity = {
                "brand": {
                    "name": "Boon",
                    "summary": "USDC gratitude tipping for GitHub and X identities.",
                },
                "messaging": {"value_propositions": ["Turn praise into proof"]},
            }
            plan, missing = create_material_plan(
                brand_dir=brand_dir,
                identity_path=identity_path,
                identity=identity,
                material_type="x-banner",
                mode="reference",
                mechanic="",
                preserve=[],
                push=[],
                ban=["Sage", "MCP", "CLI"],
                picks={},
                prompt_seed="Create a Boon X profile header. No Sage, no MCP, no CLI.",
                purpose="Boon X profile header",
                target_surface="X profile header 1500x500",
                accept_inspiration_recommendations=False,
            )
        self.assertEqual(missing, [])
        self.assertEqual(plan["material_type"], "x-banner")
        self.assertNotIn("sage_generation_contract", plan)
        self.assertNotIn("sage_vault_brief", plan)
        self.assertNotIn("Use vault-sourced Sage phrase", " ".join(plan.get("push") or []))


if __name__ == "__main__":
    unittest.main()
