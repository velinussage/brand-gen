from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from ..runtime import *
from ..material_planning import *
from ..generation_flow import *
from ..session_summary import *
from ..media_board import *
from ..brand_scaffold import build_profile_from_brief, deep_merge_defaults, load_brand_profile_template
from ..brand_prompt_pack import ensure_brand_prompt_pack
from ..material_taxonomy_migration import (
    find_saved_workspaces,
    migrate_workspace as migrate_taxonomy_workspace,
    migrate_workspaces as migrate_taxonomy_workspaces,
    report_workspace_deprecated_usage,
    report_workspaces_deprecated_usage,
)

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
    active = resolve_active_brand_key(brand_gen_dir=brand_gen_dir, repo_root=REPO_ROOT)
    if active:
        brand_dir = brand_gen_dir / "brands" / active
        profile = load_json_file(brand_dir / "brand-profile.json")
        identity = load_json_file(brand_dir / "brand-identity.json")
        if profile:
            ensure_brand_prompt_pack(brand_dir, profile=profile, identity=identity)
    if getattr(args, "consolidate_inspiration", False) or getattr(args, "inspiration_image", None):
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
    ensure_brand_prompt_pack(brand_dir, profile=profile, identity=identity)
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

def _resolve_taxonomy_target_workspaces(args) -> list[Path]:
    explicit_brand_dir = str(getattr(args, "brand_dir", "") or "").strip()
    if explicit_brand_dir:
        return [Path(explicit_brand_dir).expanduser().resolve()]
    if bool(getattr(args, "all_saved", False)):
        return find_saved_workspaces(
            REPO_ROOT,
            get_brand_gen_dir(),
            include_sessions=bool(getattr(args, "include_sessions", False)),
        )
    return [get_brand_dir()]


def cmd_migrate_material_taxonomy(args):
    workspaces = _resolve_taxonomy_target_workspaces(args)
    apply = bool(getattr(args, "apply", False))
    payload = (
        migrate_taxonomy_workspaces(workspaces, apply=apply)
        if len(workspaces) > 1
        else migrate_taxonomy_workspace(workspaces[0], apply=apply)
    )
    if getattr(args, "format", "text") == "json":
        print(json.dumps(payload, indent=2))
        return
    mode = "Applied" if apply else "Dry run"
    if len(workspaces) == 1 and "brand_dir" in payload:
        print(f"{mode} taxonomy migration for: {payload['brand_dir']}")
        print(f"Total changes: {payload.get('changes', 0)}")
        for item in payload.get("files_changed") or []:
            print(f"- {item['kind']}: {item['path']} ({item['changes']} changes)")
        if payload.get("errors"):
            print("\nErrors:")
            for item in payload["errors"]:
                print(f"- {item['path']}: {item['error']}")
    else:
        print(f"{mode} taxonomy migration across {len(workspaces)} workspaces")
        print(f"Total changes: {payload.get('changes', 0)}")
        for item in payload.get("results") or []:
            print(f"- {item['brand_dir']}: {item.get('changes', 0)} changes")
    if not apply and payload.get("changes"):
        print("\nRe-run with --apply to write these updates.")


def cmd_report_material_taxonomy(args):
    workspaces = _resolve_taxonomy_target_workspaces(args)
    payload = (
        report_workspaces_deprecated_usage(workspaces)
        if len(workspaces) > 1
        else report_workspace_deprecated_usage(workspaces[0])
    )
    if getattr(args, "format", "text") == "json":
        print(json.dumps(payload, indent=2))
        return
    if len(workspaces) == 1 and "brand_dir" in payload:
        print(f"Deprecated material-type usage report: {payload['brand_dir']}")
        print(f"Scanned files: {payload.get('scanned_files', 0)}")
        print(f"Remaining deprecated usages: {payload.get('deprecated_usage_count', 0)}")
        print("By file class:")
        for file_class, item in (payload.get("by_file_class") or {}).items():
            print(f"- {file_class}: {item.get('count', 0)} hits")
        print("By material type:")
        for material_type, item in (payload.get("deprecated_material_types") or {}).items():
            print(f"- {material_type} → {item.get('preferred_material_type') or 'n/a'}: {item.get('count', 0)} hits across {item.get('file_count', 0)} files")
    else:
        print(f"Deprecated material-type usage report across {len(workspaces)} workspaces")
        print(f"Remaining deprecated usages: {payload.get('deprecated_usage_count', 0)}")
        print("By file class:")
        for file_class, item in (payload.get("aggregate_by_file_class") or {}).items():
            print(f"- {file_class}: {item.get('count', 0)} hits across {item.get('workspace_count', 0)} workspaces")
        print("By material type:")
        for material_type, item in (payload.get("aggregate") or {}).items():
            print(f"- {material_type} → {item.get('preferred_material_type') or 'n/a'}: {item.get('count', 0)} hits across {item.get('workspace_count', 0)} workspaces")
        for item in payload.get("results") or []:
            print(f"  · {item['brand_dir']}: {item.get('deprecated_usage_count', 0)} hits")


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
    from ..mutations_ledger import append_mutation_event, content_hash
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

    json_path = custom_scratchpad_json_path(brand_dir)
    before_hash = content_hash(json_path)

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
        append_mutation_event(
            brand_dir,
            verb="append-forbidden-pattern",
            target_path=json_path,
            action=status,
            before_hash=before_hash,
            after_hash=content_hash(json_path),
            diff_summary=f"forbidden pattern: {pattern[:80]}",
            reason=reason,
            source_version=source_version,
            data={"pattern": pattern, "duplicate": duplicate, "total_forbidden_patterns": total_forbidden_patterns},
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
    from ..frontmatter import read_only_warning
    from ..mutations_ledger import append_mutation_event, content_hash
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
    warning = read_only_warning(path)
    if warning and not bool(getattr(args, "force", False)):
        raise SystemExit(f"{warning}\nPass --force to override (mutation will still be recorded in mutations.jsonl).")
    if dry_run:
        chars_added = len(f"- {text}\n")
        result = {
            "status": "would_append",
            "section": section,
            "path": str(path),
            "chars_added": chars_added,
        }
    else:
        before_hash = content_hash(path)
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
        append_mutation_event(
            brand_dir,
            verb="append-custom-scratchpad-note",
            target_path=path,
            action=status,
            before_hash=before_hash,
            after_hash=content_hash(path),
            diff_summary=f"{section}: {text[:80]}",
            data={"section": section, "chars_added": chars_added},
        )
        result = {
            "status": status,
            "section": section,
            "path": str(path),
            "chars_added": chars_added,
        }
    print(json.dumps(result, indent=2))


def cmd_promote_aesthetic_learning(args):
    from ..aesthetic_curation import promote_aesthetic_learning
    from ..run_ledger import append_run_event

    brand_dir = get_brand_dir()
    result = promote_aesthetic_learning(
        brand_dir,
        capsule_id=getattr(args, "capsule_id", None) or "",
        material_type=getattr(args, "material_type", None) or "",
        sentiment=getattr(args, "sentiment", "like") or "like",
        note=getattr(args, "note", "") or "",
    )
    append_run_event(
        brand_dir,
        uuid.uuid4().hex[:12],
        stage="mutation",
        event_type="aesthetic_learning_promoted",
        material_type=getattr(args, "material_type", None) or "",
        status=result.get("status") or "recorded",
        notes=getattr(args, "note", "") or "",
        data={"capsule_id": getattr(args, "capsule_id", None) or "", "sentiment": getattr(args, "sentiment", "like") or "like"},
    )
    if getattr(args, "format", "json") == "json":
        print(json.dumps(result, indent=2))
        return
    print(f"{result.get('status')}: {result.get('entry', {}).get('capsule_id')}")


_BRAND_CONTRACT_LIST_FIELDS = {
    "approved_phrases",
    "illustration_concepts",
    "negative_constraints",
    "brand_anchor_sources",
}


def _brand_contract_path() -> Path:
    from ..runtime_paths import SCRIPT_DIR
    return SCRIPT_DIR.parent / "data" / "sage_brand_contract.json"


def _load_brand_contract_dict() -> dict:
    path = _brand_contract_path()
    if not path.exists():
        return {"schema_version": 1}
    return json.loads(path.read_text())


def _save_brand_contract_dict(data: dict) -> Path:
    from ..brand_contract_schema import validate_brand_contract
    ok, msg = validate_brand_contract(data)
    if not ok:
        raise SystemExit(f"refusing to write invalid brand contract: {msg}")
    path = _brand_contract_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n")
    return path


def _mutate_brand_contract_list(args, *, field: str, verb: str, mode: str) -> None:
    """Append-or-remove on a list-shaped key in sage_brand_contract.json.

    mode is 'append' or 'remove'. Writes a state_mutation event with full
    provenance (before/after hashes, reason, source_version).
    """
    from ..mutations_ledger import append_mutation_event, content_hash
    from ..run_ledger import append_run_event

    if field not in _BRAND_CONTRACT_LIST_FIELDS:
        raise SystemExit(f"unsupported brand-contract list field: {field}")

    item = str(getattr(args, "item", "") or "").strip()
    if not item:
        raise SystemExit("--item is required")
    reason = str(getattr(args, "reason", "") or "").strip()
    source_version = str(getattr(args, "source_version", "") or "").strip()
    dry_run = bool(getattr(args, "dry_run", False))

    contract = _load_brand_contract_dict()
    current = list(contract.get(field) or [])
    current_lower = {str(x).strip().lower() for x in current}
    item_lower = item.lower()
    duplicate = item_lower in current_lower

    if mode == "append":
        if duplicate:
            status = "duplicate"
            new_list = current
        else:
            status = "would_append" if dry_run else "appended"
            new_list = current + [item]
    elif mode == "remove":
        if not duplicate:
            status = "missing"
            new_list = current
        else:
            status = "would_remove" if dry_run else "removed"
            new_list = [x for x in current if str(x).strip().lower() != item_lower]
    else:
        raise SystemExit(f"unsupported mode: {mode}")

    path = _brand_contract_path()
    before_hash = content_hash(path)
    if not dry_run and status in {"appended", "removed"}:
        contract[field] = new_list
        _save_brand_contract_dict(contract)

    brand_dir = get_brand_dir()
    if not dry_run and status in {"appended", "removed"}:
        append_run_event(
            brand_dir,
            uuid.uuid4().hex[:12],
            stage="mutation",
            event_type=f"{field}_{mode}d",
            source_version=source_version,
            status=status,
            notes=reason,
            data={"field": field, "item": item, "verb": verb},
        )
        append_mutation_event(
            brand_dir,
            verb=verb,
            target_path=path,
            action=status,
            before_hash=before_hash,
            after_hash=content_hash(path),
            diff_summary=f"{mode} {field}: {item[:80]}",
            reason=reason,
            source_version=source_version,
            data={"field": field, "item": item, "total_after": len(new_list)},
        )

    result = {
        "status": status,
        "field": field,
        "item": item,
        "mode": mode,
        "reason": reason,
        "source_version": source_version,
        "path": str(path),
        "total_after": len(new_list),
    }
    if getattr(args, "format", "json") == "json":
        print(json.dumps(result, indent=2))
        return
    print(f"{status}: {item}")


def cmd_sage_approved_phrase_add(args):
    _mutate_brand_contract_list(args, field="approved_phrases", verb="sage-approved-phrase-add", mode="append")


def cmd_sage_approved_phrase_remove(args):
    _mutate_brand_contract_list(args, field="approved_phrases", verb="sage-approved-phrase-remove", mode="remove")


def cmd_sage_negative_constraint_add(args):
    _mutate_brand_contract_list(args, field="negative_constraints", verb="sage-negative-constraint-add", mode="append")


def cmd_sage_negative_constraint_remove(args):
    _mutate_brand_contract_list(args, field="negative_constraints", verb="sage-negative-constraint-remove", mode="remove")


def cmd_sage_illustration_concept_add(args):
    _mutate_brand_contract_list(args, field="illustration_concepts", verb="sage-illustration-concept-add", mode="append")


def cmd_sage_illustration_concept_remove(args):
    _mutate_brand_contract_list(args, field="illustration_concepts", verb="sage-illustration-concept-remove", mode="remove")


def cmd_sage_brand_anchor_source_add(args):
    _mutate_brand_contract_list(args, field="brand_anchor_sources", verb="sage-brand-anchor-source-add", mode="append")


def cmd_sage_brand_anchor_source_remove(args):
    _mutate_brand_contract_list(args, field="brand_anchor_sources", verb="sage-brand-anchor-source-remove", mode="remove")


def cmd_framing_direction_add(args):
    """Upsert a framing direction. Structured fields go to JSON; prose to <brand>/voice/framing/<id>.md."""
    from ..framing_directions import write_framing_markdown
    from ..mutations_ledger import append_mutation_event, content_hash
    from ..run_ledger import append_run_event

    framing_id = str(getattr(args, "id", "") or "").strip()
    if not framing_id:
        raise SystemExit("--id is required")
    label = str(getattr(args, "label", "") or "").strip()
    keywords = [str(item).strip() for item in (getattr(args, "keyword", None) or []) if str(item).strip()]
    source_cues = str(getattr(args, "source_cues", "") or "").strip()
    source_priority = str(getattr(args, "source_priority", "") or "").strip()
    directive = str(getattr(args, "directive", "") or "").strip()
    adoption_scene = str(getattr(args, "adoption_scene", "") or "").strip()
    style_anchor = str(getattr(args, "style_anchor", "") or "").strip()
    body_file = str(getattr(args, "body_file", "") or "").strip()
    if body_file:
        body_path = Path(body_file).expanduser()
        if not body_path.exists():
            raise SystemExit(f"--body-file not found: {body_path}")
        from ..framing_directions import parse_framing_markdown
        parsed = parse_framing_markdown(body_path.read_text(encoding="utf-8"))
        directive = directive or parsed.get("directive", "")
        adoption_scene = adoption_scene or parsed.get("adoption_scene", "")
        style_anchor = style_anchor or parsed.get("style_anchor", "")
        if not label and parsed.get("label"):
            label = parsed["label"]
    reason = str(getattr(args, "reason", "") or "").strip()
    source_version = str(getattr(args, "source_version", "") or "").strip()
    dry_run = bool(getattr(args, "dry_run", False))

    contract = _load_brand_contract_dict()
    directions = list(contract.get("framing_directions") or [])
    found_idx = next(
        (i for i, d in enumerate(directions) if isinstance(d, dict) and str(d.get("id") or "").strip() == framing_id),
        -1,
    )
    structured: dict[str, Any] = {"id": framing_id}
    if label:
        structured["label"] = label
    if keywords:
        structured["keywords"] = keywords
    if source_cues:
        structured["source_cues"] = source_cues
    if source_priority:
        structured["source_priority"] = source_priority

    action = "updated" if found_idx >= 0 else "inserted"
    if dry_run:
        action = "would_update" if found_idx >= 0 else "would_insert"

    contract_path = _brand_contract_path()
    contract_before_hash = content_hash(contract_path)

    if not dry_run:
        if found_idx >= 0:
            merged = dict(directions[found_idx])
            merged.update(structured)
            directions[found_idx] = merged
        else:
            directions.append(structured)
        contract["framing_directions"] = directions
        _save_brand_contract_dict(contract)

    md_path: Path | None = None
    md_before_hash = ""
    md_after_hash = ""
    if directive or adoption_scene or style_anchor:
        brand_dir = get_brand_dir()
        from ..framing_directions import voice_framing_dir
        md_path = voice_framing_dir(brand_dir) / f"{framing_id}.md"
        md_before_hash = content_hash(md_path)
        if not dry_run:
            write_framing_markdown(
                brand_dir,
                framing_id=framing_id,
                label=label or (directions[found_idx].get("label") if found_idx >= 0 else ""),
                directive=directive,
                adoption_scene=adoption_scene,
                style_anchor=style_anchor,
            )
            md_after_hash = content_hash(md_path)

    if not dry_run:
        brand_dir = get_brand_dir()
        append_run_event(
            brand_dir,
            uuid.uuid4().hex[:12],
            stage="mutation",
            event_type=f"framing_direction_{action}",
            source_version=source_version,
            status=action,
            notes=reason,
            data={"id": framing_id, "label": label},
        )
        append_mutation_event(
            brand_dir,
            verb="framing-direction-add",
            target_path=contract_path,
            action=action,
            before_hash=contract_before_hash,
            after_hash=content_hash(contract_path),
            diff_summary=f"framing direction {framing_id} {action}",
            reason=reason,
            source_version=source_version,
            data={"id": framing_id, "label": label, "has_prose": bool(directive or adoption_scene or style_anchor)},
        )
        if md_path is not None:
            append_mutation_event(
                brand_dir,
                verb="framing-direction-add",
                target_path=md_path,
                action=action,
                before_hash=md_before_hash,
                after_hash=md_after_hash,
                diff_summary=f"voice/framing/{framing_id}.md {action}",
                reason=reason,
                source_version=source_version,
                data={"id": framing_id},
            )

    result = {
        "status": action,
        "id": framing_id,
        "contract_path": str(contract_path),
        "voice_path": str(md_path) if md_path else "",
        "reason": reason,
        "source_version": source_version,
    }
    if getattr(args, "format", "json") == "json":
        print(json.dumps(result, indent=2))
        return
    print(f"{action}: {framing_id}")


def cmd_framing_direction_remove(args):
    from ..framing_directions import voice_framing_dir
    from ..mutations_ledger import append_mutation_event, content_hash
    from ..run_ledger import append_run_event

    framing_id = str(getattr(args, "id", "") or "").strip()
    if not framing_id:
        raise SystemExit("--id is required")
    reason = str(getattr(args, "reason", "") or "").strip()
    source_version = str(getattr(args, "source_version", "") or "").strip()
    keep_voice = bool(getattr(args, "keep_voice", False))
    dry_run = bool(getattr(args, "dry_run", False))

    contract = _load_brand_contract_dict()
    directions = list(contract.get("framing_directions") or [])
    found_idx = next(
        (i for i, d in enumerate(directions) if isinstance(d, dict) and str(d.get("id") or "").strip() == framing_id),
        -1,
    )
    contract_path = _brand_contract_path()
    contract_before_hash = content_hash(contract_path)
    brand_dir = get_brand_dir()
    md_path = voice_framing_dir(brand_dir) / f"{framing_id}.md"
    md_before_hash = content_hash(md_path)

    if found_idx < 0 and not md_path.exists():
        action = "missing"
    else:
        action = "would_remove" if dry_run else "removed"

    if not dry_run and action == "removed":
        if found_idx >= 0:
            del directions[found_idx]
            contract["framing_directions"] = directions
            _save_brand_contract_dict(contract)
        if md_path.exists() and not keep_voice:
            md_path.unlink()
        append_run_event(
            brand_dir,
            uuid.uuid4().hex[:12],
            stage="mutation",
            event_type="framing_direction_removed",
            source_version=source_version,
            status=action,
            notes=reason,
            data={"id": framing_id, "kept_voice": keep_voice},
        )
        append_mutation_event(
            brand_dir,
            verb="framing-direction-remove",
            target_path=contract_path,
            action=action,
            before_hash=contract_before_hash,
            after_hash=content_hash(contract_path),
            diff_summary=f"framing direction {framing_id} removed",
            reason=reason,
            source_version=source_version,
            data={"id": framing_id, "kept_voice": keep_voice},
        )
        if md_path.exists() != bool(keep_voice):  # only log if we touched it
            pass
        elif not keep_voice and md_before_hash:
            append_mutation_event(
                brand_dir,
                verb="framing-direction-remove",
                target_path=md_path,
                action=action,
                before_hash=md_before_hash,
                after_hash="",
                diff_summary=f"voice/framing/{framing_id}.md deleted",
                reason=reason,
                source_version=source_version,
                data={"id": framing_id},
            )

    result = {
        "status": action,
        "id": framing_id,
        "kept_voice": keep_voice,
        "contract_path": str(contract_path),
        "voice_path": str(md_path),
        "reason": reason,
        "source_version": source_version,
    }
    if getattr(args, "format", "json") == "json":
        print(json.dumps(result, indent=2))
        return
    print(f"{action}: {framing_id}")


def cmd_contract_status(args):
    """Surface read-only-after files, brand-contract status, and recent mutations.

    Acts as the "verbose greeting" hook in the architect's PR-9: agents
    starting work on a brand can run `bgen contract-status` to see what
    is locked, what schema validation says, and what the last few state
    mutations were.
    """
    from ..brand_contract_schema import brand_contract_schema_path, validate_brand_contract
    from ..frontmatter import find_read_only_files
    from ..mutations_ledger import load_mutation_events, mutations_ledger_path
    from ..runtime_paths import SCRIPT_DIR

    brand_dir = get_brand_dir()
    limit = int(getattr(args, "limit_mutations", 10) or 10)
    fmt = getattr(args, "format", "json")

    # Brand-contract location resolution: per-brand contract.json (PR-4) or
    # legacy data/<brand>_brand_contract.json (PR-1) or no contract yet.
    per_brand_contract = brand_dir / "contract.json"
    legacy_contract = SCRIPT_DIR.parent / "data" / "sage_brand_contract.json"
    contract_path: Path | None = None
    if per_brand_contract.exists():
        contract_path = per_brand_contract
    elif legacy_contract.exists():
        contract_path = legacy_contract

    contract_status = "missing"
    contract_message = ""
    if contract_path is not None:
        try:
            contract = json.loads(contract_path.read_text())
        except (OSError, json.JSONDecodeError) as err:
            contract_status = "unreadable"
            contract_message = str(err)
        else:
            ok, msg = validate_brand_contract(contract)
            contract_status = "valid" if ok else "invalid"
            contract_message = msg

    payload: dict[str, Any] = {
        "brand_dir": str(brand_dir),
        "schema_path": str(brand_contract_schema_path()),
        "contract_path": str(contract_path) if contract_path else "",
        "contract_status": contract_status,
        "contract_message": contract_message,
        "mutations_ledger": str(mutations_ledger_path(brand_dir)),
        "read_only_files": find_read_only_files(brand_dir),
        "recent_mutations": load_mutation_events(brand_dir, limit=limit),
    }

    if fmt == "json":
        print(json.dumps(payload, indent=2, default=str))
        return
    print(f"brand_dir: {payload['brand_dir']}")
    print(f"contract:  {payload['contract_path']}  ({payload['contract_status']})")
    if payload["contract_message"]:
        print(f"  → {payload['contract_message']}")
    print(f"schema:    {payload['schema_path']}")
    print(f"ledger:    {payload['mutations_ledger']}")
    if payload["read_only_files"]:
        print("\nread-only-after files:")
        for entry in payload["read_only_files"]:
            print(f"  {entry['path']}  (after {entry['read_only_after']})")
            if entry.get("read_only_reason"):
                print(f"    reason: {entry['read_only_reason']}")
    else:
        print("\nread-only-after files: (none)")
    if payload["recent_mutations"]:
        print(f"\nrecent mutations (last {len(payload['recent_mutations'])}):")
        for ev in payload["recent_mutations"]:
            print(f"  {ev.get('timestamp', '')}  {ev.get('verb', '')}  {ev.get('action', '')}  {ev.get('diff_summary', '')}")
    else:
        print("\nrecent mutations: (none)")


def cmd_add_aesthetic_capsule(args):
    from ..aesthetic_curation import _CAPSULES_PATH, get_aesthetic_capsule, upsert_aesthetic_capsule
    from ..mutations_ledger import append_mutation_event, content_hash
    from ..run_ledger import append_run_event

    brand_dir = get_brand_dir()
    capsule_id = str(getattr(args, "id", "") or "").strip()
    if not capsule_id:
        raise SystemExit("--id is required")

    def _split(items):
        return [str(item).strip() for item in (items or []) if str(item).strip()]

    label = str(getattr(args, "label", "") or "").strip()
    safe_handle = str(getattr(args, "safe_handle", "") or "").strip()
    internal_handles = _split(getattr(args, "internal_handle", None))
    material_types = _split(getattr(args, "material_type", None))
    use_when = _split(getattr(args, "use_when", None))
    avoid_when = _split(getattr(args, "avoid_when", None))
    positive_terms = _split(getattr(args, "positive_term", None))
    negative_terms = _split(getattr(args, "negative_term", None))
    motifs = _split(getattr(args, "motif", None))
    style_axes = _split(getattr(args, "style_axis", None))
    style_strength = getattr(args, "style_strength_default", None)
    reason = str(getattr(args, "reason", "") or "").strip()
    source_version = str(getattr(args, "source_version", "") or "").strip()
    dry_run = bool(getattr(args, "dry_run", False))

    style_keys = ("medium", "palette", "line", "lighting", "composition", "density", "texture")
    style_description = {key: str(getattr(args, key, "") or "").strip() for key in style_keys}
    style_description = {k: v for k, v in style_description.items() if v}
    if motifs:
        style_description["motifs"] = motifs

    role_keys = ("style_role", "composition_role", "brand_role", "negative_role")
    role_map = {"style_role": "style", "composition_role": "composition", "brand_role": "brand", "negative_role": "negative"}
    reference_roles: dict[str, str] = {}
    for arg_key in role_keys:
        value = str(getattr(args, arg_key, "") or "").strip()
        if value:
            reference_roles[role_map[arg_key]] = value

    capsule: dict = {"id": capsule_id}
    if label:
        capsule["label"] = label
    if safe_handle:
        capsule["safe_handle"] = safe_handle
    if internal_handles:
        capsule["internal_handles"] = internal_handles
    if material_types:
        capsule["material_types"] = material_types
    if use_when:
        capsule["use_when"] = use_when
    if avoid_when:
        capsule["avoid_when"] = avoid_when
    if style_strength is not None and str(style_strength).strip() != "":
        try:
            capsule["style_strength_default"] = float(style_strength)
        except (TypeError, ValueError):
            pass
    if style_description:
        capsule["style_description"] = style_description
    if positive_terms:
        capsule["positive_prompt_terms"] = positive_terms
    if negative_terms:
        capsule["negative_prompt_terms"] = negative_terms
    if style_axes:
        capsule["style_axes"] = style_axes
    if reference_roles:
        capsule["reference_roles"] = reference_roles

    existing = get_aesthetic_capsule(capsule_id)
    if existing:
        merged = dict(existing)
        merged.update(capsule)
        capsule = merged

    if dry_run:
        result = {
            "status": "would_upsert",
            "id": capsule_id,
            "exists": bool(existing),
            "capsule": capsule,
            "reason": reason,
            "source_version": source_version,
        }
    else:
        before_hash = content_hash(_CAPSULES_PATH)
        upsert = upsert_aesthetic_capsule(capsule)
        after_hash = content_hash(_CAPSULES_PATH)
        append_run_event(
            brand_dir,
            uuid.uuid4().hex[:12],
            stage="mutation",
            event_type="aesthetic_capsule_upserted",
            source_version=source_version,
            status=upsert["action"],
            notes=reason,
            data={"capsule_id": capsule_id, "action": upsert["action"]},
        )
        append_mutation_event(
            brand_dir,
            verb="add-aesthetic-capsule",
            target_path=upsert["path"],
            action=upsert["action"],
            before_hash=before_hash,
            after_hash=after_hash,
            diff_summary=f"capsule {capsule_id} {upsert['action']}",
            reason=reason,
            source_version=source_version,
            data={"capsule_id": capsule_id},
        )
        result = {
            "status": upsert["action"],
            "id": capsule_id,
            "path": upsert["path"],
            "reason": reason,
            "source_version": source_version,
        }
    if getattr(args, "format", "json") == "json":
        print(json.dumps(result, indent=2))
        return
    print(f"{result.get('status')}: {capsule_id}")


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
