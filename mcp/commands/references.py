from __future__ import annotations

import argparse

from ..runtime import *
from ..material_planning import *
from ..generation_flow import *
from ..session_summary import *
from ..media_board import *

def cmd_consolidate_inspiration(args):
    brand_dir = get_brand_dir()
    brand_dir.mkdir(parents=True, exist_ok=True)
    payload = consolidate_inspiration_memory(
        brand_dir,
        images=list(getattr(args, "image", None) or []),
        env=build_env(),
    )
    json_path, md_path = save_inspiration_memory(brand_dir, payload)
    if getattr(args, "format", "text") == "json":
        print(json.dumps({**payload, "json_path": str(json_path), "markdown_path": str(md_path)}, indent=2))
        return
    print(f"Inspiration memory: {json_path}")
    print(f"Markdown summary: {md_path}")
    print(f"Sources: {len(payload.get('sources') or [])}")
    if payload.get("summary"):
        print(f"\nSummary: {payload['summary']}")


def cmd_inspire(args):
    if args.sources or args.clear or args.show or args.brand:
        return cmd_configure_inspiration(args)
    brand_dir = get_brand_dir()
    inspo_dir = brand_dir / "inspiration"
    inspo_dir.mkdir(parents=True, exist_ok=True)
    category = (args.category or "symbol").lower()
    url = args.url or INSPIRE_URLS.get(category, INSPIRE_URLS["symbol"])
    if args.list_only:
        files = sorted(inspo_dir.glob("*"))
        if not files:
            print(f"No inspiration files in {inspo_dir}")
            print(f"Browse {url} and save screenshots there.")
            return
        print(f"Inspiration assets ({len(files)}):")
        for path in files:
            print(f"  {path.name}")
        return
    print(f"Opening {url}")
    print(f"Save references to: {inspo_dir}/")
    print("Tips:")
    print("  - Use scripts/collect_inspiration.py for automated capture from Logo System or any URL")
    print("  - Capture references for logos, posters, banners, storyboards, or motion styleframes")
    if sys.platform == "darwin":
        subprocess.run(["open", url], check=False)


def cmd_inspiration_list(args):
    if getattr(args, "show_config", False):
        show_args = argparse.Namespace(
            brand=getattr(args, "brand", None),
            category=getattr(args, "brand", None) or getattr(args, "category", None),
            sources=None,
            clear=False,
            show=True,
            format=getattr(args, "format", "json"),
        )
        return cmd_configure_inspiration(show_args)
    brand_dir = get_brand_dir()
    inspo_dir = brand_dir / "inspiration"
    inspo_dir.mkdir(parents=True, exist_ok=True)
    files = sorted(inspo_dir.glob("*"))
    payload = {
        "category": getattr(args, "category", "symbol"),
        "path": str(inspo_dir.resolve()),
        "files": [
            {
                "name": path.name,
                "path": str(path.resolve()),
            }
            for path in files
            if path.is_file()
        ],
    }
    if getattr(args, "format", "json") == "json":
        print(json.dumps(payload, indent=2))
        return
    if not payload["files"]:
        print(f"No inspiration files in {inspo_dir}")
        return
    print(f"Inspiration assets ({len(payload['files'])}):")
    for item in payload["files"]:
        print(f"  {item['name']}")


def cmd_inspiration_capture(args):
    brand_dir = get_brand_dir()
    out_dir = Path(args.out_dir).expanduser().resolve() if getattr(args, "out_dir", None) else (brand_dir / "inspiration").resolve()
    cmd = ["--out-dir", str(out_dir), "--count", str(getattr(args, "count", 3) or 3)]
    if getattr(args, "url", None):
        cmd += ["--url", args.url]
        if getattr(args, "label", None):
            cmd += ["--label", args.label]
    else:
        cmd += ["--category", getattr(args, "category", "symbol")]
    if getattr(args, "open_folder", False):
        cmd.append("--open-folder")
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "collect_inspiration.py"), *cmd],
        env=build_env(),
        capture_output=True,
        text=True,
    )
    output = result.stdout.strip()
    if result.stderr:
        output = (output + "\n" if output else "") + result.stderr.strip()
    payload = {
        "ok": result.returncode == 0,
        "out_dir": str(out_dir),
        "category": getattr(args, "category", "symbol"),
        "url": getattr(args, "url", None) or "",
        "output": output,
    }
    if getattr(args, "format", "json") == "json":
        print(json.dumps(payload, indent=2))
        if result.returncode != 0:
            sys.exit(result.returncode)
        return
    if output:
        print(output)
    if result.returncode != 0:
        sys.exit(result.returncode)


def cmd_inspiration_configure(args):
    cfg_args = argparse.Namespace(
        brand=getattr(args, "brand", None),
        category=None,
        sources=getattr(args, "sources", None),
        clear=False,
        show=bool(getattr(args, "show", False)),
        format=getattr(args, "format", "json"),
    )
    return cmd_configure_inspiration(cfg_args)


def cmd_inspiration_clear(args):
    cfg_args = argparse.Namespace(
        brand=getattr(args, "brand", None),
        category=None,
        sources=None,
        clear=True,
        show=False,
        format=getattr(args, "format", "json"),
    )
    return cmd_configure_inspiration(cfg_args)

def cmd_extract_inspiration(args):
    brand_gen_dir = get_brand_gen_dir()
    if not brand_gen_dir:
        raise SystemExit("No .brand-gen directory found. Run: brand_iterate.py init")
    cmd = [
        "--brand-gen-dir", str(brand_gen_dir),
        "--workers", str(args.workers),
        "--timeout", str(args.timeout),
    ]
    if args.category:
        cmd += ["--category", args.category]
    if args.limit:
        cmd += ["--limit", str(args.limit)]
    if args.force:
        cmd += ["--force"]
    for source in args.source or []:
        cmd += ["--source", source]
    run_child_script(REPO_ROOT / "scripts" / "batch_extract_inspiration.py", cmd)


def cmd_inspiration_mode(args):
    brand_gen_dir = get_brand_gen_dir() or (REPO_ROOT / ".brand-gen")
    config = load_brand_gen_config(brand_gen_dir=brand_gen_dir, repo_root=REPO_ROOT)
    if args.state:
        state = args.state.lower()
        if state not in {"on", "off"}:
            raise SystemExit("State must be 'on' or 'off'.")
        config["inspirationMode"] = state == "on"
        save_brand_gen_config(config, brand_gen_dir=brand_gen_dir, repo_root=REPO_ROOT)
    print(f"inspirationMode: {'on' if config.get('inspirationMode') else 'off'}")


def cmd_configure_inspiration(args):
    brand_gen_dir = get_brand_gen_dir()
    if not brand_gen_dir:
        raise SystemExit("No .brand-gen directory found. Run: brand_iterate.py init")
    brand = args.brand or args.category or resolve_active_brand_key(brand_gen_dir=brand_gen_dir, repo_root=REPO_ROOT)
    if not brand:
        raise SystemExit("No brand specified and no active brand set.")
    brand_dir = brand_gen_dir / "brands" / brand
    if not brand_dir.exists():
        raise SystemExit(f"Brand '{brand}' not found under {brand_gen_dir / 'brands'}")

    index = load_inspiration_index(brand_gen_dir).get("sources", {})
    config = load_inspirations_config(brand, brand_gen_dir)

    if args.clear:
        config["sources"] = []
        save_inspirations_config(config, brand, brand_gen_dir)
        print(f"Cleared inspiration sources for {brand}")
        return

    if args.sources:
        sources = [item.strip() for chunk in args.sources for item in chunk.split(",") if item.strip()]
        warnings = []
        for source in sources:
            if source not in index:
                warnings.append(f"{source}: not indexed")
            elif index[source].get("status") != "complete":
                warnings.append(f"{source}: status={index[source].get('status') or 'unknown'}")
        config["sources"] = sources
        save_inspirations_config(config, brand, brand_gen_dir)
        print(f"Inspiration sources for {brand}: {', '.join(sources) or 'none'}")
        if warnings:
            warn("; ".join(warnings))
        return

    show_payload = {
        "brand": brand,
        "config": config,
        "available_indexed_sources": sorted(index.keys()),
    }
    if args.format == "json":
        print(json.dumps(show_payload, indent=2))
    else:
        print(f"Brand: {brand}")
        print(f"Sources: {', '.join(config.get('sources', [])) or 'none'}")
        print(f"Mode: {config.get('mode', 'principles')}")

def cmd_shotlist(args):
    brand_dir = get_brand_dir()
    brand_dir.mkdir(parents=True, exist_ok=True)
    output = Path(args.output).expanduser() if args.output else brand_dir / "PRODUCT-SHOTLIST.md"
    cmd = ["plan", "--output", str(output.resolve())]
    if args.product_name:
        cmd += ["--product-name", args.product_name]
    if args.goal:
        cmd += ["--goal", args.goal]
    run_child_script(PRODUCT_SCREENS_PY, cmd)


def cmd_capture_product(args):
    brand_dir = get_brand_dir()
    brand_dir.mkdir(parents=True, exist_ok=True)
    out_dir = Path(args.out_dir).expanduser() if args.out_dir else brand_dir / "product-screens"
    cmd = ["capture", "--out-dir", str(out_dir.resolve()), "--count", str(args.count), "--scroll-px", str(args.scroll_px)]
    if args.url:
        cmd += ["--url", args.url]
    if args.label:
        cmd += ["--label", args.label]
    for shot in args.shot or []:
        cmd += ["--shot", shot]
    if getattr(args, "cdp", None):
        cmd += ["--cdp", str(args.cdp)]
    if getattr(args, "preset", None):
        cmd += ["--preset", args.preset]
    if args.session:
        cmd += ["--session", args.session]
    if args.open_folder:
        cmd.append("--open-folder")
    run_child_script(PRODUCT_SCREENS_PY, cmd)


def cmd_explore_brand(args):
    brand_dir = get_brand_dir()
    brand_dir.mkdir(parents=True, exist_ok=True)
    output = Path(args.output).expanduser() if args.output else brand_dir / "brand-concept-directions.md"
    output_json = Path(args.output_json).expanduser() if args.output_json else brand_dir / "brand-concept-directions.json"
    cmd = ["--output", str(output.resolve()), "--output-json", str(output_json.resolve()), "--top", str(args.top)]
    if args.profile:
        cmd += ["--profile", str(Path(args.profile).expanduser().resolve())]
    if args.brand_name:
        cmd += ["--brand-name", args.brand_name]
    if args.business:
        cmd += ["--business", args.business]
    if args.audience:
        cmd += ["--audience", args.audience]
    if args.tone:
        cmd += ["--tone", args.tone]
    if args.avoid:
        cmd += ["--avoid", args.avoid]
    if args.product_context:
        cmd += ["--product-context", args.product_context]
    for material in args.material or []:
        cmd += ["--material", material]
    for source in args.source or []:
        cmd += ["--source", source]
    run_child_script(EXPLORE_BRAND_PY, cmd)

def cmd_example_sources(args):
    cmd = ["list"]
    if args.category:
        cmd += ["--category", args.category]
    if args.query:
        cmd += ["--query", args.query]
    if args.format:
        cmd += ["--format", args.format]
    run_child_script(BRAND_EXAMPLES_PY, cmd)


def cmd_collect_examples(args):
    brand_dir = get_brand_dir()
    brand_dir.mkdir(parents=True, exist_ok=True)
    out_dir = Path(args.out_dir).expanduser() if args.out_dir else brand_dir / "examples"
    cmd = ["capture", "--out-dir", str(out_dir.resolve()), "--width", str(args.width), "--height", str(args.height)]
    if args.category:
        cmd += ["--category", args.category]
    if args.query:
        cmd += ["--query", args.query]
    if args.limit:
        cmd += ["--limit", str(args.limit)]
    for site in args.site or []:
        cmd += ["--site", site]
    if args.open_folder:
        cmd.append("--open-folder")
    run_child_script(BRAND_EXAMPLES_PY, cmd)


def cmd_social_specs(args):
    key = (args.format or "").strip().lower()
    items = SOCIAL_SPECS.items()
    if key:
        if key not in SOCIAL_SPECS:
            available = ", ".join(sorted(SOCIAL_SPECS))
            print(f"Unknown format '{args.format}'. Available: {available}", file=sys.stderr)
            sys.exit(1)
        items = [(key, SOCIAL_SPECS[key])]
    print(f"{'FORMAT':<24} {'SIZE':<14} {'ASPECT':<10} {'LABEL'}")
    print("-" * 120)
    for name, spec in items:
        size = f"{spec['width']}x{spec['height']}"
        print(f"{name:<24} {size:<14} {spec['aspect_ratio']:<10} {spec['label']}")
        if args.verbose:
            print(f"  notes: {spec['notes']}")
            print(f"  source: {spec['source']}")
            print()
