import { McpBridge } from './mcp-bridge.ts';
import {
  buildBrandGenContext,
  createHeartbeatState,
  executeAction,
  isHeartbeatPrompt,
  parsePluginConfig,
  scheduleHeartbeat,
  stopHeartbeat,
  summarizeContext,
  triggerHeartbeat,
  type PluginConfig,
} from './core.ts';
import { createBrandExecuteTool, createBrandSearchTool, createBrandStatusTool } from './tool.ts';
import { BrandGenWidget } from './ui/brand-widget.ts';

function compatRegisterTool(pi: any, tool: any) {
  if (typeof pi?.registerTool === 'function') return pi.registerTool(tool);
  if (typeof pi?.tool === 'function') return pi.tool(tool);
  if (typeof pi?.addTool === 'function') return pi.addTool(tool);
}

function compatRegisterCommand(pi: any, command: any) {
  if (typeof pi?.registerCommand === 'function') return pi.registerCommand(command);
  if (typeof pi?.command === 'function') return pi.command(command);
  if (typeof pi?.addCommand === 'function') return pi.addCommand(command);
}

function compatOn(pi: any, event: string, handler: (...args: any[]) => any) {
  if (typeof pi?.on === 'function') return pi.on(event, handler);
  if (typeof pi?.events?.on === 'function') return pi.events.on(event, handler);
}

function extractPrompt(event: any): string {
  if (!event || typeof event !== 'object') return '';
  return typeof event.prompt === 'string' ? event.prompt : typeof event.message === 'string' ? event.message : typeof event.input === 'string' ? event.input : '';
}

export default async function brandGenPiExtension(pi: any) {
  const config: PluginConfig = parsePluginConfig(pi?.config ?? pi?.pluginConfig ?? {});
  const env: Record<string, string> = {
    HOME: process.env.HOME || '',
    PATH: process.env.PATH || '',
    USER: process.env.USER || '',
    BRAND_GEN_DIR: config.brandGenDir,
  };
  for (const key of ['REPLICATE_API_TOKEN', 'GOOGLE_API_KEY', 'BROWSERBASE_API_KEY', 'BROWSERBASE_PROJECT_ID', 'BRAND_DIR']) {
    if (process.env[key]) env[key] = process.env[key] as string;
  }

  const bridge = new McpBridge('python3', [config.brandIterateMcpPath], env);
  const heartbeat = createHeartbeatState();
  const widget = new BrandGenWidget(bridge, config, heartbeat);

  compatRegisterTool(pi, createBrandSearchTool(bridge, config));
  compatRegisterTool(pi, createBrandExecuteTool(bridge, config));
  compatRegisterTool(pi, createBrandStatusTool(config, bridge, heartbeat));

  compatRegisterCommand(pi, {
    name: 'brand-gen',
    description: 'Brand-gen control surface for status, heartbeat, switching brands, reviews, and generation.',
    execute: async (args: string[] = [], ctx?: any) => {
      const sub = args[0] ?? 'status';
      if (sub === 'status') {
        const tool = createBrandStatusTool(config, bridge, heartbeat);
        return tool.execute({});
      }
      if (sub === 'heartbeat') {
        const result = await triggerHeartbeat(bridge, config, heartbeat, pi?.logger ?? console, 'command');
        await widget.refresh(pi, ctx?.session?.id);
        return { content: [{ type: 'text', text: JSON.stringify(result, null, 2) }] };
      }
      if (sub === 'switch') {
        const brand = args[1];
        if (!brand) throw new Error('Usage: /brand-gen switch <brand>');
        const result = await executeAction(bridge, config, 'switch_brand', { brand });
        await widget.refresh(pi, ctx?.session?.id);
        return { content: [{ type: 'text', text: JSON.stringify(result, null, 2) }] };
      }
      if (sub === 'reviews') {
        const result = await createBrandSearchTool(bridge, config).execute({ action: 'get_pending_reviews', params: {} });
        return result;
      }
      if (sub === 'generate') {
        const [materialType, ...goalParts] = args.slice(1);
        if (!materialType) throw new Error('Usage: /brand-gen generate <materialType> <goal...>');
        const goal = goalParts.join(' ') || 'Explain what the brand/product is clearly';
        const result = await executeAction(bridge, config, 'generate', {
          materialType,
          goal,
          purpose: 'manual pi generation',
          targetSurface: materialType,
        });
        await widget.refresh(pi, ctx?.session?.id);
        return { content: [{ type: 'text', text: JSON.stringify(result, null, 2) }] };
      }
      if (sub === 'widget') {
        const mode = args[1] ?? 'show';
        if (mode === 'hide') await widget.hide(pi, ctx?.session?.id);
        else await widget.show(pi, ctx?.session?.id);
        return { content: [{ type: 'text', text: `Brand widget ${mode === 'hide' ? 'hidden' : 'shown'}.` }] };
      }
      throw new Error(`Unknown /brand-gen subcommand: ${sub}`);
    },
  });

  compatOn(pi, 'session_start', async (event: any) => {
    await bridge.start();
    scheduleHeartbeat(bridge, config, heartbeat, pi?.logger ?? console);
    await widget.show(pi, event?.session?.id);
  });

  compatOn(pi, 'before_agent_start', async (event: any) => {
    if (!bridge.isReady()) return undefined;
    const prompt = extractPrompt(event);
    const heartbeatResult = isHeartbeatPrompt(prompt)
      ? await triggerHeartbeat(bridge, config, heartbeat, pi?.logger ?? console, 'prompt')
      : null;
    const context = await buildBrandGenContext(bridge, config).catch(() => null);
    if (!context) return undefined;
    const prepend = [summarizeContext(context), heartbeatResult ? `Heartbeat result: ${JSON.stringify(heartbeatResult, null, 2)}` : ''].filter(Boolean).join('\n\n');
    return prepend ? { prependContext: prepend } : undefined;
  });

  for (const eventName of ['session_switch', 'session_fork']) {
    compatOn(pi, eventName, async (event: any) => {
      await widget.refresh(pi, event?.session?.id);
    });
  }

  compatOn(pi, 'session_shutdown', async (event: any) => {
    await stopHeartbeat(heartbeat);
    await widget.hide(pi, event?.session?.id);
    await bridge.stop();
  });

  if (typeof pi?.registerMessageRenderer === 'function') {
    pi.registerMessageRenderer('brand-gen-status', async () => widget.buildText());
  }

  return {
    id: 'pi-brand-gen',
    name: 'Brand Gen',
    dispose: async () => {
      await stopHeartbeat(heartbeat);
      await bridge.stop();
    },
  };
}
