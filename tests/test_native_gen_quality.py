import json
import unittest
from pathlib import Path

from brand_gen.material_planning import build_effective_prompt
from brand_gen.runtime_brand import load_prompt_fragments


QUALITY_SNIPPET = "Editorial photography, medium-format depth, real material textures — never CGI renders."
MODELS_PATH = Path(__file__).resolve().parents[1] / "brand_gen" / "models.json"


class NativeGenQualityTests(unittest.TestCase):
    def test_load_prompt_fragments_includes_non_interface_quality_prelude(self):
        fragments = load_prompt_fragments()

        self.assertIn("non_interface_quality_prelude", fragments)
        self.assertEqual(fragments["non_interface_quality_prelude"], QUALITY_SNIPPET)

    def test_build_effective_prompt_includes_quality_snippet_for_non_interface_materials(self):
        payload = build_effective_prompt(
            {"brand_name": "Test Brand"},
            {},
            "Create a campaign poster for the launch.",
            material_type="campaign-poster",
            disable_brand_guardrails=False,
        )

        self.assertEqual(payload["non_interface_quality_prelude"], QUALITY_SNIPPET)
        self.assertIn(QUALITY_SNIPPET, payload["resolved_prompt"])

    def test_build_effective_prompt_omits_quality_snippet_for_interface_materials(self):
        payload = build_effective_prompt(
            {"brand_name": "Test Brand"},
            {},
            "Show the product dashboard in a browser window.",
            material_type="browser-illustration",
            disable_brand_guardrails=False,
        )

        self.assertEqual(payload["non_interface_quality_prelude"], "")
        self.assertNotIn(QUALITY_SNIPPET, payload["resolved_prompt"])

    def test_models_json_maps_style_for_recraft_v3_and_v4(self):
        models = json.loads(MODELS_PATH.read_text())
        image_models = models["image"]

        self.assertEqual(image_models["recraft-v3"]["field_map"]["style"], "style")
        self.assertEqual(image_models["recraft-v4"]["field_map"]["style"], "style")

    def test_models_json_lists_supported_styles_for_recraft_v4(self):
        models = json.loads(MODELS_PATH.read_text())
        supported_styles = models["image"]["recraft-v4"]["supported_styles"]

        self.assertEqual(
            supported_styles,
            ["any", "realistic_image", "digital_illustration", "vector_illustration", "icon"],
        )


if __name__ == "__main__":
    unittest.main()
