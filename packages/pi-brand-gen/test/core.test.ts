import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, mkdirSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

import {
  parsePluginConfig,
  resolveActiveWorkspace,
  buildBrandGenContext,
  mapGenerateParams,
  deriveGenerationPolicy,
  runHeartbeatCycle,
} from '../src/core.ts';
import { defaultLearnings, saveLearnings, initMemory, appendJournal, getRecentEntries } from '../src/memory.ts';

class FakeBridge {
  results: Record<string, unknown>;
  calls: Array<{ name: string; args: Record<string, unknown> }>;
  constructor(results: Record<string, unknown>) {
    this.results = results;
    this.calls = [];
  }
  isReady() { return true; }
  async callTool(name: string, args: Record<string, unknown> = {}) {
    this.calls.push({ name, args });
    const payload = this.results[name];
    return { content: [{ type: 'text', text: JSON.stringify(payload ?? {}) }] };
  }
  async listTools() {
    return [{ name: 'brand_pipeline' }, { name: 'brand_show_blackboard' }];
  }
}

test('parsePluginConfig applies pi defaults', () => {
  const cfg = parsePluginConfig({ brandIterateMcpPath: '/tmp/server.py' });
  assert.equal(cfg.brandGenDir.endsWith('.brand-gen'), true);
  assert.equal(cfg.autoHeartbeat, true);
  assert.equal(cfg.heartbeatIntervalMinutes, 60);
});

test('resolveActiveWorkspace prefers activeSession and seeded_from_brand', () => {
  const root = mkdtempSync(join(tmpdir(), 'pi-brand-'));
  mkdirSync(join(root, 'brands', 'acme'), { recursive: true });
  mkdirSync(join(root, 'sessions', 'sess-1', 'brand-materials'), { recursive: true });
  writeFileSync(join(root, 'config.json'), JSON.stringify({ active: 'acme', activeSession: 'sess-1' }));
  writeFileSync(join(root, 'sessions', 'sess-1', 'brand-materials', 'brand-profile.json'), JSON.stringify({ session_context: { seeded_from_brand: 'acme' } }));
  const resolved = resolveActiveWorkspace(root, { active: 'acme', activeSession: 'sess-1' });
  assert.equal(resolved.activeBrand, 'acme');
  assert.equal(resolved.activeSession, 'sess-1');
});

test('buildBrandGenContext combines saved brand and session state', async () => {
  const root = mkdtempSync(join(tmpdir(), 'pi-brand-'));
  const brandDir = join(root, 'brands', 'acme');
  const workspaceDir = join(root, 'sessions', 'sess-2', 'brand-materials');
  mkdirSync(brandDir, { recursive: true });
  mkdirSync(workspaceDir, { recursive: true });
  writeFileSync(join(root, 'config.json'), JSON.stringify({ active: 'acme', activeSession: 'sess-2' }));
  writeFileSync(join(brandDir, 'brand-identity.json'), JSON.stringify({ brand: { name: 'Acme' }, messaging: { tagline: 'Reusable brand systems for modern teams' } }));
  writeFileSync(join(workspaceDir, 'brand-profile.json'), JSON.stringify({ session_context: { seeded_from_brand: 'acme' } }));
  saveLearnings(brandDir, defaultLearnings('acme'));
  const db = initMemory(brandDir, 'acme');
  appendJournal(db, { id: 'j1', brand: 'acme', status: 'complete', materialType: 'x-feed' });
  db.close();
  const bridge = new FakeBridge({ brand_show_blackboard: { decisions: [{ decision: 'Use product-led proof' }] }, brand_show_iteration_memory: { copy_notes: ['Avoid invented claims'] } });
  const context = await buildBrandGenContext(bridge as any, { brandGenDir: root, brandIterateMcpPath: '/tmp/server.py', approvalMode: 'output_only', logLevel: 'info', heartbeatIntervalMinutes: 60, autoHeartbeat: true });
  assert.equal(context.activeBrand, 'acme');
  assert.equal((context.identity?.brand as any)?.name, 'Acme');
  assert.equal(context.recentJournal.length, 1);
});

test('mapGenerateParams produces brand_pipeline payload', () => {
  assert.deepEqual(mapGenerateParams({ materialType: 'x-feed', goal: 'Explain', purpose: 'social', targetSurface: 'X feed', promptSeed: 'Show product truth' }), {
    material_type: 'x-feed', goal: 'Explain', purpose: 'social', target_surface: 'X feed', mode: 'hybrid', prompt_seed: 'Show product truth', max_iterations: 1,
  });
});

test('deriveGenerationPolicy skips low-rated streaks', () => {
  const policy = deriveGenerationPolicy([
    { id: 'a', brand: 'acme', status: 'complete', rating: 2, materialType: 'x-feed', goal: 'Explain what the brand/product is clearly' },
    { id: 'b', brand: 'acme', status: 'complete', rating: 1, materialType: 'browser-illustration', goal: 'Show product truth with stronger branding' },
    { id: 'c', brand: 'acme', status: 'complete', rating: 2, materialType: 'product-banner', goal: 'Create a social asset with real brand language' },
  ], 'output_only');
  assert.equal(policy.skip, true);
});

test('runHeartbeatCycle performs discover + generate with source enforcement', async () => {
  const root = mkdtempSync(join(tmpdir(), 'pi-brand-heartbeat-'));
  const brandDir = join(root, 'brands', 'acme');
  const workspaceDir = join(root, 'sessions', 'sess-3', 'brand-materials');
  mkdirSync(brandDir, { recursive: true });
  mkdirSync(workspaceDir, { recursive: true });
  writeFileSync(join(root, 'config.json'), JSON.stringify({ active: 'acme', activeSession: 'sess-3' }));
  writeFileSync(join(brandDir, 'brand-identity.json'), JSON.stringify({ brand: { name: 'Acme', summary: 'Reusable brand system for modern teams' }, identity_core: { tone_words: ['confident'] }, messaging: { tagline: 'Reusable brand systems for modern teams', elevator: 'Teams curate reusable brand systems.', value_propositions: ['Reusable assets', 'Shared standards'] } }));
  writeFileSync(join(brandDir, 'inspirations.json'), JSON.stringify({ sources: ['ramotion', 'koto-pairpoint'] }));
  writeFileSync(join(workspaceDir, 'brand-profile.json'), JSON.stringify({ session_context: { seeded_from_brand: 'acme' } }));
  const bridge = new FakeBridge({ brand_explore: { directions: ['product-led'] }, brand_pipeline: { stopped_at: 'complete', result: { version_id: 'v7', image_paths: ['/tmp/v7.png'], vlm_critique: { approved: true } }, route: { route_key: 'generative_explore' } }, brand_review: { summary: 'Looks strong' } });
  const result = await runHeartbeatCycle(bridge as any, { brandGenDir: root, brandIterateMcpPath: '/tmp/server.py', approvalMode: 'output_only', logLevel: 'info', heartbeatIntervalMinutes: 60, autoHeartbeat: true });
  assert.equal((result.discover as any).skipped, false);
  assert.equal((result.generate as any).skipped, false);
  const exploreCall = bridge.calls.find((call) => call.name === 'brand_explore');
  assert.deepEqual(exploreCall?.args.sources, ['ramotion', 'koto-pairpoint']);
  const db = initMemory(brandDir, 'acme');
  const recent = getRecentEntries(db, 'acme', 5);
  assert.ok(recent.some((entry) => entry.materialType === 'discover'));
  assert.ok(recent.some((entry) => entry.materialType === 'x-feed'));
  assert.ok(recent.some((entry) => entry.materialType === 'heartbeat-cycle'));
  db.close();
});
