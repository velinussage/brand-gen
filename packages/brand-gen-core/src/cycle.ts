import { randomUUID } from "node:crypto";
import { join } from "node:path";
import type {
  ActiveWorkspace,
  BridgeLike,
  HeartbeatState,
  JournalEntry,
  LoggerLike,
  PluginConfig,
} from "./types.ts";
import {
  DISCOVER_TIMEOUT_MS,
  GENERATE_TIMEOUT_MS,
  HEARTBEAT_CYCLE_TIMEOUT_MS,
  ORPHAN_MINUTES,
} from "./types.ts";
import { GOAL_CATALOG, MATERIAL_TYPES, type MaterialType } from "./goals.ts";
import {
  appendJournal,
  completeJournal,
  failJournal,
  getInProgressEntries,
  getJournalStats,
  getOrphanedEntries,
  getRecentEntries,
  learningsPathForWorkspace,
  journalPathForWorkspace,
  patchLearnings,
  patchJournalEntry,
  rateJournalEntry,
} from "./memory.ts";
import {
  loadBrandIdentitySummary,
  readJsonFile,
  resolveActiveWorkspace,
} from "./workspace.ts";
import { extractJsonFromMcpResult } from "./context.ts";

// ---------------------------------------------------------------------------
// Utilities
// ---------------------------------------------------------------------------

export function withTimeout<T>(promise: Promise<T>, timeoutMs: number, label: string): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    const timer = setTimeout(
      () => reject(new Error(`${label} timed out after ${timeoutMs}ms`)),
      timeoutMs,
    );
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

export function mapGenerateParams(params: Record<string, unknown>): Record<string, unknown> {
  const payload: Record<string, unknown> = {
    material_type: params.materialType,
    goal: params.goal,
    purpose: params.purpose,
    target_surface: params.targetSurface,
    mode: params.mode ?? "hybrid",
    prompt_seed: params.promptSeed,
    max_iterations: params.maxIterations ?? 1,
  };
  if (params.tag !== undefined) payload.tag = params.tag;
  if (params.mechanic !== undefined) payload.mechanic = params.mechanic;
  if (params.productTruthExpression !== undefined) {
    payload.product_truth_expression = params.productTruthExpression;
  }
  if (params.abstractionLevel !== undefined) payload.abstraction_level = params.abstractionLevel;
  if (params.briefing !== undefined) {
    payload.briefing = params.briefing;
  }
  if (params.audience !== undefined) {
    payload.audience = params.audience;
  }
  if (params.preserve !== undefined) payload.preserve = params.preserve;
  if (params.push !== undefined) payload.push = params.push;
  if (params.ban !== undefined) payload.ban = params.ban;
  if (params.pick !== undefined) payload.pick = params.pick;
  if (params.request !== undefined) payload.request = params.request;
  if (params.route !== undefined) payload.route = params.route;
  if (params.sourceVersion !== undefined) payload.source_version = params.sourceVersion;
  if (params.motionReference !== undefined) payload.motion_reference = params.motionReference;
  if (params.baseImage !== undefined) payload.base_image = params.baseImage;
  if (params.allowBlocking !== undefined) payload.allow_blocking = params.allowBlocking;
  if (params.internalVlmCritique !== undefined) {
    payload.internal_vlm_critique = params.internalVlmCritique;
  }
  return payload;
}

function average(values: number[]): number | null {
  if (!values.length) return null;
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

// ---------------------------------------------------------------------------
// Review helpers
// ---------------------------------------------------------------------------

export function isReviewableOutputEntry(entry: JournalEntry): boolean {
  return (
    entry.status === "complete" &&
    entry.materialType !== "discover" &&
    entry.materialType !== "heartbeat-cycle" &&
    (Boolean(entry.outputPath) || Boolean(entry.versionId))
  );
}

export function getPendingOutputReviews(entries: JournalEntry[]): JournalEntry[] {
  return entries.filter((entry) => isReviewableOutputEntry(entry) && entry.rating == null);
}

// ---------------------------------------------------------------------------
// Generation policy — uses expanded GOAL_CATALOG
// ---------------------------------------------------------------------------

export function deriveGenerationPolicy(
  entries: JournalEntry[],
  approvalMode: PluginConfig["approvalMode"],
): {
  skip: boolean;
  reason?: string;
  materialType?: MaterialType;
  goalId?: string;
  goal?: string;
  purpose?: string;
  targetSurface?: string;
  audience?: string;
  funnelStage?: string;
  callToAction?: string;
  briefing?: string;
} {
  const recent = entries.slice(0, 10);
  const pendingOutputReviews = getPendingOutputReviews(recent);
  const lastThreeRated = recent
    .slice(0, 3)
    .map((entry) => entry.rating)
    .filter((rating): rating is number => typeof rating === "number");
  const lastTwo = recent.slice(0, 2);
  const lastThree = recent.slice(0, 3);

  // --- Backpressure checks ---
  if (approvalMode === "all") {
    const pendingReview = pendingOutputReviews[0];
    if (pendingReview) {
      return { skip: true, reason: `Waiting for output rating on ${pendingReview.id}` };
    }
  }

  if (lastThreeRated.length === 3 && (average(lastThreeRated) ?? 0) < 3) {
    return { skip: true, reason: "Last 3 rated entries average below 3" };
  }

  if (lastTwo.length === 2 && lastTwo.every((entry) => entry.status === "failed")) {
    return { skip: true, reason: "Last 2 generations failed" };
  }

  if (
    lastThree.length === 3 &&
    lastThree.every((entry) => typeof entry.rating === "number" && entry.rating <= 2)
  ) {
    return { skip: true, reason: "Last 3 ratings are all 0-2" };
  }

  // --- Material type rotation ---
  const recentWithOutput = recent.filter(
    (entry) => entry.status === "complete" && entry.outputPath,
  );
  let materialType: MaterialType = "social";
  if (!recentWithOutput.some((entry) => entry.materialType === "social")) {
    materialType = "social";
  } else if (
    !recentWithOutput.some((entry) => entry.materialType === "browser-illustration")
  ) {
    materialType = "browser-illustration";
  } else if (
    !recentWithOutput.some((entry) => entry.materialType === "feature-illustration")
  ) {
    materialType = "feature-illustration";
  } else {
    const lastRotationType = recentWithOutput.find((entry) =>
      MATERIAL_TYPES.includes(entry.materialType as MaterialType),
    )?.materialType as MaterialType | undefined;
    const lastIndex = lastRotationType ? MATERIAL_TYPES.indexOf(lastRotationType) : -1;
    materialType = MATERIAL_TYPES[(lastIndex + 1) % MATERIAL_TYPES.length];
  }

  // --- Goal selection with rich audience/funnel tracking ---
  // Filter goals that match the selected material type (or accept any)
  const eligibleGoals = GOAL_CATALOG.filter(
    (g) => g.preferredMaterial === materialType || g.preferredMaterial === "social",
  );
  const goalPool = eligibleGoals.length > 0 ? eligibleGoals : [...GOAL_CATALOG];

  // Track usage of each goal in recent entries
  const recentTen = recent.slice(0, 10);
  const goalUsage = new Map<string, number>();
  for (const option of goalPool) goalUsage.set(option.id, 0);
  for (const entry of recentTen) {
    if (entry.goalId && goalUsage.has(entry.goalId)) {
      goalUsage.set(entry.goalId, (goalUsage.get(entry.goalId) ?? 0) + 1);
    }
  }

  // Sort by least-recently-used, break ties by funnel stage diversity
  const funnelStageUsage = new Map<string, number>();
  for (const entry of recentTen) {
    if (entry.funnelStage) {
      funnelStageUsage.set(
        entry.funnelStage,
        (funnelStageUsage.get(entry.funnelStage) ?? 0) + 1,
      );
    }
  }
  const candidateGoals = [...goalPool].sort((a, b) => {
    const usageDiff = (goalUsage.get(a.id) ?? 0) - (goalUsage.get(b.id) ?? 0);
    if (usageDiff !== 0) return usageDiff;
    // Prefer under-represented funnel stages
    return (
      (funnelStageUsage.get(a.funnelStage) ?? 0) -
      (funnelStageUsage.get(b.funnelStage) ?? 0)
    );
  });

  // Avoid repeating the exact same material+goal combo from last 3 entries
  const recentCombos = new Set(
    recent.slice(0, 3).map((entry) => `${entry.materialType ?? ""}::${entry.goalId ?? ""}`),
  );
  const selected =
    candidateGoals.find(
      (option) => !recentCombos.has(`${materialType}::${option.id}`),
    ) ?? candidateGoals[0];

  return {
    skip: false,
    materialType,
    goalId: selected.id,
    goal: selected.goal,
    purpose: selected.purpose,
    targetSurface: selected.targetSurface,
    audience: selected.audience,
    funnelStage: selected.funnelStage,
    callToAction: selected.callToAction,
    briefing: selected.briefing,
  };
}

// ---------------------------------------------------------------------------
// Generate action — creates journal entry, calls brand_pipeline, and relies on
// pipeline-provided agent-review handoff metadata when available.
// ---------------------------------------------------------------------------

export async function runGenerateAction(
  bridge: BridgeLike,
  config: PluginConfig,
  params: Record<string, unknown>,
): Promise<Record<string, unknown>> {
  const state = resolveActiveWorkspace(config.brandGenDir);
  if (!state.activeBrand || !state.workspaceDir) {
    throw new Error("No active workspace could be resolved for journal storage.");
  }
  const journalRoot = state.workspaceDir;
  const journalId = randomUUID();
  const entry: JournalEntry = {
    id: journalId,
    brand: state.activeBrand,
    materialType: typeof params.materialType === "string" ? params.materialType : undefined,
    goal: typeof params.goal === "string" ? params.goal : undefined,
    goalId: typeof params.goalId === "string" ? params.goalId : undefined,
    purpose: typeof params.purpose === "string" ? params.purpose : undefined,
    targetSurface: typeof params.targetSurface === "string" ? params.targetSurface : undefined,
    audience: typeof params.audience === "string" ? params.audience : undefined,
    funnelStage: typeof params.funnelStage === "string" ? params.funnelStage : undefined,
    callToAction: typeof params.callToAction === "string" ? params.callToAction : undefined,
    briefing: typeof params.briefing === "string" ? params.briefing : undefined,
    prompt: typeof params.promptSeed === "string" ? params.promptSeed : undefined,
    status: "in_progress",
    createdAt: new Date().toISOString(),
  };
  appendJournal(journalRoot, entry);
  try {
    const payload = mapGenerateParams(params);
    const raw = await bridge.callTool("brand_pipeline", payload);
    const json = extractJsonFromMcpResult(raw) as Record<string, unknown> | undefined;
    if (!json) throw new Error("brand_pipeline returned no JSON payload");
    completeJournal(journalRoot, journalId, json as any);
    const pipelineResult =
      json.result && typeof json.result === "object"
        ? (json.result as Record<string, unknown>)
        : undefined;
    const versionId = typeof pipelineResult?.version_id === "string" ? pipelineResult.version_id : undefined;
    const agentReviewPath =
      typeof pipelineResult?.agent_review_path === "string" ? pipelineResult.agent_review_path : undefined;
    const visualReviewStatus =
      typeof pipelineResult?.visual_review_status === "string"
        ? pipelineResult.visual_review_status
        : undefined;
    if (agentReviewPath || visualReviewStatus) {
      patchJournalEntry(journalRoot, journalId, {
        agentReviewPath,
        visualReviewStatus,
      });
    } else if (versionId && typeof versionId === "string") {
      try {
        const reviewRaw = await bridge.callTool("brand_review", {
          version: versionId,
          open: false,
        });
        const reviewJson = extractJsonFromMcpResult(reviewRaw);
        if (reviewJson && typeof reviewJson === "object") {
          patchJournalEntry(journalRoot, journalId, { critique: reviewJson as Record<string, unknown> });
        }
      } catch {
        // best effort only
      }
    }
    return { journalId, ...json };
  } catch (err) {
    failJournal(journalRoot, journalId, err instanceof Error ? err.message : String(err), "generate");
    throw err;
  }
}

// ---------------------------------------------------------------------------
// Discover step — crawl inspiration sources
// ---------------------------------------------------------------------------

export async function runDiscoverStep(
  bridge: BridgeLike,
  state: ActiveWorkspace,
  identity: Record<string, unknown> | null,
  recentEntries: JournalEntry[],
): Promise<Record<string, unknown>> {
  if (!state.activeBrand || !state.workspaceDir) {
    return { skipped: true, reason: "No active brand" };
  }
  const inspirations =
    readJsonFile<{ sources?: string[] }>(join(state.workspaceDir, "inspirations.json")) ??
    (state.savedBrandDir && state.savedBrandDir !== state.workspaceDir
      ? readJsonFile<{ sources?: string[] }>(join(state.savedBrandDir, "inspirations.json"))
      : null) ??
    {};
  const allSources = Array.isArray(inspirations.sources) ? inspirations.sources : [];
  if (!allSources.length) return { skipped: true, reason: "No inspiration sources configured" };

  const rejectedSources = new Set(
    recentEntries
      .filter(
        (entry) =>
          entry.materialType === "discover" && entry.rating === 0 && entry.feedback,
      )
      .flatMap((entry) =>
        entry.feedback!
          .split(",")
          .map((item) => item.trim())
          .filter(Boolean),
      ),
  );
  const chosenSources = allSources
    .filter((source) => !rejectedSources.has(source))
    .slice(0, 3);
  if (!chosenSources.length) {
    return { skipped: true, reason: "All inspiration sources were rejected recently" };
  }

  const summary = loadBrandIdentitySummary(identity);
  const raw = await withTimeout(
    bridge.callTool("brand_explore", {
      brand_name: summary.brandName,
      business: summary.business,
      audience: summary.audience,
      tone: summary.tone,
      product_context: summary.productContext,
      materials: [...MATERIAL_TYPES],
      sources: chosenSources,
      top: chosenSources.length,
    }),
    DISCOVER_TIMEOUT_MS,
    "Discover step",
  );
  const result =
    (extractJsonFromMcpResult(raw) as Record<string, unknown> | undefined) ?? {};

  appendJournal(state.workspaceDir, {
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

  return { skipped: false, sources: chosenSources, result };
}

// ---------------------------------------------------------------------------
// Generate step — orchestrates policy + generate action
// ---------------------------------------------------------------------------

export async function runGenerateStep(
  bridge: BridgeLike,
  config: PluginConfig,
  state: ActiveWorkspace,
  identity: Record<string, unknown> | null,
): Promise<Record<string, unknown>> {
  if (!state.activeBrand || !state.workspaceDir) {
    return { skipped: true, reason: "No active saved brand could be resolved" };
  }
  if (!identity) {
    return { skipped: true, reason: "Active workspace or brand identity missing" };
  }

  for (const orphan of getOrphanedEntries(state.workspaceDir, ORPHAN_MINUTES)) {
    failJournal(
      state.workspaceDir,
      orphan.id,
      "Marked failed by heartbeat orphan cleanup",
      orphan.stoppedAt ?? "generate",
    );
  }
  if (getInProgressEntries(state.workspaceDir, state.activeBrand).length) {
    return { skipped: true, reason: "Generation already in progress" };
  }

  const entries = getRecentEntries(state.workspaceDir, state.activeBrand, 10);
  const policy = deriveGenerationPolicy(entries, config.approvalMode);
  if (policy.skip || !policy.materialType || !policy.goal || !policy.purpose) {
    return { skipped: true, reason: policy.reason ?? "Generation policy skipped" };
  }

  const payload = {
    materialType: policy.materialType,
    goalId: policy.goalId,
    goal: policy.goal,
    purpose: policy.purpose,
    targetSurface: policy.targetSurface,
    audience: policy.audience,
    funnelStage: policy.funnelStage,
    callToAction: policy.callToAction,
    briefing: policy.briefing,
    mode: "hybrid",
    maxIterations: 1,
    promptSeed:
      typeof (identity?.messaging as Record<string, unknown> | undefined)?.tagline === "string"
        ? String((identity!.messaging as Record<string, unknown>).tagline)
        : undefined,
  };
  const generated = await withTimeout(
    runGenerateAction(bridge, config, payload),
    GENERATE_TIMEOUT_MS,
    "Generate step",
  );
  return { skipped: false, payload, result: generated };
}

// ---------------------------------------------------------------------------
// Heartbeat cycle — discover + generate
// ---------------------------------------------------------------------------

export async function runHeartbeatCycle(
  bridge: BridgeLike,
  config: PluginConfig,
): Promise<Record<string, unknown>> {
  const state = resolveActiveWorkspace(config.brandGenDir);
  const identityPath =
    (state.workspaceIdentityPath && readJsonFile<Record<string, unknown>>(state.workspaceIdentityPath)
      ? state.workspaceIdentityPath
      : null) ??
    state.savedIdentityPath;
  const identity = identityPath ? readJsonFile<Record<string, unknown>>(identityPath) : null;
  const summary: Record<string, unknown> = {
    startedAt: new Date().toISOString(),
    activeBrand: state.activeBrand,
    activeSession: state.activeSession,
    brandGenDir: state.brandGenDir,
    workspaceKind: state.workspaceKind,
    discover: null,
    generate: null,
  };

  if (!state.activeBrand || !state.workspaceDir) {
    summary.skipped = true;
    summary.reason = "No active brand configured";
    return summary;
  }

  let recentEntries: JournalEntry[] = [];
  recentEntries = getRecentEntries(state.workspaceDir, state.activeBrand, 20);

  summary.discover = await runDiscoverStep(bridge, state, identity, recentEntries);
  summary.generate = await runGenerateStep(bridge, config, state, identity);
  summary.completedAt = new Date().toISOString();

  appendJournal(state.workspaceDir, {
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
  return summary;
}

// ---------------------------------------------------------------------------
// Heartbeat state management
// ---------------------------------------------------------------------------

export function createHeartbeatState(): HeartbeatState {
  return { timer: null, runPromise: null, healthStatus: "ok", failures: 0, lastResult: null };
}

export async function triggerHeartbeat(
  bridge: BridgeLike,
  config: PluginConfig,
  state: HeartbeatState,
  logger?: LoggerLike,
  trigger: "timer" | "command" | "prompt" = "timer",
): Promise<Record<string, unknown>> {
  if (!bridge.isReady()) {
    state.healthStatus = "degraded";
    state.failures += 1;
    return { skipped: true, reason: "MCP bridge not ready" };
  }
  if (state.runPromise) {
    return { skipped: true, reason: "Heartbeat already running" };
  }

  state.runPromise = withTimeout(
    runHeartbeatCycle(bridge, config),
    HEARTBEAT_CYCLE_TIMEOUT_MS,
    "Heartbeat cycle",
  );

  try {
    const result = await state.runPromise;
    state.failures = 0;
    state.healthStatus = "ok";
    state.lastResult = result;
    logger?.info?.(`[brand-heartbeat:${trigger}] ${JSON.stringify(result)}`);
    return result;
  } catch (error) {
    state.failures += 1;
    if (state.failures >= 2) state.healthStatus = "degraded";
    const message = error instanceof Error ? error.message : String(error);
    logger?.error?.(`[brand-heartbeat:${trigger}] ${message}`);
    return { skipped: false, error: message };
  } finally {
    state.runPromise = null;
  }
}

export function scheduleHeartbeat(
  bridge: BridgeLike,
  config: PluginConfig,
  state: HeartbeatState,
  logger?: LoggerLike,
): void {
  if (state.timer) clearInterval(state.timer);
  if (!config.autoHeartbeat) return;
  state.timer = setInterval(() => {
    void triggerHeartbeat(bridge, config, state, logger, "timer");
  }, config.heartbeatIntervalMinutes * 60_000);
}

export async function stopHeartbeat(state: HeartbeatState): Promise<void> {
  if (state.timer) {
    clearInterval(state.timer);
    state.timer = null;
  }
  if (state.runPromise) {
    try {
      await state.runPromise;
    } catch {
      // drain
    }
  }
}

// ---------------------------------------------------------------------------
// Status snapshot
// ---------------------------------------------------------------------------

export function getStatusSnapshot(
  config: PluginConfig,
  bridge: BridgeLike | null,
  heartbeat: HeartbeatState,
) {
  const workspace = resolveActiveWorkspace(config.brandGenDir);
  const journalRoot = workspace.workspaceDir ?? workspace.savedBrandDir ?? null;
  return {
    bridgeConnected: bridge?.isReady() ?? false,
    brandGenDir: workspace.brandGenDir,
    workspaceKind: workspace.workspaceKind,
    activeBrand: workspace.activeBrand,
    activeSession: workspace.activeSession,
    workspaceDir: workspace.workspaceDir,
    workspaceIdentityPath: workspace.workspaceIdentityPath,
    savedBrandDir: workspace.savedBrandDir,
    approvalMode: config.approvalMode,
    heartbeatRunning: Boolean(heartbeat.runPromise),
    heartbeatFailures: heartbeat.failures,
    healthStatus: bridge?.isReady() ? heartbeat.healthStatus : "degraded",
    journalPath: journalRoot ? journalPathForWorkspace(journalRoot) : null,
    learningsPath: journalRoot ? learningsPathForWorkspace(journalRoot) : null,
    journalStats:
      journalRoot && workspace.activeBrand
        ? getJournalStats(journalRoot, workspace.activeBrand)
        : null,
    pendingOutputReviews:
      journalRoot && workspace.activeBrand
        ? getPendingOutputReviews(getRecentEntries(journalRoot, workspace.activeBrand, 25)).length
        : 0,
    lastHeartbeat: heartbeat.lastResult,
  };
}

// ---------------------------------------------------------------------------
// Action executor — shared between OpenClaw and Pi
// ---------------------------------------------------------------------------

export async function executeAction(
  bridge: BridgeLike,
  config: PluginConfig,
  action: string,
  params: Record<string, unknown>,
): Promise<Record<string, unknown>> {
  const state = resolveActiveWorkspace(config.brandGenDir);

  if (action === "switch_brand") {
    const brand = String(params.brand ?? "").trim();
    if (!brand) throw new Error("switch_brand requires params.brand");
    const raw = await bridge.callTool("brand_use", { brand });
    return { result: extractJsonFromMcpResult(raw) ?? raw };
  }

  if (action === "patch_learnings") {
    if (!state.workspaceDir) throw new Error("No active workspace directory resolved.");
    const path = String(params.path ?? "").trim();
    if (!path) throw new Error("patch_learnings requires params.path");
    return { learnings: patchLearnings(state.workspaceDir, path, params.value) };
  }

  if (action === "rate") {
    if (!state.workspaceDir || !state.activeBrand)
      throw new Error("No active brand for journal updates.");
    const id = String(params.id ?? "").trim();
    const rating = Number(params.rating);
    if (!id) throw new Error("rate requires params.id");
    if (!Number.isInteger(rating) || rating < 0 || rating > 5)
      throw new Error("rating must be an integer 0-5");
    rateJournalEntry(
      state.workspaceDir,
      id,
      rating,
      typeof params.feedback === "string" ? params.feedback : undefined,
    );
    return { ok: true, id, rating };
  }

  if (action === "generate") {
    const required = ["materialType", "goal", "purpose", "targetSurface"];
    const missing = required.filter(
      (key) => typeof params[key] !== "string" || !String(params[key]).trim(),
    );
    if (missing.length)
      throw new Error(`generate missing required params: ${missing.join(", ")}`);
    return runGenerateAction(bridge, config, params);
  }

  if (action === "derive_mockup") {
    const sourceVersion = String(params.sourceVersion ?? "").trim();
    if (!sourceVersion) throw new Error("derive_mockup requires params.sourceVersion");
    const raw = await bridge.callTool("brand_derive_mockup", {
      source_version: sourceVersion,
      material_type:
        typeof params.materialType === "string" ? params.materialType : "device-mockup",
      prompt: typeof params.prompt === "string" ? params.prompt : undefined,
      tag: typeof params.tag === "string" ? params.tag : undefined,
      model: typeof params.model === "string" ? params.model : undefined,
      aspect_ratio: typeof params.aspectRatio === "string" ? params.aspectRatio : undefined,
      negative_prompt:
        typeof params.negativePrompt === "string" ? params.negativePrompt : undefined,
      format: "json",
    });
    return { result: extractJsonFromMcpResult(raw) ?? raw };
  }

  if (action === "derive_video") {
    const sourceVersion = String(params.sourceVersion ?? "").trim();
    if (!sourceVersion) throw new Error("derive_video requires params.sourceVersion");
    const raw = await bridge.callTool("brand_derive_video", {
      source_version: sourceVersion,
      material_type:
        typeof params.materialType === "string" ? params.materialType : "short-video",
      prompt: typeof params.prompt === "string" ? params.prompt : undefined,
      tag: typeof params.tag === "string" ? params.tag : undefined,
      model: typeof params.model === "string" ? params.model : undefined,
      aspect_ratio: typeof params.aspectRatio === "string" ? params.aspectRatio : undefined,
      duration: typeof params.duration === "number" ? params.duration : undefined,
      motion_reference:
        typeof params.motionReference === "string" ? params.motionReference : undefined,
      negative_prompt:
        typeof params.negativePrompt === "string" ? params.negativePrompt : undefined,
      make_gif: params.makeGif === true,
      format: "json",
    });
    return { result: extractJsonFromMcpResult(raw) ?? raw };
  }

  if (action === "consolidate_inspiration") {
    const raw = await bridge.callTool("brand_consolidate_inspiration", {
      image: Array.isArray(params.images) ? params.images : params.image,
      brand_key: typeof params.brandKey === "string" ? params.brandKey : undefined,
      refresh: params.refresh === true,
      format: "json",
    });
    return { result: extractJsonFromMcpResult(raw) ?? raw };
  }

  if (action === "submit_critique") {
    const version = String(params.version ?? "").trim();
    if (!version) throw new Error("submit_critique requires params.version");
    const critique =
      params.critique && typeof params.critique === "object"
        ? (params.critique as Record<string, unknown>)
        : {};
    const raw = await bridge.callTool("brand_submit_critique", {
      version,
      critique_json: JSON.stringify(critique),
      format: "json",
    });
    return { result: extractJsonFromMcpResult(raw) ?? raw };
  }

  if (action === "feedback") {
    const version = String(params.version ?? "").trim();
    const score = Number(params.score);
    if (!version) throw new Error("feedback requires params.version");
    if (!Number.isFinite(score)) throw new Error("feedback requires numeric params.score");
    const raw = await bridge.callTool("brand_feedback", {
      version,
      score,
      status: typeof params.status === "string" ? params.status : undefined,
      notes: typeof params.notes === "string" ? params.notes : undefined,
      lock: Array.isArray(params.lockFragments) ? params.lockFragments : undefined,
      format: "json",
    });
    return { result: extractJsonFromMcpResult(raw) ?? raw };
  }

  throw new Error(`Unknown brand_execute action: ${action}`);
}
