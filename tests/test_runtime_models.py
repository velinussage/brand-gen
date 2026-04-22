import json
import tempfile
import unittest
from pathlib import Path

from brand_gen.runtime_models import (
    COPY_BEARING_MATERIALS,
    MATERIAL_CONFIG,
    MODELS,
    recommend_text_model,
    resolve_default_model,
    resolve_learned_model,
)


class CopyBearingDefaultModelTests(unittest.TestCase):
    def test_copy_bearing_hybrid_defaults_to_flux2flex(self):
        model = resolve_default_model(
            "editorial-card", "image", "hybrid", [Path("ref.png")]
        )
        self.assertEqual(model, "flux-2-flex")

    def test_non_copy_bearing_hybrid_keeps_nano_banana(self):
        model = resolve_default_model(
            "logo", "image", "hybrid", [Path("ref.png")]
        )
        self.assertEqual(model, "nano-banana-2")

    def test_copy_bearing_pure_defaults_to_material_config(self):
        model = resolve_default_model("wordmark", "image", "pure", [])
        self.assertEqual(model, "ideogram")

    def test_browser_illustration_with_refs_uses_flux2flex(self):
        model = resolve_default_model(
            "browser-illustration", "image", "reference", [Path("ref.png")]
        )
        self.assertEqual(model, "flux-2-flex")

    def test_flux2flex_exists_in_models_json(self):
        self.assertIn("flux-2-flex", MODELS["image"])
        cfg = MODELS["image"]["flux-2-flex"]
        self.assertEqual(cfg["replicate_id"], "black-forest-labs/flux-2-flex")
        self.assertEqual(cfg["max_reference_images"], 10)

    def test_mockup_materials_are_registered(self):
        self.assertIn("device-mockup", MATERIAL_CONFIG)
        self.assertIn("lifestyle-mockup", MATERIAL_CONFIG)
        self.assertIn("website-hero-illustration", MATERIAL_CONFIG)
        self.assertNotIn("billboard-mockup", MATERIAL_CONFIG)
        self.assertIn("device-mockup", COPY_BEARING_MATERIALS)

    def test_mockup_hybrid_with_refs_uses_flux2flex(self):
        model = resolve_default_model(
            "device-mockup", "image", "hybrid", [Path("ref.png")]
        )
        self.assertEqual(model, "flux-2-flex")


class RecommendTextModelTests(unittest.TestCase):
    def test_recommend_text_model_with_low_accuracy(self):
        critique = {"text_accuracy": 0.3, "p1": [], "text_issues": []}
        rec = recommend_text_model(critique, "nano-banana-2", "social", True)
        self.assertEqual(rec, "flux-2-flex")

    def test_recommend_text_model_with_text_issues(self):
        critique = {"text_accuracy": 1.0, "text_issues": ["misspelled word"]}
        rec = recommend_text_model(critique, "nano-banana-2", "social", True)
        self.assertEqual(rec, "flux-2-flex")

    def test_recommend_text_model_with_p1_text(self):
        critique = {"text_accuracy": 1.0, "text_issues": [], "p1": ["Text is garbled"]}
        rec = recommend_text_model(critique, "recraft-v4", "landing-hero", False)
        self.assertEqual(rec, "ideogram")

    def test_recommend_text_model_clean_returns_none(self):
        critique = {"text_accuracy": 0.95, "p1": ["palette mismatch"], "text_issues": []}
        rec = recommend_text_model(critique, "nano-banana-2", "social", True)
        self.assertIsNone(rec)

    def test_recommend_text_model_already_on_target_returns_none(self):
        critique = {"text_accuracy": 0.3}
        rec = recommend_text_model(critique, "flux-2-flex", "social", True)
        self.assertIsNone(rec)

    def test_recommend_text_model_pure_mode_recommends_ideogram(self):
        critique = {"text_accuracy": 0.5}
        rec = recommend_text_model(critique, "recraft-v4", "wordmark", False)
        self.assertEqual(rec, "ideogram")

    def test_recommend_text_model_pure_already_ideogram(self):
        critique = {"text_accuracy": 0.5}
        rec = recommend_text_model(critique, "ideogram", "wordmark", False)
        self.assertIsNone(rec)


class ResolveLearnedModelTests(unittest.TestCase):
    """Promote-from-learnings: when a brand has a modelPreferences entry for
    a material type, that model is returned and overrides the static
    material_config default. This closes the gap where the default model
    (recraft-v4) kept winning over a promoted learning (nano-banana-2) on
    concept-illustration runs.
    """

    def _write_learnings(self, tmp: Path, prefs: list) -> Path:
        brand_dir = tmp / "brand"
        brand_dir.mkdir()
        (brand_dir / "learnings.json").write_text(json.dumps({"modelPreferences": prefs}))
        return brand_dir

    def test_returns_none_when_no_brand_dir(self):
        self.assertIsNone(resolve_learned_model("concept-illustration", None))

    def test_returns_none_when_learnings_absent(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(resolve_learned_model("concept-illustration", Path(tmp)))

    def test_returns_none_when_no_matching_material(self):
        with tempfile.TemporaryDirectory() as tmp:
            brand_dir = self._write_learnings(Path(tmp), [
                {"material_type": "brand-scene", "text": "[brand_scene] Winning setup: hybrid + flux-2-pro + with refs"},
            ])
            self.assertIsNone(resolve_learned_model("concept-illustration", brand_dir))

    def test_matches_underscore_material_type(self):
        """Legacy learnings use underscore (concept_illustration); modern caller uses hyphen."""
        with tempfile.TemporaryDirectory() as tmp:
            brand_dir = self._write_learnings(Path(tmp), [
                {"material_type": "concept_illustration", "text": "[concept_illustration] Winning setup: hybrid + nano-banana-2 + with refs"},
            ])
            self.assertEqual(resolve_learned_model("concept-illustration", brand_dir), "nano-banana-2")

    def test_matches_hyphen_material_type(self):
        with tempfile.TemporaryDirectory() as tmp:
            brand_dir = self._write_learnings(Path(tmp), [
                {"material_type": "concept-illustration", "text": "[concept-illustration] Winning setup: hybrid + nano-banana-2 + with refs"},
            ])
            self.assertEqual(resolve_learned_model("concept-illustration", brand_dir), "nano-banana-2")

    def test_returns_most_recent_preference_when_multiple(self):
        with tempfile.TemporaryDirectory() as tmp:
            brand_dir = self._write_learnings(Path(tmp), [
                {"material_type": "concept-illustration", "text": "Winning setup: hybrid + flux-2-pro + with refs"},
                {"material_type": "concept-illustration", "text": "Winning setup: hybrid + nano-banana-2 + with refs"},
            ])
            self.assertEqual(resolve_learned_model("concept-illustration", brand_dir), "nano-banana-2")

    def test_returns_none_for_unknown_model_token(self):
        with tempfile.TemporaryDirectory() as tmp:
            brand_dir = self._write_learnings(Path(tmp), [
                {"material_type": "concept-illustration", "text": "[concept-illustration] Winning setup: hybrid + not-a-real-model + with refs"},
            ])
            self.assertIsNone(resolve_learned_model("concept-illustration", brand_dir))

    def test_corrupt_learnings_returns_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            brand_dir = Path(tmp) / "brand"
            brand_dir.mkdir()
            (brand_dir / "learnings.json").write_text("{not json")
            self.assertIsNone(resolve_learned_model("concept-illustration", brand_dir))
