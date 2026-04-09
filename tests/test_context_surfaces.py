import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from brand_gen.context_surfaces import (
    build_capabilities_payload,
    build_context_snapshot_payload,
    build_workspace_status_payload,
    get_prompt_resource,
    list_prompt_resources,
)
from brand_gen.run_ledger import append_run_event


class ContextSurfaceTests(unittest.TestCase):
    def test_prompt_resources_are_addressable_by_prompt_relative_name(self):
        prompts = list_prompt_resources()
        self.assertTrue(any(item["name"] == "replicate/image-workflow.md" for item in prompts))
        payload = get_prompt_resource("replicate/image-workflow.md")
        self.assertEqual(payload["name"], "replicate/image-workflow.md")
        self.assertIn("workflow", payload["content"].lower())

    def test_capabilities_surface_marks_primitives_and_convenience_tools(self):
        payload = build_capabilities_payload()
        tools = {item["command"]: item for item in payload["tools"]}
        self.assertTrue(tools["context-snapshot"]["read_only"])
        self.assertTrue(tools["generate-once"]["primitive"])
        self.assertTrue(tools["pipeline"]["convenience"])
        self.assertFalse(tools["pipeline"]["read_only"])

    def test_context_snapshot_reports_counts_prompt_sizes_and_pointers(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            brand_gen_root = repo_root / ".brand-gen"
            brand_dir = brand_gen_root / "brands" / "acme"
            brand_dir.mkdir(parents=True, exist_ok=True)
            (brand_dir / "scratchpads" / "generation").mkdir(parents=True, exist_ok=True)
            (brand_dir / "reviews").mkdir(parents=True, exist_ok=True)
            (brand_gen_root / "runtime-status" / "plugins").mkdir(parents=True, exist_ok=True)
            (brand_gen_root / "config.json").write_text(json.dumps({"active": "acme", "brandGenDir": str(brand_gen_root), "inspirationMode": True}) + "\n")
            (brand_dir / "brand-profile.json").write_text(json.dumps({"brand_name": "Acme", "description": "Brand summary"}) + "\n")
            (brand_dir / "brand-identity.json").write_text(json.dumps({"brand": {"name": "Acme", "summary": "Brand summary"}}) + "\n")
            (brand_dir / "inspirations.json").write_text(json.dumps({"sources": ["ramotion"], "mergeStrategy": "concat"}) + "\n")
            (brand_dir / "manifest.json").write_text(json.dumps({"versions": {"v001": {"files": ["v001.png"]}}, "locked_fragments": []}) + "\n")
            (brand_dir / "blackboard.json").write_text(json.dumps({"artifacts": {"latest_generation_scratchpad": str(brand_dir / "scratchpads" / "generation" / "latest.json"), "latest_auto_review": str(brand_dir / "reviews" / "v001-review.md")}, "generated_assets": [{"workflow_id": "wf-123"}], "decisions": [{"decision": "Keep product truth"}]}) + "\n")
            (brand_dir / "iteration-memory.json").write_text(json.dumps({"positive_examples": [{"version": "v001", "material_type": "social", "summary": "good"}], "copy_notes": ["Use real claims"]}) + "\n")
            (brand_dir / "learnings.json").write_text(json.dumps({"compositionPatterns": ["quiet framing"], "lastUpdated": "2026-03-18T10:00:00"}) + "\n")
            (brand_dir / "scratchpads" / "generation" / "latest.json").write_text(
                json.dumps(
                    {
                        "prompt_context": {
                            "brand_prelude": "brand prelude",
                            "inspiration_doctrine": "doctrine",
                            "reference_analysis_snippet": "ref analysis",
                        },
                        "execution_prompt": "do something",
                        "prompt_review": {
                            "execution_prompt_sections": {
                                "prelude": "brand prelude",
                                "body": "do something",
                            }
                        },
                    }
                )
                + "\n"
            )
            (brand_dir / "reviews" / "v001-review.md").write_text("# Review\n")
            append_run_event(brand_dir, "wf-123", stage="generate", output_version="v001", status="ok")

            with patch("brand_gen.context_surfaces.REPO_ROOT", repo_root), patch("brand_gen.context_surfaces.get_brand_gen_dir", return_value=brand_gen_root):
                profile = {"brand_name": "Acme", "description": "Brand summary"}
                identity = {"brand": {"name": "Acme", "summary": "Brand summary"}}
                payload = build_context_snapshot_payload(brand_dir, profile, identity)

            self.assertEqual(payload["workspace"]["kind"], "saved_brand")
            self.assertEqual(payload["counts"]["manifest"]["latest_id"], "v001")
            self.assertEqual(payload["counts"]["runs"]["latest_id"], "wf-123")
            self.assertEqual(payload["prompt_sizes"]["execution_prompt_chars"], len("do something"))
            self.assertEqual(payload["inspirations"]["sources"], ["ramotion"])
            self.assertTrue(payload["pointers"]["latest_review_packet"].endswith("v001-review.md"))
            self.assertIn("compare", payload["next_suggested_commands"])

    def test_workspace_status_reports_plugin_root_divergence(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            brand_gen_root = repo_root / ".brand-gen"
            other_root = repo_root / ".brand-gen-other"
            brand_dir = brand_gen_root / "brands" / "acme"
            marker_dir = brand_gen_root / "runtime-status" / "plugins"
            marker_dir.mkdir(parents=True, exist_ok=True)
            brand_dir.mkdir(parents=True, exist_ok=True)
            (brand_gen_root / "config.json").write_text(json.dumps({"active": "acme", "brandGenDir": str(brand_gen_root)}) + "\n")
            (brand_dir / "brand-profile.json").write_text(json.dumps({"brand_name": "Acme"}) + "\n")
            (brand_dir / "brand-identity.json").write_text(json.dumps({"brand": {"name": "Acme"}}) + "\n")
            (brand_dir / "manifest.json").write_text(json.dumps({"versions": {}}) + "\n")
            (marker_dir / "pi.json").write_text(
                json.dumps(
                    {
                        "plugin_name": "pi-brand-gen",
                        "resolved_root": str(other_root),
                        "workspace_dir": str(brand_dir),
                    }
                )
                + "\n"
            )

            with patch("brand_gen.context_surfaces.REPO_ROOT", repo_root), patch("brand_gen.context_surfaces.get_brand_gen_dir", return_value=brand_gen_root):
                payload = build_workspace_status_payload(brand_dir, {"brand_name": "Acme"}, {"brand": {"name": "Acme"}})

            self.assertFalse(payload["plugin_matches_python_root"])
            self.assertTrue(any("different BRAND_GEN_DIR" in item for item in payload["warnings"]))


if __name__ == "__main__":
    unittest.main()
