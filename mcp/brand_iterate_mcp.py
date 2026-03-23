#!/usr/bin/env python3
"""Thin MCP server wrapper for brand-iterate."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

try:
    from .mcp_bridge_registry import BRIDGE_BY_TOOL, argv_from_mcp_args, build_bridge_tools
    from .pipeline_request import PipelineRequest
    from .runtime_io import build_env, load_env_values
except ImportError:  # pragma: no cover - direct script compatibility
    from mcp_bridge_registry import BRIDGE_BY_TOOL, argv_from_mcp_args, build_bridge_tools  # type: ignore
    from pipeline_request import PipelineRequest  # type: ignore
    from runtime_io import build_env, load_env_values  # type: ignore

SCRIPT_DIR = Path(__file__).parent
REPO_ROOT = SCRIPT_DIR.parent
COLLECT_INSPIRATION = REPO_ROOT / "scripts" / "collect_inspiration.py"

SERVER_INFO = {"name": "brand-iterate", "version": "1.20.0"}
CAPABILITIES = {"tools": {"listChanged": False}}

CUSTOM_TOOLS = [
    {
        "name": "brand_inspire",
        "description": "Collect or list inspiration screenshots from Logo System or any URL, or configure which extracted inspiration sources a brand should borrow doctrine from.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "category": {"type": "string", "default": "symbol", "enum": ["symbol", "wordmark", "symbol-text", "brown", "beige", "black", "all"]},
                "url": {"type": "string"},
                "label": {"type": "string"},
                "list_only": {"type": "boolean"},
                "capture": {"type": "boolean", "default": True},
                "count": {"type": "integer", "default": 3},
                "out_dir": {"type": "string"},
                "open_folder": {"type": "boolean", "default": True},
                "brand": {"type": "string", "description": "Brand key to configure inspiration sources for."},
                "sources": {"type": "array", "items": {"type": "string"}, "description": "Curated inspiration source keys to attach to the brand."},
                "show": {"type": "boolean", "default": False},
                "clear": {"type": "boolean", "default": False},
                "format": {"type": "string", "enum": ["text", "json"], "default": "json"}
            }
        }
    },
    {
        "name": "brand_pipeline",
        "description": "Run the full generative pipeline in one call: route → plan-draft → critique → build-generation-scratchpad → generate. Stops at critique when blocking issues remain and returns every completed stage. Deterministic pipeline QA is automatic, and generation now writes an agent-review packet so a Codex-style reviewer can inspect the image without an external VLM API key. The legacy internal_vlm_critique path remains explicit opt-in only.",
        "inputSchema": PipelineRequest.mcp_input_schema(),
    },
]

TOOLS = build_bridge_tools() + CUSTOM_TOOLS


def default_inspiration_dir(env: dict[str, str]) -> Path:
    brand_gen_root = Path(env.get("BRAND_GEN_DIR")).expanduser() if env.get("BRAND_GEN_DIR") else (REPO_ROOT / ".brand-gen")
    if brand_gen_root.exists():
        config_path = brand_gen_root / "config.json"
        if config_path.exists():
            try:
                config = json.loads(config_path.read_text())
            except Exception:
                config = {}
            active_session = config.get("activeSession")
            if active_session:
                return brand_gen_root / "sessions" / str(active_session) / "brand-materials" / "inspiration"
            active = config.get("active")
            if active:
                return brand_gen_root / "brands" / str(active) / "inspiration"
    if env.get("BRAND_DIR"):
        return Path(env["BRAND_DIR"]).expanduser() / "inspiration"
    if env.get("LOGO_DIR"):
        return Path(env["LOGO_DIR"]).expanduser() / "inspiration"
    if env.get("SCREENSHOTS_DIR"):
        return Path(env["SCREENSHOTS_DIR"]).expanduser() / "brand-materials" / "inspiration"
    return REPO_ROOT / "examples" / "inspiration"


def run_python(script: Path, args: list[str]):
    env = build_env()
    result = subprocess.run([sys.executable, str(script)] + args, env=env, capture_output=True, text=True, cwd=str(REPO_ROOT))
    output = result.stdout
    if result.stderr:
        output += ("\n" if output else "") + result.stderr
    return output.strip(), result.returncode == 0


def run_brand_iterate(args: list[str]):
    env = build_env()
    result = subprocess.run([sys.executable, "-m", "mcp.brand_iterate"] + args, env=env, capture_output=True, text=True, cwd=str(REPO_ROOT))
    output = result.stdout
    if result.stderr:
        output += ("\n" if output else "") + result.stderr
    return output.strip(), result.returncode == 0


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


def build_pipeline_args_from_mcp(args: dict) -> argparse.Namespace:
    return PipelineRequest.from_mcp_args(args).to_namespace()


def handle_custom_tool_call(name: str, args: dict):
    if name == "brand_inspire":
        if args.get("brand") or args.get("sources") or args.get("show") or args.get("clear"):
            cmd = ["inspire"]
            if args.get("brand"):
                cmd += ["--brand", args["brand"]]
            if args.get("category") and not args.get("brand"):
                cmd.append(args["category"])
            for source in args.get("sources", []) or []:
                cmd += ["--sources", source]
            if args.get("show"):
                cmd += ["--show"]
            if args.get("clear"):
                cmd += ["--clear"]
            if args.get("format"):
                cmd += ["--format", args["format"]]
            output, ok = run_brand_iterate(cmd)
            return output, not ok
        if args.get("list_only"):
            cmd = ["inspire", args.get("category", "symbol"), "--list"]
            if args.get("url"):
                cmd += ["--url", args["url"]]
            output, ok = run_brand_iterate(cmd)
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
        output, ok = run_brand_iterate(cmd)
        return output, not ok

    if name == "brand_pipeline":
        try:
            from .pipeline_runner import PipelineRunner
            from .runtime import get_brand_dir, load_brand_memory
        except ImportError:  # pragma: no cover - direct script/import compatibility
            from pipeline_runner import PipelineRunner  # type: ignore
            from runtime import get_brand_dir, load_brand_memory  # type: ignore

        request = PipelineRequest.from_mcp_args(args)
        brand_dir = get_brand_dir()
        _, _, profile, identity = load_brand_memory(brand_dir, request.profile, request.identity)
        runner = PipelineRunner(
            brand_dir=brand_dir,
            profile=profile,
            identity=identity,
            **request.runner_kwargs(),
        )
        result = runner.run(request.to_namespace())
        is_error = result.stopped_at not in {"complete", "critique"}
        return json.dumps(result.to_dict(), indent=2), is_error

    return f"Unknown tool: {name}", True


def handle_tool_call(name, arguments):
    args = arguments or {}
    bridge = BRIDGE_BY_TOOL.get(name)
    if bridge:
        output, ok = run_brand_iterate(argv_from_mcp_args(bridge, args))
        return output, not ok
    return handle_custom_tool_call(name, args)


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
        send_response(id, {"protocolVersion": "2024-11-05", "serverInfo": SERVER_INFO, "capabilities": CAPABILITIES})
    elif method == "notifications/initialized":
        pass
    elif method == "tools/list":
        send_response(id, {"tools": TOOLS})
    elif method == "tools/call":
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})
        try:
            output, is_error = handle_tool_call(tool_name, arguments)
            send_response(id, {"content": [{"type": "text", "text": output}], "isError": is_error})
        except Exception as exc:
            send_response(id, {"content": [{"type": "text", "text": f"Error: {exc}"}], "isError": True})
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
