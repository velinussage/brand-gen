"""Tests for the aesthetic_commitment field and its injection.

Per the design-taste-frontend skill: "Pick an extreme... and execute it
with precision. Bold maximalism and refined minimalism both work — the
key is intentionality, not intensity." The planner must commit to ONE
axis so the output isn't averaged across three mild adjectives
("warm editorial premium"). Missing or invalid commitment emits a P2
warning in plan critique.
"""
from __future__ import annotations

import unittest

from brand_gen.plan_validation import (
    AESTHETIC_COMMITMENTS,
    aesthetic_commitment_grammar,
    normalize_aesthetic_commitment,
    validate_material_plan_dict,
)
from brand_gen.prompt_assembly import (
    build_execution_prompt,
    compact_execution_aesthetic_commitment,
)


class NormalizeCommitmentTests(unittest.TestCase):
    def test_accepts_all_enum_values(self):
        for value in AESTHETIC_COMMITMENTS:
            self.assertEqual(normalize_aesthetic_commitment(value), value)

    def test_accepts_hyphen_or_underscore(self):
        self.assertEqual(normalize_aesthetic_commitment("retro-futurist"), "retro_futurist")
        self.assertEqual(normalize_aesthetic_commitment("retro_futurist"), "retro_futurist")

    def test_case_insensitive(self):
        self.assertEqual(normalize_aesthetic_commitment("MINIMAL"), "minimal")
        self.assertEqual(normalize_aesthetic_commitment("Editorial"), "editorial")

    def test_invalid_returns_none(self):
        self.assertIsNone(normalize_aesthetic_commitment("boho"))
        self.assertIsNone(normalize_aesthetic_commitment("premium"))
        self.assertIsNone(normalize_aesthetic_commitment(None))
        self.assertIsNone(normalize_aesthetic_commitment(""))


class CommitmentGrammarTests(unittest.TestCase):
    def test_minimal_grammar_is_uncompromising(self):
        out = aesthetic_commitment_grammar("minimal")
        self.assertIn("minimal", out.lower())
        self.assertIn("extreme negative space", out)

    def test_brutalist_grammar_is_distinctive(self):
        out = aesthetic_commitment_grammar("brutalist")
        self.assertIn("raw", out)
        self.assertIn("structural grid", out.lower())

    def test_every_commitment_has_grammar(self):
        for value in AESTHETIC_COMMITMENTS:
            out = aesthetic_commitment_grammar(value)
            self.assertTrue(out, f"{value} has empty grammar")
            # Sanity: grammar references the commitment's own vocabulary
            self.assertGreater(len(out), 60, f"{value} grammar looks stubbed")

    def test_invalid_returns_empty(self):
        self.assertEqual(aesthetic_commitment_grammar("unknown"), "")
        self.assertEqual(aesthetic_commitment_grammar(None), "")


class ValidatePlanWithCommitmentTests(unittest.TestCase):
    def _base_plan(self, **overrides):
        plan = {
            "material_type": "concept-illustration",
            "purpose": "visualize system logic",
            "target_surface": "social 4:5",
            "product_truth_expression": "Sage capability routing",
            "abstraction_level": "medium",
            "brand_anchor_policy": {"rule": "quiet editorial"},
            "system_mechanic": "node-edge graph",
            "preserve": ["warm palette"],
            "push": ["editorial restraint"],
            "ban": ["gradients"],
            "prompt_seed": "a concept illustration",
        }
        plan.update(overrides)
        return plan

    def test_missing_commitment_emits_warning(self):
        plan = self._base_plan()  # no aesthetic_commitment
        report = validate_material_plan_dict(plan)
        warnings = "\n".join(report["warnings"])
        self.assertIn("aesthetic_commitment", warnings)
        self.assertIn("extreme", warnings)

    def test_invalid_commitment_emits_warning(self):
        plan = self._base_plan(aesthetic_commitment="boho")
        report = validate_material_plan_dict(plan)
        warnings = "\n".join(report["warnings"])
        self.assertIn("aesthetic_commitment 'boho'", warnings)

    def test_valid_commitment_is_quiet(self):
        plan = self._base_plan(aesthetic_commitment="editorial")
        report = validate_material_plan_dict(plan)
        warnings = "\n".join(report["warnings"])
        self.assertNotIn("aesthetic_commitment", warnings)


class CommitmentInjectionTests(unittest.TestCase):
    def test_prompt_surfaces_commitment_block(self):
        context = {
            "material_prompt_key": "concept_illustration",
            "material_prompt_snippet": "policy",
            "reference_role_pack": [],
            "aesthetic_commitment": "brutalist",
        }
        result = build_execution_prompt(
            "Body.",
            context,
            material_type="concept-illustration",
            generation_mode="image",
        )
        sections = result.get("execution_prompt_sections") or {}
        self.assertIn("aesthetic_commitment_block", sections)
        self.assertIn("Brutalist commitment", sections["aesthetic_commitment_block"])

    def test_empty_commitment_skips_block(self):
        out = compact_execution_aesthetic_commitment({})
        self.assertEqual(out, "")
        out2 = compact_execution_aesthetic_commitment({"aesthetic_commitment": "unknown"})
        self.assertEqual(out2, "")


if __name__ == "__main__":
    unittest.main()
