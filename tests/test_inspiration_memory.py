import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from brand_gen.inspiration_memory import (
    consolidate_inspiration_memory,
    inspiration_memory_paths,
    load_inspiration_memory,
    normalize_inspiration_memory,
    save_inspiration_memory,
)


class InspirationMemoryTests(unittest.TestCase):
    def test_consolidate_inspiration_memory_aggregates_vlm_results(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            brand_dir = Path(tmpdir)
            inspiration_dir = brand_dir / "inspiration"
            inspiration_dir.mkdir()
            first = inspiration_dir / "one.png"
            second = inspiration_dir / "two.png"
            first.write_bytes(b"fake")
            second.write_bytes(b"fake")

            analyses = [
                {
                    "summary": "Calm editorial framing.",
                    "palette_hexes": ["#112233", "#445566"],
                    "typography_cues": ["large serif headline"],
                    "composition_archetypes": ["one dominant crop"],
                    "surface_finishes": ["matte paper"],
                    "motion_cues": ["slow parallax"],
                    "negative_cues": ["literal logo borrowing"],
                    "confidence_notes": "clear cues",
                },
                {
                    "summary": "Quiet poster energy.",
                    "palette_hexes": ["#112233", "#778899"],
                    "typography_cues": ["large serif headline", "small utility sans"],
                    "composition_archetypes": ["one dominant crop", "generous negative space"],
                    "surface_finishes": ["matte paper"],
                    "motion_cues": ["slow parallax"],
                    "negative_cues": ["literal logo borrowing"],
                    "confidence_notes": "clear cues",
                },
            ]

            with patch("brand_gen.inspiration_memory.run_vlm_json", side_effect=analyses):
                payload = consolidate_inspiration_memory(brand_dir)

            self.assertEqual(payload["execution_mode"], "standalone_command")
            self.assertEqual(payload["analysis_strategy"], "per_image_remote_vlm_then_local_reduce")
            self.assertEqual(payload["palette_direction"][0], "#112233")
            self.assertIn("large serif headline", payload["typography_cues"])
            self.assertIn("one dominant crop", payload["composition_archetypes"])
            self.assertIn("slow parallax", payload["motion_cues"])
            self.assertIn("literal logo borrowing", payload["negative_cues"])
            self.assertTrue(payload["seed_prompt"])

    def test_save_and_load_inspiration_memory_round_trip(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            brand_dir = Path(tmpdir)
            payload = {
                "summary": "One shared style direction.",
                "palette_direction": ["#112233"],
                "typography_cues": ["high-contrast serif"],
                "composition_archetypes": ["one dominant crop"],
                "surface_finishes": ["matte paper"],
                "motion_cues": ["slow reveal"],
                "negative_cues": ["literal logo borrowing"],
                "seed_prompt": "Favor one dominant crop.",
                "sources": [{"path": "/tmp/ref.png"}],
            }

            json_path, md_path = save_inspiration_memory(brand_dir, payload)
            loaded = load_inspiration_memory(brand_dir)

            self.assertTrue(json_path.exists())
            self.assertTrue(md_path.exists())
            self.assertEqual(loaded["summary"], "One shared style direction.")
            self.assertIn("high-contrast serif", loaded["typography_cues"])

    def test_inspiration_memory_paths_are_separate_from_identity(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            brand_dir = Path(tmpdir)
            json_path, md_path = inspiration_memory_paths(brand_dir)
            self.assertEqual(json_path.name, "inspiration-memory.json")
            self.assertEqual(md_path.name, "inspiration-memory.md")
            self.assertNotEqual(json_path.name, "brand-identity.json")

    def test_normalize_inspiration_memory_backfills_new_optional_fields(self):
        payload = normalize_inspiration_memory({"summary": "legacy"})
        self.assertEqual(payload["summary"], "legacy")
        self.assertEqual(payload["execution_mode"], "standalone_command")
        self.assertEqual(payload["analysis_strategy"], "per_image_remote_vlm_then_local_reduce")
        self.assertEqual(payload["providers_used"], [])


if __name__ == "__main__":
    unittest.main()
