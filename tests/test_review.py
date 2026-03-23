import argparse
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mcp.agent_review import build_agent_visual_review_packet
from mcp.commands.review import cmd_critique_rubric, cmd_submit_critique


class CritiqueRubricTextFieldsTests(unittest.TestCase):
    def test_critique_rubric_includes_text_fields(self):
        """Rubric schema should include text_accuracy and text_issues keys."""
        brand_dir = Path(tempfile.mkdtemp())
        manifest = {
            "versions": {
                "v001": {
                    "files": ["v001-social.png"],
                    "material_type": "social",
                }
            }
        }
        (brand_dir / "manifest.json").write_text(json.dumps(manifest))
        # Create a dummy image file
        (brand_dir / "v001-social.png").write_bytes(b"\x89PNG\r\n")

        args = argparse.Namespace(version="v001")

        with patch("mcp.commands.review.get_brand_dir", return_value=brand_dir), \
             patch("mcp.commands.review.load_manifest", return_value=manifest), \
             patch("mcp.commands.review.load_blackboard", return_value={}):
            import io
            from contextlib import redirect_stdout
            f = io.StringIO()
            with redirect_stdout(f):
                cmd_critique_rubric(args)
            output = json.loads(f.getvalue())

        schema = output["rubric"]["schema"]
        self.assertIn("text_accuracy", schema)
        self.assertIn("text_issues", schema)
        self.assertEqual(output["review_status"], "pending")
        self.assertIn("submit-critique", output["submission"]["command"])

    def test_critique_rubric_brief_falls_back_to_sidecar_execution_prompt(self):
        brand_dir = Path(tempfile.mkdtemp())
        manifest = {
            "versions": {
                "v001": {
                    "files": ["v001-social.png"],
                    "material_type": "social",
                }
            }
        }
        (brand_dir / "manifest.json").write_text(json.dumps(manifest))
        (brand_dir / "v001-social.png").write_bytes(b"\x89PNG\r\n")
        (brand_dir / "v001.prompts.json").write_text(
            json.dumps({"execution_prompt": "Use the real saved brand mark and keep the proof inset small."})
        )

        args = argparse.Namespace(version="v001")

        with patch("mcp.commands.review.get_brand_dir", return_value=brand_dir), \
             patch("mcp.commands.review.load_manifest", return_value=manifest), \
             patch("mcp.commands.review.load_blackboard", return_value={}):
            import io
            from contextlib import redirect_stdout
            f = io.StringIO()
            with redirect_stdout(f):
                cmd_critique_rubric(args)
            output = json.loads(f.getvalue())

        self.assertEqual(output["brief"], "Use the real saved brand mark and keep the proof inset small.")

    def test_agent_review_brief_foregrounds_plan_intent_and_constraints(self):
        brand_dir = Path(tempfile.mkdtemp())
        manifest = {
            "versions": {
                "v001": {
                    "files": ["v001-social.png"],
                    "material_type": "x-feed",
                    "generation_scratchpad": str(brand_dir / "scratchpads" / "generation" / "v001.json"),
                }
            }
        }
        (brand_dir / "manifest.json").write_text(json.dumps(manifest))
        (brand_dir / "v001-social.png").write_bytes(b"\x89PNG\r\n")
        scratchpad_path = brand_dir / "scratchpads" / "generation" / "v001.json"
        scratchpad_path.parent.mkdir(parents=True, exist_ok=True)
        scratchpad_path.write_text(
            json.dumps(
                {
                    "plan": {
                        "purpose": "mark-led governed share card",
                        "target_surface": "wide social share",
                        "product_truth_expression": "small live prompt proof inset",
                        "preserve": ["proof inset stays clearly secondary"],
                        "ban": ["screenshot-dominant layout"],
                    },
                    "checks": {
                        "warnings": [
                            "Social proof should stay subordinate to the brand field: keep any proof inset to roughly 20–25% of the visual weight instead of letting it dominate the composition."
                        ]
                    },
                }
            )
        )

        packet = build_agent_visual_review_packet(brand_dir, "v001", manifest=manifest, board={})

        self.assertIn("mark-led governed share card", packet["brief"])
        self.assertIn("proof inset stays clearly secondary", packet["brief"])
        self.assertIn("screenshot-dominant layout", packet["brief"])
        self.assertEqual(packet["intent_summary"], "mark-led governed share card")
        self.assertIn("proof inset stays clearly secondary", packet["must_preserve"])


class SubmitCritiqueModelRecommendationTests(unittest.TestCase):
    def test_submit_critique_returns_model_recommendation(self):
        """When critique has text issues, response should include model_recommendation."""
        brand_dir = Path(tempfile.mkdtemp())
        (brand_dir / "reviews").mkdir()
        manifest = {
            "versions": {
                "v001": {
                    "files": ["v001-social.png"],
                    "material_type": "social",
                    "model": "nano-banana-2",
                    "reference_images": ["ref.png"],
                    "mode": "hybrid",
                    "workflow_id": "wf-1",
                }
            }
        }
        (brand_dir / "manifest.json").write_text(json.dumps(manifest))

        critique = {
            "approved": False,
            "p1": ["Text is garbled"],
            "p2": [],
            "text_accuracy": 0.3,
            "text_issues": ["misspelled word"],
        }
        critique_path = brand_dir / "critique-input.json"
        critique_path.write_text(json.dumps(critique))

        args = argparse.Namespace(
            version="v001",
            critique_json=str(critique_path),
        )

        with patch("mcp.commands.review.get_brand_dir", return_value=brand_dir), \
             patch("mcp.commands.review.load_manifest", return_value=manifest), \
             patch("mcp.commands.review.save_manifest"), \
             patch("mcp.commands.review.load_brand_memory", return_value=(None, None, {}, {})), \
             patch("mcp.commands.review.load_blackboard", return_value={}), \
             patch("mcp.commands.review.append_blackboard_decision"), \
             patch("mcp.commands.review.save_blackboard"), \
             patch("mcp.commands.review.append_run_event"):
            import io
            from contextlib import redirect_stdout
            f = io.StringIO()
            with redirect_stdout(f):
                cmd_submit_critique(args)
            output = json.loads(f.getvalue())

        self.assertEqual(output["model_recommendation"], "flux-2-flex")

    def test_submit_critique_clean_has_null_recommendation(self):
        """When critique is clean, model_recommendation should be None."""
        brand_dir = Path(tempfile.mkdtemp())
        (brand_dir / "reviews").mkdir()
        manifest = {
            "versions": {
                "v001": {
                    "files": ["v001-social.png"],
                    "material_type": "social",
                    "model": "nano-banana-2",
                    "reference_images": [],
                    "mode": "pure",
                    "workflow_id": "wf-1",
                }
            }
        }
        (brand_dir / "manifest.json").write_text(json.dumps(manifest))

        critique = {
            "approved": True,
            "p1": [],
            "p2": [],
            "text_accuracy": 0.95,
            "text_issues": [],
            "palette_match": 0.9,
        }
        critique_path = brand_dir / "critique-input.json"
        critique_path.write_text(json.dumps(critique))

        args = argparse.Namespace(
            version="v001",
            critique_json=str(critique_path),
        )

        with patch("mcp.commands.review.get_brand_dir", return_value=brand_dir), \
             patch("mcp.commands.review.load_manifest", return_value=manifest), \
             patch("mcp.commands.review.save_manifest"), \
             patch("mcp.commands.review.load_brand_memory", return_value=(None, None, {}, {})), \
             patch("mcp.commands.review.load_blackboard", return_value={}), \
             patch("mcp.commands.review.append_blackboard_decision"), \
             patch("mcp.commands.review.save_blackboard"), \
             patch("mcp.commands.review.append_run_event"):
            import io
            from contextlib import redirect_stdout
            f = io.StringIO()
            with redirect_stdout(f):
                cmd_submit_critique(args)
            output = json.loads(f.getvalue())

        self.assertIsNone(output["model_recommendation"])


class AgentReviewPacketBriefFallbackTests(unittest.TestCase):
    def test_agent_review_packet_uses_sidecar_or_scratchpad_brief_when_manifest_prompt_is_missing(self):
        brand_dir = Path(tempfile.mkdtemp())
        scratchpad_path = brand_dir / "scratchpads" / "generation" / "v001.json"
        scratchpad_path.parent.mkdir(parents=True, exist_ok=True)
        scratchpad_path.write_text(
            json.dumps(
                {
                    "execution_prompt": "Scratchpad execution prompt for Sage.",
                    "raw_prompt": "Raw prompt fallback.",
                    "plan": {"prompt_seed": "Plan seed."},
                }
            )
        )
        (brand_dir / "v001-social.png").write_bytes(b"\x89PNG\r\n")
        (brand_dir / "v001.prompts.json").write_text(json.dumps({"execution_prompt": "Sidecar execution prompt for Sage."}))
        manifest = {
            "versions": {
                "v001": {
                    "files": ["v001-social.png"],
                    "material_type": "social",
                    "generation_scratchpad": str(scratchpad_path),
                }
            }
        }
        (brand_dir / "manifest.json").write_text(json.dumps(manifest))

        packet = build_agent_visual_review_packet(brand_dir, "v001", manifest=manifest, board={})

        self.assertEqual(packet["brief"], "Sidecar execution prompt for Sage.")
