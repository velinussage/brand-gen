import { randomUUID } from "node:crypto";
import { existsSync, readFileSync } from "node:fs";
import { homedir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { McpBridge } from "./mcp-bridge.ts";
import {
  appendJournal,
  completeJournal,
  defaultLearnings,
  failJournal,
  getOrphanedEntries,
  getInProgressEntries,
  getJournalStats,
  getRecentEntries,
  initMemory,
  loadLearnings,
  patchLearnings,
  rateJournalEntry,
  type BrandLearnings,
  type JournalEntry,
} from "./memory.ts";

const __dirnameCompat = dirname(fileURLToPath(import.meta.url));
const PKG_VERSION: string = (() => {
  try {
    const pkg = JSON.parse(readFileSync(resolve(__dirnameCompat, "..", "package.json"), "utf8"));
    return typeof pkg.version === "string" ? pkg.version : "0.0.0";
  } catch {
    return "0.0.0";
  }
})();

const Type = {
  String: (options: Record<string, unknown> = {}) => ({ type: "string", ...options }),
  Number: (options: Record<string, unknown> = {}) => ({ type: "number", ...options }),
  Boolean: (options: Record<string, unknown> = {}) => ({ type: "boolean", ...options }),
  Unknown: () => ({}),
  Optional: (schema: Record<string, unknown>) => ({ ...schema, __optional: true }),
  Record: (_key: unknown, value: Record<string, unknown>, options: Record<string, unknown> = {}) => ({ type: "object", additionalProperties: value, ...options }),
  Array: (items: Record<string, unknown>, options: Record<string, unknown> = {}) => ({ type: "array", items, ...options }),
  Object: (properties: Record<string, Record<string, unknown>>, options: Record<string, unknown> = {}) => {
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

type PluginConfig = {
  brandGenDir: string;
  brandIterateMcpPath: string;
  approvalMode: "all" | "output_only" | "none";
  logLevel: "debug" | "info" | "warn" | "error";
};

type BrandGenConfig = {
  active?: string | null;
  activeSession?: string | null;
  version?: number;
  inspirationMode?: boolean;
};

type ActiveWorkspace = {
  brandGenDir: string;
  activeBrand: string | null;
  activeSession: string | null;
  workspaceDir: string | null;
  savedBrandDir: string | null;
  savedIdentityPath: string | null;
  workspaceIdentityPath: string | null;
};

type BrandContext = {
  activeBrand: string | null;
  activeSession: string | null;
  workspaceDir: string | null;
  identity: Record<string, unknown> | null;
  blackboard: Record<string, unknown> | null;
  iterationMemory: Record<string, unknown> | null;
  learnings: BrandLearnings | null;
  recentJournal: JournalEntry[];
  availableTools: string[];
};

type BridgeLike = Pick<McpBridge, "isReady" | "callTool" | "listTools">;

let brandBridge: McpBridge | null = null;
let discoveredToolCount = 0;
let pluginConfigState: PluginConfig | null = null;
let heartbeatTimer: NodeJS.Timeout | null = null;
let heartbeatRunPromise: Promise<Record<string, unknown>> | null = null;
let healthStatus: "ok" | "degraded" = "ok";
let heartbeatFailures = 0;

const HEARTBEAT_INTERVAL_MS = 60 * 60_000;
const HEARTBEAT_CYCLE_TIMEOUT_MS = 15 * 60_000;
const DISCOVER_TIMEOUT_MS = 5 * 60_000;
const GENERATE_TIMEOUT_MS = 10 * 60_000;
const ORPHAN_MINUTES = 10;

const GOAL_CATALOG = [
  {
    goal: "Explain what the brand/product is clearly",
    purpose: "social introduction",
    targetSurface: "X feed",
  },
  {
    goal: "Show product truth with stronger branding",
    purpose: "product-led promotion",
    targetSurface: "web hero",
  },
  {
    goal: "Create a social asset with real brand language",
    purpose: "social promo",
    targetSurface: "social promo",
  },
] as const;

const MATERIAL_ROTATION = ["x-feed", "browser-illustration", "product-banner"] as const;
function expandHome(value: string): string {
  if (!value) return value;
  if (value === "~") return homedir();
  if (value.startsWith("~/")) return join(homedir(), value.slice(2));
  return value;
}

function readJsonFile<T>(path: string): T | null {
  try {
    if (!existsSync(path)) return null;
    return JSON.parse(readFileSync(path, "utf8")) as T;
  } catch {
    return null;
  }
}

function parsePluginConfig(raw: Record<string, unknown> | undefined): PluginConfig {
  const brandGenDir = expandHome(
    typeof raw?.brandGenDir === "string" && raw.brandGenDir.trim() ? raw.brandGenDir : "~/.brand-gen",
  );
  const brandIterateMcpPath = expandHome(
    typeof raw?.brandIterateMcpPath === "string" ? raw.brandIterateMcpPath : "",
  );
  return {
    brandGenDir,
    brandIterateMcpPath,
    approvalMode:
      raw?.approvalMode === "all" || raw?.approvalMode === "none" ? raw.approvalMode : "output_only",
    logLevel:
      raw?.logLevel === "debug" || raw?.logLevel === "warn" || raw?.logLevel === "error"
        ? raw.logLevel
        : "info",
  };
}

function loadBrandGenConfig(brandGenDir: string): BrandGenConfig {
  return readJsonFile<BrandGenConfig>(join(brandGenDir, "config.json")) ?? {};
}

function deriveBrandFromWorkspace(workspaceDir: string, config: BrandGenConfig): string | null {
  const identity = readJsonFile<Record<string, unknown>>(join(workspaceDir, "brand-identity.json"));
  const profile = readJsonFile<Record<string, unknown>>(join(workspaceDir, "brand-profile.json"));
  const candidates = [identity, profile];
  for (const candidate of candidates) {
    const sessionContext = candidate?.session_context;
    if (sessionContext && typeof sessionContext === "object") {
      const seeded = (sessionContext as Record<string, unknown>).seeded_from_brand;
      if (typeof seeded === "string" && seeded.trim()) return seeded.trim();
    }
  }
  if (typeof config.active === "string" && config.active.trim()) return config.active.trim();
  return null;
}

function resolveActiveWorkspace(brandGenDir: string, config = loadBrandGenConfig(brandGenDir)): ActiveWorkspace {
  const activeSession = typeof config.activeSession === "string" && config.activeSession.trim() ? config.activeSession.trim() : null;
  const active = typeof config.active === "string" && config.active.trim() ? config.active.trim() : null;

  if (activeSession) {
    const workspaceDir = join(brandGenDir, "sessions", activeSession, "brand-materials");
    if (existsSync(workspaceDir)) {
      const activeBrand = deriveBrandFromWorkspace(workspaceDir, config) ?? active;
      const savedBrandDir = activeBrand ? join(brandGenDir, "brands", activeBrand) : null;
      return {
        brandGenDir,
        activeBrand,
        activeSession,
        workspaceDir,
        savedBrandDir,
        savedIdentityPath: savedBrandDir ? join(savedBrandDir, "brand-identity.json") : null,
        workspaceIdentityPath: join(workspaceDir, "brand-identity.json"),
      };
    }
  }

  if (active) {
    const workspaceDir = join(brandGenDir, "brands", active);
    if (existsSync(workspaceDir)) {
      return {
        brandGenDir,
        activeBrand: active,
        activeSession: null,
        workspaceDir,
        savedBrandDir: workspaceDir,
        savedIdentityPath: join(workspaceDir, "brand-identity.json"),
        workspaceIdentityPath: join(workspaceDir, "brand-identity.json"),
      };
    }
  }

  const envWorkspace = process.env.BRAND_DIR ? resolve(expandHome(process.env.BRAND_DIR)) : null;
  if (envWorkspace && existsSync(envWorkspace)) {
    const activeBrand = deriveBrandFromWorkspace(envWorkspace, config) ?? active;
    const savedBrandDir = activeBrand ? join(brandGenDir, "brands", activeBrand) : null;
    return {
      brandGenDir,
      activeBrand,
      activeSession,
      workspaceDir: envWorkspace,
      savedBrandDir,
      savedIdentityPath: savedBrandDir ? join(savedBrandDir, "brand-identity.json") : null,
      workspaceIdentityPath: join(envWorkspace, "brand-identity.json"),
    };
  }

  return {
    brandGenDir,
    activeBrand: active,
    activeSession,
    workspaceDir: null,
    savedBrandDir: active ? join(brandGenDir, "brands", active) : null,
    savedIdentityPath: active ? join(brandGenDir, "brands", active, "brand-identity.json") : null,
    workspaceIdentityPath: null,
  };
}

function extractJsonFromMcpResult(result: unknown): unknown {
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

function toToolResult(payload: unknown) {
  const text = typeof payload === "string" ? payload : JSON.stringify(payload, null, 2);
  return { content: [{ type: "text" as const, text }], details: payload };
}

async function callJsonTool(
  bridge: BridgeLike,
  name: string,
  args: Record<string, unknown>,
): Promise<Record<string, unknown> | null> {
  const raw = await bridge.callTool(name, args);
  const json = extractJsonFromMcpResult(raw);
  return json && typeof json === "object" ? (json as Record<string, unknown>) : null;
}

async function buildBrandGenContext(
  bridge: BridgeLike,
  config: PluginConfig,
  options: { toolNames?: string[] } = {},
): Promise<BrandContext> {
  const state = resolveActiveWorkspace(config.brandGenDir);
  const identity = state.savedIdentityPath
    ? readJsonFile<Record<string, unknown>>(state.savedIdentityPath)
    : null;
  const blackboard = bridge.isReady() && state.workspaceDir
    ? await callJsonTool(bridge, "brand_show_blackboard", { format: "json" }).catch(() => null)
    : null;
  const iterationMemory = bridge.isReady() && state.workspaceDir
    ? await callJsonTool(bridge, "brand_show_iteration_memory", { format: "json" }).catch(() => null)
    : null;
  const learnings = state.savedBrandDir
    ? loadLearnings(state.savedBrandDir) ?? (state.activeBrand ? defaultLearnings(state.activeBrand) : null)
    : null;
  let recentJournal: JournalEntry[] = [];
  if (state.savedBrandDir && state.activeBrand) {
    const db = initMemory(state.savedBrandDir, state.activeBrand);
    try {
      recentJournal = getRecentEntries(db, state.activeBrand, 10);
    } finally {
      db.close();
    }
  }
  const toolNames = options.toolNames ?? (bridge.isReady() ? (await bridge.listTools()).map((tool) => tool.name) : []);

  return {
    activeBrand: state.activeBrand,
    activeSession: state.activeSession,
    workspaceDir: state.workspaceDir,
    identity,
    blackboard,
    iterationMemory,
    learnings,
    recentJournal,
    availableTools: toolNames,
  };
}

function summarizeContext(context: BrandContext): string {
  const identityName = (context.identity?.brand as any)?.name ?? context.activeBrand ?? "unknown";
  const messaging = (context.identity?.messaging as Record<string, unknown> | undefined) ?? {};
  const decisions = Array.isArray(context.blackboard?.decisions) ? context.blackboard!.decisions as Array<Record<string, unknown>> : [];
  const copyNotes = Array.isArray(context.iterationMemory?.copy_notes) ? context.iterationMemory!.copy_notes as string[] : [];
  const messagingNotes = Array.isArray(context.iterationMemory?.messaging_notes) ? context.iterationMemory!.messaging_notes as string[] : [];
  const learnings = context.learnings ?? null;

  return [
    "## BRAND_GEN_CONTEXT",
    `Active brand: ${identityName}`,
    context.activeSession ? `Active session: ${context.activeSession}` : "Active session: none",
    messaging.tagline ? `Tagline: ${messaging.tagline}` : null,
    messaging.elevator ? `Elevator: ${String(messaging.elevator).slice(0, 240)}` : null,
    messaging.voice && typeof messaging.voice === "object" && (messaging.voice as any).description
      ? `Voice: ${(messaging.voice as any).description}`
      : null,
    decisions.length ? `Recent decisions: ${JSON.stringify(decisions.slice(-3), null, 2)}` : null,
    copyNotes.length ? `Copy notes: ${copyNotes.slice(-5).join(" | ")}` : null,
    messagingNotes.length ? `Messaging notes: ${messagingNotes.slice(-5).join(" | ")}` : null,
    learnings ? `Learnings: ${JSON.stringify(learnings, null, 2)}` : null,
    context.recentJournal.length ? `Recent journal: ${JSON.stringify(context.recentJournal.slice(0, 5), null, 2)}` : null,
    context.availableTools.length ? `Available MCP tools: ${context.availableTools.join(", ")}` : null,
  ]
    .filter(Boolean)
    .join("\n\n");
}

function isHeartbeatPrompt(prompt: string): boolean {
  return /brand gen heartbeat|brand_heartbeat|brand generation cycle/i.test(prompt);
}

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

function mapGenerateParams(params: Record<string, unknown>): Record<string, unknown> {
  return {
    material_type: params.materialType,
    goal: params.goal,
    purpose: params.purpose,
    target_surface: params.targetSurface,
    mode: params.mode ?? "hybrid",
    prompt_seed: params.promptSeed,
    max_iterations: params.maxIterations ?? 1,
  };
}

function loadBrandIdentitySummary(identity: Record<string, unknown> | null): {
  brandName: string;
  business: string;
  audience: string;
  tone: string;
  productContext: string;
} {
  const brand = (identity?.brand as Record<string, unknown> | undefined) ?? {};
  const identityCore = (identity?.identity_core as Record<string, unknown> | undefined) ?? {};
  const messaging = (identity?.messaging as Record<string, unknown> | undefined) ?? {};
  const toneWords = Array.isArray(identityCore.tone_words)
    ? (identityCore.tone_words as string[]).slice(0, 6).join(", ")
    : "";
  const audience =
    Array.isArray(messaging.audiences) && messaging.audiences.length
      ? (messaging.audiences as string[]).join(", ")
      : "builders, product teams, and AI-agent operators";
  const productContext = [
    typeof messaging.elevator === "string" ? messaging.elevator : "",
    Array.isArray(messaging.value_propositions)
      ? (messaging.value_propositions as string[]).slice(0, 2).join(" | ")
      : "",
  ]
    .filter(Boolean)
    .join(" ");
  return {
    brandName: typeof brand.name === "string" ? brand.name : "Brand",
    business:
      typeof brand.summary === "string" && brand.summary.trim()
        ? brand.summary
        : typeof messaging.elevator === "string"
          ? messaging.elevator
          : "",
    audience,
    tone: toneWords,
    productContext,
  };
}

function average(values: number[]): number | null {
  if (!values.length) return null;
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

function isReviewableOutputEntry(entry: JournalEntry): boolean {
  return (
    entry.status === "complete" &&
    entry.materialType !== "discover" &&
    entry.materialType !== "heartbeat-cycle" &&
    (Boolean(entry.outputPath) || Boolean(entry.versionId))
  );
}

function getPendingOutputReviews(entries: JournalEntry[]): JournalEntry[] {
  return entries.filter((entry) => isReviewableOutputEntry(entry) && entry.rating == null);
}

function deriveGenerationPolicy(entries: JournalEntry[], approvalMode: PluginConfig["approvalMode"]): {
  skip: boolean;
  reason?: string;
  materialType?: (typeof MATERIAL_ROTATION)[number];
  goal?: (typeof GOAL_CATALOG)[number]["goal"];
  purpose?: string;
  targetSurface?: string;
} {
  const recent = entries.slice(0, 10);
  const pendingOutputReviews = getPendingOutputReviews(recent);
  const lastThreeRated = recent
    .slice(0, 3)
    .map((entry) => entry.rating)
    .filter((rating): rating is number => typeof rating === "number");
  const lastTwo = recent.slice(0, 2);
  const lastThree = recent.slice(0, 3);

  if (approvalMode === "all") {
    const pendingReview = pendingOutputReviews[0];
    if (pendingReview) {
      return { skip: true, reason: `Waiting for output rating on ${pendingReview.id}` };
    }
  }

  if (lastThreeRated.length === 3 && (average(lastThreeRated) ?? 0) < 3) {
    return { skip: true, reason: "Last 3 rated entries average below 3" };
  }

  if (
    lastTwo.length === 2 &&
    lastTwo.every((entry) => entry.status === "failed")
  ) {
    return { skip: true, reason: "Last 2 generations failed" };
  }

  if (
    lastThree.length === 3 &&
    lastThree.every((entry) => typeof entry.rating === "number" && entry.rating <= 2)
  ) {
    return { skip: true, reason: "Last 3 ratings are all 0-2" };
  }

  const recentWithOutput = recent.filter((entry) => entry.status === "complete" && entry.outputPath);
  let materialType: (typeof MATERIAL_ROTATION)[number] = "x-feed";
  if (!recentWithOutput.some((entry) => entry.materialType === "x-feed")) {
    materialType = "x-feed";
  } else if (!recentWithOutput.some((entry) => entry.materialType === "browser-illustration")) {
    materialType = "browser-illustration";
  } else {
    const lastRotationType = recentWithOutput.find((entry) =>
      MATERIAL_ROTATION.includes(entry.materialType as (typeof MATERIAL_ROTATION)[number]),
    )?.materialType as (typeof MATERIAL_ROTATION)[number] | undefined;
    const lastIndex = lastRotationType ? MATERIAL_ROTATION.indexOf(lastRotationType) : -1;
    materialType = MATERIAL_ROTATION[(lastIndex + 1) % MATERIAL_ROTATION.length];
  }

  const recentFive = recent.slice(0, 5);
  const goalUsage = new Map<string, number>();
  for (const option of GOAL_CATALOG) goalUsage.set(option.goal, 0);
  for (const entry of recentFive) {
    if (entry.goal && goalUsage.has(entry.goal)) {
      goalUsage.set(entry.goal, (goalUsage.get(entry.goal) ?? 0) + 1);
    }
  }
  const candidateGoals = [...GOAL_CATALOG].sort(
    (a, b) => (goalUsage.get(a.goal) ?? 0) - (goalUsage.get(b.goal) ?? 0),
  );
  const recentCombos = new Set(
    recent.slice(0, 3).map((entry) => `${entry.materialType ?? ""}::${entry.goal ?? ""}`),
  );
  const selected =
    candidateGoals.find((option) => !recentCombos.has(`${materialType}::${option.goal}`)) ??
    candidateGoals[0];

  return {
    skip: false,
    materialType,
    goal: selected.goal,
    purpose: selected.purpose,
    targetSurface: selected.targetSurface,
  };
}

function withTimeout<T>(promise: Promise<T>, timeoutMs: number, label: string): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error(`${label} timed out after ${timeoutMs}ms`)), timeoutMs);
    promise.then(
      (value) => {
        clearTimeout(timer);
        resolve(value);
      },
      (error) => {
        clearTimeout(timer);
        reject(error);
      },
    );
  });
}

async function runDiscoverStep(
  bridge: BridgeLike,
  state: ActiveWorkspace,
  identity: Record<string, unknown> | null,
  recentEntries: JournalEntry[],
): Promise<Record<string, unknown>> {
  if (!state.activeBrand || !state.savedBrandDir) {
    return { skipped: true, reason: "No active brand" };
  }
  const inspirations =
    readJsonFile<{ sources?: string[] }>(join(state.savedBrandDir, "inspirations.json")) ?? {};
  const allSources = Array.isArray(inspirations.sources) ? inspirations.sources : [];
  if (!allSources.length) return { skipped: true, reason: "No inspiration sources configured" };

  const rejectedSources = new Set(
    recentEntries
      .filter((entry) => entry.materialType === "discover" && entry.rating === 0 && entry.feedback)
      .flatMap((entry) =>
        entry.feedback!
          .split(",")
          .map((item) => item.trim())
          .filter(Boolean),
      ),
  );
  const chosenSources = allSources.filter((source) => !rejectedSources.has(source)).slice(0, 3);
  if (!chosenSources.length) return { skipped: true, reason: "All inspiration sources were rejected recently" };

  const summary = loadBrandIdentitySummary(identity);
  const raw = await withTimeout(
    bridge.callTool("brand_explore", {
      brand_name: summary.brandName,
      business: summary.business,
      audience: summary.audience,
      tone: summary.tone,
      product_context: summary.productContext,
      materials: [...MATERIAL_ROTATION],
      sources: chosenSources,
      top: chosenSources.length,
    }),
    DISCOVER_TIMEOUT_MS,
    "Discover step",
  );
  const result = (extractJsonFromMcpResult(raw) as Record<string, unknown> | undefined) ?? {};

  const db = initMemory(state.savedBrandDir, state.activeBrand);
  try {
    appendJournal(db, {
      id: randomUUID(),
      brand: state.activeBrand,
      materialType: "discover",
      prompt: summary.business,
      inspirationSources: chosenSources,
      status: "complete",
      feedback: chosenSources.join(","),
      critique: result,
      createdAt: new Date().toISOString(),
    });
  } finally {
    db.close();
  }

  return { skipped: false, sources: chosenSources, result };
}

async function runGenerateStep(
  bridge: BridgeLike,
  config: PluginConfig,
  state: ActiveWorkspace,
  identity: Record<string, unknown> | null,
): Promise<Record<string, unknown>> {
  if (!state.activeBrand || !state.savedBrandDir) {
    return { skipped: true, reason: "No active saved brand could be resolved" };
  }
  if (!state.workspaceDir || !identity) {
    return { skipped: true, reason: "Active workspace or brand identity missing" };
  }

  const db = initMemory(state.savedBrandDir, state.activeBrand);
  try {
    for (const orphan of getOrphanedEntries(db, ORPHAN_MINUTES)) {
      failJournal(db, orphan.id, "Marked failed by heartbeat orphan cleanup", orphan.stoppedAt ?? "generate");
    }
    if (getInProgressEntries(db, state.activeBrand).length) {
      return { skipped: true, reason: "Generation already in progress" };
    }

    const entries = getRecentEntries(db, state.activeBrand, 10);
    const policy = deriveGenerationPolicy(entries, config.approvalMode);
    if (policy.skip || !policy.materialType || !policy.goal || !policy.purpose || !policy.targetSurface) {
      return { skipped: true, reason: policy.reason ?? "Generation policy skipped" };
    }

    const payload = {
      materialType: policy.materialType,
      goal: policy.goal,
      purpose: policy.purpose,
      targetSurface: policy.targetSurface,
      mode: "hybrid",
      maxIterations: 1,
      promptSeed:
        typeof (identity?.messaging as Record<string, unknown> | undefined)?.tagline === "string"
          ? String((identity!.messaging as Record<string, unknown>).tagline)
          : undefined,
    };
    const generated = await withTimeout(runGenerateAction(bridge, config, payload), GENERATE_TIMEOUT_MS, "Generate step");
    return { skipped: false, payload, result: generated };
  } finally {
    db.close();
  }
}

async function runHeartbeatCycle(
  bridge: BridgeLike,
  config: PluginConfig,
): Promise<Record<string, unknown>> {
  const state = resolveActiveWorkspace(config.brandGenDir);
  const identity = state.savedIdentityPath
    ? readJsonFile<Record<string, unknown>>(state.savedIdentityPath)
    : null;
  const summary: Record<string, unknown> = {
    startedAt: new Date().toISOString(),
    activeBrand: state.activeBrand,
    activeSession: state.activeSession,
    discover: null,
    generate: null,
  };

  if (!state.activeBrand || !state.savedBrandDir) {
    summary.skipped = true;
    summary.reason = "No active brand configured";
    return summary;
  }

  const db = initMemory(state.savedBrandDir, state.activeBrand);
  let recentEntries: JournalEntry[] = [];
  try {
    recentEntries = getRecentEntries(db, state.activeBrand, 20);
  } finally {
    db.close();
  }

  summary.discover = await runDiscoverStep(bridge, state, identity, recentEntries);
  summary.generate = await runGenerateStep(bridge, config, state, identity);
  summary.completedAt = new Date().toISOString();
  const summaryDb = initMemory(state.savedBrandDir, state.activeBrand);
  try {
    appendJournal(summaryDb, {
      id: randomUUID(),
      brand: state.activeBrand,
      materialType: "heartbeat-cycle",
      status: "complete",
      feedback: JSON.stringify({
        discoverSkipped: (summary.discover as Record<string, unknown>)?.skipped ?? null,
        generateSkipped: (summary.generate as Record<string, unknown>)?.skipped ?? null,
      }),
      critique: summary,
      createdAt: new Date().toISOString(),
    });
  } finally {
    summaryDb.close();
  }
  return summary;
}

function scheduleHeartbeat(api: PluginApi): void {
  if (heartbeatTimer) clearInterval(heartbeatTimer);
  heartbeatTimer = setInterval(() => {
    if (!brandBridge || !pluginConfigState) return;
    void triggerHeartbeat(api, "timer");
  }, HEARTBEAT_INTERVAL_MS);
}

async function triggerHeartbeat(api: PluginApi, trigger: "timer" | "prompt"): Promise<Record<string, unknown>> {
  if (!brandBridge || !pluginConfigState) {
    return { skipped: true, reason: "Plugin not configured" };
  }
  if (!brandBridge.isReady()) {
    healthStatus = "degraded";
    heartbeatFailures += 1;
    return { skipped: true, reason: "MCP bridge not ready" };
  }
  if (heartbeatRunPromise) {
    return { skipped: true, reason: "Heartbeat already running" };
  }

  heartbeatRunPromise = withTimeout(
    runHeartbeatCycle(brandBridge, pluginConfigState),
    HEARTBEAT_CYCLE_TIMEOUT_MS,
    "Heartbeat cycle",
  );

  try {
    const result = await heartbeatRunPromise;
    heartbeatFailures = 0;
    healthStatus = "ok";
    api.logger.info(`[brand-heartbeat:${trigger}] ${JSON.stringify(result)}`);
    return result;
  } catch (error) {
    heartbeatFailures += 1;
    if (heartbeatFailures >= 2) healthStatus = "degraded";
    const message = error instanceof Error ? error.message : String(error);
    api.logger.error(`[brand-heartbeat:${trigger}] ${message}`);
    return { skipped: false, error: message };
  } finally {
    heartbeatRunPromise = null;
  }
}

async function runGenerateAction(
  bridge: BridgeLike,
  config: PluginConfig,
  params: Record<string, unknown>,
): Promise<Record<string, unknown>> {
  const state = resolveActiveWorkspace(config.brandGenDir);
  if (!state.activeBrand || !state.savedBrandDir) {
    throw new Error("No active saved brand could be resolved for journal storage.");
  }
  const db = initMemory(state.savedBrandDir, state.activeBrand);
  const journalId = randomUUID();
  const entry: JournalEntry = {
    id: journalId,
    brand: state.activeBrand,
    materialType: typeof params.materialType === "string" ? params.materialType : undefined,
    goal: typeof params.goal === "string" ? params.goal : undefined,
    purpose: typeof params.purpose === "string" ? params.purpose : undefined,
    targetSurface: typeof params.targetSurface === "string" ? params.targetSurface : undefined,
    prompt: typeof params.promptSeed === "string" ? params.promptSeed : undefined,
    status: "in_progress",
    createdAt: new Date().toISOString(),
  };
  appendJournal(db, entry);
  try {
    const payload = mapGenerateParams(params);
    const raw = await bridge.callTool("brand_pipeline", payload);
    const json = extractJsonFromMcpResult(raw) as Record<string, unknown> | undefined;
    if (!json) throw new Error("brand_pipeline returned no JSON payload");
    completeJournal(db, journalId, json as any);
    const versionId =
      json.result && typeof json.result === "object"
        ? (json.result as Record<string, unknown>).version_id
        : undefined;
    if (versionId && typeof versionId === "string") {
      try {
        const reviewRaw = await bridge.callTool("brand_review", { version: versionId, open: false });
        const reviewJson = extractJsonFromMcpResult(reviewRaw);
        if (reviewJson && typeof reviewJson === "object") {
          db.prepare(`UPDATE journal SET critique = ? WHERE id = ?`).run(JSON.stringify(reviewJson), journalId);
        }
      } catch {
        // best effort only
      }
    }
    return { journalId, ...json };
  } catch (err) {
    failJournal(db, journalId, err instanceof Error ? err.message : String(err), "generate");
    throw err;
  } finally {
    db.close();
  }
}

function createBrandSearchTool() {
  return {
    name: "brand_search",
    label: "Brand Gen: search",
    description: "Read-only brand-gen plugin queries: MCP tools, learnings, journal stats, and recent entries.",
    parameters: Type.Object({
      action: Type.String(),
      params: Type.Optional(Type.Record(Type.String(), Type.Unknown())),
    }),
    execute: async (_toolCallId: string, params: Record<string, unknown>) => {
      try {
        const action = String(params.action ?? "");
        const p = params.params && typeof params.params === "object" ? (params.params as Record<string, unknown>) : {};
        const config = pluginConfigState;
        if (!config) throw new Error("Plugin is not configured yet.");
        const state = resolveActiveWorkspace(config.brandGenDir);
        const db = state.savedBrandDir && state.activeBrand ? initMemory(state.savedBrandDir, state.activeBrand) : null;
        try {
          if (action === "list_tools") {
            const tools = brandBridge?.isReady() ? await brandBridge.listTools() : [];
            return toToolResult({ tools });
          }
          if (action === "get_learnings") {
            return toToolResult({ learnings: state.savedBrandDir ? loadLearnings(state.savedBrandDir) : null });
          }
          if (action === "get_recent_entries") {
            const limit = typeof p.limit === "number" ? p.limit : 10;
            return toToolResult({ entries: db && state.activeBrand ? getRecentEntries(db, state.activeBrand, limit) : [] });
          }
          if (action === "get_journal_stats") {
            return toToolResult({ stats: db && state.activeBrand ? getJournalStats(db, state.activeBrand) : null });
          }
          if (action === "get_pending_reviews") {
            return toToolResult({
              entries: db && state.activeBrand ? getPendingOutputReviews(getRecentEntries(db, state.activeBrand, 25)) : [],
            });
          }
          if (action === "get_context") {
            const context = brandBridge ? await buildBrandGenContext(brandBridge, config) : null;
            return toToolResult({ context });
          }
          return toToolResult({ error: `Unknown brand_search action: ${action}` });
        } finally {
          db?.close();
        }
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
    description: "Mutating brand-gen plugin actions: generate, switch_brand, patch_learnings, and rate journal outputs.",
    parameters: Type.Object({
      action: Type.String(),
      params: Type.Optional(Type.Record(Type.String(), Type.Unknown())),
    }),
    execute: async (_toolCallId: string, params: Record<string, unknown>) => {
      try {
        const action = String(params.action ?? "");
        const p = params.params && typeof params.params === "object" ? (params.params as Record<string, unknown>) : {};
        const config = pluginConfigState;
        if (!config) throw new Error("Plugin is not configured yet.");
        if (!brandBridge?.isReady()) throw new Error("brand-gen MCP bridge is not connected.");
        const state = resolveActiveWorkspace(config.brandGenDir);
        if (action === "switch_brand") {
          const brand = String(p.brand ?? "").trim();
          if (!brand) throw new Error("switch_brand requires params.brand");
          const raw = await brandBridge.callTool("brand_use", { brand });
          return toToolResult({ result: extractJsonFromMcpResult(raw) ?? raw });
        }
        if (action === "patch_learnings") {
          if (!state.savedBrandDir) throw new Error("No active saved brand directory resolved.");
          const path = String(p.path ?? "").trim();
          if (!path) throw new Error("patch_learnings requires params.path");
          const learnings = patchLearnings(state.savedBrandDir, path, p.value);
          return toToolResult({ learnings });
        }
        if (action === "rate") {
          if (!state.savedBrandDir || !state.activeBrand) throw new Error("No active brand for journal updates.");
          const id = String(p.id ?? "").trim();
          const rating = Number(p.rating);
          if (!id) throw new Error("rate requires params.id");
          if (!Number.isInteger(rating) || rating < 0 || rating > 5) throw new Error("rating must be an integer 0-5");
          const db = initMemory(state.savedBrandDir, state.activeBrand);
          try {
            rateJournalEntry(db, id, rating, typeof p.feedback === "string" ? p.feedback : undefined);
            return toToolResult({ ok: true, id, rating });
          } finally {
            db.close();
          }
        }
        if (action === "generate") {
          const required = ["materialType", "goal", "purpose", "targetSurface"];
          const missing = required.filter((key) => typeof p[key] !== "string" || !String(p[key]).trim());
          if (missing.length) throw new Error(`generate missing required params: ${missing.join(", ")}`);
          const result = await runGenerateAction(brandBridge, config, p);
          return toToolResult(result);
        }
        return toToolResult({ error: `Unknown brand_execute action: ${action}` });
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
    description: "Check brand-gen plugin health: MCP bridge state, active brand/session, and memory stats.",
    parameters: Type.Object({}),
    execute: async () => {
      const config = pluginConfigState;
      if (!config) return toToolResult({ pluginVersion: PKG_VERSION, configured: false });
      const state = resolveActiveWorkspace(config.brandGenDir);
      const db = state.savedBrandDir && state.activeBrand ? initMemory(state.savedBrandDir, state.activeBrand) : null;
      try {
        const status = {
          pluginVersion: PKG_VERSION,
          configured: true,
          bridgeConnected: brandBridge?.isReady() ?? false,
          discoveredToolCount,
          activeBrand: state.activeBrand,
          activeSession: state.activeSession,
          workspaceDir: state.workspaceDir,
          savedBrandDir: state.savedBrandDir,
          approvalMode: config.approvalMode,
          healthStatus: brandBridge?.isReady() ? healthStatus : "degraded",
          heartbeatRunning: Boolean(heartbeatRunPromise),
          heartbeatFailures,
          journalStats: db && state.activeBrand ? getJournalStats(db, state.activeBrand) : null,
          pendingOutputReviews:
            db && state.activeBrand ? getPendingOutputReviews(getRecentEntries(db, state.activeBrand, 25)).length : 0,
        };
        return toToolResult(status);
      } finally {
        db?.close();
      }
    },
  };
}

const plugin = {
  id: "openclaw-brand-gen",
  name: "Brand Gen",
  version: PKG_VERSION,
  description: "OpenClaw plugin bridge for brand-gen's MCP runtime with persistent journal + learnings.",
  register(api: PluginApi) {
    const cfg = parsePluginConfig(api.pluginConfig);
    pluginConfigState = cfg;

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
      clientVersion: PKG_VERSION,
    });
    brandBridge.on("log", (line: string) => api.logger.info(`[brand-gen-mcp] ${line}`));
    brandBridge.on("error", (err: Error) => api.logger.error(`[brand-gen-mcp] ${err.message}`));

    api.registerService({
      id: "brand-gen-mcp-bridge",
      start: async (ctx) => {
        ctx.logger.info("Starting brand-gen MCP bridge...");
        await brandBridge!.start();
        const tools = await brandBridge!.listTools();
        discoveredToolCount = tools.length;
        ctx.logger.info(`brand-gen MCP bridge ready with ${tools.length} tools`);
        scheduleHeartbeat(api);
      },
      stop: async (ctx) => {
        ctx.logger.info("Stopping brand-gen MCP bridge...");
        if (heartbeatTimer) {
          clearInterval(heartbeatTimer);
          heartbeatTimer = null;
        }
        if (heartbeatRunPromise) {
          try {
            await heartbeatRunPromise;
          } catch {
            // best effort drain before shutdown
          }
        }
        await brandBridge?.stop();
      },
    });

    api.registerTool(createBrandSearchTool(), { name: "brand_search", optional: true });
    api.registerTool(createBrandExecuteTool(api), { name: "brand_execute", optional: true });
    api.registerTool(createBrandStatusTool(), { name: "brand_status", optional: true });

    api.on("before_agent_start", async (event: any) => {
      if (!brandBridge || !pluginConfigState || !brandBridge.isReady()) return undefined;
      const prompt = extractEventPrompt(event);
      const heartbeatResult = isHeartbeatPrompt(prompt)
        ? await triggerHeartbeat(api, "prompt")
        : null;
      const context = await buildBrandGenContext(brandBridge, pluginConfigState).catch(() => null);
      if (!context) return undefined;
      const heartbeatNotice = heartbeatResult
        ? `Heartbeat result: ${JSON.stringify(heartbeatResult, null, 2)}`
        : "";
      const prepend = [summarizeContext(context), heartbeatNotice].filter(Boolean).join("\n\n");
      return prepend ? { prependContext: prepend } : undefined;
    });
  },
};

export default plugin;

export const __test = {
  PKG_VERSION,
  Type,
  parsePluginConfig,
  loadBrandGenConfig,
  resolveActiveWorkspace,
  extractJsonFromMcpResult,
  buildBrandGenContext,
  summarizeContext,
  mapGenerateParams,
  isHeartbeatPrompt,
  deriveGenerationPolicy,
  loadBrandIdentitySummary,
  runHeartbeatCycle,
};
