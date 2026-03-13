import { Type } from '@sinclair/typebox';
import type { ToolDefinition } from '@mariozechner/pi-ai';

import {
  buildBrandGenContext,
  executeAction,
  getPendingOutputReviews,
  getStatusSnapshot,
  resolveActiveWorkspace,
  type BridgeLike,
  type HeartbeatState,
  type PluginConfig,
} from './core.ts';
import { getRecentEntries, initMemory, loadLearnings } from './memory.ts';

function toToolResult(payload: unknown) {
  const text = typeof payload === 'string' ? payload : JSON.stringify(payload, null, 2);
  return { content: [{ type: 'text' as const, text }], details: payload };
}

export function createBrandSearchTool(bridge: BridgeLike, config: PluginConfig): ToolDefinition {
  return {
    name: 'brand_search',
    description: 'Read-only brand-gen queries: tools, context, journal stats, pending reviews, learnings, and recent entries.',
    parameters: Type.Object({
      action: Type.String(),
      params: Type.Optional(Type.Record(Type.String(), Type.Unknown())),
    }),
    execute: async ({ action, params }: { action: string; params?: Record<string, unknown> }) => {
      const state = resolveActiveWorkspace(config.brandGenDir);
      const p = params ?? {};
      const db = state.savedBrandDir && state.activeBrand ? initMemory(state.savedBrandDir, state.activeBrand) : null;
      try {
        switch (action) {
          case 'list_tools':
            return toToolResult({ tools: bridge.isReady() ? await bridge.listTools() : [] });
          case 'get_context':
            return toToolResult({ context: await buildBrandGenContext(bridge, config) });
          case 'get_learnings':
            return toToolResult({ learnings: state.savedBrandDir ? loadLearnings(state.savedBrandDir) : null });
          case 'get_recent_entries':
            return toToolResult({ entries: db && state.activeBrand ? getRecentEntries(db, state.activeBrand, Number(p.limit ?? 10)) : [] });
          case 'get_journal_stats':
            return toToolResult(getStatusSnapshot(config, bridge as any, { timer: null, runPromise: null, healthStatus: 'ok', failures: 0, lastResult: null }).journalStats ?? {});
          case 'get_pending_reviews':
            return toToolResult({ entries: db && state.activeBrand ? getPendingOutputReviews(getRecentEntries(db, state.activeBrand, 25)) : [] });
          default:
            return toToolResult({ error: `Unknown brand_search action: ${action}` });
        }
      } finally {
        db?.close();
      }
    },
  };
}

export function createBrandExecuteTool(bridge: BridgeLike, config: PluginConfig): ToolDefinition {
  return {
    name: 'brand_execute',
    description: 'Mutating brand-gen actions: generate, switch_brand, patch_learnings, and rate.',
    parameters: Type.Object({
      action: Type.String(),
      params: Type.Optional(Type.Record(Type.String(), Type.Unknown())),
    }),
    execute: async ({ action, params }: { action: string; params?: Record<string, unknown> }) => toToolResult(await executeAction(bridge, config, action, params ?? {})),
  };
}

export function createBrandStatusTool(config: PluginConfig, bridge: BridgeLike, heartbeat: HeartbeatState): ToolDefinition {
  return {
    name: 'brand_status',
    description: 'Check brand-gen bridge health, active brand/session, pending reviews, and heartbeat state.',
    parameters: Type.Object({}),
    execute: async () => toToolResult(getStatusSnapshot(config, bridge as any, heartbeat)),
  };
}
