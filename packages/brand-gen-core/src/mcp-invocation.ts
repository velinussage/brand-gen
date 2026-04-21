// Resolve the best way to launch a Python MCP backend.
//
// Python relative imports like ``from .cli_builders import X`` only resolve
// when the file is loaded as a package member. Running ``python path/to/file.py``
// loads the file as a script with no package parent — any relative-import
// line without a fallback crashes the MCP process.
//
// This helper detects when a configured path points at a module under the
// ``brand_gen`` package and switches to ``python -m brand_gen.<module>`` with
// ``cwd=repoRoot`` so the package resolves. For anything else (tests, custom
// scripts), it falls back to direct script invocation.

import { existsSync } from "node:fs";
import { basename, dirname, resolve } from "node:path";

export type McpInvocation = {
  command: string;
  args: string[];
  cwd?: string;
};

const BRAND_GEN_PACKAGE = "brand_gen";

export function resolveMcpInvocation(
  mcpPath: string,
  opts?: { python?: string },
): McpInvocation {
  const python = opts?.python ?? "python3";
  const trimmed = (mcpPath || "").trim();
  if (!trimmed) {
    return { command: python, args: [] };
  }
  const absolute = resolve(trimmed);
  if (!absolute.endsWith(".py")) {
    return { command: python, args: [absolute] };
  }
  const parent = dirname(absolute);
  const packageName = basename(parent);
  const moduleName = basename(absolute, ".py");
  if (
    packageName === BRAND_GEN_PACKAGE &&
    existsSync(resolve(parent, "__init__.py"))
  ) {
    return {
      command: python,
      args: ["-m", `${packageName}.${moduleName}`],
      cwd: dirname(parent),
    };
  }
  return { command: python, args: [absolute] };
}
