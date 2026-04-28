from __future__ import annotations

import argparse
import unittest
from types import SimpleNamespace
from unittest import mock

from brand_gen.command_registry import build_parser
from brand_gen.commands import review as review_commands
from brand_gen.iteration_memory import capture_feedback_into_iteration_memory


class ReviewDecisionTests(unittest.TestCase):
    def test_feedback_parser_reject_refuses_score(self) -> None:
        parser = build_parser()
        with self.assertRaises(SystemExit):
            parser.parse_args(["feedback", "v001", "--reject", "--score", "3", "--notes", "bad"])

    def test_feedback_reject_requires_notes(self) -> None:
        args = SimpleNamespace(version="v001", reject=True, score=None, notes="", status=None, prompt=None, lock=None)
        with mock.patch.object(review_commands, "load_manifest", return_value={"versions": {"v001": {}}}), \
             mock.patch.object(review_commands, "get_brand_dir"):
            with self.assertRaises(SystemExit) as ctx:
                review_commands.cmd_feedback(args)
        self.assertEqual(ctx.exception.code, 2)

    def test_reject_decision_is_preserved_in_iteration_memory(self) -> None:
        memory = capture_feedback_into_iteration_memory(
            {},
            "v192",
            {"material_type": "stinger-animation", "decision": "reject", "rejection_reason": "0/5 hard reject"},
            "0/5 hard reject: incoherent metaphor",
            1,
            "rejected",
            decision="reject",
            rejection_reason="0/5 hard reject",
        )
        item = memory["negative_examples"][-1]
        self.assertEqual(item["score"], 1)
        self.assertEqual(item["decision"], "reject")
        self.assertEqual(item["primary_gate"], "user")
        self.assertEqual(item["rejection_reason"], "0/5 hard reject")
        self.assertEqual(item["verdicts"][0]["gate"], "user")


if __name__ == "__main__":
    unittest.main()
