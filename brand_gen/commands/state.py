from __future__ import annotations

import json
import uuid

from ..runtime import *
from ..material_planning import *
from ..generation_flow import *
from ..session_summary import *
from ..media_board import *
from ..brand_scaffold import build_profile_from_brief, deep_merge_defaults, load_brand_profile_template

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
    template = load_brand_profile_template()
    if profile_path.exists():
        profile_payload = load_json_file(profile_path)
    else:
        working_name = args.working_name or args.brand or "Working Brand"
        profile_payload = build_profile_from_brief(
            brand_name=working_name,
            brand_dir=brand_dir,
            description=args.goal or "Session brand under active exploration.",
        )
    profile_payload = deep_merge_defaults(profile_payload or {}, template)
    profile_payload["profile_version"] = max(int(profile_payload.get("profile_version") or 1), 2)
    profile_payload["project_root"] = str(brand_dir)
    if not profile_payload.get("brand_name"):
        profile_payload["brand_name"] = args.working_name or args.brand or "Working Brand"
    if not profile_payload.get("description"):
        profile_payload["description"] = args.goal or "Session brand under active exploration."
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

def cmd_switch_brand(args):
    """Typed verb variant of cmd_use — takes --brand-key as a named flag for MCP ergonomics."""
    class _Adapted:
        brand = str(getattr(args, "brand_key", "") or "").strip()
        list_only = False
        format = str(getattr(args, "format", "json") or "json")
    if not _Adapted.brand:
        raise SystemExit("--brand-key is required")
    return cmd_use(_Adapted)


def cmd_get_pending_reviews(args):
    """List runs whose derived status is awaiting_review."""
    from ..run_state import list_pending_reviews as _list_pending

    brand_dir = get_brand_dir()
    limit = getattr(args, "limit", None)
    runs = _list_pending(brand_dir, limit=limit if isinstance(limit, int) and limit > 0 else None)
    payload = {
        "brand_dir": str(brand_dir),
        "count": len(runs),
        "runs": [run.to_dict() for run in runs],
    }
    print(json.dumps(payload, indent=2))


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


def cmd_append_forbidden_pattern(args):
    from ..custom_scratchpad import append_forbidden_pattern, custom_scratchpad_json_path, load_custom_scratchpad_json
    from ..run_ledger import append_run_event

    brand_dir = get_brand_dir()
    pattern = str(getattr(args, "pattern", "") or "").strip()
    if not pattern:
        raise SystemExit("--pattern is required")
    reason = str(getattr(args, "reason", "") or "").strip()
    source_version = str(getattr(args, "source_version", "") or "").strip()
    dry_run = bool(getattr(args, "dry_run", False))
    before = load_custom_scratchpad_json(brand_dir)
    existing = list(before.get("forbidden_patterns") or [])
    duplicate = pattern.lower() in {
        str(item.get("pattern") or "").strip().lower()
        for item in existing
        if isinstance(item, dict)
    }

    if not dry_run and not duplicate:
        append_forbidden_pattern(
            brand_dir,
            pattern=pattern,
            reason=reason,
            source_version=source_version,
            via_cli=True,
        )
        after = load_custom_scratchpad_json(brand_dir)
        total_forbidden_patterns = len(list(after.get("forbidden_patterns") or []))
        status = "appended"
    elif dry_run:
        total_forbidden_patterns = len(existing) + (0 if duplicate else 1)
        status = "duplicate" if duplicate else "would_append"
    else:
        total_forbidden_patterns = len(existing)
        status = "duplicate"

    if not dry_run:
        append_run_event(
            brand_dir,
            uuid.uuid4().hex[:12],
            stage="mutation",
            event_type="forbidden_pattern_appended",
            source_version=source_version,
            status=status,
            notes=reason,
            data={"pattern": pattern, "duplicate": duplicate},
        )

    result = {
        "status": status,
        "pattern": pattern,
        "reason": reason,
        "source_version": source_version,
        "duplicate": duplicate,
        "path": str(custom_scratchpad_json_path(brand_dir)),
        "total_forbidden_patterns": total_forbidden_patterns,
    }
    if getattr(args, "format", "json") == "json":
        print(json.dumps(result, indent=2))
        return
    print(f"{status}: {pattern}")


LEARNING_BUCKETS = (
    "modelPreferences",
    "colorInsights",
    "compositionPatterns",
    "failurePatterns",
    "messagingInsights",
    "audienceInsights",
)


def cmd_promote_learning(args):
    from ..learnings_memory import append_learning_entry, learnings_memory_path, load_learnings_memory, save_learnings_memory
    from ..run_ledger import append_run_event

    brand_dir = get_brand_dir()
    bucket = str(getattr(args, "bucket", "") or "").strip()
    if bucket not in LEARNING_BUCKETS:
        raise SystemExit(f"--bucket must be one of: {', '.join(LEARNING_BUCKETS)}")
    text = str(getattr(args, "text", "") or "").strip()
    if not text:
        raise SystemExit("--text is required")
    material_type = str(getattr(args, "material_type", "") or "").strip()
    evidence_versions = [str(item).strip() for item in (getattr(args, "evidence_version", None) or []) if str(item).strip()]
    dry_run = bool(getattr(args, "dry_run", False))
    memory = load_learnings_memory(brand_dir)
    existing = list(memory.get(bucket) or [])
    existing_text = {
        (str(item.get("text") or "") if isinstance(item, dict) else str(item or "")).strip().lower()
        for item in existing
        if (str(item.get("text") or "") if isinstance(item, dict) else str(item or "")).strip()
    }
    duplicate = text.lower() in existing_text
    entry = {
        "text": text,
        "material_type": material_type,
        "evidence_versions": evidence_versions,
        "source": "typed_mutation_tool",
        "promoted_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }

    if dry_run:
        status = "duplicate" if duplicate else "would_promote"
        total_in_bucket = len(existing) + (0 if duplicate else 1)
    else:
        appended = append_learning_entry(memory, bucket, entry)
        if appended:
            memory["lastUpdated"] = entry["promoted_at"]
            save_learnings_memory(brand_dir, memory)
            status = "promoted"
        else:
            status = "duplicate"
        duplicate = not appended
        total_in_bucket = len(list(memory.get(bucket) or []))

    if not dry_run:
        append_run_event(
            brand_dir,
            uuid.uuid4().hex[:12],
            stage="mutation",
            event_type="learning_promoted",
            material_type=material_type,
            status=status,
            notes=text,
            data={"bucket": bucket, "evidence_versions": evidence_versions, "duplicate": duplicate},
        )

    result = {
        "status": status,
        "bucket": bucket,
        "text": text,
        "material_type": material_type,
        "evidence_versions": evidence_versions,
        "duplicate": duplicate,
        "path": str(learnings_memory_path(brand_dir)),
        "total_in_bucket": total_in_bucket,
    }
    if getattr(args, "format", "json") == "json":
        print(json.dumps(result, indent=2))
        return
    print(f"{status}: {bucket} -> {text}")


def cmd_append_custom_scratchpad_note(args):
    from ..custom_scratchpad import append_scratchpad_note, custom_scratchpad_md_path
    from ..run_ledger import append_run_event

    brand_dir = get_brand_dir()
    section = str(getattr(args, "section", "") or "").strip().lower()
    text = str(getattr(args, "text", "") or "").strip()
    if not section:
        raise SystemExit("--section is required")
    if not text:
        raise SystemExit("--text is required")
    dry_run = bool(getattr(args, "dry_run", False))
    path = custom_scratchpad_md_path(brand_dir)
    if dry_run:
        chars_added = len(f"- {text}\n")
        result = {
            "status": "would_append",
            "section": section,
            "path": str(path),
            "chars_added": chars_added,
        }
    else:
        chars_added = append_scratchpad_note(brand_dir, section=section, bullet=text, via_cli=True)
        status = "appended" if chars_added else "duplicate"
        append_run_event(
            brand_dir,
            uuid.uuid4().hex[:12],
            stage="mutation",
            event_type="scratchpad_note_appended",
            status=status,
            notes=text,
            data={"section": section, "chars_added": chars_added},
        )
        result = {
            "status": status,
            "section": section,
            "path": str(path),
            "chars_added": chars_added,
        }
    print(json.dumps(result, indent=2))


def cmd_set_motion_grammar(args):
    from ..motion_grammar import set_motion_grammar
    from ..custom_scratchpad import custom_scratchpad_json_path, custom_scratchpad_md_path
    from ..run_ledger import append_run_event

    brand_dir = get_brand_dir()
    director = str(getattr(args, "director", "") or "").strip()
    if not director:
        raise SystemExit("--director is required")
    favored = [str(item).strip() for item in (getattr(args, "favored", None) or []) if str(item).strip()]
    banned = [str(item).strip() for item in (getattr(args, "banned", None) or []) if str(item).strip()]
    intensity = str(getattr(args, "intensity", "") or "").strip()
    dry_run = bool(getattr(args, "dry_run", False))
    payload = {
        "director": director,
        "favored": favored,
        "banned": banned,
        "intensity": intensity,
    }
    if dry_run:
        result = {
            "status": "would_set",
            "motion_grammar": payload,
            "json_path": str(custom_scratchpad_json_path(brand_dir)),
            "markdown_path": str(custom_scratchpad_md_path(brand_dir)),
        }
    else:
        payload = set_motion_grammar(
            brand_dir,
            director=director,
            favored=favored,
            banned=banned,
            intensity=intensity,
            via_cli=True,
        )
        append_run_event(
            brand_dir,
            uuid.uuid4().hex[:12],
            stage="mutation",
            event_type="motion_grammar_set",
            status="set",
            notes=director,
            data=payload,
        )
        result = {
            "status": "set",
            "motion_grammar": payload,
            "json_path": str(custom_scratchpad_json_path(brand_dir)),
            "markdown_path": str(custom_scratchpad_md_path(brand_dir)),
        }
    print(json.dumps(result, indent=2))


def cmd_promote_style_policy(args):
    from ..learnings_memory import append_learning_entry, learnings_memory_path, load_learnings_memory, save_learnings_memory
    from ..run_ledger import append_run_event

    brand_dir = get_brand_dir()
    material_type = str(getattr(args, "material_type", "") or "").strip()
    if not material_type:
        raise SystemExit("--material-type is required")
    anchors = [str(item).strip() for item in (getattr(args, "anchor", None) or []) if str(item).strip()]
    if not anchors:
        raise SystemExit("at least one --anchor is required")
    applies_to = [str(item).strip() for item in (getattr(args, "apply_to", None) or []) if str(item).strip()] or [material_type]
    reference_policy = str(getattr(args, "reference_policy", "single_style_anchor") or "single_style_anchor").strip()
    style_anchor_role = str(getattr(args, "style_anchor_role", "style") or "style").strip()
    text = str(getattr(args, "text", "") or "").strip() or f"[{material_type}] Style policy anchored on {', '.join(anchors)}"
    evidence_versions = [str(item).strip() for item in (getattr(args, "evidence_version", None) or []) if str(item).strip()]
    must_carry_forward = [str(item).strip() for item in (getattr(args, "must_carry_forward", None) or []) if str(item).strip()]
    dry_run = bool(getattr(args, "dry_run", False))
    memory = load_learnings_memory(brand_dir)
    existing = list(memory.get("styleReferencePolicies") or [])
    existing_text = {
        (str(item.get("text") or "") if isinstance(item, dict) else str(item or "")).strip().lower()
        for item in existing
        if (str(item.get("text") or "") if isinstance(item, dict) else str(item or "")).strip()
    }
    entry = {
        "text": text,
        "material_type": material_type,
        "applies_to_material_types": applies_to,
        "required_style_reference_versions": anchors,
        "reference_policy": reference_policy,
        "style_anchor_role": style_anchor_role,
        "evidence_versions": evidence_versions,
        "source": str(getattr(args, "source", "typed_mutation_tool") or "typed_mutation_tool").strip(),
        "promoted_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "failure_mode_if_missing": str(getattr(args, "failure_mode_if_missing", "") or "").strip(),
        "model_behavior_note": str(getattr(args, "model_behavior_note", "") or "").strip(),
        "must_carry_forward": must_carry_forward,
        "correction_note": str(getattr(args, "correction_note", "") or "").strip(),
    }
    duplicate = any(
        isinstance(item, dict)
        and str(item.get("material_type") or "").strip() == material_type
        and list(item.get("required_style_reference_versions") or []) == anchors
        and str(item.get("reference_policy") or "").strip() == reference_policy
        for item in existing
    ) or text.lower() in existing_text

    if dry_run:
        status = "duplicate" if duplicate else "would_promote"
        total_in_bucket = len(existing) + (0 if duplicate else 1)
    else:
        appended = append_learning_entry(memory, "styleReferencePolicies", entry)
        if appended:
            memory["lastUpdated"] = entry["promoted_at"]
            save_learnings_memory(brand_dir, memory)
            status = "promoted"
        else:
            status = "duplicate"
        duplicate = not appended
        total_in_bucket = len(list(memory.get("styleReferencePolicies") or []))
        append_run_event(
            brand_dir,
            uuid.uuid4().hex[:12],
            stage="mutation",
            event_type="style_policy_promoted",
            material_type=material_type,
            status=status,
            notes=text,
            data={"anchors": anchors, "reference_policy": reference_policy, "duplicate": duplicate},
        )

    result = {
        "status": status,
        "material_type": material_type,
        "reference_policy": reference_policy,
        "anchors": anchors,
        "duplicate": duplicate,
        "path": str(learnings_memory_path(brand_dir)),
        "total_in_bucket": total_in_bucket,
    }
    print(json.dumps(result, indent=2))
