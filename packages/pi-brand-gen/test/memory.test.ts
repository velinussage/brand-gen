import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

import {
  appendJournal,
  completeJournal,
  defaultLearnings,
  failJournal,
  getJournalStats,
  getOrphanedEntries,
  getRecentEntries,
  initMemory,
  journalPathForWorkspace,
  loadLearnings,
  patchLearnings,
  rateJournalEntry,
  saveLearnings,
  learningsPathForWorkspace,
} from '../src/memory.ts';

test('journal lifecycle roundtrip works', () => {
  const dir = mkdtempSync(join(tmpdir(), 'brand-memory-'));
  appendJournal(dir, { id: 'j1', brand: 'acme', materialType: 'x-feed', status: 'in_progress' });
  completeJournal(dir, 'j1', {
    stopped_at: 'complete',
    result: { version_id: 'v42', image_paths: ['/tmp/v42.png'] },
  });
  const [entry] = getRecentEntries(dir, 'acme', 1);
  assert.equal(entry.id, 'j1');
  assert.equal(entry.status, 'complete');
  assert.equal(entry.versionId, 'v42');
  assert.equal(entry.outputPath, '/tmp/v42.png');
  assert.equal(journalPathForWorkspace(dir), join(dir, 'runs', 'journal.jsonl'));
});

test('failJournal marks entry failed', () => {
  const dir = mkdtempSync(join(tmpdir(), 'brand-memory-'));
  appendJournal(dir, { id: 'j2', brand: 'acme', status: 'in_progress' });
  failJournal(dir, 'j2', 'boom', 'generate');
  const [entry] = getRecentEntries(dir, 'acme', 1);
  assert.equal(entry.status, 'failed');
  assert.equal(entry.stoppedAt, 'generate');
  assert.equal(entry.feedback, 'boom');
});

test('orphan detection returns stale in_progress entries', () => {
  const dir = mkdtempSync(join(tmpdir(), 'brand-memory-'));
  appendJournal(dir, { id: 'fresh', brand: 'acme', status: 'in_progress' });
  appendJournal(dir, {
    id: 'stale',
    brand: 'acme',
    status: 'in_progress',
    createdAt: new Date(Date.now() - 15 * 60_000).toISOString(),
  });
  const stale = getOrphanedEntries(dir, 10);
  assert.equal(stale.length, 1);
  assert.equal(stale[0].id, 'stale');
});

test('rating updates and stats work', () => {
  const dir = mkdtempSync(join(tmpdir(), 'brand-memory-'));
  appendJournal(dir, { id: 'j3', brand: 'acme', status: 'complete' });
  rateJournalEntry(dir, 'j3', 4, 'solid');
  const stats = getJournalStats(dir, 'acme');
  assert.equal(stats.total, 1);
  assert.equal(stats.rated, 1);
  assert.equal(stats.avgRating, 4);
});

test('rating 0 persists as rejection', () => {
  const dir = mkdtempSync(join(tmpdir(), 'brand-memory-'));
  appendJournal(dir, { id: 'reject-me', brand: 'acme', status: 'complete' });
  rateJournalEntry(dir, 'reject-me', 0, 'rejected');
  const [entry] = getRecentEntries(dir, 'acme', 1);
  assert.equal(entry.rating, 0);
  assert.equal(entry.feedback, 'rejected');
});

test('completeJournal treats critique stop as complete and stores workflow route', () => {
  const dir = mkdtempSync(join(tmpdir(), 'brand-memory-'));
  appendJournal(dir, { id: 'j-critique', brand: 'acme', status: 'in_progress' });
  completeJournal(dir, 'j-critique', {
    stopped_at: 'critique',
    route: { route_key: 'generative_explore' },
    result: { version_id: 'v9', image_paths: ['/tmp/v9.png'] },
  });
  const [entry] = getRecentEntries(dir, 'acme', 1);
  assert.equal(entry.status, 'complete');
  assert.equal(entry.stoppedAt, 'critique');
  assert.equal(entry.workflowRoute, 'generative_explore');
});

test('legacy sqlite bridge still reads old journals', () => {
  const dir = mkdtempSync(join(tmpdir(), 'brand-memory-'));
  const db1 = initMemory(dir, 'acme');
  appendJournal(db1, { id: 'wal-a', brand: 'acme', status: 'complete' });
  const db2 = initMemory(dir, 'acme');
  const entries = getRecentEntries(db2, 'acme', 5);
  assert.equal(entries.length, 1);
  assert.equal(entries[0].id, 'wal-a');
  db2.close();
  db1.close();
});

test('learnings save/load/patch works', () => {
  const dir = mkdtempSync(join(tmpdir(), 'brand-memory-'));
  const learnings = defaultLearnings('acme');
  saveLearnings(dir, learnings);
  assert.equal(learningsPathForWorkspace(dir), join(dir, 'learnings.json'));
  let loaded = loadLearnings(dir);
  assert.ok(loaded);
  assert.equal(loaded?.brand, 'acme');
  patchLearnings(dir, 'colorInsights[0]', 'Use warm copper accents');
  patchLearnings(dir, 'modelPreferences[0]', 'nano-banana-2');
  loaded = loadLearnings(dir);
  assert.deepEqual(loaded?.colorInsights, ['Use warm copper accents']);
  assert.deepEqual(loaded?.modelPreferences, ['nano-banana-2']);
});
