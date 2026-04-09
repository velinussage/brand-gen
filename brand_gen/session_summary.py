from __future__ import annotations

from .context_surfaces import build_context_snapshot_payload
from .inspiration_board import build_inspiration_board_summary, inspiration_board_path, load_inspiration_board
from .learnings_memory import load_learnings_memory, summarize_learnings_memory
from .media_board import _version_sort_key
from .runtime import *
from .material_planning import *
from .run_ledger import load_all_run_events

def summarize_messaging_state(identity: dict) -> dict:
    messaging = identity.get("messaging") or {}
    copy_bank = messaging.get("approved_copy_bank") or {}
    voice = messaging.get("voice") or {}
    return {
        "tagline": messaging.get("tagline") or "",
        "elevator": messaging.get("elevator") or "",
        "voice_description": voice.get("description") or "",
        "value_propositions": list(messaging.get("value_propositions") or []),
        "copy_bank_counts": {
            "headlines": len(copy_bank.get("headlines") or []),
            "slogans": len(copy_bank.get("slogans") or []),
            "subheadlines": len(copy_bank.get("subheadlines") or []),
            "cta_pairs": len(copy_bank.get("cta_pairs") or []),
        },
        "positioning_insights": list(messaging.get("positioning_insights") or []),
        "copy_insights": list(messaging.get("copy_insights") or []),
    }


def build_session_summary_payload(brand_dir: Path, profile: dict, identity: dict, *, limit: int = 5) -> dict:
    snapshot = build_context_snapshot_payload(brand_dir, profile, identity, limit=limit)
    manifest = load_manifest(brand_dir)
    board = load_blackboard(brand_dir, profile, identity)
    memory = load_iteration_memory(brand_dir)
    learnings = load_learnings_memory(brand_dir)
    versions = manifest.get("versions") or {}
    sorted_versions = sorted(versions.items(), key=lambda item: _version_sort_key(item[0]), reverse=True)
    recent_run_events = load_all_run_events(brand_dir, limit=max(5, limit * 3))
    workflow_lookup = {
        str(item.get("version") or ""): str(item.get("workflow_id") or "")
        for item in (board.get("generated_assets") or [])
        if item.get("version")
    }
    for event in recent_run_events:
        version = str(event.get("output_version") or event.get("attempt_id") or "").strip()
        workflow_id = str(event.get("workflow_id") or "").strip()
        if version and workflow_id and version not in workflow_lookup:
            workflow_lookup[version] = workflow_id
    recent_versions = []
    recent_feedback = []
    for vid, entry in sorted_versions[: max(1, limit)]:
        item = {
            "version": vid,
            "timestamp": entry.get("timestamp") or "",
            "material_type": entry.get("material_type") or "",
            "generation_mode": entry.get("generation_mode") or "",
            "mode": entry.get("mode") or "",
            "model": entry.get("model") or "",
            "tag": entry.get("tag") or "",
            "score": entry.get("score"),
            "status": entry.get("status") or "",
            "notes": entry.get("notes") or "",
            "files": list(entry.get("files") or []),
            "workflow_id": workflow_lookup.get(vid, ""),
        }
        recent_versions.append(item)
        if item["score"] is not None or item["status"] or item["notes"]:
            recent_feedback.append({
                "version": vid,
                "score": item["score"],
                "status": item["status"],
                "notes": item["notes"],
                "workflow_id": item["workflow_id"],
            })
    workspace_kind = "saved_brand"
    session_key = None
    brand_key = infer_brand_key_from_path(brand_dir)
    brand_gen_dir = get_brand_gen_dir()
    if brand_gen_dir:
        sessions_root = (brand_gen_dir / "sessions").resolve()
        try:
            rel = brand_dir.resolve().relative_to(sessions_root)
            if len(rel.parts) >= 2 and rel.parts[1] == "brand-materials":
                workspace_kind = "session"
                session_key = rel.parts[0]
        except Exception:
            pass
    session_context = ((identity.get("session_context") if isinstance(identity, dict) else None) or (profile.get("session_context") if isinstance(profile, dict) else None) or {})
    # Branching stats: count versions that have a source_version set
    branched_versions = sum(1 for entry in versions.values() if entry.get("source_version"))
    # Route override stats: count run events where recommended != chosen
    route_override_count = sum(
        1 for event in recent_run_events
        if event.get("recommended_route") and event.get("chosen_route") and event["recommended_route"] != event["chosen_route"]
    )

    inspiration_board = load_inspiration_board(brand_dir)
    return {
        "brand_dir": str(brand_dir),
        "brand_gen_root": snapshot.get("brand_gen_root") or "",
        "brand_gen_root_status": snapshot.get("brand_gen_root_status") or {},
        "config": snapshot.get("config") or {},
        "inspirations": snapshot.get("inspirations") or {},
        "pointers": snapshot.get("pointers") or {},
        "prompt_sizes": snapshot.get("prompt_sizes") or {},
        "next_suggested_commands": snapshot.get("next_suggested_commands") or [],
        "workspace": {
            "kind": workspace_kind,
            "session": session_key,
            "active_brand": brand_key or resolve_active_brand_key(brand_gen_dir=brand_gen_dir, repo_root=REPO_ROOT),
            "seeded_from_brand": session_context.get("seeded_from_brand") or "",
        },
        "brand": {
            "name": ((identity.get("brand") or {}).get("name") or profile.get("brand_name") or "").strip(),
            "summary": ((identity.get("brand") or {}).get("summary") or profile.get("description") or "").strip(),
        },
        "generated": {
            "count": len(versions),
            "favorites": sum(1 for entry in versions.values() if entry.get("status") == "favorite"),
            "scored": sum(1 for entry in versions.values() if entry.get("score") is not None),
            "unscored": sum(1 for entry in versions.values() if entry.get("score") is None),
            "recent_versions": recent_versions,
            "recent_feedback": recent_feedback,
        },
        "run_ledger": {
            "event_count": len(recent_run_events),
            "recent_events": recent_run_events[-max(1, limit):],
            "route_override_count": route_override_count,
        },
        "branching": {
            "branched_version_count": branched_versions,
            "total_versions": len(versions),
        },
        "messaging": summarize_messaging_state(identity),
        "iteration_memory": {
            "brand_notes": list(memory.get("brand_notes") or [])[-5:],
            "messaging_notes": list(memory.get("messaging_notes") or [])[-5:],
            "copy_notes": list(memory.get("copy_notes") or [])[-5:],
            "positive_examples": list(memory.get("positive_examples") or [])[-5:],
            "negative_examples": list(memory.get("negative_examples") or [])[-5:],
            "material_notes": {
                key: list(items or [])[-3:]
                for key, items in (memory.get("material_notes") or {}).items()
                if items
            },
        },
        "blackboard": {
            "active_brief": board.get("active_brief") or {},
            "artifacts": board.get("artifacts") or {},
            "recent_decisions": list(board.get("decisions") or [])[-5:],
            "reference_analysis": board.get("reference_analysis") or {},
            "learning_summary": board.get("learning_summary") or {},
            "material_recipes": board.get("material_recipes") or {},
        },
        "learnings": summarize_learnings_memory(learnings, limit=limit),
        "inspiration_board": {
            "path": str(inspiration_board_path(brand_dir)),
            "summary": build_inspiration_board_summary(inspiration_board),
        },
    }
