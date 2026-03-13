#!/usr/bin/env python3
"""Initialize .brand-gen structure and optionally migrate an existing brand-materials workspace."""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = {
    "version": 2,
    "active": None,
    "activeSession": None,
    "inspirationMode": False,
    "brandGenDir": None,
}


def read_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text())
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def ensure_json(path: Path, payload: dict) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n")


def detect_brand_name(brand_name: str | None, legacy_dir: Path | None) -> str | None:
    if brand_name:
        return brand_name.strip()
    if legacy_dir:
        profile = legacy_dir / "brand-profile.json"
        if profile.exists():
            data = read_json(profile)
            detected = data.get("brand_name")
            if detected:
                return str(detected).strip().lower().replace(" ", "-")
    return None


def copy_if_missing(src: Path, dest: Path) -> None:
    if dest.exists():
        return
    if src.is_dir():
        shutil.copytree(src, dest)
    else:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)


def copy_tree_non_destructive(src: Path, dest: Path) -> None:
    if not src.exists():
        return
    for path in src.rglob("*"):
        rel = path.relative_to(src)
        target = dest / rel
        if path.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            continue
        if target.exists():
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)


def build_empty_index(sources_data: dict) -> dict:
    return {
        "version": 1,
        "lastRun": None,
        "sources": {
            item["key"]: {
                "url": item["url"],
                "category": item["category"],
                "status": "pending",
                "extractedAt": None,
                "error": None,
                "designMemoryPath": None,
            }
            for item in sources_data.get("sources", [])
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Initialize .brand-gen structure and optionally migrate legacy brand-materials")
    parser.add_argument("--brand-gen-dir", help="Override .brand-gen location")
    parser.add_argument("--brand-name", help="Brand key to initialize / activate")
    parser.add_argument("--legacy-brand-dir", help="Optional existing brand-materials directory to migrate")
    args = parser.parse_args()

    brand_gen_dir = Path(args.brand_gen_dir).expanduser().resolve() if args.brand_gen_dir else (REPO_ROOT / ".brand-gen")
    legacy_dir = Path(args.legacy_brand_dir).expanduser().resolve() if args.legacy_brand_dir else None
    sources_src = REPO_ROOT / "data" / "brand_example_sources.json"

    ensure_dir(brand_gen_dir)
    ensure_dir(brand_gen_dir / "sources")
    ensure_dir(brand_gen_dir / "brands")
    ensure_dir(brand_gen_dir / "sessions")
    ensure_dir(brand_gen_dir / "inspiration")

    config_path = brand_gen_dir / "config.json"
    config = read_json(config_path) if config_path.exists() else dict(DEFAULT_CONFIG)
    config = {**DEFAULT_CONFIG, **config}

    if sources_src.exists():
        copy_if_missing(sources_src, brand_gen_dir / "sources" / "brand_example_sources.json")
        sources_data = read_json(brand_gen_dir / "sources" / "brand_example_sources.json")
        for category in sources_data.get("categories", []):
            ensure_dir(brand_gen_dir / "inspiration" / category["key"])
        ensure_json(brand_gen_dir / "inspiration" / "index.json", build_empty_index(sources_data))
    else:
        print("WARNING: data/brand_example_sources.json not found; skipping source registry copy.")

    detected_brand = detect_brand_name(args.brand_name, legacy_dir)
    if detected_brand:
        brand_dir = brand_gen_dir / "brands" / detected_brand
        ensure_dir(brand_dir)
        ensure_dir(brand_dir / "screenshots")
        if legacy_dir and legacy_dir.exists():
            copy_tree_non_destructive(legacy_dir, brand_dir)
        if not config.get("active"):
            config["active"] = detected_brand

    config_path.write_text(json.dumps(config, indent=2) + "\n")
    print(f"Brand-gen dir: {brand_gen_dir}")
    print(f"Config: {config_path}")
    if detected_brand:
        print(f"Active brand: {config.get('active')}")
        print(f"Brand dir: {brand_gen_dir / 'brands' / detected_brand}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
