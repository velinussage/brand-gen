import test from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, mkdtempSync, mkdirSync, readFileSync, readdirSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';

import {
  parsePluginConfig,
  resolveActiveWorkspace,
  buildBrandGenContext,
  mapGenerateParams,
  deriveGenerationPolicy,
  runHeartbeatCycle,
  writeRuntimeStatusMarker,
} from '../src/core.ts';
import {
  defaultBrandIterateMcpPath,
  preferredPythonForRepo,
  repoRootFromModuleUrl,
  resolvePiRuntimePaths,
} from '../src/runtime-paths.ts';
import { createBrandSearchTool, createCanonicalBrandTools } from '../src/tool.ts';
import { CANONICAL_TOOLS } from '../../brand-gen-core/src/index.ts';
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

test('Pi canonical tool registration exposes all 45 brand verbs', () => {
  const cfg = parsePluginConfig({ brandGenDir: '/tmp/brand-gen' });
  const bridge = new FakeBridge({});
  const tools = createCanonicalBrandTools(bridge as any, cfg);
  const names = tools.map((tool) => tool.name).sort();
  const canonicalNames = CANONICAL_TOOLS.map((tool) => tool.name).sort();
  assert.equal(canonicalNames.length, 45);
  assert.deepEqual(names, canonicalNames);
  assert.ok(tools.every((tool) => tool.name.startsWith('brand_')));
  const scratchpad = tools.find((tool) => tool.name === 'brand_build_generation_scratchpad');
  assert.ok(scratchpad);
  assert.deepEqual((scratchpad!.parameters as any).required, ['plan']);
  const props = (scratchpad!.parameters as any).properties;
  for (const key of ['prompt', 'generation_mode', 'aspect_ratio', 'duration', 'source_version', 'reference_assets', 'motion_reference', 'base_image']) {
    assert.ok(props[key], `scratchpad schema missing ${key}`);
  }
  const execute = tools.find((tool) => tool.name === 'brand_execute_run');
  assert.ok(execute);
  assert.ok((execute!.parameters as any).properties.allow_blocking, 'execute schema missing allow_blocking');
  assert.ok(tools.find((tool) => tool.name === 'brand_source_knowledge'));
});

test('Pi brand-agent frontmatter only references registered canonical tools', () => {
  const repoRoot = resolve(repoRootFromModuleUrl(import.meta.url));
  const agentsDir = join(repoRoot, '.pi', 'agents');
  const registered = new Set(CANONICAL_TOOLS.map((tool) => tool.name));
  const offenders: string[] = [];
  for (const file of readdirSync(agentsDir).filter((name) => name.startsWith('brand-') && name.endsWith('.md'))) {
    const text = readFileSync(join(agentsDir, file), 'utf8');
    const match = text.match(/^tools:\s*"([^"]*)"/m);
    if (!match) continue;
    const declared = match[1].split(',').map((part) => part.trim()).filter(Boolean);
    for (const tool of declared) {
      if (!registered.has(tool)) offenders.push(`${file}: ${tool}`);
    }
  }
  assert.deepEqual(offenders, []);
});

test('parsePluginConfig applies pi defaults', () => {
  const cfg = parsePluginConfig({});
  assert.equal(cfg.brandGenDir.endsWith('.brand-gen'), true);
  assert.equal(cfg.brandIterateMcpPath, '');
  // autoHeartbeat defaults off — the timer runs a full generation pipeline,
  // not a health check. Users must opt in explicitly.
  assert.equal(cfg.autoHeartbeat, false);
  assert.equal(cfg.heartbeatIntervalMinutes, 60);
});

test('parsePluginConfig respects explicit autoHeartbeat: true opt-in', () => {
  const cfg = parsePluginConfig({ autoHeartbeat: true });
  assert.equal(cfg.autoHeartbeat, true);
});

test('resolvePiRuntimePaths finds the repo backend from the package checkout', () => {
  const repoRoot = repoRootFromModuleUrl(import.meta.url);
  const mcpPath = defaultBrandIterateMcpPath(repoRoot);
  assert.ok(existsSync(mcpPath));
  const runtime = resolvePiRuntimePaths(import.meta.url);
  assert.equal(runtime.repoRoot, repoRoot);
  assert.equal(runtime.mcpPath, mcpPath);
});

test('preferredPythonForRepo prefers a repo-local venv when present', () => {
  const root = mkdtempSync(join(tmpdir(), 'pi-brand-python-'));
  mkdirSync(join(root, '.venv', 'bin'), { recursive: true });
  writeFileSync(join(root, '.venv', 'bin', 'python'), '');
  assert.equal(preferredPythonForRepo(root), join(root, '.venv', 'bin', 'python'));
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
