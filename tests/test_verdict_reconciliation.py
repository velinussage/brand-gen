from __future__ import annotations

import unittest

from brand_gen.iteration_memory import capture_feedback_into_iteration_memory
from brand_gen.verdict import Verdict, legacy_verdict_from_entry, reconcile_verdicts


class VerdictReconciliationTests(unittest.TestCase):
    def test_single_verdict_primary_decision(self) -> None:
        verdict = Verdict(gate="vlm", score=4, decision="approve", rationale="clean")
        result = reconcile_verdicts([verdict])
        self.assertEqual(result["primary_decision"], "approve")
        self.assertFalse(result["verdict_conflict"])

    def test_critic_p3_plus_vlm_approved_is_not_conflict(self) -> None:
        result = reconcile_verdicts(
            [
                Verdict(gate="critic", score=4, decision="approve", rationale="P3 non-blocking"),
                Verdict(gate="vlm", score=4, decision="approve", rationale="clean"),
            ]
        )
        self.assertEqual(result["primary_decision"], "approve")
        self.assertFalse(result["verdict_conflict"])

    def test_critic_reject_overrides_vlm_approval_with_conflict(self) -> None:
        result = reconcile_verdicts(
            [
                Verdict(gate="critic", score=1, decision="reject", rationale="P1"),
                Verdict(gate="vlm", score=4, decision="approve", rationale="looks good"),
            ]
        )
        self.assertEqual(result["primary_decision"], "reject")
        self.assertEqual(result["primary_gate"], "critic")
        self.assertTrue(result["verdict_conflict"])
        self.assertIn("critic=reject", result["conflict_summary"])

    def test_iteration_memory_merges_verdicts_for_same_version(self) -> None:
        memory = {}
        memory = capture_feedback_into_iteration_memory(
            memory,
            "v010",
            {"material_type": "social"},
            "Auto-critic: missing proof",
            1,
            "rejected",
            verdicts=[Verdict(gate="critic", score=1, decision="reject", rationale="missing proof", version_id="v010")],
        )
        memory = capture_feedback_into_iteration_memory(
            memory,
            "v010",
            {"material_type": "social"},
            "VLM approved",
            4,
            None,
            verdicts=[Verdict(gate="vlm", score=4, decision="approve", rationale="clean", version_id="v010")],
        )
        self.assertEqual(len(memory["negative_examples"]), 1)
        item = memory["negative_examples"][0]
        self.assertEqual(item["primary_decision"], "reject")
        self.assertTrue(item["verdict_conflict"])
        self.assertEqual({v["gate"] for v in item["verdicts"]}, {"critic", "vlm"})

    def test_legacy_entry_gets_legacy_verdict(self) -> None:
        verdict = legacy_verdict_from_entry("v001", {"score": 1, "status": "rejected", "summary": "bad"})
        self.assertEqual(verdict.gate, "legacy")
        self.assertEqual(verdict.decision, "reject")


if __name__ == "__main__":
    unittest.main()
