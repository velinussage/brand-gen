import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MCP_DIR = REPO_ROOT / 'mcp'
if str(MCP_DIR) not in sys.path:
    sys.path.insert(0, str(MCP_DIR))

import brand_iterate_mcp  # type: ignore

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

    def test_mcp_exposes_brand_create(self):
        tools = {tool['name']: tool for tool in brand_iterate_mcp.TOOLS}
        self.assertIn('brand_create', tools)
        self.assertIn('name', tools['brand_create']['inputSchema']['required'])


if __name__ == '__main__':
    unittest.main()
