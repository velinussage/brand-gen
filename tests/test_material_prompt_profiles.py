from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from brand_gen.aesthetic_curation import get_aesthetic_capsule
from brand_gen.material_prompt_profiles import (
    get_material_prompt_profile,
    listed_material_profile_types,
    render_material_prompt_profile,
    validate_material_prompt_profiles,
)
from brand_gen.plan_builder import create_material_plan
from brand_gen.prompt_assembly import build_execution_prompt
from brand_gen.runtime import MATERIAL_CONFIG
from brand_gen.scoring.rubric_registry import material_rubric_key


BATCHED_MATERIAL_TYPES = [
    "social",
    "x-feed",
    "x-feed-square",
    "x-feed-portrait",
    "linkedin-feed",
    "linkedin-feed-square",
    "linkedin-feed-portrait",
    "linkedin-card",
    "og-card",
    "announcement-card",
    "carousel-slide",
    "proof-poster",
    "x-card",
    "landing-hero",
    "hero-banner",
    "website-hero-illustration",
    "system-explainer-illustration",
    "product-banner",
    "product-visual",
    "feature-illustration",
    "browser-illustration",
    "device-mockup",
    "lifestyle-mockup",
    "terminal-hero",
    "cli-recording",
    "command-illustration",
    "banner",
    "storyboard",
    "styleframe",
    "icon",
    "icon-family",
    "badge-family",
    "sticker-family",
    "motif-system",
    "site-pattern-tile",
    "pattern-board",
    "lockup",
    "logo",
    "poster",
    "merch-poster",
    "content-card",
    "content-card-square",
    "editorial-card",
    "editorial-metaphor-illustration",
    "info-card",
    "data-card",
    "state-card",
    "quote-card",
    "process-card",
    "event-poster",
    "podcast-cover",
    "podcast-banner",
    "illustrated-brand-world",
    "animation",
    "feature-animation",
    "logo-animation",
    "motion-loop",
    "gif",
    "short-video",
    "stinger-animation",
]


class MaterialPromptProfileCoverageTests(unittest.TestCase):
    def test_profile_registry_covers_exact_requested_batches(self):
        self.assertEqual(sorted(listed_material_profile_types()), sorted(BATCHED_MATERIAL_TYPES))

    def test_every_requested_material_has_runtime_and_valid_prompt_profile(self):
        self.assertEqual(validate_material_prompt_profiles(BATCHED_MATERIAL_TYPES), [])
        for material_type in BATCHED_MATERIAL_TYPES:
            with self.subTest(material_type=material_type):
                self.assertIn(material_type, MATERIAL_CONFIG)
                profile = get_material_prompt_profile(material_type)
                self.assertIsInstance(profile, dict)
                self.assertEqual(profile["default_model"], MATERIAL_CONFIG[material_type]["default_model"])
                self.assertEqual(profile["default_aspect_ratio"], MATERIAL_CONFIG[material_type]["default_aspect_ratio"])

                capsules = profile.get("best_aesthetic_capsules") or []
                self.assertTrue(capsules or profile.get("aesthetic_fallback"))
                for capsule_id in capsules:
                    self.assertIsNotNone(get_aesthetic_capsule(capsule_id), f"unknown capsule {capsule_id}")

                exact = profile.get("exact_text_policy") or {}
                self.assertTrue(exact.get("mode"))
                self.assertTrue(exact.get("guidance"))

                expected_rubric = material_rubric_key(material_type) or "universal"
                self.assertEqual(profile.get("review_rubric_key"), expected_rubric)
                self.assertTrue(profile.get("review_focus"))

    def test_rendered_profile_block_contains_required_process_context(self):
        profile = get_material_prompt_profile("quote-card")
        text = render_material_prompt_profile(profile)
        self.assertIn("Material job:", text)
        self.assertIn("Exact-text policy:", text)
        self.assertIn("Material-specific failures to avoid:", text)
        self.assertIn("Review focus:", text)

    def test_feedback_profile_updates_for_v148_to_v150_materials(self):
        x_square = render_material_prompt_profile(get_material_prompt_profile("x-feed-square"))
        self.assertIn("at most three skill/tool/workflow cards", x_square)
        self.assertIn("hard-to-read native image text", x_square)

        hero = render_material_prompt_profile(get_material_prompt_profile("website-hero-illustration"))
        self.assertIn("illustration sidecar", hero)
        self.assertIn("not a complete hero section", hero)
        self.assertIn("full hero section mockup", hero)

        landing = render_material_prompt_profile(get_material_prompt_profile("landing-hero"))
        self.assertIn("hero background/sidecar animation", landing)
        self.assertIn("external_hero_copy_only", landing)
        self.assertIn("1600x900", landing)
        self.assertIn("primary mp4", landing)
        self.assertIn("optional webm", landing)

        proof = render_material_prompt_profile(get_material_prompt_profile("proof-poster"))
        self.assertIn("landscape for workflow/operator proof", proof)
        self.assertIn("five compact step tiles", proof)
        self.assertIn("native-image CLI/footer copy", proof)

    def test_landing_hero_is_video_and_bumper_removed_from_batches(self):
        profile = get_material_prompt_profile("landing-hero")
        self.assertEqual(profile["generation_mode"], "video")
        self.assertEqual(profile["default_model"], "seedance-2-pro")
        self.assertEqual(MATERIAL_CONFIG["landing-hero"]["generation_mode"], "video")
        self.assertEqual(MATERIAL_CONFIG["landing-hero"]["default_model"], "seedance-2-pro")
        self.assertNotIn("bumper-animation", listed_material_profile_types())

    def test_all_non_deprecated_runtime_materials_have_prompt_profiles(self):
        deprecated = {
            key
            for key, value in json.loads(Path("data/material_policy.json").read_text())
            .get("deprecated_material_types", {})
            .items()
            if value
        }
        missing = sorted(
            key
            for key in MATERIAL_CONFIG
            if key not in deprecated and not get_material_prompt_profile(key)
        )
        self.assertEqual(missing, [])

    def test_system_explainer_profile_is_distinct_from_editorial_metaphor(self):
        system = get_material_prompt_profile("system-explainer-illustration")
        editorial = get_material_prompt_profile("editorial-metaphor-illustration")
        self.assertIn("mechanism", system["job_to_be_done"].lower())
        self.assertIn("source artifact", system["prompt_skeleton"])
        self.assertNotEqual(system["prompt_skeleton"], editorial["prompt_skeleton"])

    def test_plan_and_execution_prompt_include_material_profile(self):
        with tempfile.TemporaryDirectory() as td:
            brand_dir = Path(td)
            identity_path = brand_dir / "brand-identity.json"
            identity_path.write_text(json.dumps({"brand": {"name": "Test"}}))
            plan, missing = create_material_plan(
                brand_dir=brand_dir,
                identity_path=identity_path,
                identity={"brand": {"name": "Test"}},
                material_type="quote-card",
                mode="hybrid",
                mechanic="",
                preserve=[],
                push=[],
                ban=[],
                picks={},
                prompt_seed="Share one approved quote with exact copy handled outside native generation.",
                purpose="share a quote",
                target_surface="social",
                accept_inspiration_recommendations=False,
            )
        self.assertEqual(missing, [])
        self.assertEqual(plan["material_prompt_profile"]["material_type"], "quote-card")
        result = build_execution_prompt(
            plan["prompt_seed"],
            {
                "material_prompt_key": "quote-card",
                "material_prompt_snippet": "Quote card policy.",
                "reference_role_pack": [],
                "material_prompt_profile": plan["material_prompt_profile"],
            },
            material_type="quote-card",
            generation_mode="image",
        )
        sections = result.get("execution_prompt_sections") or {}
        self.assertIn("material_profile_block", sections)
        self.assertIn("Exact-text policy", sections["material_profile_block"])


if __name__ == "__main__":
    unittest.main()
