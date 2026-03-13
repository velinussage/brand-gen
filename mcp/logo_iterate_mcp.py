#!/usr/bin/env python3
"""
MCP server wrapper for logo_iterate.py.
Exposes logo iteration tools via Model Context Protocol (stdio transport).
Zero external dependencies — stdlib JSON-RPC over stdin/stdout.

Register with your MCP host:
  See mcp/brand_iterate_mcp.example.json for configuration.

Or run directly:
  python3 mcp/logo_iterate_mcp.py
"""

import json
import os
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
REPO_ROOT = SCRIPT_DIR.parent
LOGO_ITERATE = SCRIPT_DIR / "logo_iterate.py"
COLLECT_INSPIRATION = REPO_ROOT / "scripts" / "collect_inspiration.py"
ENV_CANDIDATES = [REPO_ROOT / ".env", Path.home() / ".claude" / ".env"]

# ── MCP Protocol Primitives ───────────────────────────────────────────────

SERVER_INFO = {
    "name": "logo-iterate",
    "version": "1.2.0",
}

CAPABILITIES = {
    "tools": {"listChanged": False},
}

TOOLS = [
    {
        "name": "logo_generate",
        "description": "Generate a new logo version. Auto-increments version number, logs to manifest, auto-converts webp to png.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "prompt": {"type": "string", "description": "The generation prompt. Use geometric language: 'flat vertical rectangles' not 'columns'."},
                "model": {"type": "string", "description": "Model alias", "default": "recraft-v4", "enum": ["recraft-v4", "recraft-v4-svg", "recraft-v3", "ideogram", "nano-banana-2"]},
                "aspect_ratio": {"type": "string", "description": "Aspect ratio: 1:1 (icon), 2:1 (horizontal), 4:5 (stacked), 16:9 (banner)"},
                "tag": {"type": "string", "description": "Short tag for filename, e.g. 'icon', 'banner', 'horizontal-lockup'"},
                "mode": {"type": "string", "description": "Workflow mode: inspiration, reference, or hybrid.", "default": "auto", "enum": ["auto", "reference", "inspiration", "hybrid"]},
                "reference_images": {"type": "array", "items": {"type": "string"}, "description": "One or more local reference image paths."},
                "reference_dir": {"type": "string", "description": "Directory of approved reference images to include."},
            },
            "required": ["prompt"],
        },
    },
    {
        "name": "logo_feedback",
        "description": "Record feedback (score, notes, status) for a logo version. Score 1-5, status: favorite or rejected.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "version": {"type": "string", "description": "Version ID, e.g. 'v90'"},
                "score": {"type": "integer", "description": "Score 1-5", "minimum": 1, "maximum": 5},
                "notes": {"type": "string", "description": "Feedback notes"},
                "status": {"type": "string", "description": "Mark as favorite or rejected", "enum": ["favorite", "rejected"]},
                "lock_fragments": {"type": "array", "items": {"type": "string"}, "description": "Prompt fragments to lock (keep in all future prompts)"},
                "prompt": {"type": "string", "description": "Backfill prompt text for this version"},
            },
            "required": ["version"],
        },
    },
    {
        "name": "logo_show",
        "description": "Show the logo manifest — all versions, favorites only, or top N by score.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "version": {"type": "string", "description": "Specific version to show detail for"},
                "favorites": {"type": "boolean", "description": "Only show favorites"},
                "top": {"type": "integer", "description": "Show top N by score"},
            },
        },
    },
    {
        "name": "logo_compare",
        "description": "Generate an HTML comparison board for selected versions. Opens in browser on macOS.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "versions": {"type": "array", "items": {"type": "string"}, "description": "Version IDs to compare, e.g. ['v90', 'v103']"},
                "favorites": {"type": "boolean", "description": "Compare all favorited versions"},
                "top": {"type": "integer", "description": "Compare top N by score"},
            },
        },
    },
    {
        "name": "logo_evolve",
        "description": "Analyze prompt patterns across scored versions. Shows what works, what fails, locked fragments, and word analysis.",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "logo_bootstrap",
        "description": "Scan existing logo files into the manifest. Run once on first use.",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "logo_inspire",
        "description": "Collect or list logo inspiration screenshots from logosystem.co or any URL. Can use agent-browser for automated capture and optionally open the output folder.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "category": {"type": "string", "description": "Category to browse", "default": "symbol", "enum": ["symbol", "wordmark", "symbol-text", "brown", "beige", "black", "all"]},
                "url": {"type": "string", "description": "Custom inspiration URL. When set, this overrides category."},
                "label": {"type": "string", "description": "Filename label to use for screenshots from a custom URL."},
                "list_only": {"type": "boolean", "description": "Just list saved inspiration screenshots instead of opening browser"},
                "capture": {"type": "boolean", "description": "Capture screenshots automatically with agent-browser", "default": True},
                "count": {"type": "integer", "description": "How many screenshots to capture", "default": 3},
                "out_dir": {"type": "string", "description": "Override the inspiration output folder"},
                "open_folder": {"type": "boolean", "description": "Open the inspiration folder after capture", "default": True},
            },
        },
    },
]


def load_env_values():
    data = {}
    for path in reversed(ENV_CANDIDATES):
        if not path.exists():
            continue
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            data[key.strip()] = value.strip().strip('"').strip("'")
    return data


def build_env():
    env = dict(os.environ)
    env.update(load_env_values())
    return env


def default_inspiration_dir(env: dict[str, str]) -> Path:
    if env.get("LOGO_DIR"):
        return Path(env["LOGO_DIR"]).expanduser() / "inspiration"
    if env.get("SCREENSHOTS_DIR"):
        return Path(env["SCREENSHOTS_DIR"]).expanduser() / "logo-redesigns" / "inspiration"
    return REPO_ROOT / "examples" / "inspiration"


def run_python(script: Path, args: list[str]):
    env = build_env()
    result = subprocess.run(
        [sys.executable, str(script)] + args,
        env=env,
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    output = result.stdout
    if result.stderr:
        output += ("\n" if output else "") + result.stderr
    return output.strip(), result.returncode == 0


def run_logo_iterate(args: list[str]):
    return run_python(LOGO_ITERATE, args)


def run_collect_inspiration(args: dict):
    env = build_env()
    out_dir = Path(args["out_dir"]).expanduser() if args.get("out_dir") else default_inspiration_dir(env)
    cmd = ["--out-dir", str(out_dir), "--count", str(args.get("count") or 3)]
    if args.get("url"):
        cmd += ["--url", args["url"]]
        if args.get("label"):
            cmd += ["--label", args["label"]]
    else:
        cmd += ["--category", args.get("category", "symbol")]
    if args.get("open_folder", True):
        cmd.append("--open-folder")
    output, ok = run_python(COLLECT_INSPIRATION, cmd)
    if ok:
        output = (output + "\n" if output else "") + f"Inspiration folder: {out_dir}"
    return output, ok


def handle_tool_call(name, arguments):
    """Dispatch MCP tool call to logo_iterate.py or helper scripts."""
    args = arguments or {}

    if name == "logo_generate":
        cmd = ["generate", "-p", args["prompt"]]
        if args.get("model"):
            cmd += ["-m", args["model"]]
        if args.get("aspect_ratio"):
            cmd += ["--aspect-ratio", args["aspect_ratio"]]
        if args.get("tag"):
            cmd += ["--tag", args["tag"]]
        if args.get("mode"):
            cmd += ["--mode", args["mode"]]
        if args.get("reference_dir"):
            cmd += ["--reference-dir", args["reference_dir"]]
        for ref in args.get("reference_images", []) or []:
            cmd += ["-i", ref]
        output, ok = run_logo_iterate(cmd)
        return output, not ok

    if name == "logo_feedback":
        cmd = ["feedback", args["version"]]
        if args.get("score"):
            cmd += ["--score", str(args["score"])]
        if args.get("notes"):
            cmd += ["--notes", args["notes"]]
        if args.get("status"):
            cmd += ["--status", args["status"]]
        if args.get("prompt"):
            cmd += ["--prompt", args["prompt"]]
        if args.get("lock_fragments"):
            cmd += ["--lock"] + args["lock_fragments"]
        output, ok = run_logo_iterate(cmd)
        return output, not ok

    if name == "logo_show":
        cmd = ["show"]
        if args.get("version"):
            cmd.append(args["version"])
        if args.get("favorites"):
            cmd.append("--favorites")
        if args.get("top"):
            cmd += ["--top", str(args["top"])]
        output, ok = run_logo_iterate(cmd)
        return output, not ok

    if name == "logo_compare":
        cmd = ["compare"]
        if args.get("versions"):
            cmd += args["versions"]
        if args.get("favorites"):
            cmd.append("--favorites")
        if args.get("top"):
            cmd += ["--top", str(args["top"])]
        output, ok = run_logo_iterate(cmd)
        return output, not ok

    if name == "logo_evolve":
        output, ok = run_logo_iterate(["evolve"])
        return output, not ok

    if name == "logo_bootstrap":
        output, ok = run_logo_iterate(["bootstrap"])
        return output, not ok

    if name == "logo_inspire":
        if args.get("list_only"):
            cmd = ["inspire", args.get("category", "symbol"), "--list"]
            output, ok = run_logo_iterate(cmd)
            return output, not ok
        if args.get("capture", True):
            output, ok = run_collect_inspiration(args)
            return output, not ok
        cmd = ["inspire"]
        if args.get("category"):
            cmd.append(args["category"])
        if args.get("url"):
            cmd += ["--url", args["url"]]
        if args.get("label"):
            cmd += ["--label", args["label"]]
        output, ok = run_logo_iterate(cmd)
        return output, not ok

    return f"Unknown tool: {name}", True


# ── JSON-RPC / MCP Protocol ───────────────────────────────────────────────

def send_response(id, result):
    msg = {"jsonrpc": "2.0", "id": id, "result": result}
    data = json.dumps(msg)
    sys.stdout.write(f"Content-Length: {len(data)}\r\n\r\n{data}")
    sys.stdout.flush()


def send_error(id, code, message):
    msg = {"jsonrpc": "2.0", "id": id, "error": {"code": code, "message": message}}
    data = json.dumps(msg)
    sys.stdout.write(f"Content-Length: {len(data)}\r\n\r\n{data}")
    sys.stdout.flush()


def read_message():
    """Read a JSON-RPC message from stdin (Content-Length framing)."""
    headers = {}
    while True:
        line = sys.stdin.readline()
        if not line:
            return None
        line = line.strip()
        if not line:
            break
        if ":" in line:
            key, val = line.split(":", 1)
            headers[key.strip()] = val.strip()

    content_length = int(headers.get("Content-Length", 0))
    if content_length == 0:
        return None

    body = sys.stdin.read(content_length)
    return json.loads(body)


def handle_message(msg):
    method = msg.get("method", "")
    id = msg.get("id")
    params = msg.get("params", {})

    if method == "initialize":
        send_response(id, {
            "protocolVersion": "2024-11-05",
            "serverInfo": SERVER_INFO,
            "capabilities": CAPABILITIES,
        })

    elif method == "notifications/initialized":
        pass

    elif method == "tools/list":
        send_response(id, {"tools": TOOLS})

    elif method == "tools/call":
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})
        try:
            output, is_error = handle_tool_call(tool_name, arguments)
            send_response(id, {
                "content": [{"type": "text", "text": output}],
                "isError": is_error,
            })
        except Exception as e:
            send_response(id, {
                "content": [{"type": "text", "text": f"Error: {e}"}],
                "isError": True,
            })

    elif id is not None:
        send_error(id, -32601, f"Method not found: {method}")


def main():
    while True:
        msg = read_message()
        if msg is None:
            break
        handle_message(msg)


if __name__ == "__main__":
    main()
