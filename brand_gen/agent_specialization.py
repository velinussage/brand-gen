"""Canonical per-agent tool allowlists.

Phase 5 of the typed-agentic-runtime refactor: agent markdown files stop
being long procedural bash contracts and become short specialization
docs. The tool allowlist that each agent can call is declared here once,
then consumed by:

  - agent markdown frontmatter (the `tools: [...]` field)
  - host-consistency tests that enforce parity across the three mirrors
    (.claude/agents/, .pi/agents/, skills/brand-gen/claude-agents/)

Invariants enforced by tests/test_host_consistency.py:

  1. Every tool listed here must exist in packages/brand-gen-core/src/
     tool-registry.ts's CANONICAL_TOOLS (soft-capped canonical surface).
  2. Every agent_id referenced here must have a markdown file in all
     three mirrors.
  3. Each mirror's brand-orchestrator.md is byte-equivalent after
     frontmatter normalization (same tool-call contract).
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class AgentSpecialization:
    """Declarative per-agent tool allowlist + role description.

    Fields:
      agent_id: slug matching the .md filename (brand-orchestrator,
        brand-planner, ...).
      role: one-sentence description shown to the orchestrator when
        delegating.
      canonical_tools: tuple of tool_name strings from
        tool-registry.ts's CANONICAL_TOOLS. No tool outside that list
        should appear.
      read_only: if True, the agent may only call inspection-category
        tools (used to double-check markdown frontmatter).
    """

    agent_id: str
    role: str
    canonical_tools: tuple[str, ...]
    read_only: bool = False
    may_call_orchestrator: bool = False


# Read-only inspection verbs (subset of CANONICAL_TOOLS that pure readers
# need). Used by the explorer and router agents.
_INSPECTION_TOOLS: tuple[str, ...] = (
    "brand_context_snapshot",
    "brand_source_knowledge",
    "brand_show_blackboard",
    "brand_show_iteration_memory",
    "brand_show_rubric",
    "brand_show_disagreements",
    "brand_scoring_status",
    "brand_capabilities",
    "brand_list_runs",
    "brand_get_run",
    "brand_get_plan",
    "brand_get_critique",
    "brand_get_scratchpad",
    "brand_get_review_packet",
    "brand_get_version",
    "brand_compare_versions",
    "brand_list_brands",
    "brand_get_pending_reviews",
    "brand_get_policy",
)


# Administrative mutation: activates a brand, writes activeBrand to
# .brand-gen/config.json. Granted only to the orchestrator (not to
# read-only agents).
_ADMIN_MUTATIONS: tuple[str, ...] = (
    "brand_switch_brand",
)


# Phase D: policy verbs. brand_get_policy is read-only (safe to grant
# broadly); set/approve/reject are operator-level mutations granted only
# to the orchestrator.
_POLICY_READ_TOOLS: tuple[str, ...] = (
    "brand_get_policy",
)
_POLICY_MUTATIONS: tuple[str, ...] = (
    "brand_set_policy",
    "brand_approve_action",
    "brand_reject_action",
)


# Scratchpad/readiness verbs used by specialists before paid generation.
_GENERATION_PREP_TOOLS: tuple[str, ...] = (
    "brand_build_generation_scratchpad",
)

# Inspiration/design-token mutations used by philosopher/planner preflights.
_PREP_MUTATIONS: tuple[str, ...] = (
    "brand_export_design_tokens",
    "brand_extract_inspiration",
    "brand_consolidate_inspiration",
)

# Mutation verbs the critic uses to land decisions from review packets.
_CRITIC_MUTATIONS: tuple[str, ...] = (
    "brand_append_forbidden_pattern",
    "brand_append_custom_scratchpad_note",
    "brand_submit_review",
    "brand_feedback",
    "brand_critique_rubric",
)


# Mutation verbs the philosopher owns (identity + scratchpad authoring).
_PHILOSOPHER_MUTATIONS: tuple[str, ...] = (
    "brand_update_palette",
    "brand_update_typography",
    "brand_update_devices",
    "brand_set_motion_grammar",
    "brand_append_custom_scratchpad_note",
)


# Orchestrator-only: the full stage surface.
_ORCHESTRATION_TOOLS: tuple[str, ...] = (
    "brand_prepare_run",
    "brand_plan_run",
    "brand_validate_run",
    "brand_execute_run",
    "brand_review_run",
    "brand_evolve_run",
    "brand_orchestrate_material",
)


AGENT_SPECIALIZATIONS: tuple[AgentSpecialization, ...] = (
    AgentSpecialization(
        agent_id="orchestrator",
        role=(
            "Default entry point. Campaigns control plane execution, handling "
            "stop reasons by routing tasks."
        ),
        canonical_tools=_ORCHESTRATION_TOOLS
        + _INSPECTION_TOOLS
        + _CRITIC_MUTATIONS
        + _ADMIN_MUTATIONS
        + _POLICY_MUTATIONS,
        may_call_orchestrator=False,
    ),
    AgentSpecialization(
        agent_id="strategist",
        role=(
            "Cultivates design philosophy, builds campaign briefs, drafts creative "
            "plan proposals, and manages brand variables."
        ),
        canonical_tools=(
            "brand_plan_run",
            "brand_validate_run",
        )
        + _INSPECTION_TOOLS
        + _PREP_MUTATIONS
        + _PHILOSOPHER_MUTATIONS,
        may_call_orchestrator=True,
    ),
    AgentSpecialization(
        agent_id="art-director",
        role=(
            "Shot-design specialist. Translates creative intent into cinematography "
            "shot layouts, motion grammars, and visual directions."
        ),
        canonical_tools=(
            "brand_execute_run",
            "brand_build_generation_scratchpad",
            "brand_set_motion_grammar",
            "brand_context_snapshot",
            "brand_show_iteration_memory",
            "brand_capabilities",
        ),
    ),
    AgentSpecialization(
        agent_id="prompt-engineer",
        role=(
            "Translates visual directions, creative intent, and brand aesthetics "
            "into high-fidelity, descriptive image prompts."
        ),
        canonical_tools=(
            "brand_build_generation_scratchpad",
            "brand_context_snapshot",
            "brand_show_blackboard",
            "brand_capabilities",
        ),
    ),
    AgentSpecialization(
        agent_id="generator",
        role=(
            "Executes generation from approved plans. Chooses models within "
            "allowed policies."
        ),
        canonical_tools=(
            "brand_execute_run",
            "brand_context_snapshot",
            "brand_show_blackboard",
            "brand_capabilities",
        ),
    ),
    AgentSpecialization(
        agent_id="product-truth-reviewer",
        role=(
            "Critique panelist focused on Sage product truth, value-proposition "
            "fidelity, and meaning clarity."
        ),
        canonical_tools=(
            "brand_validate_run",
            "brand_review_run",
            "brand_context_snapshot",
            "brand_show_blackboard",
            "brand_submit_review",
            "brand_feedback",
        ),
    ),
    AgentSpecialization(
        agent_id="critic-composition",
        role=(
            "Critique panelist focused on layout hierarchy, whitespace balance, "
            "graphic devices, and visual slop checks."
        ),
        canonical_tools=(
            "brand_validate_run",
            "brand_review_run",
            "brand_context_snapshot",
            "brand_show_blackboard",
            "brand_submit_review",
            "brand_feedback",
        ),
    ),
    AgentSpecialization(
        agent_id="critic-copy",
        role=(
            "Critique panelist focused on typography legibility, copy alignment, "
            "copy slop check, and WCAG contrast audit rules."
        ),
        canonical_tools=(
            "brand_validate_run",
            "brand_review_run",
            "brand_context_snapshot",
            "brand_show_blackboard",
            "brand_submit_review",
            "brand_feedback",
        ),
    ),
    AgentSpecialization(
        agent_id="synthesizer",
        role=(
            "Campaign dossier compiler. Synthesizes inputs from the critique panel "
            "and formats the campaign review packet."
        ),
        canonical_tools=(
            "brand_validate_run",
            "brand_review_run",
            "brand_context_snapshot",
            "brand_show_blackboard",
            "brand_submit_review",
            "brand_feedback",
        )
        + _INSPECTION_TOOLS,
    ),
)


AGENT_BY_ID: dict[str, AgentSpecialization] = {
    spec.agent_id: spec for spec in AGENT_SPECIALIZATIONS
}


def tool_allowlist_frontmatter(agent_id: str) -> str:
    """Render the YAML `tools:` line for an agent's markdown frontmatter."""
    spec = AGENT_BY_ID.get(agent_id)
    if spec is None:
        raise KeyError(f"Unknown agent_id: {agent_id!r}")
    tool_list = ", ".join(spec.canonical_tools)
    return f"tools: [{tool_list}]"


def canonical_tool_usage_across_all_agents() -> set[str]:
    """Union of every tool name referenced by any agent specialization.

    Used by host-consistency tests to assert every agent tool appears in
    the TS CANONICAL_TOOLS list.
    """
    used: set[str] = set()
    for spec in AGENT_SPECIALIZATIONS:
        used.update(spec.canonical_tools)
    return used
