import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL_PATH = ROOT / "skills" / "brand-gen" / "SKILL.md"


class SkillQualityGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.skill_text = SKILL_PATH.read_text()

    def test_skill_mentions_submit_critique(self):
        self.assertIn("submit-critique", self.skill_text)

    def test_skill_mentions_quality_gate(self):
        self.assertIn("quality gate", self.skill_text)

    def test_skill_mentions_pipeline(self):
        self.assertIn("bgen pipeline", self.skill_text)

    def test_what_to_avoid_section_exists(self):
        self.assertIn("## What to avoid", self.skill_text)


if __name__ == "__main__":
    unittest.main()
