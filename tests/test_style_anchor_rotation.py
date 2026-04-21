"""Tests for rotating_anchor_set style policies.

The rotation helper exists to address the v094-v096 failure cluster:
when a single style anchor is locked for a material (e.g. concept-illustration
always deriving from v012), outputs stop varying and the user rejects them
as 'same aesthetic thrice'. The fix is to declare a set of acceptable
anchors in learnings.styleReferencePolicies with reference_policy =
'rotating_anchor_set', and have the planner pick a different anchor each
run via pick_rotating_style_anchor.
"""
from __future__ import annotations

import unittest

from brand_gen.iteration_memory import (
    normalize_iteration_memory,
    pick_rotating_style_anchor,
    record_style_anchor_choice,
)


CONCEPT_POLICY = {
    "material_type": "concept-illustration",
    "required_style_reference_versions": ["v012", "v021", "v088", "v156", "v018"],
    "reference_policy": "rotating_anchor_set",
}

SINGLE_ANCHOR_POLICY = {
    "material_type": "campaign-poster",
    "required_style_reference_versions": ["v014"],
    "reference_policy": "single_style_anchor",
}


class RotationHelperTests(unittest.TestCase):
    def test_picks_first_anchor_when_no_prior(self):
        memory = normalize_iteration_memory(None)
        choice = pick_rotating_style_anchor(CONCEPT_POLICY, memory, material_type="concept-illustration")
        self.assertEqual(choice, "v012")

    def test_avoids_repeating_last_anchor(self):
        memory = normalize_iteration_memory({"last_style_anchor_by_material": {"concept-illustration": "v012"}})
        choice = pick_rotating_style_anchor(CONCEPT_POLICY, memory, material_type="concept-illustration")
        self.assertNotEqual(choice, "v012")
        self.assertEqual(choice, "v021")  # next in list after excluding last

    def test_cycles_across_runs(self):
        memory = normalize_iteration_memory(None)
        anchor_count = len(CONCEPT_POLICY["required_style_reference_versions"])
        seen = []
        for _ in range(anchor_count):
            choice = pick_rotating_style_anchor(CONCEPT_POLICY, memory, material_type="concept-illustration")
            seen.append(choice)
            memory = record_style_anchor_choice(
                memory,
                material_type="concept-illustration",
                anchor_version=choice,
                anchor_set_size=anchor_count,
            )
        self.assertEqual(len(set(seen)), anchor_count, f"expected full rotation, got {seen}")

    def test_repeats_only_after_full_cycle(self):
        memory = normalize_iteration_memory(None)
        anchor_count = len(CONCEPT_POLICY["required_style_reference_versions"])
        seen = []
        for _ in range(anchor_count + 2):
            choice = pick_rotating_style_anchor(CONCEPT_POLICY, memory, material_type="concept-illustration")
            seen.append(choice)
            memory = record_style_anchor_choice(
                memory,
                material_type="concept-illustration",
                anchor_version=choice,
                anchor_set_size=anchor_count,
            )
        # First N picks must all be unique; then repetition is allowed
        self.assertEqual(len(set(seen[:anchor_count])), anchor_count)
        # The (N+1)th pick must equal the 1st (the oldest one falls off the window)
        self.assertEqual(seen[anchor_count], seen[0])

    def test_falls_back_to_all_when_only_one_remains(self):
        small_policy = dict(CONCEPT_POLICY, required_style_reference_versions=["v012"])
        memory = normalize_iteration_memory({"last_style_anchor_by_material": {"concept-illustration": "v012"}})
        choice = pick_rotating_style_anchor(small_policy, memory, material_type="concept-illustration")
        # only one anchor — must return it even though it matches the last
        self.assertEqual(choice, "v012")

    def test_single_style_anchor_policy_returns_first(self):
        memory = normalize_iteration_memory({"last_style_anchor_by_material": {"campaign-poster": "v014"}})
        choice = pick_rotating_style_anchor(SINGLE_ANCHOR_POLICY, memory, material_type="campaign-poster")
        self.assertEqual(choice, "v014")

    def test_malformed_policy_returns_none(self):
        memory = normalize_iteration_memory(None)
        self.assertIsNone(pick_rotating_style_anchor({}, memory, material_type="x"))
        self.assertIsNone(pick_rotating_style_anchor({"required_style_reference_versions": []}, memory, material_type="x"))

    def test_record_persists_choice(self):
        memory = normalize_iteration_memory(None)
        memory = record_style_anchor_choice(memory, material_type="concept-illustration", anchor_version="v088")
        self.assertEqual(memory["last_style_anchor_by_material"]["concept-illustration"], "v088")

    def test_record_preserves_other_materials(self):
        memory = normalize_iteration_memory(None)
        memory = record_style_anchor_choice(memory, material_type="concept-illustration", anchor_version="v012")
        memory = record_style_anchor_choice(memory, material_type="brand-scene", anchor_version="v146")
        self.assertEqual(memory["last_style_anchor_by_material"]["concept-illustration"], "v012")
        self.assertEqual(memory["last_style_anchor_by_material"]["brand-scene"], "v146")


if __name__ == "__main__":
    unittest.main()
