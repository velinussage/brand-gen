"""v1 scoring tests.

Covers the M1 scope: rubric_registry loads, axes_for / disqualifier_for
behave correctly for each material, v2 packet shape fields are present,
to_markdown and to_json_dict produce valid outputs.

v2 tests (DSPy DummyLM hermetic flow, partition split, calibration kappa,
caching adapter token counts, concurrent-write stress) land in M2 and M3.
"""
from __future__ import annotations

import json
import unittest

from brand_gen.scoring import (
    MATERIAL_OVERLAYS,
    RUBRIC_VERSION,
    UNIVERSAL_AXES,
    axes_for,
    disqualifier_for,
    material_rubric_key,
    to_json_dict,
    to_markdown,
)


class TestUniversalAxes(unittest.TestCase):
    def test_has_five_axes(self):
        self.assertEqual(len(UNIVERSAL_AXES), 5)

    def test_axis_names(self):
        names = [a["name"] for a in UNIVERSAL_AXES]
        self.assertIn("composition", names)
        self.assertIn("brand_coherence", names)
        self.assertIn("restraint", names)
        self.assertIn("story_fidelity", names)
        self.assertIn("meaning_clarity", names)

    def test_every_axis_has_definition(self):
        for axis in UNIVERSAL_AXES:
            self.assertIn("definition", axis)
            self.assertTrue(axis["definition"].strip(), f"empty definition: {axis['name']}")
            self.assertGreater(len(axis["definition"]), 50,
                               f"definition too short: {axis['name']}")


class TestMaterialOverlays(unittest.TestCase):
    MATERIALS = ("landing-hero", "concept-illustration", "brand-scene")

    def test_three_materials_registered(self):
        for material in self.MATERIALS:
            self.assertIn(material, MATERIAL_OVERLAYS)

    def test_each_overlay_has_two_axes(self):
        for material in self.MATERIALS:
            overlay = MATERIAL_OVERLAYS[material]
            axes = overlay.get("overlay_axes", [])
            self.assertEqual(len(axes), 2, f"{material} should have 2 overlay axes")

    def test_each_overlay_has_disqualifier(self):
        for material in self.MATERIALS:
            dq = disqualifier_for(material)
            self.assertIsNotNone(dq, f"{material} should have a disqualifier")
            self.assertIn("rule_id", dq)
            self.assertIn("description", dq)
            self.assertIn("detection_prompt", dq)

    def test_disqualifier_rule_ids_are_unique(self):
        rule_ids = [disqualifier_for(m)["rule_id"] for m in self.MATERIALS]
        self.assertEqual(len(rule_ids), len(set(rule_ids)),
                         "disqualifier rule_ids should be globally unique")

    def test_axes_for_returns_universal_plus_overlay(self):
        for material in self.MATERIALS:
            axes = axes_for(material)
            self.assertEqual(
                len(axes), 7,
                f"{material}: expected 5 universal + 2 overlay = 7 axes, got {len(axes)}"
            )

    def test_axes_for_unknown_material_returns_universal_only(self):
        axes = axes_for("nonexistent-material-type")
        self.assertEqual(len(axes), len(UNIVERSAL_AXES))

    def test_axes_for_none_returns_universal_only(self):
        axes = axes_for(None)
        self.assertEqual(len(axes), len(UNIVERSAL_AXES))

    def test_underscore_aliases_resolve(self):
        # landing_hero → landing-hero
        self.assertEqual(len(axes_for("landing_hero")), 7)
        self.assertEqual(len(axes_for("concept_illustration")), 7)
        self.assertEqual(len(axes_for("brand_scene")), 7)

    def test_material_rubric_key(self):
        self.assertEqual(material_rubric_key("landing-hero"), "landing-hero")
        self.assertEqual(material_rubric_key("landing_hero"), "landing-hero")
        self.assertEqual(material_rubric_key("unknown"), "")
        self.assertEqual(material_rubric_key(None), "")


class TestToJsonDict(unittest.TestCase):
    def test_full_registry_shape(self):
        payload = to_json_dict()
        self.assertEqual(payload["rubric_version"], RUBRIC_VERSION)
        self.assertIn("universal_axes", payload)
        self.assertIn("materials", payload)
        self.assertEqual(len(payload["universal_axes"]), 5)
        self.assertEqual(len(payload["materials"]), 3)

    def test_material_focused_shape(self):
        payload = to_json_dict("landing-hero")
        self.assertEqual(payload["material_type"], "landing-hero")
        self.assertEqual(payload["material_rubric_key"], "landing-hero")
        self.assertEqual(len(payload["universal_axes"]), 5)
        self.assertEqual(len(payload["overlay_axes"]), 2)
        self.assertIsNotNone(payload["disqualifier"])

    def test_material_focused_unknown(self):
        payload = to_json_dict("nonexistent-material-type")
        self.assertEqual(payload["material_rubric_key"], "")
        self.assertEqual(len(payload["overlay_axes"]), 0)
        self.assertIsNone(payload["disqualifier"])

    def test_roundtrip_json_serializable(self):
        payload = to_json_dict()
        # should not raise
        json.dumps(payload)
        for material in ("landing-hero", "concept-illustration", "brand-scene"):
            json.dumps(to_json_dict(material))


class TestToMarkdown(unittest.TestCase):
    def test_produces_valid_markdown(self):
        md = to_markdown()
        self.assertIn(f"rubric_version: {RUBRIC_VERSION}", md)
        # Must cover both v1 and v2 packet shapes per the plan
        self.assertIn("rubric_version", md)
        self.assertIn("v2 universal axes", md)
        self.assertIn("v2 material-specific overlays", md)
        self.assertIn("v1 narrative rubric", md)

    def test_mentions_every_axis(self):
        md = to_markdown()
        for axis in UNIVERSAL_AXES:
            self.assertIn(axis["name"], md)

    def test_mentions_every_material(self):
        md = to_markdown()
        for material in MATERIAL_OVERLAYS:
            self.assertIn(material, md)

    def test_mentions_every_disqualifier_rule_id(self):
        md = to_markdown()
        for overlay in MATERIAL_OVERLAYS.values():
            dq = overlay.get("disqualifier")
            if dq:
                self.assertIn(dq["rule_id"], md)

    def test_documents_aggregation_rule(self):
        md = to_markdown()
        self.assertIn("min-biased", md)


class TestRubricVersion(unittest.TestCase):
    def test_version_is_a_date_string(self):
        # Loose check: YYYY-MM-DD shape
        parts = RUBRIC_VERSION.split("-")
        self.assertEqual(len(parts), 3)
        self.assertEqual(len(parts[0]), 4)
        self.assertTrue(RUBRIC_VERSION[:4].isdigit())


if __name__ == "__main__":
    unittest.main()
