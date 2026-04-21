"""Tests for primary_bucket + bucket_scores aware inspiration selection.

Rationale: when every inspiration source declares every bucket
(composition, narrative_system, rendering_style) in `bucket_hints`,
the ranker degenerates into first-by-index because all sources score
identically. This made sage's `pentagram-poster-house` the default
pick for every role slot.

`primary_bucket` (scalar) gives a strong ranking bonus for sources
tagged as that bucket's canonical pick. `bucket_scores` (dict) allows
fine-grained per-bucket weights when a source is useful for multiple
roles but shouldn't outcompete the primary source for any single one.
"""
from __future__ import annotations

import unittest

from brand_gen.reference_role_packs import select_inspiration_sources


def _source(key: str, **extra) -> dict:
    base = {
        "source_key": key,
        "source_name": key,
        "design_memory_path": f"/inspiration/premium-branding/{key}/.design-memory",
        "bucket_hints": ["composition", "narrative_system", "rendering_style"],
    }
    base.update(extra)
    return base


class PrimaryBucketRankingTests(unittest.TestCase):
    def test_primary_bucket_source_wins_its_slot(self):
        """When two sources both declare 'composition' in bucket_hints but
        one has primary_bucket='composition', the primary wins.
        """
        sources = [
            _source("gretel-work"),  # generic, all three buckets
            _source("pentagram-poster-house", primary_bucket="composition"),
        ]
        result = select_inspiration_sources(
            sources,
            selected_roles=[],
            material_type="concept-illustration",
        )
        records = result.get("records") or []
        self.assertTrue(records)
        # The composition slot should go to the pentagram-poster-house source
        # because its primary_bucket matches.
        top_source = records[0].get("source_key")
        self.assertEqual(top_source, "pentagram-poster-house")

    def test_different_primaries_spread_across_slots(self):
        """When each of 3 sources has a distinct primary_bucket, all 3 get picked
        exactly once for the 3 bucket slots."""
        sources = [
            _source("pentagram-poster-house", primary_bucket="composition"),
            _source("pentagram-jigsaw", primary_bucket="narrative_system"),
            _source("koto-pairpoint", primary_bucket="rendering_style"),
        ]
        result = select_inspiration_sources(
            sources,
            selected_roles=[],
            material_type="concept-illustration",
        )
        records = result.get("records") or []
        picked = {r.get("source_key") for r in records}
        self.assertIn("pentagram-poster-house", picked)
        self.assertIn("pentagram-jigsaw", picked)
        self.assertIn("koto-pairpoint", picked)

    def test_bucket_scores_weights_ranking(self):
        """bucket_scores with heavy composition weight beats a source with lighter
        composition weight, even when both declare the bucket in hints."""
        sources = [
            _source("light", bucket_scores={"composition": 0.3, "narrative_system": 0.2, "rendering_style": 0.1}),
            _source("heavy", bucket_scores={"composition": 1.0, "narrative_system": 0.2, "rendering_style": 0.1}),
        ]
        result = select_inspiration_sources(
            sources,
            selected_roles=[],
            material_type="concept-illustration",
        )
        records = result.get("records") or []
        self.assertTrue(records)
        # "heavy" should be top because its composition weight is higher
        self.assertEqual(records[0].get("source_key"), "heavy")

    def test_legacy_bucket_hints_still_work_when_no_primary(self):
        """Sources with just bucket_hints (no primary_bucket / bucket_scores)
        fall back to the legacy hint-set ranking — backward compatibility."""
        sources = [
            _source("only-composition", bucket_hints=["composition"]),
            _source("all-three"),
        ]
        result = select_inspiration_sources(
            sources,
            selected_roles=[],
            material_type="concept-illustration",
        )
        # With only bucket_hints, the "all-three" source should still be picked
        # because it scores across all three buckets.
        records = result.get("records") or []
        picked = {r.get("source_key") for r in records}
        self.assertIn("all-three", picked)


if __name__ == "__main__":
    unittest.main()
