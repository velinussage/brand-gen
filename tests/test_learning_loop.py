import json
import tempfile
import unittest
from pathlib import Path

from mcp.blackboard import DEFAULT_BLACKBOARD, build_blackboard_learning_snippet, update_blackboard_learning_summary
from mcp.learnings_memory import promote_blackboard_lessons_to_learnings
from mcp.prompt_assembly import build_effective_prompt, evaluate_prompt_review_rules
from mcp.session_summary import build_session_summary_payload


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
