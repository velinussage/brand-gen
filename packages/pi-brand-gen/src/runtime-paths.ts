import { existsSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

export function repoRootFromModuleUrl(moduleUrl: string): string {
  return resolve(dirname(fileURLToPath(moduleUrl)), "../../..");
}

export function defaultBrandIterateMcpPath(repoRoot: string): string {
  return resolve(repoRoot, "brand_gen", "brand_iterate_mcp.py");
}

export function preferredPythonForRepo(repoRoot: string): string {
  const candidates = [
    resolve(repoRoot, ".venv", "bin", "python"),
    resolve(repoRoot, ".venv", "Scripts", "python.exe"),
  ];
  return candidates.find((candidate) => existsSync(candidate)) ?? "python3";
}

export function resolvePiRuntimePaths(moduleUrl: string, explicitMcpPath?: string): {
  repoRoot: string;
  mcpPath: string;
  pythonCommand: string;
} {
  const repoRoot = repoRootFromModuleUrl(moduleUrl);
  const mcpPath =
    typeof explicitMcpPath === "string" && explicitMcpPath.trim()
      ? explicitMcpPath
      : defaultBrandIterateMcpPath(repoRoot);
  if (!existsSync(mcpPath)) {
    throw new Error(
      `Could not locate brand-gen MCP backend at ${mcpPath}. Register the Pi extension from a normal brand-gen checkout or set brandIterateMcpPath explicitly.`,
    );
  }
  return {
    repoRoot,
    mcpPath,
    pythonCommand: preferredPythonForRepo(repoRoot),
  };
}
