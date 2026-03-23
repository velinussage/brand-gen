import test from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, mkdtempSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

import {
  parsePluginConfig,
  resolveActiveWorkspace,
  buildBrandGenContext,
  mapGenerateParams,
  deriveGenerationPolicy,
  runHeartbeatCycle,
  writeRuntimeStatusMarker,
} from '../src/core.ts';
import { createBrandSearchTool } from '../src/tool.ts';
import { defaultLearnings, saveLearnings, appendJournal, getRecentEntries, journalPathForWorkspace } from '../src/memory.ts';

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
  writeFileSync(join(brandDir, 'brand-identity.json'), JSON.stringify({ brand: { name: 'Acme Saved' }, messaging: { tagline: 'Reusable brand systems for modern teams' } }));
  writeFileSync(join(workspaceDir, 'brand-identity.json'), JSON.stringify({ brand: { name: 'Acme Session' }, messaging: { tagline: 'Session-specific brand systems' } }));
  writeFileSync(join(workspaceDir, 'brand-profile.json'), JSON.stringify({ session_context: { seeded_from_brand: 'acme' } }));
  saveLearnings(workspaceDir, defaultLearnings('acme'));
  appendJournal(workspaceDir, { id: 'j1', brand: 'acme', status: 'complete', materialType: 'social' });
  const bridge = new FakeBridge({
    brand_context_snapshot: { workspace: { brandGenDir: root, activeBrand: 'acme', activeSession: 'sess-2' } },
    brand_workspace_status: { workspaceKind: 'session', root: root },
    brand_capabilities: { tools: [] },
    brand_show_blackboard: { decisions: [{ decision: 'Use product-led proof' }] },
    brand_show_iteration_memory: { copy_notes: ['Avoid invented claims'] },
  });
  bridge.listTools = async () => [
    { name: 'brand_pipeline' },
    { name: 'brand_show_blackboard' },
    { name: 'brand_show_iteration_memory' },
    { name: 'brand_context_snapshot' },
    { name: 'brand_workspace_status' },
    { name: 'brand_capabilities' },
  ];
  const context = await buildBrandGenContext(bridge as any, { brandGenDir: root, brandIterateMcpPath: '/tmp/server.py', logoIterateMcpPath: '', approvalMode: 'output_only', logLevel: 'info', heartbeatIntervalMinutes: 60, autoHeartbeat: true });
  assert.equal(context.activeBrand, 'acme');
  assert.equal(context.workspaceKind, 'session');
  assert.equal((context.identity?.brand as any)?.name, 'Acme Session');
  assert.equal(context.recentJournal.length, 1);
  assert.ok(bridge.calls.some((call) => call.name === 'brand_context_snapshot'));
});

test('writeRuntimeStatusMarker writes under runtime-status/plugins', () => {
  const root = mkdtempSync(join(tmpdir(), 'pi-brand-'));
  mkdirSync(join(root, 'brands', 'acme'), { recursive: true });
  writeFileSync(join(root, 'config.json'), JSON.stringify({ active: 'acme' }));
  const marker = writeRuntimeStatusMarker('pi-brand-gen', {
    brandGenDir: root,
    brandIterateMcpPath: '/tmp/server.py',
    logoIterateMcpPath: '',
    approvalMode: 'output_only',
    logLevel: 'info',
    heartbeatIntervalMinutes: 60,
    autoHeartbeat: true,
  });
  assert.equal(marker.brandGenDir, root);
  assert.equal(marker.workspaceKind, 'saved_brand');
  assert.equal(journalPathForWorkspace(join(root, 'brands', 'acme')), join(root, 'brands', 'acme', 'runs', 'journal.jsonl'));
  assert.ok(marker.timestamp);
  const markerPath = join(root, 'runtime-status', 'plugins', 'pi-brand-gen.json');
  assert.ok(existsSync(markerPath));
  const written = JSON.parse(readFileSync(markerPath, 'utf8'));
  assert.equal(written.pluginName, 'pi-brand-gen');
  assert.equal(written.brandGenDir, root);
});

test('mapGenerateParams produces expanded brand_pipeline payload', () => {
  assert.deepEqual(
    mapGenerateParams({
      materialType: 'social',
      goal: 'Explain',
      purpose: 'social',
      targetSurface: 'X feed',
      promptSeed: 'Show product truth',
      tag: 'launch',
      productTruthExpression: 'governed skill network',
      preserve: ['warm palette'],
      ban: ['invented text'],
      sourceVersion: 'v012',
      allowBlocking: true,
    }),
    {
      material_type: 'social',
      goal: 'Explain',
      purpose: 'social',
      target_surface: 'X feed',
      mode: 'hybrid',
      prompt_seed: 'Show product truth',
      max_iterations: 1,
      tag: 'launch',
      product_truth_expression: 'governed skill network',
      preserve: ['warm palette'],
      ban: ['invented text'],
      source_version: 'v012',
      allow_blocking: true,
    },
  );
});

test('deriveGenerationPolicy skips low-rated streaks', () => {
  const policy = deriveGenerationPolicy([
    { id: 'a', brand: 'acme', status: 'complete', rating: 2, materialType: 'social', goal: 'Explain what the brand/product is clearly' },
    { id: 'b', brand: 'acme', status: 'complete', rating: 1, materialType: 'browser-illustration', goal: 'Show product truth with stronger branding' },
    { id: 'c', brand: 'acme', status: 'complete', rating: 2, materialType: 'feature-illustration', goal: 'Create a social asset with real brand language' },
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
  writeFileSync(join(workspaceDir, 'brand-identity.json'), JSON.stringify({ brand: { name: 'Acme Session' }, messaging: { tagline: 'Session-specific brand systems' } }));
  writeFileSync(join(workspaceDir, 'brand-profile.json'), JSON.stringify({ session_context: { seeded_from_brand: 'acme' } }));
  const bridge = new FakeBridge({ brand_explore: { directions: ['product-led'] }, brand_pipeline: { stopped_at: 'complete', result: { version_id: 'v7', image_paths: ['/tmp/v7.png'], agent_review_path: '/tmp/v7-agent-review.json', visual_review_status: 'pending', vlm_critique: { approved: true } }, route: { route_key: 'generative_explore' } }, brand_review: { summary: 'Looks strong' } });
  const result = await runHeartbeatCycle(bridge as any, { brandGenDir: root, brandIterateMcpPath: '/tmp/server.py', logoIterateMcpPath: '', approvalMode: 'output_only', logLevel: 'info', heartbeatIntervalMinutes: 60, autoHeartbeat: true });
  assert.equal((result.discover as any).skipped, false);
  assert.equal((result.generate as any).skipped, false);
  const exploreCall = bridge.calls.find((call) => call.name === 'brand_explore');
  assert.deepEqual(exploreCall?.args.sources, ['ramotion', 'koto-pairpoint']);
  const recent = getRecentEntries(workspaceDir, 'acme', 5);
  assert.ok(recent.some((entry: any) => entry.materialType === 'discover'));
  assert.ok(recent.some((entry: any) => entry.materialType === 'social' && entry.agentReviewPath === '/tmp/v7-agent-review.json' && entry.visualReviewStatus === 'pending'));
  assert.ok(recent.some((entry: any) => entry.materialType === 'heartbeat-cycle'));
  assert.equal(bridge.calls.some((call) => call.name === 'brand_review'), false);
});

test('brand_search get_journal_stats returns a stats wrapper', async () => {
  const root = mkdtempSync(join(tmpdir(), 'pi-brand-stats-'));
  const brandDir = join(root, 'brands', 'acme');
  mkdirSync(brandDir, { recursive: true });
  writeFileSync(join(root, 'config.json'), JSON.stringify({ active: 'acme' }));
  writeFileSync(join(brandDir, 'brand-identity.json'), JSON.stringify({ brand: { name: 'Acme Saved' } }));
  appendJournal(brandDir, { id: 'j1', brand: 'acme', status: 'complete' });
  const tool = createBrandSearchTool({
    isReady: () => true,
    callTool: async () => ({ content: [{ type: 'text', text: '{}' }] }),
    listTools: async () => [],
  } as any, {
    brandGenDir: root,
    brandIterateMcpPath: '/tmp/server.py',
    logoIterateMcpPath: '',
    approvalMode: 'output_only',
    logLevel: 'info',
    heartbeatIntervalMinutes: 60,
    autoHeartbeat: true,
  });
  const result = await tool.execute({ action: 'get_journal_stats', params: {} as Record<string, unknown> }) as any;
  assert.ok(result.details);
  assert.equal(result.details.stats.total, 1);
  assert.equal(result.details.stats.rated, 0);
});

test('brand_search list_brands calls brand_list as JSON', async () => {
  const tool = createBrandSearchTool({
    isReady: () => true,
    callTool: async (name: string, args: Record<string, unknown>) => {
      assert.equal(name, 'brand_list');
      assert.equal(args.format, 'json');
      return { content: [{ type: 'text', text: JSON.stringify([{ key: 'acme', active: true }]) }] };
    },
    listTools: async () => [],
  } as any, {
    brandGenDir: '/tmp/brand-gen',
    brandIterateMcpPath: '/tmp/server.py',
    logoIterateMcpPath: '',
    approvalMode: 'output_only',
    logLevel: 'info',
    heartbeatIntervalMinutes: 60,
    autoHeartbeat: true,
  });
  const result = await tool.execute({ action: 'list_brands', params: {} as Record<string, unknown> }) as any;
  assert.deepEqual(result.details.brands, [{ key: 'acme', active: true }]);
});
