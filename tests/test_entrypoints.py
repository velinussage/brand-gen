import ast
import subprocess
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BRAND_ITERATE = REPO_ROOT / "brand_gen" / "brand_iterate.py"


class EntrypointTests(unittest.TestCase):
    def test_package_entrypoint_runs(self):
        result = subprocess.run(
            [sys.executable, "-m", "brand_gen.brand_iterate", "types"],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertIn("browser-illustration", result.stdout)

    def test_legacy_shim_reexecs_package_mode(self):
        result = subprocess.run(
            [sys.executable, str(BRAND_ITERATE), "types"],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertIn("browser-illustration", result.stdout)

    def test_shim_stays_thin_and_has_no_cmd_handlers(self):
        source = BRAND_ITERATE.read_text()
        tree = ast.parse(source)
        function_names = [
            node.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]
        self.assertEqual(function_names, ["_reexec_package_mode"])
        self.assertFalse(any(name.startswith("cmd_") for name in function_names))
        self.assertNotIn("sys.path", source)
        self.assertLessEqual(len(source.splitlines()), 120)

    def test_shim_has_no_business_logic_imports(self):
        tree = ast.parse(BRAND_ITERATE.read_text())
        imported_modules: set[str] = set()
        relative_modules: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_modules.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if node.level:
                    relative_modules.add(f"{'.' * node.level}{module}")
                else:
                    imported_modules.add(module)

        self.assertEqual(imported_modules, {"__future__", "os", "sys", "pathlib"})
        self.assertEqual(relative_modules, {".cli"})

    def test_shim_does_not_define_extracted_helper_families(self):
        source = BRAND_ITERATE.read_text()
        forbidden_tokens = [
            "def cmd_",
            "def load_brand_memory(",
            "def load_manifest(",
            "def build_generation_scratchpad(",
            "def build_reference_analysis_inputs(",
            "def save_plan_draft(",
            "def save_generation_scratchpad(",
            "MATERIAL_CONFIG = {",
        ]
        for token in forbidden_tokens:
            self.assertNotIn(token, source, token)


if __name__ == "__main__":
    unittest.main()
