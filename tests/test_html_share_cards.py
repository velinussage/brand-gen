import argparse
import struct
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from brand_gen.cli_builders import build_pipeline_cli
from brand_gen.html_share_cards import evaluate_html_layout_warnings, execute_html_share_card_scratchpad
from brand_gen.pipeline_request import PIPELINE_MCP_PROPERTIES, PipelineRequest
from brand_gen.card_engine import LayoutSpec, ShareCardPayload, _verify_render, default_layout_spec
from brand_gen.card_builder import build_web_app_share_card_payload


class PipelineRequestHtmlTests(unittest.TestCase):
    def test_pipeline_request_schema_and_defaults_are_html_only(self):
        self.assertNotIn("stitch_model", PIPELINE_MCP_PROPERTIES)
        request = PipelineRequest.from_mcp_args(
            {
                "material_type": "announcement-card",
                "render_backend": "html",
                "source_url": "https://app.sageprotocol.io/prompts/bafkexample",
                "entity_type": "prompt",
            }
        ).with_pipeline_defaults()
        self.assertEqual(request.render_backend, "html")
        self.assertEqual(request.product_truth_expression, "real prompt text resolved from source")
        self.assertEqual(request.target_surface, "portrait social poster / story-style share")
        self.assertIn("governed prompt", request.purpose)

    def test_pipeline_cli_does_not_accept_stitch_flags(self):
        parser = argparse.ArgumentParser(prog="pipeline")
        build_pipeline_cli(parser, inspire_urls={})
        args = parser.parse_args(["--material-type", "announcement-card", "--render-backend", "html"])
        self.assertEqual(args.render_backend, "html")
        with self.assertRaises(SystemExit):
            parser.parse_args(["--material-type", "announcement-card", "--render-backend", "stitch"])
        with self.assertRaises(SystemExit):
            parser.parse_args(["--material-type", "announcement-card", "--stitch-model", "GEMINI_3_1_PRO"])


class ShareCardPayloadTests(unittest.TestCase):
    @patch("brand_gen.card_builder.resolve_brand_asset_paths")
    @patch("brand_gen.card_builder.load_brand_memory")
    @patch("brand_gen.card_builder.validate_brand_workspace_dir")
    @patch("brand_gen.card_builder.fetch_card_page_data")
    def test_build_payload_prefers_literal_prompt_body_lines(
        self,
        mock_fetch_sage,
        mock_validate,
        mock_load_memory,
        mock_resolve_assets,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            brand_dir = Path(tmp)
            logo_path = brand_dir / "logo.png"
            logo_path.write_bytes(b"png")
            mock_validate.return_value = brand_dir
            mock_load_memory.return_value = (None, None, {}, {})
            mock_resolve_assets.return_value = [logo_path]
            mock_fetch_sage.return_value = {
                "title": "Knowledge Management for Agents",
                "h1": "Knowledge Management for Agents",
                "h2": "Prompt Details",
                "description": "How to build, organize, and query knowledge bases that help agents remember, learn, and retrieve information effectively.",
                "cid": "bafkreiexamplecid",
                "lines": [
                    "Agents forget. Every session starts fresh. Without persistent knowledge:",
                    "Episodic Memory - What happened",
                    "Semantic Memory - Facts and concepts",
                    "Procedural Memory - How to do things",
                    "Option A: Vector Database (Semantic Search)",
                    "Best for: Semantic search, similarity matching, large unstructured knowledge bases",
                ],
            }
            card = build_web_app_share_card_payload(
                {
                    "brand_dir": str(brand_dir),
                    "material_type": "announcement-card",
                    "render_backend": "html",
                    "entity_type": "prompt",
                    "source_url": "https://app.sageprotocol.io/prompts/bafkreiexamplecid",
                    "selected_surface_strategy": "editorial_poster",
                    "design_variance": 8,
                }
            )
        self.assertEqual(card.headline, "Knowledge Management for Agents")
        self.assertIn("Agents forget. Every session starts fresh.", card.proof_excerpt)
        self.assertNotEqual(card.proof_excerpt.strip(), "")
        self.assertIn(card.composition_mode, {"statement_poster", "prompt_sheet", "artifact_monolith", "reference_sheet"})
        self.assertEqual(card.logo_path, str(logo_path))

    def test_layout_warning_flags_dense_prompt_cards(self):
        card = ShareCardPayload(
            material_type="announcement-card",
            surface="artifact share card",
            entity_type="prompt",
            source_url="https://app.sageprotocol.io/prompts/bafkexample",
            source_domain="app.sageprotocol.io",
            page_title="Example",
            headline="A very long share-card headline that will absolutely compress the hierarchy in a social card",
            subhead="Subhead",
            cta="Open prompt",
            logo_path="",
            proof_title="",
            proof_meta=[],
            proof_excerpt="x" * 500,
            proof_row="y" * 200,
            proof_crop_path="",
            proof_weight_guidance="",
            support_crop_path="",
            layout_spec=LayoutSpec(canvas_preset="document"),
            composition_mode="utility_sidebar",
        )
        warnings = evaluate_html_layout_warnings(card)
        self.assertGreaterEqual(len(warnings), 3)


class ExecuteHtmlScratchpadTests(unittest.TestCase):
    @patch("brand_gen.html_share_cards.write_pipeline_qa_report", return_value=("report", "/tmp/qa.md"))
    @patch("brand_gen.html_share_cards.write_agent_visual_review_packet", return_value=({}, "/tmp/review.json"))
    @patch("brand_gen.html_share_cards._verify_render", return_value={"passed": True})
    @patch("brand_gen.html_share_cards.build_web_app_share_card_payload")
    @patch("brand_gen.html_share_cards.render_html_to_png")
    @patch("brand_gen.html_share_cards.validate_brand_workspace_dir")
    def test_execute_html_share_card_scratchpad_updates_manifest(
        self,
        mock_validate,
        mock_render,
        mock_build_card,
        _mock_verify,
        _mock_review,
        _mock_qa,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            brand_dir = Path(tmp)
            mock_validate.return_value = brand_dir
            mock_build_card.return_value = ShareCardPayload(
                material_type="announcement-card",
                surface="artifact share card",
                entity_type="prompt",
                source_url="https://app.sageprotocol.io/prompts/bafkreiexamplecid",
                source_domain="app.sageprotocol.io",
                page_title="Knowledge Management for Agents",
                headline="Knowledge Management for Agents",
                subhead="How to build, organize, and query knowledge bases that help agents remember, learn, and retrieve information effectively.",
                cta="Open prompt",
                logo_path="",
                proof_title="",
                proof_meta=[],
                proof_excerpt="Agents forget. Every session starts fresh. Without persistent knowledge, every workflow starts over.",
                proof_row="Episodic memory • semantic memory • procedural memory",
                proof_crop_path="",
                proof_weight_guidance="Keep the reading card legible.",
                support_crop_path="",
                composition_mode="prompt_sheet",
                composition_summary="Prompt-led artifact sheet",
                layout_spec=LayoutSpec(canvas_preset="document"),
            )

            def _fake_render(html_path: Path, png_path: Path, *, width: int, height: int) -> bool:
                html_path = Path(html_path)
                png_path = Path(png_path)
                if not html_path.exists():
                    return False
                png_path.write_bytes(b"fakepng")
                return True

            mock_render.side_effect = _fake_render
            payload = {
                "schema_type": "generation_scratchpad",
                "brand_dir": str(brand_dir),
                "material_type": "announcement-card",
                "workflow_mode": "reference",
                "workflow_id": "wf-test",
                "tag": "html-card-test",
                "source_url": "https://app.sageprotocol.io/prompts/bafkreiexamplecid",
                "entity_type": "prompt",
                "headline": "Knowledge Management for Agents",
                "subhead": "How to build, organize, and query knowledge bases that help agents remember, learn, and retrieve information effectively.",
                "proof_excerpt": "Agents forget. Every session starts fresh. Without persistent knowledge, every workflow starts over.",
                "proof_row": "Episodic memory • semantic memory • procedural memory",
                "selected_surface_strategy": "editorial_poster",
                "selected_surface_strategy_label": "Editorial poster",
                "selected_surface_strategy_summary": "Statement-led artifact share",
                "selected_surface_strategy_layout_family": "poster",
                "surface_strategy_reason": "Exact prompt text needs a strong title field with a subordinate reading card.",
                "design_variance": 7,
                "execution_prompt": "render html card",
                "effective_prompt": "render html card",
                "raw_prompt": "render html card",
                "selected_reference_ids": [],
                "selected_inspiration_ids": [],
            }
            vid = execute_html_share_card_scratchpad(payload, workflow_id="wf-test")
            self.assertEqual(vid, "v001")
            manifest = __import__("brand_gen.runtime", fromlist=["load_manifest"]).load_manifest(brand_dir)
            entry = manifest["versions"][vid]
            self.assertEqual(entry["render_backend"], "html")
            self.assertEqual(entry["render_source"], "html_browser")
            self.assertEqual(entry["generation_mode"], "html-share-card")
            self.assertEqual(entry["source_url"], payload["source_url"])
            self.assertEqual(entry["entity_type"], "prompt")
            self.assertTrue((brand_dir / entry["files"][0]).exists())
            self.assertTrue(Path(entry["html_path"]).exists())


class LayoutSpecTests(unittest.TestCase):
    def test_default_social_is_two_column_left(self):
        spec = default_layout_spec("social")
        self.assertEqual(spec.columns, 2)
        self.assertEqual(spec.alignment, "left")
        self.assertEqual(spec.proof_position, "right")
        self.assertEqual(spec.headline_size, "xl")
        self.assertEqual(spec.canvas_preset, "square")

    def test_default_x_feed_is_two_column_wide(self):
        spec = default_layout_spec("x-feed")
        self.assertEqual(spec.columns, 2)
        self.assertEqual(spec.canvas_preset, "wide")
        self.assertEqual(spec.padding, "normal")

    def test_default_announcement_low_var_is_centered(self):
        spec = default_layout_spec("announcement-card", 4)
        self.assertEqual(spec.columns, 1)
        self.assertEqual(spec.alignment, "center")
        self.assertEqual(spec.accent_style, "none")

    def test_default_announcement_high_var_has_accent(self):
        spec = default_layout_spec("announcement-card", 8)
        self.assertEqual(spec.columns, 1)
        self.assertEqual(spec.alignment, "left")
        self.assertEqual(spec.accent_style, "left-strip")

    def test_default_announcement_prompt_entity_is_document(self):
        spec = default_layout_spec("announcement-card", entity_type="prompt")
        self.assertEqual(spec.columns, 2)
        self.assertEqual(spec.canvas_preset, "document")
        self.assertEqual(spec.proof_style, "document")

    def test_to_dict_from_dict_roundtrip(self):
        original = LayoutSpec(columns=2, alignment="center", accent_style="top-bar", canvas_preset="wide")
        reconstructed = LayoutSpec.from_dict(original.to_dict())
        self.assertEqual(original.to_dict(), reconstructed.to_dict())

    def test_from_dict_handles_empty(self):
        spec = LayoutSpec.from_dict({})
        self.assertEqual(spec.columns, 1)
        self.assertEqual(spec.alignment, "left")
        self.assertEqual(spec.padding, "generous")

    def test_from_dict_handles_none(self):
        spec = LayoutSpec.from_dict(None)
        self.assertEqual(spec.columns, 1)


def _make_valid_png(width: int, height: int, *, body_size: int = 8192) -> bytes:
    """Build a minimal PNG-like byte sequence with correct magic + IHDR dimensions."""
    magic = b'\x89PNG\r\n\x1a\n'
    # IHDR chunk: length(4) + "IHDR"(4) + width(4) + height(4) + ...
    ihdr_data = struct.pack(">II", width, height) + b'\x08\x06\x00\x00\x00'
    ihdr_len = struct.pack(">I", len(ihdr_data))
    ihdr = ihdr_len + b"IHDR" + ihdr_data
    # Pad to at least body_size
    padding = b'\x00' * max(0, body_size - len(magic) - len(ihdr))
    return magic + ihdr + padding


class RenderVerificationTests(unittest.TestCase):
    def test_verify_passes_valid_render(self):
        with tempfile.TemporaryDirectory() as tmp:
            png = Path(tmp) / "card.png"
            png.write_bytes(_make_valid_png(1200, 1200))
            result = _verify_render(
                png, "<h1>Hello World</h1>",
                expected_width=1200, expected_height=1200, headline="Hello World",
            )
            self.assertTrue(result["passed"])
            self.assertTrue(all(result["checks"].values()))

    def test_verify_fails_missing_file(self):
        result = _verify_render(
            "/nonexistent/path.png", "<h1>Test</h1>",
            expected_width=1200, expected_height=1200,
        )
        self.assertFalse(result["passed"])
        self.assertFalse(result["checks"]["file_exists"])

    def test_verify_fails_tiny_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            png = Path(tmp) / "tiny.png"
            png.write_bytes(_make_valid_png(1200, 1200, body_size=100))
            result = _verify_render(
                png, "<h1>Test</h1>",
                expected_width=1200, expected_height=1200,
            )
            self.assertFalse(result["passed"])
            self.assertFalse(result["checks"]["min_size"])

    def test_verify_fails_wrong_dimensions(self):
        with tempfile.TemporaryDirectory() as tmp:
            png = Path(tmp) / "wrong.png"
            png.write_bytes(_make_valid_png(800, 600))
            result = _verify_render(
                png, "<h1>Test</h1>",
                expected_width=1200, expected_height=1200,
            )
            self.assertFalse(result["passed"])
            self.assertFalse(result["checks"]["dimensions"])

    def test_verify_fails_headline_not_in_html(self):
        with tempfile.TemporaryDirectory() as tmp:
            png = Path(tmp) / "card.png"
            png.write_bytes(_make_valid_png(1200, 1200))
            result = _verify_render(
                png, "<h1>Something Else</h1>",
                expected_width=1200, expected_height=1200, headline="Missing Headline",
            )
            self.assertFalse(result["passed"])
            self.assertFalse(result["checks"]["headline_in_html"])

    def test_verify_fails_non_png_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            png = Path(tmp) / "fake.png"
            png.write_bytes(b"JFIF" + b'\x00' * 9000)
            result = _verify_render(
                png, "<h1>Test</h1>",
                expected_width=1200, expected_height=1200,
            )
            self.assertFalse(result["passed"])
            self.assertFalse(result["checks"]["png_magic"])

    def test_verify_passes_no_headline_check_when_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            png = Path(tmp) / "card.png"
            png.write_bytes(_make_valid_png(1200, 1500))
            result = _verify_render(
                png, "<div>No headline tag</div>",
                expected_width=1200, expected_height=1500, headline="",
            )
            self.assertTrue(result["passed"])
            self.assertNotIn("headline_in_html", result["checks"])

    def test_render_suspect_status_in_manifest(self):
        """Integration: when render verification fails, visual_review_status is render_suspect."""
        with tempfile.TemporaryDirectory() as tmp:
            brand_dir = Path(tmp)
            with patch("brand_gen.html_share_cards.write_pipeline_qa_report", return_value=("report", "/tmp/qa.md")):
                with patch("brand_gen.html_share_cards.write_agent_visual_review_packet", return_value=({}, "/tmp/review.json")):
                    with patch("brand_gen.html_share_cards._verify_render", return_value={"passed": False, "checks": {"min_size": False}}):
                        with patch("brand_gen.html_share_cards.build_web_app_share_card_payload") as mock_card:
                            with patch("brand_gen.html_share_cards.render_html_to_png") as mock_render:
                                with patch("brand_gen.html_share_cards.validate_brand_workspace_dir", return_value=brand_dir):
                                    mock_card.return_value = ShareCardPayload(
                                        material_type="social",
                                        surface="social share",
                                        entity_type="prompt",
                                        source_url="https://example.com",
                                        source_domain="example.com",
                                        page_title="Test",
                                        headline="Test Card",
                                        subhead="Sub",
                                        cta="Open",
                                        logo_path="",
                                        proof_title="",
                                        proof_meta=[],
                                        proof_excerpt="Some text.",
                                        proof_row="",
                                        proof_crop_path="",
                                        proof_weight_guidance="",
                                        support_crop_path="",
                                        layout_spec=LayoutSpec(),
                                        composition_mode="split_editorial",
                                    )
                                    mock_render.side_effect = lambda hp, pp, *, width, height: Path(pp).write_bytes(b"fake") or True
                                    payload = {
                                        "schema_type": "generation_scratchpad",
                                        "brand_dir": str(brand_dir),
                                        "material_type": "social",
                                        "workflow_mode": "reference",
                                        "workflow_id": "wf-suspect",
                                        "tag": "test",
                                        "source_url": "https://example.com",
                                        "entity_type": "prompt",
                                        "design_variance": 5,
                                        "execution_prompt": "test",
                                        "effective_prompt": "test",
                                        "raw_prompt": "test",
                                        "selected_reference_ids": [],
                                        "selected_inspiration_ids": [],
                                    }
                                    vid = execute_html_share_card_scratchpad(payload, workflow_id="wf-suspect")
                                    manifest = __import__("brand_gen.runtime", fromlist=["load_manifest"]).load_manifest(brand_dir)
                                    entry = manifest["versions"][vid]
                                    self.assertEqual(entry["visual_review_status"], "render_suspect")


class CardPluginTests(unittest.TestCase):
    def test_plugin_registry_ordering(self):
        from brand_gen.card_plugins import get_plugins
        plugins = get_plugins()
        self.assertGreaterEqual(len(plugins), 2)
        self.assertEqual(plugins[0].name, "sage")
        self.assertEqual(plugins[0].priority, 10)
        self.assertEqual(plugins[1].name, "web")
        self.assertEqual(plugins[1].priority, 100)

    def test_plugin_sage_can_handle(self):
        from brand_gen.card_plugins.sage import SageCardPlugin
        plugin = SageCardPlugin()
        self.assertTrue(plugin.can_handle("https://app.sageprotocol.io/prompts/test", "prompt"))
        self.assertFalse(plugin.can_handle("https://example.com/page", "prompt"))

    def test_plugin_web_fallback_always_handles(self):
        from brand_gen.card_plugins.web import WebCardPlugin
        plugin = WebCardPlugin()
        self.assertTrue(plugin.can_handle("https://example.com", "prompt"))
        self.assertTrue(plugin.can_handle("https://app.sageprotocol.io/prompts/test", "skill"))

    def test_fetch_card_page_data_dispatches(self):
        from brand_gen.card_plugins import fetch_card_page_data, clear_plugins, register_plugin, CardDataPlugin, get_plugins

        class FakePlugin(CardDataPlugin):
            priority = 1

            @property
            def name(self) -> str:
                return "fake"

            def can_handle(self, url: str, entity_type: str) -> bool:
                return "fake.test" in url

            def fetch_page_data(self, url, entity_type):
                return {"title": "Fake", "description": "test", "h1": "Fake", "h2": "", "lines": []}

        saved = list(get_plugins())
        clear_plugins()
        try:
            register_plugin(FakePlugin())
            result = fetch_card_page_data("https://fake.test/page", "prompt")
            self.assertIsNotNone(result)
            self.assertEqual(result["title"], "Fake")
            # Non-matching URL
            result2 = fetch_card_page_data("https://other.test/page", "prompt")
            self.assertIsNone(result2)
        finally:
            clear_plugins()
            for p in saved:
                register_plugin(p)

    def test_clear_plugins(self):
        from brand_gen.card_plugins import clear_plugins, get_plugins, register_plugin
        saved = list(get_plugins())
        clear_plugins()
        try:
            self.assertEqual(len(get_plugins()), 0)
        finally:
            for p in saved:
                register_plugin(p)


if __name__ == "__main__":
    unittest.main()
