import json
import tempfile
import unittest
from pathlib import Path
import ast

from brand_gen import blackboard, iteration_memory, session

REPO_ROOT = Path(__file__).resolve().parents[1]


class ProjectLayoutTests(unittest.TestCase):
    def test_openclaw_typecheck_uses_tsc(self):
        package_json = json.loads((REPO_ROOT / 'packages' / 'openclaw-brand-gen' / 'package.json').read_text())
        self.assertEqual(package_json['scripts']['typecheck'], 'tsc --noEmit')

    def test_pyproject_exists_and_declares_python_requirement(self):
        pyproject = (REPO_ROOT / 'pyproject.toml').read_text()
        self.assertIn('requires-python = ">=3.11"', pyproject)
        self.assertIn('dataclasses-json', pyproject)
        self.assertIn('bgen = "brand_gen.cli:main"', pyproject)

    def test_runtime_no_longer_imports_shared_logic_from_scripts(self):
        runtime = (REPO_ROOT / 'brand_gen' / 'runtime.py').read_text()
        self.assertNotIn('from scripts.brand_scaffold', runtime)
        self.assertNotIn('from scripts.load_inspiration_doctrine', runtime)
        self.assertTrue((REPO_ROOT / 'brand_gen' / 'brand_scaffold.py').exists())
        self.assertTrue((REPO_ROOT / 'brand_gen' / 'inspiration_doctrine.py').exists())

    def test_runtime_is_split_into_focused_modules(self):
        runtime = (REPO_ROOT / 'brand_gen' / 'runtime.py').read_text()
        for module_name in [
            'runtime_paths',
            'runtime_io',
            'runtime_support',
            'runtime_models',
            'runtime_refs',
            'runtime_brand',
        ]:
            self.assertTrue((REPO_ROOT / 'brand_gen' / f'{module_name}.py').exists(), module_name)
            self.assertIn(f'from .{module_name} import *', runtime)
        self.assertLessEqual(len(runtime.splitlines()), 80)
        self.assertNotIn('def load_env_values(', runtime)
        self.assertNotIn('def build_env(', runtime)
        self.assertNotIn('def load_json_file(', runtime)
        self.assertNotIn('def load_blackboard(', runtime)
        self.assertNotIn('def persist_plan_draft_to_blackboard(', runtime)
        self.assertNotIn('def add_iteration_note(', runtime)
        self.assertNotIn('def role_pack_material_key(', runtime)
        self.assertNotIn('MATERIAL_CONFIG = {', runtime)

    def test_repo_no_longer_imports_legacy_api_internally(self):
        offenders: list[str] = []
        for scope in [REPO_ROOT / 'brand_gen', REPO_ROOT / 'tests']:
            for path in scope.rglob('*.py'):
                if path.name == 'legacy_api.py':
                    continue
                module = ast.parse(path.read_text())
                for node in ast.walk(module):
                    if isinstance(node, ast.ImportFrom) and node.module == 'brand_gen.legacy_api':
                        offenders.append(str(path.relative_to(REPO_ROOT)))
                    elif isinstance(node, ast.Import):
                        for alias in node.names:
                            if alias.name == 'brand_gen.legacy_api':
                                offenders.append(str(path.relative_to(REPO_ROOT)))
        self.assertEqual(offenders, [])

    def test_old_file_path_entrypoint_only_appears_in_compatibility_notes(self):
        allowed = {
            'README.md',
            'CONTRIBUTING.md',
            'docs/brand-iterate-refactor-finish-plan.md',
            'docs/cli-reference.md',
            'docs/getting-started.md',
            'skills/brand-gen/SKILL.md',
        }
        offenders: list[str] = []
        for scope in [REPO_ROOT / 'docs', REPO_ROOT / 'skills']:
            for path in scope.rglob('*.md'):
                rel = str(path.relative_to(REPO_ROOT))
                if 'python3 brand_gen/brand_iterate.py' in path.read_text() and rel not in allowed:
                    offenders.append(rel)
        for rel in ['README.md', 'CONTRIBUTING.md']:
            path = REPO_ROOT / rel
            if 'python3 brand_gen/brand_iterate.py' in path.read_text() and rel not in allowed:
                offenders.append(rel)
        self.assertEqual(sorted(set(offenders)), [])

    def test_session_config_round_trip(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            saved = session.save_brand_gen_config({'active': 'sage'}, repo_root=root)
            loaded = session.load_brand_gen_config(repo_root=root)
            self.assertTrue(saved.exists())
            self.assertEqual(loaded['active'], 'sage')

    def test_iteration_memory_round_trip(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            brand_dir = Path(tmpdir)
            payload = iteration_memory.normalize_iteration_memory({'brand_notes': ['keep logo once']})
            json_path, md_path = iteration_memory.save_iteration_memory(brand_dir, payload)
            loaded = iteration_memory.load_iteration_memory(brand_dir)
            self.assertTrue(json_path.exists())
            self.assertTrue(md_path.exists())
            self.assertEqual(loaded['brand_notes'], ['keep logo once'])

    def test_blackboard_round_trip(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            brand_dir = Path(tmpdir)
            board = blackboard.load_blackboard(brand_dir)
            blackboard.append_blackboard_decision(board, agent='critic', decision='Looks good')
            path = blackboard.save_blackboard(brand_dir, board)
            reloaded = blackboard.load_blackboard(brand_dir)
            self.assertTrue(path.exists())
            self.assertEqual(reloaded['decisions'][0]['agent'], 'critic')


if __name__ == '__main__':
    unittest.main()
