import tempfile
import unittest
from pathlib import Path

from brand_gen.inspiration_doctrine import load_token_fragments, merge_token_fragments


class TokenMergeTests(unittest.TestCase):
    def test_merge_token_fragments_dedupes_sections_and_css_vars(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src1 = root / "src1"
            src2 = root / "src2"
            src1.mkdir()
            src2.mkdir()

            (src1 / "style.md").write_text(
                ":root {\n"
                "  --bg: #ffffff;\n"
                "  --fg: #111111;\n"
                "}\n\n"
                "## Color palette\n"
                "- Warm white base\n"
                "- Charcoal text\n\n"
                "## Typography scale\n"
                "- Display 48 / Body 16\n"
            )
            (src2 / "reference.md").write_text(
                ":root {\n"
                "  --bg: #ffffff;\n"
                "  --accent: #ff6600;\n"
                "}\n\n"
                "## Color palette\n"
                "- Warm white base\n"
                "- Copper accent\n\n"
                "## Typography scale\n"
                "- Display 48 / Body 16\n"
                "- Mono captions 12\n\n"
                "## Tailwind\n"
                "- Use shadow-sm only\n"
            )

            merged = merge_token_fragments([load_token_fragments(src1), load_token_fragments(src2)])
            token_block = merged["token_block"]

            self.assertEqual(token_block.count(":root {"), 1)
            self.assertEqual(token_block.count("--bg: #ffffff;"), 1)
            self.assertIn("--fg: #111111;", token_block)
            self.assertIn("--accent: #ff6600;", token_block)
            self.assertEqual(token_block.count("## Color palette"), 1)
            self.assertEqual(token_block.count("## Typography scale"), 1)
            self.assertEqual(token_block.count("Warm white base"), 1)
            self.assertIn("Copper accent", token_block)
            self.assertIn("Mono captions 12", token_block)
            self.assertIn("## Notes", token_block)
            self.assertIn("Use shadow-sm only", token_block)
            self.assertEqual(len(merged["source_fragments"]), 2)

    def test_load_token_fragments_keeps_file_level_debug_fragments(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "src"
            source.mkdir()
            (source / "style.md").write_text(
                "## Color palette\n"
                "- Copper accent\n\n"
                "## Typography scale\n"
                "- Display 64 / Body 18\n"
            )
            (source / "reference.md").write_text(
                ":root {\n"
                "  --accent: #ff6600;\n"
                "}\n"
            )

            fragments = load_token_fragments(source)

            self.assertEqual(fragments["source"], str(source))
            self.assertTrue(any(item["file"] == "style.md" for item in fragments["files"]))
            self.assertTrue(any(item["file"] == "reference.md" for item in fragments["files"]))
            self.assertIn("--accent: #ff6600;", fragments["css_vars"])
            self.assertIn("- Copper accent", fragments["color_palette"])
            self.assertIn("- Display 64 / Body 18", fragments["typography_scale"])


if __name__ == "__main__":
    unittest.main()
