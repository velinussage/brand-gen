#!/usr/bin/env python3
"""Initialize .brand-gen structure and optionally migrate an existing brand-materials workspace."""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

from brand_scaffold import (
    build_profile_from_brief,
    ensure_brand_structure,
    parse_csv_values,
    read_json,
    register_brand,
    slugify,
    write_json,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
BUILD_IDENTITY_PY = REPO_ROOT / "scripts" / "build_brand_identity.py"
DEFAULT_CONFIG = {
    "version": 2,
    "active": None,
    "activeSession": None,
    "inspirationMode": False,
    "brandGenDir": None,
}


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def ensure_json(path: Path, payload: dict) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n")


def detect_brand_identity(brand_name: str | None, legacy_dir: Path | None) -> tuple[str | None, str | None]:
    if brand_name:
        display = brand_name.strip()
        return slugify(display), display
    if legacy_dir:
        profile = legacy_dir / "brand-profile.json"
        if profile.exists():
            data = read_json(profile)
            detected = str(data.get("brand_name") or "").strip()
            if detected:
                return slugify(detected), detected
    return None, None


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


def scaffold_brand_files(brand_dir: Path, *, brand_name: str, description: str = "", tone: list[str] | None = None, palette: list[str] | None = None, keywords: list[str] | None = None, homepage_url: str = "", voice_description: str = "", value_props: list[str] | None = None) -> tuple[Path, Path, bool]:
    profile_path = brand_dir / "brand-profile.json"
    existing_profile = read_json(profile_path)
    profile_payload = build_profile_from_brief(
        brand_name=brand_name,
        brand_dir=brand_dir,
        description=description or (existing_profile.get("description") or "A working brand scaffold. Add more detail through conversation, extraction, and iteration."),
        tone_words=tone or [],
        palette=palette or [],
        keywords=keywords or [],
        homepage_url=homepage_url or str(existing_profile.get("homepage_url") or ""),
        voice_description=voice_description or str((((existing_profile.get("messaging") or {}).get("voice") or {}).get("description") or "")),
        value_props=value_props or [],
        profile=existing_profile,
    )
    changed = profile_payload != existing_profile
    if changed or not profile_path.exists():
        write_json(profile_path, profile_payload)

    identity_path = brand_dir / "brand-identity.json"
    identity_md_path = brand_dir / "brand-identity.md"
    should_build_identity = changed or not identity_path.exists() or not identity_md_path.exists()
    if should_build_identity:
        subprocess.run([
            sys.executable,
            str(BUILD_IDENTITY_PY),
            "--profile",
            str(profile_path),
            "--output-json",
            str(identity_path),
            "--output-markdown",
            str(identity_md_path),
        ], check=True)
    return profile_path, identity_path, should_build_identity


def main() -> int:
    parser = argparse.ArgumentParser(description="Initialize .brand-gen structure and optionally migrate legacy brand-materials")
    parser.add_argument("--brand-gen-dir", help="Override .brand-gen location")
    parser.add_argument("--brand-name", help="Brand key to initialize / activate")
    parser.add_argument("--legacy-brand-dir", help="Optional existing brand-materials directory to migrate")
    parser.add_argument("--description", help="Short plain-language brand or product description")
    parser.add_argument("--tone", action="append", help="Comma-separated tone words; repeatable")
    parser.add_argument("--palette", action="append", help="Comma-separated palette hex values; repeatable")
    parser.add_argument("--keywords", action="append", help="Comma-separated keywords; repeatable")
    parser.add_argument("--homepage-url", help="Optional homepage URL")
    parser.add_argument("--voice-description", help="Optional short description of the desired brand voice")
    parser.add_argument("--value-prop", action="append", help="Approved value proposition; repeatable")
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

    brand_key, display_name = detect_brand_identity(args.brand_name, legacy_dir)
    if brand_key and display_name:
        brand_dir = brand_gen_dir / "brands" / brand_key
        ensure_brand_structure(brand_dir)
        if legacy_dir and legacy_dir.exists():
            copy_tree_non_destructive(legacy_dir, brand_dir)
        tone_words = parse_csv_values(*(args.tone or []))
        palette = parse_csv_values(*(args.palette or []))
        keywords = parse_csv_values(*(args.keywords or []))
        value_props = parse_csv_values(*(args.value_prop or []))
        profile_path, identity_path, rebuilt_identity = scaffold_brand_files(
            brand_dir,
            brand_name=display_name,
            description=args.description or "",
            tone=tone_words,
            palette=palette,
            keywords=keywords,
            homepage_url=args.homepage_url or "",
            voice_description=args.voice_description or "",
            value_props=value_props,
        )
        config["active"] = brand_key
        register_brand(brand_gen_dir, brand_key, {
            "name": display_name,
            "path": str(brand_dir),
            "profile": str(profile_path),
            "identity": str(identity_path),
            "description": args.description or read_json(profile_path).get("description") or "",
            "homepage_url": args.homepage_url or read_json(profile_path).get("homepage_url") or "",
        })

    config_path.write_text(json.dumps(config, indent=2) + "\n")
    print(f"Brand-gen dir: {brand_gen_dir}")
    print(f"Config: {config_path}")
    if brand_key and display_name:
        print(f"Active brand: {config.get('active')}")
        print(f"Brand dir: {brand_gen_dir / 'brands' / brand_key}")
        print(f"Profile: {brand_gen_dir / 'brands' / brand_key / 'brand-profile.json'}")
        print(f"Identity: {brand_gen_dir / 'brands' / brand_key / 'brand-identity.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
