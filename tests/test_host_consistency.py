"""Cross-host agent-markdown and specialization parity.

Phase 5 of the typed-agentic-runtime refactor: agent markdown stops being
a runtime contract (long bash procedures) and becomes a thin
specialization doc. The invariants this test enforces:

  1. Every agent listed in brand_gen/agent_specialization.py has a
     markdown file in all three mirrors (.claude/agents/, .pi/agents/,
     skills/brand-gen/claude-agents/).
  2. Every tool listed in any agent's canonical_tools tuple appears in
     the TS CANONICAL_TOOLS registry (the same list
     test_mcp_schema_parity.py parses).
  3. The orchestrator markdown body (everything after the YAML
     frontmatter) is byte-equivalent between .claude/agents/ and
     skills/brand-gen/claude-agents/ — they are meant to be mirrors.
  4. Read-only agent specializations only reference inspection-category
     tools (no mutation tools).
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]

MIRRORS = (
    REPO_ROOT / ".claude" / "agents",
    REPO_ROOT / ".pi" / "agents",
    REPO_ROOT / "skills" / "brand-gen" / "claude-agents",
)

TOOL_REGISTRY_PATH = REPO_ROOT / "packages" / "brand-gen-core" / "src" / "tool-registry.ts"

_CANONICAL_TOOL_RE = re.compile(r'name:\s*"([a-z_]+)"\s*,\s*category:\s*"[a-z]+"')


def _parse_canonical_tool_names() -> set[str]:
    if not TOOL_REGISTRY_PATH.exists():
        raise AssertionError(f"tool-registry.ts missing at {TOOL_REGISTRY_PATH}")
    return set(_CANONICAL_TOOL_RE.findall(TOOL_REGISTRY_PATH.read_text()))


def _strip_frontmatter(markdown: str) -> str:
    """Strip the YAML frontmatter block and leading whitespace.

    Pi markdown uses different model/tool-list frontmatter than Claude Code,
    but the body (the actual contract the agent reads at runtime) should be
    identical across mirrors.
    """
    if not markdown.startswith("---"):
        return markdown.strip()
    end = markdown.find("\n---", 3)
    if end == -1:
        return markdown.strip()
    return markdown[end + 4:].strip()


class AgentSpecializationTests(unittest.TestCase):
    def setUp(self) -> None:
        from brand_gen.agent_specialization import (
            AGENT_SPECIALIZATIONS,
            canonical_tool_usage_across_all_agents,
        )

        self.specs = AGENT_SPECIALIZATIONS
        self.used_tools = canonical_tool_usage_across_all_agents()
        self.canonical_names = _parse_canonical_tool_names()

    def test_every_spec_has_markdown_in_all_three_mirrors(self) -> None:
        missing: list[str] = []
        for spec in self.specs:
            for mirror in MIRRORS:
                path = mirror / f"{spec.agent_id}.md"
                if not path.exists():
                    missing.append(f"{path.relative_to(REPO_ROOT)}")
        self.assertEqual(
            missing,
            [],
            f"Agent markdown files missing from mirrors: {missing}",
        )

    def test_every_spec_tool_is_in_canonical_registry(self) -> None:
        missing = sorted(self.used_tools - self.canonical_names)
        self.assertEqual(
            missing,
            [],
            "Agent specializations reference tools not in the TS "
            f"CANONICAL_TOOLS list: {missing}. Either add the verb to "
            "packages/brand-gen-core/src/tool-registry.ts or remove it "
            "from the agent's canonical_tools tuple.",
        )

    def test_no_duplicate_agent_ids(self) -> None:
        ids = [spec.agent_id for spec in self.specs]
        self.assertEqual(
            len(ids),
            len(set(ids)),
            f"Duplicate agent_id in AGENT_SPECIALIZATIONS: {ids}",
        )

    def test_read_only_agents_reference_only_inspection_tools(self) -> None:
        """brand-explorer and brand-router must not hold mutation verbs."""
        mutation_prefixes = (
            "brand_append_",
            "brand_update_",
            "brand_promote_",
            "brand_set_motion_",
            "brand_submit_",
        )
        offenders: dict[str, list[str]] = {}
        for spec in self.specs:
            if not spec.read_only:
                continue
            leaks = [
                tool
                for tool in spec.canonical_tools
                if any(tool.startswith(prefix) for prefix in mutation_prefixes)
            ]
            if leaks:
                offenders[spec.agent_id] = leaks
        self.assertEqual(
            offenders,
            {},
            f"Read-only agents carry mutation verbs: {offenders}",
        )

    def test_every_spec_has_non_empty_role_description(self) -> None:
        empty = [spec.agent_id for spec in self.specs if not spec.role.strip()]
        self.assertEqual(empty, [], f"Agents with empty role description: {empty}")

    def test_claude_markdown_tools_frontmatter_matches_python_spec(self) -> None:
        """Phase E invariant: every `.claude/agents/<spec>.md` declares
        the same canonical tool list as brand_gen/agent_specialization.

        This is the contract that makes the typed-runtime surface the
        single source of truth — changes to Python flow through to
        markdown without drift.
        """
        import re

        failures: list[str] = []
        claude_dir = REPO_ROOT / ".claude" / "agents"
        for spec in self.specs:
            path = claude_dir / f"{spec.agent_id}.md"
            text = path.read_text(encoding="utf-8")
            match = re.search(r"^tools:\s*\[(.*?)\]", text, re.MULTILINE)
            if not match:
                failures.append(f"{spec.agent_id}: no `tools: [...]` frontmatter")
                continue
            declared = frozenset(
                tool.strip()
                for tool in match.group(1).split(",")
                if tool.strip()
            )
            expected = frozenset(spec.canonical_tools)
            missing = expected - declared
            extra = declared - expected
            if missing or extra:
                failures.append(
                    f"{spec.agent_id}:\n  missing from markdown: {sorted(missing)}\n"
                    f"  extra in markdown:    {sorted(extra)}"
                )
        self.assertEqual(
            failures,
            [],
            "Specialist markdown `tools:` frontmatter diverges from "
            "brand_gen/agent_specialization.py:\n\n" + "\n\n".join(failures),
        )


class OrchestratorMirrorParityTests(unittest.TestCase):
    """The brand-orchestrator contract body must be byte-equivalent between
    .claude/agents/ and skills/brand-gen/claude-agents/ (the distribution
    mirror). The Pi mirror uses different frontmatter (model + tool format
    string), so we compare body-only there.
    """

    def setUp(self) -> None:
        self.claude_path = REPO_ROOT / ".claude" / "agents" / "brand-orchestrator.md"
        self.skills_path = REPO_ROOT / "skills" / "brand-gen" / "claude-agents" / "brand-orchestrator.md"
        self.pi_path = REPO_ROOT / ".pi" / "agents" / "brand-orchestrator.md"

    def test_claude_and_skills_mirrors_match_exactly(self) -> None:
        self.assertEqual(
            self.claude_path.read_text(),
            self.skills_path.read_text(),
            "brand-orchestrator.md must be byte-equivalent between "
            ".claude/agents/ and skills/brand-gen/claude-agents/; they "
            "are meant to be mirrors.",
        )

    def test_pi_body_matches_claude_body(self) -> None:
        claude_body = _strip_frontmatter(self.claude_path.read_text())
        pi_body = _strip_frontmatter(self.pi_path.read_text())
        self.assertEqual(
            claude_body,
            pi_body,
            "brand-orchestrator.md body differs between .claude/agents/ "
            "and .pi/agents/ — the contract text must be identical; only "
            "frontmatter should differ.",
        )

    def test_orchestrator_is_compact_tool_call_contract(self) -> None:
        """Shouldn't balloon back to a 250-line bash procedure."""
        self.assertLessEqual(
            len(self.claude_path.read_text().splitlines()),
            100,
            "brand-orchestrator.md has grown past 100 lines — is it "
            "drifting back toward procedural bash contract? The Phase 5 "
            "target is ≤80 lines.",
        )

    def test_orchestrator_has_no_bash_commands(self) -> None:
        """The orchestrator contract is typed-tool-only after Phase 5."""
        text = self.claude_path.read_text()
        self.assertNotIn(
            "source .venv/bin/activate",
            text,
            "brand-orchestrator.md contains bash activation command; "
            "Phase 5 contract is typed-tool-only.",
        )
        self.assertNotIn(
            "bgen ",
            text,
            "brand-orchestrator.md references `bgen` CLI directly; "
            "Phase 5 contract uses typed tools only.",
        )


class SpecialistBashFreeTests(unittest.TestCase):
    """Phase E: every specialist body must be free of ``source .venv``
    activation blocks. ``bgen`` may still appear as a debugging-fallback
    reference, but the contract is typed-tool-first.
    """

    def test_no_venv_activate_in_any_specialist(self) -> None:
        offenders: list[str] = []
        specialist_files = list((REPO_ROOT / ".claude" / "agents").glob("brand-*.md"))
        specialist_files += list(
            (REPO_ROOT / "skills" / "brand-gen" / "claude-agents").glob("brand-*.md")
        )
        for path in specialist_files:
            text = path.read_text(encoding="utf-8")
            if "source .venv/bin/activate" in text:
                offenders.append(str(path.relative_to(REPO_ROOT)))
        self.assertEqual(
            offenders,
            [],
            "Specialist markdown still carries `source .venv/bin/activate` "
            f"activation blocks (Phase E violation): {offenders}",
        )


if __name__ == "__main__":
    unittest.main()
