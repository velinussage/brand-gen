import unittest

from brand_gen.critique_policy import build_critique_policy, normalize_critique_policy
from brand_gen.generation_flow import apply_generation_critique_policy


class CritiquePolicyTests(unittest.TestCase):
    def test_advisory_policy_reports_without_blocking_generation(self):
        policy = build_critique_policy(
            critique_mode="advisory",
            entrypoint="critique-plan",
            blocking=["Missing required role refs: product_truth"],
        )

        self.assertEqual(policy["critique_mode"], "advisory")
        self.assertEqual(policy["blocking_policy"], "report_only")
        self.assertFalse(policy["blocks_generation"])
        self.assertFalse(policy["bypass_recorded"])

    def test_strict_policy_records_bypass_when_allow_blocking_is_set(self):
        payload = {
            "state": {"status": "blocked"},
            "checks": {"blocking": ["Missing required role refs: product_truth"], "warnings": []},
        }

        policy = apply_generation_critique_policy(payload, entrypoint="pipeline", allow_blocking=True)

        self.assertEqual(policy["critique_mode"], "strict")
        self.assertEqual(policy["blocking_policy"], "allow_with_recorded_bypass")
        self.assertTrue(policy["bypass_recorded"])
        self.assertFalse(policy["blocks_generation"])
        self.assertEqual(payload["state"]["status"], "ready_to_generate_with_bypass")

    def test_legacy_strict_payloads_block_by_default(self):
        policy = normalize_critique_policy({}, default_mode="strict", entrypoint="generate", blocking=["x"])

        self.assertEqual(policy["blocking_policy"], "block_generation")
        self.assertTrue(policy["blocks_generation"])
        self.assertFalse(policy["bypass_recorded"])

    def test_missing_reference_asset_block_cannot_be_bypassed(self):
        payload = {
            "state": {"status": "blocked"},
            "checks": {"blocking": ["Mode 'reference' requires at least one reference asset."], "warnings": []},
        }

        policy = apply_generation_critique_policy(payload, entrypoint="pipeline", allow_blocking=True)

        self.assertTrue(policy["blocks_generation"])
        self.assertEqual(policy["blocking_policy"], "block_generation")
        self.assertFalse(policy["bypass_recorded"])
        self.assertEqual(payload["state"]["status"], "blocked")

    def test_html_share_card_policy_block_cannot_be_bypassed(self):
        payload = {
            "state": {"status": "blocked"},
            "checks": {
                "blocking": [
                    "HTML share-card policy block: Sage social/editorial HTML share-card variants duplicate proof-poster."
                ],
                "warnings": [],
            },
        }

        policy = apply_generation_critique_policy(payload, entrypoint="pipeline", allow_blocking=True)

        self.assertTrue(policy["blocks_generation"])
        self.assertEqual(policy["blocking_policy"], "block_generation")
        self.assertFalse(policy["bypass_recorded"])
        self.assertEqual(payload["state"]["status"], "blocked")


if __name__ == "__main__":
    unittest.main()
