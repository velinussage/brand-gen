from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

from .learnings_memory import learnings_memory_path, load_learnings_memory, summarize_learnings_memory
from .runtime_brand import (
    get_brand_gen_dir,
    load_brand_gen_config,
    load_inspirations_config,
    load_manifest,
    resolve_active_brand_key,
)
from .runtime_io import load_json_file
from .runtime_models import (
    DEPRECATED_MATERIAL_TYPES,
    INTERFACE_MATERIAL_KEYS,
    MATERIAL_CONFIG,
    MATERIAL_PROMPT_SNIPPET_ALIASES,
    MODELS,
    model_supports_motion_reference,
    model_supports_reference_images,
)
from .runtime_paths import REPO_ROOT
from .runtime_support import version_sort_key
from .run_ledger import load_all_run_events


def _path_info(path: Path | None) -> dict[str, Any]:
    if not path:
        return {"path": "", "exists": False, "mtime": ""}
    resolved = Path(path).expanduser().resolve()
    exists = resolved.exists()
    mtime = ""
    if exists:
        try:
            mtime = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(resolved.stat().st_mtime))
        except OSError:
            mtime = ""
    return {"path": str(resolved), "exists": exists, "mtime": mtime}


def _workspace_kind(brand_dir: Path, brand_gen_root: Path | None) -> tuple[str, str | None]:
    if not brand_gen_root:
        return "legacy_or_unknown", None
    sessions_root = (brand_gen_root / "sessions").resolve()
    try:
        rel = brand_dir.resolve().relative_to(sessions_root)
        if len(rel.parts) >= 2 and rel.parts[1] == "brand-materials":
            return "session", rel.parts[0]
    except (OSError, ValueError):
        pass
    brands_root = (brand_gen_root / "brands").resolve()
    try:
        rel = brand_dir.resolve().relative_to(brands_root)
        if rel.parts:
            return "saved_brand", None
    except (OSError, ValueError):
        pass
    return "legacy_or_unknown", None


def resolve_brand_gen_root_status() -> dict[str, Any]:
    env_value = os.environ.get("BRAND_GEN_DIR")
    env_override = Path(env_value).expanduser().resolve() if env_value else None
    repo_candidate = (REPO_ROOT / ".brand-gen").resolve()
    resolved = get_brand_gen_dir()
    resolution_mode = "missing"
    degraded = True
    if env_override:
        resolution_mode = "env"
        degraded = False
    elif repo_candidate.exists():
        resolution_mode = "repo_local_fallback"
        degraded = True
    elif resolved:
        resolution_mode = "legacy_fallback"
        degraded = True
    candidate_roots: list[str] = []
    for candidate in [env_override, repo_candidate if repo_candidate.exists() else None, resolved]:
        if candidate and str(candidate) not in candidate_roots:
            candidate_roots.append(str(candidate))
    return {
        "brand_gen_root": str(resolved.resolve()) if resolved else "",
        "resolution_mode": resolution_mode,
        "degraded": degraded,
        "brand_gen_dir_env": str(env_override) if env_override else "",
        "repo_local_root": str(repo_candidate) if repo_candidate.exists() else "",
        "candidate_roots": candidate_roots,
        "multiple_candidate_roots": len(candidate_roots) > 1,
    }


def prompt_resource_root() -> Path:
    return (REPO_ROOT / "prompts").resolve()


def list_prompt_resources() -> list[dict[str, Any]]:
    root = prompt_resource_root()
    items: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix.lower() not in {".md", ".json"}:
            continue
        rel = path.relative_to(root).as_posix()
        info = _path_info(path)
        items.append(
            {
                "name": rel,
                "path": info["path"],
                "mtime": info["mtime"],
                "kind": "prompt",
                "format": path.suffix.lower().lstrip("."),
            }
        )
    return items


def get_prompt_resource(name: str) -> dict[str, Any]:
    wanted = str(name or "").strip().lstrip("/")
    if not wanted:
        raise FileNotFoundError("Prompt name is required.")
    root = prompt_resource_root()
    path = (root / wanted).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise FileNotFoundError(f"Prompt resource '{wanted}' is outside prompts/.") from exc
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f"Prompt resource '{wanted}' not found.")
    return {
        "name": wanted,
        "path": str(path),
        "content": path.read_text(),
        "mtime": _path_info(path)["mtime"],
        "format": path.suffix.lower().lstrip("."),
    }


def _latest_generation_scratchpad_path(brand_dir: Path, board: dict) -> Path | None:
    artifacts = board.get("artifacts") or {}
    latest = str(artifacts.get("latest_generation_scratchpad") or "").strip()
    if latest:
        path = Path(latest).expanduser().resolve()
        if path.exists():
            return path
    scratch_dir = brand_dir / "scratchpads" / "generation"
    candidates = sorted(scratch_dir.glob("*.json"), key=lambda path: path.stat().st_mtime if path.exists() else 0, reverse=True)
    return candidates[0] if candidates else None


def _count_iteration_examples(items: list[Any]) -> int:
    return len(items or [])


def _latest_iteration_version(memory: dict) -> str:
    examples = list(memory.get("positive_examples") or []) + list(memory.get("negative_examples") or [])
    versions = [str(item.get("version") or "").strip() for item in examples if str(item.get("version") or "").strip()]
    return next(iter(sorted(versions, key=version_sort_key, reverse=True)), "")


def _load_plugin_markers(brand_gen_root: Path | None) -> list[dict[str, Any]]:
    if not brand_gen_root:
        return []
    marker_dir = brand_gen_root / "runtime-status" / "plugins"
    items: list[dict[str, Any]] = []
    for path in sorted(marker_dir.glob("*.json")):
        payload = load_json_file(path)
        if not payload:
            continue
        payload["marker_path"] = str(path.resolve())
        items.append(payload)
    return items


def _load_local_workspace_config() -> dict[str, Any]:
    """Load repo-local machine config without failing context snapshots.

    `.brand-gen-local.json` is intentionally untracked and may contain
    machine-specific Obsidian/doc paths. The snapshot exposes only path
    existence/freshness metadata so Pi agents can decide whether a brand has
    configured knowledge bases without embedding personal paths in shared docs.
    """
    path = REPO_ROOT / ".brand-gen-local.json"
    if not path.exists():
        return {}
    payload = load_json_file(path)
    return payload if isinstance(payload, dict) else {}


def _knowledge_base_paths_for_brand(active_brand: str, profile: dict) -> list[dict[str, Any]]:
    local = _load_local_workspace_config()
    brand_key = str(active_brand or "").strip()
    raw_paths: list[Any] = []

    # Backward-compatible global paths. These are useful when a checkout is
    # dedicated to one brand, but the brand-specific maps below should be used
    # for multi-brand installs.
    raw_paths.extend(local.get("vault_paths") or [])

    for map_key in ("brand_vault_paths", "brand_knowledge_base_paths"):
        mapping = local.get(map_key) or {}
        if isinstance(mapping, dict) and brand_key:
            raw_paths.extend(mapping.get(brand_key) or [])

    creative_context = profile.get("creative_context") if isinstance(profile, dict) else {}
    if isinstance(creative_context, dict):
        raw_paths.extend(creative_context.get("knowledge_base_paths") or [])
        raw_paths.extend(creative_context.get("source_vault_paths") or [])

    seen: set[str] = set()
    paths: list[dict[str, Any]] = []
    for raw in raw_paths:
        text = str(raw or "").strip()
        if not text:
            continue
        resolved = str(Path(text).expanduser().resolve())
        if resolved in seen:
            continue
        seen.add(resolved)
        info = _path_info(Path(resolved))
        md_count = 0
        latest_mtime = info.get("mtime") or ""
        if info.get("exists"):
            try:
                path = Path(resolved)
                md_files = list(path.rglob("*.md")) if path.is_dir() else ([path] if path.suffix.lower() == ".md" else [])
                md_count = len(md_files)
                mtimes = [candidate.stat().st_mtime for candidate in md_files if candidate.exists()]
                if mtimes:
                    latest_mtime = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(max(mtimes)))
            except OSError:
                md_count = 0
        paths.append(
            {
                "path": resolved,
                "exists": bool(info.get("exists")),
                "mtime": info.get("mtime") or "",
                "markdown_file_count": md_count,
                "latest_markdown_mtime": latest_mtime,
            }
        )
    return paths


def _markdown_excerpt(text: str, query_tokens: list[str], *, max_chars: int) -> str:
    normalized = text.replace("\r\n", "\n").strip()
    if not normalized:
        return ""
    lowered = normalized.lower()
    idx = -1
    for token in query_tokens:
        idx = lowered.find(token)
        if idx >= 0:
            break
    if idx < 0:
        idx = 0
    start = max(0, idx - max_chars // 3)
    end = min(len(normalized), start + max_chars)
    excerpt = normalized[start:end].strip()
    if start > 0:
        excerpt = "…" + excerpt
    if end < len(normalized):
        excerpt += "…"
    return excerpt


def _title_from_markdown(path: Path, text: str) -> str:
    for line in text.splitlines()[:20]:
        stripped = line.strip()
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip() or path.stem
    return path.stem.replace("-", " ").replace("_", " ").strip() or path.name


def build_source_knowledge_payload(
    brand_dir: Path,
    profile: dict,
    identity: dict,
    *,
    query: str = "",
    limit: int = 8,
    max_chars: int = 900,
) -> dict[str, Any]:
    """Return bounded local knowledge excerpts for the active brand.

    This is intentionally a local, read-only surface. It lets typed-tool-only
    agents inspect configured Obsidian/docs folders without embedding private
    paths or source contents in repo-tracked prompts.
    """
    snapshot = build_context_snapshot_payload(brand_dir, profile, identity, limit=3)
    source_knowledge = snapshot.get("source_knowledge") or {}
    paths = [item for item in (source_knowledge.get("paths") or []) if item.get("exists")]
    query_tokens = [token.lower() for token in str(query or "").split() if len(token.strip()) > 2]
    candidates: list[dict[str, Any]] = []
    max_scan_files = 500
    scanned = 0
    for info in paths:
        root = Path(str(info.get("path") or "")).expanduser()
        if not root.exists():
            continue
        md_files = sorted(root.rglob("*.md")) if root.is_dir() else ([root] if root.suffix.lower() == ".md" else [])
        for path in md_files[: max(0, max_scan_files - scanned)]:
            scanned += 1
            try:
                text = path.read_text(errors="ignore")
            except OSError:
                continue
            lowered = text.lower()
            if query_tokens:
                score = sum(lowered.count(token) for token in query_tokens)
                name_score = sum(path.name.lower().count(token) for token in query_tokens)
                if score + name_score <= 0:
                    continue
            else:
                score = 0
                name_score = 0
            try:
                relpath = path.relative_to(root).as_posix()
            except ValueError:
                relpath = path.name
            candidates.append(
                {
                    "path": str(path.resolve()),
                    "source_root": str(root.resolve()),
                    "relpath": relpath,
                    "title": _title_from_markdown(path, text),
                    "score": int(score + name_score * 5),
                    "mtime": _path_info(path).get("mtime") or "",
                    "excerpt": _markdown_excerpt(text, query_tokens, max_chars=max(120, int(max_chars or 900))),
                }
            )
            if scanned >= max_scan_files:
                break
    if query_tokens:
        candidates.sort(key=lambda item: (item.get("score") or 0, item.get("mtime") or ""), reverse=True)
    else:
        candidates.sort(key=lambda item: item.get("mtime") or "", reverse=True)
    return {
        "brand": (snapshot.get("workspace") or {}).get("active_brand") or "",
        "configured": bool(paths),
        "query": query,
        "paths": source_knowledge.get("paths") or [],
        "scanned_markdown_files": scanned,
        "results": candidates[: max(1, int(limit or 8))],
        "instruction": "Use excerpts as brand-specific source truth. Do not apply them to other brands.",
    }


def _material_capabilities() -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for material_type, config in sorted(MATERIAL_CONFIG.items()):
        material_key = MATERIAL_PROMPT_SNIPPET_ALIASES.get(material_type, material_type.replace("-", "_"))
        classification = "interface" if material_key in INTERFACE_MATERIAL_KEYS else "non_interface"
        deprecated = DEPRECATED_MATERIAL_TYPES.get(material_type) or {}
        items.append(
            {
                "material_type": material_type,
                "classification": classification,
                "generation_mode": config.get("generation_mode") or "",
                "default_model": config.get("default_model") or "",
                "default_aspect_ratio": config.get("default_aspect_ratio") or "",
                "deprecated": bool(deprecated),
                "preferred_material_type": deprecated.get("prefer") or "",
                "deprecation_note": deprecated.get("note") or "",
            }
        )
    return items


def _model_capabilities() -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for generation_mode, model_map in sorted(MODELS.items()):
        for alias, config in sorted((model_map or {}).items()):
            items.append(
                {
                    "alias": alias,
                    "generation_mode": generation_mode,
                    "best_for": config.get("best_for") or "",
                    "cost": config.get("cost") or "",
                    "supports_reference_images": model_supports_reference_images(config, generation_mode),
                    "supports_base_image": bool(config.get("supports_base_image")),
                    "supports_motion_reference": model_supports_motion_reference(config),
                }
            )
    return items


def build_capabilities_payload() -> dict[str, Any]:
    from .command_registry import COMMAND_SPECS

    tools = []
    for spec in COMMAND_SPECS:
        tools.append(
            {
                "command": spec.name,
                "tool_name": f"brand_{spec.name.replace('-', '_')}",
                "read_only": spec.read_only,
                "mutates_state": spec.mutates_state,
                "primitive": spec.primitive,
                "convenience": spec.convenience,
                "feature_tags": list(spec.feature_tags),
            }
        )
    command_names = {spec.name for spec in COMMAND_SPECS}
    return {
        "material_types": _material_capabilities(),
        "models": _model_capabilities(),
        "tools": tools,
        "feature_flags": {
            "internal_vlm_critique_available": True,
            "set_workflows_available": {"plan-set", "validate-set", "generate-set"}.issubset(command_names),
            "prompt_resources_available": {"prompts-list", "prompts-get"}.issubset(command_names),
            "workspace_status_available": "workspace-status" in command_names,
        },
    }


def _suggest_next_commands(
    *,
    generated_count: int,
    latest_version: str,
    latest_scratchpad_path: str,
    has_active_critique: bool,
) -> list[str]:
    commands: list[str] = []
    if not generated_count:
        commands.extend(["route-request", "plan-draft", "pipeline"])
    elif latest_version:
        commands.extend(["show-session-summary", "compare", "review-brand"])
    if latest_scratchpad_path:
        commands.append("generate-once")
    if has_active_critique:
        commands.append("submit-critique")
    return commands


def build_context_snapshot_payload(brand_dir: Path, profile: dict, identity: dict, *, limit: int = 5) -> dict[str, Any]:
    brand_dir = brand_dir.expanduser().resolve()
    brand_gen_status = resolve_brand_gen_root_status()
    brand_gen_root = Path(brand_gen_status["brand_gen_root"]) if brand_gen_status["brand_gen_root"] else None
    workspace_kind, session_key = _workspace_kind(brand_dir, brand_gen_root)
    config = load_brand_gen_config(brand_gen_dir=brand_gen_root)
    manifest = load_manifest(brand_dir)
    versions = manifest.get("versions") or {}
    latest_version = next(iter(sorted(versions.keys(), key=version_sort_key, reverse=True)), "")
    board = load_json_file(brand_dir / "blackboard.json")
    iteration_memory = load_json_file(brand_dir / "iteration-memory.json")
    run_events = load_all_run_events(brand_dir, limit=max(20, limit * 4))
    learnings_path = learnings_memory_path(brand_dir)
    learnings = load_learnings_memory(brand_dir)
    profile_path = brand_dir / "brand-profile.json"
    identity_path = brand_dir / "brand-identity.json"
    inspirations_path = None
    active_brand = ""
    seeded_from_brand = ""
    session_context = ((identity.get("session_context") if isinstance(identity, dict) else None)
                       or (profile.get("session_context") if isinstance(profile, dict) else None)
                       or {})
    seeded_from_brand = str(session_context.get("seeded_from_brand") or "").strip()
    if workspace_kind == "saved_brand":
        active_brand = brand_dir.name
    else:
        active_brand = seeded_from_brand or str(resolve_active_brand_key(brand_gen_dir=brand_gen_root, repo_root=REPO_ROOT) or "")
    if active_brand and brand_gen_root:
        inspirations_path = brand_gen_root / "brands" / active_brand / "inspirations.json"
    inspirations = load_inspirations_config(active_brand, brand_gen_root) if active_brand and brand_gen_root else {"sources": [], "mergeStrategy": "concat"}
    knowledge_base_paths = _knowledge_base_paths_for_brand(active_brand, profile)
    latest_scratchpad_path = _latest_generation_scratchpad_path(brand_dir, board)
    latest_scratchpad = load_json_file(latest_scratchpad_path) if latest_scratchpad_path else {}
    prompt_context = latest_scratchpad.get("prompt_context") or {}
    prompt_review = latest_scratchpad.get("prompt_review") or {}
    execution_sections = prompt_review.get("execution_prompt_sections") or {}
    artifacts = board.get("artifacts") or {}
    review_dir = brand_dir / "reviews"
    review_candidates = sorted(review_dir.glob("*"), key=lambda path: path.stat().st_mtime if path.exists() else 0, reverse=True)
    latest_review_packet = next((path for path in review_candidates if path.suffix.lower() in {".md", ".json"}), None)
    latest_review_files = [str(path.resolve()) for path in review_candidates[:5]]
    has_active_critique = bool((artifacts.get("latest_auto_review") or latest_review_files))

    return {
        "brand_gen_root": brand_gen_status["brand_gen_root"],
        "brand_gen_root_status": brand_gen_status,
        "brand_dir": str(brand_dir),
        "workspace": {
            "kind": workspace_kind,
            "active_brand": active_brand,
            "active_session": session_key or str(config.get("activeSession") or "") or None,
            "seeded_from_brand": seeded_from_brand,
            "is_testing_fork": workspace_kind == "session",
        },
        "files": {
            "profile": _path_info(profile_path),
            "identity": _path_info(identity_path),
            "config": _path_info((brand_gen_root / "config.json") if brand_gen_root else None),
            "inspirations": _path_info(inspirations_path),
            "manifest": _path_info(brand_dir / "manifest.json"),
            "blackboard": _path_info(brand_dir / "blackboard.json"),
            "iteration_memory": _path_info(brand_dir / "iteration-memory.json"),
            "learnings": _path_info(learnings_path),
        },
        "config": {
            "inspiration_mode": bool(config.get("inspirationMode")),
            "brand_gen_dir": str(config.get("brandGenDir") or brand_gen_status["brand_gen_root"] or ""),
            "active": str(config.get("active") or ""),
            "active_session": str(config.get("activeSession") or ""),
        },
        "inspirations": {
            "sources": list(inspirations.get("sources") or []),
            "merge_strategy": inspirations.get("mergeStrategy") or "concat",
            "mode": inspirations.get("mode") or "principles",
        },
        "source_knowledge": {
            "configured": bool(knowledge_base_paths),
            "paths": knowledge_base_paths,
            "instruction": (
                "If configured paths exist, brand-philosopher/interviewer should inspect the relevant "
                "markdown files before planning and convert brand-specific facts into typed prompt seeds, "
                "approved copy, or scratchpad notes. Do not assume these paths apply to other brands."
            ),
        },
        "counts": {
            "manifest": {"count": len(versions), "latest_id": latest_version},
            "blackboard": {
                "decision_count": len(board.get("decisions") or []),
                "latest_workflow_id": str(((board.get("generated_assets") or [])[-1].get("workflow_id") if (board.get("generated_assets") or []) else "") or ""),
                "learning_material_count": len(board.get("learning_summary") or {}),
            },
            "iteration_memory": {
                "brand_notes": len(iteration_memory.get("brand_notes") or []),
                "messaging_notes": len(iteration_memory.get("messaging_notes") or []),
                "copy_notes": len(iteration_memory.get("copy_notes") or []),
                "positive_examples": _count_iteration_examples(iteration_memory.get("positive_examples") or []),
                "negative_examples": _count_iteration_examples(iteration_memory.get("negative_examples") or []),
                "latest_id": _latest_iteration_version(iteration_memory),
            },
            "runs": {
                "event_count": len(run_events),
                "latest_id": str((run_events[-1].get("workflow_id") if run_events else "") or ""),
            },
            "learnings": {
                "insight_count": sum(len(learnings.get(key) or []) for key in [
                    "modelPreferences",
                    "colorInsights",
                    "compositionPatterns",
                    "failurePatterns",
                    "messagingInsights",
                    "audienceInsights",
                ]),
                "latest_id": str(learnings.get("lastUpdated") or ""),
            },
        },
        "learnings": summarize_learnings_memory(learnings, limit=limit),
        "prompt_sizes": {
            "latest_scratchpad_path": str(latest_scratchpad_path.resolve()) if latest_scratchpad_path else "",
            "prelude_chars": len(str(prompt_context.get("brand_prelude") or "")),
            "doctrine_chars": len(str(prompt_context.get("inspiration_doctrine") or "")),
            "reference_analysis_chars": len(str(prompt_context.get("reference_analysis_snippet") or "")),
            "execution_prompt_chars": len(str(latest_scratchpad.get("execution_prompt") or latest_scratchpad.get("effective_prompt") or "")),
            "execution_prompt_sections": {
                key: len(str(value or ""))
                for key, value in execution_sections.items()
            },
        },
        "pointers": {
            "compare_board": str((brand_dir / "compare.html").resolve()),
            "latest_review_packet": str(latest_review_packet.resolve()) if latest_review_packet else "",
            "latest_review_files": latest_review_files,
            "latest_plan_draft": str(artifacts.get("latest_plan_draft") or ""),
            "latest_plan_critique": str(artifacts.get("latest_plan_critique") or ""),
            "latest_generation_scratchpad": str(artifacts.get("latest_generation_scratchpad") or ""),
            "latest_generated_version": str(artifacts.get("latest_generated_version") or latest_version or ""),
            "latest_auto_review": str(artifacts.get("latest_auto_review") or ""),
        },
        "next_suggested_commands": _suggest_next_commands(
            generated_count=len(versions),
            latest_version=latest_version,
            latest_scratchpad_path=str(latest_scratchpad_path or ""),
            has_active_critique=has_active_critique,
        ),
    }


def build_workspace_status_payload(brand_dir: Path, profile: dict, identity: dict) -> dict[str, Any]:
    snapshot = build_context_snapshot_payload(brand_dir, profile, identity)
    brand_gen_root = Path(snapshot["brand_gen_root"]) if snapshot.get("brand_gen_root") else None
    plugin_markers = _load_plugin_markers(brand_gen_root)
    brand_dir_resolved = str(brand_dir.expanduser().resolve())
    warnings: list[str] = []
    for marker in plugin_markers:
        marker_root = str(marker.get("resolved_root") or "")
        if marker_root and marker_root != snapshot["brand_gen_root"]:
            warnings.append(f"Plugin '{marker.get('plugin_name') or marker.get('plugin') or 'plugin'}' points at a different BRAND_GEN_DIR: {marker_root}")
        marker_workspace = str(marker.get("workspace_dir") or "")
        if marker_workspace and marker_workspace != brand_dir_resolved:
            warnings.append(f"Plugin '{marker.get('plugin_name') or marker.get('plugin') or 'plugin'}' is attached to a different workspace: {marker_workspace}")
    if snapshot["brand_gen_root_status"].get("multiple_candidate_roots"):
        warnings.append("Multiple candidate .brand-gen roots detected.")
    if snapshot["brand_gen_root_status"].get("degraded"):
        warnings.append("BRAND_GEN_DIR is not explicitly set; running in degraded compatibility mode.")
    return {
        "brand_gen_root": snapshot["brand_gen_root"],
        "resolution_mode": snapshot["brand_gen_root_status"].get("resolution_mode"),
        "degraded": snapshot["brand_gen_root_status"].get("degraded"),
        "candidate_roots": snapshot["brand_gen_root_status"].get("candidate_roots") or [],
        "workspace": snapshot["workspace"],
        "brand_dir": snapshot["brand_dir"],
        "manifest_path": snapshot["files"]["manifest"]["path"],
        "plugin_markers": plugin_markers,
        "plugin_matches_python_workspace": all(
            (not marker.get("workspace_dir")) or str(marker.get("workspace_dir")) == brand_dir_resolved
            for marker in plugin_markers
        ),
        "plugin_matches_python_root": all(
            (not marker.get("resolved_root")) or str(marker.get("resolved_root")) == snapshot["brand_gen_root"]
            for marker in plugin_markers
        ),
        "warnings": warnings,
    }


def format_workspace_status_text(payload: dict[str, Any]) -> str:
    lines = [
        "Workspace status",
        "",
        f"BRAND_GEN_DIR: {payload.get('brand_gen_root') or 'n/a'}",
        f"Resolution mode: {payload.get('resolution_mode') or 'n/a'}",
        f"Workspace: {(payload.get('workspace') or {}).get('kind') or 'n/a'}",
        f"Brand dir: {payload.get('brand_dir') or 'n/a'}",
    ]
    workspace = payload.get("workspace") or {}
    if workspace.get("active_brand"):
        lines.append(f"Active brand: {workspace['active_brand']}")
    if workspace.get("active_session"):
        lines.append(f"Active session: {workspace['active_session']}")
    if workspace.get("seeded_from_brand"):
        lines.append(f"Seeded from brand: {workspace['seeded_from_brand']}")
    if payload.get("candidate_roots"):
        lines.append("Candidate roots: " + ", ".join(payload["candidate_roots"]))
    markers = payload.get("plugin_markers") or []
    if markers:
        lines.append("")
        lines.append("Plugin markers:")
        for marker in markers:
            lines.append(
                f"- {(marker.get('plugin_name') or marker.get('plugin') or 'plugin')}: "
                f"root={marker.get('resolved_root') or 'n/a'} workspace={marker.get('workspace_dir') or 'n/a'}"
            )
    warnings = payload.get("warnings") or []
    if warnings:
        lines.append("")
        lines.append("Warnings:")
        lines.extend(f"- {item}" for item in warnings)
    return "\n".join(lines)


__all__ = [
    "build_capabilities_payload",
    "build_context_snapshot_payload",
    "build_source_knowledge_payload",
    "build_workspace_status_payload",
    "format_workspace_status_text",
    "get_prompt_resource",
    "list_prompt_resources",
    "prompt_resource_root",
    "resolve_brand_gen_root_status",
]
