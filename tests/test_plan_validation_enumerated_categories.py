"""Tests for the enumerated-categories detector in plan critique.

Covers the v062 / v163-168 / v176-178 failure cluster: when a prompt
seed lists N>=4 named categories in parentheses and the plan also
carries a text ban ("textless", "no labels", "no headlines"), the
image model keeps rendering the names as labels despite the ban.
The detector fires a warning by default and escalates to an error
when a text ban is present in the plan.
"""
from __future__ import annotations

import unittest

from brand_gen.plan_validation import (
    detect_enumerated_categories,
    plan_has_text_ban,
)


class DetectEnumeratedCategoriesTests(unittest.TestCase):
    def test_detects_six_category_enumeration(self):
        text = (
            "Textless asymmetric composition. Show six differentiated habitats "
            "(skills forge, prompt curation atelier, library discovery stacks, "
            "provenance/review checkpoints, CLI/MCP runtime relay, agent "
            "orchestration commons) connected with non-linear handoffs."
        )
        hits = detect_enumerated_categories(text)
        self.assertEqual(len(hits), 1)
        # At least the six distinct habitats should be extracted
        self.assertGreaterEqual(len(hits[0]), 5)

    def test_detects_comma_and_enumeration(self):
        text = "Show the capability family (publishing, curating, reviewing, routing and distribution)"
        hits = detect_enumerated_categories(text)
        self.assertEqual(len(hits), 1)
        self.assertGreaterEqual(len(hits[0]), 4)

    def test_skips_three_item_enumeration(self):
        # v2 rubric's publish->govern->distribute triplet is legitimate
        text = "Publish, govern, distribute as the core loop (publish, govern, distribute)"
        hits = detect_enumerated_categories(text)
        self.assertEqual(hits, [])

    def test_skips_palette_enumeration(self):
        """Color palettes in parens are style direction, not category labels."""
        text = "Warm palette (terracotta, sage, cream, amber, parchment) with editorial restraint"
        hits = detect_enumerated_categories(text)
        self.assertEqual(hits, [], f"expected palette to be skipped, got {hits}")

    def test_empty_and_none_inputs(self):
        self.assertEqual(detect_enumerated_categories(""), [])
        self.assertEqual(detect_enumerated_categories(None), [])  # type: ignore

    def test_configurable_min_items(self):
        text = "Show three regions (alpha, beta, gamma)"
        self.assertEqual(detect_enumerated_categories(text, min_items=4), [])
        hits = detect_enumerated_categories(text, min_items=3)
        self.assertEqual(len(hits), 1)


class PlanHasTextBanTests(unittest.TestCase):
    def test_textless_in_prompt_seed(self):
        self.assertTrue(plan_has_text_ban({"prompt_seed": "Textless asymmetric composition"}))

    def test_no_labels_in_ban_list(self):
        self.assertTrue(plan_has_text_ban({"ban": ["flat gradients", "no labels, no invented UI text"]}))

    def test_no_ban_returns_false(self):
        self.assertFalse(plan_has_text_ban({"prompt_seed": "Dense isometric city composition"}))

    def test_handles_missing_fields(self):
        self.assertFalse(plan_has_text_ban({}))

    def test_case_insensitive(self):
        self.assertTrue(plan_has_text_ban({"prompt_seed": "NO HEADLINES anywhere in this asset"}))


class IntegrationWithValidateMaterialPlanDict(unittest.TestCase):
    """End-to-end: the warning/error fires through validate_material_plan_dict."""

    def _base_plan(self, **overrides):
        plan = {
            "material_type": "concept-illustration",
            "purpose": "Visualize system logic",
            "target_surface": "social 4:5",
            "product_truth_expression": "Sage capability routing",
            "abstraction_level": "medium",
            "brand_anchor_policy": {"rule": "quiet editorial"},
            "system_mechanic": "Node-edge graph",
            "preserve": ["warm palette"],
            "push": ["editorial restraint"],
            "ban": ["gradients"],
            "prompt_seed": "A concept illustration.",
        }
        plan.update(overrides)
        return plan

    def test_enumeration_without_text_ban_is_warning(self):
        from brand_gen.plan_validation import validate_material_plan_dict
        plan = self._base_plan(
            prompt_seed="Show six habitats (skills forge, prompt curation, library discovery, provenance review, runtime relay, agent orchestration).",
        )
        report = validate_material_plan_dict(plan)
        warnings = "\n".join(report["warnings"])
        self.assertIn("enumerates", warnings)
        # Should NOT be a blocking error
        enum_errors = [e for e in report["errors"] if "enumerates" in e]
        self.assertEqual(enum_errors, [])

    def test_enumeration_with_text_ban_blocks(self):
        from brand_gen.plan_validation import validate_material_plan_dict
        plan = self._base_plan(
            prompt_seed="Textless composition. Show six habitats (skills forge, prompt curation, library discovery, provenance review, runtime relay, agent orchestration).",
        )
        report = validate_material_plan_dict(plan)
        errors = "\n".join(report["errors"])
        self.assertIn("enumerates", errors)
        self.assertIn("text ban", errors)
        self.assertFalse(report["ok"])

    def test_palette_enumeration_does_not_fire(self):
        from brand_gen.plan_validation import validate_material_plan_dict
        plan = self._base_plan(
            prompt_seed="Textless composition with warm palette (terracotta, sage, cream, amber, parchment).",
        )
        report = validate_material_plan_dict(plan)
        all_msgs = "\n".join(report["warnings"] + report["errors"])
        self.assertNotIn("enumerates", all_msgs)


if __name__ == "__main__":
    unittest.main()
