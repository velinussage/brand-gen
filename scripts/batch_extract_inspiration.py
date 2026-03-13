#!/usr/bin/env python3
"""Run design-memory extraction for curated inspiration sources into .brand-gen/inspiration."""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def read_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text())
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


def load_registry(path: Path) -> dict:
    if not path.exists():
        raise SystemExit(f"Source registry not found: {path}")
    return read_json(path)


def load_index(path: Path) -> dict:
    if not path.exists():
        return {"version": 1, "lastRun": None, "sources": {}}
    payload = read_json(path)
    payload.setdefault("version", 1)
    payload.setdefault("lastRun", None)
    payload.setdefault("sources", {})
    return payload


def discover_design_memory_cmd() -> list[str]:
    direct = shutil.which("design-memory")
    if direct:
        return [direct]
    if (Path("/tmp/design-memory") / "package.json").exists():
        return ["npx", "--prefix", "/tmp/design-memory", "design-memory"]
    raise SystemExit(
        "design-memory is not available. Install it first or clone it to /tmp/design-memory."
    )


def verify_design_memory(cmd: list[str]) -> None:
    probe = subprocess.run(cmd + ["--version"], capture_output=True, text=True, check=False)
    if probe.returncode != 0:
        raise SystemExit(
            "design-memory preflight failed. Ensure the CLI works before running extract-inspiration."
        )


def filter_sources(registry: dict, category: str | None, source_keys: list[str] | None, limit: int | None) -> list[dict]:
    items = list(registry.get("sources", []))
    if category:
        items = [item for item in items if item.get("category") == category]
    if source_keys:
        wanted = set(source_keys)
        items = [item for item in items if item.get("key") in wanted]
    if limit:
        items = items[:limit]
    return items


def extract_one(cmd: list[str], source: dict, target_root: Path, timeout: int) -> dict:
    target = target_root / source["category"] / source["key"]
    target.mkdir(parents=True, exist_ok=True)
    start = time.time()
    proc = subprocess.run(
        cmd + ["learn", source["url"], "--project-root", str(target)],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    duration = round(time.time() - start, 2)
    if proc.returncode == 0:
        return {
            "key": source["key"],
            "status": "complete",
            "error": None,
            "duration": duration,
            "designMemoryPath": str((target / ".design-memory").resolve()),
        }
    error = (proc.stderr or proc.stdout or "unknown failure").strip().splitlines()[-1][:500]
    return {
        "key": source["key"],
        "status": "failed",
        "error": error,
        "duration": duration,
        "designMemoryPath": str((target / ".design-memory").resolve()),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Batch extract inspiration design systems with design-memory")
    parser.add_argument("--brand-gen-dir", required=True)
    parser.add_argument("--category")
    parser.add_argument("--source", action="append")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--timeout", type=int, default=120)
    args = parser.parse_args()

    brand_gen_dir = Path(args.brand_gen_dir).expanduser().resolve()
    registry_path = brand_gen_dir / "sources" / "brand_example_sources.json"
    index_path = brand_gen_dir / "inspiration" / "index.json"
    registry = load_registry(registry_path)
    index = load_index(index_path)
    design_cmd = discover_design_memory_cmd()
    verify_design_memory(design_cmd)

    items = filter_sources(registry, args.category, args.source, args.limit)
    if not items:
        print("No inspiration sources matched the requested filters.", file=sys.stderr)
        return 1

    pending: list[dict] = []
    skipped = 0
    for item in items:
        current = index["sources"].get(item["key"], {})
        if current.get("status") == "complete" and not args.force:
            skipped += 1
            continue
        pending.append(item)

    print(f"Preparing inspiration extraction: {len(items)} selected, {len(pending)} to run, {skipped} cached.")
    results: list[dict] = []
    if pending:
        with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
            future_map = {
                executor.submit(extract_one, design_cmd, item, brand_gen_dir / "inspiration", args.timeout): item
                for item in pending
            }
            total = len(pending)
            completed = 0
            for future in concurrent.futures.as_completed(future_map):
                item = future_map[future]
                completed += 1
                print(f"[{completed}/{total}] extracting: {item['key']} ({item['category']})...")
                try:
                    results.append(future.result())
                except subprocess.TimeoutExpired:
                    results.append({
                        "key": item["key"],
                        "status": "failed",
                        "error": f"timeout after {args.timeout}s",
                        "duration": args.timeout,
                        "designMemoryPath": str((brand_gen_dir / 'inspiration' / item['category'] / item['key'] / '.design-memory').resolve()),
                    })

    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    index["lastRun"] = now
    for item in items:
        entry = index["sources"].get(item["key"], {})
        entry.update({
            "url": item["url"],
            "category": item["category"],
        })
        index["sources"][item["key"]] = entry
    for result in results:
        entry = index["sources"].get(result["key"], {})
        entry.update({
            "status": result["status"],
            "error": result["error"],
            "extractedAt": now if result["status"] == "complete" else None,
            "designMemoryPath": result["designMemoryPath"],
        })
        index["sources"][result["key"]] = entry
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(json.dumps(index, indent=2) + "\n")

    complete = sum(1 for item in results if item["status"] == "complete")
    failed = sum(1 for item in results if item["status"] == "failed")
    print(f"Done: {complete}/{len(items)} extracted, {failed} failed, {skipped} skipped (cached).")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
