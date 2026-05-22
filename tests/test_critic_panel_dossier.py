"""Unit tests for the PR-4 concurrent critique panel, hard constraints, claims, and dossier synthesis."""

import unittest
import tempfile
import json
import shutil
from pathlib import Path
from typing import Any

from brand_gen.harness.policy import RunPolicy
from brand_gen.harness.critique.rubric import check_hard_constraints
from brand_gen.harness.critique.claims import aggregate_surviving_claims, categorize_claim_axis
from brand_gen.harness.critique.dossier import write_dossier


class CriticPanelDossierTests(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.brand_dir = Path(self.test_dir) / "test_brand"
        self.brand_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_categorize_claim_axis(self):
        """Verify keyword matching categorizes claims into correct universal axes."""
        self.assertEqual(categorize_claim_axis("the layout feels cluttered and lacks focal hierarchy"), "composition")
        self.assertEqual(categorize_claim_axis("wrong palette colors used"), "brand_coherence")
        self.assertEqual(categorize_claim_axis("too much neon slop decoration"), "restraint")
        self.assertEqual(categorize_claim_axis("does not serve the campaign creative brief"), "story_fidelity")
        self.assertEqual(categorize_claim_axis("unclear meaning for visitors"), "meaning_clarity")
        self.assertEqual(categorize_claim_axis("uses logo as a content substitute instead of showing skills/mcp tools"), "value_proposition_fidelity")
        self.assertEqual(categorize_claim_axis("random unknown feedback"), "general")

    def test_aggregate_surviving_claims(self):
        """Verify argue-style aggregation: deduplication, severity rating, and prioritization."""
        critics_results = [
            {
                "critic_id": "critic-composition",
                "score": 3,
                "rationale": "Layout feels slightly off.",
                "evidence": ["cluttered focal point", "palette has minor issues"],
                "blocking": ["cluttered focal point"]
            },
            {
                "critic_id": "critic-copy",
                "score": 2,
                "rationale": "Copy is wordy.",
                "evidence": ["unclear meaning for visitors"],
                "blocking": ["unclear meaning for visitors", "cluttered focal point"]  # Overlapping blocking claim
            },
            {
                "critic_id": "product-truth-reviewer",
                "score": 4,
                "rationale": "Good overall representation.",
                "evidence": ["palette has minor issues"],  # Overlapping advisory claim
                "blocking": []
            }
        ]

        claims = aggregate_surviving_claims(critics_results)
        
        # Verify deduplication
        # "cluttered focal point" is blocking in both first & second critic -> should aggregate
        cluttered_claim = next(c for c in claims if "cluttered" in c["text"])
        self.assertEqual(cluttered_claim["severity"], "blocking")
        self.assertEqual(cluttered_claim["consensus_level"], "consensus")
        self.assertCountEqual(cluttered_claim["source_critics"], ["critic-composition", "critic-copy"])
        self.assertEqual(cluttered_claim["axis"], "composition")

        # "palette has minor issues" is advisory in first & third critic -> should aggregate
        palette_claim = next(c for c in claims if "palette" in c["text"])
        self.assertEqual(palette_claim["severity"], "advisory")
        self.assertEqual(palette_claim["consensus_level"], "consensus")
        self.assertCountEqual(palette_claim["source_critics"], ["critic-composition", "product-truth-reviewer"])
        self.assertEqual(palette_claim["axis"], "brand_coherence")

        # "unclear meaning for visitors" is blocking only in second critic -> unique
        meaning_claim = next(c for c in claims if "meaning" in c["text"])
        self.assertEqual(meaning_claim["severity"], "blocking")
        self.assertEqual(meaning_claim["consensus_level"], "unique")
        self.assertEqual(meaning_claim["source_critics"], ["critic-copy"])

        # Sort order: priority score (blocking consensus > blocking unique > advisory consensus)
        self.assertEqual(claims[0], cluttered_claim)
        self.assertEqual(claims[1], meaning_claim)
        self.assertEqual(claims[2], palette_claim)

    def test_check_hard_constraints_forbidden_patterns(self):
        """Verify that forbidden patterns are caught in prompts and text fields."""
        # Set up a mock custom-scratchpad.json
        scratchpad_path = self.brand_dir / "custom-scratchpad.json"
        scratchpad_data = {
            "schema_type": "custom_scratchpad",
            "schema_version": 1,
            "forbidden_patterns": [
                {"pattern": "purple slop", "reason": "not premium", "source_version": "v1.0"},
                {"pattern": "neon glow", "reason": "slop decoration", "source_version": "v1.0"}
            ]
        }
        with open(scratchpad_path, "w", encoding="utf-8") as f:
            json.dump(scratchpad_data, f)

        # 1. Clean check
        res_clean = check_hard_constraints(
            brand_dir=self.brand_dir,
            material_type="logo",
            generation_prompt="A clean minimalist vector brand identity emblem.",
            text_details={"headline": "Sage Development Tools", "cta": "Get Started"}
        )
        self.assertTrue(res_clean["passed"])
        self.assertEqual(len(res_clean["blocking_failures"]), 0)

        # 2. Block on forbidden prompt pattern
        res_bad_prompt = check_hard_constraints(
            brand_dir=self.brand_dir,
            material_type="logo",
            generation_prompt="A glossy tech emblem featuring purple slop lighting.",
            text_details={"headline": "Sage Tools", "cta": "Get Started"}
        )
        self.assertFalse(res_bad_prompt["passed"])
        self.assertIn("Forbidden pattern 'purple slop' detected in generation prompt", res_bad_prompt["blocking_failures"][0])

        # 3. Block on forbidden text details pattern
        res_bad_text = check_hard_constraints(
            brand_dir=self.brand_dir,
            material_type="logo",
            generation_prompt="A clean minimalist vector brand identity emblem.",
            text_details={"headline": "Sage with neon glow design", "cta": "Get Started"}
        )
        self.assertFalse(res_bad_text["passed"])
        self.assertIn("Forbidden pattern 'neon glow' detected in text field 'headline'", res_bad_text["blocking_failures"][0])

    def test_check_hard_constraints_allowed_models_and_aspect_ratio(self):
        """Verify that disallowed models/tools and aspect ratio mismatches are caught."""
        policy = RunPolicy(allowed_models=["flux-2-pro"], allowed_tools=["image-generation"])
        
        # aspect ratio mismatch check
        res = check_hard_constraints(
            brand_dir=self.brand_dir,
            material_type="logo",
            generation_prompt="A clean emblem.",
            text_details={},
            policy=policy,
            metadata={
                "model": "flux-2-pro",
                "tools": ["image-generation"],
                "expected_aspect_ratio": "1:1",
                "aspect_ratio": "16:9"
            }
        )
        self.assertFalse(res["passed"])
        self.assertIn("Aspect ratio mismatch: expected 1:1, got 16:9", res["blocking_failures"])

        # disallowed model check
        res_disallowed_model = check_hard_constraints(
            brand_dir=self.brand_dir,
            material_type="logo",
            generation_prompt="A clean emblem.",
            text_details={},
            policy=policy,
            metadata={
                "model": "unapproved-slop-generator",
                "tools": ["image-generation"]
            }
        )
        self.assertFalse(res_disallowed_model["passed"])
        self.assertIn("Model 'unapproved-slop-generator' is not in policy allowed_models", res_disallowed_model["blocking_failures"][0])

    def test_write_dossier_paired_outputs(self):
        """Verify that write_dossier outputs correctly structured paired JSON and Markdown files."""
        critics_results = [
            {
                "critic_id": "critic-composition",
                "score": 4,
                "rationale": "Perfect composition.",
                "evidence": ["clean balanced negative space"],
                "blocking": []
            }
        ]
        synthesis = {
            "score": 4.0,
            "recommendation": "lock",
            "blocking_findings": [],
            "prose_summary": "Overall exceptional premium execution, perfectly matching the Sage guidelines."
        }

        json_path, md_path = write_dossier(
            brand_dir=self.brand_dir,
            run_id="run_123",
            campaign_id="camp_456",
            version_id="v001",
            material_type="logo",
            creative_brief="Mock creative brief and strategy.",
            critics_results=critics_results,
            synthesis=synthesis
        )

        self.assertTrue(json_path.exists())
        self.assertTrue(md_path.exists())

        # Verify JSON content
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            self.assertEqual(data["schema_type"], "review_dossier")
            self.assertEqual(data["run_id"], "run_123")
            self.assertEqual(data["campaign_id"], "camp_456")
            self.assertEqual(data["score"], 4.0)
            self.assertEqual(data["recommendation"], "lock")
            self.assertEqual(data["prose_summary"], synthesis["prose_summary"])
            self.assertEqual(len(data["surviving_claims"]), 1)
            self.assertEqual(data["surviving_claims"][0]["text"], "clean balanced negative space")

        # Verify Markdown content
        md_text = md_path.read_text(encoding="utf-8")
        self.assertIn("# Creative Dossier: v001", md_text)
        self.assertIn("Overall Synthesized Score:** `4.0 / 5.0`", md_text)
        self.assertIn("Recommendation:** **`LOCK`**", md_text)
        self.assertIn("Mock creative brief and strategy.", md_text)
        self.assertIn("clean balanced negative space", md_text)
