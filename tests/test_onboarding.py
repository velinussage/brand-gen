import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
from mcp import brand_iterate_mcp

BRAND_ITERATE = REPO_ROOT / 'mcp' / 'brand_iterate.py'


class OnboardingTests(unittest.TestCase):
    def test_init_scaffolds_profile_and_identity(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            brand_gen_dir = Path(tmpdir) / '.brand-gen'
            subprocess.run(
                [
                    sys.executable,
                    str(BRAND_ITERATE),
                    'init',
                    '--brand-name',
                    'Acme Cloud',
                    '--brand-gen-dir',
                    str(brand_gen_dir),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            brand_dir = brand_gen_dir / 'brands' / 'acme-cloud'
            self.assertTrue((brand_dir / 'brand-profile.json').exists())
            self.assertTrue((brand_dir / 'brand-identity.json').exists())
            self.assertTrue((brand_gen_dir / 'brands' / 'index.json').exists())
            profile = json.loads((brand_dir / 'brand-profile.json').read_text())
            config = json.loads((brand_gen_dir / 'config.json').read_text())
            self.assertEqual(profile['brand_name'], 'Acme Cloud')
            self.assertEqual(config['active'], 'acme-cloud')


    def test_init_is_idempotent_for_existing_brand(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            brand_gen_dir = Path(tmpdir) / '.brand-gen'
            cmd = [
                sys.executable,
                str(BRAND_ITERATE),
                'init',
                '--brand-name',
                'Acme Cloud',
                '--brand-gen-dir',
                str(brand_gen_dir),
            ]
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            brand_dir = brand_gen_dir / 'brands' / 'acme-cloud'
            self.assertTrue((brand_dir / 'brand-profile.json').exists())
            self.assertTrue((brand_dir / 'brand-identity.json').exists())

    def test_create_brand_bootstraps_from_conversational_inputs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            brand_gen_dir = Path(tmpdir) / '.brand-gen'
            subprocess.run(
                [
                    sys.executable,
                    str(BRAND_ITERATE),
                    'create-brand',
                    '--name',
                    'Orbit Ops',
                    '--description',
                    'Operational intelligence software for distributed teams.',
                    '--tone',
                    'calm,technical',
                    '--palette',
                    '#1A6B6B,#C85A2A',
                    '--keywords',
                    'operations,distributed systems',
                    '--value-prop',
                    'Clearer operational visibility',
                    '--brand-gen-dir',
                    str(brand_gen_dir),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            brand_dir = brand_gen_dir / 'brands' / 'orbit-ops'
            profile = json.loads((brand_dir / 'brand-profile.json').read_text())
            identity = json.loads((brand_dir / 'brand-identity.json').read_text())
            self.assertEqual(profile['brand_name'], 'Orbit Ops')
            self.assertIn('#1A6B6B', profile['color_candidates'])
            self.assertIn('calm', profile['identity']['tone_words'])
            self.assertIn('Clearer operational visibility', profile['messaging']['value_propositions'])
            self.assertEqual(identity.get('brand', {}).get('name'), 'Orbit Ops')

    def test_start_testing_uses_canonical_profile_template_for_new_sessions(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            brand_gen_dir = Path(tmpdir) / '.brand-gen'
            subprocess.run(
                [
                    sys.executable,
                    str(BRAND_ITERATE),
                    'start-testing',
                    '--working-name',
                    'Scratch Test',
                    '--goal',
                    'Explore a first direction',
                    '--brand-gen-dir',
                    str(brand_gen_dir),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            session_dir = brand_gen_dir / 'sessions' / 'scratch-test' / 'brand-materials'
            profile = json.loads((session_dir / 'brand-profile.json').read_text())
            config = json.loads((brand_gen_dir / 'config.json').read_text())

            self.assertEqual(profile['brand_name'], 'Scratch Test')
            self.assertIn('creative_context', profile)
            self.assertIn('messaging', profile)
            self.assertIn('identity', profile)
            self.assertEqual(profile['session_context']['type'], 'testing-session')
            self.assertEqual(config['activeSession'], 'scratch-test')

    def test_start_testing_only_patches_missing_schema_in_session_copy(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            brand_gen_dir = Path(tmpdir) / '.brand-gen'
            subprocess.run(
                [
                    sys.executable,
                    str(BRAND_ITERATE),
                    'create-brand',
                    '--name',
                    'Acme Cloud',
                    '--description',
                    'Operational intelligence for teams.',
                    '--brand-gen-dir',
                    str(brand_gen_dir),
                ],
                check=True,
                capture_output=True,
                text=True,
            )

            saved_brand_dir = brand_gen_dir / 'brands' / 'acme-cloud'
            saved_profile_path = saved_brand_dir / 'brand-profile.json'
            saved_profile = json.loads(saved_profile_path.read_text())
            saved_profile.pop('creative_context', None)
            saved_profile_path.write_text(json.dumps(saved_profile, indent=2) + '\n')

            subprocess.run(
                [
                    sys.executable,
                    str(BRAND_ITERATE),
                    'start-testing',
                    '--brand',
                    'acme-cloud',
                    '--session-name',
                    'acme-fork',
                    '--goal',
                    'Try a new direction safely',
                    '--brand-gen-dir',
                    str(brand_gen_dir),
                ],
                check=True,
                capture_output=True,
                text=True,
            )

            session_profile = json.loads(
                (brand_gen_dir / 'sessions' / 'acme-fork' / 'brand-materials' / 'brand-profile.json').read_text()
            )
            saved_profile_after = json.loads(saved_profile_path.read_text())

            self.assertNotIn('creative_context', saved_profile_after)
            self.assertIn('creative_context', session_profile)
            self.assertEqual(session_profile['session_context']['seeded_from_brand'], 'acme-cloud')

    def test_mcp_exposes_brand_create(self):
        tools = {tool['name']: tool for tool in brand_iterate_mcp.TOOLS}
        self.assertIn('brand_create', tools)
        self.assertIn('name', tools['brand_create']['inputSchema']['required'])


if __name__ == '__main__':
    unittest.main()
