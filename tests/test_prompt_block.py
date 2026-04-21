from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from brand_gen.prompt_assembly import build_execution_prompt, compress_prompt_body, review_prompt_architecture
from brand_gen.prompt_block import PromptBlock, evict_to_budget


class EvictToBudgetTests(unittest.TestCase):
    def test_under_budget_keeps_all_blocks(self):
        blocks = [
            PromptBlock(id="brand_anchor_rule", text="Anchor", priority=0, constraint_type="hard"),
            PromptBlock(id="selected_inspiration_block", text="Inspiration", priority=85),
        ]
        kept, dropped = evict_to_budget(blocks, 100)
        self.assertEqual([block.id for block in kept], ["brand_anchor_rule", "selected_inspiration_block"])
        self.assertEqual(dropped, [])

    def test_drops_highest_priority_number_first(self):
        blocks = [
            PromptBlock(id="brand_anchor_rule", text="Anchor", priority=0, constraint_type="hard"),
            PromptBlock(id="material_policy", text="Policy" * 20, priority=20),
            PromptBlock(id="role_pack_block", text="Role" * 20, priority=80),
            PromptBlock(id="selected_inspiration_block", text="Inspiration" * 20, priority=85),
        ]
        kept, dropped = evict_to_budget(blocks, 160)
        self.assertEqual([block.id for block in dropped], ["selected_inspiration_block", "role_pack_block"])
        self.assertEqual([block.id for block in kept], ["brand_anchor_rule", "material_policy"])

    def test_hard_blocks_are_never_dropped(self):
        blocks = [
            PromptBlock(id="brand_anchor_rule", text="Anchor" * 20, priority=0, constraint_type="hard"),
            PromptBlock(id="critical_bans", text="Bans" * 20, priority=5, constraint_type="hard"),
            PromptBlock(id="selected_inspiration_block", text="Inspiration" * 20, priority=85),
        ]
        kept, dropped = evict_to_budget(blocks, 40)
        self.assertEqual([block.id for block in kept], ["brand_anchor_rule", "critical_bans"])
        self.assertEqual([block.id for block in dropped], ["selected_inspiration_block"])

    def test_kept_blocks_preserve_original_order(self):
        blocks = [
            PromptBlock(id="brand_anchor_rule", text="Anchor", priority=0, constraint_type="hard"),
            PromptBlock(id="material_policy", text="Policy", priority=20),
            PromptBlock(id="five_slot_brief", text="Brief", priority=40),
            PromptBlock(id="selected_inspiration_block", text="Inspiration" * 40, priority=85),
        ]
        kept, _ = evict_to_budget(blocks, 40)
        self.assertEqual([block.id for block in kept], ["brand_anchor_rule", "material_policy", "five_slot_brief"])


class CompressPromptBodyTests(unittest.TestCase):
    def test_preserves_sentence_order(self):
        body = "Third logo sentence. First plain sentence. Second product sentence. Fourth brand sentence."
        result = compress_prompt_body(body, "social", max_sentences=2, max_chars=60)
        self.assertEqual(result, "Third logo sentence. First plain sentence.")

    def test_single_long_sentence_returns_whole_sentence(self):
        body = "One very long sentence with no sentence break that should stay whole rather than truncating mid thought"
        result = compress_prompt_body(body, "social", max_sentences=1, max_chars=20)
        self.assertEqual(result, body)

    def test_long_first_sentence_does_not_return_full_body(self):
        first = "One very long sentence that exceeds the cap and should remain whole"
        body = f"{first}. Second short sentence."
        result = compress_prompt_body(body, "social", max_sentences=2, max_chars=20)
        self.assertEqual(result, f"{first}.")


class BuildExecutionPromptBlockTests(unittest.TestCase):
    def test_dropped_blocks_key_present_under_budget(self):
        context = {
            "material_prompt_key": "concept_illustration",
            "material_prompt_snippet": "Concept illustration policy.",
            "reference_role_pack": [],
        }
        result = build_execution_prompt(
            "Short body.",
            context,
            material_type="concept-illustration",
            generation_mode="image",
        )
        self.assertIn("dropped_blocks", result)
        self.assertEqual(result["dropped_blocks"], [])
        self.assertIsInstance(result.get("execution_prompt_sections"), dict)

    def test_execution_prompt_payload_is_json_serializable(self):
        context = {
            "material_prompt_key": "concept_illustration",
            "material_prompt_snippet": "Concept illustration policy.",
            "reference_role_pack": [],
        }
        result = build_execution_prompt(
            "Short body.",
            context,
            material_type="concept-illustration",
            generation_mode="image",
        )
        json.dumps(result)

    def test_build_execution_prompt_drops_example_blocks_first(self):
        long_policy = " ".join(f"Policy sentence {i}." for i in range(90))
        long_inspiration = "Selected inspiration translation: " + " ".join(
            f"Inspiration sentence {i}." for i in range(120)
        )
        context = {
            "material_prompt_key": "concept_illustration",
            "material_prompt_snippet": long_policy,
            "reference_role_pack": [
                {
                    "role": "composition",
                    "source_name": "Ref A",
                    "translation": {
                        "borrow_mechanics": ["one dominant crop", "deep negative space"],
                        "avoid_literal": ["literal layout copy"],
                    },
                }
            ],
            "selected_inspiration_translation": long_inspiration,
            "copy_anchor_snippet": "Use approved copy sparingly.",
        }
        budget_map = {
            "total_prelude_cap": 260,
            "compact_body_max_sentences": 3,
            "compact_body_max_chars": 80,
        }
        with patch("brand_gen.prompt_assembly._ni", side_effect=lambda key: budget_map.get(key, 500)):
            result = build_execution_prompt(
                "Body sentence one. Body sentence two. Body sentence three.",
                context,
                material_type="concept-illustration",
                generation_mode="image",
            )
        dropped = [item["id"] for item in result.get("dropped_blocks") or []]
        self.assertTrue(dropped)
        self.assertIn("selected_inspiration_block", dropped)
        self.assertNotIn("brand_anchor_rule", dropped)
        self.assertNotIn("critical_bans", dropped)

    def test_review_prompt_architecture_surfaces_dropped_block_metadata(self):
        long_policy = " ".join(f"Policy sentence {i}." for i in range(90))
        long_inspiration = "Selected inspiration translation: " + " ".join(
            f"Inspiration sentence {i}." for i in range(120)
        )
        context = {
            "resolved_prompt": "Create a concept illustration.",
            "material_prompt_key": "concept_illustration",
            "material_prompt_snippet": long_policy,
            "reference_role_pack": [],
            "reference_analysis_snippet": "",
            "inspiration_doctrine": "",
            "iteration_memory_snippet": "",
            "blackboard_learning_snippet": "",
            "selected_inspiration_translation": long_inspiration,
            "token_block": "",
            "reference_analysis": {},
        }
        budget_map = {
            "total_prelude_cap": 260,
            "compact_body_max_sentences": 3,
            "compact_body_max_chars": 80,
            "compact_memory_cap": 500,
            "selected_inspiration_cap": 500,
        }
        with patch("brand_gen.prompt_assembly._ni", side_effect=lambda key: budget_map.get(key, 500)):
            review = review_prompt_architecture(
                {},
                {},
                "Create a concept illustration.",
                context,
                material_type="concept-illustration",
            )
        self.assertTrue(review.get("dropped_blocks"))
        self.assertTrue(any("dropped lower-priority prompt blocks" in item for item in review.get("recommendations") or []))
        json.dumps(review)


if __name__ == "__main__":
    unittest.main()
