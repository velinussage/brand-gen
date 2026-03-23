import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL_PATH = ROOT / "skills" / "brand-gen" / "SKILL.md"


class SkillQualityGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.skill_text = SKILL_PATH.read_text()

    def test_skill_mentions_aspirational_brands_bar(self):
        self.assertIn("aspirational brands bar", self.skill_text)

    def test_skill_mentions_submit_critique(self):
        self.assertIn("submit-critique", self.skill_text)

    def test_skill_names_reference_brands(self):
        for brand in ("Stripe", "Aesop", "Criterion", "Muji"):
            with self.subTest(brand=brand):
                self.assertIn(brand, self.skill_text)

    def test_skill_mentions_mean_score_threshold(self):
        self.assertIn("mean score < 3", self.skill_text)

    def test_what_to_avoid_mentions_quality_gate(self):
        _, _, tail = self.skill_text.partition("## What to avoid")
        self.assertTrue(tail, "Expected '## What to avoid' section in SKILL.md")
        self.assertIn("quality gate", tail)


if __name__ == "__main__":
    unittest.main()
