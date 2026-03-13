import { randomUUID } from "node:crypto";
import { existsSync, mkdirSync, readFileSync, renameSync, writeFileSync } from "node:fs";
import { DatabaseSync } from "node:sqlite";
import { basename, dirname, join } from "node:path";

export type JournalStatus = "in_progress" | "complete" | "failed";

export type JournalEntry = {
  id: string;
  brand: string;
  materialType?: string;
  goal?: string;
  purpose?: string;
  targetSurface?: string;
  workflowRoute?: string;
  model?: string;
  prompt?: string;
  inspirationSources?: string[];
  referenceRoles?: Record<string, unknown>;
  outputPath?: string;
  versionId?: string;
  status: JournalStatus;
  stoppedAt?: string;
  rating?: number | null;
  feedback?: string;
  critique?: Record<string, unknown> | null;
  createdAt?: string;
};

export type BrandLearnings = {
  brand: string;
  modelPreferences: string[];
  colorInsights: string[];
  compositionPatterns: string[];
  failurePatterns: string[];
  messagingInsights?: string[];
  lastUpdated?: string;
};

export type PipelineResultLike = {
  workflow_id?: string;
  stopped_at?: string;
  stop_reason?: string;
  route?: { route_key?: string } | null;
  result?: {
    version_id?: string;
    image_paths?: string[];
    vlm_critique?: Record<string, unknown> | null;
  } | null;
  critique?: Record<string, unknown> | null;
};

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

export function defaultLearnings(brand: string): BrandLearnings {
  return {
    brand,
    modelPreferences: [],
    colorInsights: [],
    compositionPatterns: [],
    failurePatterns: [],
    messagingInsights: [],
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
      purpose TEXT,
      target_surface TEXT,
      workflow_route TEXT,
      model TEXT,
      prompt TEXT,
      inspiration_sources TEXT,
      reference_roles TEXT,
      output_path TEXT,
      version_id TEXT,
      status TEXT DEFAULT 'complete' CHECK(status IN ('in_progress', 'complete', 'failed')),
      stopped_at TEXT,
      rating INTEGER CHECK(rating BETWEEN 0 AND 5),
      feedback TEXT,
      critique TEXT,
      created_at TEXT DEFAULT (datetime('now'))
    );
  `);
  const columns = (db.prepare("PRAGMA table_info(journal)").all() as Array<Record<string, unknown>>).map(
    (row) => String(row.name ?? ""),
  );
  const maybeAddColumn = (name: string, ddl: string) => {
    if (!columns.includes(name)) db.exec(`ALTER TABLE journal ADD COLUMN ${ddl};`);
  };
  maybeAddColumn("goal", "goal TEXT");
  maybeAddColumn("purpose", "purpose TEXT");
  maybeAddColumn("target_surface", "target_surface TEXT");
  return db;
}

function rowToEntry(row: Record<string, unknown>): JournalEntry {
  return {
    id: String(row.id ?? ""),
    brand: String(row.brand ?? ""),
    materialType: typeof row.material_type === "string" ? row.material_type : undefined,
    goal: typeof row.goal === "string" ? row.goal : undefined,
    purpose: typeof row.purpose === "string" ? row.purpose : undefined,
    targetSurface: typeof row.target_surface === "string" ? row.target_surface : undefined,
    workflowRoute: typeof row.workflow_route === "string" ? row.workflow_route : undefined,
    model: typeof row.model === "string" ? row.model : undefined,
    prompt: typeof row.prompt === "string" ? row.prompt : undefined,
    inspirationSources:
      typeof row.inspiration_sources === "string" && row.inspiration_sources
        ? JSON.parse(row.inspiration_sources)
        : [],
    referenceRoles:
      typeof row.reference_roles === "string" && row.reference_roles
        ? JSON.parse(row.reference_roles)
        : {},
    outputPath: typeof row.output_path === "string" ? row.output_path : undefined,
    versionId: typeof row.version_id === "string" ? row.version_id : undefined,
    status: (row.status as JournalStatus) ?? "failed",
    stoppedAt: typeof row.stopped_at === "string" ? row.stopped_at : undefined,
    rating: typeof row.rating === "number" ? row.rating : null,
    feedback: typeof row.feedback === "string" ? row.feedback : undefined,
    critique:
      typeof row.critique === "string" && row.critique ? JSON.parse(row.critique) : null,
    createdAt: typeof row.created_at === "string" ? row.created_at : undefined,
  };
}

export function appendJournal(db: DatabaseSync, entry: JournalEntry): void {
  const stmt = db.prepare(`
    INSERT INTO journal (
      id, brand, material_type, goal, purpose, target_surface, workflow_route, model, prompt,
      inspiration_sources, reference_roles, output_path, version_id,
      status, stopped_at, rating, feedback, critique, created_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
  `);
  stmt.run(
    entry.id || randomUUID(),
    entry.brand,
    entry.materialType ?? null,
    entry.goal ?? null,
    entry.purpose ?? null,
    entry.targetSurface ?? null,
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
}

export function completeJournal(db: DatabaseSync, id: string, result: PipelineResultLike): void {
  const outputPath = result.result?.image_paths?.[0] ?? null;
  const versionId = result.result?.version_id ?? null;
  const critique = result.result?.vlm_critique ?? result.critique ?? null;
  const stoppedAt = result.stopped_at ?? "complete";
  const completedStages = new Set(["complete", "critique"]);
  const status: JournalStatus = completedStages.has(stoppedAt) ? "complete" : "failed";
  const workflowRoute = result.route?.route_key ?? null;
  db.prepare(
    `UPDATE journal SET status = ?, stopped_at = ?, workflow_route = COALESCE(?, workflow_route), version_id = ?, output_path = ?, critique = ?, feedback = COALESCE(feedback, ?) WHERE id = ?`,
  ).run(
    status,
    stoppedAt,
    workflowRoute,
    versionId,
    outputPath,
    critique ? JSON.stringify(critique) : null,
    result.stop_reason ?? null,
    id,
  );
}

export function failJournal(db: DatabaseSync, id: string, reason: string, stoppedAt = "failed"): void {
  db.prepare(`UPDATE journal SET status = 'failed', stopped_at = ?, feedback = ? WHERE id = ?`).run(
    stoppedAt,
    reason,
    id,
  );
}

export function getOrphanedEntries(db: DatabaseSync, olderThanMinutes: number): JournalEntry[] {
  const stmt = db.prepare(`
    SELECT * FROM journal
    WHERE status = 'in_progress'
      AND datetime(created_at) <= datetime('now', ?)
    ORDER BY datetime(created_at) ASC
  `);
  const rows = stmt.all(`-${Math.max(olderThanMinutes, 1)} minutes`) as Record<string, unknown>[];
  return rows.map(rowToEntry);
}

export function rateJournalEntry(
  db: DatabaseSync,
  id: string,
  rating: number,
  feedback?: string,
): void {
  db.prepare(`UPDATE journal SET rating = ?, feedback = COALESCE(?, feedback) WHERE id = ?`).run(
    rating,
    feedback ?? null,
    id,
  );
}

export function getRecentEntries(db: DatabaseSync, brand: string, limit = 10): JournalEntry[] {
  const stmt = db.prepare(`
    SELECT * FROM journal
    WHERE brand = ?
    ORDER BY datetime(created_at) DESC, rowid DESC
    LIMIT ?
  `);
  const rows = stmt.all(brand, limit) as Record<string, unknown>[];
  return rows.map(rowToEntry);
}

export function getInProgressEntries(db: DatabaseSync, brand: string): JournalEntry[] {
  const rows = db
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

export function getJournalStats(db: DatabaseSync, brand: string): {
  total: number;
  rated: number;
  avgRating: number | null;
  inProgress: number;
  failed: number;
} {
  const row = db
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

export function loadLearnings(brandPath: string): BrandLearnings | null {
  const path = join(brandPath, "learnings.json");
  if (!existsSync(path)) return null;
  return JSON.parse(readFileSync(path, "utf8")) as BrandLearnings;
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
