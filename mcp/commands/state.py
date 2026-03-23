from __future__ import annotations

from ..runtime import *
from ..material_planning import *
from ..generation_flow import *
from ..session_summary import *
from ..media_board import *

def cmd_bootstrap(args):
    manifest = load_manifest()
    brand_dir = get_brand_dir()
    brand_dir.mkdir(parents=True, exist_ok=True)
    added = 0
    for path in sorted(brand_dir.iterdir()):
        match = re.match(r"(v\d+)", path.stem)
        if not match or path.suffix.lower() not in SUPPORTED_MEDIA_EXTS:
            continue
        vid = match.group(1)
        material_type = infer_material_type_from_filename(path.name)
        generation_mode = MATERIAL_CONFIG.get(material_type, {}).get("generation_mode", "image")
        if vid in manifest["versions"]:
            entry = manifest["versions"][vid]
            if path.name not in entry.get("files", []):
                entry.setdefault("files", []).append(path.name)
            continue
        manifest["versions"][vid] = {
            "prompt": "",
            "model": "",
            "mode": "",
            "material_type": material_type,
            "generation_mode": generation_mode,
            "aspect_ratio": "",
            "duration": None,
            "tag": re.sub(r"^v\d+-?", "", path.stem),
            "files": [path.name],
            "reference_images": [],
            "reference_count": 0,
            "reference_dir": "",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(path.stat().st_mtime)),
            "score": None,
            "notes": "",
            "status": None,
        }
        added += 1
    save_manifest(manifest)
    print(f"Bootstrap complete: {added} new versions added, {len(manifest['versions'])} total in manifest")

def cmd_init(args):
    brand_gen_dir = Path(args.brand_gen_dir).expanduser().resolve() if args.brand_gen_dir else (get_brand_gen_dir() or (REPO_ROOT / ".brand-gen"))
    if args.legacy_brand_dir:
        legacy_dir = Path(args.legacy_brand_dir).expanduser().resolve()
    else:
        candidate = get_legacy_brand_dir()
        legacy_dir = candidate.resolve() if candidate.exists() else None
    cmd = ["--brand-gen-dir", str(brand_gen_dir)]
    if args.brand_name:
        cmd += ["--brand-name", args.brand_name]
    if legacy_dir:
        cmd += ["--legacy-brand-dir", str(legacy_dir)]
    run_child_script(REPO_ROOT / "scripts" / "init_brand_gen.py", cmd)

def cmd_create_brand(args):
    brand_gen_dir = Path(args.brand_gen_dir).expanduser().resolve() if args.brand_gen_dir else (get_brand_gen_dir() or (REPO_ROOT / ".brand-gen"))
    cmd = ["--brand-gen-dir", str(brand_gen_dir), "--brand-name", args.name]
    if args.description:
        cmd += ["--description", args.description]
    if args.homepage_url:
        cmd += ["--homepage-url", args.homepage_url]
    if args.voice_description:
        cmd += ["--voice-description", args.voice_description]
    for item in args.tone or []:
        cmd += ["--tone", item]
    for item in args.palette or []:
        cmd += ["--palette", item]
    for item in args.keywords or []:
        cmd += ["--keywords", item]
    for item in args.value_prop or []:
        cmd += ["--value-prop", item]
    run_child_script(REPO_ROOT / "scripts" / "init_brand_gen.py", cmd)
    if getattr(args, "consolidate_inspiration", False) or getattr(args, "inspiration_image", None):
        active = resolve_active_brand_key(brand_gen_dir=brand_gen_dir, repo_root=REPO_ROOT)
        if not active:
            return
        brand_dir = brand_gen_dir / "brands" / active
        payload = consolidate_inspiration_memory(
            brand_dir,
            images=list(getattr(args, "inspiration_image", None) or []),
            env=build_env(),
        )
        save_inspiration_memory(brand_dir, payload)

def cmd_start_testing(args):
    brand_gen_dir = Path(args.brand_gen_dir).expanduser().resolve() if args.brand_gen_dir else (get_brand_gen_dir() or (REPO_ROOT / ".brand-gen"))
    brand_gen_dir.mkdir(parents=True, exist_ok=True)
    (brand_gen_dir / "sessions").mkdir(parents=True, exist_ok=True)
    session_key = slugify(args.session_name or args.working_name or args.brand or f"session-{time.strftime('%Y%m%d-%H%M%S')}")
    session_root = brand_gen_dir / "sessions" / session_key
    brand_dir = session_root / "brand-materials"
    brand_dir.mkdir(parents=True, exist_ok=True)
    for child in ["plans", "sets", "examples", "reviews", "references", "product-screens", "inspiration", "motion-references"]:
        (brand_dir / child).mkdir(parents=True, exist_ok=True)

    seeded_from = ""
    if args.brand:
        source_dir = brand_gen_dir / "brands" / args.brand
        if not source_dir.exists():
            raise SystemExit(f"Brand '{args.brand}' not found under {brand_gen_dir / 'brands'}")
        for path in source_dir.rglob('*'):
            rel = path.relative_to(source_dir)
            target = brand_dir / rel
            if path.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                if not target.exists():
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(path, target)
        seeded_from = args.brand

    profile_path = brand_dir / "brand-profile.json"
    if profile_path.exists():
        profile_payload = load_json_file(profile_path)
    else:
        working_name = args.working_name or args.brand or "Working Brand"
        profile_payload = {
            "profile_version": 2,
            "brand_name": working_name,
            "description": args.goal or "Session brand under active exploration.",
            "project_root": str(brand_dir),
            "keywords": [],
            "color_candidates": [],
            "font_candidates": [],
            "radius_tokens": [],
            "logo_candidates": [],
            "brand_assets": {
                "icon": "",
                "wordmark": "",
                "lockup": "",
                "icon_candidates": [],
                "wordmark_candidates": [],
                "lockup_candidates": [],
                "allow_synthetic_lockup": False,
            },
            "design_language": {},
            "brand_guardrail_prelude": "",
        }
    profile_payload["session_context"] = {
        "type": "testing-session",
        "session_key": session_key,
        "seeded_from_brand": seeded_from,
        "goal": args.goal or "",
        "notes": "Build brand memory from reverse interviews, references, and iteration before promoting to a saved brand.",
    }
    profile_path.write_text(json.dumps(profile_payload, indent=2) + "\n")

    identity_path = brand_dir / "brand-identity.json"
    if not identity_path.exists():
        cmd = [sys.executable, str(BUILD_IDENTITY_PY), "--profile", str(profile_path), "--output-json", str(identity_path), "--output-markdown", str(brand_dir / "brand-identity.md")]
        subprocess.run(cmd, check=False)
    if identity_path.exists():
        identity_payload = load_json_file(identity_path)
        identity_payload["session_context"] = {
            "type": "testing-session",
            "session_key": session_key,
            "seeded_from_brand": seeded_from,
            "goal": args.goal or "",
        }
        identity_path.write_text(json.dumps(identity_payload, indent=2) + "\n")

    profile = load_json_file(profile_path)
    identity = load_json_file(identity_path)
    board = load_blackboard(brand_dir, profile, identity)
    append_blackboard_decision(
        board,
        agent="brand_director",
        decision=f"Started testing session '{session_key}'{' seeded from ' + seeded_from if seeded_from else ''}.",
        confidence=0.95,
        data={"goal": args.goal or "", "seeded_from_brand": seeded_from},
    )
    save_blackboard(brand_dir, board)

    config = load_brand_gen_config(brand_gen_dir=brand_gen_dir, repo_root=REPO_ROOT)
    config["activeSession"] = session_key
    save_brand_gen_config(config, brand_gen_dir=brand_gen_dir, repo_root=REPO_ROOT)
    print(f"Testing session: {session_key}")
    print(f"Session brand dir: {brand_dir}")
    if seeded_from:
        print(f"Seeded from brand: {seeded_from}")
    print("\nNext:")
    print(f"- Run the main skill in {REPO_ROOT / 'skills' / 'brand-gen' / 'SKILL.md'}")
    print(f"- Reverse interview into: {REPO_ROOT / 'prompts' / 'start-brand-testing.md'}")
    print("- Then route-request -> plan-draft -> critique-plan -> build-generation-scratchpad -> generate --scratchpad")

def cmd_use(args):
    brand_gen_dir = get_brand_gen_dir() or (REPO_ROOT / ".brand-gen")
    brand_dirs = list_brand_dirs(brand_gen_dir)
    if args.list_only:
        class _Args:
            format = getattr(args, "format", "text")
        return cmd_list_brands(_Args())
    if not args.brand:
        raise SystemExit("Specify a brand key or use --list.")
    wanted = args.brand.strip()
    available = {path.name: path for path in brand_dirs}
    if wanted not in available:
        raise SystemExit(f"Brand '{wanted}' not found. Available: {', '.join(sorted(available)) or 'none'}")
    config = load_brand_gen_config(brand_gen_dir=brand_gen_dir, repo_root=REPO_ROOT)
    config["active"] = wanted
    config["activeSession"] = None
    save_brand_gen_config(config, brand_gen_dir=brand_gen_dir, repo_root=REPO_ROOT)
    fmt = getattr(args, "format", "text")
    if fmt == "json":
        import json
        print(json.dumps({"active_brand": wanted}, indent=2))
    else:
        print(f"Active brand: {wanted}")

def cmd_list_brands(args):
    brand_gen_dir = get_brand_gen_dir()
    if not brand_gen_dir:
        print("No .brand-gen directory found.")
        return
    active = resolve_active_brand_key(brand_gen_dir=brand_gen_dir, repo_root=REPO_ROOT)
    registry = load_brand_registry(brand_gen_dir)
    registry_items = registry.get("brands") or {}
    items = []
    for brand_dir in list_brand_dirs(brand_gen_dir):
        profile = brand_dir / "brand-profile.json"
        identity = brand_dir / "brand-identity.json"
        inspirations = load_inspirations_config(brand_dir.name, brand_gen_dir)
        report = validate_identity_summary(profile, identity, load_json_file(profile), load_json_file(identity))
        reg = registry_items.get(brand_dir.name) or {}
        items.append({
            "key": brand_dir.name,
            "name": reg.get("name") or (load_json_file(profile).get("brand_name") or brand_dir.name),
            "description": reg.get("description") or (load_json_file(profile).get("description") or ""),
            "active": brand_dir.name == active,
            "profile": profile.exists(),
            "identity": identity.exists(),
            "score": f"{report['score']}/{report['max_score']}",
            "warnings": len(report["warnings"]),
            "inspiration_sources": len(inspirations.get("sources", [])),
        })
    if args.format == "json":
        print(json.dumps(items, indent=2))
        return
    print(f"{'':<2} {'BRAND':<20} {'PROFILE':<8} {'IDENTITY':<9} {'VALID':<8} {'WARN':<5} {'INSP'}")
    print("-" * 80)
    for item in items:
        marker = "*" if item["active"] else " "
        print(f"{marker:<2} {item['key']:<20} {str(item['profile']):<8} {str(item['identity']):<9} {item['score']:<8} {item['warnings']:<5} {item['inspiration_sources']}")
        if item["description"]:
            print(f"   {item['description'][:120]}")
