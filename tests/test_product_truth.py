from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from brand_gen.plan_builder import create_material_plan
from brand_gen.plan_validation import validate_material_plan_dict
from brand_gen.product_truth import (
    render_product_truth_contract,
    sage_product_truth_prompt_moves,
    validate_product_truth_plan,
)
from brand_gen.prompt_assembly import build_execution_prompt, compact_execution_product_truth_contract
from brand_gen.sage_generation_contract import build_sage_vault_brief, repair_stale_sage_plan_contract


SAGE_IDENTITY = {
    "brand": {
        "name": "sage",
        "summary": "Governed skill network for AI agents.",
    },
    "messaging": {
        "value_propositions": [
            "Agents discover trusted reusable capabilities through skill libraries, prompt libraries, and MCP tools."
        ]
    },
}


class SageProductTruthTests(unittest.TestCase):
    def test_blocks_invented_product_taxonomy(self):
        report = validate_product_truth_plan(
            {
                "brand_dir": "/tmp/sage",
                "material_type": "social",
                "prompt_seed": "Hero card for a Prompt Pack and System of Provenance.",
            },
            identity=SAGE_IDENTITY,
        )
        self.assertTrue(report["errors"])
        self.assertTrue(any("invented_product_taxonomy" in item for item in report["errors"]))

    def test_allows_negated_banned_taxonomy_guardrails(self):
        contract = render_product_truth_contract(
            {
                "brand_dir": "/tmp/sage",
                "material_type": "social",
                "prompt_seed": "Show agents installing skills from libraries.",
            },
            identity=SAGE_IDENTITY,
        )
        report = validate_product_truth_plan(
            {
                "brand_dir": "/tmp/sage",
                "material_type": "social",
                "prompt_seed": (
                    "Show reusable skill cards flowing into agent runtimes. "
                    "No Prompt Pack, no fake dashboard, and no Approved Library Update stamp."
                ),
                "ban": ["Prompt Pack", "System of Provenance", "Approved Library Update", contract],
            },
            identity=SAGE_IDENTITY,
        )
        self.assertEqual(report["errors"], [])

    def test_allows_long_negated_fake_screen_guardrail_list(self):
        report = validate_product_truth_plan(
            {
                "brand_dir": "/tmp/sage",
                "material_type": "proof-poster",
                "prompt_seed": (
                    "Make an operator proof poster for the x-intel skill bundle. "
                    "Use a large deterministic proof module with five evidence rows: "
                    "Ingest, Clean, Extract, Score, Corroborate. "
                    "No QR code, source URL block, private preview badge, password/access text, "
                    "login interface, DAO/governance scene, generic AI hype, or fake app screen. "
                    "Prioritize distinct capability moments such as skill publishing, reusable skills, "
                    "prompt curation, and library discovery."
                ),
            },
            identity=SAGE_IDENTITY,
        )
        self.assertEqual(report["errors"], [])

    def test_blocks_fake_screen_after_contrastive_turn(self):
        report = validate_product_truth_plan(
            {
                "brand_dir": "/tmp/sage",
                "material_type": "proof-poster",
                "prompt_seed": (
                    "Show agents installing reusable skills from libraries. "
                    "No QR code, but create a fake app screen as the central proof module."
                ),
            },
            identity=SAGE_IDENTITY,
        )
        self.assertTrue(any("fake product modules" in item for item in report["errors"]))

    def test_blocks_affirmative_fake_product_screen(self):
        report = validate_product_truth_plan(
            {
                "brand_dir": "/tmp/sage",
                "material_type": "social",
                "prompt_seed": "Create a fake dashboard module for agents installing skills.",
            },
            identity=SAGE_IDENTITY,
        )
        self.assertTrue(any("fake product modules" in item for item in report["errors"]))

    def test_blocks_proposal_process_when_not_governance_education(self):
        report = validate_material_plan_dict(
            {
                "brand_dir": "/tmp/sage",
                "material_type": "feature-illustration",
                "purpose": "explain Sage",
                "target_surface": "social explainer",
                "product_truth_expression": "proposal review publish workflow",
                "abstraction_level": "medium",
                "brand_anchor_policy": {"rule": "Use Sage brand."},
                "system_mechanic": "proposal review publish",
                "preserve": ["Sage mark"],
                "push": ["proposal review publish flow"],
                "ban": ["generic art"],
                "prompt_seed": "Show proposal review publish as the main story.",
                "role_pack": {},
                "inspiration_translation": {},
            }
        )
        self.assertFalse(report["ok"])
        self.assertTrue(any("wrong_value_hero" in item for item in report["errors"]))

    def test_allows_governance_when_explicitly_requested(self):
        report = validate_product_truth_plan(
            {
                "brand_dir": "/tmp/sage",
                "material_type": "social",
                "entity_type": "proposal",
                "selected_surface_strategy": "governance_snapshot",
                "purpose": "governance education for a proposal detail page",
                "prompt_seed": "Explain proposal review and voting mechanics.",
            },
            identity=SAGE_IDENTITY,
        )
        self.assertEqual(report["errors"], [])

    def test_contract_prefers_capability_artifacts_and_subordinate_governance(self):
        contract = render_product_truth_contract(
            {
                "brand_dir": "/tmp/sage",
                "material_type": "data-card",
                "prompt_seed": "Show agents using skills.",
            },
            identity=SAGE_IDENTITY,
        )
        self.assertIn("agents gaining trusted reusable capabilities", contract)
        self.assertIn("Governance/review/promotion is a reason to trust", contract)
        self.assertIn("Text-heavy material rule", contract)
        self.assertIn("5-8% visual weight", contract)

    def test_plan_creation_injects_product_truth_moves_and_validation(self):
        with tempfile.TemporaryDirectory() as td:
            brand_dir = Path(td) / "sage"
            brand_dir.mkdir()
            identity_path = brand_dir / "brand-identity.json"
            identity_path.write_text("{}")
            plan, missing = create_material_plan(
                brand_dir=brand_dir,
                identity_path=identity_path,
                identity=SAGE_IDENTITY,
                material_type="social",
                mode="hybrid",
                mechanic="",
                preserve=[],
                push=[],
                ban=[],
                picks={},
                prompt_seed="Show agents installing skills from libraries.",
                purpose="show capability distribution",
                target_surface="social",
                accept_inspiration_recommendations=False,
            )
        self.assertEqual(missing, [])
        self.assertIn("product_truth_contract", plan)
        self.assertTrue(plan["product_truth_contract"])
        self.assertIn("skill/prompt libraries", " ".join(plan["push"]))
        self.assertTrue(any("Prompt Pack" in item for item in plan["ban"]))

    def test_plan_creation_injects_sage_vault_generation_contract(self):
        with tempfile.TemporaryDirectory() as td:
            brand_dir = Path(td) / "sage"
            brand_dir.mkdir()
            identity_path = brand_dir / "brand-identity.json"
            identity_path.write_text("{}")
            with patch("brand_gen.sage_generation_contract.build_source_knowledge_payload", return_value={"configured": False, "scanned_markdown_files": 0, "results": []}):
                plan, missing = create_material_plan(
                    brand_dir=brand_dir,
                    identity_path=identity_path,
                    identity=SAGE_IDENTITY,
                    material_type="poster",
                    mode="hybrid",
                    mechanic="",
                    preserve=[],
                    push=[],
                    ban=[],
                    picks={},
                    prompt_seed="Native illustration for Sage capability work: show a skill layer for AI agents.",
                    purpose="native Sage capability illustration",
                    target_surface="brand/product story illustration",
                    accept_inspiration_recommendations=False,
                )
        self.assertEqual(missing, [])
        self.assertEqual(plan["material_type"], "editorial-metaphor-illustration")
        self.assertTrue(plan["sage_generation_contract"]["applies"])
        self.assertIn("skill layer for AI agents", plan["prompt_seed"])
        self.assertIn("at most one small Sage logo", plan["brand_anchor_policy"]["rule"])
        self.assertTrue(any("repeated logos" in item for item in plan["ban"]))

    def test_sage_feature_illustration_without_product_carrier_routes_to_system_explainer(self):
        with tempfile.TemporaryDirectory() as td:
            brand_dir = Path(td) / "sage"
            brand_dir.mkdir()
            identity_path = brand_dir / "brand-identity.json"
            identity_path.write_text("{}")
            with patch("brand_gen.sage_generation_contract.build_source_knowledge_payload", return_value={"configured": False, "scanned_markdown_files": 0, "results": []}):
                plan, _ = create_material_plan(
                    brand_dir=brand_dir,
                    identity_path=identity_path,
                    identity=SAGE_IDENTITY,
                    material_type="feature-illustration",
                    mode="hybrid",
                    mechanic="",
                    preserve=[],
                    push=[],
                    ban=[],
                    picks={},
                    prompt_seed="Explain a routing workflow where a manifest installs a default into an agent runtime.",
                    purpose="system explainer for Sage capability work",
                    target_surface="native illustration",
                    accept_inspiration_recommendations=False,
                )
        self.assertEqual(plan["material_type"], "system-explainer-illustration")
        self.assertIn("no real base/product screenshot", plan["material_type_resolution"]["note"])

    def test_build_sage_vault_brief_preserves_approved_phrases_and_constraints(self):
        with tempfile.TemporaryDirectory() as td:
            brand_dir = Path(td) / "sage"
            brand_dir.mkdir()
            with patch("brand_gen.sage_generation_contract.build_source_knowledge_payload", return_value={"configured": False, "scanned_markdown_files": 0, "results": []}):
                brief = build_sage_vault_brief(
                    brand_dir=brand_dir,
                    identity=SAGE_IDENTITY,
                    profile={},
                    material_type="editorial-metaphor-illustration",
                    prompt_seed="Show a switchboard that selects a Behavior as an agent default.",
                )
        self.assertTrue(brief["applies"])
        self.assertIn("skill layer for AI agents", brief["approved_phrases"])
        self.assertIn("switchboard / exchange node", brief["illustration_concepts"])
        self.assertIn("no thread/loom/wardrobe/textile/closet metaphor", brief["hard_bans"])
        self.assertIn("no raw prompt dump / random capability card deck / glowing light-bulb idea icon", brief["hard_bans"])
        self.assertIn("no repeated logos", brief["hard_bans"])
        self.assertIn("Sage generation contract", brief["prompt_block"])

    def test_stale_sage_contract_repair_removes_positive_loom_language(self):
        plan = {
            "material_type": "stinger-animation",
            "prompt_seed": (
                "A crafted routing loom where a Sage Manifest threads a reusable Behavior into a thin agent harness. "
                "No thread/loom/wardrobe/textile/closet metaphor."
            ),
            "product_truth_expression": (
                "routing loom threads one reusable Behavior into a thin agent harness; "
                "the agent uses it as the default path to finish work"
            ),
            "ban": ["no thread/loom/wardrobe/textile/closet metaphor"],
            "sage_generation_contract": {
                "applies": True,
                "source_truth_phrase": "curated skills improve agent performance by +16.2pp",
                "adoption_scene": (
                    "routing loom threads one reusable Behavior into a thin agent harness; "
                    "the agent uses it as the default path to finish work"
                ),
                "style_anchor": "editorial metaphor illustration: routing loom, warm palette",
                "logo_rule": "one small Sage provenance/source seal only",
                "hard_bans": ["no repeated logos"],
            },
        }

        repaired, warnings = repair_stale_sage_plan_contract(plan)

        self.assertTrue(warnings)
        self.assertIn("switchboard", repaired["product_truth_expression"])
        self.assertIn("switchboard/control-room routing grid", repaired["prompt_seed"])
        self.assertIn("No thread/loom/wardrobe/textile/closet metaphor", repaired["prompt_seed"])
        contract = repaired["sage_generation_contract"]
        self.assertIn("switchboard", contract["adoption_scene"])
        self.assertNotIn("routing loom", contract["adoption_scene"].lower())
        self.assertIn("control-room routing grid", contract["style_anchor"])
        self.assertIn("no thread/loom/wardrobe/textile/closet metaphor", contract["hard_bans"])
        self.assertIn("glowing light-bulb idea icon", contract["prompt_block"])

    def test_execution_prompt_keeps_product_truth_when_aesthetic_is_dropped(self):
        context = {
            "material_prompt_key": "social",
            "material_prompt_snippet": "Social card policy.",
            "product_truth_contract": render_product_truth_contract(
                {"brand_dir": "/tmp/sage", "material_type": "social", "prompt_seed": "skills"},
                identity=SAGE_IDENTITY,
            ),
            "reference_role_pack": [],
            "aesthetic_capsule": {
                "id": "fake",
                "label": "Fake aesthetic",
                "prompt_lines": {"medium": "Very long aesthetic " * 40},
            },
        }
        result = build_execution_prompt(
            "Show agents installing curated skills.",
            context,
            material_type="social",
            generation_mode="image",
        )
        self.assertIn("Sage product-truth contract", result["execution_prompt"])
        self.assertNotIn("product_truth_contract", [item["id"] for item in result.get("dropped_blocks") or []])

    def test_execution_product_truth_uses_compact_structured_metadata(self):
        text = compact_execution_product_truth_contract(
            {
                "material_prompt_key": "proof_poster",
                "product_truth_metadata": {
                    "applies": True,
                    "hero_value": "agents gaining trusted reusable capabilities from governed skill and prompt libraries across multiple runtimes",
                    "proof_artifacts": [
                        "library manifest distributing skill cards",
                        "MCP tool card",
                        "workflow card",
                        "operator proof board",
                    ],
                    "trust_role": "governance and reputation establish trust but should not become the poster hero",
                    "avoid": [
                        "fake product taxonomy",
                        "fake app screens",
                        "logo-only hero",
                        "generic Web3 coin art",
                    ],
                    "logo_rule": "use a small subordinate Sage mark",
                },
                "product_truth_validation": {"applies": True},
            }
        )
        self.assertIn("Sage product-truth:", text)
        self.assertIn("show=", text)
        self.assertIn("proof=", text)
        self.assertLessEqual(len(text), 365)

    def test_execution_prompt_keeps_sage_contract_when_policy_is_dropped(self):
        context = {
            "material_prompt_key": "editorial_metaphor_illustration",
            "material_prompt_snippet": " ".join(f"Policy sentence {i}." for i in range(80)),
            "reference_role_pack": [],
            "sage_generation_contract": {
                "applies": True,
                "source_truth_phrase": "fat skills / thin harness",
                "adoption_scene": "Sage Manifest switchboard selects one reusable Behavior as the agent default",
                "style_anchor": "editorial metaphor illustration",
                "logo_rule": "one small Sage provenance/source seal only; never repeated, never the hero",
                "hard_bans": ["no repeated logos", "no trust layer as hero", "no governance process hero"],
                "brand_anchor_sources": ["palette", "routed/lattice/path motifs", "agent adoption/use scene"],
            },
        }
        result = build_execution_prompt(
            "Create a Sage editorial metaphor illustration. " * 20,
            context,
            material_type="editorial-metaphor-illustration",
            generation_mode="image",
        )
        prompt = result["execution_prompt"]
        dropped = [item["id"] for item in result.get("dropped_blocks") or []]
        self.assertIn("Sage generation contract", prompt)
        self.assertIn("fat skills / thin harness", prompt)
        self.assertIn("no repeated logos", prompt)
        self.assertNotIn("sage_generation_contract", dropped)


class ProductTruthMoveTests(unittest.TestCase):
    def test_moves_are_empty_for_non_sage(self):
        moves = sage_product_truth_prompt_moves(
            {"brand_dir": "/tmp/acme", "prompt_seed": "Brand poster"},
            identity={"brand": {"name": "acme"}},
        )
        self.assertEqual(moves, {"push": [], "ban": []})


if __name__ == "__main__":
    unittest.main()
