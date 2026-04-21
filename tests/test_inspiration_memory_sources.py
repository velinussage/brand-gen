import json
import os
import tempfile
import unittest
from pathlib import Path

from brand_gen.inspiration_memory import consolidate_inspiration_memory


class InspirationMemorySourceFallbackTests(unittest.TestCase):
    def test_consolidates_from_design_memory_when_no_local_images_exist(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            brand_gen_dir = root / ".brand-gen"
            brand_dir = brand_gen_dir / "brands" / "sage"
            source_dir = brand_gen_dir / "inspiration" / "premium-branding" / "demo-source" / ".design-memory"
            brand_dir.mkdir(parents=True)
            source_dir.mkdir(parents=True)

            (brand_dir / "inspirations.json").write_text(json.dumps({
                "version": 1,
                "sources": ["demo-source"],
                "mode": "principles",
            }))
            (brand_gen_dir / "inspiration" / "index.json").parent.mkdir(parents=True, exist_ok=True)
            (brand_gen_dir / "inspiration" / "index.json").write_text(json.dumps({
                "version": 1,
                "sources": {
                    "demo-source": {
                        "name": "Demo Source",
                        "status": "complete",
                        "category": "premium-branding",
                        "designMemoryPath": str(source_dir),
                    }
                }
            }))
            (source_dir / "source-summary.json").write_text(json.dumps({
                "source": {
                    "key": "demo-source",
                    "name": "Demo Source",
                    "notes": "Editorial restraint and campaign hierarchy.",
                    "tags": ["editorial", "typography"],
                    "borrow_mechanics": ["editorial hierarchy", "system reduction"],
                    "avoid_literal": ["their logo"],
                    "best_for": ["composition", "campaign framing"]
                },
                "analysis": {
                    "layout_cues": ["strong margins", "single dominant frame"],
                    "palette_lines": ["Neutral-led palette with restrained chroma."],
                    "typography_lines": ["Type should carry hierarchy through scale contrast."],
                    "motion_cues": ["Restrained transitions."]
                }
            }))

            old = os.environ.get("BRAND_GEN_DIR")
            os.environ["BRAND_GEN_DIR"] = str(brand_gen_dir)
            try:
                payload = consolidate_inspiration_memory(brand_dir)
            finally:
                if old is None:
                    os.environ.pop("BRAND_GEN_DIR", None)
                else:
                    os.environ["BRAND_GEN_DIR"] = old

            self.assertEqual(payload["execution_mode"], "configured_source_reduce")
            self.assertEqual(payload["providers_used"], ["design-memory"])
            self.assertTrue(payload["composition_archetypes"])
            self.assertTrue(payload["typography_cues"])
            self.assertIn("design-memory sources", payload["confidence_notes"])


if __name__ == "__main__":
    unittest.main()
