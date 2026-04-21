"""Cross-host parity: every canonical tool declared in the TS tool-registry
must correspond to a live Python MCP bridge.

Background (Phase 3 of the typed-agentic-runtime refactor): the generic
`brand_search(action, params)` / `brand_execute(action, params)` multiplexers
on Pi and OpenClaw were replaced with a curated list of ≤25 verb-specific
host tools, declared once in
`packages/brand-gen-core/src/tool-registry.ts` and re-used by every host
adapter.

The TS file is the canonical source of truth host-side. This Python test
parses it (text-only — no TS runtime required), extracts the
CANONICAL_TOOLS names, and asserts each one:

- exists as a tool_name in `brand_gen.mcp_bridge_registry.BRIDGE_BY_TOOL`
- is backed by an enabled CLI bridge (convenience wrappers excluded)
- is declared in one of the four recognized categories
- plus the total count stays at or below the 25-tool soft cap per
  Anthropic's 2026 tool-design guidance.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
TOOL_REGISTRY_PATH = REPO_ROOT / "packages" / "brand-gen-core" / "src" / "tool-registry.ts"

_VALID_CATEGORIES = {"orchestration", "mutation", "inspection", "feedback"}

_TOOL_ENTRY_RE = re.compile(
    r'name:\s*"(?P<name>[a-z_]+)"\s*,\s*category:\s*"(?P<category>[a-z]+)"',
    re.DOTALL,
)


def _parse_canonical_tools() -> list[tuple[str, str]]:
    """Return [(tool_name, category), ...] parsed from the TS tool-registry.

    Text parse is fine here — the file is deliberately authored in a stable
    declarative shape so the Python test can mirror it without a JS runtime.
    """
    if not TOOL_REGISTRY_PATH.exists():
        raise AssertionError(f"tool-registry.ts missing at {TOOL_REGISTRY_PATH}")
    text = TOOL_REGISTRY_PATH.read_text()
    matches = _TOOL_ENTRY_RE.findall(text)
    if not matches:
        raise AssertionError(
            "Failed to parse any canonical tool entries from tool-registry.ts — "
            "the regex expects `name: \"...\", category: \"...\"`."
        )
    return matches


class CanonicalToolParityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.canonical_tools = _parse_canonical_tools()
        self.canonical_names = [name for name, _ in self.canonical_tools]
        # Import here so the test file can be parsed even when brand_gen isn't on
        # sys.path (the test itself will fail cleanly instead of collection-erroring).
        from brand_gen.mcp_bridge_registry import BRIDGE_BY_TOOL

        self.bridge_by_tool = BRIDGE_BY_TOOL

    def test_registry_parses_at_least_one_tool(self) -> None:
        self.assertGreaterEqual(
            len(self.canonical_tools),
            10,
            "Expected at least 10 canonical tools in tool-registry.ts",
        )

    def test_no_duplicate_tool_names(self) -> None:
        self.assertEqual(
            len(self.canonical_names),
            len(set(self.canonical_names)),
            f"Duplicate canonical tool names: {self.canonical_names}",
        )

    def test_every_category_is_recognized(self) -> None:
        for name, category in self.canonical_tools:
            self.assertIn(
                category,
                _VALID_CATEGORIES,
                f"Canonical tool {name!r} has unrecognized category {category!r}; "
                f"must be one of {sorted(_VALID_CATEGORIES)}",
            )

    def test_every_canonical_tool_has_python_bridge(self) -> None:
        missing = [name for name in self.canonical_names if name not in self.bridge_by_tool]
        self.assertEqual(
            missing,
            [],
            "Canonical tools declared in tool-registry.ts have no matching "
            f"Python MCP bridge: {missing}. Either add a CLI command + bridge "
            "in brand_gen/mcp_bridge_registry.py, or remove the tool from the "
            "canonical list.",
        )

    def test_every_canonical_tool_is_a_primitive_bridge(self) -> None:
        """Convenience wrappers (e.g. pipeline) shouldn't appear in the
        canonical surface — agents should call the individual stage verbs
        instead. The one exception is brand_orchestrate_material which IS a
        primitive stage-orchestration wrapper.
        """
        allowed_convenience = {"brand_orchestrate_material", "brand_critique_rubric"}
        offenders: list[str] = []
        for name in self.canonical_names:
            bridge = self.bridge_by_tool.get(name)
            if bridge is None:
                continue
            if bridge.convenience and name not in allowed_convenience:
                offenders.append(name)
        self.assertEqual(
            offenders,
            [],
            f"Canonical tools that wrap convenience commands: {offenders}. "
            "Agents should call primitive verbs instead.",
        )

    def test_soft_cap_respected(self) -> None:
        # Cap raised from 25 → 45 for the Phase A-D runtime-discovery-policy
        # work (run projection, artifact inspection, brand discovery,
        # policy/approval). Each addition is narrowly scoped by category;
        # the category groupings remain small.
        self.assertLessEqual(
            len(self.canonical_tools),
            45,
            f"Canonical tool list has {len(self.canonical_tools)} entries; "
            "soft cap is 45. Growing beyond this undermines agent discovery "
            "(Anthropic 2026 tool-design guidance).",
        )

    def test_required_orchestration_verbs_present(self) -> None:
        required = {
            "brand_prepare_run",
            "brand_plan_run",
            "brand_validate_run",
            "brand_execute_run",
            "brand_review_run",
            "brand_evolve_run",
            "brand_orchestrate_material",
        }
        actual = set(self.canonical_names)
        self.assertTrue(
            required.issubset(actual),
            f"Orchestration verbs missing from canonical list: {sorted(required - actual)}",
        )

    def test_required_mutation_verbs_present(self) -> None:
        required = {
            "brand_append_forbidden_pattern",
            "brand_append_custom_scratchpad_note",
            "brand_promote_learning",
            "brand_promote_style_policy",
            "brand_set_motion_grammar",
            "brand_update_palette",
            "brand_update_typography",
            "brand_update_devices",
            "brand_submit_review",
        }
        actual = set(self.canonical_names)
        self.assertTrue(
            required.issubset(actual),
            f"Mutation verbs missing from canonical list: {sorted(required - actual)}",
        )

    def test_categories_match_known_python_grouping(self) -> None:
        """Sanity: orchestration verbs on the TS side must align with
        orchestration-shaped commands on the Python side (those we added in
        Phase 2 of the refactor).
        """
        orchestration_prefix = {
            "brand_prepare_run",
            "brand_plan_run",
            "brand_validate_run",
            "brand_execute_run",
            "brand_review_run",
            "brand_evolve_run",
            "brand_orchestrate_material",
        }
        by_category: dict[str, list[str]] = {}
        for name, category in self.canonical_tools:
            by_category.setdefault(category, []).append(name)
        self.assertTrue(
            orchestration_prefix.issubset(set(by_category.get("orchestration", []))),
            f"Orchestration category in TS registry missing expected verbs; "
            f"got {sorted(by_category.get('orchestration', []))}",
        )


class DeprecatedMultiplexerShimTests(unittest.TestCase):
    """The generic multiplexers stay registered for backward compatibility.
    This test guards against accidentally removing the compat path or the
    `[DEPRECATED]` marker in their host descriptions.
    """

    def test_pi_tool_keeps_brand_search_and_brand_execute(self) -> None:
        pi_tool_path = REPO_ROOT / "packages" / "pi-brand-gen" / "src" / "tool.ts"
        text = pi_tool_path.read_text()
        self.assertIn('name: "brand_search"', text)
        self.assertIn('name: "brand_execute"', text)
        self.assertIn("[DEPRECATED]", text)

    def test_openclaw_keeps_brand_search_and_brand_execute(self) -> None:
        path = REPO_ROOT / "packages" / "openclaw-brand-gen" / "src" / "index.ts"
        text = path.read_text()
        self.assertIn('name: "brand_search"', text)
        self.assertIn('name: "brand_execute"', text)
        self.assertIn("[DEPRECATED]", text)


if __name__ == "__main__":
    unittest.main()
