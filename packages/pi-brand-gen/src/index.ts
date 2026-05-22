import { existsSync } from "node:fs";
import { resolve } from "node:path";
import {
  McpBridge,
  buildBrandGenContext,
  createHeartbeatState,
  executeAction,
  isHeartbeatPrompt,
  parsePluginConfig,
  resolveMcpInvocation,
  scheduleHeartbeat,
  stopHeartbeat,
  summarizeContext,
  triggerHeartbeat,
  writeRuntimeStatusMarker,
  type PluginConfig,
} from "@brand-gen/core";
import { resolvePiRuntimePaths } from "./runtime-paths.js";
import {
  createBrandExecuteTool,
  createBrandSearchTool,
  createBrandStatusTool,
  createCanonicalBrandTools,
} from "./tool.js";
import { BrandGenWidget } from "./ui/brand-widget.js";

function compatRegisterTool(pi: any, tool: any) {
  if (typeof pi?.registerTool === "function") return pi.registerTool(tool);
  if (typeof pi?.tool === "function") return pi.tool(tool);
  if (typeof pi?.addTool === "function") return pi.addTool(tool);
}

function compatRegisterCommand(pi: any, command: any) {
  if (typeof pi?.registerCommand === "function") return pi.registerCommand(command);
  if (typeof pi?.command === "function") return pi.command(command);
  if (typeof pi?.addCommand === "function") return pi.addCommand(command);
}

function compatOn(pi: any, event: string, handler: (...args: any[]) => any) {
  if (typeof pi?.on === "function") return pi.on(event, handler);
  if (typeof pi?.events?.on === "function") return pi.events.on(event, handler);
}

function extractPrompt(event: any): string {
  if (!event || typeof event !== "object") return "";
  return typeof event.prompt === "string"
    ? event.prompt
    : typeof event.message === "string"
      ? event.message
      : typeof event.input === "string"
        ? event.input
        : "";
}

export default async function brandGenPiExtension(pi: any) {
  const rawConfig = (pi?.config ?? pi?.pluginConfig ?? {}) as Record<string, unknown>;
  // Prefer a project-local `.brand-gen` when the operator hasn't set an
  // explicit brandGenDir. parsePluginConfig's default of `~/.brand-gen`
  // assumes a single global workspace, but most brand-gen users run
  // against the checkout's own `.brand-gen/` directory. We pick in this
  // order: explicit config > repoRoot/.brand-gen (if it exists) > cwd/.brand-gen
  // (if it exists) > ~/.brand-gen (parsePluginConfig default).
  if (!(typeof rawConfig?.brandGenDir === "string" && rawConfig.brandGenDir.trim())) {
    const probeRuntime = resolvePiRuntimePaths(
      import.meta.url,
      typeof rawConfig.brandIterateMcpPath === "string" ? rawConfig.brandIterateMcpPath : undefined,
    );
    const candidates = [
      resolve(probeRuntime.repoRoot, ".brand-gen"),
      resolve(process.cwd(), ".brand-gen"),
    ];
    for (const candidate of candidates) {
      if (existsSync(candidate)) {
        rawConfig.brandGenDir = candidate;
        break;
      }
    }
  }
  const config: PluginConfig = parsePluginConfig(rawConfig);
  const runtime = resolvePiRuntimePaths(import.meta.url, config.brandIterateMcpPath);
  const env: Record<string, string> = {
    HOME: process.env.HOME || "",
    PATH: process.env.PATH || "",
    USER: process.env.USER || "",
    BRAND_GEN_DIR: config.brandGenDir,
    BRAND_GEN_REPO_ROOT: runtime.repoRoot,
  };
  for (const key of [
    "REPLICATE_API_TOKEN",
    "GOOGLE_API_KEY",
    "BROWSERBASE_API_KEY",
    "BROWSERBASE_PROJECT_ID",
    "BRAND_DIR",
  ]) {
    if (process.env[key]) env[key] = process.env[key] as string;
  }

  // Launch the MCP backend as a Python module (`-m brand_gen.brand_iterate_mcp`)
  // with cwd=repoRoot so intra-package relative imports resolve. Running the
  // .py file as a script breaks `from .cli_builders import ...` inside
  // brand_gen/command_registry.py. resolveMcpInvocation detects the
  // brand_gen package layout and builds the right command+args+cwd.
  const invocation = resolveMcpInvocation(runtime.mcpPath, { python: runtime.pythonCommand });
  const bridge = new McpBridge(invocation.command, invocation.args, env, {
    cwd: invocation.cwd,
  });
  const heartbeat = createHeartbeatState();
  const widget = new BrandGenWidget(bridge, config, heartbeat);

  // Phase 3: register the canonical verb-specific tool surface first so
  // agents discover the typed verbs by default. The deprecated multiplexers
  // (brand_search, brand_execute) stay registered for backward compatibility.
  for (const tool of createCanonicalBrandTools(bridge, config)) {
    compatRegisterTool(pi, tool);
  }
  compatRegisterTool(pi, createBrandSearchTool(bridge, config));
  compatRegisterTool(pi, createBrandExecuteTool(bridge, config));
  compatRegisterTool(pi, createBrandStatusTool(config, bridge, heartbeat));

  compatRegisterCommand(pi, {
    name: "brand-gen",
    description:
      "Brand-gen control surface for status, heartbeat, switching brands, reviews, and generation.",
    execute: async (args: string[] = [], ctx?: any) => {
      const sub = args[0] ?? "status";
      if (sub === "status") {
        const tool = createBrandStatusTool(config, bridge, heartbeat);
        return tool.execute({});
      }
      if (sub === "brands") {
        const result = await createBrandSearchTool(bridge, config).execute({
          action: "list_brands",
          params: {},
        });
        return result;
      }
      if (sub === "heartbeat") {
        const result = await triggerHeartbeat(
          bridge,
          config,
          heartbeat,
          pi?.logger ?? console,
          "command",
        );
        await widget.refresh(pi, ctx?.session?.id);
        return { content: [{ type: "text", text: JSON.stringify(result, null, 2) }] };
      }
      if (sub === "switch") {
        const brand = args[1];
        if (!brand) throw new Error("Usage: /brand-gen switch <brand>");
        const result = await executeAction(bridge, config, "switch_brand", { brand });
        await widget.refresh(pi, ctx?.session?.id);
        return { content: [{ type: "text", text: JSON.stringify(result, null, 2) }] };
      }
      if (sub === "reviews") {
        const result = await createBrandSearchTool(bridge, config).execute({
          action: "get_pending_reviews",
          params: {},
        });
        return result;
      }
      if (sub === "summary") {
        const result = await createBrandSearchTool(bridge, config).execute({
          action: "get_session_summary",
          params: {},
        });
        return result;
      }
      if (sub === "review") {
        const version = args[1];
        if (!version) throw new Error("Usage: /brand-gen review <version>");
        const raw = await bridge.callTool("brand_review", { version, open: true });
        await widget.refresh(pi, ctx?.session?.id);
        return raw as any;
      }
      if (sub === "generate") {
        const [materialType, ...goalParts] = args.slice(1);
        if (!materialType) throw new Error("Usage: /brand-gen generate <materialType> <goal...>");
        const goal = goalParts.join(" ") || "Explain what the brand/product is clearly";
        const result = await executeAction(bridge, config, "generate", {
          materialType,
          goal,
          purpose: "manual pi generation",
          targetSurface: materialType,
        });
        await widget.refresh(pi, ctx?.session?.id);
        return { content: [{ type: "text", text: JSON.stringify(result, null, 2) }] };
      }
      if (sub === "mockup") {
        const sourceVersion = args[1];
        const materialType = args[2] ?? "device-mockup";
        if (!sourceVersion) {
          throw new Error("Usage: /brand-gen mockup <sourceVersion> [device-mockup|lifestyle-mockup|website-hero-illustration]");
        }
        const result = await executeAction(bridge, config, "derive_mockup", {
          sourceVersion,
          materialType,
        });
        await widget.refresh(pi, ctx?.session?.id);
        return { content: [{ type: "text", text: JSON.stringify(result, null, 2) }] };
      }
      if (sub === "video") {
        const sourceVersion = args[1];
        const materialType = args[2] ?? "short-video";
        if (!sourceVersion) {
          throw new Error("Usage: /brand-gen video <sourceVersion> [short-video|feature-animation|motion-loop]");
        }
        const result = await executeAction(bridge, config, "derive_video", {
          sourceVersion,
          materialType,
        });
        await widget.refresh(pi, ctx?.session?.id);
        return { content: [{ type: "text", text: JSON.stringify(result, null, 2) }] };
      }
      if (sub === "feedback") {
        const version = args[1];
        const score = Number(args[2]);
        const notes = args.slice(3).join(" ");
        if (!version || !Number.isFinite(score)) {
          throw new Error("Usage: /brand-gen feedback <version> <score> [notes...]");
        }
        const result = await executeAction(bridge, config, "feedback", {
          version,
          score,
          notes,
        });
        await widget.refresh(pi, ctx?.session?.id);
        return { content: [{ type: "text", text: JSON.stringify(result, null, 2) }] };
      }
      if (sub === "widget") {
        const mode = args[1] ?? "show";
        if (mode === "hide") await widget.hide(pi, ctx?.session?.id);
        else await widget.show(pi, ctx?.session?.id);
        return {
          content: [
            { type: "text", text: `Brand widget ${mode === "hide" ? "hidden" : "shown"}.` },
          ],
        };
      }
      throw new Error(`Unknown /brand-gen subcommand: ${sub}`);
    },
  });

  compatOn(pi, "session_start", async (event: any) => {
    // Kick off the MCP bridge in the BACKGROUND. Do not await —
    // bridge.start() awaits an MCP `initialize` handshake with no
    // timeout, so blocking session_start on it can hang Pi's entire
    // session-ready state. Tools check bridge.isReady() before calling;
    // heartbeat scheduler waits for the ready event internally.
    //
    // Swallow "Bridge stopped" — short-lived Pi sessions (e.g.
    // --no-session -p) dispose before the handshake lands, and the
    // pending promise rejects with that message. That's not an error.
    bridge
      .start()
      .catch((err: unknown) => {
        const message = err instanceof Error ? err.message : String(err);
        if (message.includes("Bridge stopped")) return;
        (pi?.logger ?? console).warn?.(
          `[brand-gen] MCP bridge failed to start: ${message}`,
        );
      });
    scheduleHeartbeat(bridge, config, heartbeat, pi?.logger ?? console);
    writeRuntimeStatusMarker("pi-brand-gen", config, {
      plugin: "pi",
      sessionId: event?.session?.id ?? null,
      heartbeatEnabled: config.autoHeartbeat,
    });
    await widget.show(pi, event?.session?.id);
  });

  compatOn(pi, "before_agent_start", async (event: any) => {
    if (!bridge.isReady()) return undefined;
    const prompt = extractPrompt(event);
    const heartbeatResult = isHeartbeatPrompt(prompt)
      ? await triggerHeartbeat(bridge, config, heartbeat, pi?.logger ?? console, "prompt")
      : null;
    const context = await buildBrandGenContext(bridge, config).catch(() => null);
    if (!context) return undefined;
    const prepend = [
      summarizeContext(context),
      heartbeatResult ? `Heartbeat result: ${JSON.stringify(heartbeatResult, null, 2)}` : "",
    ]
      .filter(Boolean)
      .join("\n\n");
    return prepend ? { prependContext: prepend } : undefined;
  });

  for (const eventName of ["session_switch", "session_fork"]) {
    compatOn(pi, eventName, async (event: any) => {
      writeRuntimeStatusMarker("pi-brand-gen", config, {
        plugin: "pi",
        event: eventName,
        sessionId: event?.session?.id ?? null,
      });
      await widget.refresh(pi, event?.session?.id);
    });
  }

  compatOn(pi, "session_shutdown", async (event: any) => {
    await stopHeartbeat(heartbeat);
    await widget.hide(pi, event?.session?.id);
    await bridge.stop();
  });

  if (typeof pi?.registerMessageRenderer === "function") {
    pi.registerMessageRenderer("brand-gen-status", async () => widget.buildText());
  }

  return {
    id: "pi-brand-gen",
    name: "Brand Gen",
    dispose: async () => {
      await stopHeartbeat(heartbeat);
      await bridge.stop();
    },
  };
}
