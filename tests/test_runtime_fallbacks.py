import io
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest.mock import patch

from brand_gen import blackboard, route_predicates
from brand_gen.pipeline_runner import PipelineRunner
from brand_gen.reference_analysis import check_inspiration_pipeline_status, extract_reference_image_stats
from brand_gen.pipeline_types import RoutingBrief
from brand_gen.runtime_brand import load_brand_memory, load_workflow_router_rules


class RuntimeFallbackTests(unittest.TestCase):
    def test_blackboard_warns_and_falls_back_on_corrupt_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            brand_dir = Path(tmpdir)
            (brand_dir / "blackboard.json").write_text("{not json")
            stderr = io.StringIO()
            with redirect_stderr(stderr):
                board = blackboard.load_blackboard(brand_dir)
            self.assertEqual(board["schema_type"], "brand_blackboard")
            self.assertIn("Failed to load blackboard", stderr.getvalue())

    def test_route_predicates_warn_and_fallback_when_classifier_fails(self):
        stderr = io.StringIO()
        with patch("brand_gen.route_predicates.classify_workflow_route_smart", side_effect=RuntimeError("boom")), \
             patch("brand_gen.route_predicates.load_workflow_router_rules", return_value={"routes": []}), \
             redirect_stderr(stderr):
            result = route_predicates.route_brief(RoutingBrief(material_type="social", material_key="unknown"))
        self.assertEqual(result["route_key"], "generative_explore")
        self.assertIn("route_classifier_warning", stderr.getvalue())

    def test_pipeline_stage_callback_warning_does_not_raise(self):
        runner = PipelineRunner(Path("/tmp/brand-gen"), {}, {}, on_stage_complete=lambda *_: (_ for _ in ()).throw(RuntimeError("callback boom")))
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            runner._notify("route", {"ok": True})
        self.assertIn("Pipeline stage callback failed for route", stderr.getvalue())

    def test_reference_analysis_warns_on_invalid_image(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "bad.png"
            path.write_text("not-an-image")
            stderr = io.StringIO()
            with redirect_stderr(stderr):
                stats = extract_reference_image_stats(path)
            self.assertEqual(stats["dominant_colors"], [])
            self.assertTrue(
                not stderr.getvalue() or "Reference analysis fell back to empty stats" in stderr.getvalue()
            )

    def test_inspiration_pipeline_status_suggestions_use_module_entrypoint(self):
        status = check_inspiration_pipeline_status(None, None, "hybrid")
        self.assertTrue(status["suggestions"])
        self.assertTrue(all("bgen " in item for item in status["suggestions"]))

    def test_inspiration_pipeline_status_finds_uncategorized_sources_in_any_category(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            brand_gen_dir = root / ".brand-gen"
            brand_dir = brand_gen_dir / "brands" / "sage"
            brand_dir.mkdir(parents=True)
            (brand_dir / "inspirations.json").write_text('{"sources":["pentagram"]}')
            (brand_gen_dir / "inspiration" / "premium-branding" / "pentagram" / ".design-memory").mkdir(parents=True)

            status = check_inspiration_pipeline_status(brand_gen_dir, "sage", "hybrid")

            self.assertTrue(status["ok"])
            self.assertEqual(status["warnings"], [])

    def test_workflow_router_rules_next_commands_use_module_entrypoint(self):
        rules = load_workflow_router_rules()
        for route in rules.get("routes") or []:
            for command in route.get("next_commands") or []:
                self.assertIn("bgen ", command)
                self.assertNotIn("python3 mcp/brand_iterate.py", command)

    def test_load_brand_memory_falls_back_to_saved_brand_for_session_without_local_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            brand_gen_dir = root / ".brand-gen"
            saved_brand_dir = brand_gen_dir / "brands" / "sage"
            saved_brand_dir.mkdir(parents=True)
            (saved_brand_dir / "brand-profile.json").write_text('{"brand_assets":{"icon":"public/logo.png"}}')
            (saved_brand_dir / "brand-identity.json").write_text('{"generation_guardrails":{"material_prompt_snippets":{"social":{"default":"Use Sage proof carefully."}}}}')
            session_dir = brand_gen_dir / "sessions" / "sage-session" / "brand-materials"
            session_dir.mkdir(parents=True)

            with patch("brand_gen.runtime_brand.get_brand_gen_dir", return_value=brand_gen_dir), \
                 patch("brand_gen.runtime_brand.resolve_context_brand_key", return_value="sage"):
                profile_path, identity_path, profile, identity = load_brand_memory(session_dir)

            self.assertEqual(profile_path, (saved_brand_dir / "brand-profile.json").resolve())
            self.assertEqual(identity_path, (saved_brand_dir / "brand-identity.json").resolve())
            self.assertEqual(profile["brand_assets"]["icon"], "public/logo.png")
            self.assertIn("social", (identity.get("generation_guardrails") or {}).get("material_prompt_snippets", {}))


if __name__ == "__main__":
    unittest.main()
