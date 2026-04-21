import unittest

from brand_gen.route_predicates import RoutingBrief, route_brief


class RoutePredicateTests(unittest.TestCase):
    def test_set_scope_takes_priority(self):
        result = route_brief(RoutingBrief(material_type='social', material_key='social', set_scope=True))
        self.assertEqual(result['route_key'], 'set_orchestrator')
        self.assertGreaterEqual(result['score'], 1.0)

    def test_motion_reference_routes_to_motion(self):
        result = route_brief(RoutingBrief(material_type='feature-animation', material_key='feature_animation', has_motion_reference=True))
        self.assertEqual(result['route_key'], 'motion_specialist')
        self.assertEqual(result['method'], 'predicate')

    def test_translate_material_key_routes_to_translate(self):
        result = route_brief(RoutingBrief(material_type='browser-illustration', material_key='browser_illustration'))
        self.assertEqual(result['route_key'], 'reference_translate')
        self.assertEqual(result['method'], 'predicate')

    def test_low_confidence_defaults_to_generative_explore_with_scores(self):
        result = route_brief(RoutingBrief(material_type='unknown', material_key='unknown'))
        self.assertEqual(result['route_key'], 'generative_explore')
        self.assertIn(result['method'], {'default', 'llm', 'predicate'})
        self.assertIn('generative_explore', result['score_vector'])

    def test_landing_hero_routes_to_generative_explore(self):
        """After removing deterministic compose, landing_hero should fall through to LLM or explore."""
        result = route_brief(RoutingBrief(material_type='landing-hero', material_key='landing_hero'))
        self.assertNotEqual(result['route_key'], 'deterministic_compose')
        self.assertIn('generative_explore', result['score_vector'])
        self.assertNotIn('deterministic_compose', result['score_vector'])

    def test_illustration_only_request_avoids_reference_translate_for_page_adjacent_materials(self):
        result = route_brief(
            RoutingBrief(
                material_type='feature-illustration',
                material_key='feature_illustration',
                goal='Need just the illustration for the landing page, not the full landing page',
                request='standalone illustration only, no nav or page chrome',
            )
        )
        self.assertEqual(result['route_key'], 'generative_explore')
        self.assertEqual(result['method'], 'predicate')


if __name__ == '__main__':
    unittest.main()
