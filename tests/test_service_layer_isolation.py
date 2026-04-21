"""Phase 6 invariant: services/ must not cross-import each other.

The point of the facade split is that callers that need two layers
(memory + orchestration, orchestration + prompt) compose at the call
site — they don't rely on one service quietly pulling another.

If memory_service.py imports orchestration_service.py, refactors
become viral and the layering guarantee is lost.
"""
from __future__ import annotations

import ast
import unittest
from pathlib import Path


SERVICES_DIR = Path(__file__).resolve().parents[1] / "brand_gen" / "services"

_SERVICE_MODULES = ("memory_service", "orchestration_service", "prompt_resolver")


def _imports_from(module_path: Path) -> set[str]:
    """Return the set of sibling-service module names imported by this
    file. Local helpers inside brand_gen are OK; only cross-service
    imports are forbidden.
    """
    tree = ast.parse(module_path.read_text())
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            # relative imports: "from .memory_service import ..."
            if node.module in _SERVICE_MODULES:
                imported.add(node.module)
            # absolute imports: "from brand_gen.services.memory_service import ..."
            if node.module and node.module.startswith("brand_gen.services."):
                sibling = node.module.split(".", 2)[-1]
                if sibling in _SERVICE_MODULES:
                    imported.add(sibling)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("brand_gen.services."):
                    sibling = alias.name.split(".", 2)[-1]
                    if sibling in _SERVICE_MODULES:
                        imported.add(sibling)
    return imported


class ServiceLayerIsolationTests(unittest.TestCase):
    def test_services_package_exists(self) -> None:
        self.assertTrue(SERVICES_DIR.is_dir(), f"services/ dir missing at {SERVICES_DIR}")
        for name in _SERVICE_MODULES:
            path = SERVICES_DIR / f"{name}.py"
            self.assertTrue(path.exists(), f"{name}.py missing at {path}")

    def test_memory_service_does_not_cross_import(self) -> None:
        path = SERVICES_DIR / "memory_service.py"
        imported = _imports_from(path)
        offenders = imported - {"memory_service"}
        self.assertEqual(
            offenders,
            set(),
            f"memory_service.py cross-imports: {offenders}. "
            "Callers that need multiple services compose at the call site.",
        )

    def test_orchestration_service_does_not_cross_import(self) -> None:
        path = SERVICES_DIR / "orchestration_service.py"
        imported = _imports_from(path)
        offenders = imported - {"orchestration_service"}
        self.assertEqual(
            offenders,
            set(),
            f"orchestration_service.py cross-imports: {offenders}.",
        )

    def test_prompt_resolver_does_not_cross_import(self) -> None:
        path = SERVICES_DIR / "prompt_resolver.py"
        imported = _imports_from(path)
        offenders = imported - {"prompt_resolver"}
        self.assertEqual(
            offenders,
            set(),
            f"prompt_resolver.py cross-imports: {offenders}.",
        )

    def test_all_three_services_instantiate(self) -> None:
        from brand_gen.services import (
            MemoryService,
            OrchestrationService,
            PromptResolver,
        )

        # Instantiating should not require any external state — the
        # classes accept a brand_dir Path and do lazy reads.
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            brand = Path(tmpdir)
            mem = MemoryService(brand)
            orch = OrchestrationService(brand)
            resolver = PromptResolver()
            self.assertEqual(mem.brand_dir, brand)
            self.assertEqual(orch.brand_dir, brand)
            self.assertIsNotNone(resolver)

    def test_memory_service_snapshot_shape(self) -> None:
        import tempfile

        from brand_gen.services import MemoryService

        with tempfile.TemporaryDirectory() as tmpdir:
            snapshot = MemoryService(Path(tmpdir)).snapshot()
            self.assertIn("brand_dir", snapshot)
            self.assertIn("learnings_summary", snapshot)
            self.assertIn("iteration_memory", snapshot)
            self.assertIn("inspiration_sources", snapshot)

    def test_prompt_resolver_returns_typed_result(self) -> None:
        from brand_gen.services import PromptResolver

        resolver = PromptResolver()
        result = resolver.resolve(
            "A brand concept.",
            {
                "material_prompt_key": "concept_illustration",
                "material_prompt_snippet": "policy",
                "reference_role_pack": [],
            },
            material_type="concept-illustration",
            generation_mode="image",
        )
        self.assertTrue(hasattr(result, "execution_prompt"))
        self.assertTrue(hasattr(result, "blocks"))
        self.assertTrue(hasattr(result, "dropped_blocks"))
        self.assertIsInstance(result.execution_prompt, str)
        self.assertIsInstance(result.blocks, tuple)


if __name__ == "__main__":
    unittest.main()
