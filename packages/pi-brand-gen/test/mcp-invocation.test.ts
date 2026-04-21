import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, mkdirSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';

import { resolveMcpInvocation } from '../../brand-gen-core/src/mcp-invocation.ts';

test('resolveMcpInvocation launches brand_gen modules via -m with cwd=repoRoot', () => {
  // Build a fake repo layout: <tmp>/project/brand_gen/{__init__.py, brand_iterate_mcp.py}
  const root = mkdtempSync(join(tmpdir(), 'resolve-mcp-'));
  const project = join(root, 'project');
  const pkg = join(project, 'brand_gen');
  mkdirSync(pkg, { recursive: true });
  writeFileSync(join(pkg, '__init__.py'), '');
  const mcpPath = join(pkg, 'brand_iterate_mcp.py');
  writeFileSync(mcpPath, '# fake');

  const invocation = resolveMcpInvocation(mcpPath);
  assert.deepEqual(invocation.args, ['-m', 'brand_gen.brand_iterate_mcp']);
  assert.equal(invocation.cwd, project);
  assert.equal(invocation.command, 'python3');
});

test('resolveMcpInvocation honors custom python command', () => {
  const root = mkdtempSync(join(tmpdir(), 'resolve-mcp-'));
  const pkg = join(root, 'brand_gen');
  mkdirSync(pkg, { recursive: true });
  writeFileSync(join(pkg, '__init__.py'), '');
  const mcpPath = join(pkg, 'logo_iterate_mcp.py');
  writeFileSync(mcpPath, '');

  const invocation = resolveMcpInvocation(mcpPath, { python: '/opt/venv/bin/python' });
  assert.equal(invocation.command, '/opt/venv/bin/python');
  assert.deepEqual(invocation.args, ['-m', 'brand_gen.logo_iterate_mcp']);
  assert.equal(invocation.cwd, root);
});

test('resolveMcpInvocation falls back to script mode when package marker is missing', () => {
  // A .py file sitting under a brand_gen dir WITHOUT __init__.py can't be
  // launched as a module — fall back to direct invocation.
  const root = mkdtempSync(join(tmpdir(), 'resolve-mcp-'));
  const pkg = join(root, 'brand_gen');
  mkdirSync(pkg, { recursive: true });
  const mcpPath = join(pkg, 'brand_iterate_mcp.py');
  writeFileSync(mcpPath, '');

  const invocation = resolveMcpInvocation(mcpPath);
  assert.deepEqual(invocation.args, [resolve(mcpPath)]);
  assert.equal(invocation.cwd, undefined);
});

test('resolveMcpInvocation falls back to script mode for non-brand_gen paths', () => {
  const root = mkdtempSync(join(tmpdir(), 'resolve-mcp-'));
  const pkg = join(root, 'logo_gen');
  mkdirSync(pkg, { recursive: true });
  writeFileSync(join(pkg, '__init__.py'), '');
  const mcpPath = join(pkg, 'iterate.py');
  writeFileSync(mcpPath, '');

  const invocation = resolveMcpInvocation(mcpPath);
  assert.deepEqual(invocation.args, [resolve(mcpPath)]);
  assert.equal(invocation.cwd, undefined);
});

test('resolveMcpInvocation returns empty args when path is blank', () => {
  const invocation = resolveMcpInvocation('');
  assert.deepEqual(invocation.args, []);
  assert.equal(invocation.command, 'python3');
  assert.equal(invocation.cwd, undefined);
});

test('resolveMcpInvocation leaves non-.py paths untouched (script invocation)', () => {
  const invocation = resolveMcpInvocation('/usr/local/bin/my-mcp-server');
  assert.deepEqual(invocation.args, ['/usr/local/bin/my-mcp-server']);
  assert.equal(invocation.cwd, undefined);
});
