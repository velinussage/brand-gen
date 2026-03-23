import { existsSync, mkdirSync, readFileSync, writeFileSync, renameSync } from "node:fs";
import { dirname, join } from "node:path";

import type { PluginConfig, RuntimeStatusMarker } from "./types.ts";
import { journalPathForWorkspace, learningsPathForWorkspace } from "./memory.ts";
import { resolveActiveWorkspace } from "./workspace.ts";

function ensureDir(path: string): void {
  mkdirSync(path, { recursive: true });
}

function atomicWrite(path: string, content: string): void {
  ensureDir(dirname(path));
  const tmp = `${path}.${process.pid}.${Date.now()}.tmp`;
  writeFileSync(tmp, content, "utf8");
  renameSync(tmp, path);
}

export function runtimeStatusDir(brandGenDir: string): string {
  return join(brandGenDir, "runtime-status", "plugins");
}

export function runtimeStatusPath(brandGenDir: string, pluginName: string): string {
  return join(runtimeStatusDir(brandGenDir), `${pluginName}.json`);
}

export function buildRuntimeStatusMarker(
  pluginName: string,
  config: PluginConfig,
  extra: Record<string, unknown> = {},
): RuntimeStatusMarker {
  const state = resolveActiveWorkspace(config.brandGenDir);
  const journalPath = state.workspaceDir ? journalPathForWorkspace(state.workspaceDir) : null;
  const learningsPath = state.workspaceDir ? learningsPathForWorkspace(state.workspaceDir) : null;
  const brandRootMode: RuntimeStatusMarker["brandRootMode"] =
    state.workspaceKind === "session"
      ? "session"
      : state.workspaceKind === "saved_brand"
        ? "saved_brand"
        : "unresolved";
  const journalBackend: RuntimeStatusMarker["journalBackend"] =
    state.workspaceDir && state.workspaceKind !== "unresolved"
      ? "workspace-jsonl"
      : state.savedBrandDir && existsSync(join(state.savedBrandDir, "brand.sqlite"))
        ? "legacy-sqlite-bridge"
        : state.workspaceKind === "unresolved"
          ? "unresolved"
          : "workspace-jsonl";
  const timestamp = new Date().toISOString();
  return {
    pluginName,
    brandGenDir: state.brandGenDir,
    activeBrand: state.activeBrand,
    activeSession: state.activeSession,
    workspaceKind: state.workspaceKind,
    workspaceDir: state.workspaceDir,
    workspaceIdentityPath: state.workspaceIdentityPath,
    journalPath,
    learningsPath,
    journalBackend,
    brandRootMode,
    timestamp,
    updatedAt: timestamp,
    extra: Object.keys(extra).length ? extra : undefined,
  };
}

export function writeRuntimeStatusMarker(
  pluginName: string,
  config: PluginConfig,
  extra: Record<string, unknown> = {},
): RuntimeStatusMarker {
  const marker = buildRuntimeStatusMarker(pluginName, config, extra);
  const path = runtimeStatusPath(marker.brandGenDir, pluginName);
  atomicWrite(path, JSON.stringify(marker, null, 2) + "\n");
  return marker;
}

export function readRuntimeStatusMarker(
  brandGenDir: string,
  pluginName: string,
): RuntimeStatusMarker | null {
  const path = runtimeStatusPath(brandGenDir, pluginName);
  if (!existsSync(path)) return null;
  try {
    const parsed = JSON.parse(readFileSync(path, "utf8"));
    return parsed && typeof parsed === "object" ? (parsed as RuntimeStatusMarker) : null;
  } catch {
    return null;
  }
}

