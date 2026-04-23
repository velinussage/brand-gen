import { Type } from "@sinclair/typebox";

import {
  callJsonTool,
  canonicalToolDefinition,
  CANONICAL_TOOLS,
  executeAction,
  generateHostTools,
  getJournalStats,
  getPendingOutputReviews,
  getRecentEntries,
  getStatusSnapshot,
  loadLearnings,
  resolveActiveWorkspace,
  toToolResult,
  type BridgeLike,
  type HeartbeatState,
  type HostToolDefinition,
  type PluginConfig,
} from "../../brand-gen-core/src/index.ts";

type ToolDefinition = {
  name: string;
  description: string;
  parameters: Record<string, unknown>;
  execute: (args: any) => Promise<unknown> | unknown;
};

/**
 * Phase 3 of the typed-agentic-runtime refactor: host adapters expose the
 * 44 canonical verb-specific tools from
 * `packages/brand-gen-core/src/tool-registry.ts` instead of the generic
 * `brand_search(action, params)` / `brand_execute(action, params)` multiplexers.
 *
 * The multiplexers remain registered as deprecated shims so older agent
 * scripts keep working — they log a warning and delegate to the underlying
 * MCP bridge call.
 */
export function createCanonicalBrandTools(
  bridge: BridgeLike,
  config: PluginConfig,
): HostToolDefinition[] {
  return generateHostTools(bridge, config);
}

/**
 * Deprecated: generic read-side multiplexer. Kept for backward compatibility
 * so Pi sessions that still use `brand_search({action:"get_context"})`
 * continue to work. New code should call the canonical tool directly, e.g.
 * `brand_context_snapshot`.
 */
export function createBrandSearchTool(bridge: BridgeLike, config: PluginConfig): ToolDefinition {
  const actionMap: Record<string, string> = {
    list_tools: "",
    get_context: "brand_context_snapshot",
    list_brands: "brand_list",
    get_session_summary: "brand_show_session_summary",
    get_blackboard: "brand_show_blackboard",
    get_iteration_memory: "brand_show_iteration_memory",
    get_workspace_status: "brand_workspace_status",
    get_capabilities: "brand_capabilities",
    get_improvement_questions: "brand_improvement_questions",
  };
  return {
    name: "brand_search",
    description:
      "[DEPRECATED] Use the canonical verb-specific tools (brand_context_snapshot, brand_show_blackboard, brand_show_iteration_memory, brand_capabilities, etc.). This multiplexer stays registered for backward compatibility and will be removed in a future release.",
    parameters: Type.Object({
      action: Type.String(),
      params: Type.Optional(Type.Record(Type.String(), Type.Unknown())),
    }),
    execute: async ({ action, params }: { action: string; params?: Record<string, unknown> }) => {
      const state = resolveActiveWorkspace(config.brandGenDir);
      const p = params ?? {};
      const tool = actionMap[action];
      if (tool !== undefined) {
        if (tool === "") {
          const tools = bridge.isReady() ? await bridge.listTools() : [];
          return toToolResult({ tools, canonical: CANONICAL_TOOLS });
        }
        const payload = await callJsonTool(bridge, tool, {
          format: "json",
          ...(params ?? {}),
        });
        if (action === "list_brands") {
          return toToolResult({ brands: payload ?? [] });
        }
        if (action === "get_session_summary") {
          return toToolResult({ summary: payload ?? null });
        }
        if (action === "get_blackboard") {
          return toToolResult({ blackboard: payload ?? null });
        }
        if (action === "get_iteration_memory") {
          return toToolResult({ iterationMemory: payload ?? null });
        }
        if (action === "get_workspace_status") {
          return toToolResult({ workspaceStatus: payload ?? null });
        }
        if (action === "get_capabilities") {
          return toToolResult({ capabilities: payload ?? null });
        }
        if (action === "get_improvement_questions") {
          return toToolResult({ questions: payload ?? null });
        }
        if (action === "get_context") {
          return toToolResult({ context: payload ?? null });
        }
        return toToolResult(payload ?? { status: "ok" });
      }

      if (action === "get_learnings") {
        return toToolResult({
          learnings:
            (state.workspaceDir ? loadLearnings(state.workspaceDir) : null) ??
            (state.savedBrandDir && state.savedBrandDir !== state.workspaceDir
              ? loadLearnings(state.savedBrandDir)
              : null),
        });
      }
      if (action === "get_recent_entries") {
        return toToolResult({
          entries:
            state.workspaceDir && state.activeBrand
              ? getRecentEntries(state.workspaceDir, state.activeBrand, Number(p.limit ?? 10))
              : [],
        });
      }
      if (action === "get_journal_stats") {
        return toToolResult({
          stats:
            state.workspaceDir && state.activeBrand
              ? getJournalStats(state.workspaceDir, state.activeBrand)
              : null,
        });
      }
      if (action === "get_pending_reviews") {
        return toToolResult({
          entries:
            state.workspaceDir && state.activeBrand
              ? getPendingOutputReviews(getRecentEntries(state.workspaceDir, state.activeBrand, 25))
              : [],
        });
      }

      return toToolResult({
        error: `Unknown brand_search action '${action}'. Use canonical tools instead: ${Object.values(
          actionMap,
        )
          .filter(Boolean)
          .join(", ")}.`,
      });
    },
  };
}

/**
 * Deprecated: generic mutation multiplexer. Kept for backward compatibility.
 * New code should call the canonical mutation tools directly
 * (`brand_append_forbidden_pattern`, `brand_update_palette`, etc.).
 */
export function createBrandExecuteTool(bridge: BridgeLike, config: PluginConfig): ToolDefinition {
  return {
    name: "brand_execute",
    description:
      "[DEPRECATED] Use the canonical verb-specific mutation tools (brand_append_forbidden_pattern, brand_update_palette, brand_submit_review, brand_feedback, etc.). This multiplexer stays registered for backward compatibility.",
    parameters: Type.Object({
      action: Type.String(),
      params: Type.Optional(Type.Record(Type.String(), Type.Unknown())),
    }),
    execute: async ({ action, params }: { action: string; params?: Record<string, unknown> }) =>
      toToolResult(await executeAction(bridge, config, action, params ?? {})),
  };
}

export function createBrandStatusTool(
  config: PluginConfig,
  bridge: BridgeLike,
  heartbeat: HeartbeatState,
): ToolDefinition {
  return {
    name: "brand_status",
    description:
      "Check brand-gen bridge health, active brand/session, pending reviews, and heartbeat state.",
    parameters: Type.Object({}),
    execute: async () => {
      const snapshot = getStatusSnapshot(config, bridge as any, heartbeat);
      const toolNames = bridge.isReady()
        ? new Set((await bridge.listTools()).map((tool) => tool.name))
        : new Set<string>();
      const extras: Record<string, unknown> = {};
      if (toolNames.has("brand_context_snapshot")) {
        extras.contextSnapshot = await callJsonTool(bridge, "brand_context_snapshot", {
          format: "json",
        }).catch(() => null);
      }
      if (toolNames.has("brand_workspace_status")) {
        extras.workspaceStatus = await callJsonTool(bridge, "brand_workspace_status", {
          format: "json",
        }).catch(() => null);
      }
      if (toolNames.has("brand_capabilities")) {
        extras.capabilities = await callJsonTool(bridge, "brand_capabilities", {
          format: "json",
        }).catch(() => null);
      }
      return toToolResult({ ...snapshot, ...extras });
    },
  };
}

// Re-export for callers that want to wire the canonical registry directly.
export { canonicalToolDefinition, CANONICAL_TOOLS, generateHostTools };
export type { HostToolDefinition };
