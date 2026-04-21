import json
import tempfile
import unittest
from pathlib import Path

from brand_gen.capability_focus import build_capability_focus_context, derive_brand_capability_candidates


class CapabilityFocusTests(unittest.TestCase):
    def test_derives_brand_specific_candidates_from_identity_messaging(self):
        identity = {
            "brand": {"summary": "Governed skills for AI agents with CLI and MCP workflows."},
            "messaging": {
                "approved_claims": ["Sage is a governed network for curated prompts, skills, behaviors, and libraries."],
                "value_propositions": ["Distribute trusted capabilities through CLI and MCP workflows."],
            },
            "material_dna": {"feature_illustration": "Connect one product moment to the larger system or story."},
        }
        labels = [item["label"] for item in derive_brand_capability_candidates(identity)]
        self.assertIn("reusable skills", labels)
        self.assertIn("CLI workflows", labels)
        self.assertIn("MCP tools", labels)

    def test_illustration_scope_avoids_repeating_linear_story_when_candidates_exist(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            brand_dir = Path(tmpdir)
            (brand_dir / "iteration-memory.json").write_text(json.dumps({"version": 1, "negative_examples": []}))
            identity = {
                "brand": {"summary": "Governed skills for AI agents with CLI and MCP workflows."},
                "messaging": {
                    "approved_claims": ["Sage is a governed network for curated prompts, skills, behaviors, and libraries."],
                    "value_propositions": ["Distribute trusted capabilities through CLI and MCP workflows."],
                },
                "material_dna": {"feature_illustration": "Connect one product moment to the larger system or story."},
            }
            ctx = build_capability_focus_context(
                brand_dir=brand_dir,
                identity=identity,
                material_type="feature-illustration",
                product_truth_expression="Creators publish skills, communities govern approvals, libraries distribute trusted capabilities.",
                artifact_scope="illustration_only",
            )
            self.assertTrue(ctx["avoid_repeating_linear_story"])
            self.assertTrue(ctx["selected"])
            selected_labels = [item["label"] for item in ctx["selected"]]
            self.assertTrue(any(label in selected_labels for label in ["CLI workflows", "MCP tools"]))
            self.assertIn("agent orchestration", selected_labels)


if __name__ == "__main__":
    unittest.main()
