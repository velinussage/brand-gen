import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mcp.inspiration_extraction import extract_inspiration_source


class InspirationExtractionTests(unittest.TestCase):
    def _source(self) -> dict:
        return {
            "key": "ramotion-like",
            "name": "Ramotion-like",
            "category": "saas-product-specialists",
            "url": "https://example.com/work",
            "notes": "Iconic SaaS branding and ultra-clean product mockups.",
            "tags": ["saas", "branding", "mockups", "clean", "product"],
            "borrow_mechanics": [
                "single hero move",
                "scale contrast",
                "clean crop discipline",
            ],
            "avoid_literal": [
                "their gradients",
                "their typography",
            ],
            "best_for": ["composition", "product-led campaign framing"],
            "direct_generation_risk": "low",
        }

    def test_extract_inspiration_source_writes_semantic_design_memory(self):
        snapshot = {
            "requested_url": "https://example.com/work",
            "final_url": "https://example.com/work",
            "content_type": "text/html",
            "title": "Work — Example Studio",
            "meta_description": "Premium SaaS work and product case studies.",
            "og_title": "Example Studio Work",
            "og_description": "Selected projects and product showcases.",
            "headings": ["Selected Work", "Product Case Studies", "Feature Highlights"],
            "class_tokens": {"hero": 3, "card": 2, "button": 2, "dashboard": 2},
            "stylesheets": ["https://example.com/app.css"],
            "css_texts": [
                """
                :root { --brand-accent: #7c5cff; --surface: #f7f7fb; }
                .hero { border-radius: 20px; transition: transform 200ms ease; }
                .card { background: #111827; color: #f8fafc; }
                .button { font-family: 'Inter', sans-serif; }
                """
            ],
            "warnings": [],
        }
        with tempfile.TemporaryDirectory() as tmpdir, patch(
            "mcp.inspiration_extraction.capture_web_snapshot", return_value=snapshot
        ):
            result = extract_inspiration_source(self._source(), Path(tmpdir), timeout=5)
            self.assertEqual(result["status"], "complete")
            self.assertEqual(result["mode"], "metadata-plus-fetch")
            dm_dir = Path(result["designMemoryPath"])
            self.assertTrue((dm_dir / "reference.md").exists())
            self.assertTrue((dm_dir / "principles.md").exists())
            self.assertTrue((dm_dir / "components.md").exists())
            self.assertTrue((dm_dir / "layout.md").exists())
            reference = (dm_dir / "reference.md").read_text()
            principles = (dm_dir / "principles.md").read_text()
            components = (dm_dir / "components.md").read_text()
            self.assertIn("--ref-product-proof-emphasis", reference)
            self.assertIn("Borrow mechanics", reference)
            self.assertIn("single hero move", reference)
            self.assertIn("Do not borrow literal elements", principles)
            self.assertIn("hero carrier", components.lower())
            summary = json.loads((dm_dir / "source-summary.json").read_text())
            self.assertFalse(summary["degraded"])
            self.assertIn("Selected Work", summary["snapshot"]["headings"])

    def test_extract_inspiration_source_falls_back_to_metadata_only(self):
        with tempfile.TemporaryDirectory() as tmpdir, patch(
            "mcp.inspiration_extraction.capture_web_snapshot", side_effect=RuntimeError("offline")
        ):
            result = extract_inspiration_source(self._source(), Path(tmpdir), timeout=5)
            self.assertEqual(result["status"], "complete")
            self.assertEqual(result["mode"], "metadata-only")
            self.assertIn("remote fetch unavailable", result["warning"])
            dm_dir = Path(result["designMemoryPath"])
            reference = (dm_dir / "reference.md").read_text()
            principles = (dm_dir / "principles.md").read_text()
            summary = json.loads((dm_dir / "source-summary.json").read_text())
            self.assertIn("metadata-first fallback", reference)
            self.assertIn("curated registry metadata", principles)
            self.assertTrue(summary["degraded"])


if __name__ == "__main__":
    unittest.main()
