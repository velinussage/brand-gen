import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from brand_gen.commands.inspection import cmd_compare
from brand_gen.generation_flow import execute_generation_scratchpad
from brand_gen.material_planning import (
    build_material_plan_from_args,
    build_role_pack_override_from_plan,
    build_effective_prompt,
    create_material_plan,
    evaluate_prompt_review_rules,
    resolve_material_prompt_snippet,
    review_prompt_architecture,
    validate_material_plan_dict,
)
from brand_gen.media_board import build_agent_regeneration_prompt
from brand_gen.runtime_brand import load_prompt_review_rules
from brand_gen.session_summary import build_session_summary_payload


class PromptUpdateTests(unittest.TestCase):
    def test_podcast_material_uses_fallback_snippet(self):
        key, variant, snippet = resolve_material_prompt_snippet({}, {}, 'podcast-cover', 'hybrid')
        self.assertEqual(key, 'podcast_cover')
        self.assertEqual(variant, 'default')
        self.assertIn('Podcast cover', snippet)
        self.assertIn('thumbnail', snippet)

    def test_copy_anchor_and_image_safety_are_included_for_podcast_banner(self):
        identity = {
            'messaging': {
                'tagline': 'Governed skills for AI agents',
                'approved_copy_bank': {
                    'headlines': ['Intro to Sage'],
                    'subheadlines': ['A guided walkthrough of the protocol'],
                },
            }
        }
        payload = build_effective_prompt(
            {},
            identity,
            'Podcast episode banner for Intro to Sage',
            material_type='podcast-banner',
            workflow_mode='hybrid',
            disable_brand_guardrails=False,
        )
        self.assertIn('Intro to Sage', payload['copy_anchor_snippet'])
        self.assertIn('metadata', payload['image_safety_snippet'])
        self.assertIn('annotations', payload['resolved_prompt'])

    def test_copy_anchor_applies_to_concept_illustration(self):
        identity = {
            'messaging': {
                'tagline': 'Governed skills for AI agents',
                'approved_copy_bank': {
                    'headlines': ['Decentralized Governance'],
                },
            }
        }
        payload = build_effective_prompt(
            {},
            identity,
            'Abstract illustration of governance flow',
            material_type='concept-illustration',
            workflow_mode='hybrid',
            disable_brand_guardrails=False,
        )
        self.assertIn('Decentralized Governance', payload['copy_anchor_snippet'])
        self.assertIn('render no text', payload['copy_anchor_snippet'])

    def test_copy_anchor_applies_to_brand_scene(self):
        payload = build_effective_prompt(
            {},
            {},
            'Brand scene with abstract pillars',
            material_type='brand-scene',
            workflow_mode='hybrid',
            disable_brand_guardrails=False,
        )
        # With no messaging, gets the "no strings" variant
        self.assertIn('render no text', payload['copy_anchor_snippet'])

    def test_agent_regeneration_prompt_includes_new_screen_instruction(self):
        prompt = build_agent_regeneration_prompt(
            'v34',
            {
                'material_type': 'browser-illustration',
                'mode': 'hybrid',
                'aspect_ratio': '16:9',
                'model': 'nano-banana-2',
                'reference_images': ['references/v34-ref-01.png'],
                'raw_prompt': 'One calm browser illustration with a real product crop.',
                'critic_summary': {'issues': ['copy felt generic']},
            },
        )
        self.assertIn('version v34', prompt)
        self.assertIn('<NEW_SCREEN_PATH>', prompt)
        self.assertIn('browser-illustration', prompt)
        self.assertIn('compare it against v34', prompt)

    def test_social_copy_recommendation_does_not_leak_podcast_guidance(self):
        issues, recommendations = evaluate_prompt_review_rules(
            'social',
            'Product-led social launch card with one real product crop.',
            {'resolved_prompt': 'Product-led social launch card with one real product crop.', 'reference_role_pack': []},
        )

        self.assertEqual(issues, [])
        self.assertIn('Consider adding deterministic copy so the surface is not image-only.', recommendations)
        self.assertFalse(any('podcast' in item.lower() or 'show title' in item.lower() for item in recommendations))

    def test_exact_text_rule_recommends_deterministic_composition(self):
        issues, recommendations = evaluate_prompt_review_rules(
            'social',
            'Keep the exact title visible and render the exact tagline in the image.',
            {'resolved_prompt': 'Keep the exact title visible and render the exact tagline in the image.', 'reference_role_pack': []},
        )

        self.assertEqual(issues, [])
        self.assertTrue(any('prefer deterministic composition' in item.lower() for item in recommendations))

    def test_podcast_material_gets_podcast_specific_title_guidance(self):
        issues, recommendations = evaluate_prompt_review_rules(
            'podcast_banner',
            'Landscape banner with the Sage mark on a dark field.',
            {'resolved_prompt': 'Landscape banner with the Sage mark on a dark field.', 'reference_role_pack': []},
        )

        self.assertTrue(any('show title' in item.lower() or 'episode / host / guest' in item.lower() for item in recommendations))

    def test_prompt_review_rules_keep_podcast_language_scoped_to_podcast_materials(self):
        rules = load_prompt_review_rules().get('rules') or []
        podcast_terms = ('podcast', 'show title', 'episode', 'host', 'guest')

        for rule in rules:
            text = f"{rule.get('issue', '')} {rule.get('recommendation', '')}".lower()
            if not any(term in text for term in podcast_terms):
                continue
            materials = set(rule.get('materials') or [])
            self.assertTrue(materials, msg=f"Podcast-specific rule {rule.get('id')} must be explicitly material-scoped")
            self.assertTrue(materials.issubset({'podcast_cover', 'podcast_banner'}), msg=f"Podcast-specific rule {rule.get('id')} leaks outside podcast materials")

    def test_build_effective_prompt_preserves_token_block_fragments_for_debugging(self):
        with patch(
            'brand_gen.prompt_assembly.load_inspiration_prompt_context',
            return_value={
                'doctrine': '',
                'token_block': ':root {\n  --accent: #ff6600;\n}',
                'token_block_fragments': [{'source': '/tmp/src', 'css_vars': ['--accent: #ff6600;']}],
                'sources': ['src'],
                'skipped': [],
                'mode': 'full',
            },
        ):
            payload = build_effective_prompt({}, {}, 'Create a social card.', material_type='social')

        self.assertIn('--accent: #ff6600;', payload['token_block'])
        self.assertEqual(payload['token_block_fragments'][0]['source'], '/tmp/src')

    def test_social_fallback_snippet_caps_proof_inset_weight(self):
        key, variant, snippet = resolve_material_prompt_snippet({}, {}, 'social', 'hybrid')
        self.assertEqual(key, 'social')
        self.assertEqual(variant, 'default')
        self.assertIn('25% visual weight', snippet)

    def test_system_explainer_uses_explicit_new_snippet(self):
        key, variant, snippet = resolve_material_prompt_snippet({}, {}, 'system-explainer-illustration', 'hybrid')
        self.assertEqual(key, 'system_explainer_illustration')
        self.assertEqual(variant, 'default')
        self.assertIn('clearly legible flow', snippet)

    def test_proof_poster_uses_explicit_new_snippet(self):
        key, variant, snippet = resolve_material_prompt_snippet({}, {}, 'proof-poster', 'hybrid')
        self.assertEqual(key, 'proof_poster')
        self.assertEqual(variant, 'default')
        self.assertIn('proof payload', snippet)
        self.assertIn('subordinate mark', snippet)

    def test_build_effective_prompt_surfaces_pattern_discovery_packet(self):
        with patch(
            'brand_gen.prompt_assembly.discover_prompt_patterns',
            return_value={
                'retrieval_mode': 'material_exact',
                'hypotheses': [{'version': 'v001', 'model': 'gpt-image-2', 'borrow': ['single_thesis']}],
                'recommended_moves': ['single_thesis'],
                'avoid_moves': ['logo_dominance'],
                'packet': 'Pattern hypotheses:\n- v001 (gpt-image-2): bias toward single_thesis',
            },
        ):
            payload = build_effective_prompt(
                {},
                {},
                'Create a system explainer.',
                material_type='system-explainer-illustration',
                brand_dir=Path('/tmp/brand'),
            )

        self.assertIn('Pattern hypotheses', payload['pattern_discovery_packet'])
        self.assertEqual(payload['pattern_discovery']['retrieval_mode'], 'material_exact')

    def test_build_effective_prompt_surfaces_selected_inspiration_translation(self):
        with patch(
            'brand_gen.prompt_assembly.load_inspiration_prompt_context',
            return_value={
                'doctrine': 'Long merged doctrine that should remain available for inspection.',
                'token_block': '',
                'token_block_fragments': [],
                'sources': ['ramotion', 'gretel-work'],
                'source_records': [
                    {
                        'source_key': 'ramotion',
                        'source_name': 'Ramotion',
                        'design_memory_path': '/tmp/ramotion',
                    },
                    {
                        'source_key': 'gretel-work',
                        'source_name': 'Gretel',
                        'design_memory_path': '/tmp/gretel',
                    },
                ],
                'skipped': [],
                'mode': 'full',
            },
        ), patch(
            'brand_gen.prompt_assembly.build_selected_inspiration_translation',
            return_value={
                'translation': 'Selected inspiration translation:\n- Ramotion: lead with one dominant product window.',
                'mechanics': ['lead with one dominant product window'],
                'source_summaries': [],
            },
        ):
            payload = build_effective_prompt(
                {},
                {},
                'Create a browser illustration.',
                material_type='browser-illustration',
                role_pack_override={
                    'roles': [{'role': 'composition', 'source_key': 'ramotion', 'source_name': 'Ramotion'}],
                },
            )

        self.assertIn('Selected inspiration translation', payload['selected_inspiration_translation'])
        self.assertEqual(payload['selected_inspiration_ids'], ['ramotion'])
        self.assertEqual(payload['inspiration_selection_mode'], 'advisory_shortlist')

    def test_build_effective_prompt_exposes_reference_analysis_mode_confidence_and_warning(self):
        payload = build_effective_prompt(
            {},
            {},
            'Create a browser illustration.',
            material_type='browser-illustration',
            reference_analysis={
                'per_image': [{'vlm_available': False, 'confidence': 0.22}],
                'consistency_score': 0.22,
                'warnings': [],
            },
        )

        self.assertEqual(payload['reference_analysis_mode'], 'deterministic_only')
        self.assertEqual(payload['reference_analysis_confidence'], 'low')
        self.assertIn('deterministic-only', payload['reference_analysis_warning'])

    def test_build_effective_prompt_surfaces_inspiration_memory_seed_prompt(self):
        with patch(
            'brand_gen.prompt_assembly.load_inspiration_prompt_context',
            return_value={
                'doctrine': '',
                'token_block': '',
                'token_block_fragments': [],
                'sources': [],
                'source_records': [],
                'skipped': [],
                'mode': 'principles',
                'memory': {'summary': 'Shared memory summary.', 'seed_prompt': 'Favor calm negative space and one dominant crop.'},
                'memory_summary': 'Shared memory summary.',
                'memory_seed_prompt': 'Favor calm negative space and one dominant crop.',
            },
        ):
            payload = build_effective_prompt({}, {}, 'Create a social card.', material_type='social')

        self.assertEqual(payload['inspiration_memory_summary'], 'Shared memory summary.')
        self.assertIn('Favor calm negative space', payload['inspiration_memory_snippet'])
        self.assertIn('Favor calm negative space', payload['resolved_prompt'])

    def test_build_effective_prompt_exposes_policy_setup_risks(self):
        role_pack_override = {
            'snippet': '',
            'roles': [
                {
                    'role': 'composition',
                    'source_key': 'product-live',
                    'source_name': 'Library Live Viewport',
                    'path': '/tmp/product-screens-live/library-live-viewport.png',
                    'notes': 'real product screenshot',
                    'reference_quality': 'custom-proof',
                    'reference_quality_reasons': [],
                }
            ],
            'paths': [],
            'motion_paths': [],
            'missing_roles': [],
            'required_roles': [],
            'missing_required_roles': [],
            'priority': [],
            'prefer_unique_sources': True,
            'material_key': 'landing_hero',
        }

        payload = build_effective_prompt(
            {},
            {},
            'Create a landing hero.',
            material_type='landing-hero',
            role_pack_override=role_pack_override,
        )

        self.assertTrue(any('Policy/setup risk:' in item for item in payload['policy_setup_risks']))
        self.assertTrue(any('lacks a selected `product_truth` role' in item for item in payload['policy_setup_risks']))
        self.assertFalse(any('requires an approved logo/mark asset' in item for item in payload['policy_setup_risks']))

    def test_create_material_plan_records_selected_inspiration_metadata(self):
        with tempfile.TemporaryDirectory() as tmpdir, \
             patch('brand_gen.plan_builder.get_brand_gen_dir', return_value=Path('/tmp/brand-gen')), \
             patch('brand_gen.plan_builder.resolve_context_brand_key', return_value='sage'), \
             patch(
                 'brand_gen.plan_builder.load_inspiration_prompt_context',
                 return_value={
                     'source_records': [
                         {
                             'source_key': 'ramotion',
                             'source_name': 'Ramotion',
                             'design_memory_path': '/tmp/ramotion',
                         },
                         {
                             'source_key': 'gretel-work',
                             'source_name': 'Gretel',
                             'design_memory_path': '/tmp/gretel',
                         },
                     ],
                 },
             ), \
             patch(
                 'brand_gen.plan_builder.build_selected_inspiration_translation',
                 return_value={
                     'translation': 'Selected inspiration translation:\n- Ramotion: one dominant product window.',
                     'mechanics': ['one dominant product window'],
                     'source_summaries': [],
                 },
             ):
            plan, _ = create_material_plan(
                brand_dir=Path(tmpdir),
                identity_path=Path(tmpdir) / 'brand-identity.json',
                identity={},
                material_type='browser-illustration',
                mode='hybrid',
                mechanic='one dominant product window',
                preserve=[],
                push=[],
                ban=[],
                picks={},
                accept_inspiration_recommendations=True,
            )

        self.assertEqual(plan['selected_inspiration_source_keys'], ['ramotion'])
        self.assertEqual(plan['inspiration_selection_mode'], 'agent_confirmed_recommendations')
        self.assertIn('accepted the recommended inspiration shortlist', plan['inspiration_selection_reason'])
        self.assertEqual(plan['selected_mechanic_labels'], ['one dominant product window'])
        self.assertTrue(plan['selected_mechanic_ids'])
        self.assertIn('Selected inspiration translation', plan['selected_inspiration_translation'])

    def test_create_material_plan_without_accept_recommendations_gets_empty_inspiration(self):
        """Regression: calling create_material_plan without accept_inspiration_recommendations
        should produce an 'unselected' mode with empty records, not silently break the pipeline."""
        with tempfile.TemporaryDirectory() as tmpdir, \
             patch('brand_gen.plan_builder.get_brand_gen_dir', return_value=Path('/tmp/brand-gen')), \
             patch('brand_gen.plan_builder.resolve_context_brand_key', return_value='sage'), \
             patch(
                 'brand_gen.plan_builder.load_inspiration_prompt_context',
                 return_value={
                     'source_records': [
                         {'source_key': 'ramotion', 'source_name': 'Ramotion', 'design_memory_path': '/tmp/ramotion'},
                     ],
                 },
             ), \
             patch(
                 'brand_gen.plan_builder.build_selected_inspiration_translation',
                 return_value={'translation': '', 'mechanics': [], 'source_summaries': []},
             ):
            plan, _ = create_material_plan(
                brand_dir=Path(tmpdir),
                identity_path=Path(tmpdir) / 'brand-identity.json',
                identity={},
                material_type='social',
                mode='hybrid',
                mechanic='',
                preserve=[], push=[], ban=[], picks={},
            )

        self.assertEqual(plan['selected_inspiration_source_keys'], [])
        self.assertEqual(plan['inspiration_selection_mode'], 'unselected')

    def test_create_material_plan_auto_synthesizes_system_mechanic_when_blank(self):
        with tempfile.TemporaryDirectory() as tmpdir, \
             patch('brand_gen.plan_builder.get_brand_gen_dir', return_value=Path('/tmp/brand-gen')), \
             patch('brand_gen.plan_builder.resolve_context_brand_key', return_value='sage'), \
             patch(
                 'brand_gen.plan_builder.load_inspiration_prompt_context',
                 return_value={
                     'source_records': [
                         {'source_key': 'ramotion', 'source_name': 'Ramotion', 'design_memory_path': '/tmp/ramotion'},
                     ],
                 },
             ), \
             patch(
                 'brand_gen.plan_builder.build_selected_inspiration_translation',
                 return_value={
                     'translation': 'Selected inspiration translation.',
                     'mechanics': ['one dominant product window'],
                     'source_summaries': [],
                 },
             ):
            plan, _ = create_material_plan(
                brand_dir=Path(tmpdir),
                identity_path=Path(tmpdir) / 'brand-identity.json',
                identity={},
                material_type='browser-illustration',
                mode='hybrid',
                mechanic='',
                preserve=[],
                push=[],
                ban=[],
                picks={},
                purpose='Show Sage as a credible governed-library product surface',
                target_surface='browser illustration for docs',
                product_truth_expression='one real Sage activity view kept readable',
                accept_inspiration_recommendations=True,
            )

        self.assertTrue(plan['system_mechanic'])
        self.assertEqual(plan['system_mechanic_source'], 'auto_synthesized')
        self.assertIn('one real Sage activity view kept readable', plan['system_mechanic'])

    def test_create_material_plan_relaxes_role_pack_gate_when_no_candidates_and_inspiration_exists(self):
        with tempfile.TemporaryDirectory() as tmpdir, \
             patch('brand_gen.plan_builder.get_brand_gen_dir', return_value=Path('/tmp/brand-gen')), \
             patch('brand_gen.plan_builder.resolve_context_brand_key', return_value='sage'), \
             patch(
                 'brand_gen.plan_builder.suggest_reference_role_pack',
                 return_value={
                     'material_key': 'social',
                     'priority': ['composition', 'application'],
                     'required_roles': ['composition', 'application'],
                     'prefer_unique_sources': True,
                     'selection_note': 'Use one composition ref and one application ref.',
                     'candidates': {'composition': [], 'application': []},
                 },
             ), \
             patch(
                 'brand_gen.plan_builder.load_inspiration_prompt_context',
                 return_value={
                     'source_records': [
                         {'source_key': 'ramotion', 'source_name': 'Ramotion', 'design_memory_path': '/tmp/ramotion'},
                     ],
                 },
             ), \
             patch(
                 'brand_gen.plan_builder.build_selected_inspiration_translation',
                 return_value={
                     'translation': 'Selected inspiration translation.',
                     'mechanics': ['editorial pacing'],
                     'source_summaries': [],
                 },
             ):
            plan, missing_required = create_material_plan(
                brand_dir=Path(tmpdir),
                identity_path=Path(tmpdir) / 'brand-identity.json',
                identity={},
                material_type='social',
                mode='hybrid',
                mechanic='',
                preserve=[],
                push=[],
                ban=[],
                picks={},
                accept_inspiration_recommendations=True,
            )

        self.assertEqual(missing_required, [])
        self.assertEqual(plan['role_pack']['requirement_mode'], 'advisory_inspiration_fallback')
        self.assertEqual(plan['role_pack']['required_roles'], [])
        self.assertEqual(plan['role_pack']['configured_required_roles'], ['composition', 'application'])
        self.assertEqual(plan['role_pack']['unavailable_required_roles'], ['composition', 'application'])
        validation = validate_material_plan_dict(plan)
        self.assertNotIn('Material plan needs translated role-pack refs.', validation['warnings'])
        self.assertTrue(any('fallback guide' in item for item in validation['warnings']))

    def test_build_material_plan_from_args_accepts_inspiration_recommendations(self):
        """Regression: build_material_plan_from_args (the pipeline path) must pass
        accept_inspiration_recommendations=True so auto-selected inspiration sources
        are used by default. Without this, the pipeline gets empty inspiration sources
        and critique blocks generation."""
        import argparse
        with tempfile.TemporaryDirectory() as tmpdir, \
             patch('brand_gen.plan_builder.load_brand_memory', return_value=(None, Path(tmpdir) / 'identity.json', {}, {})), \
             patch('brand_gen.plan_builder.get_brand_gen_dir', return_value=Path('/tmp/brand-gen')), \
             patch('brand_gen.plan_builder.resolve_context_brand_key', return_value='sage'), \
             patch(
                 'brand_gen.plan_builder.load_inspiration_prompt_context',
                 return_value={
                     'source_records': [
                         {'source_key': 'ramotion', 'source_name': 'Ramotion', 'design_memory_path': '/tmp/ramotion'},
                     ],
                 },
             ), \
             patch(
                 'brand_gen.plan_builder.build_selected_inspiration_translation',
                 return_value={
                     'translation': 'Selected inspiration translation.',
                     'mechanics': ['dominant window'],
                     'source_summaries': [],
                 },
             ), \
             patch('brand_gen.plan_builder.save_plan_draft', return_value=Path(tmpdir) / 'draft.json'), \
             patch('brand_gen.plan_builder.persist_plan_inspiration_board', return_value={}), \
             patch('brand_gen.plan_builder.persist_inspiration_source_selection', return_value=([], '')):
            args = argparse.Namespace(
                material_type='social', mode='hybrid', mechanic='', pick=[],
                preserve=[], push=[], ban=[], prompt_seed=None,
                purpose=None, target_surface=None, product_truth_expression=None,
                abstraction_level=None, briefing=None, profile=None, identity=None,
            )
            _, plan, _ = build_material_plan_from_args(args, Path(tmpdir))

        self.assertEqual(plan['inspiration_selection_mode'], 'agent_confirmed_recommendations')
        self.assertEqual(plan['selected_inspiration_source_keys'], ['ramotion'])

    def test_validate_material_plan_uses_role_pack_wording_for_missing_translations(self):
        plan = {
            'material_type': 'social',
            'purpose': 'Launch Sage',
            'target_surface': 'social card',
            'product_truth_expression': 'one real library detail',
            'abstraction_level': 'low',
            'brand_anchor_policy': {'rule': 'Show the stored logo or wordmark clearly.'},
            'system_mechanic': 'one product proof crop inside a launch card',
            'preserve': ['real mark recognition'],
            'push': ['cleaner hierarchy'],
            'ban': ['invented chrome'],
            'prompt_seed': 'Create a social card.',
            'inspiration_translation': {'references': []},
            'role_pack': {
                'material_key': 'social',
                'selected_roles': [],
                'required_roles': ['composition', 'application'],
            },
        }

        validation = validate_material_plan_dict(plan)

        self.assertIn('Material plan needs translated role-pack refs.', validation['warnings'])

    def test_role_assignment_warnings_are_visible_without_rewriting_explicit_role_pick(self):
        plan = {
            'material_type': 'social',
            'purpose': 'Launch social card',
            'target_surface': 'social feed',
            'product_truth_expression': 'one real product proof surface',
            'abstraction_level': 'low',
            'brand_anchor_policy': {'rule': 'Keep the output clearly branded.'},
            'system_mechanic': 'calm framed proof',
            'preserve': ['real product truth'],
            'push': ['one composition move'],
            'ban': ['invented product chrome'],
            'prompt_seed': 'Create a social card with one real product crop.',
            'inspiration_translation': {'references': []},
            'role_pack': {
                'material_key': 'social',
                'selected_roles': [
                    {
                        'role': 'composition',
                        'source_key': 'product-live',
                        'source_name': 'Library Live Viewport',
                        'path': '/tmp/product-screens-live/library-live-viewport.png',
                        'notes': 'real product screenshot',
                    }
                ],
                'required_roles': [],
                'role_assignment_warnings': [
                    "Ref 'Library Live Viewport' looks like product proof but is assigned to `composition`; keep the explicit pick if intentional, but consider assigning a `product_truth` role so real UI/workflow truth stays authoritative."
                ],
            },
        }

        override = build_role_pack_override_from_plan(plan)
        payload = build_effective_prompt({}, {}, 'Create a social card.', material_type='social', role_pack_override=override)
        validation = validate_material_plan_dict(plan)

        self.assertEqual(override['roles'][0]['role'], 'composition')
        self.assertTrue(any('looks like product proof' in item for item in override['role_assignment_warnings']))
        self.assertTrue(any('looks like product proof' in item for item in payload['reference_role_assignment_warnings']))
        self.assertTrue(any('looks like product proof' in item for item in validation['warnings']))

    def test_review_prompt_architecture_surfaces_reference_analysis_warning(self):
        context = {
            'resolved_prompt': 'Create a browser illustration.',
            'material_prompt_key': 'browser_illustration',
            'material_prompt_snippet': '',
            'reference_role_pack': [],
            'reference_analysis': {
                'per_image': [{'vlm_available': False, 'confidence': 0.22}],
                'consistency_score': 0.22,
                'warnings': [],
            },
            'reference_analysis_mode': 'deterministic_only',
            'reference_analysis_confidence': 'low',
            'reference_analysis_warning': 'Reference analysis is deterministic-only (confidence: low); treat role matching and transferable mechanics as approximate.',
            'reference_analysis_snippet': '',
            'inspiration_doctrine': '',
            'iteration_memory_snippet': '',
            'token_block': '',
        }

        review = review_prompt_architecture({}, {}, 'Create a browser illustration.', context, material_type='browser-illustration')

        self.assertEqual(review['reference_analysis_mode'], 'deterministic_only')
        self.assertEqual(review['reference_analysis_confidence'], 'low')
        self.assertIn('deterministic-only', review['reference_analysis_warning'])
        self.assertTrue(any('deterministic-only' in item for item in review['recommendations']))

    def test_review_prompt_architecture_surfaces_reference_role_assignment_warning(self):
        context = {
            'resolved_prompt': 'Create a social card.',
            'brand_prelude': 'Keep the output clearly branded.',
            'material_prompt_key': 'social',
            'material_prompt_snippet': 'Design a social card around one real product crop.',
            'reference_role_pack': [{'role': 'composition', 'source_name': 'Library Live Viewport'}],
            'reference_role_assignment_warnings': [
                "Ref 'Library Live Viewport' looks like product proof but is assigned to `composition`; keep the explicit pick if intentional, but consider assigning a `product_truth` role so real UI/workflow truth stays authoritative."
            ],
            'reference_analysis': {},
            'reference_analysis_snippet': '',
            'inspiration_doctrine': '',
            'iteration_memory_snippet': '',
            'token_block': '',
        }

        review = review_prompt_architecture({}, {}, 'Create a social card.', context, material_type='social')

        self.assertTrue(any('looks like product proof' in item for item in review['reference_role_assignment_warnings']))
        self.assertTrue(any('looks like product proof' in item for item in review['recommendations']))

    def test_review_prompt_architecture_surfaces_policy_setup_risks(self):
        context = {
            'resolved_prompt': 'Create a landing hero.',
            'brand_prelude': 'Show the stored logo or wordmark clearly.',
            'material_prompt_key': 'landing_hero',
            'material_prompt_snippet': 'Use one real product moment in the hero.',
            'reference_role_pack': [{'role': 'composition', 'source_name': 'Library Live Viewport'}],
            'policy_setup_risks': [
                'Policy/setup risk: proof-sensitive material lacks a selected `product_truth` role; the setup may drift toward decorative framing.',
                'Policy/setup risk: prompt/reference setup is decorative-only for this proof-sensitive material; selected roles are framing-oriented rather than product-truth-oriented.',
            ],
            'reference_analysis': {},
            'reference_analysis_snippet': '',
            'inspiration_doctrine': '',
            'iteration_memory_snippet': '',
            'token_block': '',
        }

        review = review_prompt_architecture({}, {}, 'Create a landing hero.', context, material_type='landing-hero')

        self.assertTrue(any('Policy/setup risk:' in item for item in review['policy_setup_risks']))
        self.assertTrue(any('decorative-only' in item for item in review['recommendations']))

    def test_review_prompt_architecture_warns_when_announcement_card_is_screenshot_led(self):
        context = {
            'resolved_prompt': 'Create an announcement card with a screenshot proof inset.',
            'brand_prelude': 'Keep the output clearly branded.',
            'material_prompt_key': 'announcement_card',
            'material_prompt_snippet': 'For announcement cards, lead with a bold headline and avoid a full screenshot hero.',
            'reference_role_pack': [{'role': 'product_truth', 'source_name': 'Prompt Screenshot'}],
            'reference_analysis': {},
            'reference_analysis_snippet': '',
            'inspiration_doctrine': '',
            'iteration_memory_snippet': '',
            'token_block': '',
        }

        review = review_prompt_architecture(
            {},
            {},
            'Create an announcement card with a screenshot proof inset and exact headline text.',
            context,
            material_type='announcement-card',
        )

        self.assertTrue(any('Announcement-card policy conflicts' in item for item in review['recommendations']))
        self.assertTrue(any('Exact text request detected' in item for item in review['recommendations']))

    def test_review_prompt_architecture_builds_compact_image_execution_prompt(self):
        context = {
            'resolved_prompt': 'Resolved debug prompt with long doctrine and tokens.',
            'brand_prelude': 'Show the stored logo or wordmark clearly. Do not invent extra product chrome.',
            'material_prompt_key': 'social',
            'material_prompt_snippet': 'Design a social card that packages one real product crop inside a calm branded frame. Keep the composition legible at feed speed.',
            'reference_role_pack': [
                {
                    'role': 'composition',
                    'source_name': 'Clay',
                    'translation': {
                        'borrow_mechanics': ['frame depth', 'soft inset'],
                        'avoid_literal': ['literal UI cloning'],
                    },
                }
            ],
            'reference_analysis_mode': 'deterministic_only',
            'reference_analysis_confidence': 'low',
            'reference_analysis_warning': 'Reference analysis is deterministic-only (confidence: low); treat role matching and transferable mechanics as approximate.',
            'copy_anchor_snippet': 'If visible copy appears in the image, use only explicit user-provided copy. Otherwise render no text rather than inventing slogans or captions.',
            'image_safety_snippet': 'Output only the designed artwork. Never render prompt metadata or file paths as visible content.',
            'reference_analysis_snippet': 'Longer analysis block that should not be copied verbatim into the compact execution prompt.',
            'selected_inspiration_translation': 'Selected inspiration translation:\n- Ramotion: lead with one dominant product window and generous negative space.',
            'selected_inspiration_ids': ['ramotion'],
            'selected_mechanic_ids': ['mechanic_123'],
            'inspiration_selection_reason': 'matched configured inspiration to the selected composition ref',
            'inspiration_selection_mode': 'auto',
            'inspiration_doctrine': 'Long doctrine block that belongs in the debug prompt, not the compact image execution prompt.',
            'iteration_memory_snippet': 'Recent iteration note that should stay out of the compact execution prompt.',
            'token_block': ':root { --accent: #ff6600; }',
        }

        review = review_prompt_architecture(
            {},
            {},
            'Create a product-led social card with one real crop and the tagline "Governed skills for AI agents".',
            context,
            material_type='social',
            generation_mode='image',
        )

        execution_prompt = review['execution_prompt']
        self.assertTrue(review['execution_prompt_compressed'])
        self.assertEqual(review['execution_prompt_kind'], 'image_compact')
        self.assertIn('Material policy:', execution_prompt)
        self.assertIn('Brand anchor:', execution_prompt)
        self.assertIn('Translate references into mechanics only:', execution_prompt)
        self.assertIn('Selected inspiration translation:', execution_prompt)
        self.assertIn('Critical bans:', execution_prompt)
        self.assertIn('Copy rule:', execution_prompt)
        self.assertIn('Reference caveat:', execution_prompt)
        self.assertNotIn('Long doctrine block', execution_prompt)
        self.assertNotIn('--accent', execution_prompt)
        self.assertNotIn('Recent iteration note', execution_prompt)
        self.assertEqual(review['selected_inspiration_ids'], ['ramotion'])
        self.assertEqual(review['selected_mechanic_ids'], ['mechanic_123'])

    def test_execute_generation_scratchpad_preserves_debug_and_execution_prompts_in_sidecar(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            brand_dir = Path(tmpdir).resolve()
            payload = {
                'schema_type': 'generation_scratchpad',
                'brand_dir': str(brand_dir),
                'workflow_id': 'wf-123',
                'material_type': 'social',
                'tag': 'social',
                'workflow_mode': 'hybrid',
                'generation_mode': 'image',
                'effective_prompt': 'Long reviewed prompt for debugging and inspection.',
                'execution_prompt': 'Short model prompt.',
                'execution': {'model': 'mock-image-model', 'aspect_ratio': '1:1'},
                'checks': {'blocking': [], 'warnings': []},
                'prompt_context': {
                    'brand_prelude': 'Show the stored logo or wordmark clearly.',
                    'material_prompt_snippet': 'Design a calm social card.',
                    'reference_role_pack_snippet': 'Translate references into mechanics only.',
                    'inspiration_doctrine': 'Debug doctrine.',
                    'reference_role_pack': [],
                    'token_block': '',
                    'token_block_fragments': [],
                },
                'prompt_review': {
                    'resolved_prompt': 'Full debug prompt artifact.',
                    'execution_prompt_kind': 'image_compact',
                    'execution_prompt_compressed': True,
                    'execution_prompt_sections': {'material_policy': 'Material policy: Design a calm social card.'},
                },
                'reference_context': {'passed_reference_paths': [], 'all_context_refs': []},
                'selected_inspiration_ids': [],
                'profile_path': '',
                'identity_path': '',
            }

            with patch('brand_gen.runtime_brand.get_brand_dir', return_value=brand_dir), \
                 patch('brand_gen.generation_flow.MODELS', {'image': {'mock-image-model': {'output_format': 'png'}}}), \
                 patch('brand_gen.generation_flow.load_manifest', return_value={'versions': {}}), \
                 patch('brand_gen.generation_flow.save_manifest'), \
                 patch('brand_gen.generation_flow.next_version_num', return_value=1), \
                 patch('brand_gen.generation_flow.subprocess.run', side_effect=lambda cmd, **kwargs: (Path(cmd[cmd.index("-o") + 1]).write_bytes(b"\x89PNG\r\n") and type('Result', (), {'returncode': 0, 'stdout': '', 'stderr': ''})())), \
                 patch('brand_gen.generation_flow.stage_reference_assets', return_value=[]), \
                 patch('brand_gen.generation_flow.write_agent_visual_review_packet', return_value=({}, brand_dir / 'reviews' / 'v001-agent-review.json')), \
                 patch('brand_gen.generation_flow.run_auto_brand_review', return_value=('', False)), \
                 patch('brand_gen.generation_flow.load_brand_memory', return_value=(None, None, {}, {})), \
                 patch('brand_gen.generation_flow.persist_generated_asset_to_blackboard'), \
                 patch('brand_gen.generation_flow.append_run_event'), \
                 patch('brand_gen.generation_flow.build_env', return_value={}):
                version_id = execute_generation_scratchpad(payload, workflow_id='wf-123')

            sidecar = json.loads((brand_dir / f'{version_id}.prompts.json').read_text())
            self.assertEqual(sidecar['effective_prompt'], 'Long reviewed prompt for debugging and inspection.')
            self.assertEqual(sidecar['execution_prompt'], 'Short model prompt.')
            self.assertEqual(sidecar['execution_prompt_kind'], 'image_compact')
            self.assertTrue(sidecar['execution_prompt_compressed'])
            self.assertEqual(sidecar['resolved_prompt'], 'Full debug prompt artifact.')

    def test_execute_generation_scratchpad_uses_explicit_brand_dir_for_manifest_io(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            brand_dir = Path(tmpdir).resolve()
            payload = {
                'schema_type': 'generation_scratchpad',
                'brand_dir': str(brand_dir),
                'workflow_id': 'wf-123',
                'material_type': 'social',
                'tag': 'social',
                'workflow_mode': 'hybrid',
                'generation_mode': 'image',
                'effective_prompt': 'Debug prompt.',
                'execution_prompt': 'Short model prompt.',
                'execution': {'model': 'mock-image-model', 'aspect_ratio': '1:1'},
                'checks': {'blocking': [], 'warnings': []},
                'prompt_context': {},
                'prompt_review': {},
                'reference_context': {'passed_reference_paths': [], 'all_context_refs': []},
                'selected_inspiration_ids': [],
                'profile_path': '',
                'identity_path': '',
            }

            with patch('brand_gen.runtime_brand.get_brand_dir', return_value=brand_dir), \
                 patch('brand_gen.generation_flow.MODELS', {'image': {'mock-image-model': {'output_format': 'png'}}}), \
                 patch('brand_gen.generation_flow.load_manifest', return_value={'versions': {}}) as load_manifest_mock, \
                 patch('brand_gen.generation_flow.save_manifest') as save_manifest_mock, \
                 patch('brand_gen.generation_flow.next_version_num', return_value=1) as next_version_num_mock, \
                 patch('brand_gen.generation_flow.subprocess.run', side_effect=lambda cmd, **kwargs: (Path(cmd[cmd.index("-o") + 1]).write_bytes(b"\x89PNG\r\n") and type('Result', (), {'returncode': 0, 'stdout': '', 'stderr': ''})())), \
                 patch('brand_gen.generation_flow.stage_reference_assets', return_value=[]), \
                 patch('brand_gen.generation_flow.write_agent_visual_review_packet', return_value=({}, brand_dir / 'reviews' / 'v001-agent-review.json')), \
                 patch('brand_gen.generation_flow.run_auto_brand_review', return_value=('', False)), \
                 patch('brand_gen.generation_flow.load_brand_memory', return_value=(None, None, {}, {})), \
                 patch('brand_gen.generation_flow.persist_generated_asset_to_blackboard'), \
                 patch('brand_gen.generation_flow.append_run_event'), \
                 patch('brand_gen.generation_flow.build_env', return_value={}):
                execute_generation_scratchpad(payload, workflow_id='wf-123')

            self.assertEqual(load_manifest_mock.call_count, 4)
            for call in load_manifest_mock.call_args_list:
                self.assertEqual(call.args[0], brand_dir)
            next_version_num_mock.assert_called_once()
            self.assertEqual(next_version_num_mock.call_args.args[1], brand_dir)
            self.assertEqual(save_manifest_mock.call_count, 4)
            for call in save_manifest_mock.call_args_list:
                self.assertEqual(call.args[1], brand_dir)


    def test_compare_marks_latest_overall_when_showing_all_versions(self):
        import argparse
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            brand_dir = Path(tmpdir).resolve()
            (brand_dir / 'v1-social.png').write_bytes(b'fake')
            (brand_dir / 'v2-social.png').write_bytes(b'fake')
            output = brand_dir / 'compare.html'
            manifest = {
                'versions': {
                    'v1': {
                        'material_type': 'social',
                        'generation_mode': 'hybrid',
                        'model': 'nano-banana-2',
                        'files': ['v1-social.png'],
                    },
                    'v2': {
                        'material_type': 'social',
                        'generation_mode': 'hybrid',
                        'model': 'nano-banana-2',
                        'files': ['v2-social.png'],
                    },
                }
            }
            with patch('brand_gen.commands.inspection.load_manifest', return_value=manifest), \
                 patch('brand_gen.commands.inspection.get_brand_dir', return_value=brand_dir), \
                 patch('brand_gen.commands.inspection.sys.platform', 'linux'):
                cmd_compare(argparse.Namespace(
                    versions=[],
                    favorites=False,
                    top=None,
                    latest=None,
                    all_versions=True,
                    output=str(output),
                ))

            html = output.read_text()
            self.assertIn('latest overall: v2', html)
            self.assertIn('Most recent overall', html)

    def test_compare_loads_manifest_from_active_brand_dir(self):
        import argparse
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            brand_dir = Path(tmpdir)
            (brand_dir / 'v2-social.png').write_bytes(b'fake')
            output = brand_dir / 'compare.html'
            manifest = {
                'versions': {
                    'v2': {
                        'material_type': 'social',
                        'generation_mode': 'hybrid',
                        'model': 'nano-banana-2',
                        'files': ['v2-social.png'],
                    },
                }
            }
            with patch('brand_gen.commands.inspection.load_manifest', return_value=manifest) as load_manifest_mock, \
                 patch('brand_gen.commands.inspection.get_brand_dir', return_value=brand_dir), \
                 patch('brand_gen.commands.inspection.sys.platform', 'linux'):
                cmd_compare(argparse.Namespace(
                    versions=[],
                    favorites=False,
                    top=None,
                    latest=1,
                    all_versions=False,
                    output=str(output),
                    embed=False,
                ))

            load_manifest_mock.assert_called_once_with(brand_dir)
            self.assertIn('v2', output.read_text())

    def test_session_summary_uses_requested_brand_dir_manifest(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            brand_dir = Path(tmpdir)
            manifest = {
                'versions': {
                    'v2': {'timestamp': '2026-03-17T22:47:13', 'material_type': 'browser-illustration', 'files': ['v2.png']},
                    'v1': {'timestamp': '2026-03-17T22:45:46', 'material_type': 'social', 'files': ['v1.png']},
                }
            }
            with patch('brand_gen.session_summary.load_manifest', return_value=manifest) as load_manifest_mock, \
                 patch('brand_gen.session_summary.load_blackboard', return_value={'generated_assets': [], 'artifacts': {}, 'decisions': [], 'reference_analysis': {}}), \
                 patch('brand_gen.session_summary.load_iteration_memory', return_value={}), \
                 patch('brand_gen.session_summary.load_all_run_events', return_value=[]), \
                 patch('brand_gen.session_summary.load_inspiration_board', return_value={}), \
                 patch('brand_gen.session_summary.build_inspiration_board_summary', return_value={}), \
                 patch('brand_gen.session_summary.get_brand_gen_dir', return_value=None), \
                 patch('brand_gen.session_summary.infer_brand_key_from_path', return_value='sage'), \
                 patch('brand_gen.session_summary.resolve_active_brand_key', return_value='sage'):
                payload = build_session_summary_payload(brand_dir, {'brand_name': 'Sage'}, {'brand': {'name': 'Sage'}}, limit=2)

            load_manifest_mock.assert_called_once_with(brand_dir)
            self.assertEqual([item['version'] for item in payload['generated']['recent_versions']], ['v2', 'v1'])


class ImprovementQuestionsTests(unittest.TestCase):
    """Tests for build_improvement_questions auto-resolution behavior."""

    def _make_manifest(self, versions: dict) -> dict:
        return {"versions": versions}

    def _make_memory(self, negative_examples=None):
        return {
            "version": 1,
            "brand_notes": [],
            "positive_examples": [],
            "negative_examples": negative_examples or [],
            "messaging_notes": [],
            "material_notes": {},
            "copy_notes": [],
        }

    @patch('brand_gen.plan_builder.load_iteration_memory')
    def test_quality_question_is_actionable_when_feedback_not_captured(self, mock_mem):
        from brand_gen.plan_builder import build_improvement_questions
        # 2 low-scored versions, but iteration memory has no negative examples for them
        mock_mem.return_value = self._make_memory()
        manifest = self._make_manifest({
            "v01": {"material_type": "social", "score": 1, "notes": "bad"},
            "v02": {"material_type": "social", "score": 2, "notes": "weak"},
        })
        questions = build_improvement_questions(Path("/tmp"), {}, {}, manifest)
        quality_qs = [q for q in questions if q["category"] == "quality_feedback"]
        self.assertEqual(len(quality_qs), 1)
        self.assertFalse(quality_qs[0].get("auto_resolved", False))
        self.assertIn("scored poorly", quality_qs[0]["question"])

    @patch('brand_gen.plan_builder.load_iteration_memory')
    def test_quality_question_auto_resolved_when_feedback_already_captured(self, mock_mem):
        from brand_gen.plan_builder import build_improvement_questions
        # 2 low-scored versions, and iteration memory already has negative examples for both
        mock_mem.return_value = self._make_memory(negative_examples=[
            {"version": "v01", "material_type": "social", "summary": "Auto-critic: too generic", "score": 1},
            {"version": "v02", "material_type": "social", "summary": "Auto-critic: weak", "score": 2},
        ])
        manifest = self._make_manifest({
            "v01": {"material_type": "social", "score": 1, "notes": "bad"},
            "v02": {"material_type": "social", "score": 2, "notes": "weak"},
        })
        questions = build_improvement_questions(Path("/tmp"), {}, {}, manifest)
        quality_qs = [q for q in questions if q["category"] == "quality_feedback"]
        self.assertEqual(len(quality_qs), 1)
        self.assertTrue(quality_qs[0].get("auto_resolved", False))
        self.assertIn("auto-captured", quality_qs[0]["question"].lower())
        self.assertEqual(quality_qs[0]["priority"], 2)

    @patch('brand_gen.plan_builder.load_iteration_memory')
    def test_quality_question_actionable_when_partially_captured(self, mock_mem):
        from brand_gen.plan_builder import build_improvement_questions
        # 2 low-scored but only 1 captured in memory
        mock_mem.return_value = self._make_memory(negative_examples=[
            {"version": "v01", "material_type": "social", "summary": "Auto-critic: too generic", "score": 1},
        ])
        manifest = self._make_manifest({
            "v01": {"material_type": "social", "score": 1, "notes": "bad"},
            "v02": {"material_type": "social", "score": 2, "notes": "weak"},
        })
        questions = build_improvement_questions(Path("/tmp"), {}, {}, manifest)
        quality_qs = [q for q in questions if q["category"] == "quality_feedback"]
        self.assertEqual(len(quality_qs), 1)
        self.assertFalse(quality_qs[0].get("auto_resolved", False))


if __name__ == '__main__':
    unittest.main()
