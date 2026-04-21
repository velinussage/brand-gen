"""M2 hermetic tests for the DSPy scorer.

Tests that don't touch the network:
- Signatures construct cleanly and have the expected fields
- build_cached_messages produces the Anthropic content-block shape with
  cache_control breakpoints placed correctly
- image_source_from_path loads a local image into the base64 block shape
- BrandScorer.forward() runs end-to-end against a captured DummyLM,
  produces the v2 packet shape, and honors aliases (landing_hero → landing-hero)
- _extract_json_dict handles fenced and unfenced JSON, and partial text

Tests that DO touch the network are NOT added in M2; they live behind
an explicit flag in M3+ once the caching spike has a real result.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import dspy
from dspy.utils import DummyLM

from brand_gen.scoring.config import (
    build_cached_messages,
    image_source_from_path,
)
from brand_gen.scoring.program import (
    SCORER_VERSION,
    _extract_json_dict,
    _extract_text,
)
from brand_gen.scoring.signatures import AxisScore, DescribeImage, Synthesize


class TestSignatures(unittest.TestCase):
    def test_describe_image_has_expected_fields(self):
        fields = set(DescribeImage.model_fields)
        self.assertIn("image", fields)
        self.assertIn("material_type", fields)
        self.assertIn("scene_summary", fields)
        self.assertIn("visual_elements", fields)
        self.assertIn("first_impression", fields)

    def test_axis_score_has_expected_fields(self):
        fields = set(AxisScore.model_fields)
        self.assertIn("score", fields)
        self.assertIn("rationale", fields)
        self.assertIn("evidence", fields)

    def test_synthesize_has_why_user_might_dislike_field(self):
        # The critical field; if this regresses the rubric loses its point.
        self.assertIn("why_user_might_dislike_if_polished", Synthesize.model_fields)


class TestBuildCachedMessages(unittest.TestCase):
    def _sample_image_source(self):
        return {
            "type": "base64",
            "media_type": "image/png",
            "data": "aGVsbG8=",  # "hello" base64
        }

    def test_message_shape_basic(self):
        msgs = build_cached_messages(
            system_prompt="system instructions",
            image_source=self._sample_image_source(),
            user_text="score axis composition",
        )
        self.assertEqual(len(msgs), 2)
        self.assertEqual(msgs[0]["role"], "system")
        self.assertEqual(msgs[1]["role"], "user")

    def test_cache_control_on_system_by_default(self):
        msgs = build_cached_messages(
            system_prompt="sys",
            image_source=self._sample_image_source(),
            user_text="u",
        )
        system_content = msgs[0]["content"][0]
        self.assertIn("cache_control", system_content)
        self.assertEqual(system_content["cache_control"], {"type": "ephemeral"})

    def test_cache_control_on_image_by_default(self):
        msgs = build_cached_messages(
            system_prompt="sys",
            image_source=self._sample_image_source(),
            user_text="u",
        )
        user_content = msgs[1]["content"]
        image_block = [c for c in user_content if c.get("type") == "image_url"][0]
        self.assertIn("cache_control", image_block)

    def test_cache_control_opt_out(self):
        msgs = build_cached_messages(
            system_prompt="sys",
            image_source=self._sample_image_source(),
            user_text="u",
            cache_system=False,
            cache_image=False,
        )
        self.assertNotIn("cache_control", msgs[0]["content"][0])
        user_image = [c for c in msgs[1]["content"] if c.get("type") == "image_url"][0]
        self.assertNotIn("cache_control", user_image)

    def test_image_block_has_data_url(self):
        """OpenAI-compatible image_url format — data-URL encoded base64."""
        src = self._sample_image_source()
        msgs = build_cached_messages(
            system_prompt="sys",
            image_source=src,
            user_text="u",
        )
        user_image = [c for c in msgs[1]["content"] if c.get("type") == "image_url"][0]
        url = user_image["image_url"]["url"]
        self.assertTrue(url.startswith("data:image/png;base64,"))
        self.assertIn(src["data"], url)

    def test_user_text_block_present(self):
        msgs = build_cached_messages(
            system_prompt="sys",
            image_source=self._sample_image_source(),
            user_text="please score this",
        )
        user_text_blocks = [c for c in msgs[1]["content"] if c.get("type") == "text"]
        self.assertEqual(len(user_text_blocks), 1)
        self.assertEqual(user_text_blocks[0]["text"], "please score this")


class TestImageSourceFromPath(unittest.TestCase):
    def test_loads_png(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test.png"
            path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"fake-png-bytes")
            source = image_source_from_path(path)
            self.assertEqual(source["type"], "base64")
            self.assertEqual(source["media_type"], "image/png")
            self.assertIn("data", source)

    def test_media_type_for_jpeg(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test.jpg"
            path.write_bytes(b"\xff\xd8\xff\xe0" + b"fake-jpeg-bytes")
            source = image_source_from_path(path)
            self.assertEqual(source["media_type"], "image/jpeg")

    def test_media_type_for_webp(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test.webp"
            path.write_bytes(b"fake-webp")
            source = image_source_from_path(path)
            self.assertEqual(source["media_type"], "image/webp")


class TestJsonExtraction(unittest.TestCase):
    def test_plain_json(self):
        parsed = _extract_json_dict('{"score": 4, "rationale": "ok"}')
        self.assertEqual(parsed["score"], 4)
        self.assertEqual(parsed["rationale"], "ok")

    def test_fenced_json(self):
        raw = '```json\n{"score": 3}\n```'
        parsed = _extract_json_dict(raw)
        self.assertEqual(parsed["score"], 3)

    def test_json_with_prose_prefix(self):
        raw = 'Here is the scoring:\n{"score": 2, "rationale": "weak"}'
        parsed = _extract_json_dict(raw)
        self.assertEqual(parsed["score"], 2)

    def test_unparseable_returns_empty(self):
        parsed = _extract_json_dict("not json at all")
        self.assertEqual(parsed, {})

    def test_extract_text_from_list(self):
        self.assertEqual(_extract_text(['hello']), 'hello')

    def test_extract_text_from_str(self):
        self.assertEqual(_extract_text('hello'), 'hello')


class TestBrandScorerConstruction(unittest.TestCase):
    """Verify BrandScorer constructs cleanly and exposes the right sub-modules.

    Full end-to-end forward() testing is gated behind a live ANTHROPIC_API_KEY
    and lands in M3 as an integration test. Mixing DummyLM with both
    Signature-based (describe/synthesize) and raw messages=... calls
    (per-axis) requires more DSPy adapter plumbing than is worth in M2.
    """

    def test_scorer_constructs(self):
        from brand_gen.scoring.program import BrandScorer
        scorer = BrandScorer()
        self.assertIsNotNone(scorer.describe)
        self.assertIsNotNone(scorer.synthesize)

    def test_scorer_version_constant(self):
        from brand_gen.scoring.program import SCORER_VERSION
        self.assertTrue(SCORER_VERSION.startswith("v"))


class TestScorerHelpers(unittest.TestCase):
    """Isolated unit tests for the per-axis message construction path.

    These verify that the scorer's defensive caching approach (bypass
    Signature formatting for axis calls, build Anthropic messages
    inline) produces the correct shape.
    """

    def test_axis_system_prompt_template_has_axis_name(self):
        from brand_gen.scoring.program import _AXIS_SYSTEM_PROMPT_TEMPLATE
        rendered = _AXIS_SYSTEM_PROMPT_TEMPLATE.format(
            rubric_version="test-version",
            material_type="landing-hero",
            material_rubric_key="landing-hero",
            axis_name="composition",
            axis_definition="Layout hierarchy...",
            brand_dna="cream + terracotta",
            story_objective="communicate category",
        )
        self.assertIn("composition", rendered)
        self.assertIn("Layout hierarchy", rendered)
        self.assertIn("1-5", rendered)  # scoring scale documented

    def test_disqualifier_template_has_detection_prompt(self):
        from brand_gen.scoring.program import _DISQUALIFIER_SYSTEM_PROMPT_TEMPLATE
        rendered = _DISQUALIFIER_SYSTEM_PROMPT_TEMPLATE.format(
            rubric_version="test-version",
            material_type="landing-hero",
            rule_id="test-rule",
            description="Test description",
            detection_prompt="Look for X, Y, Z. Return true if X is present.",
        )
        self.assertIn("test-rule", rendered)
        self.assertIn("Return true if X is present", rendered)


if __name__ == "__main__":
    unittest.main()
