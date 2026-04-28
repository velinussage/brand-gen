import json
import tempfile
import unittest
from pathlib import Path

from brand_gen.blackboard import (
    DEFAULT_BLACKBOARD,
    build_blackboard_feedback_directives,
    build_blackboard_learning_snippet,
    get_blackboard_learning_warnings,
    update_blackboard_learning_summary,
)
from brand_gen.learnings_memory import promote_blackboard_lessons_to_learnings
from brand_gen.plan_builder import create_material_plan
from brand_gen.prompt_assembly import build_effective_prompt, evaluate_prompt_review_rules
from brand_gen.session_summary import build_session_summary_payload


class LearningLoopTests(unittest.TestCase):
    def test_blackboard_feedback_synthesis_and_learning_promotion(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            brand_dir = Path(tmpdir)
            board = dict(DEFAULT_BLACKBOARD)
            bad_entry_a = {
                "material_type": "browser-illustration",
                "mode": "pure",
                "model": "nano-banana-2",
                "reference_images": [],
                "score": 1,
                "status": "rejected",
            }
            bad_entry_b = {
                "material_type": "browser-illustration",
                "mode": "pure",
                "model": "nano-banana-2",
                "reference_images": [],
                "score": 2,
                "status": "rejected",
            }
            good_entry_a = {
                "material_type": "browser-illustration",
                "mode": "hybrid",
                "model": "flux-2-flex",
                "reference_images": ["ref-a.png"],
                "score": 5,
                "status": "favorite",
            }
            good_entry_b = {
                "material_type": "browser-illustration",
                "mode": "hybrid",
                "model": "flux-2-flex",
                "reference_images": ["ref-b.png"],
                "score": 4,
                "status": "favorite",
            }

            board = update_blackboard_learning_summary(
                board,
                material_type="browser-illustration",
                version_id="v001",
                entry=bad_entry_a,
                source="feedback",
                notes="Invented dashboard chrome around the real product crop.",
                score=1,
                status="rejected",
            )
            board = update_blackboard_learning_summary(
                board,
                material_type="browser-illustration",
                version_id="v002",
                entry=bad_entry_b,
                source="submit_critique",
                notes="",
                score=2,
                status="rejected",
                critique={
                    "approved": False,
                    "p1": ["Invented dashboard chrome around the real product crop."],
                    "p2": ["Text looked garbled."],
                    "refinement_suggestion": "Use one real product crop with explicit product-truth framing.",
                },
            )
            board = update_blackboard_learning_summary(
                board,
                material_type="browser-illustration",
                version_id="v003",
                entry=good_entry_a,
                source="feedback",
                notes="Use one real product crop with explicit product-truth framing.",
                score=5,
                status="favorite",
            )
            board = update_blackboard_learning_summary(
                board,
                material_type="browser-illustration",
                version_id="v004",
                entry=good_entry_b,
                source="submit_critique",
                notes="",
                score=4,
                status="favorite",
                critique={
                    "approved": True,
                    "clean": ["Use one real product crop with explicit product-truth framing."],
                    "p1": [],
                    "p2": [],
                },
            )

            summary = board["learning_summary"]["browser_illustration"]
            self.assertTrue(any("Invented dashboard chrome" in item for item in summary["failure_patterns"]))
            self.assertTrue(any("without references" in item.lower() for item in summary["reference_bias"]))
            self.assertTrue(any("Recent wins cluster in hybrid mode." == item for item in [summary["route_bias"]]))
            self.assertTrue(board["material_recipes"]["browser_illustration"]["recipes"])

            promotion = promote_blackboard_lessons_to_learnings(brand_dir, board=board, material_type="browser-illustration")
            promoted_buckets = {item["bucket"] for item in promotion["promoted"]}
            self.assertIn("failurePatterns", promoted_buckets)
            self.assertIn("compositionPatterns", promoted_buckets)
            self.assertIn("modelPreferences", promoted_buckets)

    def test_build_effective_prompt_includes_blackboard_learning_snippet(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            brand_dir = Path(tmpdir)
            board = dict(DEFAULT_BLACKBOARD)
            board = update_blackboard_learning_summary(
                board,
                material_type="browser-illustration",
                version_id="v001",
                entry={
                    "material_type": "browser-illustration",
                    "mode": "hybrid",
                    "model": "flux-2-flex",
                    "reference_images": ["ref.png"],
                    "score": 5,
                    "status": "favorite",
                },
                source="feedback",
                notes="Keep one real product crop and explicit product-truth framing.",
                score=5,
                status="favorite",
            )
            (brand_dir / "blackboard.json").write_text(json.dumps(board, indent=2) + "\n")

            payload = build_effective_prompt(
                {},
                {},
                "Create a browser illustration for Sage.",
                brand_dir=brand_dir,
                material_type="browser-illustration",
                workflow_mode="hybrid",
            )

            self.assertIn("blackboard_learning_snippet", payload)
            self.assertIn("Recent blackboard preferred setup", payload["blackboard_learning_snippet"])
            self.assertIn("Keep one real product crop", payload["resolved_prompt"])

    def test_feedback_directives_normalize_user_design_notes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            brand_dir = Path(tmpdir)
            board = dict(DEFAULT_BLACKBOARD)
            board = update_blackboard_learning_summary(
                board,
                material_type="x-feed-square",
                version_id="v148",
                entry={"material_type": "x-feed-square", "mode": "reference", "score": 2, "status": "rejected"},
                source="feedback",
                notes=(
                    "Pretty busy; text is hard to read; colors are not working. "
                    "Premise is liked, but the agent hyper-focuses on one specific feature."
                ),
                score=2,
                status="rejected",
            )

            directives = build_blackboard_feedback_directives(brand_dir, "x-feed-square", board=board)
            joined_push = " ".join(directives["push"]).lower()
            joined_ban = " ".join(directives["ban"]).lower()
            self.assertIn("simplify", joined_push)
            self.assertIn("deterministic", joined_push)
            self.assertIn("brand palette", joined_push)
            self.assertIn("fresh angle", joined_push)
            self.assertIn("busy", joined_ban)
            self.assertEqual(directives["visual_density_cap"], 4)
            self.assertEqual(directives["complexity_tier_hint"], "simple")

    def test_feedback_directives_force_style_shift_for_repetitive_sage_runs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            brand_dir = Path(tmpdir)
            board = dict(DEFAULT_BLACKBOARD)
            for idx, note in enumerate(
                [
                    "User score: 3/5. Better than the animations, but the image generation is copying the same style too closely.",
                    "User score: 3/5. Do not keep repeating the same terracotta/isometric/exchange-node look.",
                    "User score: 3/5. Too stylistically repetitive; next pass must deliberately vary generation style.",
                ],
                start=189,
            ):
                board = update_blackboard_learning_summary(
                    board,
                    material_type="editorial-metaphor-illustration",
                    version_id=f"v{idx}",
                    entry={"material_type": "editorial-metaphor-illustration", "mode": "reference", "score": 3},
                    source="feedback",
                    notes=note,
                    score=3,
                )

            directives = build_blackboard_feedback_directives(brand_dir, "editorial-metaphor-illustration", board=board)
            joined_push = " ".join(directives["push"]).lower()
            joined_ban = " ".join(directives["ban"]).lower()
            joined_warnings = " ".join(directives["warnings"]).lower()
            self.assertIn("different art-direction branch", joined_push)
            self.assertIn("terracotta/isometric/exchange-node", joined_ban)
            self.assertIn("v189-v191", joined_warnings)

    def test_website_hero_feedback_directives_force_sidecar_not_full_section(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            brand_dir = Path(tmpdir)
            board = dict(DEFAULT_BLACKBOARD)
            board = update_blackboard_learning_summary(
                board,
                material_type="website-hero-illustration",
                version_id="v149",
                entry={"material_type": "website-hero-illustration", "mode": "reference", "score": 1, "status": "rejected"},
                source="feedback",
                notes="This should not be a full hero section; it should be a supporting illustration on the right or left side of hero text.",
                score=1,
                status="rejected",
            )

            directives = build_blackboard_feedback_directives(brand_dir, "website-hero-illustration", board=board)
            self.assertTrue(any("sidecar hero illustration" in item for item in directives["push"]))
            self.assertTrue(any("full hero section" in item for item in directives["ban"]))
            self.assertEqual(directives["visual_density_cap"], 4)

    def test_proof_poster_feedback_preserves_illustration_but_reduces_density(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            brand_dir = Path(tmpdir)
            board = dict(DEFAULT_BLACKBOARD)
            board = update_blackboard_learning_summary(
                board,
                material_type="proof-poster",
                version_id="v150",
                entry={"material_type": "proof-poster", "mode": "reference", "score": 4},
                source="feedback",
                notes="User score 3.8/5. Liked the illustration and poster craft, but it is a bit too busy.",
                score=4,
            )

            directives = build_blackboard_feedback_directives(brand_dir, "proof-poster", board=board)
            self.assertTrue(any("Preserve the illustrated proof-poster craft" in item for item in directives["push"]))
            self.assertTrue(any("many competing text blocks" in item for item in directives["ban"]))
            self.assertEqual(directives["visual_density_cap"], 4)

    def test_material_plan_applies_feedback_directives_to_push_ban_and_density(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            brand_dir = Path(tmpdir)
            identity = {"brand": {"name": "Sage"}}
            identity_path = brand_dir / "brand-identity.json"
            identity_path.write_text(json.dumps(identity))
            board = dict(DEFAULT_BLACKBOARD)
            board = update_blackboard_learning_summary(
                board,
                material_type="x-feed-square",
                version_id="v148",
                entry={"material_type": "x-feed-square", "mode": "reference", "score": 2, "status": "rejected"},
                source="feedback",
                notes="Pretty busy; text is hard to read; colors are not working.",
                score=2,
                status="rejected",
            )
            (brand_dir / "blackboard.json").write_text(json.dumps(board))

            plan, missing = create_material_plan(
                brand_dir=brand_dir,
                identity_path=identity_path,
                identity=identity,
                material_type="x-feed-square",
                mode="reference",
                mechanic="",
                preserve=[],
                push=[],
                ban=[],
                picks={},
                product_truth_expression="Sage libraries distribute reusable capabilities to agents.",
            )

            self.assertEqual(missing, [])
            self.assertEqual(plan["visual_density"], 4)
            self.assertEqual(plan["complexity_tier"], "simple")
            self.assertTrue(any("Simplify hierarchy" in item for item in plan["push"]))
            self.assertTrue(any("tiny native image text" in item for item in plan["ban"]))
            self.assertTrue(plan["feedback_directives"]["warnings"])

    def test_underperforming_warning_requires_distinct_losses_without_recent_win(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            brand_dir = Path(tmpdir)
            board = dict(DEFAULT_BLACKBOARD)
            for source in ("feedback", "submit_critique"):
                board = update_blackboard_learning_summary(
                    board,
                    material_type="social",
                    version_id="v001",
                    entry={"material_type": "social", "mode": "reference", "score": 1, "status": "rejected"},
                    source=source,
                    notes="Same rejected version recorded twice.",
                    score=1,
                    status="rejected",
                )
            warnings = get_blackboard_learning_warnings(
                brand_dir,
                "social",
                proposed_mode="reference",
                has_reference_roles=True,
                board=board,
            )
            self.assertFalse(any("underperforming" in item for item in warnings))

            board = update_blackboard_learning_summary(
                board,
                material_type="social",
                version_id="v002",
                entry={"material_type": "social", "mode": "reference", "score": 1, "status": "rejected"},
                source="feedback",
                notes="Second distinct rejected version.",
                score=1,
                status="rejected",
            )
            warnings = get_blackboard_learning_warnings(
                brand_dir,
                "social",
                proposed_mode="reference",
                has_reference_roles=True,
                board=board,
            )
            self.assertTrue(any("underperforming" in item for item in warnings))

            board = update_blackboard_learning_summary(
                board,
                material_type="social",
                version_id="v003",
                entry={"material_type": "social", "mode": "reference", "score": 4, "status": "favorite"},
                source="feedback",
                notes="Recent reference-mode win.",
                score=4,
                status="favorite",
            )
            warnings = get_blackboard_learning_warnings(
                brand_dir,
                "social",
                proposed_mode="reference",
                has_reference_roles=True,
                board=board,
            )
            self.assertFalse(any("underperforming" in item for item in warnings))

    def test_prompt_review_rules_consume_learning_signals(self):
        issues, recommendations = evaluate_prompt_review_rules(
            "browser_illustration",
            "Create a browser illustration." * 80,
            {
                "resolved_prompt": "Create a browser illustration." * 80,
                "reference_role_pack": [{"role": "composition"}],
                "blackboard_learning_summary": {
                    "recent_low_score_count": 2,
                    "failure_patterns": ["Invented dashboard chrome around the real product crop."],
                    "reference_bias": ["Recent misses cluster when generating without references."],
                },
            },
        )

        self.assertTrue(any("over-specified" in item.lower() for item in issues))
        self.assertTrue(any("product truth" in item.lower() for item in recommendations))
        self.assertTrue(any("reference-backed setup" in item.lower() for item in recommendations))

    def test_session_summary_exposes_learning_surfaces(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            brand_dir = Path(tmpdir)
            (brand_dir / "manifest.json").write_text('{"versions": {}}')
            payload = build_session_summary_payload(
                brand_dir,
                {"brand_name": "Sage"},
                {"brand": {"name": "Sage"}},
                limit=2,
            )

            self.assertIn("learning_summary", payload["blackboard"])
            self.assertIn("learnings", payload)
            self.assertIn("counts", payload["learnings"])


if __name__ == "__main__":
    unittest.main()
