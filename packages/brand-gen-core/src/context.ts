import type { BrandContext, BridgeLike, PluginConfig } from "./types.ts";
import { defaultLearnings, getRecentEntries, loadLearnings } from "./memory.ts";
import { resolveActiveWorkspace, readJsonFile } from "./workspace.ts";

export function extractJsonFromMcpResult(result: unknown): unknown {
  const anyResult = result as any;
  if (!anyResult || typeof anyResult !== "object") return undefined;
  const text = Array.isArray(anyResult.content)
    ? anyResult.content
        .map((item: any) => (item && typeof item.text === "string" ? item.text : ""))
        .filter(Boolean)
        .join("\n")
    : "";
  if (!text) return undefined;
  try {
    return JSON.parse(text);
  } catch {
    return undefined;
  }
}

export function toToolResult(payload: unknown) {
  const text = typeof payload === "string" ? payload : JSON.stringify(payload, null, 2);
  return { content: [{ type: "text" as const, text }], details: payload };
}

export async function callJsonTool(
  bridge: BridgeLike,
  name: string,
  args: Record<string, unknown>,
): Promise<Record<string, unknown> | null> {
  const raw = await bridge.callTool(name, args);
  const json = extractJsonFromMcpResult(raw);
  return json && typeof json === "object" ? (json as Record<string, unknown>) : null;
}

export async function buildBrandGenContext(
  bridge: BridgeLike,
  config: PluginConfig,
  options: { toolNames?: string[] } = {},
): Promise<BrandContext> {
  const state = resolveActiveWorkspace(config.brandGenDir);
  const availableTools =
    options.toolNames ??
    (bridge.isReady() ? (await bridge.listTools()).map((tool) => tool.name) : []);
  const toolSet = new Set(availableTools);

  const remoteContextSnapshot =
    bridge.isReady() && toolSet.has("brand_context_snapshot")
      ? await callJsonTool(bridge, "brand_context_snapshot", { format: "json" }).catch(() => null)
      : null;
  const remoteWorkspaceStatus =
    bridge.isReady() && toolSet.has("brand_workspace_status")
      ? await callJsonTool(bridge, "brand_workspace_status", { format: "json" }).catch(() => null)
      : null;
  const remoteCapabilities =
    bridge.isReady() && toolSet.has("brand_capabilities")
      ? await callJsonTool(bridge, "brand_capabilities", { format: "json" }).catch(() => null)
      : null;

  const identityPath =
    (state.workspaceIdentityPath && readJsonFile<Record<string, unknown>>(state.workspaceIdentityPath)
      ? state.workspaceIdentityPath
      : null) ??
    state.savedIdentityPath;
  const identity = identityPath ? readJsonFile<Record<string, unknown>>(identityPath) : null;
  const blackboard =
    bridge.isReady() && state.workspaceDir
      ? (await callJsonTool(bridge, "brand_show_blackboard", { format: "json" }).catch(
          () => null,
        )) ?? null
      : null;
  const iterationMemory =
    bridge.isReady() && state.workspaceDir
      ? (await callJsonTool(bridge, "brand_show_iteration_memory", { format: "json" }).catch(
          () => null,
        )) ?? null
      : null;
  const learnings =
    (state.workspaceDir ? loadLearnings(state.workspaceDir) : null) ??
    (state.savedBrandDir && state.savedBrandDir !== state.workspaceDir
      ? loadLearnings(state.savedBrandDir)
      : null) ??
    (state.activeBrand ? defaultLearnings(state.activeBrand) : null);
  const workspaceJournal =
    state.workspaceDir && state.activeBrand
      ? getRecentEntries(state.workspaceDir, state.activeBrand, 10)
      : [];
  const recentJournal =
    workspaceJournal.length
      ? workspaceJournal
      : state.savedBrandDir && state.savedBrandDir !== state.workspaceDir && state.activeBrand
        ? getRecentEntries(state.savedBrandDir, state.activeBrand, 10)
        : workspaceJournal;
  return {
    brandGenDir: state.brandGenDir,
    workspaceKind: state.workspaceKind,
    activeBrand: state.activeBrand,
    activeSession: state.activeSession,
    workspaceDir: state.workspaceDir,
    workspaceIdentityPath: identityPath,
    identity,
    blackboard,
    iterationMemory,
    learnings,
    recentJournal,
    availableTools,
    contextSnapshot: remoteContextSnapshot,
    workspaceStatus: remoteWorkspaceStatus,
    capabilities: remoteCapabilities,
  };
}

export function summarizeContext(context: BrandContext): string {
  const identityName =
    (context.identity?.brand as any)?.name ?? context.activeBrand ?? "unknown";
  const messaging =
    (context.identity?.messaging as Record<string, unknown> | undefined) ?? {};
  const decisions = Array.isArray(context.blackboard?.decisions)
    ? (context.blackboard!.decisions as Array<Record<string, unknown>>)
    : [];
  const copyNotes = Array.isArray(context.iterationMemory?.copy_notes)
    ? (context.iterationMemory!.copy_notes as string[])
    : [];
  const messagingNotes = Array.isArray(context.iterationMemory?.messaging_notes)
    ? (context.iterationMemory!.messaging_notes as string[])
    : [];
  const learnings = context.learnings ?? null;

  return [
    "## BRAND_GEN_CONTEXT",
    `Resolved root: ${context.brandGenDir}`,
    `Workspace kind: ${context.workspaceKind}`,
    `Active brand: ${identityName}`,
    context.activeSession
      ? `Active session: ${context.activeSession}`
      : "Active session: none",
    context.workspaceIdentityPath ? `Workspace identity: ${context.workspaceIdentityPath}` : null,
    messaging.tagline ? `Tagline: ${messaging.tagline}` : null,
    messaging.elevator
      ? `Elevator: ${String(messaging.elevator).slice(0, 240)}`
      : null,
    messaging.voice &&
    typeof messaging.voice === "object" &&
    (messaging.voice as any).description
      ? `Voice: ${(messaging.voice as any).description}`
      : null,
    decisions.length
      ? `Recent decisions: ${JSON.stringify(decisions.slice(-3), null, 2)}`
      : null,
    copyNotes.length
      ? `Copy notes: ${copyNotes.slice(-5).join(" | ")}`
      : null,
    messagingNotes.length
      ? `Messaging notes: ${messagingNotes.slice(-5).join(" | ")}`
      : null,
    learnings ? `Learnings: ${JSON.stringify(learnings, null, 2)}` : null,
    context.workspaceStatus ? `Workspace status: ${JSON.stringify(context.workspaceStatus, null, 2)}` : null,
    context.capabilities ? `Capabilities: ${JSON.stringify(context.capabilities, null, 2)}` : null,
    context.recentJournal.length
      ? `Recent journal: ${JSON.stringify(context.recentJournal.slice(0, 5), null, 2)}`
      : null,
    context.availableTools.length
      ? `Available MCP tools: ${context.availableTools.join(", ")}`
      : null,
  ]
    .filter(Boolean)
    .join("\n\n");
}

export function isHeartbeatPrompt(prompt: string): boolean {
  return /brand gen heartbeat|brand_heartbeat|brand generation cycle/i.test(prompt);
}
