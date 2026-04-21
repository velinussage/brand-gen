import unittest

from brand_gen.plan_validation import validate_material_plan_dict


class IllustrationOnlyPlanValidationTests(unittest.TestCase):
    def _base_plan(self, material_type: str) -> dict:
        return {
            "material_type": material_type,
            "purpose": "standalone illustration only for the landing page",
            "target_surface": "landing page right-side illustration slot",
            "product_truth_expression": "creators publish skills, communities govern approvals, libraries distribute trusted capabilities",
            "abstraction_level": "medium",
            "brand_anchor_policy": {"rule": "Keep the output clearly branded."},
            "system_mechanic": "one clear routed system gesture",
            "preserve": ["quiet authority"],
            "push": ["publish to govern to distribute story"],
            "ban": ["no full landing page chrome"],
            "prompt_seed": "Standalone illustration only, not the full landing page.",
            "artifact_scope": "illustration_only",
            "selected_inspiration_sources": [],
            "inspiration_requirements": {"required": True, "min_selected_sources": 3},
            "role_pack": {},
        }

    def test_browser_illustration_is_blocked_for_illustration_only_scope(self):
        report = validate_material_plan_dict(self._base_plan("browser-illustration"))
        self.assertTrue(any("Illustration-only request is using interface material" in item for item in report["errors"]))

    def test_feature_illustration_is_warned_not_blocked_for_illustration_only_scope(self):
        report = validate_material_plan_dict(self._base_plan("feature-illustration"))
        self.assertFalse(any("Illustration-only request is using interface material" in item for item in report["errors"]))
        self.assertTrue(any("feature-illustration" in item for item in report["warnings"]))

    def test_explicit_inspiration_set_is_required_for_illustration_only_scope(self):
        report = validate_material_plan_dict(self._base_plan("concept-illustration"))
        self.assertTrue(any("requires an explicit inspiration set" in item for item in report["errors"]))


if __name__ == "__main__":
    unittest.main()
