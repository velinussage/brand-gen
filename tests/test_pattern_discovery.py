import json
import tempfile
import unittest
from pathlib import Path

from brand_gen.pattern_discovery import discover_prompt_patterns


class PatternDiscoveryTests(unittest.TestCase):
    def _write_manifest(self, brand_dir: Path, versions: dict):
        (brand_dir / "manifest.json").write_text(json.dumps({"versions": versions}))

    def test_discovers_multiple_positive_hypotheses_for_material(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            brand_dir = Path(tmpdir)
            self._write_manifest(
                brand_dir,
                {
                    "v001": {
                        "material_type": "system-explainer-illustration",
                        "model": "gpt-image-2",
                        "score": 4,
                        "raw_prompt": "Textless editorial explainer with one mechanism and generous negative space.",
                        "notes": "User scored 4/5. Calm editorial direction with one dominant path.",
                        "critic_summary": {"clean": ["single explanation lane", "quiet composition"]},
                    },
                    "v002": {
                        "material_type": "system-explainer-illustration",
                        "model": "gpt-image-2",
                        "score": 5,
                        "raw_prompt": "Flat geometric explainer diagram with one hero card and routed provenance flow.",
                        "notes": "User scored 5/5. Flat graphic style landed.",
                        "critic_summary": {"clean": ["crisp diagrammatic flow"]},
                    },
                },
            )
            discovered = discover_prompt_patterns(brand_dir, "system-explainer-illustration")

        self.assertEqual(discovered["retrieval_mode"], "material_exact")
        self.assertGreaterEqual(len(discovered["hypotheses"]), 2)
        packet = discovered["packet"]
        self.assertIn("Pattern hypotheses", packet)
        self.assertIn("gpt-image-2", packet)

    def test_collects_avoid_moves_from_negative_runs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            brand_dir = Path(tmpdir)
            self._write_manifest(
                brand_dir,
                {
                    "v010": {
                        "material_type": "system-explainer-illustration",
                        "model": "flux-2-flex",
                        "score": 1,
                        "raw_prompt": "Busy screenshot-like dashboard explainer.",
                        "notes": "User override: 0/5 absolute reject. Logo too big and different explanations competing at once.",
                        "critic_summary": {"p1": ["Text is off"], "p2": ["Too screenshot-like"]},
                    }
                },
            )
            discovered = discover_prompt_patterns(brand_dir, "system-explainer-illustration")

        joined = " ".join(discovered["avoid_moves"])
        self.assertIn("logo", joined.lower())
        self.assertTrue("competing" in joined.lower() or "screenshot" in joined.lower())

    def test_falls_back_to_material_group_when_exact_material_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            brand_dir = Path(tmpdir)
            self._write_manifest(
                brand_dir,
                {
                    "v101": {
                        "material_type": "concept-illustration",
                        "model": "gpt-image-2",
                        "score": 4,
                        "raw_prompt": "Textless editorial concept illustration with one dominant metaphor.",
                        "notes": "User scored 4/5. Strong single-thesis concept.",
                        "critic_summary": {"clean": ["one dominant metaphor"]},
                    }
                },
            )
            discovered = discover_prompt_patterns(brand_dir, "editorial-metaphor-illustration")

        self.assertEqual(discovered["retrieval_mode"], "material_group_fallback")
        self.assertTrue(discovered["hypotheses"])


if __name__ == "__main__":
    unittest.main()
