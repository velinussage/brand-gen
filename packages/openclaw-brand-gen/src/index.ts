import { readFileSync } from "node:fs";
import { homedir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import {
  McpBridge,
  buildBrandGenContext,
  callJsonTool,
  createHeartbeatState,
  deriveGenerationPolicy,
  executeAction,
  extractJsonFromMcpResult,
  getJournalStats,
  getPendingOutputReviews,
  getRecentEntries,
  getStatusSnapshot,
  isHeartbeatPrompt,
  loadLearnings,
  mapGenerateParams,
  parsePluginConfig,
  resolveActiveWorkspace,
  runHeartbeatCycle,
  scheduleHeartbeat,
  stopHeartbeat,
  summarizeContext,
  toToolResult,
  triggerHeartbeat,
  writeRuntimeStatusMarker,
  type BridgeLike,
  type HeartbeatState,
  type PluginConfig,
} from "../../brand-gen-core/src/index.ts";

const __dirnameCompat = dirname(fileURLToPath(import.meta.url));
const PKG_VERSION: string = (() => {
  try {
    const pkg = JSON.parse(readFileSync(resolve(__dirnameCompat, "..", "package.json"), "utf8"));
    return typeof pkg.version === "string" ? pkg.version : "0.0.0";
  } catch {
    return "0.0.0";
  }
})();

// Inline Type shim — avoids @sinclair/typebox dependency for OpenClaw tool schemas
const Type = {
  String: (options: Record<string, unknown> = {}) => ({ type: "string", ...options }),
  Optional: (schema: Record<string, unknown>) => ({ ...schema, __optional: true }),
  Record: (_key: unknown, value: Record<string, unknown>, options: Record<string, unknown> = {}) => ({
    type: "object",
    additionalProperties: value,
    ...options,
  }),
  Unknown: () => ({}),
  Object: (
    properties: Record<string, Record<string, unknown>>,
    options: Record<string, unknown> = {},
  ) => {
    const required = Object.entries(properties)
      .filter(([, schema]) => !schema.__optional)
      .map(([key]) => key);
    const normalized = Object.fromEntries(
      Object.entries(properties).map(([key, schema]) => {
        const { __optional: _omit, ...rest } = schema;
        return [key, rest];
      }),
    );
    return { type: "object", properties: normalized, required, ...options };
  },
};

type PluginLogger = {
  info: (msg: string) => void;
  warn: (msg: string) => void;
  error: (msg: string) => void;
  debug?: (msg: string) => void;
};

type PluginServiceContext = {
  config: unknown;
  workspaceDir?: string;
  stateDir: string;
  logger: PluginLogger;
};

type PluginApi = {
  id: string;
  name: string;
  logger: PluginLogger;
  pluginConfig?: Record<string, unknown>;
  registerTool: (tool: unknown, opts?: { name?: string; optional?: boolean }) => void;
  registerService: (service: {
    id: string;
    start: (ctx: PluginServiceContext) => void | Promise<void>;
    stop?: (ctx: PluginServiceContext) => void | Promise<void>;
  }) => void;
  on: (hook: string, handler: (...args: unknown[]) => unknown | Promise<unknown>) => void;
};

let brandBridge: McpBridge | null = null;
let logoBridge: McpBridge | null = null;
let discoveredToolCount = 0;
let logoToolCount = 0;
let pluginConfigState: PluginConfig | null = null;
let heartbeatState: HeartbeatState | null = null;

function extractEventPrompt(event: any): string {
  if (!event || typeof event !== "object") return "";
  return typeof event.prompt === "string"
    ? event.prompt
    : typeof event.message === "string"
      ? event.message
      : typeof event.input === "string"
        ? event.input
        : "";
}

function createBrandSearchTool() {
  return {
    name: "brand_search",
    label: "Brand Gen: search",
    description:
      "Read-only brand-gen plugin queries: MCP tools, context, session summary, workspace status, reviews, learnings, and recent entries.",
    parameters: Type.Object({
      action: Type.String(),
      params: Type.Optional(Type.Record(Type.String(), Type.Unknown())),
    }),
    execute: async (_toolCallId: string, params: Record<string, unknown>) => {
      try {
        const action = String(params.action ?? "");
        const p =
          params.params && typeof params.params === "object"
            ? (params.params as Record<string, unknown>)
            : {};
        const config = pluginConfigState;
        if (!config) throw new Error("Plugin is not configured yet.");
        const state = resolveActiveWorkspace(config.brandGenDir);
        if (action === "list_tools") {
          const tools = brandBridge?.isReady() ? await brandBridge.listTools() : [];
          return toToolResult({ tools });
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
          const limit = typeof p.limit === "number" ? p.limit : 10;
          return toToolResult({
            entries:
              state.workspaceDir && state.activeBrand
                ? getRecentEntries(state.workspaceDir, state.activeBrand, limit)
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
        if (action === "get_context") {
          const context = brandBridge
            ? await buildBrandGenContext(brandBridge, config)
            : null;
          return toToolResult({ context });
        }
        if (action === "get_session_summary") {
          return toToolResult({
            summary: brandBridge
              ? await callJsonTool(brandBridge, "brand_show_session_summary", {
                  format: "json",
                }).catch(() => null)
              : null,
          });
        }
        if (action === "get_blackboard") {
          return toToolResult({
            blackboard: brandBridge
              ? await callJsonTool(brandBridge, "brand_show_blackboard", {
                  format: "json",
                }).catch(() => null)
              : null,
          });
        }
        if (action === "get_iteration_memory") {
          return toToolResult({
            iterationMemory: brandBridge
              ? await callJsonTool(brandBridge, "brand_show_iteration_memory", {
                  format: "json",
                }).catch(() => null)
              : null,
          });
        }
        if (action === "get_workspace_status") {
          return toToolResult({
            workspaceStatus: brandBridge
              ? await callJsonTool(brandBridge, "brand_workspace_status", {
                  format: "json",
                }).catch(() => null)
              : null,
          });
        }
        if (action === "get_capabilities") {
          return toToolResult({
            capabilities: brandBridge
              ? await callJsonTool(brandBridge, "brand_capabilities", {
                  format: "json",
                }).catch(() => null)
              : null,
          });
        }
        if (action === "get_improvement_questions") {
          return toToolResult({
            questions: brandBridge
              ? await callJsonTool(brandBridge, "brand_improvement_questions", {
                  format: "json",
                }).catch(() => null)
              : null,
          });
        }
        return toToolResult({ error: `Unknown brand_search action: ${action}` });
      } catch (err) {
        return toToolResult({ error: err instanceof Error ? err.message : String(err) });
      }
    },
  };
}

function createBrandExecuteTool(api: PluginApi) {
  return {
    name: "brand_execute",
    label: "Brand Gen: execute",
    description:
      "Mutating brand-gen plugin actions: generate, derive mockups/videos, consolidate inspiration, feedback, critique submission, switch_brand, patch_learnings, and rate journal outputs.",
    parameters: Type.Object({
      action: Type.String(),
      params: Type.Optional(Type.Record(Type.String(), Type.Unknown())),
    }),
    execute: async (_toolCallId: string, params: Record<string, unknown>) => {
      try {
        const action = String(params.action ?? "");
        const p =
          params.params && typeof params.params === "object"
            ? (params.params as Record<string, unknown>)
            : {};
        const config = pluginConfigState;
        if (!config) throw new Error("Plugin is not configured yet.");
        if (!brandBridge?.isReady()) throw new Error("brand-gen MCP bridge is not connected.");
        return toToolResult(await executeAction(brandBridge, config, action, p));
      } catch (err) {
        api.logger.error(`[brand_execute] ${err instanceof Error ? err.message : String(err)}`);
        return toToolResult({ error: err instanceof Error ? err.message : String(err) });
      }
    },
  };
}

function createBrandStatusTool() {
  return {
    name: "brand_status",
    label: "Brand Gen: status",
    description:
      "Check brand-gen plugin health: MCP bridge state, active brand/session, and memory stats.",
    parameters: Type.Object({}),
    execute: async () => {
      const config = pluginConfigState;
      if (!config) return toToolResult({ pluginVersion: PKG_VERSION, configured: false });
      const hb = heartbeatState ?? createHeartbeatState();
      const snapshot = getStatusSnapshot(config, brandBridge, hb);
      const toolNames = brandBridge?.isReady()
        ? new Set((await brandBridge.listTools()).map((tool) => tool.name))
        : new Set<string>();
      const extras: Record<string, unknown> = {};
      if (toolNames.has("brand_context_snapshot")) {
        extras.contextSnapshot = await callJsonTool(brandBridge!, "brand_context_snapshot", { format: "json" }).catch(() => null);
      }
      if (toolNames.has("brand_workspace_status")) {
        extras.workspaceStatus = await callJsonTool(brandBridge!, "brand_workspace_status", { format: "json" }).catch(() => null);
      }
      if (toolNames.has("brand_capabilities")) {
        extras.capabilities = await callJsonTool(brandBridge!, "brand_capabilities", { format: "json" }).catch(() => null);
      }
      return toToolResult({
        pluginVersion: PKG_VERSION,
        configured: true,
        discoveredToolCount,
        logoBridgeConnected: logoBridge?.isReady() ?? false,
        logoToolCount,
        ...snapshot,
        ...extras,
      });
    },
  };
}

const VALID_LOGO_TOOLS = new Set([
  "logo_generate",
  "logo_feedback",
  "logo_show",
  "logo_compare",
  "logo_evolve",
  "logo_bootstrap",
  "logo_inspire",
]);

function createLogoExecuteTool(api: PluginApi) {
  return {
    name: "logo_execute",
    label: "Logo: execute",
    description:
      "Execute logo iteration tools. Tools: logo_generate, logo_feedback, logo_show, " +
      "logo_compare, logo_evolve, logo_bootstrap, logo_inspire.",
    parameters: Type.Object({
      tool: Type.String({ description: "Logo tool name, e.g. logo_generate" }),
      params: Type.Optional(Type.Record(Type.String(), Type.Unknown())),
    }),
    execute: async (_toolCallId: string, params: Record<string, unknown>) => {
      try {
        if (!logoBridge?.isReady()) throw new Error("Logo MCP bridge is not connected.");
        const toolName = String(params.tool ?? "").trim();
        if (!VALID_LOGO_TOOLS.has(toolName)) {
          throw new Error(
            `Unknown logo tool: ${toolName}. Valid: ${[...VALID_LOGO_TOOLS].join(", ")}`,
          );
        }
        const toolParams =
          params.params && typeof params.params === "object"
            ? (params.params as Record<string, unknown>)
            : {};
        const raw = await logoBridge.callTool(toolName, toolParams);
        const json = extractJsonFromMcpResult(raw);
        return toToolResult(json ?? raw);
      } catch (err) {
        api.logger.error(`[logo_execute] ${err instanceof Error ? err.message : String(err)}`);
        return toToolResult({ error: err instanceof Error ? err.message : String(err) });
      }
    },
  };
}

const plugin = {
  id: "openclaw-brand-gen",
  name: "Brand Gen",
  version: PKG_VERSION,
  description:
    "OpenClaw plugin bridge for brand-gen's MCP runtime with persistent journal + learnings.",
  register(api: PluginApi) {
    const cfg = parsePluginConfig(api.pluginConfig);
    pluginConfigState = cfg;
    heartbeatState = createHeartbeatState();
    writeRuntimeStatusMarker("openclaw-brand-gen", cfg, { pluginVersion: PKG_VERSION, plugin: "openclaw" });

    const brandEnv: Record<string, string> = {
      HOME: homedir(),
      PATH: process.env.PATH || "",
      USER: process.env.USER || "",
      BRAND_GEN_DIR: cfg.brandGenDir,
    };
    for (const key of [
      "REPLICATE_API_TOKEN",
      "GOOGLE_API_KEY",
      "BROWSERBASE_API_KEY",
      "BROWSERBASE_PROJECT_ID",
      "BRAND_DIR",
    ]) {
      if (process.env[key]) brandEnv[key] = process.env[key] as string;
    }

    brandBridge = new McpBridge("python3", [cfg.brandIterateMcpPath], brandEnv, {
      clientName: "openclaw-brand-gen",
      clientVersion: PKG_VERSION,
    });
    brandBridge.on("log", (line: string) => api.logger.info(`[brand-gen-mcp] ${line}`));
    brandBridge.on("error", (err: Error) => api.logger.error(`[brand-gen-mcp] ${err.message}`));

    if (cfg.logoIterateMcpPath) {
      logoBridge = new McpBridge("python3", [cfg.logoIterateMcpPath], brandEnv, {
        clientName: "openclaw-logo",
        clientVersion: PKG_VERSION,
      });
      logoBridge.on("log", (line: string) => api.logger.info(`[logo-mcp] ${line}`));
      logoBridge.on("error", (err: Error) => api.logger.error(`[logo-mcp] ${err.message}`));
    }

    api.registerService({
      id: "brand-gen-mcp-bridge",
      start: async (ctx) => {
        ctx.logger.info("Starting brand-gen MCP bridge...");
        await brandBridge!.start();
        const tools = await brandBridge!.listTools();
        discoveredToolCount = tools.length;
        writeRuntimeStatusMarker("openclaw-brand-gen", cfg, {
          pluginVersion: PKG_VERSION,
          plugin: "openclaw",
          discoveredToolCount,
          logoBridgeConnected: logoBridge?.isReady() ?? false,
        });
        ctx.logger.info(`brand-gen MCP bridge ready with ${tools.length} tools`);
        if (logoBridge) {
          try {
            await logoBridge.start();
            const logoTools = await logoBridge.listTools();
            logoToolCount = logoTools.length;
            ctx.logger.info(`logo MCP bridge ready with ${logoTools.length} tools`);
          } catch (err) {
            ctx.logger.warn(
              `logo MCP bridge failed to start: ${err instanceof Error ? err.message : String(err)}`,
            );
          }
        }
        scheduleHeartbeat(brandBridge!, cfg, heartbeatState!, api.logger);
      },
      stop: async (ctx) => {
        ctx.logger.info("Stopping brand-gen MCP bridge...");
        await stopHeartbeat(heartbeatState!);
        await logoBridge?.stop();
        await brandBridge?.stop();
      },
    });

    api.registerTool(createBrandSearchTool(), { name: "brand_search", optional: true });
    api.registerTool(createBrandExecuteTool(api), { name: "brand_execute", optional: true });
    api.registerTool(createBrandStatusTool(), { name: "brand_status", optional: true });
    api.registerTool(createLogoExecuteTool(api), { name: "logo_execute", optional: true });

    api.on("before_agent_start", async (event: any) => {
      if (!brandBridge || !pluginConfigState || !brandBridge.isReady()) return undefined;
      const prompt = extractEventPrompt(event);
      const heartbeatResult = isHeartbeatPrompt(prompt)
        ? await triggerHeartbeat(brandBridge, pluginConfigState, heartbeatState!, api.logger, "prompt")
        : null;
      const context = await buildBrandGenContext(brandBridge, pluginConfigState).catch(() => null);
      const heartbeatNotice = heartbeatResult
        ? `Heartbeat result: ${JSON.stringify(heartbeatResult, null, 2)}`
        : "";
      const contextSummary = context ? summarizeContext(context) : "";
      const prepend = [contextSummary, heartbeatNotice].filter(Boolean).join("\n\n");
      return prepend ? { prependContext: prepend } : undefined;
    });
  },
};

export default plugin;

export const __test = {
  PKG_VERSION,
  Type,
  createBrandSearchTool,
  buildBrandGenContext,
  deriveGenerationPolicy,
  mapGenerateParams,
  resolveActiveWorkspace,
  runHeartbeatCycle,
};
