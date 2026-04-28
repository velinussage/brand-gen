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
    detect_deterministic_text_surface_request,
    detect_enumerated_categories,
    detect_exact_text_request,
    plan_declares_deterministic_text_strategy,
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

    def test_exact_text_request_requires_deterministic_strategy(self):
        from brand_gen.plan_validation import validate_material_plan_dict
        plan = self._base_plan(
            prompt_seed='Render the exact headline "95% to the creator. Instant." inside the image.',
            ban=['no invented copy'],
        )
        report = validate_material_plan_dict(plan)
        self.assertFalse(report['ok'])
        self.assertTrue(any('Exact text request detected' in item for item in report['errors']))

    def test_exact_text_request_allows_html_strategy(self):
        from brand_gen.plan_validation import validate_material_plan_dict
        plan = self._base_plan(
            prompt_seed='Render the exact headline "95% to the creator. Instant."',
            render_backend='html',
        )
        report = validate_material_plan_dict(plan)
        self.assertTrue(report['ok'], report['errors'])
        self.assertTrue(detect_exact_text_request(plan))
        self.assertTrue(plan_declares_deterministic_text_strategy(plan))

    def test_exact_text_detects_read_wording_variants(self):
        self.assertTrue(detect_exact_text_request('The visible text reads "Join now".'))
        self.assertTrue(detect_exact_text_request('The badge must say approved by curators.'))
        self.assertTrue(detect_exact_text_request('Include the words Protocol Owned by Builders.'))

    def test_exact_text_ignores_negated_phrases(self):
        self.assertFalse(detect_exact_text_request('Avoid exact text; use abstract marks only.'))
        self.assertFalse(detect_exact_text_request('Do not use the words as labels.'))

    def test_exact_text_allows_typographic_overlay_strategy(self):
        from brand_gen.plan_validation import validate_material_plan_dict
        plan = self._base_plan(
            prompt_seed='The headline reads "Own your prompts".',
            text_rendering_strategy='typographic-overlay',
        )
        report = validate_material_plan_dict(plan)
        self.assertTrue(report['ok'], report['errors'])
        self.assertTrue(plan_declares_deterministic_text_strategy(plan))

    def test_proof_poster_cli_footer_requires_deterministic_strategy(self):
        from brand_gen.plan_validation import validate_material_plan_dict
        plan = self._base_plan(
            material_type="proof-poster",
            prompt_seed="Create a proof poster with a CLI footer and capability labels.",
        )
        report = validate_material_plan_dict(plan)
        self.assertFalse(report["ok"])
        self.assertTrue(detect_deterministic_text_surface_request(plan))
        self.assertTrue(any("Text-heavy material requests visible labels" in item for item in report["errors"]))

    def test_proof_poster_cli_footer_allows_html_strategy(self):
        from brand_gen.plan_validation import validate_material_plan_dict
        plan = self._base_plan(
            material_type="proof-poster",
            prompt_seed="Create a proof poster with a CLI footer and capability labels.",
            render_backend="html",
        )
        report = validate_material_plan_dict(plan)
        self.assertTrue(report["ok"], report["errors"])
        self.assertTrue(plan_declares_deterministic_text_strategy(plan))

    def test_text_surface_detector_uses_word_boundaries(self):
        plan = self._base_plan(
            material_type="proof-poster",
            prompt_seed="Create a static proof composition around the state of agent capability distribution.",
        )
        self.assertFalse(detect_deterministic_text_surface_request(plan))



class ComplexityTierTests(unittest.TestCase):
    def test_normalize_respects_explicit_value(self):
        from brand_gen.plan_validation import normalize_complexity_tier
        self.assertEqual(normalize_complexity_tier("simple"), "simple")
        self.assertEqual(normalize_complexity_tier("moderate"), "moderate")
        self.assertEqual(normalize_complexity_tier("dense"), "dense")

    def test_normalize_falls_back_to_material_default(self):
        from brand_gen.plan_validation import normalize_complexity_tier
        self.assertEqual(
            normalize_complexity_tier(None, material_type="concept-illustration"),
            "simple",
        )
        self.assertEqual(
            normalize_complexity_tier(None, material_type="brand-scene"),
            "simple",
        )
        self.assertEqual(
            normalize_complexity_tier(None, material_type="system-explainer-illustration"),
            "simple",
        )
        self.assertEqual(
            normalize_complexity_tier(None, material_type="illustrated-brand-world"),
            "simple",
        )
        self.assertEqual(
            normalize_complexity_tier(None, material_type="campaign-poster"),
            "moderate",
        )
        self.assertEqual(
            normalize_complexity_tier(None, material_type="proof-poster"),
            "moderate",
        )
        self.assertEqual(
            normalize_complexity_tier(None, material_type="site-pattern-tile"),
            "simple",
        )

    def test_normalize_underscore_material_type(self):
        """Legacy plans may have underscore form; normalize should handle it."""
        from brand_gen.plan_validation import normalize_complexity_tier
        self.assertEqual(
            normalize_complexity_tier(None, material_type="concept_illustration"),
            "simple",
        )

    def test_normalize_invalid_value_falls_back(self):
        from brand_gen.plan_validation import normalize_complexity_tier
        self.assertEqual(
            normalize_complexity_tier("ultradense", material_type="concept-illustration"),
            "simple",
        )

    def test_threshold_per_tier(self):
        from brand_gen.plan_validation import complexity_tier_enumeration_min_items
        self.assertEqual(complexity_tier_enumeration_min_items("simple"), 2)
        self.assertEqual(complexity_tier_enumeration_min_items("moderate"), 4)
        self.assertEqual(complexity_tier_enumeration_min_items("dense"), 99)


class ComplexityTierIntegrationTests(unittest.TestCase):
    """complexity_tier on the plan must tighten or loosen the enumeration
    detector accordingly. A 'simple' tier catches a 3-item enumeration that
    'moderate' would tolerate; 'dense' disables the check entirely.
    """

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

    def test_simple_tier_catches_three_item_list(self):
        from brand_gen.plan_validation import validate_material_plan_dict
        plan = self._base_plan(
            complexity_tier="simple",
            prompt_seed="Show regions (alpha, beta, gamma)",
        )
        report = validate_material_plan_dict(plan)
        all_msgs = "\n".join(report["warnings"] + report["errors"])
        self.assertIn("enumerates", all_msgs)

    def test_moderate_tier_tolerates_three_item_list(self):
        from brand_gen.plan_validation import validate_material_plan_dict
        plan = self._base_plan(
            complexity_tier="moderate",
            prompt_seed="Show regions (alpha, beta, gamma)",
        )
        report = validate_material_plan_dict(plan)
        all_msgs = "\n".join(report["warnings"] + report["errors"])
        self.assertNotIn("enumerates", all_msgs)

    def test_dense_tier_tolerates_six_item_list(self):
        from brand_gen.plan_validation import validate_material_plan_dict
        plan = self._base_plan(
            complexity_tier="dense",
            prompt_seed="Show six habitats (A, B, C, D, E, F)",
        )
        report = validate_material_plan_dict(plan)
        all_msgs = "\n".join(report["warnings"] + report["errors"])
        self.assertNotIn("enumerates", all_msgs)

    def test_concept_illustration_defaults_to_simple(self):
        """No explicit tier on concept-illustration → simple default → 3-item list fires."""
        from brand_gen.plan_validation import validate_material_plan_dict
        plan = self._base_plan(
            prompt_seed="Show regions (alpha, beta, gamma)",
        )
        plan.pop("complexity_tier", None)  # ensure unset
        report = validate_material_plan_dict(plan)
        all_msgs = "\n".join(report["warnings"] + report["errors"])
        self.assertIn("enumerates", all_msgs)


if __name__ == "__main__":
    unittest.main()
