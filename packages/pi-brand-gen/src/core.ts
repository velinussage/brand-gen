import { randomUUID } from 'node:crypto';
import { existsSync, readFileSync } from 'node:fs';
import { homedir } from 'node:os';
import { dirname, join, resolve } from 'node:path';

import { McpBridge } from './mcp-bridge.ts';
import {
  appendJournal,
  completeJournal,
  defaultLearnings,
  failJournal,
  getInProgressEntries,
  getJournalStats,
  getOrphanedEntries,
  getRecentEntries,
  initMemory,
  loadLearnings,
  patchLearnings,
  rateJournalEntry,
  type BrandLearnings,
  type JournalEntry,
} from './memory.ts';

export type PluginConfig = {
  brandGenDir: string;
  brandIterateMcpPath: string;
  approvalMode: 'all' | 'output_only' | 'none';
  logLevel: 'debug' | 'info' | 'warn' | 'error';
  heartbeatIntervalMinutes: number;
  autoHeartbeat: boolean;
};

export type BrandGenConfig = {
  active?: string | null;
  activeSession?: string | null;
  version?: number;
  inspirationMode?: boolean;
};

export type ActiveWorkspace = {
  brandGenDir: string;
  activeBrand: string | null;
  activeSession: string | null;
  workspaceDir: string | null;
  savedBrandDir: string | null;
  savedIdentityPath: string | null;
  workspaceIdentityPath: string | null;
};

export type BrandContext = {
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

export type HeartbeatState = {
  timer: NodeJS.Timeout | null;
  runPromise: Promise<Record<string, unknown>> | null;
  healthStatus: 'ok' | 'degraded';
  failures: number;
  lastResult: Record<string, unknown> | null;
};

export type PiLoggerLike = {
  info?: (msg: string) => void;
  warn?: (msg: string) => void;
  error?: (msg: string) => void;
  debug?: (msg: string) => void;
};

export type BridgeLike = Pick<McpBridge, 'isReady' | 'callTool' | 'listTools'>;

export const HEARTBEAT_CYCLE_TIMEOUT_MS = 15 * 60_000;
export const DISCOVER_TIMEOUT_MS = 5 * 60_000;
export const GENERATE_TIMEOUT_MS = 10 * 60_000;
export const ORPHAN_MINUTES = 10;
export const DEFAULT_HEARTBEAT_INTERVAL_MINUTES = 60;

export const GOAL_CATALOG = [
  { goal: 'Explain what the brand/product is clearly', purpose: 'social introduction', targetSurface: 'X feed' },
  { goal: 'Show product truth with stronger branding', purpose: 'product-led promotion', targetSurface: 'web hero' },
  { goal: 'Create a social asset with real brand language', purpose: 'social promo', targetSurface: 'social promo' },
] as const;

export const MATERIAL_ROTATION = ['x-feed', 'browser-illustration', 'product-banner'] as const;

export function expandHome(value: string): string {
  if (!value) return value;
  if (value === '~') return homedir();
  if (value.startsWith('~/')) return join(homedir(), value.slice(2));
  return value;
}

export function readJsonFile<T>(path: string): T | null {
  try {
    if (!existsSync(path)) return null;
    return JSON.parse(readFileSync(path, 'utf8')) as T;
  } catch {
    return null;
  }
}

export function parsePluginConfig(raw: Record<string, unknown> | undefined): PluginConfig {
  const heartbeatRaw = Number(raw?.heartbeatIntervalMinutes ?? DEFAULT_HEARTBEAT_INTERVAL_MINUTES);
  return {
    brandGenDir: expandHome(typeof raw?.brandGenDir === 'string' && raw.brandGenDir.trim() ? raw.brandGenDir : '~/.brand-gen'),
    brandIterateMcpPath: expandHome(typeof raw?.brandIterateMcpPath === 'string' ? raw.brandIterateMcpPath : ''),
    approvalMode: raw?.approvalMode === 'all' || raw?.approvalMode === 'none' ? raw.approvalMode : 'output_only',
    logLevel:
      raw?.logLevel === 'debug' || raw?.logLevel === 'warn' || raw?.logLevel === 'error' ? raw.logLevel : 'info',
    heartbeatIntervalMinutes: Number.isFinite(heartbeatRaw) && heartbeatRaw > 0 ? heartbeatRaw : DEFAULT_HEARTBEAT_INTERVAL_MINUTES,
    autoHeartbeat: raw?.autoHeartbeat !== false,
  };
}

export function loadBrandGenConfig(brandGenDir: string): BrandGenConfig {
  return readJsonFile<BrandGenConfig>(join(brandGenDir, 'config.json')) ?? {};
}

export function deriveBrandFromWorkspace(workspaceDir: string, config: BrandGenConfig): string | null {
  const identity = readJsonFile<Record<string, unknown>>(join(workspaceDir, 'brand-identity.json'));
  const profile = readJsonFile<Record<string, unknown>>(join(workspaceDir, 'brand-profile.json'));
  for (const candidate of [identity, profile]) {
    const sessionContext = candidate?.session_context;
    if (sessionContext && typeof sessionContext === 'object') {
      const seeded = (sessionContext as Record<string, unknown>).seeded_from_brand;
      if (typeof seeded === 'string' && seeded.trim()) return seeded.trim();
    }
  }
  return typeof config.active === 'string' && config.active.trim() ? config.active.trim() : null;
}

export function resolveActiveWorkspace(brandGenDir: string, config = loadBrandGenConfig(brandGenDir)): ActiveWorkspace {
  const activeSession = typeof config.activeSession === 'string' && config.activeSession.trim() ? config.activeSession.trim() : null;
  const active = typeof config.active === 'string' && config.active.trim() ? config.active.trim() : null;

  if (activeSession) {
    const workspaceDir = join(brandGenDir, 'sessions', activeSession, 'brand-materials');
    if (existsSync(workspaceDir)) {
      const activeBrand = deriveBrandFromWorkspace(workspaceDir, config) ?? active;
      const savedBrandDir = activeBrand ? join(brandGenDir, 'brands', activeBrand) : null;
      return {
        brandGenDir,
        activeBrand,
        activeSession,
        workspaceDir,
        savedBrandDir,
        savedIdentityPath: savedBrandDir ? join(savedBrandDir, 'brand-identity.json') : null,
        workspaceIdentityPath: join(workspaceDir, 'brand-identity.json'),
      };
    }
  }

  if (active) {
    const workspaceDir = join(brandGenDir, 'brands', active);
    if (existsSync(workspaceDir)) {
      return {
        brandGenDir,
        activeBrand: active,
        activeSession: null,
        workspaceDir,
        savedBrandDir: workspaceDir,
        savedIdentityPath: join(workspaceDir, 'brand-identity.json'),
        workspaceIdentityPath: join(workspaceDir, 'brand-identity.json'),
      };
    }
  }

  const envWorkspace = process.env.BRAND_DIR ? resolve(expandHome(process.env.BRAND_DIR)) : null;
  if (envWorkspace && existsSync(envWorkspace)) {
    const activeBrand = deriveBrandFromWorkspace(envWorkspace, config) ?? active;
    const savedBrandDir = activeBrand ? join(brandGenDir, 'brands', activeBrand) : null;
    return {
      brandGenDir,
      activeBrand,
      activeSession,
      workspaceDir: envWorkspace,
      savedBrandDir,
      savedIdentityPath: savedBrandDir ? join(savedBrandDir, 'brand-identity.json') : null,
      workspaceIdentityPath: join(envWorkspace, 'brand-identity.json'),
    };
  }

  return {
    brandGenDir,
    activeBrand: active,
    activeSession,
    workspaceDir: null,
    savedBrandDir: active ? join(brandGenDir, 'brands', active) : null,
    savedIdentityPath: active ? join(brandGenDir, 'brands', active, 'brand-identity.json') : null,
    workspaceIdentityPath: null,
  };
}

export function extractJsonFromMcpResult(result: unknown): unknown {
  const anyResult = result as any;
  if (!anyResult || typeof anyResult !== 'object') return undefined;
  const text = Array.isArray(anyResult.content)
    ? anyResult.content.map((c: any) => (c && typeof c.text === 'string' ? c.text : '')).filter(Boolean).join('\n')
    : '';
  if (!text) return undefined;
  try {
    return JSON.parse(text);
  } catch {
    return undefined;
  }
}

export async function callJsonTool(bridge: BridgeLike, name: string, args: Record<string, unknown>): Promise<Record<string, unknown> | null> {
  const raw = await bridge.callTool(name, args);
  const json = extractJsonFromMcpResult(raw);
  return json && typeof json === 'object' ? (json as Record<string, unknown>) : null;
}

export async function buildBrandGenContext(bridge: BridgeLike, config: PluginConfig): Promise<BrandContext> {
  const state = resolveActiveWorkspace(config.brandGenDir);
  const identity = state.savedIdentityPath ? readJsonFile<Record<string, unknown>>(state.savedIdentityPath) : null;
  const blackboard = bridge.isReady() && state.workspaceDir ? await callJsonTool(bridge, 'brand_show_blackboard', { format: 'json' }).catch(() => null) : null;
  const iterationMemory = bridge.isReady() && state.workspaceDir ? await callJsonTool(bridge, 'brand_show_iteration_memory', { format: 'json' }).catch(() => null) : null;
  const learnings = state.savedBrandDir ? loadLearnings(state.savedBrandDir) ?? (state.activeBrand ? defaultLearnings(state.activeBrand) : null) : null;
  let recentJournal: JournalEntry[] = [];
  if (state.savedBrandDir && state.activeBrand) {
    const db = initMemory(state.savedBrandDir, state.activeBrand);
    try {
      recentJournal = getRecentEntries(db, state.activeBrand, 10);
    } finally {
      db.close();
    }
  }
  const availableTools = bridge.isReady() ? (await bridge.listTools()).map((tool) => tool.name) : [];
  return { activeBrand: state.activeBrand, activeSession: state.activeSession, workspaceDir: state.workspaceDir, identity, blackboard, iterationMemory, learnings, recentJournal, availableTools };
}

export function summarizeContext(context: BrandContext): string {
  const identityName = (context.identity?.brand as any)?.name ?? context.activeBrand ?? 'unknown';
  const messaging = (context.identity?.messaging as Record<string, unknown> | undefined) ?? {};
  const decisions = Array.isArray(context.blackboard?.decisions) ? (context.blackboard!.decisions as Array<Record<string, unknown>>) : [];
  const copyNotes = Array.isArray(context.iterationMemory?.copy_notes) ? (context.iterationMemory!.copy_notes as string[]) : [];
  const messagingNotes = Array.isArray(context.iterationMemory?.messaging_notes) ? (context.iterationMemory!.messaging_notes as string[]) : [];
  return [
    '## BRAND_GEN_CONTEXT',
    `Active brand: ${identityName}`,
    context.activeSession ? `Active session: ${context.activeSession}` : 'Active session: none',
    messaging.tagline ? `Tagline: ${messaging.tagline}` : null,
    messaging.elevator ? `Elevator: ${String(messaging.elevator).slice(0, 240)}` : null,
    decisions.length ? `Recent decisions: ${JSON.stringify(decisions.slice(-3), null, 2)}` : null,
    copyNotes.length ? `Copy notes: ${copyNotes.slice(-5).join(' | ')}` : null,
    messagingNotes.length ? `Messaging notes: ${messagingNotes.slice(-5).join(' | ')}` : null,
    context.learnings ? `Learnings: ${JSON.stringify(context.learnings, null, 2)}` : null,
    context.recentJournal.length ? `Recent journal: ${JSON.stringify(context.recentJournal.slice(0, 5), null, 2)}` : null,
    context.availableTools.length ? `Available MCP tools: ${context.availableTools.join(', ')}` : null,
  ].filter(Boolean).join('\n\n');
}

export function isHeartbeatPrompt(prompt: string): boolean {
  return /brand gen heartbeat|brand_heartbeat|brand generation cycle/i.test(prompt);
}

export function mapGenerateParams(params: Record<string, unknown>): Record<string, unknown> {
  return {
    material_type: params.materialType,
    goal: params.goal,
    purpose: params.purpose,
    target_surface: params.targetSurface,
    mode: params.mode ?? 'hybrid',
    prompt_seed: params.promptSeed,
    max_iterations: params.maxIterations ?? 1,
  };
}

export function loadBrandIdentitySummary(identity: Record<string, unknown> | null) {
  const brand = (identity?.brand as Record<string, unknown> | undefined) ?? {};
  const identityCore = (identity?.identity_core as Record<string, unknown> | undefined) ?? {};
  const messaging = (identity?.messaging as Record<string, unknown> | undefined) ?? {};
  const toneWords = Array.isArray(identityCore.tone_words) ? (identityCore.tone_words as string[]).slice(0, 6).join(', ') : '';
  const audience = Array.isArray((messaging as any).audiences) && (messaging as any).audiences.length
    ? ((messaging as any).audiences as string[]).join(', ')
    : 'builders, product teams, and AI-agent operators';
  const productContext = [typeof messaging.elevator === 'string' ? messaging.elevator : '', Array.isArray(messaging.value_propositions) ? (messaging.value_propositions as string[]).slice(0,2).join(' | ') : ''].filter(Boolean).join(' ');
  return {
    brandName: typeof brand.name === 'string' ? brand.name : 'Brand',
    business: typeof brand.summary === 'string' && brand.summary.trim() ? brand.summary : typeof messaging.elevator === 'string' ? messaging.elevator : '',
    audience,
    tone: toneWords,
    productContext,
  };
}

function average(values: number[]): number | null {
  return values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : null;
}

export function isReviewableOutputEntry(entry: JournalEntry): boolean {
  return entry.status === 'complete' && entry.materialType !== 'discover' && entry.materialType !== 'heartbeat-cycle' && (Boolean(entry.outputPath) || Boolean(entry.versionId));
}

export function getPendingOutputReviews(entries: JournalEntry[]): JournalEntry[] {
  return entries.filter((entry) => isReviewableOutputEntry(entry) && entry.rating == null);
}

export function deriveGenerationPolicy(entries: JournalEntry[], approvalMode: PluginConfig['approvalMode']) {
  const recent = entries.slice(0, 10);
  const pendingOutputReviews = getPendingOutputReviews(recent);
  const lastThreeRated = recent.slice(0, 3).map((entry) => entry.rating).filter((rating): rating is number => typeof rating === 'number');
  const lastTwo = recent.slice(0, 2);
  const lastThree = recent.slice(0, 3);

  if (approvalMode === 'all') {
    const pendingReview = pendingOutputReviews[0];
    if (pendingReview) return { skip: true, reason: `Waiting for output rating on ${pendingReview.id}` };
  }
  if (lastThreeRated.length === 3 && (average(lastThreeRated) ?? 0) < 3) return { skip: true, reason: 'Last 3 rated entries average below 3' };
  if (lastTwo.length === 2 && lastTwo.every((entry) => entry.status === 'failed')) return { skip: true, reason: 'Last 2 generations failed' };
  if (lastThree.length === 3 && lastThree.every((entry) => typeof entry.rating === 'number' && entry.rating <= 2)) return { skip: true, reason: 'Last 3 ratings are all 0-2' };

  const recentWithOutput = recent.filter((entry) => entry.status === 'complete' && entry.outputPath);
  let materialType: (typeof MATERIAL_ROTATION)[number] = 'x-feed';
  if (!recentWithOutput.some((entry) => entry.materialType === 'x-feed')) materialType = 'x-feed';
  else if (!recentWithOutput.some((entry) => entry.materialType === 'browser-illustration')) materialType = 'browser-illustration';
  else {
    const lastRotationType = recentWithOutput.find((entry) => MATERIAL_ROTATION.includes(entry.materialType as any))?.materialType as (typeof MATERIAL_ROTATION)[number] | undefined;
    const lastIndex = lastRotationType ? MATERIAL_ROTATION.indexOf(lastRotationType) : -1;
    materialType = MATERIAL_ROTATION[(lastIndex + 1) % MATERIAL_ROTATION.length];
  }

  const recentFive = recent.slice(0, 5);
  const goalUsage = new Map<string, number>();
  for (const option of GOAL_CATALOG) goalUsage.set(option.goal, 0);
  for (const entry of recentFive) if (entry.goal && goalUsage.has(entry.goal)) goalUsage.set(entry.goal, (goalUsage.get(entry.goal) ?? 0) + 1);
  const candidateGoals = [...GOAL_CATALOG].sort((a, b) => (goalUsage.get(a.goal) ?? 0) - (goalUsage.get(b.goal) ?? 0));
  const recentCombos = new Set(recent.slice(0, 3).map((entry) => `${entry.materialType ?? ''}::${entry.goal ?? ''}`));
  const selected = candidateGoals.find((option) => !recentCombos.has(`${materialType}::${option.goal}`)) ?? candidateGoals[0];
  return { skip: false, materialType, goal: selected.goal, purpose: selected.purpose, targetSurface: selected.targetSurface };
}

export function withTimeout<T>(promise: Promise<T>, timeoutMs: number, label: string): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error(`${label} timed out after ${timeoutMs}ms`)), timeoutMs);
    promise.then((value) => { clearTimeout(timer); resolve(value); }, (error) => { clearTimeout(timer); reject(error); });
  });
}

export async function runGenerateAction(bridge: BridgeLike, config: PluginConfig, params: Record<string, unknown>): Promise<Record<string, unknown>> {
  const state = resolveActiveWorkspace(config.brandGenDir);
  if (!state.activeBrand || !state.savedBrandDir) throw new Error('No active saved brand could be resolved for journal storage.');
  const db = initMemory(state.savedBrandDir, state.activeBrand);
  const journalId = randomUUID();
  appendJournal(db, {
    id: journalId,
    brand: state.activeBrand,
    materialType: typeof params.materialType === 'string' ? params.materialType : undefined,
    goal: typeof params.goal === 'string' ? params.goal : undefined,
    purpose: typeof params.purpose === 'string' ? params.purpose : undefined,
    targetSurface: typeof params.targetSurface === 'string' ? params.targetSurface : undefined,
    prompt: typeof params.promptSeed === 'string' ? params.promptSeed : undefined,
    status: 'in_progress',
    createdAt: new Date().toISOString(),
  });
  try {
    const raw = await bridge.callTool('brand_pipeline', mapGenerateParams(params));
    const json = extractJsonFromMcpResult(raw) as Record<string, unknown> | undefined;
    if (!json) throw new Error('brand_pipeline returned no JSON payload');
    completeJournal(db, journalId, json as any);
    const versionId = json.result && typeof json.result === 'object' ? (json.result as Record<string, unknown>).version_id : undefined;
    if (versionId && typeof versionId === 'string') {
      try {
        const reviewRaw = await bridge.callTool('brand_review', { version: versionId, open: false });
        const reviewJson = extractJsonFromMcpResult(reviewRaw);
        if (reviewJson && typeof reviewJson === 'object') db.prepare(`UPDATE journal SET critique = ? WHERE id = ?`).run(JSON.stringify(reviewJson), journalId);
      } catch {}
    }
    return { journalId, ...json };
  } catch (err) {
    failJournal(db, journalId, err instanceof Error ? err.message : String(err), 'generate');
    throw err;
  } finally {
    db.close();
  }
}

export async function runDiscoverStep(bridge: BridgeLike, state: ActiveWorkspace, identity: Record<string, unknown> | null, recentEntries: JournalEntry[]) {
  if (!state.activeBrand || !state.savedBrandDir) return { skipped: true, reason: 'No active brand' };
  const inspirations = readJsonFile<{sources?: string[]}>(join(state.savedBrandDir, 'inspirations.json')) ?? {};
  const allSources = Array.isArray(inspirations.sources) ? inspirations.sources : [];
  if (!allSources.length) return { skipped: true, reason: 'No inspiration sources configured' };
  const rejectedSources = new Set(recentEntries.filter((entry) => entry.materialType === 'discover' && entry.rating === 0 && entry.feedback).flatMap((entry) => entry.feedback!.split(',').map((i) => i.trim()).filter(Boolean)));
  const chosenSources = allSources.filter((source) => !rejectedSources.has(source)).slice(0, 3);
  if (!chosenSources.length) return { skipped: true, reason: 'All inspiration sources were rejected recently' };
  const summary = loadBrandIdentitySummary(identity);
  const raw = await withTimeout(bridge.callTool('brand_explore', {
    brand_name: summary.brandName,
    business: summary.business,
    audience: summary.audience,
    tone: summary.tone,
    product_context: summary.productContext,
    materials: [...MATERIAL_ROTATION],
    sources: chosenSources,
    top: chosenSources.length,
  }), DISCOVER_TIMEOUT_MS, 'Discover step');
  const result = (extractJsonFromMcpResult(raw) as Record<string, unknown> | undefined) ?? {};
  const db = initMemory(state.savedBrandDir, state.activeBrand);
  try {
    appendJournal(db, { id: randomUUID(), brand: state.activeBrand, materialType: 'discover', prompt: summary.business, inspirationSources: chosenSources, status: 'complete', feedback: chosenSources.join(','), critique: result, createdAt: new Date().toISOString() });
  } finally {
    db.close();
  }
  return { skipped: false, sources: chosenSources, result };
}

export async function runGenerateStep(bridge: BridgeLike, config: PluginConfig, state: ActiveWorkspace, identity: Record<string, unknown> | null) {
  if (!state.activeBrand || !state.savedBrandDir) return { skipped: true, reason: 'No active saved brand could be resolved' };
  if (!state.workspaceDir || !identity) return { skipped: true, reason: 'Active workspace or brand identity missing' };
  const db = initMemory(state.savedBrandDir, state.activeBrand);
  try {
    for (const orphan of getOrphanedEntries(db, ORPHAN_MINUTES)) failJournal(db, orphan.id, 'Marked failed by heartbeat orphan cleanup', orphan.stoppedAt ?? 'generate');
    if (getInProgressEntries(db, state.activeBrand).length) return { skipped: true, reason: 'Generation already in progress' };
    const entries = getRecentEntries(db, state.activeBrand, 10);
    const policy = deriveGenerationPolicy(entries, config.approvalMode);
    if (policy.skip || !policy.materialType || !policy.goal || !policy.purpose || !policy.targetSurface) return { skipped: true, reason: policy.reason ?? 'Generation policy skipped' };
    const payload = {
      materialType: policy.materialType,
      goal: policy.goal,
      purpose: policy.purpose,
      targetSurface: policy.targetSurface,
      mode: 'hybrid',
      maxIterations: 1,
      promptSeed: typeof (identity?.messaging as Record<string, unknown> | undefined)?.tagline === 'string' ? String((identity!.messaging as Record<string, unknown>).tagline) : undefined,
    };
    const generated = await withTimeout(runGenerateAction(bridge, config, payload), GENERATE_TIMEOUT_MS, 'Generate step');
    return { skipped: false, payload, result: generated };
  } finally {
    db.close();
  }
}

export async function runHeartbeatCycle(bridge: BridgeLike, config: PluginConfig): Promise<Record<string, unknown>> {
  const state = resolveActiveWorkspace(config.brandGenDir);
  const identity = state.savedIdentityPath ? readJsonFile<Record<string, unknown>>(state.savedIdentityPath) : null;
  const summary: Record<string, unknown> = { startedAt: new Date().toISOString(), activeBrand: state.activeBrand, activeSession: state.activeSession, discover: null, generate: null };
  if (!state.activeBrand || !state.savedBrandDir) {
    summary.skipped = true;
    summary.reason = 'No active brand configured';
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
    appendJournal(summaryDb, { id: randomUUID(), brand: state.activeBrand, materialType: 'heartbeat-cycle', status: 'complete', feedback: JSON.stringify({ discoverSkipped: (summary.discover as any)?.skipped ?? null, generateSkipped: (summary.generate as any)?.skipped ?? null }), critique: summary, createdAt: new Date().toISOString() });
  } finally {
    summaryDb.close();
  }
  return summary;
}

export async function triggerHeartbeat(bridge: BridgeLike, config: PluginConfig, state: HeartbeatState, logger?: PiLoggerLike, trigger: 'timer' | 'command' | 'prompt' = 'timer'): Promise<Record<string, unknown>> {
  if (!bridge.isReady()) {
    state.healthStatus = 'degraded';
    state.failures += 1;
    return { skipped: true, reason: 'MCP bridge not ready' };
  }
  if (state.runPromise) return { skipped: true, reason: 'Heartbeat already running' };
  state.runPromise = withTimeout(runHeartbeatCycle(bridge, config), HEARTBEAT_CYCLE_TIMEOUT_MS, 'Heartbeat cycle');
  try {
    const result = await state.runPromise;
    state.failures = 0;
    state.healthStatus = 'ok';
    state.lastResult = result;
    logger?.info?.(`[brand-heartbeat:${trigger}] ${JSON.stringify(result)}`);
    return result;
  } catch (error) {
    state.failures += 1;
    if (state.failures >= 2) state.healthStatus = 'degraded';
    const message = error instanceof Error ? error.message : String(error);
    logger?.error?.(`[brand-heartbeat:${trigger}] ${message}`);
    return { skipped: false, error: message };
  } finally {
    state.runPromise = null;
  }
}

export function createHeartbeatState(): HeartbeatState {
  return { timer: null, runPromise: null, healthStatus: 'ok', failures: 0, lastResult: null };
}

export function scheduleHeartbeat(bridge: BridgeLike, config: PluginConfig, state: HeartbeatState, logger?: PiLoggerLike): void {
  if (state.timer) clearInterval(state.timer);
  if (!config.autoHeartbeat) return;
  state.timer = setInterval(() => {
    void triggerHeartbeat(bridge, config, state, logger, 'timer');
  }, config.heartbeatIntervalMinutes * 60_000);
}

export async function stopHeartbeat(state: HeartbeatState): Promise<void> {
  if (state.timer) {
    clearInterval(state.timer);
    state.timer = null;
  }
  if (state.runPromise) {
    try { await state.runPromise; } catch {}
  }
}

export function getStatusSnapshot(config: PluginConfig, bridge: BridgeLike | null, heartbeat: HeartbeatState) {
  const workspace = resolveActiveWorkspace(config.brandGenDir);
  const db = workspace.savedBrandDir && workspace.activeBrand ? initMemory(workspace.savedBrandDir, workspace.activeBrand) : null;
  try {
    return {
      bridgeConnected: bridge?.isReady() ?? false,
      activeBrand: workspace.activeBrand,
      activeSession: workspace.activeSession,
      workspaceDir: workspace.workspaceDir,
      savedBrandDir: workspace.savedBrandDir,
      approvalMode: config.approvalMode,
      heartbeatRunning: Boolean(heartbeat.runPromise),
      heartbeatFailures: heartbeat.failures,
      healthStatus: bridge?.isReady() ? heartbeat.healthStatus : 'degraded',
      journalStats: db && workspace.activeBrand ? getJournalStats(db, workspace.activeBrand) : null,
      pendingOutputReviews: db && workspace.activeBrand ? getPendingOutputReviews(getRecentEntries(db, workspace.activeBrand, 25)).length : 0,
      lastHeartbeat: heartbeat.lastResult,
    };
  } finally {
    db?.close();
  }
}

export async function executeAction(bridge: BridgeLike, config: PluginConfig, action: string, params: Record<string, unknown>): Promise<Record<string, unknown>> {
  const state = resolveActiveWorkspace(config.brandGenDir);
  if (action === 'switch_brand') {
    const brand = String(params.brand ?? '').trim();
    if (!brand) throw new Error('switch_brand requires params.brand');
    const raw = await bridge.callTool('brand_use', { brand });
    return { result: extractJsonFromMcpResult(raw) ?? raw };
  }
  if (action === 'patch_learnings') {
    if (!state.savedBrandDir) throw new Error('No active saved brand directory resolved.');
    const path = String(params.path ?? '').trim();
    if (!path) throw new Error('patch_learnings requires params.path');
    return { learnings: patchLearnings(state.savedBrandDir, path, params.value) };
  }
  if (action === 'rate') {
    if (!state.savedBrandDir || !state.activeBrand) throw new Error('No active brand for journal updates.');
    const id = String(params.id ?? '').trim();
    const rating = Number(params.rating);
    if (!id) throw new Error('rate requires params.id');
    if (!Number.isInteger(rating) || rating < 0 || rating > 5) throw new Error('rating must be an integer 0-5');
    const db = initMemory(state.savedBrandDir, state.activeBrand);
    try {
      rateJournalEntry(db, id, rating, typeof params.feedback === 'string' ? params.feedback : undefined);
      return { ok: true, id, rating };
    } finally { db.close(); }
  }
  if (action === 'generate') {
    const required = ['materialType', 'goal', 'purpose', 'targetSurface'];
    const missing = required.filter((key) => typeof params[key] !== 'string' || !String(params[key]).trim());
    if (missing.length) throw new Error(`generate missing required params: ${missing.join(', ')}`);
    return runGenerateAction(bridge, config, params);
  }
  throw new Error(`Unknown brand_execute action: ${action}`);
}
