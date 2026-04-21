"""Tests for v2 rubric overlay-axis injection into execution_prompt.

The planner's Step 5 already reads show-rubric so the plan targets
the right axes. But the execution_prompt the model sees had no
rubric content — the model never learned the scorer's criteria.
`compact_execution_rubric_overlay_push` closes that gap by emitting
a compact 'Prove axes: ...' clause that is injected into the
prompt between the selected-inspiration block and the critical-bans
block.
"""
from __future__ import annotations

import unittest

from brand_gen.prompt_assembly import (
    build_execution_prompt,
    compact_execution_rubric_overlay_push,
)


class OverlayPushClauseTests(unittest.TestCase):
    def test_concept_illustration_emits_overlay_clauses(self):
        out = compact_execution_rubric_overlay_push("concept-illustration")
        self.assertIn("system_logic_visible", out)
        self.assertIn("brand_specificity", out)
        self.assertIn("Prove axes:", out)

    def test_brand_scene_emits_process_implied(self):
        out = compact_execution_rubric_overlay_push("brand-scene")
        self.assertIn("process_implied", out)
        self.assertIn("brand_specificity", out)

    def test_landing_hero_emits_surface_fit_and_meaning_at_glance(self):
        out = compact_execution_rubric_overlay_push("landing-hero")
        self.assertIn("surface_fit", out)
        self.assertIn("meaning_at_glance", out)

    def test_disqualifier_is_surfaced(self):
        out = compact_execution_rubric_overlay_push("concept-illustration")
        self.assertIn("Avoid the", out)
        self.assertIn("generic-abstract-metaphor", out)

    def test_material_without_overlay_returns_empty(self):
        # material types with no v2 overlay should return nothing
        self.assertEqual(compact_execution_rubric_overlay_push("x-feed"), "")
        self.assertEqual(compact_execution_rubric_overlay_push("social"), "")

    def test_empty_material_type_returns_empty(self):
        self.assertEqual(compact_execution_rubric_overlay_push(None), "")
        self.assertEqual(compact_execution_rubric_overlay_push(""), "")

    def test_underscore_material_type_still_matches(self):
        """Legacy plans may have underscore form; the helper should alias."""
        out = compact_execution_rubric_overlay_push("concept_illustration")
        self.assertIn("system_logic_visible", out)


class ExecutionPromptInjectionTests(unittest.TestCase):
    def test_execution_prompt_includes_prove_axes_clause(self):
        context = {
            "material_prompt_key": "concept_illustration",
            "material_prompt_snippet": "Concept illustration policy",
            "selected_inspiration_translation": "pentagram translation",
            "reference_role_pack": [],
        }
        result = build_execution_prompt(
            "A simple brand concept.",
            context,
            material_type="concept-illustration",
            generation_mode="image",
        )
        ep = result["execution_prompt"] or ""
        sections = result["execution_prompt_sections"] or {}
        self.assertIn("rubric_overlay_push", sections)
        self.assertIn("Prove axes:", sections["rubric_overlay_push"])
        self.assertIn("system_logic_visible", ep)

    def test_non_overlay_material_still_produces_prompt(self):
        """Materials without an overlay shouldn't break the prompt path."""
        context = {
            "material_prompt_key": "x_feed",
            "material_prompt_snippet": "X-feed policy",
            "reference_role_pack": [],
        }
        result = build_execution_prompt(
            "X feed content",
            context,
            material_type="x-feed",
            generation_mode="image",
        )
        # Empty overlay push section should not break the prompt
        self.assertIn("execution_prompt", result)
        self.assertNotIn("Prove axes:", result["execution_prompt"])


if __name__ == "__main__":
    unittest.main()
