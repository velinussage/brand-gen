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
  loadLearnings,
  patchLearnings,
  rateJournalEntry,
  saveLearnings,
} from '../src/memory.ts';

test('journal lifecycle roundtrip works', () => {
  const dir = mkdtempSync(join(tmpdir(), 'brand-memory-'));
  const db = initMemory(dir, 'acme');
  appendJournal(db, { id: 'j1', brand: 'acme', materialType: 'x-feed', status: 'in_progress' });
  completeJournal(db, 'j1', {
    stopped_at: 'complete',
    result: { version_id: 'v42', image_paths: ['/tmp/v42.png'] },
  });
  const [entry] = getRecentEntries(db, 'acme', 1);
  assert.equal(entry.id, 'j1');
  assert.equal(entry.status, 'complete');
  assert.equal(entry.versionId, 'v42');
  assert.equal(entry.outputPath, '/tmp/v42.png');
  db.close();
});

test('failJournal marks entry failed', () => {
  const dir = mkdtempSync(join(tmpdir(), 'brand-memory-'));
  const db = initMemory(dir, 'acme');
  appendJournal(db, { id: 'j2', brand: 'acme', status: 'in_progress' });
  failJournal(db, 'j2', 'boom', 'generate');
  const [entry] = getRecentEntries(db, 'acme', 1);
  assert.equal(entry.status, 'failed');
  assert.equal(entry.stoppedAt, 'generate');
  assert.equal(entry.feedback, 'boom');
  db.close();
});

test('orphan detection returns stale in_progress entries', () => {
  const dir = mkdtempSync(join(tmpdir(), 'brand-memory-'));
  const db = initMemory(dir, 'acme');
  appendJournal(db, { id: 'fresh', brand: 'acme', status: 'in_progress' });
  appendJournal(db, {
    id: 'stale',
    brand: 'acme',
    status: 'in_progress',
    createdAt: new Date(Date.now() - 15 * 60_000).toISOString(),
  });
  const stale = getOrphanedEntries(db, 10);
  assert.equal(stale.length, 1);
  assert.equal(stale[0].id, 'stale');
  db.close();
});

test('rating updates and stats work', () => {
  const dir = mkdtempSync(join(tmpdir(), 'brand-memory-'));
  const db = initMemory(dir, 'acme');
  appendJournal(db, { id: 'j3', brand: 'acme', status: 'complete' });
  rateJournalEntry(db, 'j3', 4, 'solid');
  const stats = getJournalStats(db, 'acme');
  assert.equal(stats.total, 1);
  assert.equal(stats.rated, 1);
  assert.equal(stats.avgRating, 4);
  db.close();
});

test('rating 0 persists as rejection', () => {
  const dir = mkdtempSync(join(tmpdir(), 'brand-memory-'));
  const db = initMemory(dir, 'acme');
  appendJournal(db, { id: 'reject-me', brand: 'acme', status: 'complete' });
  rateJournalEntry(db, 'reject-me', 0, 'rejected');
  const [entry] = getRecentEntries(db, 'acme', 1);
  assert.equal(entry.rating, 0);
  assert.equal(entry.feedback, 'rejected');
  db.close();
});

test('completeJournal treats critique stop as complete and stores workflow route', () => {
  const dir = mkdtempSync(join(tmpdir(), 'brand-memory-'));
  const db = initMemory(dir, 'acme');
  appendJournal(db, { id: 'j-critique', brand: 'acme', status: 'in_progress' });
  completeJournal(db, 'j-critique', {
    stopped_at: 'critique',
    route: { route_key: 'generative_explore' },
    result: { version_id: 'v9', image_paths: ['/tmp/v9.png'] },
  });
  const [entry] = getRecentEntries(db, 'acme', 1);
  assert.equal(entry.status, 'complete');
  assert.equal(entry.stoppedAt, 'critique');
  assert.equal(entry.workflowRoute, 'generative_explore');
  db.close();
});

test('WAL mode allows concurrent readers on the same journal db', () => {
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
  let loaded = loadLearnings(dir);
  assert.ok(loaded);
  assert.equal(loaded?.brand, 'acme');
  patchLearnings(dir, 'colorInsights[0]', 'Use warm copper accents');
  patchLearnings(dir, 'modelPreferences[0]', 'nano-banana-2');
  loaded = loadLearnings(dir);
  assert.deepEqual(loaded?.colorInsights, ['Use warm copper accents']);
  assert.deepEqual(loaded?.modelPreferences, ['nano-banana-2']);
});
