"""Tests for the 5-slot Subject/Style/Lighting/Composition/Details brief.

Fix background (from the imagevideogen skill): image models respond to
concrete, specific slots ("Kodak Portra 400 film grain", "golden hour
backlight", "85mm portrait lens") rather than to prose mood words
("warm editorial premium"). The planner may populate these slots and
the execution prompt surfaces them as a dedicated directive block.
"""
from __future__ import annotations

import unittest

from brand_gen.prompt_assembly import (
    build_execution_prompt,
    compact_execution_five_slot_brief,
)


class FiveSlotBriefTests(unittest.TestCase):
    def test_empty_context_returns_empty(self):
        self.assertEqual(compact_execution_five_slot_brief({}), "")

    def test_single_slot_populates_brief(self):
        out = compact_execution_five_slot_brief({"prompt_subject": "a potter at work"})
        self.assertIn("Subject: a potter at work", out)
        self.assertIn("Five-slot brief", out)

    def test_all_slots_concatenated(self):
        out = compact_execution_five_slot_brief({
            "prompt_subject": "a potter at work",
            "prompt_style_descriptors": "Kodak Portra 400 grain, hand-inked",
            "prompt_lighting": "golden hour backlight",
            "prompt_camera": "85mm portrait lens",
            "prompt_composition": "shallow depth of field on the hands",
            "prompt_details": "warm muted palette, matte finish",
        })
        self.assertIn("Subject: a potter at work", out)
        self.assertIn("Style: Kodak Portra 400 grain", out)
        self.assertIn("Lighting + camera: golden hour backlight, 85mm portrait lens", out)
        self.assertIn("Composition: shallow depth of field on the hands", out)
        self.assertIn("Details: warm muted palette, matte finish", out)

    def test_lighting_and_camera_merge(self):
        """Lighting + camera render in one joined slot so the model reads
        them as the 'how is this seen' directive, not two unrelated
        sentences."""
        lighting_only = compact_execution_five_slot_brief({"prompt_lighting": "north daylight"})
        self.assertIn("Lighting + camera: north daylight", lighting_only)
        camera_only = compact_execution_five_slot_brief({"prompt_camera": "bird's eye view"})
        self.assertIn("Lighting + camera: bird's eye view", camera_only)

    def test_composition_falls_back_to_surface_strategy(self):
        """When the planner didn't give an explicit composition directive,
        the surface-strategy directive covers the slot."""
        out = compact_execution_five_slot_brief({
            "prompt_subject": "a potter",
            "selected_surface_strategy_prompt_directive": "left column copy, right column art",
        })
        self.assertIn("Composition: left column copy, right column art", out)


class FiveSlotPromptInjectionTests(unittest.TestCase):
    def test_execution_prompt_surfaces_five_slot_section(self):
        context = {
            "material_prompt_key": "concept_illustration",
            "material_prompt_snippet": "concept illustration policy",
            "reference_role_pack": [],
            "prompt_subject": "two potters at a wheel",
            "prompt_style_descriptors": "hand-inked woodcut",
            "prompt_lighting": "diffused north window light",
        }
        result = build_execution_prompt(
            "Brief body.",
            context,
            material_type="concept-illustration",
            generation_mode="image",
        )
        sections = result.get("execution_prompt_sections") or {}
        self.assertIn("five_slot_brief", sections)
        brief = sections["five_slot_brief"]
        self.assertIn("two potters at a wheel", brief)
        self.assertIn("hand-inked woodcut", brief)
        ep = result.get("execution_prompt") or ""
        self.assertIn("Subject: two potters at a wheel", ep)

    def test_empty_five_slot_does_not_bloat_prompt(self):
        context = {
            "material_prompt_key": "concept_illustration",
            "material_prompt_snippet": "concept illustration policy",
            "reference_role_pack": [],
        }
        result = build_execution_prompt(
            "Brief body.",
            context,
            material_type="concept-illustration",
            generation_mode="image",
        )
        sections = result.get("execution_prompt_sections") or {}
        # Section exists in the sections dict but empty — no "Subject:" string
        self.assertEqual(sections.get("five_slot_brief", ""), "")
        ep = result.get("execution_prompt") or ""
        self.assertNotIn("Five-slot brief", ep)


if __name__ == "__main__":
    unittest.main()
