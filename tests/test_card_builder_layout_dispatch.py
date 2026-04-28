from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from brand_gen.card_builder import build_web_app_share_card_payload
from brand_gen.card_engine import default_layout_spec
from brand_gen.route_predicates import requires_prompt_detail_matrix


class CardBuilderLayoutDispatchTests(unittest.TestCase):
    def test_predicate_requires_positive_prompt_detail_signal(self) -> None:
        self.assertFalse(
            requires_prompt_detail_matrix(
                "announcement-card",
                "prompt",
                has_source_url=False,
                has_detail_blocks=False,
            )
        )
        self.assertTrue(
            requires_prompt_detail_matrix(
                "announcement-card",
                "prompt",
                has_source_url=True,
                has_detail_blocks=False,
            )
        )
        self.assertTrue(
            requires_prompt_detail_matrix(
                "announcement-card",
                "prompt",
                has_source_url=False,
                has_detail_blocks=True,
            )
        )
        self.assertFalse(
            requires_prompt_detail_matrix(
                "announcement-card",
                "prompt",
                has_source_url=True,
                has_detail_blocks=True,
                share_card_retired=True,
            )
        )

    def test_default_layout_no_source_prompt_falls_back_to_portrait(self) -> None:
        spec = default_layout_spec("announcement-card", entity_type="prompt", has_source_url=False, has_detail_blocks=False)
        self.assertEqual(spec.canvas_preset, "portrait")
        self.assertEqual(spec.columns, 1)

    def test_default_layout_source_prompt_uses_document_matrix(self) -> None:
        spec = default_layout_spec("announcement-card", entity_type="prompt", has_source_url=True, has_detail_blocks=False)
        self.assertEqual(spec.canvas_preset, "document")
        self.assertEqual(spec.proof_style, "document")

    def test_no_source_social_prompt_payload_does_not_use_detail_matrix(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            brand_dir = Path(td)
            with patch("brand_gen.card_builder.validate_brand_workspace_dir", return_value=brand_dir), \
                 patch("brand_gen.card_builder.load_brand_memory", return_value=(None, None, {"brand_name": "Test"}, {"brand": {"name": "Test"}})), \
                 patch("brand_gen.card_builder.resolve_brand_asset_paths", return_value=[]), \
                 patch("brand_gen.card_builder.fetch_card_page_data", return_value={"title": "", "description": "", "h1": "", "h2": "", "lines": []}):
                card = build_web_app_share_card_payload(
                    {
                        "brand_dir": str(brand_dir),
                        "material_type": "social",
                        "entity_type": "prompt",
                        "headline": "Capability routing",
                        "proof_excerpt": "No source URL should not force prompt detail chrome.",
                        "design_variance": 8,
                    }
                )
        self.assertNotEqual(card.composition_mode, "detail_matrix")
        self.assertEqual(card.layout_spec.canvas_preset, "square")


if __name__ == "__main__":
    unittest.main()
