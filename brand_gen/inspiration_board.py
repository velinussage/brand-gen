from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

from .runtime_io import dedupe_keep_order, load_json_file
from .runtime_brand import resolve_workflow_id

INSPIRATION_BOARD_SCHEMA_VERSION = 1
INSPIRATION_BOARD_FILENAME = "inspiration-board.json"


def inspiration_board_path(brand_dir: Path) -> Path:
    return Path(brand_dir).expanduser().resolve() / INSPIRATION_BOARD_FILENAME


def _default_board() -> dict[str, Any]:
    return {
        "schema_type": "inspiration_board",
        "schema_version": INSPIRATION_BOARD_SCHEMA_VERSION,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "objects": [],
        "relations": [],
    }


def load_inspiration_board(brand_dir: Path) -> dict[str, Any]:
    path = inspiration_board_path(brand_dir)
    payload = load_json_file(path)
    if not payload:
        return _default_board()
    merged = _default_board()
    merged.update(payload)
    merged["objects"] = list(merged.get("objects") or [])
    merged["relations"] = list(merged.get("relations") or [])
    return merged


def save_inspiration_board(brand_dir: Path, board: dict[str, Any]) -> Path:
    path = inspiration_board_path(brand_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = _default_board()
    payload.update(board or {})
    payload["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    path.write_text(json.dumps(payload, indent=2) + "\n")
    return path


def _stable_id(object_type: str, *parts: object) -> str:
    key = "|".join(str(part or "").strip() for part in parts if str(part or "").strip())
    digest = hashlib.sha1(f"{object_type}:{key}".encode("utf-8")).hexdigest()[:12]
    return f"{object_type.lower()}_{digest}"


def _object_index(board: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(item.get("id") or ""): item
        for item in (board.get("objects") or [])
        if isinstance(item, dict) and str(item.get("id") or "").strip()
    }


def _relation_index(board: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(item.get("id") or ""): item
        for item in (board.get("relations") or [])
        if isinstance(item, dict) and str(item.get("id") or "").strip()
    }


def upsert_object(
    board: dict[str, Any],
    *,
    object_type: str,
    stable_parts: list[object],
    label: str,
    data: dict[str, Any] | None = None,
    workflow_id: str | None = None,
    status: str = "active",
) -> dict[str, Any]:
    object_id = _stable_id(object_type, *stable_parts)
    objects = _object_index(board)
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    item = objects.get(object_id)
    if item is None:
        item = {
            "id": object_id,
            "type": object_type,
            "label": str(label or object_id),
            "status": status,
            "created_at": now,
            "updated_at": now,
            "workflow_ids": [],
            "data": {},
        }
        (board.setdefault("objects", [])).append(item)
    item["label"] = str(label or item.get("label") or object_id)
    item["status"] = str(status or item.get("status") or "active")
    item["updated_at"] = now
    if workflow_id:
        item["workflow_ids"] = dedupe_keep_order(list(item.get("workflow_ids") or []) + [str(workflow_id)])
    merged_data = dict(item.get("data") or {})
    merged_data.update(data or {})
    item["data"] = merged_data
    return item


def add_relation(
    board: dict[str, Any],
    *,
    relation_type: str,
    from_id: str,
    to_id: str,
    workflow_id: str | None = None,
    data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    relation_id = _stable_id("rel", relation_type, from_id, to_id, workflow_id or "")
    relations = _relation_index(board)
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    item = relations.get(relation_id)
    if item is None:
        item = {
            "id": relation_id,
            "type": relation_type,
            "from_id": str(from_id),
            "to_id": str(to_id),
            "created_at": now,
            "updated_at": now,
            "workflow_ids": [],
            "data": {},
        }
        (board.setdefault("relations", [])).append(item)
    item["updated_at"] = now
    if workflow_id:
        item["workflow_ids"] = dedupe_keep_order(list(item.get("workflow_ids") or []) + [str(workflow_id)])
    merged_data = dict(item.get("data") or {})
    merged_data.update(data or {})
    item["data"] = merged_data
    return item


def _reference_stable_parts(item: dict[str, Any]) -> list[object]:
    source_key = str(item.get("source_key") or "").strip()
    source_name = str(item.get("source_name") or "").strip()
    path = str(item.get("path") or "").strip()
    if source_key:
        return [source_key]
    if path:
        return [path]
    return [source_name or "reference"]


def upsert_reference_object(board: dict[str, Any], reference: dict[str, Any], *, workflow_id: str | None = None) -> dict[str, Any]:
    label = str(reference.get("source_name") or reference.get("source_key") or Path(str(reference.get("path") or "")).name or "Reference")
    translation = reference.get("translation") or {}
    return upsert_object(
        board,
        object_type="Reference",
        stable_parts=_reference_stable_parts(reference),
        label=label,
        workflow_id=workflow_id,
        data={
            "source_key": str(reference.get("source_key") or ""),
            "source_name": str(reference.get("source_name") or ""),
            "path": str(reference.get("path") or ""),
            "role": str(reference.get("role") or ""),
            "notes": str(reference.get("notes") or ""),
            "asset_kind": str(reference.get("asset_kind") or ""),
            "translation_summary": str(translation.get("summary") or ""),
            "borrow_mechanics": list(translation.get("borrow_mechanics") or reference.get("borrow_mechanics") or []),
            "avoid_literal": list(translation.get("avoid_literal") or reference.get("avoid_literal") or []),
            "direct_generation_risk": str(translation.get("direct_generation_risk") or reference.get("direct_generation_risk") or ""),
            "translation_only": bool(translation.get("translation_only", reference.get("translation_only"))),
        },
    )


def upsert_inspiration_source_object(board: dict[str, Any], source: dict[str, Any], *, workflow_id: str | None = None) -> dict[str, Any]:
    key = str(source.get("source_key") or source.get("key") or "").strip()
    label = str(source.get("source_name") or source.get("name") or key or "Inspiration source")
    return upsert_object(
        board,
        object_type="Reference",
        stable_parts=[key or source.get("design_memory_path") or label],
        label=label,
        workflow_id=workflow_id,
        data={
            "source_key": key,
            "source_name": label,
            "source_url": str(source.get("source_url") or source.get("url") or ""),
            "design_memory_path": str(source.get("design_memory_path") or ""),
            "selection_mode": str(source.get("selection_mode") or "configured_inspiration"),
            "category": "inspiration_source",
        },
    )


def upsert_direction_object(board: dict[str, Any], plan: dict[str, Any], *, workflow_id: str | None = None) -> dict[str, Any]:
    material_type = str(plan.get("material_type") or "")
    mode = str(plan.get("mode") or "")
    mechanic = str(plan.get("system_mechanic") or "")
    purpose = str(plan.get("purpose") or "")
    label = f"{material_type or 'material'} — {mechanic or purpose or mode or 'direction'}"
    stable_parts = [workflow_id or resolve_workflow_id(plan), material_type, mode, mechanic or purpose]
    return upsert_object(
        board,
        object_type="Direction",
        stable_parts=stable_parts,
        label=label,
        workflow_id=workflow_id,
        data={
            "material_type": material_type,
            "mode": mode,
            "system_mechanic": mechanic,
            "purpose": purpose,
            "target_surface": str(plan.get("target_surface") or ""),
            "product_truth_expression": str(plan.get("product_truth_expression") or ""),
            "abstraction_level": str(plan.get("abstraction_level") or ""),
        },
    )


def upsert_constraint_object(
    board: dict[str, Any],
    *,
    workflow_id: str | None,
    material_type: str,
    bucket: str,
    text: str,
) -> dict[str, Any]:
    return upsert_object(
        board,
        object_type="Constraint",
        stable_parts=[workflow_id or material_type, bucket, text],
        label=f"{bucket}: {text}",
        workflow_id=workflow_id,
        data={"bucket": bucket, "text": text, "material_type": material_type},
    )


def upsert_decision_object(
    board: dict[str, Any],
    *,
    workflow_id: str | None,
    plan: dict[str, Any],
    selected_roles: list[dict[str, Any]],
    missing_required_roles: list[str],
) -> dict[str, Any]:
    material_type = str(plan.get("material_type") or "")
    mode = str(plan.get("mode") or "")
    summary = f"Selected {len(selected_roles)} inspiration refs for {material_type or 'material'}"
    return upsert_object(
        board,
        object_type="Decision",
        stable_parts=[workflow_id or resolve_workflow_id(plan), "role-pack-selection", material_type, mode],
        label=summary,
        workflow_id=workflow_id,
        data={
            "summary": summary,
            "material_type": material_type,
            "mode": mode,
            "selected_roles": [
                {
                    "role": str(item.get("role") or ""),
                    "source_key": str(item.get("source_key") or ""),
                    "source_name": str(item.get("source_name") or ""),
                    "reference_id": str(item.get("_board_reference_id") or ""),
                }
                for item in selected_roles
            ],
            "missing_required_roles": list(missing_required_roles or []),
            "selection_note": str(((plan.get("role_pack") or {}).get("selection_note") or "")),
        },
    )


def upsert_critique_finding_object(
    board: dict[str, Any],
    *,
    workflow_id: str | None,
    material_type: str,
    severity: str,
    category: str,
    message: str,
) -> dict[str, Any]:
    return upsert_object(
        board,
        object_type="CritiqueFinding",
        stable_parts=[workflow_id or material_type, severity, category, message],
        label=message,
        workflow_id=workflow_id,
        status=severity.lower() if severity else "active",
        data={
            "severity": severity,
            "category": category,
            "message": message,
            "material_type": material_type,
        },
    )


def build_inspiration_board_summary(board: dict[str, Any]) -> dict[str, Any]:
    objects = list(board.get("objects") or [])
    relations = list(board.get("relations") or [])
    by_type: dict[str, int] = {}
    for item in objects:
        kind = str(item.get("type") or "unknown")
        by_type[kind] = by_type.get(kind, 0) + 1
    return {
        "object_count": len(objects),
        "relation_count": len(relations),
        "object_types": by_type,
        "updated_at": board.get("updated_at") or "",
    }


def persist_plan_inspiration_board(brand_dir: Path, plan: dict[str, Any], *, workflow_id: str | None = None) -> dict[str, Any]:
    resolved_workflow_id = workflow_id or resolve_workflow_id(plan)
    board = load_inspiration_board(brand_dir)
    direction = upsert_direction_object(board, plan, workflow_id=resolved_workflow_id)

    selected_roles = list(((plan.get("role_pack") or {}).get("selected_roles") or []))
    missing_required_roles = list(((plan.get("role_pack") or {}).get("missing_required_roles") or []))
    reference_ids: list[str] = []
    for item in selected_roles:
        ref = upsert_reference_object(board, item, workflow_id=resolved_workflow_id)
        item["_board_reference_id"] = ref["id"]
        reference_ids.append(ref["id"])
        add_relation(
            board,
            relation_type="selected_for",
            from_id=ref["id"],
            to_id=direction["id"],
            workflow_id=resolved_workflow_id,
            data={
                "role": str(item.get("role") or ""),
                "translation_summary": str(((item.get("translation") or {}).get("summary") or "")),
            },
        )
        add_relation(
            board,
            relation_type="derived_from",
            from_id=direction["id"],
            to_id=ref["id"],
            workflow_id=resolved_workflow_id,
            data={"role": str(item.get("role") or "")},
        )

    constraint_ids: list[str] = []
    for bucket in ("preserve", "push", "ban"):
        for text in [str(value).strip() for value in (plan.get(bucket) or []) if str(value).strip()]:
            constraint = upsert_constraint_object(
                board,
                workflow_id=resolved_workflow_id,
                material_type=str(plan.get("material_type") or ""),
                bucket=bucket,
                text=text,
            )
            constraint_ids.append(constraint["id"])
            add_relation(
                board,
                relation_type="supports" if bucket != "ban" else "conflicts_with",
                from_id=constraint["id"],
                to_id=direction["id"],
                workflow_id=resolved_workflow_id,
                data={"bucket": bucket},
            )

    decision = upsert_decision_object(
        board,
        workflow_id=resolved_workflow_id,
        plan=plan,
        selected_roles=selected_roles,
        missing_required_roles=missing_required_roles,
    )
    add_relation(
        board,
        relation_type="supports",
        from_id=decision["id"],
        to_id=direction["id"],
        workflow_id=resolved_workflow_id,
        data={"reason": "selected inspiration sources and translations"},
    )

    finding_ids: list[str] = []
    role_pack = plan.get("role_pack") or {}
    for warning in role_pack.get("quality_warnings") or []:
        finding = upsert_critique_finding_object(
            board,
            workflow_id=resolved_workflow_id,
            material_type=str(plan.get("material_type") or ""),
            severity="P2",
            category="reference_quality",
            message=str(warning),
        )
        finding_ids.append(finding["id"])
        add_relation(
            board,
            relation_type="conflicts_with",
            from_id=finding["id"],
            to_id=direction["id"],
            workflow_id=resolved_workflow_id,
            data={"source": "plan"},
        )
    for error in role_pack.get("quality_errors") or []:
        finding = upsert_critique_finding_object(
            board,
            workflow_id=resolved_workflow_id,
            material_type=str(plan.get("material_type") or ""),
            severity="P1",
            category="reference_quality",
            message=str(error),
        )
        finding_ids.append(finding["id"])
        add_relation(
            board,
            relation_type="conflicts_with",
            from_id=finding["id"],
            to_id=direction["id"],
            workflow_id=resolved_workflow_id,
            data={"source": "plan"},
        )

    board_path = save_inspiration_board(brand_dir, board)
    selection = {
        "board_path": str(board_path),
        "direction_id": direction["id"],
        "selected_reference_ids": reference_ids,
        "constraint_ids": constraint_ids,
        "decision_ids": [decision["id"]],
        "critique_finding_ids": finding_ids,
        "workflow_id": resolved_workflow_id,
        "selection_mode": "role_pack",
    }
    plan["inspiration_board"] = selection
    plan["selected_reference_ids"] = list(reference_ids)
    return selection


def persist_inspiration_source_selection(
    brand_dir: Path,
    source_records: list[dict[str, Any]],
    *,
    workflow_id: str | None = None,
    direction_id: str | None = None,
) -> tuple[list[str], str]:
    board = load_inspiration_board(brand_dir)
    source_ids: list[str] = []
    resolved_workflow_id = workflow_id or ""
    for item in source_records or []:
        source = upsert_inspiration_source_object(board, item, workflow_id=resolved_workflow_id or None)
        source_ids.append(source["id"])
        if direction_id:
            add_relation(
                board,
                relation_type="supports",
                from_id=source["id"],
                to_id=direction_id,
                workflow_id=resolved_workflow_id or None,
                data={"selection_mode": "configured_inspiration"},
            )
    board_path = save_inspiration_board(brand_dir, board)
    return source_ids, str(board_path)


__all__ = [
    "INSPIRATION_BOARD_FILENAME",
    "INSPIRATION_BOARD_SCHEMA_VERSION",
    "add_relation",
    "build_inspiration_board_summary",
    "inspiration_board_path",
    "load_inspiration_board",
    "persist_plan_inspiration_board",
    "persist_inspiration_source_selection",
    "save_inspiration_board",
    "upsert_object",
]
