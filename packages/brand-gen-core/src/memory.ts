import { randomUUID } from "node:crypto";
import {
  appendFileSync,
  existsSync,
  mkdirSync,
  readFileSync,
  renameSync,
  writeFileSync,
} from "node:fs";
import type { PathLike } from "node:fs";
import { DatabaseSync } from "node:sqlite";
import { basename, dirname, join } from "node:path";
import type { BrandLearnings, JournalEntry, JournalStatus, PipelineResultLike } from "./types.ts";

function nowIso(): string {
  return new Date().toISOString();
}

function ensureDir(path: string): void {
  mkdirSync(path, { recursive: true });
}

function atomicWrite(path: string, content: string): void {
  ensureDir(dirname(path));
  const tmp = `${path}.${process.pid}.${Date.now()}.tmp`;
  writeFileSync(tmp, content, "utf8");
  renameSync(tmp, path);
}

type JournalTarget = DatabaseSync | PathLike;

function isLegacyJournalDb(target: JournalTarget): target is DatabaseSync {
  return Boolean(target) && typeof (target as DatabaseSync).prepare === "function";
}

function workspaceJournalPath(brandPath: PathLike): string {
  return join(String(brandPath), "runs", "journal.jsonl");
}

function readJsonlFile(path: string): JournalEntry[] {
  if (!existsSync(path)) return [];
  const entries: JournalEntry[] = [];
  for (const rawLine of readFileSync(path, "utf8").split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line) continue;
    try {
      const parsed = JSON.parse(line);
      if (parsed && typeof parsed === "object") {
        entries.push(rowToEntry(parsed as Record<string, unknown>));
      }
    } catch {
      continue;
    }
  }
  return entries;
}

export function defaultLearnings(brand: string): BrandLearnings {
  return {
    brand,
    modelPreferences: [],
    colorInsights: [],
    compositionPatterns: [],
    failurePatterns: [],
    messagingInsights: [],
    audienceInsights: [],
    lastUpdated: nowIso(),
  };
}

export function initMemory(brandDir: string, _brand: string): DatabaseSync {
  ensureDir(brandDir);
  const db = new DatabaseSync(join(brandDir, "brand.sqlite"));
  db.exec("PRAGMA journal_mode = WAL;");
  db.exec("PRAGMA synchronous = NORMAL;");
  db.exec(`
    CREATE TABLE IF NOT EXISTS journal (
      id TEXT PRIMARY KEY,
      brand TEXT NOT NULL,
      material_type TEXT,
      goal TEXT,
      goal_id TEXT,
      purpose TEXT,
      target_surface TEXT,
      audience TEXT,
      funnel_stage TEXT,
      call_to_action TEXT,
      briefing TEXT,
      workflow_route TEXT,
      model TEXT,
      prompt TEXT,
      inspiration_sources TEXT,
      reference_roles TEXT,
      output_path TEXT,
      version_id TEXT,
      agent_review_path TEXT,
      visual_review_status TEXT,
      status TEXT DEFAULT 'complete' CHECK(status IN ('in_progress', 'complete', 'failed')),
      stopped_at TEXT,
      rating INTEGER CHECK(rating BETWEEN 0 AND 5),
      feedback TEXT,
      critique TEXT,
      created_at TEXT DEFAULT (datetime('now'))
    );
  `);

  // Auto-migrate: add columns that may be missing from older databases
  const columns = (db.prepare("PRAGMA table_info(journal)").all() as Array<Record<string, unknown>>).map(
    (row) => String(row.name ?? ""),
  );
  const maybeAddColumn = (name: string, ddl: string) => {
    if (!columns.includes(name)) db.exec(`ALTER TABLE journal ADD COLUMN ${ddl};`);
  };
  maybeAddColumn("goal", "goal TEXT");
  maybeAddColumn("goal_id", "goal_id TEXT");
  maybeAddColumn("purpose", "purpose TEXT");
  maybeAddColumn("target_surface", "target_surface TEXT");
  maybeAddColumn("audience", "audience TEXT");
  maybeAddColumn("funnel_stage", "funnel_stage TEXT");
  maybeAddColumn("call_to_action", "call_to_action TEXT");
  maybeAddColumn("briefing", "briefing TEXT");
  maybeAddColumn("agent_review_path", "agent_review_path TEXT");
  maybeAddColumn("visual_review_status", "visual_review_status TEXT");

  return db;
}

function rowToEntry(row: Record<string, unknown>): JournalEntry {
  const stringValue = (camel: string, snake: string): string | undefined => {
    if (typeof row[camel] === "string") return row[camel] as string;
    if (typeof row[snake] === "string") return row[snake] as string;
    return undefined;
  };
  const jsonValue = <T>(camel: string, snake: string, fallback: T): T => {
    const raw = row[camel] ?? row[snake];
    if (typeof raw === "string" && raw) {
      try {
        return JSON.parse(raw) as T;
      } catch {
        return fallback;
      }
    }
    if (raw && typeof raw === "object") return raw as T;
    return fallback;
  };
  return {
    id: String(row.id ?? ""),
    brand: String(row.brand ?? ""),
    materialType: stringValue("materialType", "material_type"),
    goal: stringValue("goal", "goal"),
    goalId: stringValue("goalId", "goal_id"),
    purpose: stringValue("purpose", "purpose"),
    targetSurface: stringValue("targetSurface", "target_surface"),
    audience: stringValue("audience", "audience"),
    funnelStage: stringValue("funnelStage", "funnel_stage"),
    callToAction: stringValue("callToAction", "call_to_action"),
    briefing: stringValue("briefing", "briefing"),
    workflowRoute: stringValue("workflowRoute", "workflow_route"),
    model: stringValue("model", "model"),
    prompt: stringValue("prompt", "prompt"),
    inspirationSources: jsonValue<string[]>("inspirationSources", "inspiration_sources", []),
    referenceRoles: jsonValue<Record<string, unknown>>("referenceRoles", "reference_roles", {}),
    outputPath: stringValue("outputPath", "output_path"),
    versionId: stringValue("versionId", "version_id"),
    agentReviewPath: stringValue("agentReviewPath", "agent_review_path"),
    visualReviewStatus: stringValue("visualReviewStatus", "visual_review_status"),
    status: (row.status as JournalStatus) ?? "failed",
    stoppedAt: stringValue("stoppedAt", "stopped_at"),
    rating: typeof row.rating === "number" ? row.rating : null,
    feedback: stringValue("feedback", "feedback"),
    critique: jsonValue<Record<string, unknown> | null>("critique", "critique", null),
    createdAt: stringValue("createdAt", "created_at"),
  };
}

function entryToJsonLine(entry: JournalEntry): string {
  return JSON.stringify(entry) + "\n";
}

function workspaceJournalEntries(brandPath: PathLike): JournalEntry[] {
  return readJsonlFile(workspaceJournalPath(brandPath));
}

function legacyJournalEntries(db: DatabaseSync, brand: string): JournalEntry[] {
  const rows = db
    .prepare(
      `
        SELECT * FROM journal
        WHERE brand = ?
        ORDER BY datetime(created_at) DESC, rowid DESC
      `,
    )
    .all(brand) as Record<string, unknown>[];
  return rows.map(rowToEntry);
}

function journalEntriesForTarget(target: JournalTarget, brand: string): JournalEntry[] {
  if (isLegacyJournalDb(target)) {
    return legacyJournalEntries(target, brand);
  }
  const entries = workspaceJournalEntries(target);
  const filtered = entries.filter((entry) => entry.brand === brand);
  if (filtered.length || existsSync(workspaceJournalPath(target))) {
    return filtered;
  }
  const legacyDbPath = join(String(target), "brand.sqlite");
  if (existsSync(legacyDbPath)) {
    const db = initMemory(String(target), brand);
    try {
      return legacyJournalEntries(db, brand);
    } finally {
      db.close();
    }
  }
  return filtered;
}

function allJournalEntriesForTarget(target: JournalTarget): JournalEntry[] {
  if (isLegacyJournalDb(target)) {
    const rows = target
      .prepare(`SELECT * FROM journal ORDER BY datetime(created_at) DESC, rowid DESC`)
      .all() as Record<string, unknown>[];
    return rows.map(rowToEntry);
  }
  const entries = workspaceJournalEntries(target);
  if (entries.length || existsSync(workspaceJournalPath(target))) {
    return entries;
  }
  const legacyDbPath = join(String(target), "brand.sqlite");
  if (existsSync(legacyDbPath)) {
    const db = initMemory(String(target), "");
    try {
      const rows = db
        .prepare(`SELECT * FROM journal ORDER BY datetime(created_at) DESC, rowid DESC`)
        .all() as Record<string, unknown>[];
      return rows.map(rowToEntry);
    } finally {
      db.close();
    }
  }
  return entries;
}

function writeWorkspaceJournalEntries(brandPath: PathLike, entries: JournalEntry[]): void {
  const path = workspaceJournalPath(brandPath);
  const payload = entries.map(entryToJsonLine).join("");
  atomicWrite(path, payload);
}

function updateWorkspaceJournalEntry(
  brandPath: PathLike,
  updater: (entries: JournalEntry[]) => JournalEntry[],
): void {
  const current = workspaceJournalEntries(brandPath);
  const next = updater(current);
  writeWorkspaceJournalEntries(brandPath, next);
}

export function appendJournal(target: JournalTarget, entry: JournalEntry): void {
  if (isLegacyJournalDb(target)) {
    const stmt = target.prepare(`
      INSERT INTO journal (
        id, brand, material_type, goal, goal_id, purpose, target_surface,
        audience, funnel_stage, call_to_action, briefing,
        workflow_route, model, prompt,
        inspiration_sources, reference_roles, output_path, version_id,
        status, stopped_at, rating, feedback, critique, created_at
      ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    `);
    stmt.run(
      entry.id || randomUUID(),
      entry.brand,
      entry.materialType ?? null,
      entry.goal ?? null,
      entry.goalId ?? null,
      entry.purpose ?? null,
      entry.targetSurface ?? null,
      entry.audience ?? null,
      entry.funnelStage ?? null,
      entry.callToAction ?? null,
      entry.briefing ?? null,
      entry.workflowRoute ?? null,
      entry.model ?? null,
      entry.prompt ?? null,
      JSON.stringify(entry.inspirationSources ?? []),
      JSON.stringify(entry.referenceRoles ?? {}),
      entry.outputPath ?? null,
      entry.versionId ?? null,
      entry.status,
      entry.stoppedAt ?? null,
      entry.rating ?? null,
      entry.feedback ?? null,
      entry.critique ? JSON.stringify(entry.critique) : null,
      entry.createdAt ?? nowIso(),
    );
    return;
  }
  const path = workspaceJournalPath(target);
  ensureDir(dirname(path));
  appendFileSync(path, entryToJsonLine({ ...entry, id: entry.id || randomUUID(), createdAt: entry.createdAt ?? nowIso() }));
}

export function completeJournal(target: JournalTarget, id: string, result: PipelineResultLike): void {
  const outputPath = result.result?.image_paths?.[0] ?? null;
  const versionId = result.result?.version_id ?? null;
  const agentReviewPath = result.result?.agent_review_path ?? null;
  const visualReviewStatus = result.result?.visual_review_status ?? null;
  const critique = result.result?.vlm_critique ?? result.critique ?? null;
  const stoppedAt = result.stopped_at ?? "complete";
  const completedStages = new Set(["complete", "critique"]);
  const status: JournalStatus = completedStages.has(stoppedAt) ? "complete" : "failed";
  const workflowRoute = result.route?.route_key ?? null;
  if (isLegacyJournalDb(target)) {
    target.prepare(
      `UPDATE journal SET status = ?, stopped_at = ?, workflow_route = COALESCE(?, workflow_route), version_id = ?, output_path = ?, agent_review_path = COALESCE(?, agent_review_path), visual_review_status = COALESCE(?, visual_review_status), critique = ?, feedback = COALESCE(feedback, ?) WHERE id = ?`,
    ).run(
      status,
      stoppedAt,
      workflowRoute,
      versionId,
      outputPath,
      agentReviewPath,
      visualReviewStatus,
      critique ? JSON.stringify(critique) : null,
      result.stop_reason ?? null,
      id,
    );
    return;
  }
  updateWorkspaceJournalEntry(target, (entries) =>
    entries.map((entry) =>
      entry.id === id
        ? {
            ...entry,
            status,
            stoppedAt,
            workflowRoute: workflowRoute ?? entry.workflowRoute,
            versionId: versionId ?? entry.versionId,
            outputPath: outputPath ?? entry.outputPath,
            agentReviewPath: agentReviewPath ?? entry.agentReviewPath,
            visualReviewStatus: visualReviewStatus ?? entry.visualReviewStatus,
            critique: critique ? (critique as Record<string, unknown>) : entry.critique,
            feedback: result.stop_reason ?? entry.feedback,
          }
        : entry,
    ),
  );
}

export function failJournal(target: JournalTarget, id: string, reason: string, stoppedAt = "failed"): void {
  if (isLegacyJournalDb(target)) {
    target.prepare(`UPDATE journal SET status = 'failed', stopped_at = ?, feedback = ? WHERE id = ?`).run(
      stoppedAt,
      reason,
      id,
    );
    return;
  }
  updateWorkspaceJournalEntry(target, (entries) =>
    entries.map((entry) => (entry.id === id ? { ...entry, status: "failed", stoppedAt, feedback: reason } : entry)),
  );
}

export function getOrphanedEntries(target: JournalTarget, olderThanMinutes: number): JournalEntry[] {
  if (isLegacyJournalDb(target)) {
    const stmt = target.prepare(`
      SELECT * FROM journal
      WHERE status = 'in_progress'
        AND datetime(created_at) <= datetime('now', ?)
      ORDER BY datetime(created_at) ASC
    `);
    const rows = stmt.all(`-${Math.max(olderThanMinutes, 1)} minutes`) as Record<string, unknown>[];
    return rows.map(rowToEntry);
  }
  const thresholdMs = Date.now() - Math.max(olderThanMinutes, 1) * 60_000;
  return allJournalEntriesForTarget(target)
    .filter((entry) => entry.status === "in_progress")
    .filter((entry) => {
      const createdAt = Date.parse(entry.createdAt || "");
      return Number.isFinite(createdAt) ? createdAt <= thresholdMs : true;
    });
}

export function rateJournalEntry(
  target: JournalTarget,
  id: string,
  rating: number,
  feedback?: string,
): void {
  if (isLegacyJournalDb(target)) {
    target.prepare(`UPDATE journal SET rating = ?, feedback = COALESCE(?, feedback) WHERE id = ?`).run(
      rating,
      feedback ?? null,
      id,
    );
    return;
  }
  updateWorkspaceJournalEntry(target, (entries) =>
    entries.map((entry) => (entry.id === id ? { ...entry, rating, feedback: feedback ?? entry.feedback } : entry)),
  );
}

export function patchJournalEntry(
  target: JournalTarget,
  id: string,
  patch: Partial<JournalEntry>,
): void {
  if (isLegacyJournalDb(target)) {
    const fragments: string[] = [];
    const values: unknown[] = [];
    const mapping: Array<[keyof JournalEntry, string, (value: unknown) => unknown]> = [
      ["brand", "brand = ?", (value) => value],
      ["materialType", "material_type = ?", (value) => value],
      ["goal", "goal = ?", (value) => value],
      ["goalId", "goal_id = ?", (value) => value],
      ["purpose", "purpose = ?", (value) => value],
      ["targetSurface", "target_surface = ?", (value) => value],
      ["audience", "audience = ?", (value) => value],
      ["funnelStage", "funnel_stage = ?", (value) => value],
      ["callToAction", "call_to_action = ?", (value) => value],
      ["briefing", "briefing = ?", (value) => value],
      ["workflowRoute", "workflow_route = ?", (value) => value],
      ["model", "model = ?", (value) => value],
      ["prompt", "prompt = ?", (value) => value],
      ["outputPath", "output_path = ?", (value) => value],
      ["versionId", "version_id = ?", (value) => value],
      ["agentReviewPath", "agent_review_path = ?", (value) => value],
      ["visualReviewStatus", "visual_review_status = ?", (value) => value],
      ["status", "status = ?", (value) => value],
      ["stoppedAt", "stopped_at = ?", (value) => value],
      ["feedback", "feedback = ?", (value) => value],
      ["critique", "critique = ?", (value) => (value == null ? null : JSON.stringify(value))],
    ];
    for (const [key, fragment, transform] of mapping) {
      const value = patch[key];
      if (value === undefined) continue;
      fragments.push(fragment);
      values.push(transform(value));
    }
    if (!fragments.length) return;
    values.push(id);
    target.prepare(`UPDATE journal SET ${fragments.join(", ")} WHERE id = ?`).run(...(values as any[]));
    return;
  }
  updateWorkspaceJournalEntry(target, (entries) =>
    entries.map((entry) => (entry.id === id ? { ...entry, ...patch } : entry)),
  );
}

export function getRecentEntries(target: JournalTarget, brand: string, limit = 10): JournalEntry[] {
  if (isLegacyJournalDb(target)) {
    const stmt = target.prepare(`
      SELECT * FROM journal
      WHERE brand = ?
      ORDER BY datetime(created_at) DESC, rowid DESC
      LIMIT ?
    `);
    const rows = stmt.all(brand, limit) as Record<string, unknown>[];
    return rows.map(rowToEntry);
  }
  const entries = journalEntriesForTarget(target, brand);
  entries.sort((a, b) => (Date.parse(b.createdAt || "") || 0) - (Date.parse(a.createdAt || "") || 0));
  return entries.slice(0, limit);
}

export function getInProgressEntries(target: JournalTarget, brand: string): JournalEntry[] {
  if (isLegacyJournalDb(target)) {
    const rows = target
      .prepare(
        `
          SELECT * FROM journal
          WHERE brand = ? AND status = 'in_progress'
          ORDER BY datetime(created_at) DESC, rowid DESC
        `,
      )
      .all(brand) as Record<string, unknown>[];
    return rows.map(rowToEntry);
  }
  return journalEntriesForTarget(target, brand).filter((entry) => entry.status === "in_progress");
}

export function getJournalStats(target: JournalTarget, brand: string): {
  total: number;
  rated: number;
  avgRating: number | null;
  inProgress: number;
  failed: number;
} {
  if (isLegacyJournalDb(target)) {
    const row = target
      .prepare(`
        SELECT
          COUNT(*) AS total,
          SUM(CASE WHEN rating IS NOT NULL THEN 1 ELSE 0 END) AS rated,
          AVG(CASE WHEN rating IS NOT NULL THEN rating END) AS avg_rating,
          SUM(CASE WHEN status = 'in_progress' THEN 1 ELSE 0 END) AS in_progress,
          SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) AS failed
        FROM journal
        WHERE brand = ?
      `)
      .get(brand) as Record<string, number | null>;

    return {
      total: Number(row.total ?? 0),
      rated: Number(row.rated ?? 0),
      avgRating: row.avg_rating == null ? null : Number(row.avg_rating),
      inProgress: Number(row.in_progress ?? 0),
      failed: Number(row.failed ?? 0),
    };
  }
  const entries = journalEntriesForTarget(target, brand);
  const rated = entries.filter((entry) => typeof entry.rating === "number");
  return {
    total: entries.length,
    rated: rated.length,
    avgRating: rated.length
      ? rated.reduce((sum, entry) => sum + Number(entry.rating ?? 0), 0) / rated.length
      : null,
    inProgress: entries.filter((entry) => entry.status === "in_progress").length,
    failed: entries.filter((entry) => entry.status === "failed").length,
  };
}

export function loadLearnings(brandPath: string): BrandLearnings | null {
  const path = join(brandPath, "learnings.json");
  if (!existsSync(path)) return null;
  try {
    const parsed = JSON.parse(readFileSync(path, "utf8"));
    return parsed && typeof parsed === "object" ? (parsed as BrandLearnings) : null;
  } catch {
    return null;
  }
}

export function journalPathForWorkspace(brandPath: string | PathLike): string {
  return workspaceJournalPath(brandPath);
}

export function learningsPathForWorkspace(brandPath: string | PathLike): string {
  return join(String(brandPath), "learnings.json");
}

export function saveLearnings(brandPath: string, learnings: BrandLearnings): void {
  const payload = { ...learnings, lastUpdated: nowIso() };
  atomicWrite(join(brandPath, "learnings.json"), JSON.stringify(payload, null, 2) + "\n");
}

function parsePatchPath(path: string): Array<string | number> {
  const tokens: Array<string | number> = [];
  const re = /([^.[\]]+)|\[(\d+)\]/g;
  let match: RegExpExecArray | null;
  while ((match = re.exec(path))) {
    if (match[1]) tokens.push(match[1]);
    else if (match[2]) tokens.push(Number(match[2]));
  }
  if (!tokens.length) throw new Error(`Invalid patch path: ${path}`);
  return tokens;
}

export function patchLearnings(brandPath: string, path: string, value: unknown): BrandLearnings {
  const current = loadLearnings(brandPath) ?? defaultLearnings(basename(brandPath) || "brand");
  const root: Record<string, unknown> = { ...current };
  const tokens = parsePatchPath(path);
  let cursor: any = root;
  for (let i = 0; i < tokens.length - 1; i += 1) {
    const token = tokens[i];
    const next = tokens[i + 1];
    if (typeof token === "number") {
      if (!Array.isArray(cursor)) throw new Error(`Expected array at token ${token}`);
      if (cursor[token] == null) cursor[token] = typeof next === "number" ? [] : {};
      cursor = cursor[token];
      continue;
    }
    if (cursor[token] == null) cursor[token] = typeof next === "number" ? [] : {};
    cursor = cursor[token];
  }
  const last = tokens[tokens.length - 1];
  if (typeof last === "number") {
    if (!Array.isArray(cursor)) throw new Error(`Expected array at token ${last}`);
    cursor[last] = value;
  } else {
    cursor[last] = value;
  }
  const patched = root as BrandLearnings;
  saveLearnings(brandPath, patched);
  return loadLearnings(brandPath) ?? patched;
}

export const __test = {
  atomicWrite,
  parsePatchPath,
  rowToEntry,
};
