from __future__ import annotations

from ..inspiration_board import build_inspiration_board_summary, inspiration_board_path, load_inspiration_board
from ..context_surfaces import (
    build_capabilities_payload,
    build_context_snapshot_payload,
    build_source_knowledge_payload,
    build_workspace_status_payload,
    format_workspace_status_text,
    get_prompt_resource,
    list_prompt_resources,
)
from ..learnings_memory import load_learnings_memory, summarize_learnings_memory
from ..runtime import *
from ..material_planning import *
from ..generation_flow import *
from ..reference_analysis import reference_analysis_confidence, reference_analysis_mode
from ..run_ledger import load_run_events
from ..run_state import Run, get_run as project_run_by_id, list_all_runs
from ..artifact_inspection import (
    compare_versions as artifact_compare_versions,
    fetch_critique,
    fetch_plan,
    fetch_review_packet,
    fetch_scratchpad,
    fetch_version,
)
from ..runtime_support import html_escape, version_sort_key as _version_sort_key
from ..session_summary import *
from ..media_board import *

def cmd_show(args):
    manifest = load_manifest()
    versions = manifest["versions"]
    if args.version:
        version = versions.get(args.version)
        if not version:
            print(f"Not found: {args.version}")
            sys.exit(1)
        payload = {
            "version": args.version,
            "entry": version,
            "summary": {
                "total_versions": len(versions),
                "scored_versions": sum(1 for v in versions.values() if v.get("score") is not None),
                "favorites": sum(1 for v in versions.values() if v.get("status") == "favorite"),
            },
        }
        print(json.dumps(payload, indent=2))
        return

    items = list(versions.items())
    filter_mode = "all"
    if args.favorites:
        items = [(k, v) for k, v in items if v.get("status") == "favorite"]
        filter_mode = "favorites"
    elif args.top:
        items = [(k, v) for k, v in items if v.get("score")]
        items.sort(key=lambda x: (-(x[1].get("score") or 0), -_version_sort_key(x[0])))
        items = items[: args.top]
        filter_mode = "top"
    elif args.latest:
        items = sorted(items, key=lambda x: _version_sort_key(x[0]), reverse=True)[: args.latest]
        filter_mode = "latest"
    else:
        items = sorted(items, key=lambda x: _version_sort_key(x[0]))
    if not items:
        print("No versions match filter.")
        return

    if args.format == "json":
        payload = {
            "filter": {
                "mode": filter_mode,
                "favorites": bool(args.favorites),
                "top": args.top,
                "latest": args.latest,
            },
            "summary": {
                "total_versions": len(versions),
                "matched_versions": len(items),
                "scored_versions": sum(1 for v in versions.values() if v.get("score") is not None),
                "favorites": sum(1 for v in versions.values() if v.get("status") == "favorite"),
                "locked_fragments": list(manifest.get("locked_fragments") or []),
            },
            "versions": [{"version": vid, **version} for vid, version in items],
        }
        print(json.dumps(payload, indent=2))
        return

    print(f"{'VER':<8} {'SCORE':<8} {'STATUS':<10} {'TYPE':<20} {'GEN':<8} {'MODE':<12} {'REFS':<6} {'MODEL':<12} {'TAG':<16}")
    print("-" * 132)
    for vid, version in items:
        score = "★" * (version.get("score") or 0) if version.get("score") else "—"
        print(
            f"{vid:<8} {score:<8} {(version.get('status') or ''):<10} "
            f"{(version.get('material_type') or ''):<20} {(version.get('generation_mode') or ''):<8} "
            f"{(version.get('mode') or ''):<12} {str(version.get('reference_count') or 0):<6} "
            f"{(version.get('model') or ''):<12} {(version.get('tag') or '')[:16]:<16}"
        )
    print(f"\n{len(versions)} versions, {sum(1 for v in versions.values() if v.get('score') is not None)} scored, {sum(1 for v in versions.values() if v.get('status') == 'favorite')} favorites")
    if manifest.get("locked_fragments"):
        print(f"\nLocked fragments: {', '.join(manifest['locked_fragments'])}")


def summarize_version_metadata(version_id: str, entry: dict) -> dict:
    prompt_len = entry.get("prompt_char_count") or len(entry.get("prompt") or "")
    raw_prompt = entry.get("raw_prompt") or ""
    prompt_prelude = entry.get("prompt_prelude") or ""
    critic = entry.get("critic_summary") or {}
    prompt_review = entry.get("prompt_review") or {}
    return {
        "version": version_id,
        "material_type": entry.get("material_type") or "",
        "generation_mode": entry.get("generation_mode") or "",
        "mode": entry.get("mode") or "",
        "model": entry.get("model") or "",
        "aspect_ratio": entry.get("aspect_ratio") or "",
        "timestamp": entry.get("timestamp") or "",
        "score": entry.get("score"),
        "status": entry.get("status") or "",
        "workflow_id": entry.get("workflow_id") or "",
        "source_version": entry.get("source_version") or "",
        "scratchpad": entry.get("generation_scratchpad") or "",
        "auto_review_path": entry.get("auto_review_path") or "",
        "files": list(entry.get("files") or []),
        "reference_images": list(entry.get("reference_images") or []),
        "reference_count": entry.get("reference_count") or 0,
        "prompt_chars": prompt_len,
        "raw_prompt_chars": len(raw_prompt),
        "prelude_chars": len(prompt_prelude),
        "critic_issues": list(critic.get("issues") or []),
        "prompt_review_ok": prompt_review.get("ok", True),
        "prompt_review_warnings": list(prompt_review.get("warnings") or []),
        "notes": entry.get("notes") or "",
        "tag": entry.get("tag") or "",
        "prompt": entry.get("prompt") or "",
        "raw_prompt": raw_prompt,
    }


def build_agent_regeneration_prompt(version_id: str, entry: dict) -> str:
    meta = summarize_version_metadata(version_id, entry)
    lines = [
        "Use brand-gen in the current active workspace.",
        f"Start from version {version_id} as the baseline.",
        f"Material type: {meta['material_type'] or 'material'}.",
        f"Workflow mode: {meta['mode'] or 'hybrid'}.",
    ]
    if meta["aspect_ratio"]:
        lines.append(f"Aspect ratio: {meta['aspect_ratio']}.")
    if meta["model"]:
        lines.append(f"Prefer the same model unless there is a clear reason to switch: {meta['model']}.")
    lines.append("Keep the brand direction and any approved messaging that made this version useful.")
    if meta["notes"]:
        lines.append(f"Existing notes to preserve or react to: {meta['notes'][:220]}")
    if meta["critic_issues"]:
        lines.append("Avoid repeating these issues: " + "; ".join(str(item) for item in meta["critic_issues"][:3]))
    if meta["reference_images"]:
        lines.append("Replace the primary product/reference image with <NEW_SCREEN_PATH> if you are using a new screen from the app.")
    else:
        lines.append("If you want to incorporate a new app screen, attach it as <NEW_SCREEN_PATH> and use it as the new primary product truth reference.")
    if meta["material_type"] in {"landing-hero", "social", "campaign-poster", "proof-poster", "merch-poster", "podcast-cover", "podcast-banner", "og-card"}:
        lines.append("If visible copy appears, use explicit user-provided copy or approved messaging only; do not invent new slogans or event names.")
    if meta["raw_prompt"]:
        lines.append(f"Starting prompt seed from {version_id}: {meta['raw_prompt'][:400]}")
    lines.append(f"After generating the new version, compare it against {version_id} and summarize what improved.")
    return "\n".join(lines)


def cmd_compare(args):
    brand_dir = get_brand_dir()
    manifest = load_manifest(brand_dir)
    if args.favorites:
        vids = [k for k, v in manifest["versions"].items() if v.get("status") == "favorite"]
    elif args.top:
        scored = [(k, v) for k, v in manifest["versions"].items() if v.get("score")]
        scored.sort(key=lambda x: -(x[1].get("score") or 0))
        vids = [k for k, _ in scored[: args.top]]
    elif getattr(args, "latest", None):
        vids = [k for k, _ in sorted(manifest["versions"].items(), key=lambda item: _version_sort_key(item[0]), reverse=True)[: args.latest]]
    elif getattr(args, "all_versions", False):
        vids = [k for k, _ in sorted(manifest["versions"].items(), key=lambda item: _version_sort_key(item[0]), reverse=True)]
    else:
        vids = args.versions or [k for k, _ in sorted(manifest["versions"].items(), key=lambda item: _version_sort_key(item[0]), reverse=True)]
    if not vids:
        print("No versions to compare.")
        sys.exit(1)

    filter_label = "selected versions"
    if args.favorites:
        filter_label = "favorites"
    elif args.top:
        filter_label = f"top {args.top}"
    elif getattr(args, "latest", None):
        filter_label = f"latest {args.latest}"
    elif getattr(args, "all_versions", False) or not args.versions:
        filter_label = "all versions"

    out_path = Path(args.output).expanduser() if args.output else None
    result = generate_compare_board(
        brand_dir,
        vids,
        manifest=manifest,
        embed=getattr(args, "embed", False),
        filter_label=filter_label,
        output=out_path,
        open_browser=True,
    )
    print(f"Comparison board: {result} ({len(vids)} versions)")


def cmd_diagnose(args):
    """Compare diagnostic metadata for two or more versions side-by-side."""
    manifest = load_manifest()
    vids = args.versions
    if not vids or len(vids) < 1:
        raise SystemExit("Specify at least one version to diagnose, e.g.: diagnose v14 v15")
    rows: list[dict] = []
    for vid in vids:
        v = manifest["versions"].get(vid)
        if not v:
            print(f"WARNING: {vid} not in manifest", file=sys.stderr)
            continue
        prompt_len = v.get("prompt_char_count") or len(v.get("prompt") or "")
        critic = v.get("critic_summary") or {}
        pr = v.get("prompt_review") or {}
        rows.append({
            "version": vid,
            "material_type": v.get("material_type") or "",
            "model": v.get("model") or "",
            "mode": v.get("mode") or "",
            "aspect_ratio": v.get("aspect_ratio") or "",
            "prompt_chars": prompt_len,
            "prompt_budget_ok": prompt_len <= 1800 if role_pack_material_key(v.get("material_type")) in INTERFACE_MATERIAL_KEYS else "n/a",
            "ref_count": v.get("reference_count") or 0,
            "refs": v.get("reference_images") or [],
            "workflow_id": v.get("workflow_id") or "",
            "scratchpad": v.get("generation_scratchpad") or "",
            "prompt_review_ok": pr.get("ok", True),
            "prompt_review_warnings": pr.get("warnings") or [],
            "critic_issues": critic.get("issues") or [],
            "score": v.get("score"),
            "notes": v.get("notes") or "",
            "status": v.get("status") or "",
            "raw_prompt_chars": len(v.get("raw_prompt") or ""),
            "prelude_chars": len(v.get("prompt_prelude") or ""),
        })
    if args.format == "json":
        print(json.dumps(rows, indent=2))
        return
    for row in rows:
        print(f"=== {row['version']} ===")
        print(f"  material: {row['material_type']}  model: {row['model']}  mode: {row['mode']}  aspect: {row['aspect_ratio']}")
        print(f"  prompt: {row['prompt_chars']} chars (raw: {row['raw_prompt_chars']}, prelude: {row['prelude_chars']})")
        if row['prompt_budget_ok'] != "n/a":
            print(f"  budget ok: {'✓' if row['prompt_budget_ok'] else '✗ OVER BUDGET'}")
        print(f"  refs: {row['ref_count']}  {row['refs']}")
        if row['workflow_id']:
            print(f"  workflow: {row['workflow_id']}")
        if row['scratchpad']:
            print(f"  scratchpad: {row['scratchpad']}")
        if not row['prompt_review_ok']:
            print(f"  ⚠ prompt review FAILED")
        if row['prompt_review_warnings']:
            for w in row['prompt_review_warnings']:
                print(f"    ⚠ {w}")
        if row['critic_issues']:
            for issue in row['critic_issues']:
                print(f"    ⚠ critic: {issue}")
        if row['score'] is not None:
            print(f"  score: {row['score']}/5")
        if row['notes']:
            print(f"  notes: {row['notes'][:200]}")
        if row['status']:
            print(f"  status: {row['status']}")
        print()

def cmd_show_session_summary(args):
    brand_dir = get_brand_dir()
    brand_dir.mkdir(parents=True, exist_ok=True)
    _, _, profile, identity = load_brand_memory(brand_dir, getattr(args, "profile", None), getattr(args, "identity", None))
    payload = build_session_summary_payload(brand_dir, profile, identity, limit=max(1, int(getattr(args, "limit", 5) or 5)))
    if args.format == "json":
        print(json.dumps(payload, indent=2))
        return

    print("Current workspace summary\n")
    print(f"Brand: {payload['brand']['name'] or 'n/a'}")
    workspace = payload['workspace']
    label = workspace.get('kind') or 'workspace'
    if workspace.get('session'):
        label += f" ({workspace['session']})"
    print(f"Workspace: {label}")
    root_status = payload.get("brand_gen_root_status") or {}
    if root_status.get("brand_gen_root"):
        print(f"Brand-gen root: {root_status['brand_gen_root']}")
        print(f"Root resolution: {root_status.get('resolution_mode') or 'n/a'}")
    if workspace.get('seeded_from_brand'):
        print(f"Seeded from: {workspace['seeded_from_brand']}")
    print(f"Brand dir: {payload['brand_dir']}")
    config = payload.get("config") or {}
    print(f"Inspiration mode: {'on' if config.get('inspiration_mode') else 'off'}")
    inspirations = payload.get("inspirations") or {}
    if inspirations.get("sources"):
        print(f"Inspiration sources: {', '.join(inspirations['sources'])}")
    pointers = payload.get("pointers") or {}
    if pointers.get("compare_board"):
        print(f"Compare board: {pointers['compare_board']}")
    if pointers.get("latest_review_packet"):
        print(f"Latest review packet: {pointers['latest_review_packet']}")
    if pointers.get("latest_auto_review"):
        print(f"Latest review/QA: {pointers['latest_auto_review']}")

    generated = payload['generated']
    print(f"\nGenerated versions: {generated['count']} total, {generated['scored']} scored, {generated['unscored']} unscored, {generated['favorites']} favorites")
    if generated['recent_versions']:
        print("Recent versions:")
        for item in generated['recent_versions']:
            score = f" score={item['score']}" if item['score'] is not None else ""
            status = f" {item['status']}" if item['status'] else ""
            workflow = f" workflow={item['workflow_id']}" if item.get('workflow_id') else ""
            print(f"- {item['version']} ({item['material_type'] or 'material'}, {item['timestamp'] or 'n/a'}){score}{status}{workflow}")
    if generated['recent_feedback']:
        print("\nRecent feedback:")
        for item in generated['recent_feedback']:
            parts = [item['version']]
            if item['score'] is not None:
                parts.append(f"score={item['score']}")
            if item['status']:
                parts.append(item['status'])
            if item['notes']:
                parts.append(item['notes'][:140])
            print(f"- {' | '.join(parts)}")

    messaging = payload['messaging']
    print("\nMessaging:")
    print(f"- Tagline: {messaging['tagline'] or 'n/a'}")
    if messaging['elevator']:
        print(f"- Elevator: {messaging['elevator'][:180]}{'…' if len(messaging['elevator']) > 180 else ''}")
    if messaging['voice_description']:
        print(f"- Voice: {messaging['voice_description']}")
    if messaging['value_propositions']:
        print(f"- Value props: {len(messaging['value_propositions'])}")
    counts = messaging['copy_bank_counts']
    print(f"- Copy bank: {counts['headlines']} headlines, {counts['slogans']} slogans, {counts['subheadlines']} subheadlines, {counts['cta_pairs']} CTA pairs")

    iteration = payload['iteration_memory']
    if any(iteration.get(key) for key in ['brand_notes', 'messaging_notes', 'copy_notes']):
        print("\nRecent iteration notes:")
        for label, key in [("Brand", "brand_notes"), ("Messaging", "messaging_notes"), ("Copy", "copy_notes")]:
            items = iteration.get(key) or []
            if items:
                print(f"- {label}: {' | '.join(items[-3:])}")

    blackboard = payload['blackboard']
    artifacts = blackboard.get('artifacts') or {}
    if artifacts:
        print("\nLatest artifacts:")
        for label, key in [("Plan draft", "latest_plan_draft"), ("Critique", "latest_plan_critique"), ("Scratchpad", "latest_generation_scratchpad"), ("Version", "latest_generated_version"), ("Pipeline QA", "latest_auto_review")]:
            if artifacts.get(key):
                print(f"- {label}: {artifacts[key]}")
    decisions = blackboard.get('recent_decisions') or []
    if decisions:
        print("\nRecent blackboard decisions:")
        for item in decisions[-3:]:
            sev = f" [{item.get('severity')}]" if item.get('severity') else ""
            print(f"- {item.get('timestamp')} {item.get('agent')}{sev}: {item.get('decision')}")
    ledger = payload.get('run_ledger') or {}
    recent_events = ledger.get('recent_events') or []
    if recent_events:
        print("\nRecent run ledger events:")
        for item in recent_events[-3:]:
            version = item.get('output_version') or item.get('attempt_id') or ''
            route = item.get('chosen_route') or ''
            suffix = f" -> {version}" if version else ""
            route_note = f" ({route})" if route else ""
            print(f"- {item.get('timestamp')} {item.get('event_type')}{route_note}{suffix}")
    inspiration_board = payload.get("inspiration_board") or {}
    board_summary = inspiration_board.get("summary") or {}
    if board_summary:
        print("\nInspiration board:")
        print(f"- Path: {inspiration_board.get('path') or 'n/a'}")
        print(f"- Objects: {board_summary.get('object_count') or 0}")
        print(f"- Relations: {board_summary.get('relation_count') or 0}")
        object_types = board_summary.get("object_types") or {}
        if object_types:
            print("- Object types: " + ", ".join(f"{kind}={count}" for kind, count in sorted(object_types.items())))
    next_commands = payload.get("next_suggested_commands") or []
    if next_commands:
        print("\nSuggested next commands:")
        for item in next_commands:
            print(f"- {item}")


def cmd_context_snapshot(args):
    brand_dir = get_brand_dir()
    brand_dir.mkdir(parents=True, exist_ok=True)
    _, _, profile, identity = load_brand_memory(brand_dir, getattr(args, "profile", None), getattr(args, "identity", None))
    payload = build_context_snapshot_payload(brand_dir, profile, identity, limit=max(1, int(getattr(args, "limit", 5) or 5)))
    if args.format == "json":
        print(json.dumps(payload, indent=2))
        return
    print("Context snapshot\n")
    print(f"Brand-gen root: {payload.get('brand_gen_root') or 'n/a'}")
    workspace = payload.get("workspace") or {}
    print(f"Workspace: {workspace.get('kind') or 'n/a'}")
    print(f"Brand dir: {payload.get('brand_dir') or 'n/a'}")
    if workspace.get("active_brand"):
        print(f"Active brand: {workspace['active_brand']}")
    if workspace.get("active_session"):
        print(f"Active session: {workspace['active_session']}")
    if workspace.get("seeded_from_brand"):
        print(f"Seeded from brand: {workspace['seeded_from_brand']}")
    counts = payload.get("counts") or {}
    manifest = counts.get("manifest") or {}
    runs = counts.get("runs") or {}
    print(f"Manifest versions: {manifest.get('count') or 0} (latest: {manifest.get('latest_id') or 'n/a'})")
    print(f"Run events: {runs.get('event_count') or 0} (latest workflow: {runs.get('latest_id') or 'n/a'})")
    prompt_sizes = payload.get("prompt_sizes") or {}
    print(f"Execution prompt chars: {prompt_sizes.get('execution_prompt_chars') or 0}")
    next_commands = payload.get("next_suggested_commands") or []
    if next_commands:
        print("Next commands: " + ", ".join(next_commands))


def cmd_source_knowledge(args):
    brand_dir = get_brand_dir()
    _, _, profile, identity = load_brand_memory(brand_dir, getattr(args, "profile", None), getattr(args, "identity", None))
    payload = build_source_knowledge_payload(
        brand_dir,
        profile,
        identity,
        query=getattr(args, "query", "") or "",
        limit=max(1, int(getattr(args, "limit", 8) or 8)),
        max_chars=max(120, int(getattr(args, "max_chars", 900) or 900)),
    )
    if args.format == "json":
        print(json.dumps(payload, indent=2))
        return
    print(f"Source knowledge for brand: {payload.get('brand') or 'n/a'}")
    print(f"Configured: {'yes' if payload.get('configured') else 'no'}")
    print(f"Scanned markdown files: {payload.get('scanned_markdown_files') or 0}")
    for item in payload.get("results") or []:
        print(f"\n- {item.get('title') or item.get('relpath')} ({item.get('relpath')})")
        print(str(item.get("excerpt") or "").strip())


def cmd_capabilities(args):
    payload = build_capabilities_payload()
    if args.format == "json":
        print(json.dumps(payload, indent=2))
        return
    print("Capabilities\n")
    print("Material types:")
    for item in payload.get("material_types") or []:
        suffix = ""
        if item.get("deprecated"):
            preferred = item.get("preferred_material_type") or "new taxonomy"
            suffix = f" [deprecated → {preferred}]"
        print(f"- {item['material_type']}: {item['classification']} · {item['generation_mode']} · default {item['default_model']} @ {item['default_aspect_ratio']}{suffix}")
    print("\nModels:")
    for item in (payload.get("models") or [])[:12]:
        supports = []
        if item.get("supports_reference_images"):
            supports.append("refs")
        if item.get("supports_base_image"):
            supports.append("base-image")
        if item.get("supports_motion_reference"):
            supports.append("motion-ref")
        print(f"- {item['alias']} ({item['generation_mode']}): {item['best_for'] or 'n/a'} [{', '.join(supports) or 'basic'}]")
    print("\nTools:")
    for item in payload.get("tools") or []:
        mode = "read-only" if item.get("read_only") else "mutating"
        shape = "primitive" if item.get("primitive") else "convenience"
        print(f"- {item['command']}: {mode}, {shape}")


def cmd_list_aesthetic_capsules(args):
    from ..aesthetic_curation import list_aesthetic_capsules, load_aesthetic_preferences, render_capsule_prompt

    brand_dir = get_brand_dir()
    material_type = getattr(args, "material_type", None) or ""
    capsules = list_aesthetic_capsules(material_type or None)
    prefs = load_aesthetic_preferences(brand_dir)
    payload = {
        "schema_type": "aesthetic_capsule_list",
        "schema_version": 1,
        "material_type": material_type,
        "preferences_path": str(brand_dir / "aesthetic-preferences.json"),
        "preferences": prefs,
        "capsules": [
            {
                "id": item.get("id"),
                "label": item.get("label"),
                "safe_handle": item.get("safe_handle"),
                "material_types": item.get("material_types") or [],
                "use_when": item.get("use_when") or [],
                "avoid_when": item.get("avoid_when") or [],
                "style_strength_default": item.get("style_strength_default"),
                "negative_prompt_terms": item.get("negative_prompt_terms") or [],
                "prompt_preview": render_capsule_prompt(item),
            }
            for item in capsules
        ],
    }
    if getattr(args, "format", "json") == "json":
        print(json.dumps(payload, indent=2))
        return
    print("Aesthetic capsules\n")
    for item in payload["capsules"]:
        print(f"- {item['id']}: {item['label']} — {item['safe_handle']}")


def cmd_suggest_aesthetic_directions(args):
    from ..aesthetic_curation import build_aesthetic_direction_brief

    brand_dir = get_brand_dir()
    payload = build_aesthetic_direction_brief(
        brand_dir=brand_dir,
        material_type=getattr(args, "material_type", None) or "",
        style_text=getattr(args, "style_handle", None) or "",
        count=getattr(args, "count", 3) or 3,
    )
    if getattr(args, "format", "json") == "json":
        print(json.dumps(payload, indent=2))
        return
    print("Aesthetic direction branches\n")
    print(payload.get("selection_rule") or "")
    for item in payload.get("variants") or []:
        print(f"\n{item.get('rank')}. {item.get('capsule_id')} — {item.get('visual_thesis')}")
        axes = ", ".join(item.get("difference_axes") or [])
        if axes:
            print(f"   Axes: {axes}")
        if item.get("exploration_role"):
            print(f"   Role: {item['exploration_role']}")


def cmd_workspace_status(args):
    brand_dir = get_brand_dir()
    brand_dir.mkdir(parents=True, exist_ok=True)
    _, _, profile, identity = load_brand_memory(brand_dir, getattr(args, "profile", None), getattr(args, "identity", None))
    payload = build_workspace_status_payload(brand_dir, profile, identity)
    if args.format == "json":
        print(json.dumps(payload, indent=2))
        return
    print(format_workspace_status_text(payload))


def cmd_prompts_list(args):
    payload = {"prompts": list_prompt_resources()}
    if args.format == "json":
        print(json.dumps(payload, indent=2))
        return
    print("Prompt resources\n")
    for item in payload["prompts"]:
        print(f"- {item['name']} ({item['format']})")


def cmd_prompts_get(args):
    payload = get_prompt_resource(args.name)
    if args.format == "json":
        print(json.dumps(payload, indent=2))
        return
    print(payload["content"])

def cmd_show_blackboard(args):
    brand_dir = get_brand_dir()
    brand_dir.mkdir(parents=True, exist_ok=True)
    _, _, profile, identity = load_brand_memory(brand_dir, getattr(args, "profile", None), getattr(args, "identity", None))
    board = load_blackboard(brand_dir, profile, identity)
    if args.format == "json":
        print(json.dumps(board, indent=2))
        return
    print("Brand blackboard\n")
    print(f"Brand: {(board.get('brand_dna') or {}).get('brand_name') or 'n/a'}")
    active = board.get("active_brief") or {}
    print(f"Active brief: {(active.get('material_type') or 'none')} ({active.get('stage') or 'idle'})")
    if active:
        print(f"Purpose: {active.get('purpose') or 'n/a'}")
        print(f"Mechanic: {active.get('system_mechanic') or 'n/a'}")
    latest = board.get("artifacts") or {}
    print(f"Latest plan draft: {latest.get('latest_plan_draft') or 'n/a'}")
    print(f"Latest critique: {latest.get('latest_plan_critique') or 'n/a'}")
    print(f"Latest scratchpad: {latest.get('latest_generation_scratchpad') or 'n/a'}")
    print(f"Latest version: {latest.get('latest_generated_version') or 'n/a'}")
    print(f"Latest pipeline QA: {latest.get('latest_auto_review') or 'n/a'}")
    learning_summary = board.get("learning_summary") or {}
    material_recipes = board.get("material_recipes") or {}
    if learning_summary:
        print("\nLearning summary:")
        for material_key, summary in sorted(learning_summary.items()):
            print(f"- {material_key}:")
            avoid = list((summary or {}).get("avoid") or [])[:2]
            prefer = list((summary or {}).get("prefer") or [])[:2]
            failures = list((summary or {}).get("failure_patterns") or [])[:2]
            if avoid:
                print(f"  avoid: {' | '.join(avoid)}")
            if prefer:
                print(f"  prefer: {' | '.join(prefer)}")
            if failures:
                print(f"  repeated failures: {' | '.join(failures)}")
            if (summary or {}).get("route_bias"):
                print(f"  route bias: {(summary or {}).get('route_bias')}")
            if (summary or {}).get("model_bias"):
                print(f"  model bias: {' | '.join((summary or {}).get('model_bias')[:2])}")
            if (summary or {}).get("reference_bias"):
                print(f"  reference bias: {' | '.join((summary or {}).get('reference_bias')[:2])}")
            recipes = list((material_recipes.get(material_key) or {}).get("recipes") or [])[:2]
            if recipes:
                print("  preferred recipes:")
                for recipe in recipes:
                    hint = f" — {recipe.get('hint')}" if recipe.get("hint") else ""
                    print(f"    - {recipe.get('label')}{hint}")
    if board.get("reference_assignments"):
        print("\nReference assignments:")
        for role, item in (board.get("reference_assignments") or {}).items():
            print(f"- {role}: {item.get('source_name') or item.get('source_key') or 'n/a'}")
    reference_analysis = board.get("reference_analysis") or {}
    if reference_analysis:
        print("\nReference analysis:")
        print(f"- Source count: {reference_analysis.get('source_count') or 0}")
        print(f"- Mode: {reference_analysis.get('reference_analysis_mode') or reference_analysis_mode(reference_analysis)}")
        print(f"- Confidence: {reference_analysis.get('reference_analysis_confidence') or reference_analysis_confidence(reference_analysis)}")
        print(f"- Consistency: {reference_analysis.get('consistency_score') or 0}")
        if reference_analysis.get("reference_set_hash"):
            print(f"- Hash: {reference_analysis.get('reference_set_hash')}")
        product_palette = ((reference_analysis.get("product_observations") or {}).get("palette") or [])[:4]
        if product_palette:
            print(f"- Observed product palette: {', '.join(product_palette)}")
        mechanics = ((reference_analysis.get("inspiration_observations") or {}).get("mechanics") or [])[:3]
        if mechanics:
            print(f"- Inspiration mechanics: {', '.join(mechanics)}")
        print("- Details: run `show-reference-analysis`")
    decisions = board.get("decisions") or []
    if decisions:
        print("\nRecent decisions:")
        for item in decisions[-5:]:
            sev = f" [{item.get('severity')}]" if item.get("severity") else ""
            print(f"- {item.get('timestamp')} {item.get('agent')}{sev}: {item.get('decision')}")
    inspiration_board = load_inspiration_board(brand_dir)
    board_summary = build_inspiration_board_summary(inspiration_board)
    if board_summary.get("object_count"):
        print("\nInspiration board:")
        print(f"- Path: {inspiration_board_path(brand_dir)}")
        print(f"- Objects: {board_summary.get('object_count') or 0}")
        print(f"- Relations: {board_summary.get('relation_count') or 0}")
        for kind, count in sorted((board_summary.get("object_types") or {}).items()):
            print(f"  - {kind}: {count}")
    learnings = summarize_learnings_memory(load_learnings_memory(brand_dir), limit=2)
    if any((learnings.get("counts") or {}).values()):
        print("\nPromoted learnings:")
        for bucket, items in (learnings.get("recent") or {}).items():
            if not items:
                continue
            print(f"- {bucket}:")
            for item in items[:2]:
                print(f"  - {item.get('text')}")

def cmd_show_workflow_lineage(args):
    brand_dir = get_brand_dir()
    brand_dir.mkdir(parents=True, exist_ok=True)
    board = load_blackboard(brand_dir)
    workflow_id = str(args.workflow_id)
    lineage = get_workflow_lineage(board, workflow_id)
    lineage["run_events"] = load_run_events(brand_dir, workflow_id)
    lineage["artifacts"] = collect_workflow_artifacts(brand_dir, workflow_id)
    lineage["brand_dir"] = str(brand_dir)
    scratchpad_selected_ids: list[str] = []
    for artifact in (lineage.get("artifacts") or {}).get("generation_scratchpads") or []:
        payload = load_json_file(Path(str(artifact.get("path") or "")))
        scratchpad_selected_ids.extend(str(item).strip() for item in (payload.get("selected_inspiration_ids") or []) if str(item).strip())
    board_payload = load_inspiration_board(brand_dir)
    lineage["inspiration_board"] = {
        "path": str(inspiration_board_path(brand_dir)),
        "summary": build_inspiration_board_summary(board_payload),
        "selected_inspiration_ids": dedupe_keep_order(
            [
                *[
                    str(item).strip()
                    for event in (lineage.get("run_events") or [])
                    for item in (event.get("selected_reference_ids") or [])
                    if str(item).strip()
                ],
                *scratchpad_selected_ids,
            ]
        ),
    }
    if args.format == "json":
        print(json.dumps(lineage, indent=2))
        return
    print("Workflow lineage\n")
    print(f"Workflow ID: {workflow_id}")
    print(f"Brand dir: {brand_dir}")
    decisions = lineage.get("decisions") or []
    assets = lineage.get("assets") or []
    run_events = lineage.get("run_events") or []
    print(f"Decisions: {len(decisions)}")
    print(f"Generated assets: {len(assets)}")
    print(f"Run ledger events: {len(run_events)}")
    insp_summary = ((lineage.get("inspiration_board") or {}).get("summary") or {})
    if insp_summary:
        print(f"Inspiration board: {insp_summary.get('object_count') or 0} objects, {insp_summary.get('relation_count') or 0} relations")
    artifacts = lineage.get("artifacts") or {}
    print(
        "Artifacts: "
        f"{len(artifacts.get('plan_drafts') or [])} drafts, "
        f"{len(artifacts.get('plan_critiques') or [])} critiques, "
        f"{len(artifacts.get('generation_scratchpads') or [])} scratchpads"
    )
    if decisions:
        print("\nDecisions:")
        for item in decisions[-10:]:
            print(f"- [{item.get('timestamp') or 'n/a'}] {item.get('agent') or 'agent'}: {item.get('decision') or ''}")
    if assets:
        print("\nGenerated assets:")
        for item in assets[-10:]:
            files = ", ".join(item.get("files") or []) or "n/a"
            print(f"- {item.get('version') or 'n/a'} ({item.get('material_type') or 'material'}) -> {files}")
    if run_events:
        print("\nRun ledger:")
        for item in run_events[-12:]:
            version = item.get("output_version") or item.get("attempt_id") or ""
            route = item.get("chosen_route") or item.get("recommended_route") or ""
            detail = f" -> {version}" if version else ""
            route_note = f" [{route}]" if route else ""
            source_ver = item.get("source_version") or ""
            branch = item.get("branch_id") or ""
            override_suffix = ""
            if item.get("recommended_route") and item.get("chosen_route") and item["recommended_route"] != item["chosen_route"]:
                override_suffix = f" [OVERRIDE: {item['recommended_route']} -> {item['chosen_route']}]"
            lineage_parts = []
            if source_ver:
                lineage_parts.append(f"from:{source_ver}")
            if branch:
                lineage_parts.append(f"branch:{branch}")
            lineage_suffix = f" ({', '.join(lineage_parts)})" if lineage_parts else ""
            print(f"- [{item.get('timestamp') or 'n/a'}] {item.get('event_type') or item.get('stage')}{route_note}{detail}{override_suffix}{lineage_suffix}")
    for bucket in ("plan_drafts", "plan_critiques", "generation_scratchpads"):
        items = artifacts.get(bucket) or []
        if not items:
            continue
        print(f"\n{bucket.replace('_', ' ').title()}:")
        for item in items:
            print(f"- {item.get('path')}")


def cmd_show_reference_analysis(args):
    brand_dir = get_brand_dir()
    brand_dir.mkdir(parents=True, exist_ok=True)
    _, _, profile, identity = load_brand_memory(brand_dir, getattr(args, "profile", None), getattr(args, "identity", None))
    board = load_blackboard(brand_dir, profile, identity)
    analysis = board.get("reference_analysis") or {}
    if getattr(args, "refresh_reference_analysis", False):
        reference_paths = [Path(item.get("path")).expanduser().resolve() for item in (board.get("reference_assignments") or {}).values() if item.get("path")]
        role_pack_roles = [
            {
                "role": role,
                "path": item.get("path") or "",
                "source_key": item.get("source_key") or "",
                "source_name": item.get("source_name") or "",
            }
            for role, item in (board.get("reference_assignments") or {}).items()
            if item.get("path")
        ]
        analysis = ensure_reference_analysis(
            brand_dir,
            profile=profile,
            identity=identity,
            reference_paths=reference_paths,
            role_pack_roles=role_pack_roles,
            material_type=((board.get("active_brief") or {}).get("material_type") or None),
            refresh_extraction=True,
        )
    if args.format == "json":
        print(json.dumps(analysis, indent=2))
        return

    if not analysis:
        print("No cached reference analysis found.")
        print("Build a generation scratchpad first, or run build-generation-scratchpad without --skip-extraction.")
        return

    product = analysis.get("product_observations") or {}
    inspiration = analysis.get("inspiration_observations") or {}
    print("Reference analysis\n")
    print(f"Source count: {analysis.get('source_count') or 0}")
    print(f"Reference set hash: {analysis.get('reference_set_hash') or 'n/a'}")
    print(f"Mode: {analysis.get('reference_analysis_mode') or reference_analysis_mode(analysis)}")
    print(f"Confidence: {analysis.get('reference_analysis_confidence') or reference_analysis_confidence(analysis)}")
    print(f"Consistency score: {analysis.get('consistency_score') or 0}")
    if product.get("palette"):
        print(f"\nObserved product palette: {', '.join(product.get('palette')[:6])}")
    if product.get("typography_cues"):
        print(f"Observed product typography: {', '.join(product.get('typography_cues')[:6])}")
    if product.get("component_cues"):
        print(f"Observed product component cues: {', '.join(product.get('component_cues')[:6])}")
    if inspiration.get("mechanics"):
        print(f"\nInspiration mechanics: {', '.join(inspiration.get('mechanics')[:6])}")
    if inspiration.get("composition_patterns"):
        print(f"Inspiration composition patterns: {', '.join(inspiration.get('composition_patterns')[:4])}")
    if inspiration.get("texture_patterns"):
        print(f"Inspiration texture patterns: {', '.join(inspiration.get('texture_patterns')[:6])}")
    warnings = analysis.get("warnings") or []
    if warnings:
        print("\nWarnings:")
        for item in warnings:
            print(f"- {item}")
    per_image = analysis.get("per_image") or []
    if per_image:
        print("\nPer-image:")
        for item in per_image:
            source = item.get("source_name") or item.get("source_key") or Path(item.get("path") or "").name or "ref"
            print(f"- {item.get('role') or item.get('bucket') or 'reference'}: {source}")
            if item.get("dominant_colors"):
                print(f"  palette: {', '.join((item.get('dominant_colors') or [])[:4])}")
            if item.get("composition"):
                print(f"  composition: {item.get('composition')}")
            if item.get("transferable_mechanics"):
                print(f"  mechanics: {', '.join((item.get('transferable_mechanics') or [])[:3])}")

def cmd_show_iteration_memory(args):
    brand_dir = get_brand_dir()
    brand_dir.mkdir(parents=True, exist_ok=True)
    memory = load_iteration_memory(brand_dir)
    json_path, md_path = iteration_memory_paths(brand_dir)
    if args.format == "json":
        print(json.dumps({"paths": {"json": str(json_path), "markdown": str(md_path)}, "memory": memory}, indent=2))
        return
    print(f"Iteration memory JSON: {json_path}")
    print(f"Iteration memory markdown: {md_path}\n")
    print(render_iteration_memory_markdown(memory))


def cmd_update_iteration_memory(args):
    brand_dir = get_brand_dir()
    brand_dir.mkdir(parents=True, exist_ok=True)
    memory = load_iteration_memory(brand_dir)
    material_type = args.material_type or ""
    if args.note:
        if args.kind == "material":
            memory = add_iteration_note(memory, args.note, material_type=material_type, bucket="material")
        elif args.kind == "copy":
            memory = add_iteration_note(memory, args.note, bucket="copy_notes")
        elif args.kind == "messaging":
            memory = add_iteration_note(memory, args.note, bucket="messaging_notes")
        else:
            memory = add_iteration_note(memory, args.note, bucket="brand_notes")
    if args.negative:
        memory["negative_examples"].append({
            "version": args.version or "note",
            "material_type": material_type,
            "summary": args.negative,
            "score": args.score,
            "status": "rejected" if args.score is not None and args.score <= 2 else "",
        })
        memory["negative_examples"] = memory["negative_examples"][-20:]
    if args.positive:
        memory["positive_examples"].append({
            "version": args.version or "note",
            "material_type": material_type,
            "summary": args.positive,
            "score": args.score,
            "status": "favorite" if args.score is not None and args.score >= 4 else "",
        })
        memory["positive_examples"] = memory["positive_examples"][-20:]
    json_path, md_path = save_iteration_memory(brand_dir, memory)
    if args.format == "json":
        print(json.dumps({"json": str(json_path), "markdown": str(md_path), "memory": memory}, indent=2))
        return
    print(f"Updated iteration memory:\n- {json_path}\n- {md_path}")


def cmd_inspiration_status(args):
    """Phase 1 preflight: report which inspiration sources are configured, which are
    extracted, and whether the brand is ready for hybrid/inspiration mode without
    the self-referential drift the pipeline retro surfaced.
    """
    from ..reference_analysis import check_inspiration_pipeline_status
    brand_gen_dir = get_brand_gen_dir()
    brand_dir = get_brand_dir()
    profile_path, identity_path, profile_data, identity_data = load_brand_memory(
        brand_dir, getattr(args, "profile", None), getattr(args, "identity", None)
    )
    active_brand = resolve_context_brand_key(
        brand_dir=brand_dir,
        profile_path=profile_path,
        identity_path=identity_path,
        profile=profile_data,
        identity=identity_data,
        brand_gen_dir=brand_gen_dir,
    )

    inspirations_path = brand_dir / "inspirations.json"
    configured: list[dict] = []
    extracted: list[str] = []
    pending: list[str] = []
    if inspirations_path.exists():
        try:
            payload = json.loads(inspirations_path.read_text())
        except (json.JSONDecodeError, OSError, UnicodeDecodeError):
            payload = {}
        raw_sources = payload.get("sources") or []
        if isinstance(raw_sources, dict):
            sources = [
                {"key": k, **(v if isinstance(v, dict) else {"source": v})}
                for k, v in raw_sources.items()
            ]
        elif isinstance(raw_sources, list):
            sources = [
                item if isinstance(item, dict) else {"key": str(item), "source": str(item)}
                for item in raw_sources
            ]
        else:
            sources = []
        for source in sources:
            key = str(source.get("key") or source.get("source") or "").strip()
            if not key:
                continue
            category = source.get("category") or ""
            dm_dir = brand_gen_dir / "inspiration" / category / key / ".design-memory"
            entry = {"key": key, "category": category, "design_memory_path": str(dm_dir)}
            configured.append(entry)
            if dm_dir.exists():
                extracted.append(key)
            else:
                pending.append(key)

    # Check each mode's readiness status
    mode_readiness: dict[str, dict] = {}
    for mode in ("reference", "hybrid", "inspiration"):
        status = check_inspiration_pipeline_status(brand_gen_dir, active_brand, mode)
        mode_readiness[mode] = {
            "ok": status.get("ok", False),
            "warnings": list(status.get("warnings") or []),
            "suggestions": list(status.get("suggestions") or []),
        }

    recommended_next: list[str] = []
    if pending:
        recommended_next.append(
            f"bgen extract-inspiration --source {pending[0]}"
            + ("  # ... repeat for the rest" if len(pending) > 1 else "")
        )
        recommended_next.append("bgen consolidate-inspiration --format json")
    if not configured:
        recommended_next.append("bgen inspire --sources <source1,source2>  # configure sources first")

    response = {
        "active_brand": active_brand,
        "inspirations_path": str(inspirations_path) if inspirations_path.exists() else "",
        "configured_sources": configured,
        "extracted_sources": extracted,
        "pending_sources": pending,
        "ready_for_hybrid": mode_readiness["hybrid"]["ok"] and not pending,
        "ready_for_inspiration": mode_readiness["inspiration"]["ok"] and not pending,
        "mode_readiness": mode_readiness,
        "recommended_next_commands": recommended_next,
    }

    if args.format == "json":
        print(json.dumps(response, indent=2))
        return
    print(f"Inspiration status for brand: {active_brand or 'n/a'}")
    print(f"  configured: {len(configured)}  extracted: {len(extracted)}  pending: {len(pending)}")
    if configured:
        print("  sources:")
        for s in configured:
            mark = "✓" if s["key"] in extracted else "✗"
            print(f"    {mark} {s['key']} (category: {s['category'] or 'n/a'})")
    print(f"  ready for hybrid mode: {'yes' if response['ready_for_hybrid'] else 'no'}")
    print(f"  ready for inspiration mode: {'yes' if response['ready_for_inspiration'] else 'no'}")
    if recommended_next:
        print("  next commands:")
        for cmd in recommended_next:
            print(f"    $ {cmd}")


def cmd_show_disagreements(args):
    """List recent agent-vs-user disagreement records.

    Filters by --material-type, --bucket, --partition-tag. Defaults to
    the 10 most recent records across all materials.
    """
    from ..scoring.dataset import load_disagreements

    brand_dir = get_brand_dir()
    records = load_disagreements(
        brand_dir,
        partition_tag=getattr(args, "partition_tag", None) or None,
        material_type=getattr(args, "material_type", None) or None,
        bucket=getattr(args, "bucket", None) or None,
        limit=int(getattr(args, "limit", 10) or 10),
    )

    if args.format == "json":
        print(json.dumps({"n": len(records), "records": records}, indent=2, default=str))
        return

    if not records:
        print("No disagreement records found.")
        print(f"  brand_dir: {brand_dir}")
        print("  (nothing will appear until bgen feedback lands a user score on a v2-scored version)")
        return

    print(f"Disagreement records ({len(records)} most recent):")
    for r in records:
        vid = r.get("version_id") or "?"
        mat = r.get("material_type") or "?"
        agent = r.get("agent_score")
        user = r.get("user_score")
        delta = r.get("delta")
        bucket = r.get("agreement_bucket") or "?"
        partition = r.get("partition_tag") or "?"
        notes = (r.get("user_notes") or "").strip().replace("\n", " / ")
        if len(notes) > 60:
            notes = notes[:57] + "..."
        print(f"  {vid:8s} {mat:22s} agent={agent} user={user} delta={delta} {bucket:22s} [{partition}]")
        if notes:
            print(f"           notes: {notes}")


def cmd_scoring_status(args):
    """Report current scoring calibration state for the active brand.

    Returns aggregate weighted Cohen's kappa (quadratic weights) + raw
    agreement %, plus per-bucket and per-material counts. Raw agreement
    alongside kappa is intentional: when kappa is near 0 but raw
    agreement is high, you're hitting the kappa paradox (approve-heavy
    outcomes + class imbalance). Reporting both keeps the paradox visible.
    """
    from ..scoring.dataset import (
        disagreement_dataset_path,
        load_disagreements,
        partition_split_observed,
    )
    from ..scoring.calibration import compute_agreement_stats

    brand_dir = get_brand_dir()
    path = disagreement_dataset_path(brand_dir)
    records = load_disagreements(brand_dir, limit=None)  # all records
    stats = compute_agreement_stats(records)
    split = partition_split_observed(records)

    response = {
        "dataset_path": str(path),
        "dataset_exists": path.exists(),
        "n_total": stats["n_total"],
        "n_scored": stats["n_scored"],
        "raw_agreement": stats["raw_agreement"],
        "weighted_kappa": stats["weighted_kappa"],
        "n_per_bucket": stats["n_per_bucket"],
        "n_per_material": stats["n_per_material"],
        "partition_split_observed": split,
        "metrics_note": (
            "Raw agreement reported alongside weighted kappa to surface the "
            "approve-heavy kappa paradox. If raw_agreement is high (>0.8) "
            "but weighted_kappa is low (<0.3), outcomes are imbalanced and "
            "kappa understates actual signal. Full Gwet's AC1 / PABAK "
            "instrumentation lands in v2."
        ),
    }

    if args.format == "json":
        print(json.dumps(response, indent=2, default=str))
        return

    print(f"Scoring status for brand workspace: {brand_dir}")
    print(f"  dataset: {path}")
    print(f"  records: {stats['n_total']} total, {stats['n_scored']} with both scores")
    print()
    print(f"  raw agreement:   {stats['raw_agreement']:.1%}")
    print(f"  weighted kappa:  {stats['weighted_kappa']:.3f}   (quadratic weights, 1-5 ordinal)")
    print()
    if stats["n_per_bucket"]:
        print("  buckets:")
        for name in ("strong_agreement", "mild_disagreement", "strong_disagreement", "calibration_failure"):
            count = stats["n_per_bucket"].get(name, 0)
            print(f"    {name:24s} {count}")
    if stats["n_per_material"]:
        print()
        print("  per material:")
        for mat, count in sorted(stats["n_per_material"].items(), key=lambda x: -x[1]):
            flag = "  (insufficient data)" if count < 10 else ""
            print(f"    {mat:28s} {count}{flag}")
    print()
    print(f"  partition split (scorer_training / iteration_memory):")
    print(f"    scorer_training:    {split['scorer_training']}")
    print(f"    iteration_memory:   {split['iteration_memory']}")
    if split.get("unknown"):
        print(f"    unknown:            {split['unknown']}  (records pre-partition; expected for backfill)")

    if stats["n_total"] == 0:
        print()
        print("  No records yet. bgen feedback on a v2-scored version will populate this.")


def cmd_show_rubric(args):
    """Dump the scoring rubric registry.

    Without --material-type: full registry (all universal axes + all materials
    with their overlays + disqualifiers).
    With --material-type <t>: focused view for that material.
    """
    from ..scoring import (
        RUBRIC_VERSION,
        UNIVERSAL_AXES,
        MATERIAL_OVERLAYS,
        axes_for,
        disqualifier_for,
        material_rubric_key,
        to_json_dict,
    )

    material_type = getattr(args, "material_type", None)
    payload = to_json_dict(material_type)

    if args.format == "json":
        print(json.dumps(payload, indent=2))
        return

    # Text rendering
    print(f"Scoring rubric (version: {RUBRIC_VERSION})")
    if material_type:
        print(f"  material_type: {material_type}")
        print(f"  material_rubric_key: {material_rubric_key(material_type) or '(no overlay — universal only)'}")
        print()
        print("Universal axes:")
        for axis in UNIVERSAL_AXES:
            print(f"  - {axis['name']}")
            print(f"    {axis['definition']}")
        overlay_axes = payload.get("overlay_axes", [])
        if overlay_axes:
            print()
            print(f"Overlay axes (material-specific):")
            for axis in overlay_axes:
                print(f"  - {axis['name']}")
                print(f"    {axis['definition']}")
        else:
            print()
            print(f"No overlay axes for material '{material_type}' (universal axes only)")
        dq = payload.get("disqualifier")
        if dq:
            print()
            print(f"Disqualifier rule ({dq['rule_id']}):")
            print(f"  {dq['description']}")
        else:
            print()
            print(f"No disqualifier rule for material '{material_type}'")
    else:
        print(f"  universal_axes: {len(UNIVERSAL_AXES)}")
        print(f"  materials with overlays: {len(MATERIAL_OVERLAYS)}")
        print()
        print("Universal axes:")
        for axis in UNIVERSAL_AXES:
            print(f"  - {axis['name']}")
        print()
        print("Materials with overlays:")
        for key, overlay in MATERIAL_OVERLAYS.items():
            dq = overlay.get("disqualifier")
            axes_count = len(overlay.get("overlay_axes", []))
            dq_label = dq["rule_id"] if dq else "(no disqualifier)"
            print(f"  - {key}: {axes_count} overlay axes + {dq_label}")
        print()
        print("Run with --material-type <t> for the full overlay + disqualifier for one material.")


def cmd_rebucket_inspiration(args):
    """Rewrite per-source bucket assignments in the brand's inspiration-memory.json.

    When every inspiration source declares every bucket (composition,
    narrative_system, rendering_style), role-pack selection degenerates
    into first-by-index. This command lets a brand pin a PRIMARY bucket
    per source so the ranker stops returning the same source for every
    role slot.

    Modes:
      --primary <bucket>           — set primary_bucket on the source
      --scores '<json weights>'    — set full bucket_scores dict
      --clear                      — remove both primary_bucket and bucket_scores

    The brand's inspiration-memory.json is updated in place; no other
    files change.
    """
    brand_dir = get_brand_dir()
    im_path = brand_dir / "inspiration-memory.json"
    if not im_path.exists():
        msg = f"inspiration-memory.json not found at {im_path}"
        if args.format == "json":
            print(json.dumps({"status": "error", "error": msg}))
            sys.exit(1)
        print(msg)
        sys.exit(1)

    data = json.loads(im_path.read_text())
    source_key = str(getattr(args, "source", "")).strip()
    sources = data.get("sources") or []
    target = next((s for s in sources if str(s.get("source") or "").strip() == source_key), None)
    if not target:
        available = ", ".join(sorted(str(s.get("source") or "") for s in sources if s.get("source")))
        msg = f"Source '{source_key}' not found. Available: {available or '(none)'}"
        if args.format == "json":
            print(json.dumps({"status": "error", "error": msg}))
            sys.exit(1)
        print(msg)
        sys.exit(1)

    changes: list[str] = []

    if getattr(args, "clear", False):
        for key in ("primary_bucket", "bucket_scores"):
            if key in target:
                del target[key]
                changes.append(f"cleared {key}")
    if getattr(args, "scores", None):
        try:
            weights = json.loads(args.scores)
        except json.JSONDecodeError as exc:
            msg = f"--scores is not valid JSON: {exc}"
            if args.format == "json":
                print(json.dumps({"status": "error", "error": msg}))
                sys.exit(1)
            print(msg)
            sys.exit(1)
        if not isinstance(weights, dict):
            msg = "--scores must be a JSON object of {bucket: weight}"
            if args.format == "json":
                print(json.dumps({"status": "error", "error": msg}))
                sys.exit(1)
            print(msg)
            sys.exit(1)
        target["bucket_scores"] = {k: float(v) for k, v in weights.items()}
        changes.append(f"bucket_scores={target['bucket_scores']}")
    if getattr(args, "primary", None):
        target["primary_bucket"] = args.primary
        changes.append(f"primary_bucket={args.primary}")

    if not changes:
        msg = "No changes requested (pass --primary, --scores, or --clear)."
        if args.format == "json":
            print(json.dumps({"status": "noop", "message": msg}))
            return
        print(msg)
        return

    im_path.write_text(json.dumps(data, indent=2) + "\n")

    result = {
        "status": "ok",
        "source": source_key,
        "brand_dir": str(brand_dir),
        "changes": changes,
        "primary_bucket": target.get("primary_bucket"),
        "bucket_scores": target.get("bucket_scores"),
    }
    if args.format == "json":
        print(json.dumps(result, indent=2))
        return
    print(f"Updated {source_key} in {im_path}")
    for ch in changes:
        print(f"  - {ch}")


def cmd_list_runs(args):
    """List projected runs from the run ledger under the active brand dir."""
    brand_dir = get_brand_dir()
    status_filter = getattr(args, "status", None) or None
    material_filter = getattr(args, "material_type", None) or None
    limit = getattr(args, "limit", None)
    runs = list_all_runs(
        brand_dir,
        status=status_filter,
        material_type=material_filter,
        limit=limit if isinstance(limit, int) and limit > 0 else None,
    )
    payload = {
        "brand_dir": str(brand_dir),
        "count": len(runs),
        "filter": {
            "status": status_filter,
            "material_type": material_filter,
            "limit": limit if isinstance(limit, int) and limit > 0 else None,
        },
        "runs": [run.to_dict() for run in runs],
    }
    if getattr(args, "format", "json") == "json":
        print(json.dumps(payload, indent=2))
        return
    if not runs:
        print("No runs found.")
        return
    print(f"{'RUN_ID':<14} {'STAGE':<14} {'STATUS':<18} {'MATERIAL':<22} {'UPDATED':<20} {'EVENTS':>6}")
    print("-" * 100)
    for run in runs:
        print(
            f"{run.run_id:<14} {(run.current_stage or '—'):<14} "
            f"{(run.status or '—'):<18} {(run.material_type or '—'):<22} "
            f"{(run.last_updated_at or run.created_at or '—'):<20} {run.event_count:>6}"
        )


def cmd_get_run(args):
    """Return the projected Run object for a workflow_id."""
    brand_dir = get_brand_dir()
    workflow_id = str(getattr(args, "run_id", "") or "").strip()
    if not workflow_id:
        raise SystemExit("--run-id is required")
    run = project_run_by_id(brand_dir, workflow_id)
    if run is None:
        payload = {
            "status": "not_found",
            "run_id": workflow_id,
            "brand_dir": str(brand_dir),
        }
        print(json.dumps(payload, indent=2))
        return
    payload = {
        "status": "ok",
        "brand_dir": str(brand_dir),
        "run": run.to_dict(),
    }
    if getattr(args, "format", "json") == "json":
        print(json.dumps(payload, indent=2))
        return
    print(f"Run {run.run_id}")
    print(f"  brand_key:      {run.brand_key or '—'}")
    print(f"  material_type:  {run.material_type or '—'}")
    print(f"  mode:           {run.mode or '—'}")
    print(f"  current_stage:  {run.current_stage or '—'}")
    print(f"  status:         {run.status}")
    print(f"  created_at:     {run.created_at}")
    print(f"  last_updated:   {run.last_updated_at}")
    print(f"  stages:         {', '.join(run.stages_completed) or '—'}")
    if run.blocking_issues:
        print(f"  blocking_issues:")
        for item in run.blocking_issues:
            print(f"    - {item}")
    if run.lineage:
        print(f"  lineage:        {', '.join(run.lineage)}")
    if run.artifact_ids:
        print("  artifacts:")
        for k, v in run.artifact_ids.items():
            print(f"    {k}: {v}")


def _resolve_run_or_path(args) -> tuple[str | None, str | None]:
    run_id = str(getattr(args, "run_id", "") or "").strip() or None
    path = str(getattr(args, "path", "") or "").strip() or None
    return run_id, path


def cmd_get_plan(args):
    brand_dir = get_brand_dir()
    run_id, path = _resolve_run_or_path(args)
    result = fetch_plan(brand_dir, run_id=run_id, path=path)
    print(json.dumps(result, indent=2))


def cmd_get_critique(args):
    brand_dir = get_brand_dir()
    run_id, path = _resolve_run_or_path(args)
    result = fetch_critique(brand_dir, run_id=run_id, path=path)
    print(json.dumps(result, indent=2))


def cmd_get_scratchpad(args):
    brand_dir = get_brand_dir()
    run_id, path = _resolve_run_or_path(args)
    result = fetch_scratchpad(brand_dir, run_id=run_id, path=path)
    print(json.dumps(result, indent=2))


def cmd_get_review_packet(args):
    brand_dir = get_brand_dir()
    version_id = str(getattr(args, "version_id", "") or "").strip()
    if not version_id:
        raise SystemExit("--version-id is required")
    result = fetch_review_packet(brand_dir, version_id=version_id)
    print(json.dumps(result, indent=2))


def cmd_get_version(args):
    brand_dir = get_brand_dir()
    version_id = str(getattr(args, "version_id", "") or "").strip()
    if not version_id:
        raise SystemExit("--version-id is required")
    result = fetch_version(brand_dir, version_id=version_id)
    print(json.dumps(result, indent=2))


def cmd_compare_versions(args):
    brand_dir = get_brand_dir()
    version_a = str(getattr(args, "a", "") or "").strip()
    version_b = str(getattr(args, "b", "") or "").strip()
    if not version_a or not version_b:
        raise SystemExit("--a and --b are required")
    result = artifact_compare_versions(brand_dir, version_a=version_a, version_b=version_b)
    print(json.dumps(result, indent=2))
