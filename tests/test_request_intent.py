import unittest

from brand_gen.request_intent import resolve_planner_material_type


class PlannerMaterialTypeResolutionTests(unittest.TestCase):
    def test_brand_scene_upgrades_to_illustrated_brand_world(self):
        resolved, note = resolve_planner_material_type("brand-scene")
        self.assertEqual(resolved, "illustrated-brand-world")
        self.assertIn("illustrated-brand-world", note)

    def test_campaign_poster_upgrades_to_proof_poster(self):
        resolved, note = resolve_planner_material_type("campaign-poster")
        self.assertEqual(resolved, "proof-poster")
        self.assertIn("proof-poster", note)

    def test_pattern_system_defaults_to_site_pattern_tile(self):
        resolved, note = resolve_planner_material_type(
            "pattern-system",
            purpose="Create one subtle background pattern for the website",
            target_surface="pricing page section background",
        )
        self.assertEqual(resolved, "site-pattern-tile")
        self.assertIn("site-pattern-tile", note)

    def test_pattern_system_can_route_to_pattern_board(self):
        resolved, note = resolve_planner_material_type(
            "pattern-system",
            briefing="Make an exploration board with a few pattern variants for review",
        )
        self.assertEqual(resolved, "pattern-board")
        self.assertIn("pattern-board", note)

    def test_concept_illustration_defaults_to_system_explainer(self):
        resolved, note = resolve_planner_material_type(
            "concept-illustration",
            purpose="Explain how the routing workflow works",
            product_truth_expression="one visible protocol mechanic with flow",
        )
        self.assertEqual(resolved, "system-explainer-illustration")
        self.assertIn("system-explainer-illustration", note)

    def test_concept_illustration_can_route_to_editorial_metaphor(self):
        resolved, note = resolve_planner_material_type(
            "concept-illustration",
            purpose="Create an essay illustration with one strong metaphor",
            briefing="thought leadership narrative opener",
        )
        self.assertEqual(resolved, "editorial-metaphor-illustration")
        self.assertIn("editorial-metaphor-illustration", note)

    def test_new_material_type_stays_stable(self):
        resolved, note = resolve_planner_material_type("proof-poster")
        self.assertEqual(resolved, "proof-poster")
        self.assertEqual(note, "")


if __name__ == "__main__":
    unittest.main()
