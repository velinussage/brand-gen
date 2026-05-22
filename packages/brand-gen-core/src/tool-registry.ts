// Canonical brand-gen host-tool registry
//
// This module is the single source of truth for the tools host adapters
// (Pi, OpenClaw, Claude Code MCP client) expose to agents. It replaces the
// generic `brand_search(action, params)` / `brand_execute(action, params)`
// multiplexers with a curated list of verb-specific tools (soft cap ~45)
// matching the Python MCP bridge registry in `brand_gen/mcp_bridge_registry.py`.
//
// Per Anthropic 2026 tool-design guidance: semantically-narrow verb-first
// tools kept under the local soft cap are discoverable without long markdown contracts.
// Generic action-enum dispatchers fail agent priors.
//
// The canonical list is validated against the Python side by the
// `tests/test_mcp_schema_parity.py` Python test at CI time.

import {
  callJsonTool,
  toToolResult,
  type BridgeLike,
  type PluginConfig,
} from "./index.js";

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
  | "feedback"
  | "policy";

export type ToolPolicyClass =
  | "read_only"          // always allowed; read-only inspection.
  | "local_mutation"     // writes brand-gen state; configurable per-brand.
  | "costly_generation"  // paid image/video model call; hosts may require approval.
  | "publish_external";  // pushes outside the local workspace; denied by default.

export type CanonicalTool = {
  name: string; // Python MCP bridge tool_name, e.g. "brand_append_forbidden_pattern"
  category: ToolCategory;
  description: string;
  policy_class?: ToolPolicyClass; // Phase D: policy-tag-first enforcement. Keep in sync with brand_gen/policy.py::POLICY_CLASSES_BY_TOOL.
  /**
   * Required parameter keys the host must provide before the tool is
   * dispatched to the Python CLI bridge. Caught pre-spawn so agents get a
   * clear validation error (`missing_required_param: version_id`) instead of
   * an argparse usage blob truncated in the tool-result surface. Populate
   * this for any tool whose CLI bridge would exit non-zero without the key.
   */
  requiredParams?: readonly string[];
  parameterSchema?: Record<string, unknown>;
};

// The canonical host-exposed tools (soft cap ~45). Each maps to exactly one
// brand_gen.mcp_bridge_registry CLI bridge. When adding a tool:
//
//   1. add the verb to this list, and
//   2. confirm the bridge exists in brand_gen/mcp_bridge_registry.py, and
//   3. run `pytest tests/test_mcp_schema_parity.py` to verify.
//
// Ordering is stable: orchestration → mutation → inspection → feedback.
export const CANONICAL_TOOLS: readonly CanonicalTool[] = [
  // Orchestration (8) — stage-by-stage typed responses plus one convenience wrapper and scratchpad prep.
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
      "Phase 2 — draft a material plan (material_type, mode, prompt_seed, style_handle/aesthetic_capsule). Returns PlanRunResponse with plan_id + next_action.",
    requiredParams: ["material_type"],
    parameterSchema: objectSchema({
      material_type: { type: "string", description: "Material type to generate." },
      mode: { type: "string", enum: ["reference", "inspiration", "hybrid"], default: "hybrid" },
      purpose: { type: "string" },
      target_surface: { type: "string" },
      prompt_seed: { type: "string" },
      style_handle: { type: "string", description: "Human shorthand for the desired look; the planner compiles it into a safe curated aesthetic capsule." },
      aesthetic_capsule: { type: "string", description: "Curated aesthetic capsule id/label; overrides automatic capsule selection." },
      render_backend: { type: "string", enum: ["native", "html"], default: "native" },
      workflow_id: { type: "string" },
    }, ["material_type"], "Arguments for brand_plan_run"),
  },
  {
    name: "brand_validate_run",
    category: "orchestration",
    description:
      "Phase 3 — critique the plan, surface blocking issues. Returns ValidateRunResponse with critique_id + status + next_action.",
    requiredParams: ["plan_draft"],
    parameterSchema: objectSchema({
      plan_draft: { type: "string", description: "Path to a plan draft JSON produced by plan-run." },
      workflow_id: { type: "string" },
      critique_mode: { type: "string", enum: ["advisory", "strict"], default: "strict" },
      allow_blocking: { type: "boolean", default: false },
    }, ["plan_draft"], "Arguments for brand_validate_run"),
  },
  {
    name: "brand_execute_run",
    category: "orchestration",
    description:
      "Phase 4 — assemble the scratchpad and generate. Returns ExecuteRunResponse with version_id + image_paths + next_action.",
    policy_class: "costly_generation",
    requiredParams: ["plan_draft"],
    parameterSchema: objectSchema({
      plan_draft: { type: "string", description: "Path to a plan draft JSON produced by plan-run." },
      critique_path: { type: "string" },
      workflow_id: { type: "string" },
      max_iterations: { type: "integer", minimum: 1, maximum: 3, default: 1 },
      max_retries: { type: "integer", minimum: 0, maximum: 2, default: 1 },
      allow_blocking: {
        type: "boolean",
        default: false,
        description: "Record an explicit bypass and continue despite blocking critique/scratchpad findings. Use only when the user explicitly authorizes a bypass.",
      },
    }, ["plan_draft"], "Arguments for brand_execute_run"),
  },
  {
    name: "brand_review_run",
    category: "orchestration",
    description:
      "Phase 5 — run the v2 DSPy scorer + before/after diffs. Returns ReviewRunResponse with axis_scores + decision + next_action.",
    requiredParams: ["version_id"],
    parameterSchema: objectSchema({
      version_id: { type: "string", description: "Generated version id to inspect." },
      workflow_id: { type: "string" },
    }, ["version_id"], "Arguments for brand_review_run"),
  },
  {
    name: "brand_evolve_run",
    category: "orchestration",
    description:
      "Phase 6 — promote learnings, log disagreements, recommend next iteration. Returns EvolveRunResponse with improvement_questions.",
    parameterSchema: objectSchema({
      version_id: { type: "string" },
      workflow_id: { type: "string" },
    }, [], "Arguments for brand_evolve_run"),
  },
  {
    name: "brand_orchestrate_material",
    category: "orchestration",
    description:
      "Convenience: run all six phases end-to-end until a blocking condition. Returns OrchestrateMaterialResponse with stages_completed + stop_reason + next_action + artifacts.",
    policy_class: "costly_generation",
    requiredParams: ["material_type"],
    parameterSchema: objectSchema({
      material_type: { type: "string", description: "Material type to generate." },
      mode: { type: "string", enum: ["reference", "inspiration", "hybrid"], default: "hybrid" },
      purpose: { type: "string" },
      target_surface: { type: "string" },
      prompt_seed: { type: "string" },
      style_handle: { type: "string", description: "Human shorthand for the desired look; the planner compiles it into a safe curated aesthetic capsule." },
      aesthetic_capsule: { type: "string", description: "Curated aesthetic capsule id/label; overrides automatic capsule selection." },
      render_backend: { type: "string", enum: ["native", "html"], default: "native" },
      max_iterations: { type: "integer", minimum: 1, maximum: 3, default: 1 },
      max_retries: { type: "integer", minimum: 0, maximum: 2, default: 1 },
      allow_blocking: { type: "boolean", default: false },
    }, ["material_type"], "Arguments for brand_orchestrate_material"),
  },

  {
    name: "brand_build_generation_scratchpad",
    category: "orchestration",
    description:
      "Assemble a generation scratchpad from a plan without running the paid generation step. Useful for video specialists and debugging generation readiness.",
    policy_class: "local_mutation",
    requiredParams: ["plan"],
    parameterSchema: objectSchema({
      plan: { type: "string", description: "Material plan JSON or plan-draft JSON." },
      prompt: { type: "string", description: "Validated prompt override; for video this is the six-element Seedance prompt." },
      material_type: { type: "string" },
      mode: { type: "string", enum: ["auto", "reference", "inspiration", "hybrid"], default: "auto" },
      generation_mode: { type: "string", enum: ["auto", "image", "video"], default: "auto" },
      model: { type: "string" },
      aspect_ratio: { type: "string" },
      resolution: { type: "string" },
      duration: { type: "integer", minimum: 1 },
      source_version: { type: "string", description: "Prior version id for lineage / derive-video workflows." },
      reference_assets: { type: "array", items: { type: "string" }, description: "Image references; bridged to repeated --image flags." },
      motion_reference: { type: "string", description: "Motion/video reference asset path." },
      base_image: { type: "string", description: "Authoritative base image or screenshot to preserve/edit." },
      style_handle: { type: "string", description: "Optional scratchpad-level aesthetic shorthand override; compiles to a safe capsule block." },
      aesthetic_capsule: { type: "string", description: "Optional scratchpad-level curated aesthetic capsule override." },
      negative_prompt: { type: "string" },
      render_backend: { type: "string", enum: ["native", "html"], default: "native" },
      allow_blocking: { type: "boolean", default: false },
    }, ["plan"], "Arguments for brand_build_generation_scratchpad"),
  },


  // Mutation (13) — typed state-change tools replacing direct JSON/markdown edits.
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
    name: "brand_export_design_tokens",
    category: "mutation",
    description:
      "Export brand identity as production design tokens (CSS/Tailwind/JSON/W3C) and run the WCAG audit before HTML-bound generation.",
    policy_class: "local_mutation",
    parameterSchema: objectSchema({
      output_format: { type: "string", enum: ["css", "tailwind", "json", "w3c"], default: "css" },
      skip_audit: { type: "boolean", default: false },
      out: { type: "string" },
    }, [], "Arguments for brand_export_design_tokens"),
  },
  {
    name: "brand_extract_inspiration",
    category: "mutation",
    description:
      "Run built-in semantic extraction for configured inspiration sources so hybrid/inspiration plans have real source analysis.",
    policy_class: "local_mutation",
    parameterSchema: objectSchema({
      sources: { type: "array", items: { type: "string" } },
      category: { type: "string" },
      workers: { type: "integer", default: 4 },
      force: { type: "boolean", default: false },
      limit: { type: "integer" },
    }, [], "Arguments for brand_extract_inspiration"),
  },
  {
    name: "brand_consolidate_inspiration",
    category: "mutation",
    description:
      "Consolidate extracted inspiration analyses into reusable inspiration-memory artifacts for planning and prompt assembly.",
    policy_class: "local_mutation",
    parameterSchema: objectSchema({
      image: { type: "array", items: { type: "string" } },
    }, [], "Arguments for brand_consolidate_inspiration"),
  },
  {
    name: "brand_submit_review",
    category: "mutation",
    description:
      "Submit a v2 critique packet for a version (alias for submit-critique). Supports --dry-run.",
    requiredParams: ["version_id", "critique_json"],
  },

  // Inspection (15) — read-only queries over durable state.
  //   Phase A added brand_list_runs + brand_get_run (run projection).
  //   Phase B added 6 artifact inspection verbs (plan/critique/scratchpad/review_packet/version/compare).
  {
    name: "brand_list_runs",
    category: "inspection",
    description:
      "List projected Run objects (run_id, current_stage, status, artifact_ids, lineage) from the run ledger. Filter by status (in_progress|blocked|awaiting_review|completed) or material_type. Default format json.",
  },
  {
    name: "brand_get_run",
    category: "inspection",
    description:
      "Fetch the projected Run object for a run_id — derived over the append-only run ledger events. Returns status + artifact_ids an agent can use to resume or inspect.",
  },
  {
    name: "brand_get_plan",
    category: "inspection",
    description:
      "Fetch a plan-draft artifact by run_id (most recent match) or by explicit path. Returns the typed plan JSON an agent can revise.",
  },
  {
    name: "brand_get_critique",
    category: "inspection",
    description:
      "Fetch a plan-critique artifact by run_id or path. Returns blocking_issues + warnings the critic found.",
  },
  {
    name: "brand_get_scratchpad",
    category: "inspection",
    description:
      "Fetch a generation-scratchpad artifact by run_id or path. Shows the execution_prompt, reference assignments, and execution params used for generation.",
  },
  {
    name: "brand_get_review_packet",
    category: "inspection",
    description:
      "Fetch the agent or auto review packet for a generated version (prefers agent-review.json over auto-review.json).",
    requiredParams: ["version_id"],
  },
  {
    name: "brand_get_version",
    category: "inspection",
    description:
      "Fetch the manifest entry + on-disk files for a version.",
    requiredParams: ["version_id"],
    parameterSchema: objectSchema({ version_id: { type: "string" } }, ["version_id"], "Arguments for brand_get_version"),
  },
  {
    name: "brand_compare_versions",
    category: "inspection",
    description:
      "Side-by-side diff of two version manifest entries (material_type, model, score, mode, reference_count, etc.).",
    requiredParams: ["a", "b"],
    parameterSchema: objectSchema({ a: { type: "string" }, b: { type: "string" } }, ["a", "b"], "Arguments for brand_compare_versions"),
  },
  {
    name: "brand_list_brands",
    category: "inspection",
    description:
      "List brands under .brand-gen/brands with profile/identity presence, validation score, warnings, and active marker.",
  },
  {
    name: "brand_switch_brand",
    category: "mutation",
    description:
      "Activate a different brand by slug. Writes activeBrand to .brand-gen/config.json. Takes --brand-key. Administrative mutation granted only to the orchestrator.",
  },
  {
    name: "brand_get_pending_reviews",
    category: "inspection",
    description:
      "List runs whose derived status is awaiting_review — the single source of truth for 'what needs a human'.",
  },
  {
    name: "brand_context_snapshot",
    category: "inspection",
    description:
      "Canonical machine-readable workspace snapshot — active brand, blackboard summary, recent versions, capabilities. Use this at the start of any agent session.",
  },
  {
    name: "brand_source_knowledge",
    category: "inspection",
    description:
      "Search brand-scoped Obsidian/docs markdown configured in source_knowledge and return bounded excerpts for product truth before planning.",
    parameterSchema: objectSchema({
      query: { type: "string", description: "Keyword query such as governed skill network, RLM, DAO, MCP, libraries." },
      limit: { type: "integer", minimum: 1, maximum: 20, default: 8 },
      max_chars: { type: "integer", minimum: 120, maximum: 2000, default: 900 },
    }, [], "Arguments for brand_source_knowledge"),
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

  // Policy (4) — per-brand envelope that hosts (notably OpenClaw) read
  // before dispatching. brand_get_policy is read-only; the other three
  // are local_mutation.
  {
    name: "brand_get_policy",
    category: "policy",
    description:
      "Return the per-brand policy envelope: classes (read_only/local_mutation/costly_generation/publish_external) + pending_approvals + recent_decisions.",
    policy_class: "read_only",
  },
  {
    name: "brand_set_policy",
    category: "policy",
    description:
      "Update the mode (allow|require_approval|deny) for a policy class. Persists to <brand_dir>/.policy.json.",
    policy_class: "local_mutation",
  },
  {
    name: "brand_approve_action",
    category: "policy",
    description:
      "Approve a pending_approval by pending_id, or pre-approve a tool call with --tool (mints + resolves a new pending_id).",
    policy_class: "local_mutation",
  },
  {
    name: "brand_reject_action",
    category: "policy",
    description:
      "Reject a pending_approval by pending_id with an optional reason.",
    policy_class: "local_mutation",
  },

  // Feedback + legacy review (2).
  {
    name: "brand_feedback",
    category: "feedback",
    description:
      "Record a user score and notes on a version. Updates manifest + iteration memory. Use --status rejected for auto-fails.",
    requiredParams: ["version"],
    parameterSchema: objectSchema({
      version: { type: "string", description: "Version ID (e.g. v12)." },
      score: { type: "integer", enum: [1, 2, 3, 4, 5] },
      notes: { type: "string" },
      status: { type: "string", enum: ["favorite", "rejected"] },
    }, ["version"], "Arguments for brand_feedback"),
  },
  {
    name: "brand_critique_rubric",
    category: "feedback",
    description:
      "Produce an agent-visual-review packet for a version. With --dspy-scorer the v2 DSPy rubric runs inline and the packet includes axis_scores + before_after_diffs.",
    requiredParams: ["version_id"],
    parameterSchema: objectSchema({
      version_id: { type: "string" },
      dspy_scorer: { type: "boolean", default: false },
    }, ["version_id"], "Arguments for brand_critique_rubric"),
  },
] as const;

export const CANONICAL_TOOL_NAMES: readonly string[] = CANONICAL_TOOLS.map(
  (tool) => tool.name,
);

function objectSchema(
  properties: Record<string, unknown>,
  required: readonly string[] = [],
  description = "Arguments",
): Record<string, unknown> {
  return {
    type: "object",
    properties,
    ...(required.length ? { required: [...required] } : {}),
    additionalProperties: true,
    description,
  };
}

// Minimal permissive parameter schema shared by every generated host tool.
// The real schema lives in Python (brand_gen.mcp_bridge_registry.build_tool_schema)
// and is exposed through the MCP bridge. TS-side we accept an open object and
// forward verbatim — type validation happens server-side.
//
// OpenAI's function-calling spec requires object schemas to include a
// `properties` field (even an empty `{}`), so we emit one explicitly.
// Without this, providers like openai-codex reject every tool call with
// "Invalid schema for function '...': object schema missing properties".
function openObjectSchema(description: string): Record<string, unknown> {
  return {
    type: "object",
    properties: {},
    additionalProperties: true,
    description,
  };
}

/**
 * Wait for the MCP bridge to become ready before dispatching tool calls.
 *
 * session_start runs bridge.start() in the background (to avoid hanging Pi's
 * session-ready state on a slow MCP handshake). If the LLM emits tool calls
 * before the handshake lands, we'd write JSON-RPC requests to an
 * uninitialized server. This helper blocks up to `timeoutMs` (default 15s)
 * waiting for `bridge.isReady()` before proceeding.
 */
async function waitForBridgeReady(bridge: BridgeLike, timeoutMs = 15000): Promise<boolean> {
  if (bridge.isReady()) return true;
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (bridge.isReady()) return true;
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  return bridge.isReady();
}

/**
 * Wrap a canonical tool entry as a HostToolDefinition that dispatches through
 * the MCP bridge. Host adapters (Pi, OpenClaw) call this to register all
 * canonical tools without repeating dispatch logic.
 *
 * Pi's tool execute signature evolved to `(toolCallId, params, signal,
 * onUpdate, ctx)`. OpenClaw uses `(toolCallId, params)`. Older hosts pass
 * plain `(args)` as the first argument. This wrapper handles all three shapes
 * by sniffing the first argument: if it's a string we treat it as a
 * toolCallId and read params from the second argument.
 */
export function canonicalToolDefinition(
  bridge: BridgeLike,
  tool: CanonicalTool,
): HostToolDefinition {
  return {
    name: tool.name,
    description: tool.description,
    parameters: tool.parameterSchema ?? openObjectSchema(`Arguments for ${tool.name}`),
    execute: (async (...invokeArgs: unknown[]) => {
      // Normalize across Pi / OpenClaw / legacy calling conventions.
      let rawParams: unknown;
      let signal: AbortSignal | undefined;
      if (typeof invokeArgs[0] === "string") {
        // Pi / OpenClaw: (toolCallId, params, signal?, onUpdate?, ctx?)
        rawParams = invokeArgs[1];
        signal = invokeArgs[2] as AbortSignal | undefined;
      } else {
        // Legacy generic host: (args)
        rawParams = invokeArgs[0];
      }
      const params =
        rawParams && typeof rawParams === "object"
          ? ({ ...(rawParams as Record<string, unknown>) } as Record<string, unknown>)
          : {};
      // Default to JSON format so agents get structured payloads back unless
      // they explicitly override.
      if (params.format === undefined) {
        params.format = "json";
      }

      // Pre-flight required-param validation. Without this, the CLI spawns
      // and argparse emits a usage blob that the pi adapter truncates to
      // "brand_xxx failed (exit 1): usage:..." — unreadable to the subagent.
      // Reject the call here with a structured error instead.
      if (tool.requiredParams && tool.requiredParams.length > 0) {
        const missing = tool.requiredParams.filter((key) => {
          const v = (params as Record<string, unknown>)[key];
          return v === undefined || v === null || v === "";
        });
        if (missing.length > 0) {
          return toToolResult({
            status: "error",
            tool: tool.name,
            error: "missing_required_param",
            missing,
            message: `Tool '${tool.name}' requires: ${tool.requiredParams.join(", ")}. Missing: ${missing.join(", ")}.`,
          });
        }
      }

      // Honour AbortSignal if the host supplied one.
      if (signal?.aborted) {
        return toToolResult({ status: "cancelled", tool: tool.name });
      }

      // Wait for bridge readiness; if the handshake never lands, return a
      // structured error instead of hanging the tool call indefinitely.
      const ready = await waitForBridgeReady(bridge);
      if (!ready) {
        return toToolResult({
          status: "error",
          tool: tool.name,
          error: "MCP bridge not ready — Python backend failed to initialize within 15s.",
        });
      }

      const payload = await callJsonTool(bridge, tool.name, params);
      return toToolResult(payload ?? { status: "ok" });
    }) as HostToolDefinition["execute"],
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
