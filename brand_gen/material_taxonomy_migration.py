from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .brand_policy import normalize_material_brand_policy
from .request_intent import resolve_planner_material_type
from .runtime import role_pack_material_key
from .runtime_models import DEPRECATED_MATERIAL_TYPES

__all__ = [
    "migrate_material_type",
    "migrate_plan_payload",
    "migrate_set_manifest_payload",
    "migrate_generation_scratchpad_payload",
    "migrate_manifest_payload",
    "migrate_workspace",
    "find_saved_workspaces",
    "migrate_workspaces",
    "report_workspace_deprecated_usage",
    "report_workspaces_deprecated_usage",
]


WORKSPACE_JSON_GLOBS = (
    "manifest.json",
    "plans/*.json",
    "sets/*.json",
    "scratchpads/plan-drafts/*.json",
    "scratchpads/plan-critiques/*.json",
    "scratchpads/generation/*.json",
    "learnings.json",
    "iteration-memory.json",
    "blackboard.json",
)

REPORT_JSON_GLOBS = WORKSPACE_JSON_GLOBS

_IGNORE_REPORT_BRANCH_KEYS = {
    "material_type_resolution",
    "deprecated_material_types",
}

_IGNORE_REPORT_SCALAR_KEYS = {
    "requested_material_type",
    "legacy_material_type",
}


def _context_from_mapping(payload: dict[str, Any] | None) -> dict[str, str]:
    payload = payload or {}
    return {
        "purpose": str(payload.get("purpose") or ""),
        "target_surface": str(payload.get("target_surface") or ""),
        "prompt_seed": str(payload.get("prompt_seed") or payload.get("raw_prompt") or payload.get("prompt") or ""),
        "briefing": str(payload.get("briefing") or payload.get("notes") or ""),
        "product_truth_expression": str(payload.get("product_truth_expression") or ""),
    }


def migrate_material_type(material_type: str | None, *, context: dict[str, Any] | None = None) -> tuple[str, str]:
    ctx = _context_from_mapping(context)
    return resolve_planner_material_type(material_type, **ctx)


def _merge_brand_anchor_policy(material_type: str, policy: dict[str, Any] | None) -> dict[str, Any]:
    base = normalize_material_brand_policy(material_type)
    existing = dict(policy or {})
    for key in (
        "role",
        "target_surface",
        "purpose",
        "product_truth_expression",
        "abstraction_level",
        "logo_mode",
        "clearly_branded_without_logo_min",
    ):
        if existing.get(key) not in (None, "", [], {}):
            base[key] = existing[key]
    return base


def migrate_plan_payload(plan: dict[str, Any]) -> tuple[dict[str, Any], int]:
    if not isinstance(plan, dict):
        return plan, 0
    old_type = str(plan.get("material_type") or "").strip()
    if not old_type:
        return plan, 0
    new_type, note = migrate_material_type(old_type, context=plan)
    if new_type == old_type:
        return plan, 0

    changes = 0
    plan["material_type"] = new_type
    changes += 1
    plan.setdefault("requested_material_type", old_type)
    plan["material_type_resolution"] = {
        "requested": old_type,
        "resolved": new_type,
        "changed": True,
        "note": note,
        "migration": "taxonomy-v1",
    }
    if isinstance(plan.get("brand_anchor_policy"), dict) or "brand_anchor_policy" in plan:
        plan["brand_anchor_policy"] = _merge_brand_anchor_policy(new_type, plan.get("brand_anchor_policy") or {})
        changes += 1
    if isinstance(plan.get("role_pack"), dict):
        plan["role_pack"]["material_key"] = role_pack_material_key(new_type)
        changes += 1
    return plan, changes


def migrate_set_manifest_payload(payload: dict[str, Any]) -> tuple[dict[str, Any], int]:
    if not isinstance(payload, dict):
        return payload, 0
    materials = payload.get("materials")
    if not isinstance(materials, list):
        return payload, 0
    changes = 0
    for item in materials:
        if not isinstance(item, dict):
            continue
        old_type = str(item.get("material_type") or "").strip()
        if not old_type:
            continue
        new_type, note = migrate_material_type(old_type, context=item)
        if new_type == old_type:
            continue
        item["material_type"] = new_type
        item["material_key"] = role_pack_material_key(new_type)
        item.setdefault("requested_material_type", old_type)
        item["material_type_resolution"] = {
            "requested": old_type,
            "resolved": new_type,
            "changed": True,
            "note": note,
            "migration": "taxonomy-v1",
        }
        changes += 1
    return payload, changes


def migrate_generation_scratchpad_payload(payload: dict[str, Any]) -> tuple[dict[str, Any], int]:
    if not isinstance(payload, dict):
        return payload, 0
    old_type = str(payload.get("material_type") or "").strip()
    if not old_type:
        return payload, 0
    new_type, note = migrate_material_type(old_type, context=payload)
    if new_type == old_type:
        return payload, 0
    payload["material_type"] = new_type
    payload.setdefault("requested_material_type", old_type)
    payload["material_type_resolution"] = {
        "requested": old_type,
        "resolved": new_type,
        "changed": True,
        "note": note,
        "migration": "taxonomy-v1",
    }
    prompt_context = payload.get("prompt_context")
    if isinstance(prompt_context, dict) and prompt_context.get("material_type"):
        prompt_context["material_type"] = new_type
    return payload, 1


def migrate_manifest_payload(payload: dict[str, Any]) -> tuple[dict[str, Any], int]:
    if not isinstance(payload, dict):
        return payload, 0
    versions = payload.get("versions")
    if not isinstance(versions, dict):
        return payload, 0
    changes = 0
    for entry in versions.values():
        if not isinstance(entry, dict):
            continue
        old_type = str(entry.get("material_type") or "").strip()
        if not old_type:
            continue
        new_type, note = migrate_material_type(old_type, context=entry)
        if new_type == old_type:
            continue
        entry["material_type"] = new_type
        entry.setdefault("legacy_material_type", old_type)
        entry["material_type_resolution"] = {
            "requested": old_type,
            "resolved": new_type,
            "changed": True,
            "note": note,
            "migration": "taxonomy-v1",
        }
        changes += 1
    return payload, changes


def _migrate_deprecated_material_references(value: Any, *, parent_key: str = "") -> int:
    """Recursively rewrite deprecated material-type references in payloads.

    The first migration pass handled top-level plan/manifest/scratchpad
    fields, but saved artifacts also embed plans inside wrappers
    (``plan_wrapper.plan.material_type``), critiques
    (``plan_critique.plan.material_type``), learning rollups, and memory
    arrays. The report command scans all of those nested locations, so the
    writer must migrate them too.
    """

    changes = 0
    if isinstance(value, dict):
        if parent_key in _IGNORE_REPORT_BRANCH_KEYS:
            return 0

        material_type = value.get("material_type")
        if isinstance(material_type, str) and material_type in DEPRECATED_MATERIAL_TYPES:
            old_type = material_type
            new_type, note = migrate_material_type(old_type, context=value)
            if new_type != old_type:
                value["material_type"] = new_type
                changes += 1
                # Only plan-like records get the richer migration metadata.
                # Small memory/rollup entries should stay compact.
                if any(key in value for key in ("prompt_seed", "purpose", "target_surface", "brand_anchor_policy", "role_pack")):
                    value.setdefault("requested_material_type", old_type)
                    value["material_type_resolution"] = {
                        "requested": old_type,
                        "resolved": new_type,
                        "changed": True,
                        "note": note,
                        "migration": "taxonomy-v1",
                    }
                    if isinstance(value.get("brand_anchor_policy"), dict) or "brand_anchor_policy" in value:
                        value["brand_anchor_policy"] = _merge_brand_anchor_policy(new_type, value.get("brand_anchor_policy") or {})
                    if isinstance(value.get("role_pack"), dict):
                        value["role_pack"]["material_key"] = role_pack_material_key(new_type)

        for key, nested in value.items():
            if key in _IGNORE_REPORT_BRANCH_KEYS or key in _IGNORE_REPORT_SCALAR_KEYS:
                continue
            if key == "applies_to_material_types" and isinstance(nested, list):
                for idx, item in enumerate(nested):
                    if isinstance(item, str) and item in DEPRECATED_MATERIAL_TYPES:
                        new_type, _ = migrate_material_type(item)
                        if new_type != item:
                            nested[idx] = new_type
                            changes += 1
                continue
            changes += _migrate_deprecated_material_references(nested, parent_key=key)
        return changes

    if isinstance(value, list):
        for item in value:
            changes += _migrate_deprecated_material_references(item, parent_key=parent_key)
    return changes


def _migrate_payload(path: Path, payload: dict[str, Any]) -> tuple[dict[str, Any], int, str]:
    kind = "unknown"
    changes = 0
    if path.name == "manifest.json":
        payload, changes = migrate_manifest_payload(payload)
        kind = "manifest"
    elif payload.get("schema_type") == "plan_draft" and isinstance(payload.get("plan"), dict):
        _, changes = migrate_plan_payload(payload["plan"])
        kind = "plan_draft"
    elif payload.get("schema_type") == "plan_critique" and isinstance(payload.get("plan"), dict):
        _, changes = migrate_plan_payload(payload["plan"])
        kind = "plan_critique"
    elif payload.get("schema_type") == "generation_scratchpad":
        payload, changes = migrate_generation_scratchpad_payload(payload)
        kind = "generation_scratchpad"
    elif isinstance(payload.get("materials"), list):
        payload, changes = migrate_set_manifest_payload(payload)
        kind = "set_manifest"
    elif payload.get("material_type"):
        payload, changes = migrate_plan_payload(payload)
        kind = "plan"

    nested_changes = _migrate_deprecated_material_references(payload)
    return payload, changes + nested_changes, kind


def migrate_workspace(brand_dir: Path, *, apply: bool = False) -> dict[str, Any]:
    brand_dir = Path(brand_dir).expanduser().resolve()
    changed_files: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    total_changes = 0
    for pattern in WORKSPACE_JSON_GLOBS:
        for path in sorted(brand_dir.glob(pattern)):
            try:
                payload = json.loads(path.read_text())
            except (json.JSONDecodeError, OSError, UnicodeDecodeError) as exc:
                # Empty/corrupt/unreadable workspace memory file — record the
                # path and keep migrating the rest. Previously this site was
                # wrapped in bare `except Exception`, which also masked real
                # bugs (TypeError, AttributeError) behind the same error
                # bucket. Narrowing to the three expected IO/decode failures.
                errors.append({"path": str(path), "error": f"{type(exc).__name__}: {exc}"})
                continue
            updated, changes, kind = _migrate_payload(path, payload)
            if not changes:
                continue
            total_changes += changes
            changed_files.append({"path": str(path), "kind": kind, "changes": changes})
            if apply:
                path.write_text(json.dumps(updated, indent=2) + "\n")
    return {
        "brand_dir": str(brand_dir),
        "status": "ok" if not errors else "partial",
        "dry_run": not apply,
        "changes": total_changes,
        "files_changed": changed_files,
        "errors": errors,
    }


def find_saved_workspaces(repo_root: Path, brand_gen_dir: Path | None = None, *, include_sessions: bool = False) -> list[Path]:
    repo_root = Path(repo_root).expanduser().resolve()
    configured_brand_gen_dir = Path(brand_gen_dir).expanduser().resolve() if brand_gen_dir else None
    candidate_brand_gen_dirs: list[Path] = []
    if configured_brand_gen_dir:
        candidate_brand_gen_dirs.append(configured_brand_gen_dir)
    nested_brand_gen_dir = repo_root / ".brand-gen"
    if nested_brand_gen_dir.exists() and nested_brand_gen_dir.resolve() not in {path.resolve() for path in candidate_brand_gen_dirs}:
        candidate_brand_gen_dirs.append(nested_brand_gen_dir.resolve())

    discovered: dict[str, Path] = {}

    repo_brands = repo_root / "brands"
    if repo_brands.exists():
        for path in sorted(repo_brands.iterdir()):
            if path.is_dir():
                discovered[str(path.resolve())] = path.resolve()

    for resolved_brand_gen_dir in candidate_brand_gen_dirs:
        saved_brands = resolved_brand_gen_dir / "brands"
        if saved_brands.exists():
            for path in sorted(saved_brands.iterdir()):
                if path.is_dir():
                    discovered[str(path.resolve())] = path.resolve()
        if include_sessions:
            sessions_root = resolved_brand_gen_dir / "sessions"
            if sessions_root.exists():
                for session in sorted(sessions_root.iterdir()):
                    candidate = session / "brand-materials"
                    if candidate.is_dir():
                        discovered[str(candidate.resolve())] = candidate.resolve()

    return [discovered[key] for key in sorted(discovered)]


def migrate_workspaces(workspaces: list[Path], *, apply: bool = False) -> dict[str, Any]:
    results = [migrate_workspace(path, apply=apply) for path in workspaces]
    return {
        "status": "ok" if all(item.get("status") == "ok" for item in results) else "partial",
        "dry_run": not apply,
        "workspace_count": len(workspaces),
        "changes": sum(int(item.get("changes") or 0) for item in results),
        "results": results,
    }


def _file_class(path: Path, brand_dir: Path) -> str:
    try:
        rel = path.resolve().relative_to(brand_dir.resolve())
    except Exception:  # pragma: no cover - defensive
        rel = path
    rel_str = rel.as_posix()
    if rel_str == "manifest.json":
        return "manifest"
    if rel_str.startswith("plans/"):
        return "plans"
    if rel_str.startswith("sets/"):
        return "sets"
    if rel_str.startswith("scratchpads/plan-drafts/"):
        return "scratchpads.plan_drafts"
    if rel_str.startswith("scratchpads/plan-critiques/"):
        return "scratchpads.plan_critiques"
    if rel_str.startswith("scratchpads/generation/"):
        return "scratchpads.generation"
    if rel_str == "learnings.json":
        return "memory.learnings"
    if rel_str == "iteration-memory.json":
        return "memory.iteration"
    if rel_str == "blackboard.json":
        return "memory.blackboard"
    return "other"


def _record_deprecated_scalar(usage: dict[str, Any], *, material_type: str, path: Path, field_path: str, file_class: str) -> None:
    entry = usage.setdefault(material_type, {"count": 0, "files": {}, "file_classes": {}, "examples": []})
    entry["count"] += 1
    entry["files"][str(path)] = entry["files"].get(str(path), 0) + 1
    entry["file_classes"][file_class] = entry["file_classes"].get(file_class, 0) + 1
    if len(entry["examples"]) < 8:
        entry["examples"].append({"path": str(path), "field_path": field_path, "file_class": file_class})


def _scan_deprecated_material_types(value: Any, *, path: Path, field_path: str, usage: dict[str, Any], brand_dir: Path, parent_key: str = "") -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            if key in _IGNORE_REPORT_BRANCH_KEYS:
                continue
            next_path = f"{field_path}.{key}" if field_path else key
            _scan_deprecated_material_types(nested, path=path, field_path=next_path, usage=usage, brand_dir=brand_dir, parent_key=key)
        return
    if isinstance(value, list):
        if parent_key == "applies_to_material_types":
            for idx, item in enumerate(value):
                if isinstance(item, str) and item in DEPRECATED_MATERIAL_TYPES:
                    _record_deprecated_scalar(usage, material_type=item, path=path, field_path=f"{field_path}[{idx}]", file_class=_file_class(path, brand_dir))
        else:
            for idx, item in enumerate(value):
                next_path = f"{field_path}[{idx}]"
                _scan_deprecated_material_types(item, path=path, field_path=next_path, usage=usage, brand_dir=brand_dir, parent_key=parent_key)
        return
    if parent_key in _IGNORE_REPORT_SCALAR_KEYS:
        return
    if parent_key == "material_type" and isinstance(value, str) and value in DEPRECATED_MATERIAL_TYPES:
        _record_deprecated_scalar(usage, material_type=value, path=path, field_path=field_path, file_class=_file_class(path, brand_dir))


def report_workspace_deprecated_usage(brand_dir: Path) -> dict[str, Any]:
    brand_dir = Path(brand_dir).expanduser().resolve()
    usage: dict[str, Any] = {}
    scanned_files = 0
    errors: list[dict[str, Any]] = []
    by_file_class: dict[str, Any] = {}
    for pattern in REPORT_JSON_GLOBS:
        for path in sorted(brand_dir.glob(pattern)):
            scanned_files += 1
            try:
                payload = json.loads(path.read_text())
            except (json.JSONDecodeError, OSError, UnicodeDecodeError) as exc:
                errors.append({"path": str(path), "error": f"{type(exc).__name__}: {exc}"})
                continue
            _scan_deprecated_material_types(payload, path=path, field_path="", usage=usage, brand_dir=brand_dir)
    by_material_type = {
        key: {
            "count": value["count"],
            "file_count": len(value["files"]),
            "files": dict(sorted(value["files"].items())),
            "file_classes": dict(sorted(value.get("file_classes", {}).items())),
            "examples": value["examples"],
            "preferred_material_type": (DEPRECATED_MATERIAL_TYPES.get(key) or {}).get("prefer") or "",
        }
        for key, value in sorted(usage.items())
    }
    for material_type, item in by_material_type.items():
        for file_class, count in (item.get("file_classes") or {}).items():
            target = by_file_class.setdefault(file_class, {"count": 0, "material_types": {}})
            target["count"] += int(count or 0)
            target["material_types"][material_type] = int(count or 0)
    return {
        "brand_dir": str(brand_dir),
        "status": "ok" if not errors else "partial",
        "scanned_files": scanned_files,
        "deprecated_usage_count": sum(item["count"] for item in usage.values()),
        "deprecated_material_types": by_material_type,
        "by_file_class": dict(sorted(by_file_class.items())),
        "errors": errors,
    }


def report_workspaces_deprecated_usage(workspaces: list[Path]) -> dict[str, Any]:
    results = [report_workspace_deprecated_usage(path) for path in workspaces]
    aggregate: dict[str, Any] = {}
    aggregate_by_file_class: dict[str, Any] = {}
    for result in results:
        for material_type, item in (result.get("deprecated_material_types") or {}).items():
            target = aggregate.setdefault(material_type, {"count": 0, "workspace_count": 0, "workspaces": {}, "preferred_material_type": item.get("preferred_material_type") or ""})
            target["count"] += int(item.get("count") or 0)
            target["workspaces"][result["brand_dir"]] = int(item.get("count") or 0)
        for file_class, item in (result.get("by_file_class") or {}).items():
            target = aggregate_by_file_class.setdefault(file_class, {"count": 0, "workspace_count": 0, "workspaces": {}, "material_types": {}})
            target["count"] += int(item.get("count") or 0)
            target["workspaces"][result["brand_dir"]] = int(item.get("count") or 0)
            for material_type, count in (item.get("material_types") or {}).items():
                target["material_types"][material_type] = target["material_types"].get(material_type, 0) + int(count or 0)
    for target in aggregate.values():
        target["workspace_count"] = len(target["workspaces"])
    for target in aggregate_by_file_class.values():
        target["workspace_count"] = len(target["workspaces"])
        target["material_types"] = dict(sorted(target["material_types"].items()))
    return {
        "status": "ok" if all(item.get("status") == "ok" for item in results) else "partial",
        "workspace_count": len(workspaces),
        "deprecated_usage_count": sum(int(item.get("deprecated_usage_count") or 0) for item in results),
        "results": results,
        "aggregate": dict(sorted(aggregate.items())),
        "aggregate_by_file_class": dict(sorted(aggregate_by_file_class.items())),
    }
