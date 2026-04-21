// Canonical brand-gen host-tool registry
//
// This module is the single source of truth for the tools host adapters
// (Pi, OpenClaw, Claude Code MCP client) expose to agents. It replaces the
// generic `brand_search(action, params)` / `brand_execute(action, params)`
// multiplexers with a curated list of ≤25 verb-specific tools matching the
// Python MCP bridge registry in `brand_gen/mcp_bridge_registry.py`.
//
// Per Anthropic 2026 tool-design guidance: semantically-narrow verb-first
// tools (≤20-40 cap) are discoverable without long markdown contracts.
// Generic action-enum dispatchers fail agent priors.
//
// The canonical list is validated against the Python side by the
// `tests/test_mcp_schema_parity.py` Python test at CI time.

import {
  callJsonTool,
  toToolResult,
  type BridgeLike,
  type PluginConfig,
} from "./index.ts";

export type HostToolDefinition = {
  name: string;
  description: string;
  parameters: Record<string, unknown>;
  execute: (args: Record<string, unknown>) => Promise<unknown> | unknown;
};

export type ToolCategory =
  | "orchestration"
  | "mutation"
  | "inspection"
  | "feedback";

export type CanonicalTool = {
  name: string; // Python MCP bridge tool_name, e.g. "brand_append_forbidden_pattern"
  category: ToolCategory;
  description: string;
};

// The canonical ≤25 host-exposed tools. Each maps to exactly one
// brand_gen.mcp_bridge_registry CLI bridge. When adding a tool:
//
//   1. add the verb to this list, and
//   2. confirm the bridge exists in brand_gen/mcp_bridge_registry.py, and
//   3. run `pytest tests/test_mcp_schema_parity.py` to verify.
//
// Ordering is stable: orchestration → mutation → inspection → feedback.
export const CANONICAL_TOOLS: readonly CanonicalTool[] = [
  // Orchestration (7) — stage-by-stage typed responses plus one convenience wrapper.
  {
    name: "brand_prepare_run",
    category: "orchestration",
    description:
      "Phase 1 of the agentic pipeline — read brand DNA, learnings, readiness issues. Returns a typed PrepareRunResponse with a next_action pointer.",
  },
  {
    name: "brand_plan_run",
    category: "orchestration",
    description:
      "Phase 2 — draft a material plan (material_type, mode, prompt_seed, archetype). Returns PlanRunResponse with plan_id + next_action.",
  },
  {
    name: "brand_validate_run",
    category: "orchestration",
    description:
      "Phase 3 — critique the plan, surface blocking issues. Returns ValidateRunResponse with critique_id + status + next_action.",
  },
  {
    name: "brand_execute_run",
    category: "orchestration",
    description:
      "Phase 4 — assemble the scratchpad and generate. Returns ExecuteRunResponse with version_id + image_paths + next_action.",
  },
  {
    name: "brand_review_run",
    category: "orchestration",
    description:
      "Phase 5 — run the v2 DSPy scorer + before/after diffs. Returns ReviewRunResponse with axis_scores + decision + next_action.",
  },
  {
    name: "brand_evolve_run",
    category: "orchestration",
    description:
      "Phase 6 — promote learnings, log disagreements, recommend next iteration. Returns EvolveRunResponse with improvement_questions.",
  },
  {
    name: "brand_orchestrate_material",
    category: "orchestration",
    description:
      "Convenience: run all six phases end-to-end until a blocking condition. Returns OrchestrateMaterialResponse with stages_completed + stop_reason + next_action + artifacts.",
  },

  // Mutation (9) — typed state-change tools replacing direct JSON/markdown edits.
  {
    name: "brand_append_forbidden_pattern",
    category: "mutation",
    description:
      "Append a forbidden pattern to custom-scratchpad.json so future prompts auto-ban it. Supports --dry-run. Dedupes on pattern text.",
  },
  {
    name: "brand_append_custom_scratchpad_note",
    category: "mutation",
    description:
      "Append a directive bullet to a named section of custom-scratchpad.md (global/motion/typography/composition). Supports --dry-run.",
  },
  {
    name: "brand_promote_learning",
    category: "mutation",
    description:
      "Promote a learning to learnings.json under a named bucket (modelPreferences / colorInsights / compositionPatterns / failurePatterns / messagingInsights / audienceInsights).",
  },
  {
    name: "brand_promote_style_policy",
    category: "mutation",
    description:
      "Promote a styleReferencePolicies entry to learnings.json, optionally as a rotating_anchor_set with multiple version anchors.",
  },
  {
    name: "brand_set_motion_grammar",
    category: "mutation",
    description:
      "Set the brand's motion-grammar block (director, favored/banned moves, intensity) in custom-scratchpad.json + .md. Replaces freeform markdown editing.",
  },
  {
    name: "brand_update_palette",
    category: "mutation",
    description:
      "Update one role-hex pair in brand-identity.json and re-run the WCAG audit. Writes to brand_colors + must_preserve.palette_direction + design_language.semantic_palette_roles.",
  },
  {
    name: "brand_update_typography",
    category: "mutation",
    description:
      "Update a typography role (display/body/mono) in brand-identity.json with family + fallback stack.",
  },
  {
    name: "brand_update_devices",
    category: "mutation",
    description:
      "Add or remove an approved graphic device from brand-identity.json approved devices list.",
  },
  {
    name: "brand_submit_review",
    category: "mutation",
    description:
      "Submit a v2 critique packet for a version (alias for submit-critique). Supports --dry-run.",
  },

  // Inspection (7) — read-only queries over durable state.
  {
    name: "brand_context_snapshot",
    category: "inspection",
    description:
      "Canonical machine-readable workspace snapshot — active brand, blackboard summary, recent versions, capabilities. Use this at the start of any agent session.",
  },
  {
    name: "brand_show_blackboard",
    category: "inspection",
    description:
      "Dump the blackboard.json projection: active brief, decisions, reference assignments, latest artifact pointers.",
  },
  {
    name: "brand_show_iteration_memory",
    category: "inspection",
    description:
      "Read iteration memory: positive/negative examples, material-specific notes, rotation state for style anchors and archetypes.",
  },
  {
    name: "brand_show_rubric",
    category: "inspection",
    description:
      "Dump the scoring rubric registry: universal axes + material overlays + disqualifier rules. Required reading before planning or critiquing.",
  },
  {
    name: "brand_show_disagreements",
    category: "inspection",
    description:
      "List agent-vs-user score disagreements with filters (bucket, material, partition). Drives GEPA-style calibration in v2.",
  },
  {
    name: "brand_scoring_status",
    category: "inspection",
    description:
      "Summary of scoring calibration: weighted Cohen's kappa, raw agreement, per-material and per-bucket counts, partition split.",
  },
  {
    name: "brand_capabilities",
    category: "inspection",
    description:
      "Enumerate available brand-gen tools, material types, and runtime capabilities.",
  },

  // Feedback + legacy review (2).
  {
    name: "brand_feedback",
    category: "feedback",
    description:
      "Record a user score and notes on a version. Updates manifest + iteration memory. Use --status rejected for auto-fails.",
  },
  {
    name: "brand_critique_rubric",
    category: "feedback",
    description:
      "Produce an agent-visual-review packet for a version. With --dspy-scorer the v2 DSPy rubric runs inline and the packet includes axis_scores + before_after_diffs.",
  },
] as const;

export const CANONICAL_TOOL_NAMES: readonly string[] = CANONICAL_TOOLS.map(
  (tool) => tool.name,
);

// Minimal permissive parameter schema shared by every generated host tool.
// The real schema lives in Python (brand_gen.mcp_bridge_registry.build_tool_schema)
// and is exposed through the MCP bridge. TS-side we accept an open object and
// forward verbatim — type validation happens server-side.
function openObjectSchema(description: string): Record<string, unknown> {
  return {
    type: "object",
    additionalProperties: true,
    description,
  };
}

/**
 * Wrap a canonical tool entry as a HostToolDefinition that dispatches through
 * the MCP bridge. Host adapters (Pi, OpenClaw) call this to register all ≤25
 * canonical tools without repeating dispatch logic.
 */
export function canonicalToolDefinition(
  bridge: BridgeLike,
  tool: CanonicalTool,
): HostToolDefinition {
  return {
    name: tool.name,
    description: tool.description,
    parameters: openObjectSchema(`Arguments for ${tool.name}`),
    execute: async (args: Record<string, unknown>) => {
      const normalizedArgs = (args && typeof args === "object" ? args : {}) as Record<
        string,
        unknown
      >;
      // Default to JSON format so agents get structured payloads back unless
      // they explicitly override.
      if (normalizedArgs.format === undefined) {
        normalizedArgs.format = "json";
      }
      const payload = await callJsonTool(bridge, tool.name, normalizedArgs);
      return toToolResult(payload ?? { status: "ok" });
    },
  };
}

/**
 * Produce HostToolDefinitions for every canonical tool. Host adapters call
 * this once at startup and register the result with their plugin API.
 */
export function generateHostTools(
  bridge: BridgeLike,
  _config: PluginConfig,
): HostToolDefinition[] {
  return CANONICAL_TOOLS.map((tool) => canonicalToolDefinition(bridge, tool));
}

/**
 * Filter helper: by-category selection for hosts that want to stage rollouts
 * (e.g., register only inspection tools first, then mutation, then
 * orchestration).
 */
export function canonicalToolsByCategory(
  category: ToolCategory,
): readonly CanonicalTool[] {
  return CANONICAL_TOOLS.filter((tool) => tool.category === category);
}
