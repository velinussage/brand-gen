from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from .runtime_io import load_json_file
from .verdict import (
    Verdict,
    coerce_verdicts,
    legacy_verdict_from_entry,
    reconcile_verdicts,
    verdict_from_user_feedback,
)

DEFAULT_ITERATION_MEMORY = {
    "version": 1,
    "brand_notes": [],
    "positive_examples": [],
    "negative_examples": [],
    "copy_notes": [],
    "messaging_notes": [],
    "material_notes": {},
    "last_style_anchor_by_material": {},
    "recent_style_anchors_by_material": {},
    "recent_archetypes_by_material": {},
    "recent_sage_framings_by_material": {},
}

def iteration_memory_paths(brand_dir: Path) -> tuple[Path, Path]:
    return brand_dir / "iteration-memory.json", brand_dir / "iteration-memory.md"


def normalize_iteration_memory(payload: dict | None) -> dict:
    out = dict(DEFAULT_ITERATION_MEMORY)
    if isinstance(payload, dict):
        out.update(payload)
    out["brand_notes"] = list(out.get("brand_notes") or [])
    out["positive_examples"] = list(out.get("positive_examples") or [])
    out["negative_examples"] = list(out.get("negative_examples") or [])
    out["copy_notes"] = list(out.get("copy_notes") or [])
    out["messaging_notes"] = list(out.get("messaging_notes") or [])
    out["material_notes"] = dict(out.get("material_notes") or {})
    out["last_style_anchor_by_material"] = dict(out.get("last_style_anchor_by_material") or {})
    out["recent_style_anchors_by_material"] = {
        k: list(v) for k, v in (out.get("recent_style_anchors_by_material") or {}).items()
    }
    out["recent_archetypes_by_material"] = {
        k: list(v) for k, v in (out.get("recent_archetypes_by_material") or {}).items()
    }
    out["recent_sage_framings_by_material"] = {
        k: list(v) for k, v in (out.get("recent_sage_framings_by_material") or {}).items()
    }
    out["positive_examples"] = [_normalize_feedback_record(item) for item in out["positive_examples"] if isinstance(item, dict)]
    out["negative_examples"] = [_normalize_feedback_record(item) for item in out["negative_examples"] if isinstance(item, dict)]
    return out


def _normalize_feedback_record(item: dict[str, Any]) -> dict[str, Any]:
    record = dict(item or {})
    verdicts = coerce_verdicts(record.get("verdicts") or [])
    if not verdicts:
        verdicts = [legacy_verdict_from_entry(str(record.get("version") or ""), record)]
    reconciliation = reconcile_verdicts(verdicts)
    record["verdicts"] = reconciliation["verdicts"]
    record.setdefault("primary_decision", reconciliation["primary_decision"])
    record.setdefault("primary_gate", reconciliation["primary_gate"])
    record.setdefault("verdict_conflict", reconciliation["verdict_conflict"])
    record.setdefault("conflict_summary", reconciliation["conflict_summary"])
    if "decision" not in record and reconciliation["primary_decision"]:
        record["decision"] = reconciliation["primary_decision"]
    return record


def pick_rotating_style_anchor(
    policy: dict,
    memory: dict,
    *,
    material_type: str | None = None,
) -> str | None:
    """Pick a style anchor from a `rotating_anchor_set` policy that differs
    from the recent anchors used for this material type.

    The helper uses a rotation window of size N-1 (N = number of anchors in
    the policy) so the planner cycles through the full set before any
    anchor repeats. This prevents the v094-v096 failure cluster where
    "same aesthetic thrice" triggers user rejection.

    Returns the chosen anchor version, or None when the policy is malformed.
    Updates are written by `record_style_anchor_choice` — this helper is
    read-only so plan-building can stay pure.
    """
    if not isinstance(policy, dict):
        return None
    anchors = policy.get("required_style_reference_versions") or []
    if not anchors:
        return None
    if policy.get("reference_policy") != "rotating_anchor_set":
        return anchors[0]
    mt = material_type or policy.get("material_type") or ""
    recent = list((memory.get("recent_style_anchors_by_material") or {}).get(mt) or [])
    # legacy single-field fallback so older iteration memories still rotate
    if not recent:
        last = (memory.get("last_style_anchor_by_material") or {}).get(mt)
        if last:
            recent = [last]
    candidates = [a for a in anchors if a not in recent]
    if not candidates:
        candidates = list(anchors)
    return candidates[0]


def record_style_anchor_choice(
    memory: dict,
    *,
    material_type: str,
    anchor_version: str,
    anchor_set_size: int | None = None,
) -> dict:
    """Persist the chosen style anchor so the next run's rotation picks a
    different one. Callers must `save_iteration_memory` after.

    `anchor_set_size` determines the rotation-window length — pass the
    number of anchors in the policy so the window size stays N-1 and the
    helper cycles through the full set before repeating.
    """
    memory = normalize_iteration_memory(memory)
    memory["last_style_anchor_by_material"][material_type] = anchor_version
    history = list(memory["recent_style_anchors_by_material"].get(material_type) or [])
    history = [h for h in history if h != anchor_version]
    history.append(anchor_version)
    window = max((anchor_set_size or len(history)) - 1, 1)
    memory["recent_style_anchors_by_material"][material_type] = history[-window:]
    return memory


def record_sage_framing_choice(
    memory: dict,
    *,
    material_type: str,
    framing_id: str,
    framing_set_size: int | None = None,
) -> dict:
    """Persist Sage product-framing choices so planning rotates the visible
    metaphor/structure instead of fossilizing on one default.
    """
    memory = normalize_iteration_memory(memory)
    material_key = str(material_type or "").strip().lower().replace("_", "-")
    framing_id = str(framing_id or "").strip()
    if not material_key or not framing_id:
        return memory
    history = [h for h in list(memory["recent_sage_framings_by_material"].get(material_key) or []) if h != framing_id]
    history.append(framing_id)
    window = max((framing_set_size or len(history)) - 1, 1)
    memory["recent_sage_framings_by_material"][material_key] = history[-window:]
    return memory


def load_iteration_memory(brand_dir: Path) -> dict:
    json_path, _ = iteration_memory_paths(brand_dir)
    if not json_path.exists():
        return dict(DEFAULT_ITERATION_MEMORY)
    return normalize_iteration_memory(load_json_file(json_path))


def render_iteration_memory_markdown(payload: dict) -> str:
    lines = ["# Iteration memory", ""]
    if payload.get("brand_notes"):
        lines += ["## Brand notes"] + [f"- {item}" for item in payload["brand_notes"]] + [""]
    if payload.get("messaging_notes"):
        lines += ["## Messaging notes"] + [f"- {item}" for item in payload["messaging_notes"]] + [""]
    if payload.get("copy_notes"):
        lines += ["## Copy notes"] + [f"- {item}" for item in payload["copy_notes"]] + [""]
    if payload.get("negative_examples"):
        lines += ["## Negative examples"]
        for item in payload["negative_examples"][-12:]:
            lines.append(f"- {item.get('version','note')}: {item.get('material_type','')} — {item.get('summary','')}")
        lines.append("")
    if payload.get("positive_examples"):
        lines += ["## Positive examples"]
        for item in payload["positive_examples"][-12:]:
            lines.append(f"- {item.get('version','note')}: {item.get('material_type','')} — {item.get('summary','')}")
        lines.append("")
    material_notes = payload.get("material_notes") or {}
    if material_notes:
        lines += ["## Material-specific notes"]
        for key, items in material_notes.items():
            lines.append(f"### {key}")
            for item in items[-8:]:
                lines.append(f"- {item}")
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def save_iteration_memory(brand_dir: Path, payload: dict) -> tuple[Path, Path]:
    json_path, md_path = iteration_memory_paths(brand_dir)
    normalized = normalize_iteration_memory(payload)
    json_path.write_text(json.dumps(normalized, indent=2) + "\n")
    md_path.write_text(render_iteration_memory_markdown(normalized))
    return json_path, md_path


def add_iteration_note(memory: dict, note: str, *, material_type: str | None = None, bucket: str = "brand_notes", role_pack_material_key_fn: Callable[[str | None], str | None] | None = None) -> dict:
    if not note.strip():
        return memory
    memory = normalize_iteration_memory(memory)
    if bucket == "material":
        key = (role_pack_material_key_fn(material_type) if role_pack_material_key_fn else None) or (material_type or "general")
        memory["material_notes"].setdefault(key, [])
        if note not in memory["material_notes"][key]:
            memory["material_notes"][key].append(note)
        return memory
    if note not in memory.get(bucket, []):
        memory[bucket].append(note)
    return memory


def capture_feedback_into_iteration_memory(
    memory: dict,
    version: str,
    entry: dict,
    notes: str | None,
    score: int | None,
    status: str | None,
    *,
    decision: str | None = None,
    rejection_reason: str | None = None,
    verdicts: list[Verdict | dict[str, Any]] | None = None,
    branch_id: str | None = None,
    role_pack_material_key_fn: Callable[[str | None], str | None] | None = None,
) -> dict:
    memory = normalize_iteration_memory(memory)
    if role_pack_material_key_fn is None:
        from .runtime_models import role_pack_material_key

        role_pack_material_key_fn = role_pack_material_key
    material_type = entry.get("material_type") or ""
    summary = (notes or "").strip() or "Feedback recorded."
    resolved_decision = str(decision or entry.get("decision") or "").strip()
    resolved_rejection_reason = str(rejection_reason or entry.get("rejection_reason") or "").strip()
    incoming_verdicts = coerce_verdicts(verdicts or [])
    if not incoming_verdicts and (score is not None or status or resolved_decision):
        incoming_verdicts = [
            verdict_from_user_feedback(
                version_id=version,
                score=score,
                decision=resolved_decision,
                status=status,
                rationale=resolved_rejection_reason or summary,
                payload={"status": status or "", "notes": notes or ""},
            )
        ]
    # Preserve earlier gate verdicts for this same version so critic and VLM
    # paths can converge into one memory entry even though they run separately.
    prior_verdicts: list[Verdict] = []
    for bucket in ("positive_examples", "negative_examples"):
        for item in memory.get(bucket, []) or []:
            if isinstance(item, dict) and item.get("version") == version:
                prior_verdicts.extend(coerce_verdicts(item.get("verdicts") or []))
    merged_by_gate: dict[str, Verdict] = {}
    for verdict in prior_verdicts + incoming_verdicts:
        merged_by_gate[verdict.gate] = verdict
    reconciliation = reconcile_verdicts(list(merged_by_gate.values()))
    primary_decision = reconciliation["primary_decision"] or resolved_decision
    primary_score = reconciliation["primary_score"] if reconciliation["primary_score"] is not None else score
    record = {
        "version": version,
        "material_type": material_type,
        "summary": summary,
        "score": primary_score if primary_score is not None else score,
        "status": status or "",
        "decision": primary_decision or "",
        "primary_decision": primary_decision or "",
        "primary_gate": reconciliation["primary_gate"],
        "verdicts": reconciliation["verdicts"],
        "verdict_conflict": bool(reconciliation["verdict_conflict"]),
        "conflict_summary": reconciliation["conflict_summary"],
        "branch_id": branch_id or entry.get("branch_id") or "",
    }
    if resolved_rejection_reason:
        record["rejection_reason"] = resolved_rejection_reason
    target_bucket = None
    if primary_decision == "approve" or status == "favorite" or (primary_score is not None and primary_score >= 4):
        target_bucket = "positive_examples"
    elif primary_decision in {"reject", "iterate"} or status == "rejected" or (primary_score is not None and primary_score <= 2):
        target_bucket = "negative_examples"
    if target_bucket:
        # Remove stale copies from both buckets before appending the reconciled
        # entry.  This prevents a version from being both positive and negative
        # after separate gates report conflicting results.
        for bucket in ("positive_examples", "negative_examples"):
            memory[bucket] = [item for item in (memory.get(bucket) or []) if not (isinstance(item, dict) and item.get("version") == version)]
        existing = memory.get(target_bucket, [])
        existing.append(record)
        memory[target_bucket] = existing[-20:]
    if notes and notes.strip():
        memory = add_iteration_note(
            memory,
            notes.strip(),
            material_type=material_type,
            bucket="material",
            role_pack_material_key_fn=role_pack_material_key_fn,
        )
    return memory


def build_iteration_memory_snippet(
    brand_dir: Path,
    material_type: str | None,
    *,
    role_pack_material_key_fn: Callable[[str | None], str | None] | None = None,
    interface_material_keys: set[str] | None = None,
) -> str:
    if role_pack_material_key_fn is None or interface_material_keys is None:
        from .runtime_models import INTERFACE_MATERIAL_KEYS, role_pack_material_key

        role_pack_material_key_fn = role_pack_material_key_fn or role_pack_material_key
        interface_material_keys = interface_material_keys or INTERFACE_MATERIAL_KEYS
    memory = load_iteration_memory(brand_dir)
    lines: list[str] = []
    key = role_pack_material_key_fn(material_type) or (material_type or "")
    brand_notes = memory.get("brand_notes") or []
    messaging_notes = memory.get("messaging_notes") or []
    copy_notes = memory.get("copy_notes") or []
    material_notes = (memory.get("material_notes") or {}).get(key, [])
    negative = memory.get("negative_examples") or []
    if brand_notes:
        lines.append("Recent brand memory:")
        for item in brand_notes[-2:]:
            lines.append(f"- {item}")
    if messaging_notes and (key in interface_material_keys or key in {"social", "campaign_poster", "merch_poster", "landing_hero", "podcast_cover", "podcast_banner", "content_card", "editorial_card", "data_card", "quote_card", "announcement_card", "process_card"}):
        lines.append("Recent messaging notes:")
        for item in messaging_notes[-3:]:
            lines.append(f"- {item}")
    if material_notes:
        lines.append("Recent material-specific notes:")
        for item in material_notes[-3:]:
            lines.append(f"- {item}")
    if copy_notes and (key in interface_material_keys or key in {"social", "campaign_poster", "merch_poster", "podcast_cover", "podcast_banner", "content_card", "editorial_card", "data_card", "quote_card", "announcement_card", "process_card"}):
        lines.append("Recent copy notes:")
        for item in copy_notes[-2:]:
            lines.append(f"- {item}")
    if negative:
        new_schema_count = sum(1 for item in negative if isinstance(item, dict) and item.get("verdicts"))
        recent_negative = [
            item
            for item in reversed(negative)
            if (not key or role_pack_material_key_fn(item.get("material_type")) == key)
            and (new_schema_count < 3 or item.get("primary_decision") != "approve")
        ]
        if recent_negative:
            lines.append("Recent misses to avoid:")
            for item in recent_negative[:2]:
                prefix = ""
                if item.get("primary_gate"):
                    prefix = f"[{item.get('primary_gate')}:{item.get('primary_decision')}] "
                conflict = f" ({item.get('conflict_summary')})" if item.get("verdict_conflict") and item.get("conflict_summary") else ""
                lines.append(f"- {prefix}{item.get('summary')}{conflict}")
    return "\n".join(lines).strip()
