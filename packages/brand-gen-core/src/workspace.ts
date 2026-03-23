import { existsSync, readFileSync } from "node:fs";
import { homedir } from "node:os";
import { join, resolve } from "node:path";
import type { ActiveWorkspace, BrandGenConfig, PluginConfig } from "./types.ts";

export function expandHome(value: string): string {
  if (!value) return value;
  if (value === "~") return homedir();
  if (value.startsWith("~/")) return join(homedir(), value.slice(2));
  return value;
}

export function normalizeWorkspaceRoot(value: string): string {
  return resolve(expandHome(value));
}

export function readJsonFile<T>(path: string): T | null {
  try {
    if (!existsSync(path)) return null;
    return JSON.parse(readFileSync(path, "utf8")) as T;
  } catch {
    return null;
  }
}

export function parsePluginConfig(raw: Record<string, unknown> | undefined): PluginConfig {
  const brandGenDir = normalizeWorkspaceRoot(
    typeof raw?.brandGenDir === "string" && raw.brandGenDir.trim() ? raw.brandGenDir : "~/.brand-gen",
  );
  const brandIterateMcpPath = expandHome(
    typeof raw?.brandIterateMcpPath === "string" ? raw.brandIterateMcpPath : "",
  );
  const logoIterateMcpPath = expandHome(
    typeof raw?.logoIterateMcpPath === "string" && raw.logoIterateMcpPath.trim()
      ? raw.logoIterateMcpPath
      : "",
  );
  const heartbeatRaw = Number(raw?.heartbeatIntervalMinutes ?? 60);
  return {
    brandGenDir,
    brandIterateMcpPath,
    logoIterateMcpPath,
    approvalMode:
      raw?.approvalMode === "all" || raw?.approvalMode === "none" ? raw.approvalMode : "output_only",
    logLevel:
      raw?.logLevel === "debug" || raw?.logLevel === "warn" || raw?.logLevel === "error"
        ? raw.logLevel
        : "info",
    heartbeatIntervalMinutes: Number.isFinite(heartbeatRaw) && heartbeatRaw > 0 ? heartbeatRaw : 60,
    autoHeartbeat: raw?.autoHeartbeat !== false,
  };
}

export function loadBrandGenConfig(brandGenDir: string): BrandGenConfig {
  return readJsonFile<BrandGenConfig>(join(brandGenDir, "config.json")) ?? {};
}

export function deriveBrandFromWorkspace(workspaceDir: string, config: BrandGenConfig): string | null {
  const identity = readJsonFile<Record<string, unknown>>(join(workspaceDir, "brand-identity.json"));
  const profile = readJsonFile<Record<string, unknown>>(join(workspaceDir, "brand-profile.json"));
  for (const candidate of [identity, profile]) {
    const sessionContext = candidate?.session_context;
    if (sessionContext && typeof sessionContext === "object") {
      const seeded = (sessionContext as Record<string, unknown>).seeded_from_brand;
      if (typeof seeded === "string" && seeded.trim()) return seeded.trim();
    }
  }
  return typeof config.active === "string" && config.active.trim() ? config.active.trim() : null;
}

export function resolveActiveWorkspace(
  brandGenDir: string,
  config = loadBrandGenConfig(brandGenDir),
): ActiveWorkspace {
  const resolvedBrandGenDir = normalizeWorkspaceRoot(brandGenDir);
  const activeSession =
    typeof config.activeSession === "string" && config.activeSession.trim()
      ? config.activeSession.trim()
      : null;
  const active =
    typeof config.active === "string" && config.active.trim() ? config.active.trim() : null;

  if (activeSession) {
    const workspaceDir = join(resolvedBrandGenDir, "sessions", activeSession, "brand-materials");
    if (existsSync(workspaceDir)) {
      const activeBrand = deriveBrandFromWorkspace(workspaceDir, config) ?? active;
      const savedBrandDir = activeBrand ? join(resolvedBrandGenDir, "brands", activeBrand) : null;
      return {
        brandGenDir: resolvedBrandGenDir,
        workspaceKind: "session",
        activeBrand,
        activeSession,
        workspaceDir,
        savedBrandDir,
        savedIdentityPath: savedBrandDir ? join(savedBrandDir, "brand-identity.json") : null,
        workspaceIdentityPath: join(workspaceDir, "brand-identity.json"),
      };
    }
  }

  if (active) {
    const workspaceDir = join(resolvedBrandGenDir, "brands", active);
    if (existsSync(workspaceDir)) {
      return {
        brandGenDir: resolvedBrandGenDir,
        workspaceKind: "saved_brand",
        activeBrand: active,
        activeSession: null,
        workspaceDir,
        savedBrandDir: workspaceDir,
        savedIdentityPath: join(workspaceDir, "brand-identity.json"),
        workspaceIdentityPath: join(workspaceDir, "brand-identity.json"),
      };
    }
  }

  const envWorkspace = process.env.BRAND_DIR ? resolve(expandHome(process.env.BRAND_DIR)) : null;
  if (envWorkspace && existsSync(envWorkspace)) {
    const activeBrand = deriveBrandFromWorkspace(envWorkspace, config) ?? active;
    const savedBrandDir = activeBrand ? join(resolvedBrandGenDir, "brands", activeBrand) : null;
    return {
      brandGenDir: resolvedBrandGenDir,
      workspaceKind: activeSession ? "session" : "saved_brand",
      activeBrand,
      activeSession,
      workspaceDir: envWorkspace,
      savedBrandDir,
      savedIdentityPath: savedBrandDir ? join(savedBrandDir, "brand-identity.json") : null,
      workspaceIdentityPath: join(envWorkspace, "brand-identity.json"),
    };
  }

  return {
    brandGenDir: resolvedBrandGenDir,
    workspaceKind: "unresolved",
    activeBrand: active,
    activeSession,
    workspaceDir: null,
    savedBrandDir: active ? join(resolvedBrandGenDir, "brands", active) : null,
    savedIdentityPath: active ? join(resolvedBrandGenDir, "brands", active, "brand-identity.json") : null,
    workspaceIdentityPath: null,
  };
}

export function loadBrandIdentitySummary(identity: Record<string, unknown> | null): {
  brandName: string;
  business: string;
  audience: string;
  tone: string;
  productContext: string;
} {
  const brand = (identity?.brand as Record<string, unknown> | undefined) ?? {};
  const identityCore = (identity?.identity_core as Record<string, unknown> | undefined) ?? {};
  const messaging = (identity?.messaging as Record<string, unknown> | undefined) ?? {};
  const toneWords = Array.isArray(identityCore.tone_words)
    ? (identityCore.tone_words as string[]).slice(0, 6).join(", ")
    : "";
  const audience =
    Array.isArray(messaging.audiences) && messaging.audiences.length
      ? (messaging.audiences as string[]).join(", ")
      : "builders, product teams, and AI-agent operators";
  const productContext = [
    typeof messaging.elevator === "string" ? messaging.elevator : "",
    Array.isArray(messaging.value_propositions)
      ? (messaging.value_propositions as string[]).slice(0, 2).join(" | ")
      : "",
  ]
    .filter(Boolean)
    .join(" ");
  return {
    brandName: typeof brand.name === "string" ? brand.name : "Brand",
    business:
      typeof brand.summary === "string" && brand.summary.trim()
        ? brand.summary
        : typeof messaging.elevator === "string"
          ? messaging.elevator
          : "",
    audience,
    tone: toneWords,
    productContext,
  };
}
