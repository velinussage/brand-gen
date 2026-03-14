"""Tests for non-interface prelude budget caps.

Verifies that the prelude capping logic introduced to prevent prompt bloat
(v15: 7205-char prelude → nonsensical output) correctly truncates
non-interface materials while leaving interface materials unchanged.
"""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MCP_DIR = REPO_ROOT / "mcp"
if str(MCP_DIR) not in sys.path:
    sys.path.insert(0, str(MCP_DIR))

from brand_iterate import (  # type: ignore
    INTERFACE_MATERIAL_KEYS,
    NON_INTERFACE_MATERIAL_KEYS,
    NON_INTERFACE_DOCTRINE_CAP,
    NON_INTERFACE_PRELUDE_CAP,
    NON_INTERFACE_REF_ANALYSIS_CAP,
    NON_INTERFACE_TOTAL_PRELUDE_CAP,
    cap_text_at_sentence,
    build_effective_prompt,
    review_prompt_architecture,
)


class TestCapTextAtSentence(unittest.TestCase):
    def test_short_text_unchanged(self):
        text = "Keep the copper palette. Use cream accents."
        self.assertEqual(cap_text_at_sentence(text, 200), text)

    def test_truncates_at_sentence_boundary(self):
        text = "First sentence. Second sentence. Third sentence that is very long indeed."
        result = cap_text_at_sentence(text, 40)
        self.assertIn("First sentence.", result)
        self.assertLessEqual(len(result), 45)  # small overshoot OK for punctuation
        self.assertTrue(result.endswith("."))

    def test_hard_truncation_when_no_boundary(self):
        text = "One very long sentence with no periods that goes on and on and on"
        result = cap_text_at_sentence(text, 30)
        self.assertTrue(result.endswith("…"))
        self.assertLessEqual(len(result), 31)

    def test_empty_and_none(self):
        self.assertEqual(cap_text_at_sentence("", 100), "")
        self.assertEqual(cap_text_at_sentence(None, 100), "")

    def test_exact_boundary(self):
        text = "Exact."
        self.assertEqual(cap_text_at_sentence(text, 6), "Exact.")


class TestNonInterfacePreludeCaps(unittest.TestCase):
    """Verify that build_effective_prompt caps non-interface preludes."""

    def _make_profile(self):
        return {"brand_name": "Test"}

    def _make_identity(self, prelude_chars=2500):
        # Generate a prelude that exceeds the cap
        sentences = [f"Sentence number {i} describes brand anatomy details." for i in range(50)]
        long_prelude = " ".join(sentences)[:prelude_chars]
        return {
            "generation_guardrails": {
                "non_interface_prompt_prelude": long_prelude,
                "interface_prompt_prelude": "Short interface prelude.",
            }
        }

    def test_non_interface_prelude_is_capped(self):
        """Non-interface materials should have their prelude capped."""
        profile = self._make_profile()
        identity = self._make_identity(2500)
        result = build_effective_prompt(
            profile, identity, "Create a bold campaign poster.",
            material_type="campaign-poster",
        )
        resolved = result["resolved_prompt"]
        # Total resolved = capped prelude (≤3000) + body (~30 chars) + joining
        # Must be under total cap + body + margin
        self.assertLess(len(resolved), NON_INTERFACE_TOTAL_PRELUDE_CAP + 500,
                        f"Resolved prompt ({len(resolved)} chars) should respect total prelude cap")

    def test_interface_prelude_not_capped_by_non_interface_logic(self):
        """Interface materials should NOT be affected by non-interface caps."""
        profile = self._make_profile()
        identity = self._make_identity()
        result = build_effective_prompt(
            profile, identity, "Show the product dashboard.",
            material_type="browser-illustration",
        )
        prelude = result["brand_prelude"]
        # Interface uses interface_prompt_prelude which is short
        self.assertEqual(prelude.strip(), "Short interface prelude.")


class TestReviewArchitectureCaps(unittest.TestCase):
    """Verify that review_prompt_architecture also caps non-interface refined prompts."""

    def test_refined_prompt_respects_total_cap(self):
        profile = {"brand_name": "Test"}
        # Build a long context
        long_prelude = " ".join(f"Brand anatomy detail {i}." for i in range(80))
        identity = {
            "generation_guardrails": {
                "non_interface_prompt_prelude": long_prelude,
            }
        }
        context = {
            "resolved_prompt": long_prelude + "\n\nMake a poster.",
            "material_prompt_key": "campaign_poster",
            "material_prompt_snippet": "Use bold composition.",
            "reference_role_pack": [],
            "reference_analysis_snippet": "",
            "inspiration_doctrine": "Embrace warm copper tones throughout.",
            "iteration_memory_snippet": "",
            "token_block": "",
            "reference_analysis": {},
        }
        result = review_prompt_architecture(
            profile, identity, "Make a poster.", context,
            material_type="campaign-poster",
        )
        refined = result["refined_prompt"]
        # Should be capped — not the full 3000+ char monstrosity
        self.assertLess(len(refined), NON_INTERFACE_TOTAL_PRELUDE_CAP + 800,
                        f"Refined prompt ({len(refined)} chars) should respect total prelude cap")


if __name__ == "__main__":
    unittest.main()
