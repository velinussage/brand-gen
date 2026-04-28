from __future__ import annotations

import unittest

from brand_gen.verdict import (
    Verdict,
    verdict_from_critic,
    verdict_from_rubric_payload,
    verdict_from_vlm,
)


class VerdictEmissionTests(unittest.TestCase):
    def test_verdict_round_trip_and_validation(self) -> None:
        verdict = Verdict(gate="critic", score=1, decision="reject", rationale="P1 issue", version_id="v001")
        self.assertEqual(Verdict.from_dict(verdict.to_dict()), verdict)
        with self.assertRaises(ValueError):
            Verdict(gate="critic", score=0, decision="reject", rationale="bad")

    def test_critic_p1_maps_to_reject(self) -> None:
        verdict = verdict_from_critic("v001", {"p1": ["Product proof missing"], "p2": [], "p3": []})
        self.assertIsNotNone(verdict)
        self.assertEqual(verdict.gate, "critic")
        self.assertEqual(verdict.score, 1)
        self.assertEqual(verdict.decision, "reject")

    def test_vlm_approved_maps_to_approve(self) -> None:
        verdict = verdict_from_vlm("v002", {"vlm_available": True, "approved": True, "p1": [], "p2": []})
        self.assertIsNotNone(verdict)
        self.assertEqual(verdict.gate, "vlm")
        self.assertEqual(verdict.score, 4)
        self.assertEqual(verdict.decision, "approve")

    def test_rubric_disqualifier_forces_reject(self) -> None:
        verdict = verdict_from_rubric_payload(
            "v003",
            {
                "axis_scores": {"craft": 5, "value_proposition_fidelity": 4},
                "decision": "approve",
                "disqualifier_triggered": True,
                "disqualifier_rule_id": "wrong_product",
            },
        )
        self.assertEqual(verdict.gate, "rubric")
        self.assertEqual(verdict.score, 1)
        self.assertEqual(verdict.decision, "reject")


if __name__ == "__main__":
    unittest.main()
