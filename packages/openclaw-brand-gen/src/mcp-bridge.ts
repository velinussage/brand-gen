import { spawn, type ChildProcess } from "node:child_process";
import { randomUUID } from "node:crypto";
import { EventEmitter } from "node:events";
import { createInterface, type Interface as ReadlineInterface } from "node:readline";

export type McpToolDef = {
  name: string;
  description?: string;
  inputSchema?: Record<string, unknown>;
  annotations?: Record<string, unknown>;
};

type JsonRpcRequest = {
  jsonrpc: "2.0";
  id: string | number;
  method: string;
  params?: Record<string, unknown>;
};

type JsonRpcResponse = {
  jsonrpc: "2.0";
  id: string | number;
  result?: unknown;
  error?: { code: number; message: string; data?: unknown };
};

const MAX_RETRIES = 3;
const RESTART_DELAY_MS = 1000;

export class McpBridge extends EventEmitter {
  private command: string;
  private args: string[];
  private env?: Record<string, string>;
  private proc: ChildProcess | null = null;
  private rl: ReadlineInterface | null = null;
  private pending = new Map<string, { resolve: (v: unknown) => void; reject: (e: Error) => void }>();
  private ready = false;
  private retries = 0;
  private stopped = false;
  private clientVersion: string;

  constructor(
    command: string,
    args: string[],
    env?: Record<string, string>,
    opts?: { clientVersion?: string },
  ) {
    super();
    this.command = command;
    this.args = args;
    this.env = env;
    this.clientVersion = opts?.clientVersion ?? "0.0.0";
  }

  isReady(): boolean {
    return this.ready && this.proc !== null && !this.stopped;
  }

  async start(): Promise<void> {
    this.stopped = false;
    await this.spawn();
    await this.initialize();
  }

  async stop(): Promise<void> {
    this.stopped = true;
    this.ready = false;
    this.rejectAll("Bridge stopped");
    if (this.rl) {
      this.rl.close();
      this.rl = null;
    }
    if (this.proc) {
      this.proc.kill("SIGTERM");
      this.proc = null;
    }
  }

  async listTools(): Promise<McpToolDef[]> {
    const result = (await this.request("tools/list", {})) as { tools?: McpToolDef[] };
    return result?.tools ?? [];
  }

  async callTool(name: string, args: Record<string, unknown>): Promise<unknown> {
    const result = (await this.request("tools/call", { name, arguments: args })) as {
      content?: Array<{ type: string; text?: string }>;
      isError?: boolean;
    };

    if (result?.isError) {
      const text = result.content?.map((c) => c.text ?? "").join("\n") ?? "MCP tool error";
      throw new Error(text);
    }

    return result;
  }

  private spawn(): Promise<void> {
    return new Promise((resolve, reject) => {
      const proc = spawn(this.command, this.args, {
        stdio: ["pipe", "pipe", "pipe"],
        env: { ...process.env, ...this.env },
      });

      proc.on("error", (err) => {
        if (!this.stopped) void this.handleCrash(err);
      });

      proc.on("exit", (code) => {
        if (!this.stopped && code !== 0) {
          void this.handleCrash(new Error(`MCP process exited with code ${code}`));
        }
      });

      if (!proc.stdout || !proc.stdin) {
        reject(new Error("Failed to open stdio pipes for MCP process"));
        return;
      }

      this.proc = proc;
      this.rl = createInterface({ input: proc.stdout });
      this.rl.on("line", (line) => this.handleLine(line));

      if (proc.stderr) {
        const errRl = createInterface({ input: proc.stderr });
        errRl.on("line", (line) => this.emit("log", line));
      }

      resolve();
    });
  }

  private async initialize(): Promise<void> {
    const result = (await this.request("initialize", {
      protocolVersion: "2024-11-05",
      capabilities: {},
      clientInfo: { name: "openclaw-brand-gen-plugin", version: this.clientVersion },
    })) as { serverInfo?: { name?: string } };

    this.notify("notifications/initialized", {});
    this.ready = true;
    this.retries = 0;
    this.emit("ready", result?.serverInfo);
  }

  private request(method: string, params: Record<string, unknown>): Promise<unknown> {
    return new Promise((resolve, reject) => {
      if (!this.proc?.stdin?.writable) {
        reject(new Error("MCP process not running"));
        return;
      }

      const id = randomUUID();
      const req: JsonRpcRequest = { jsonrpc: "2.0", id, method, params };
      this.pending.set(id, { resolve, reject });
      this.proc.stdin.write(JSON.stringify(req) + "\n");
    });
  }

  private notify(method: string, params: Record<string, unknown>): void {
    if (!this.proc?.stdin?.writable) return;
    this.proc.stdin.write(JSON.stringify({ jsonrpc: "2.0", method, params }) + "\n");
  }

  private handleLine(line: string): void {
    let msg: JsonRpcResponse;
    try {
      msg = JSON.parse(line);
    } catch {
      return;
    }
    if (!msg.id) return;
    const pending = this.pending.get(String(msg.id));
    if (!pending) return;
    this.pending.delete(String(msg.id));
    if (msg.error) pending.reject(new Error(`MCP error ${msg.error.code}: ${msg.error.message}`));
    else pending.resolve(msg.result);
  }

  private async handleCrash(err: Error): Promise<void> {
    this.ready = false;
    this.rejectAll(`MCP process crashed: ${err.message}`);

    if (this.retries >= MAX_RETRIES) {
      this.emit("error", new Error(`MCP bridge failed after ${MAX_RETRIES} retries: ${err.message}`));
      return;
    }

    this.retries += 1;
    this.emit("log", `MCP process crashed, retry ${this.retries}/${MAX_RETRIES}...`);
    await new Promise((resolve) => setTimeout(resolve, RESTART_DELAY_MS));
    if (this.stopped) return;

    try {
      await this.spawn();
      await this.initialize();
    } catch (retryErr) {
      await this.handleCrash(retryErr instanceof Error ? retryErr : new Error(String(retryErr)));
    }
  }

  private rejectAll(reason: string): void {
    for (const [, pending] of this.pending) pending.reject(new Error(reason));
    this.pending.clear();
  }
}
