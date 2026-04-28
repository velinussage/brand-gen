from __future__ import annotations

import unittest

from brand_gen.prompt_assembly import _cap_with_telemetry
from brand_gen.prompt_block import PromptBlock, evict_to_budget
from brand_gen.prompt_telemetry import clear_prompt_telemetry, drain_prompt_telemetry


class PromptTruncationTelemetryTests(unittest.TestCase):
    def test_cap_site_records_pre_priority_telemetry(self) -> None:
        clear_prompt_telemetry()
        text = "One very long sentence without enough room to keep all of it. Second sentence survives only if budget allows."
        capped = _cap_with_telemetry(
            text,
            48,
            block_name="brand_prelude",
            pre_priority=True,
            stage="full_prompt_prelude",
        )
        self.assertLess(len(capped), len(text))
        events = drain_prompt_telemetry()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["block_name"], "brand_prelude")
        self.assertTrue(events[0]["pre_priority"])

    def test_evict_to_budget_records_dropped_block(self) -> None:
        clear_prompt_telemetry()
        kept, dropped = evict_to_budget(
            [
                PromptBlock(id="brand_anchor_rule", text="hard block", priority=0, constraint_type="hard"),
                PromptBlock(id="reference_analysis_caveat", text="x" * 500, priority=80),
            ],
            budget_chars=80,
        )
        self.assertEqual([block.id for block in kept], ["brand_anchor_rule"])
        self.assertEqual([block.id for block in dropped], ["reference_analysis_caveat"])
        events = drain_prompt_telemetry()
        self.assertEqual(events[0]["kind"], "dropped_block")
        self.assertEqual(events[0]["block_name"], "reference_analysis_caveat")
        self.assertFalse(events[0]["pre_priority"])


if __name__ == "__main__":
    unittest.main()
