"""Tests for the visual_density dial and its prompt-grammar injection.

Rationale: complexity_tier (from earlier fix) caps named-element COUNT.
visual_density is the orthogonal SPATIAL dial (airy vs packed). Per
the design-taste-frontend skill: low density = Art Gallery, mid =
Daily App, high = Cockpit (packed data, 1px separators).
"""
from __future__ import annotations

import unittest

from brand_gen.plan_validation import (
    normalize_visual_density,
    visual_density_grammar,
)
from brand_gen.prompt_assembly import (
    build_execution_prompt,
    compact_execution_visual_density,
)


class NormalizeVisualDensityTests(unittest.TestCase):
    def test_caps_to_range(self):
        self.assertEqual(normalize_visual_density(0), 1)
        self.assertEqual(normalize_visual_density(11), 10)
        self.assertEqual(normalize_visual_density(-5), 1)
        self.assertEqual(normalize_visual_density(100), 10)

    def test_integer_input(self):
        self.assertEqual(normalize_visual_density(7), 7)

    def test_string_input(self):
        self.assertEqual(normalize_visual_density("8"), 8)

    def test_invalid_input_falls_back_to_material_default(self):
        self.assertEqual(normalize_visual_density(None, material_type="concept-illustration"), 4)
        self.assertEqual(normalize_visual_density("abc", material_type="concept-illustration"), 4)
        self.assertEqual(normalize_visual_density(None, material_type="landing-hero"), 4)
        self.assertEqual(normalize_visual_density(None, material_type="campaign-poster"), 5)

    def test_underscore_material_type(self):
        """Plan legacy uses underscore; normalizer must alias."""
        self.assertEqual(normalize_visual_density(None, material_type="concept_illustration"), 4)


class VisualDensityGrammarTests(unittest.TestCase):
    def test_low_band_is_art_gallery(self):
        self.assertIn("Art-gallery", visual_density_grammar(1))
        self.assertIn("Art-gallery", visual_density_grammar(3))

    def test_mid_band_is_daily_app(self):
        self.assertIn("Daily-app", visual_density_grammar(5))
        self.assertIn("Daily-app", visual_density_grammar(4))

    def test_high_band_is_cockpit(self):
        self.assertIn("Cockpit", visual_density_grammar(8))
        self.assertIn("Cockpit", visual_density_grammar(10))


class VisualDensityInjectionTests(unittest.TestCase):
    """The execution_prompt should surface the density directive only
    when the planner pushed to a non-default band (to avoid bloating
    the prompt with mid-band boilerplate on every run)."""

    def test_low_density_emits_directive(self):
        result = compact_execution_visual_density({"visual_density": 2})
        self.assertIn("Art-gallery", result)
        self.assertIn("2/10", result)

    def test_high_density_emits_directive(self):
        result = compact_execution_visual_density({"visual_density": 9})
        self.assertIn("Cockpit", result)
        self.assertIn("9/10", result)

    def test_mid_band_emits_empty(self):
        """Mid-band runs add no directive — avoid prompt bloat."""
        self.assertEqual(compact_execution_visual_density({"visual_density": 4}), "")
        self.assertEqual(compact_execution_visual_density({"visual_density": 5}), "")

    def test_absent_density_emits_empty(self):
        self.assertEqual(compact_execution_visual_density({}), "")

    def test_prompt_injection_includes_directive(self):
        context = {
            "material_prompt_key": "concept_illustration",
            "material_prompt_snippet": "policy",
            "reference_role_pack": [],
            "visual_density": 2,
        }
        result = build_execution_prompt(
            "Body.",
            context,
            material_type="concept-illustration",
            generation_mode="image",
        )
        sections = result.get("execution_prompt_sections") or {}
        self.assertIn("visual_density_block", sections)
        self.assertIn("Art-gallery", sections["visual_density_block"])


if __name__ == "__main__":
    unittest.main()
