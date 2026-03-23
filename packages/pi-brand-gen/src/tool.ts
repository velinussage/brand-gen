import { Type } from "@sinclair/typebox";

import {
  buildBrandGenContext,
  callJsonTool,
  executeAction,
  getRecentEntries,
  getStatusSnapshot,
  getPendingOutputReviews,
  loadLearnings,
  resolveActiveWorkspace,
  toToolResult,
  type BridgeLike,
  type HeartbeatState,
  type PluginConfig,
} from "../../brand-gen-core/src/index.ts";

type ToolDefinition = {
  name: string;
  description: string;
  parameters: Record<string, unknown>;
  execute: (args: any) => Promise<unknown> | unknown;
};

export function createBrandSearchTool(bridge: BridgeLike, config: PluginConfig): ToolDefinition {
  return {
    name: "brand_search",
    description:
      "Read-only brand-gen queries: tools, context, session summary, workspace status, reviews, learnings, and recent entries.",
    parameters: Type.Object({
      action: Type.String(),
      params: Type.Optional(Type.Record(Type.String(), Type.Unknown())),
    }),
    execute: async ({ action, params }: { action: string; params?: Record<string, unknown> }) => {
      const state = resolveActiveWorkspace(config.brandGenDir);
      const p = params ?? {};
      switch (action) {
        case "list_tools":
          return toToolResult({ tools: bridge.isReady() ? await bridge.listTools() : [] });
        case "get_context":
          return toToolResult({ context: await buildBrandGenContext(bridge, config) });
        case "list_brands":
          return toToolResult({
            brands: await callJsonTool(bridge, "brand_list", { format: "json" }),
          });
        case "get_session_summary":
          return toToolResult({
            summary: await callJsonTool(bridge, "brand_show_session_summary", { format: "json" }),
          });
        case "get_blackboard":
          return toToolResult({
            blackboard: await callJsonTool(bridge, "brand_show_blackboard", { format: "json" }),
          });
        case "get_iteration_memory":
          return toToolResult({
            iterationMemory: await callJsonTool(bridge, "brand_show_iteration_memory", {
              format: "json",
            }),
          });
        case "get_workspace_status":
          return toToolResult({
            workspaceStatus: await callJsonTool(bridge, "brand_workspace_status", {
              format: "json",
            }),
          });
        case "get_capabilities":
          return toToolResult({
            capabilities: await callJsonTool(bridge, "brand_capabilities", { format: "json" }),
          });
        case "get_improvement_questions":
          return toToolResult({
            questions: await callJsonTool(bridge, "brand_improvement_questions", {
              format: "json",
            }),
          });
        case "get_learnings":
          return toToolResult({
            learnings:
              (state.workspaceDir ? loadLearnings(state.workspaceDir) : null) ??
              (state.savedBrandDir && state.savedBrandDir !== state.workspaceDir
                ? loadLearnings(state.savedBrandDir)
                : null),
          });
        case "get_recent_entries":
          return toToolResult({
            entries:
              state.workspaceDir && state.activeBrand
                ? getRecentEntries(state.workspaceDir, state.activeBrand, Number(p.limit ?? 10))
                : [],
          });
        case "get_journal_stats":
          return toToolResult({
            stats:
              getStatusSnapshot(config, bridge as any, {
                timer: null,
                runPromise: null,
                healthStatus: "ok",
                failures: 0,
                lastResult: null,
              }).journalStats ?? null,
          });
        case "get_pending_reviews":
          return toToolResult({
            entries:
              state.workspaceDir && state.activeBrand
                ? getPendingOutputReviews(getRecentEntries(state.workspaceDir, state.activeBrand, 25))
                : [],
          });
        default:
          return toToolResult({ error: `Unknown brand_search action: ${action}` });
      }
    },
  };
}

export function createBrandExecuteTool(bridge: BridgeLike, config: PluginConfig): ToolDefinition {
  return {
    name: "brand_execute",
    description:
      "Mutating brand-gen actions: generate, derive mockups/videos, consolidate inspiration, feedback, critique submission, switch_brand, patch_learnings, and rate.",
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
      const toolNames = bridge.isReady() ? new Set((await bridge.listTools()).map((tool) => tool.name)) : new Set<string>();
      const extras: Record<string, unknown> = {};
      if (toolNames.has("brand_context_snapshot")) {
        extras.contextSnapshot = await callJsonTool(bridge, "brand_context_snapshot", { format: "json" }).catch(() => null);
      }
      if (toolNames.has("brand_workspace_status")) {
        extras.workspaceStatus = await callJsonTool(bridge, "brand_workspace_status", { format: "json" }).catch(() => null);
      }
      if (toolNames.has("brand_capabilities")) {
        extras.capabilities = await callJsonTool(bridge, "brand_capabilities", { format: "json" }).catch(() => null);
      }
      return toToolResult({ ...snapshot, ...extras });
    },
  };
}
