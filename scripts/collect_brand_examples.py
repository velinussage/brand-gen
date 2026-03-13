#!/usr/bin/env python3
"""List, search, and capture curated brand-example sources into categorized folders."""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = REPO_ROOT / "data" / "brand_example_sources.json"
BRAND_GEN_PATH = REPO_ROOT / ".brand-gen"
ENV_CANDIDATES = [REPO_ROOT / ".env", Path.home() / ".claude" / ".env"]


def load_env() -> dict[str, str]:
    env = dict(os.environ)
    for path in reversed(ENV_CANDIDATES):
        if not path.exists():
            continue
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            env[key.strip()] = value.strip().strip('"').strip("'")
    return env


def load_sources() -> dict:
    source_path = BRAND_GEN_PATH / "sources" / "brand_example_sources.json" if BRAND_GEN_PATH.exists() else DATA_PATH
    return json.loads(source_path.read_text())


def category_map(data: dict) -> dict[str, dict]:
    return {item["key"]: item for item in data["categories"]}


def slugify(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower())
    return value.strip("-") or "example"


def default_out_dir(env: dict[str, str]) -> Path:
    if env.get("BRAND_GEN_DIR"):
        return Path(env["BRAND_GEN_DIR"]).expanduser() / "inspiration"
    if BRAND_GEN_PATH.exists():
        return BRAND_GEN_PATH / "inspiration"
    if env.get("BRAND_DIR"):
        return Path(env["BRAND_DIR"]).expanduser() / "examples"
    if env.get("LOGO_DIR"):
        return Path(env["LOGO_DIR"]).expanduser() / "examples"
    if env.get("SCREENSHOTS_DIR"):
        return Path(env["SCREENSHOTS_DIR"]).expanduser() / "brand-materials" / "examples"
    return REPO_ROOT / "examples" / "brand-sources"


def find_agent_browser(env: dict[str, str]) -> str | None:
    override = env.get("AGENT_BROWSER_BIN")
    if override:
        path = Path(override).expanduser()
        return str(path) if path.exists() else None
    proc = subprocess.run(["which", "-a", "agent-browser"], capture_output=True, text=True, check=False)
    seen = set()
    candidates = []
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line or line in seen:
            continue
        seen.add(line)
        candidates.append(line)
    if not candidates:
        return None
    home = str(Path.home())
    candidates.sort(key=lambda p: (0 if p.startswith(home) else 1, p))
    return candidates[0]


def run(cmd: list[str], env: dict[str, str]) -> None:
    proc = subprocess.run(cmd, env=env, capture_output=True, text=True)
    if proc.stdout.strip():
        print(proc.stdout.strip())
    if proc.returncode != 0:
        if proc.stderr.strip():
            print(proc.stderr.strip(), file=sys.stderr)
        if "Playwright" in proc.stderr or "chrome-headless-shell" in proc.stderr:
            print("Hint: install the browser runtime with: npx playwright install", file=sys.stderr)
        raise SystemExit(proc.returncode)


def filter_sources(data: dict, category: str | None = None, query: str | None = None, site_keys: list[str] | None = None) -> list[dict]:
    items = data["sources"]
    if category:
        items = [item for item in items if item["category"] == category]
    if site_keys:
        wanted = set(site_keys)
        items = [item for item in items if item["key"] in wanted]
    if query:
        q = query.strip().lower()
        items = [
            item for item in items
            if q in item["name"].lower()
            or q in item["notes"].lower()
            or any(q in tag.lower() for tag in item.get("tags", []))
            or q in item["category"].lower()
        ]
    return items


def print_table(items: list[dict], categories: dict[str, dict]) -> None:
    print(f"{'KEY':<22} {'CATEGORY':<28} {'NAME':<28} URL")
    print("-" * 120)
    for item in items:
        category_label = categories[item["category"]]["label"]
        print(f"{item['key']:<22} {category_label:<28.28} {item['name']:<28.28} {item['url']}")


def write_index(path: Path, items: list[dict], categories: dict[str, dict]) -> None:
    lines = [
        "# Brand example captures",
        "",
        "Generated from the curated source registry.",
        "",
    ]
    for item in items:
        category_label = categories[item["category"]]["label"]
        lines.extend([
            f"## {item['name']}",
            f"- Category: {category_label}",
            f"- URL: {item['url']}",
            f"- Notes: {item['notes']}",
            f"- Tags: {', '.join(item.get('tags', []))}",
            "",
        ])
    path.write_text("\n".join(lines) + "\n")


def cmd_list(args) -> int:
    data = load_sources()
    cats = category_map(data)
    items = filter_sources(data, category=args.category, query=args.query)
    if args.format == "json":
        print(json.dumps(items, indent=2))
    else:
        print_table(items, cats)
    return 0


def cmd_capture(args) -> int:
    env = load_env()
    agent_browser = find_agent_browser(env)
    if not agent_browser:
        print("ERROR: agent-browser is not installed. Install with: npm install -g agent-browser", file=sys.stderr)
        return 1

    data = load_sources()
    cats = category_map(data)
    items = filter_sources(data, category=args.category, query=args.query, site_keys=args.site)
    if args.limit:
        items = items[: args.limit]
    if not items:
        print("No sources matched the requested filters.", file=sys.stderr)
        return 1

    out_dir = Path(args.out_dir).expanduser().resolve() if args.out_dir else default_out_dir(env)
    out_dir.mkdir(parents=True, exist_ok=True)

    for item in items:
        session = f"brand-example-{item['key']}-{time.time_ns()}-{os.getpid()}"
        env["AGENT_BROWSER_SESSION"] = session
        site_root = out_dir / item["category"] / item["key"]
        site_dir = site_root / "screenshots"
        site_dir.mkdir(parents=True, exist_ok=True)
        run([agent_browser, "set", "viewport", str(args.width), str(args.height)], env)
        run([agent_browser, "open", item["url"]], env)
        try:
            run([agent_browser, "wait", "--load", "networkidle"], env)
        except SystemExit:
            pass
        viewport = site_dir / "viewport.png"
        full = site_dir / "full.png"
        snapshot = site_dir / "snapshot.txt"
        meta = site_root / "source.json"
        run([agent_browser, "screenshot", str(viewport)], env)
        try:
            run([agent_browser, "screenshot", "--full", str(full)], env)
        except SystemExit:
            pass
        with snapshot.open("w") as fh:
            subprocess.run([agent_browser, "snapshot", "-i", "-c"], env=env, stdout=fh, stderr=subprocess.DEVNULL, check=False)
        meta.write_text(json.dumps(item, indent=2) + "\n")
        print(f"Captured {item['name']} -> {site_dir}")

    write_index(out_dir / "INDEX.md", items, cats)
    if args.open_folder:
        subprocess.run([sys.executable, str(REPO_ROOT / "scripts" / "open_folder.py"), str(out_dir)], check=False)
    print(f"Brand example captures: {out_dir}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Search and capture curated brand-example sources")
    sub = parser.add_subparsers(dest="command", required=True)

    list_parser = sub.add_parser("list", help="List curated example sources")
    list_parser.add_argument("--category", help="Filter by category key")
    list_parser.add_argument("--query", help="Search across names, notes, and tags")
    list_parser.add_argument("--format", choices=["table", "json"], default="table")

    capture = sub.add_parser("capture", help="Capture screenshots from curated example sources")
    capture.add_argument("--category", help="Filter by category key")
    capture.add_argument("--query", help="Search across names, notes, and tags")
    capture.add_argument("--site", action="append", help="Specific site key to capture; repeat as needed")
    capture.add_argument("--limit", type=int, help="Limit number of captures after filtering")
    capture.add_argument("--out-dir", help="Output directory for categorized example captures")
    capture.add_argument("--width", type=int, default=1600)
    capture.add_argument("--height", type=int, default=1100)
    capture.add_argument("--open-folder", action="store_true")

    args = parser.parse_args()
    if args.command == "list":
        return cmd_list(args)
    return cmd_capture(args)


if __name__ == "__main__":
    raise SystemExit(main())
