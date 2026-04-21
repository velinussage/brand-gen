"""Tests for the aesthetic archetype library and its injection into prompts.

Fix background: v181 and v182 failed because the execution_prompt carried
only mood prose ("calm branded illustration, restrained, premium
editorial") with no concrete compositional grammar. Image models need
specific handholds — named paradigms with compositional grammar, color
rule, and rendering finish. This module provides that library and the
rotation helper so the pipeline doesn't fossilize on one paradigm.
"""
from __future__ import annotations

import unittest

from brand_gen.aesthetic_archetypes import (
    get_archetype,
    list_archetypes,
    pick_rotating_archetype,
    record_archetype_choice,
    render_archetype_brief,
)
from brand_gen.iteration_memory import normalize_iteration_memory
from brand_gen.prompt_assembly import (
    build_execution_prompt,
    compact_execution_aesthetic_archetype,
)


class ArchetypeRegistryTests(unittest.TestCase):
    def test_concept_illustration_has_archetypes(self):
        archetypes = list_archetypes("concept-illustration")
        self.assertGreaterEqual(len(archetypes), 3, "expected multiple archetypes for concept-illustration")
        ids = {a["id"] for a in archetypes}
        self.assertIn("penguin-classics-paperback", ids)

    def test_brand_scene_has_archetypes(self):
        archetypes = list_archetypes("brand-scene")
        self.assertGreaterEqual(len(archetypes), 3)

    def test_landing_hero_has_archetypes(self):
        archetypes = list_archetypes("landing-hero")
        self.assertGreaterEqual(len(archetypes), 3)

    def test_campaign_poster_has_archetypes(self):
        archetypes = list_archetypes("campaign-poster")
        self.assertGreaterEqual(len(archetypes), 3)

    def test_underscore_form_accepted(self):
        """Legacy plan data uses underscore form — loader must accept both."""
        a_hyphen = list_archetypes("concept-illustration")
        a_under = list_archetypes("concept_illustration")
        self.assertEqual(
            [x["id"] for x in a_hyphen],
            [x["id"] for x in a_under],
        )

    def test_unknown_material_returns_empty(self):
        self.assertEqual(list_archetypes("nonexistent-type"), [])
        self.assertEqual(list_archetypes(None), [])

    def test_get_archetype_by_id(self):
        a = get_archetype("concept-illustration", "penguin-classics-paperback")
        self.assertIsNotNone(a)
        self.assertEqual(a["id"], "penguin-classics-paperback")

    def test_get_archetype_missing_returns_none(self):
        self.assertIsNone(get_archetype("concept-illustration", "no-such-id"))
        self.assertIsNone(get_archetype("concept-illustration", None))


class ArchetypeSchemaTests(unittest.TestCase):
    """Every archetype must carry the full compositional contract — missing
    fields produce weak prompt injection."""

    def test_every_archetype_has_required_fields(self):
        for material in ("concept-illustration", "brand-scene", "landing-hero", "campaign-poster"):
            for a in list_archetypes(material):
                for field in (
                    "id",
                    "name",
                    "reference_work",
                    "compositional_grammar",
                    "color_rule",
                    "rendering_finish",
                ):
                    self.assertIn(field, a, f"{material}/{a.get('id')} missing {field}")
                    self.assertTrue(a[field], f"{material}/{a.get('id')}.{field} is empty")
                self.assertIsInstance(a.get("signature_moves"), list)
                self.assertIsInstance(a.get("example_bans"), list)


class ArchetypeRotationTests(unittest.TestCase):
    def test_pick_first_when_no_history(self):
        memory = normalize_iteration_memory(None)
        chosen = pick_rotating_archetype("concept-illustration", memory)
        self.assertIsNotNone(chosen)
        self.assertEqual(chosen["id"], list_archetypes("concept-illustration")[0]["id"])

    def test_rotation_avoids_recent_picks(self):
        memory = normalize_iteration_memory(None)
        material = "concept-illustration"
        archetypes = list_archetypes(material)
        set_size = len(archetypes)
        seen = []
        for _ in range(set_size):
            chosen = pick_rotating_archetype(material, memory)
            self.assertIsNotNone(chosen)
            seen.append(chosen["id"])
            memory = record_archetype_choice(
                memory,
                material_type=material,
                archetype_id=chosen["id"],
                archetype_set_size=set_size,
            )
        # Full cycle should visit every archetype exactly once before repeat
        self.assertEqual(len(set(seen)), set_size)

    def test_rotation_repeats_only_after_full_cycle(self):
        memory = normalize_iteration_memory(None)
        material = "concept-illustration"
        archetypes = list_archetypes(material)
        set_size = len(archetypes)
        seen = []
        for _ in range(set_size + 2):
            chosen = pick_rotating_archetype(material, memory)
            seen.append(chosen["id"])
            memory = record_archetype_choice(
                memory,
                material_type=material,
                archetype_id=chosen["id"],
                archetype_set_size=set_size,
            )
        # First N unique, then repetition
        self.assertEqual(len(set(seen[:set_size])), set_size)
        self.assertEqual(seen[set_size], seen[0])

    def test_pick_none_for_unknown_material(self):
        memory = normalize_iteration_memory(None)
        self.assertIsNone(pick_rotating_archetype("unknown-material", memory))


class ArchetypeRenderTests(unittest.TestCase):
    def test_render_includes_key_directive_parts(self):
        a = get_archetype("concept-illustration", "kyoto-garden-stillness")
        self.assertIsNotNone(a)
        brief = render_archetype_brief(a)
        self.assertIn("Kyoto garden stillness", brief)
        self.assertIn("Composition:", brief)
        self.assertIn("Color:", brief)
        self.assertIn("Finish:", brief)
        self.assertIn("Avoid:", brief)

    def test_render_empty_archetype_returns_empty(self):
        self.assertEqual(render_archetype_brief({}), "")
        self.assertEqual(render_archetype_brief(None), "")  # type: ignore


class ArchetypeInjectionTests(unittest.TestCase):
    """The execution_prompt must include the archetype brief as its own
    section so the model sees concrete compositional grammar before the
    critical bans."""

    def test_prompt_includes_archetype_block(self):
        archetype = get_archetype("concept-illustration", "penguin-classics-paperback")
        context = {
            "material_prompt_key": "concept_illustration",
            "material_prompt_snippet": "concept illustration policy",
            "selected_inspiration_translation": "some translation",
            "reference_role_pack": [],
            "aesthetic_archetype": archetype,
            "aesthetic_archetype_id": archetype["id"],
        }
        result = build_execution_prompt(
            "Test body.",
            context,
            material_type="concept-illustration",
            generation_mode="image",
        )
        sections = result.get("execution_prompt_sections") or {}
        self.assertIn("aesthetic_archetype_block", sections)
        block = sections["aesthetic_archetype_block"]
        self.assertIn("Penguin Classics paperback", block)
        ep = result.get("execution_prompt") or ""
        self.assertIn("Penguin Classics paperback", ep)

    def test_prompt_falls_back_to_first_archetype_when_unspecified(self):
        """Even without an explicit pick, the prompt must surface an
        opinionated archetype so the model isn't left with mood prose."""
        context = {
            "material_prompt_key": "concept_illustration",
            "material_prompt_snippet": "concept illustration policy",
            "reference_role_pack": [],
            # no aesthetic_archetype provided
        }
        result = build_execution_prompt(
            "Test body.",
            context,
            material_type="concept-illustration",
            generation_mode="image",
        )
        sections = result.get("execution_prompt_sections") or {}
        self.assertIn("aesthetic_archetype_block", sections)
        self.assertTrue(sections["aesthetic_archetype_block"])

    def test_materials_without_library_emit_empty(self):
        out = compact_execution_aesthetic_archetype({}, "unknown-material")
        self.assertEqual(out, "")


if __name__ == "__main__":
    unittest.main()
