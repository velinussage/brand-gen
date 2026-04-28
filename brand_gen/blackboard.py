from __future__ import annotations

import json
import os
import time
import uuid
from collections import Counter
from pathlib import Path
from typing import Callable

from .runtime_io import warn

MAX_BLACKBOARD_FEEDBACK_ITEMS = 8
MAX_BLACKBOARD_LEARNING_ITEMS = 4
MAX_BLACKBOARD_RECIPE_ITEMS = 3
MAX_BLACKBOARD_EVIDENCE_VERSIONS = 6

DEFAULT_BLACKBOARD = {
    "schema_type": "brand_blackboard",
    "schema_version": 2,
    "brand_dna": {},
    "reference_analysis": {},
    "active_brief": {},
    "decisions": [],
    "iteration_history": {},
    "reference_assignments": {},
    "generated_assets": [],
    "learning_summary": {},
    "feedback_rollups": {},
    "material_recipes": {},
    "artifacts": {
        "latest_plan_draft": "",
        "latest_plan_critique": "",
        "latest_generation_scratchpad": "",
        "latest_generated_version": "",
        "latest_auto_review": "",
        "latest_agent_review_packet": "",
    },
}


def blackboard_path(brand_dir: Path) -> Path:
    return brand_dir / "blackboard.json"


def _now_timestamp() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def _dedupe_strings(items: list[str], *, limit: int) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        text = " ".join(str(item or "").strip().split())
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(text)
        if len(out) >= limit:
            break
    return out


def _short_signal(value: str | None, *, max_chars: int = 160) -> str:
    text = " ".join(str(value or "").strip().split()).strip(" -•\n\t")
    if not text:
        return ""
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1].rstrip() + "…"


def _top_counter_values(counter: Counter[str], *, limit: int) -> list[str]:
    ranked = sorted(counter.items(), key=lambda item: (-item[1], item[0].lower()))
    return [item for item, _ in ranked[:limit]]


def _normalize_material_key(material_type: str | None) -> str:
    from .runtime_models import role_pack_material_key

    return role_pack_material_key(material_type) or str(material_type or "general").strip().replace("-", "_") or "general"


def _empty_learning_bucket(material_key: str) -> dict:
    return {
        "material_key": material_key,
        "avoid": [],
        "prefer": [],
        "failure_patterns": [],
        "success_patterns": [],
        "route_bias": "",
        "model_bias": [],
        "reference_bias": [],
        "evidence_versions": [],
        "recent_low_score_count": 0,
        "recent_positive_signal_count": 0,
        "last_updated": "",
    }


def _empty_feedback_rollup(material_key: str) -> dict:
    return {
        "material_key": material_key,
        "recent_feedback": [],
        "recent_low_score_count": 0,
        "recent_positive_signal_count": 0,
        "last_updated": "",
    }


def _empty_recipe_bucket(material_key: str) -> dict:
    return {
        "material_key": material_key,
        "recipes": [],
        "last_updated": "",
    }


def _normalize_blackboard(board: dict | None) -> dict:
    out = dict(DEFAULT_BLACKBOARD)
    if isinstance(board, dict):
        out.update(board)
    out["brand_dna"] = dict(out.get("brand_dna") or {})
    out["reference_analysis"] = dict(out.get("reference_analysis") or {})
    out["active_brief"] = dict(out.get("active_brief") or {})
    out["decisions"] = list(out.get("decisions") or [])
    out["iteration_history"] = dict(out.get("iteration_history") or {})
    out["reference_assignments"] = dict(out.get("reference_assignments") or {})
    out["generated_assets"] = list(out.get("generated_assets") or [])
    out["artifacts"] = dict(DEFAULT_BLACKBOARD["artifacts"])
    out["artifacts"].update(dict((board or {}).get("artifacts") or {}))
    out["learning_summary"] = dict(out.get("learning_summary") or {})
    out["feedback_rollups"] = dict(out.get("feedback_rollups") or {})
    out["material_recipes"] = dict(out.get("material_recipes") or {})
    return out


def _prepare_mutable_blackboard(board: dict | None) -> dict:
    normalized = _normalize_blackboard(board)
    if isinstance(board, dict):
        board.clear()
        board.update(normalized)
        return board
    return normalized


def summarize_iteration_memory_for_blackboard(memory: dict) -> dict:
    return {
        "brand_notes": (memory.get("brand_notes") or [])[-5:],
        "copy_notes": (memory.get("copy_notes") or [])[-5:],
        "negative_examples": (memory.get("negative_examples") or [])[-5:],
        "positive_examples": (memory.get("positive_examples") or [])[-5:],
        "material_notes": memory.get("material_notes") or {},
    }


def append_blackboard_decision(
    board: dict,
    *,
    agent: str,
    decision: str,
    confidence: float | None = None,
    severity: str | None = None,
    data: dict | None = None,
    workflow_id: str | None = None,
) -> dict:
    board = _prepare_mutable_blackboard(board)
    decisions = board.setdefault("decisions", [])
    item = {
        "timestamp": _now_timestamp(),
        "agent": agent,
        "decision": decision,
    }
    if workflow_id:
        item["workflow_id"] = workflow_id
    if confidence is not None:
        item["confidence"] = confidence
    if severity:
        item["severity"] = severity
    if data:
        item["data"] = data
    decisions.append(item)
    board["decisions"] = decisions[-40:]
    return board


def _feedback_key(item: dict) -> str:
    return f"{item.get('version') or ''}:{item.get('source') or ''}"


def _feedback_version_key(item: dict) -> str:
    version = str(item.get("version") or "").strip()
    if version:
        return version
    return _feedback_key(item)


def _is_positive_feedback(item: dict) -> bool:
    status = str(item.get("status") or "").strip().lower()
    score = item.get("score")
    critique = item.get("critique") or {}
    approved = critique.get("approved")
    if status == "favorite":
        return True
    if isinstance(score, (int, float)) and score >= 4:
        return True
    if approved is True and not (critique.get("p1") or []):
        return True
    return False


def _is_negative_feedback(item: dict) -> bool:
    status = str(item.get("status") or "").strip().lower()
    score = item.get("score")
    critique = item.get("critique") or {}
    approved = critique.get("approved")
    if status == "rejected":
        return True
    if isinstance(score, (int, float)) and score <= 2:
        return True
    if approved is False:
        return True
    if critique.get("p1"):
        return True
    return False


def extract_feedback_patterns(item: dict) -> dict:
    critique = item.get("critique") or {}
    avoid: list[str] = []
    prefer: list[str] = []
    failure_patterns: list[str] = []
    success_patterns: list[str] = []

    note = _short_signal(item.get("notes") or "")
    refinement = _short_signal(critique.get("refinement_suggestion") or "")
    p1 = [_short_signal(entry) for entry in (critique.get("p1") or [])]
    p2 = [_short_signal(entry) for entry in (critique.get("p2") or [])]
    clean = [_short_signal(entry) for entry in (critique.get("clean") or [])]

    if _is_negative_feedback(item):
        if note:
            avoid.append(note)
            failure_patterns.append(note)
        avoid.extend(p1[:2])
        failure_patterns.extend(p1[:2])
        failure_patterns.extend(p2[:2])
        if refinement:
            prefer.append(refinement)
    if _is_positive_feedback(item):
        if note:
            prefer.append(note)
            success_patterns.append(note)
        prefer.extend(clean[:2])
        success_patterns.extend(clean[:3])
        if refinement:
            prefer.append(refinement)

    return {
        "avoid": _dedupe_strings(avoid, limit=3),
        "prefer": _dedupe_strings(prefer, limit=3),
        "failure_patterns": _dedupe_strings(failure_patterns, limit=3),
        "success_patterns": _dedupe_strings(success_patterns, limit=3),
    }


def _build_model_bias(feedback_items: list[dict]) -> list[str]:
    stats: dict[str, dict[str, int]] = {}
    for item in feedback_items:
        model = str(item.get("model") or "").strip()
        if not model:
            continue
        bucket = stats.setdefault(model, {"positive": 0, "negative": 0})
        if _is_positive_feedback(item):
            bucket["positive"] += 1
        if _is_negative_feedback(item):
            bucket["negative"] += 1
    lines: list[str] = []
    for model, bucket in sorted(stats.items(), key=lambda item: (-(item[1]["positive"] + item[1]["negative"]), item[0])):
        if bucket["negative"] >= 2 and bucket["negative"] > bucket["positive"]:
            lines.append(f"Recent misses cluster on {model}.")
        elif bucket["positive"] >= 2 and bucket["positive"] >= bucket["negative"]:
            lines.append(f"Recent wins cluster on {model}.")
    return lines[:2]


def _build_reference_bias(feedback_items: list[dict]) -> list[str]:
    positive_with_refs = sum(1 for item in feedback_items if item.get("has_reference_images") and _is_positive_feedback(item))
    negative_without_refs = sum(1 for item in feedback_items if not item.get("has_reference_images") and _is_negative_feedback(item))
    source_versions = _dedupe_strings(
        [
            f"Rejected source version {item.get('source_version')} should not drive the next derive/mockup pass."
            for item in feedback_items
            if _is_negative_feedback(item) and str(item.get("source_version") or "").strip()
        ],
        limit=2,
    )
    notes: list[str] = []
    if positive_with_refs >= 2:
        notes.append("Reference-backed runs are outperforming unreferenced runs recently.")
    if negative_without_refs >= 2:
        notes.append("Recent misses cluster when generating without references.")
    notes.extend(source_versions)
    return notes[:2]


def _build_route_bias(feedback_items: list[dict]) -> str:
    stats: dict[str, dict[str, int]] = {}
    for item in feedback_items:
        mode = str(item.get("mode") or "").strip()
        if not mode:
            continue
        bucket = stats.setdefault(mode, {"positive": 0, "negative": 0})
        if _is_positive_feedback(item):
            bucket["positive"] += 1
        if _is_negative_feedback(item):
            bucket["negative"] += 1
    ranked = sorted(stats.items(), key=lambda item: (-(item[1]["positive"] + item[1]["negative"]), item[0]))
    for mode, bucket in ranked:
        if bucket["negative"] >= 2 and bucket["negative"] > bucket["positive"]:
            return f"Recent misses cluster in {mode} mode."
        if bucket["positive"] >= 2 and bucket["positive"] >= bucket["negative"]:
            return f"Recent wins cluster in {mode} mode."
    return ""


def summarize_feedback_for_blackboard(rollup_or_feedback: dict | list[dict] | None) -> dict:
    if isinstance(rollup_or_feedback, dict):
        material_key = str(rollup_or_feedback.get("material_key") or "general")
        feedback_items = list(rollup_or_feedback.get("recent_feedback") or [])
        last_updated = str(rollup_or_feedback.get("last_updated") or "")
    else:
        material_key = "general"
        feedback_items = list(rollup_or_feedback or [])
        last_updated = ""
    summary = _empty_learning_bucket(material_key)
    summary["last_updated"] = last_updated
    if not feedback_items:
        return summary

    avoid_counter: Counter[str] = Counter()
    prefer_counter: Counter[str] = Counter()
    failure_counter: Counter[str] = Counter()
    success_counter: Counter[str] = Counter()
    evidence_versions = _dedupe_strings(
        [str(item.get("version") or "").strip() for item in reversed(feedback_items)],
        limit=MAX_BLACKBOARD_EVIDENCE_VERSIONS,
    )

    for item in feedback_items:
        signals = item.get("signals") or extract_feedback_patterns(item)
        for phrase in signals.get("avoid") or []:
            avoid_counter[phrase] += 1
        for phrase in signals.get("prefer") or []:
            prefer_counter[phrase] += 1
        for phrase in signals.get("failure_patterns") or []:
            failure_counter[phrase] += 1
        for phrase in signals.get("success_patterns") or []:
            success_counter[phrase] += 1

    summary["avoid"] = _top_counter_values(avoid_counter, limit=MAX_BLACKBOARD_LEARNING_ITEMS)
    summary["prefer"] = _top_counter_values(prefer_counter, limit=MAX_BLACKBOARD_LEARNING_ITEMS)
    summary["failure_patterns"] = _top_counter_values(failure_counter, limit=MAX_BLACKBOARD_LEARNING_ITEMS)
    summary["success_patterns"] = _top_counter_values(success_counter, limit=MAX_BLACKBOARD_LEARNING_ITEMS)
    summary["route_bias"] = _build_route_bias(feedback_items)
    summary["model_bias"] = _build_model_bias(feedback_items)
    summary["reference_bias"] = _build_reference_bias(feedback_items)
    summary["evidence_versions"] = evidence_versions
    summary["recent_low_score_count"] = sum(1 for item in feedback_items if _is_negative_feedback(item))
    summary["recent_positive_signal_count"] = sum(1 for item in feedback_items if _is_positive_feedback(item))
    return summary


def _recipe_label(item: dict) -> str:
    bits = [str(item.get("mode") or "").strip(), str(item.get("model") or "").strip()]
    bits = [bit for bit in bits if bit]
    bits.append("with refs" if item.get("has_reference_images") else "without refs")
    return " + ".join(bits)


def _build_material_recipes(rollup_or_feedback: dict | list[dict] | None) -> list[dict]:
    feedback_items = (
        list((rollup_or_feedback or {}).get("recent_feedback") or [])
        if isinstance(rollup_or_feedback, dict)
        else list(rollup_or_feedback or [])
    )
    recipe_stats: dict[str, dict] = {}
    for item in feedback_items:
        if not _is_positive_feedback(item):
            continue
        label = _recipe_label(item)
        if not label:
            continue
        bucket = recipe_stats.setdefault(label, {"count": 0, "evidence_versions": [], "hints": []})
        bucket["count"] += 1
        version = str(item.get("version") or "").strip()
        if version and version not in bucket["evidence_versions"]:
            bucket["evidence_versions"].append(version)
        signals = item.get("signals") or extract_feedback_patterns(item)
        for hint in signals.get("prefer") or []:
            if hint and hint not in bucket["hints"]:
                bucket["hints"].append(hint)
    recipes: list[dict] = []
    for label, bucket in sorted(recipe_stats.items(), key=lambda item: (-item[1]["count"], item[0].lower())):
        if bucket["count"] < 2:
            continue
        recipes.append(
            {
                "label": label,
                "count": bucket["count"],
                "hint": next(iter(bucket["hints"]), ""),
                "evidence_versions": bucket["evidence_versions"][:MAX_BLACKBOARD_EVIDENCE_VERSIONS],
            }
        )
    return recipes[:MAX_BLACKBOARD_RECIPE_ITEMS]


def update_blackboard_learning_summary(
    board: dict,
    *,
    material_type: str | None,
    version_id: str,
    entry: dict,
    source: str,
    notes: str = "",
    score: int | None = None,
    status: str = "",
    critique: dict | None = None,
) -> dict:
    board = _prepare_mutable_blackboard(board)
    material_key = _normalize_material_key(material_type or entry.get("material_type"))
    rollups = board.setdefault("feedback_rollups", {})
    existing_rollup = dict(rollups.get(material_key) or _empty_feedback_rollup(material_key))
    existing_rollup["material_key"] = material_key
    recent_feedback = [dict(item) for item in (existing_rollup.get("recent_feedback") or []) if isinstance(item, dict)]

    critique_payload = {}
    if isinstance(critique, dict):
        critique_payload = {
            "approved": critique.get("approved"),
            "p1": list(critique.get("p1") or []),
            "p2": list(critique.get("p2") or []),
            "clean": list(critique.get("clean") or []),
            "refinement_suggestion": critique.get("refinement_suggestion") or "",
        }

    feedback_item = {
        "timestamp": _now_timestamp(),
        "version": version_id,
        "material_type": entry.get("material_type") or material_type or "",
        "material_key": material_key,
        "source": source,
        "score": entry.get("score") if score is None else score,
        "status": status or entry.get("status") or "",
        "notes": _short_signal(notes or entry.get("notes") or ""),
        "mode": entry.get("mode") or entry.get("generation_mode") or "",
        "model": entry.get("model") or "",
        "has_reference_images": bool(entry.get("reference_images") or entry.get("reference_count")),
        "source_version": entry.get("source_version") or "",
        "critique": critique_payload,
    }
    feedback_item["signals"] = extract_feedback_patterns(feedback_item)

    recent_feedback = [item for item in recent_feedback if _feedback_key(item) != _feedback_key(feedback_item)]
    recent_feedback.append(feedback_item)
    recent_feedback = recent_feedback[-MAX_BLACKBOARD_FEEDBACK_ITEMS:]
    existing_rollup["recent_feedback"] = recent_feedback
    existing_rollup["recent_low_score_count"] = sum(1 for item in recent_feedback if _is_negative_feedback(item))
    existing_rollup["recent_positive_signal_count"] = sum(1 for item in recent_feedback if _is_positive_feedback(item))
    existing_rollup["last_updated"] = feedback_item["timestamp"]
    rollups[material_key] = existing_rollup

    board.setdefault("learning_summary", {})[material_key] = summarize_feedback_for_blackboard(existing_rollup)
    board.setdefault("material_recipes", {})[material_key] = {
        "material_key": material_key,
        "recipes": _build_material_recipes(existing_rollup),
        "last_updated": feedback_item["timestamp"],
    }
    return board


def build_blackboard_learning_context(
    brand_dir: Path,
    material_type: str | None,
    *,
    board: dict | None = None,
) -> dict:
    board = _normalize_blackboard(board if board is not None else load_blackboard(brand_dir))
    material_key = _normalize_material_key(material_type)
    summary = dict(board.get("learning_summary", {}).get(material_key) or _empty_learning_bucket(material_key))
    rollup = dict(board.get("feedback_rollups", {}).get(material_key) or _empty_feedback_rollup(material_key))
    recipe_bucket = dict(board.get("material_recipes", {}).get(material_key) or _empty_recipe_bucket(material_key))
    warnings: list[str] = []
    if summary.get("route_bias"):
        warnings.append(str(summary["route_bias"]))
    warnings.extend(str(item) for item in (summary.get("model_bias") or [])[:1])
    warnings.extend(str(item) for item in (summary.get("reference_bias") or [])[:1])
    if summary.get("recent_low_score_count", 0) >= 2 and not (recipe_bucket.get("recipes") or []):
        warnings.append("Recent low scores are repeating without a stable winning recipe yet.")
    return {
        "material_key": material_key,
        "summary": summary,
        "rollup": rollup,
        "recipes": list(recipe_bucket.get("recipes") or []),
        "warnings": _dedupe_strings(warnings, limit=3),
    }


def _feedback_text_blob(items: list[dict], summary: dict | None = None) -> str:
    parts: list[str] = []
    for item in items[-MAX_BLACKBOARD_FEEDBACK_ITEMS:]:
        parts.extend(
            [
                str(item.get("notes") or ""),
                " ".join(str(signal) for signal in ((item.get("signals") or {}).get("avoid") or [])),
                " ".join(str(signal) for signal in ((item.get("signals") or {}).get("prefer") or [])),
                " ".join(str(signal) for signal in ((item.get("signals") or {}).get("failure_patterns") or [])),
                " ".join(str(signal) for signal in ((item.get("signals") or {}).get("success_patterns") or [])),
            ]
        )
    if summary:
        for key in ("avoid", "prefer", "failure_patterns", "success_patterns"):
            parts.extend(str(item) for item in (summary.get(key) or []))
    return " ".join(part for part in parts if part).lower()


def build_blackboard_feedback_directives(
    brand_dir: Path,
    material_type: str | None,
    *,
    board: dict | None = None,
) -> dict:
    """Convert recent human/critic feedback into prompt-facing directives.

    Blackboard summaries preserve raw notes, but planning needs normalized
    actions: simplify when users say "busy", force deterministic text when
    copy was hard to read, and distinguish material semantics such as a
    hero-side illustration versus a complete hero section.
    """
    context = build_blackboard_learning_context(brand_dir, material_type, board=board)
    summary = context.get("summary") or {}
    rollup = context.get("rollup") or {}
    feedback_items = [dict(item) for item in (rollup.get("recent_feedback") or []) if isinstance(item, dict)]
    material_key = str(context.get("material_key") or _normalize_material_key(material_type))
    raw_material_key = str(material_type or "").strip().lower().replace("-", "_")
    blob = _feedback_text_blob(feedback_items, summary)
    push: list[str] = []
    ban: list[str] = []
    warnings: list[str] = []
    visual_density_cap: int | None = None
    complexity_tier_hint = ""

    if any(token in blob for token in ("too busy", "pretty busy", "busy", "clutter", "cluttered", "too dense")):
        push.append(
            "Simplify hierarchy: one primary idea, one proof/illustration module, and at most two supporting elements with visible negative space."
        )
        ban.append("busy multi-card collage, dense micro-module swarm, crowded labels, or every-card-is-a-feature composition")
        warnings.append("Recent feedback says this material is too busy; reduce element count before adding style.")
        visual_density_cap = 4
        complexity_tier_hint = "simple"

    if any(token in blob for token in ("text is hard to read", "hard to read", "hard-to-read", "unreadable", "tiny text", "text clutter")):
        push.append(
            "Keep native image text minimal; route important labels, CLI/footer copy, stats, and proof copy through deterministic HTML/SVG/composite text."
        )
        ban.append("tiny native image text, pseudo-text, low-contrast labels, or text-heavy art generated by the image model")
        warnings.append("Recent feedback flagged poor text legibility; deterministic overlays should own readable copy.")

    if any(token in blob for token in ("don't like the colors", "do not like the colors", "colors are not working", "bad colors", "palette not working")):
        push.append(
            "Re-ground color in the approved brand palette with high-contrast cream/charcoal/terracotta/sage relationships before adding accents."
        )
        ban.append("off-brand palette drift, muddy color fields, low-contrast type/color pairings, or decorative colors not tied to brand tokens")
        warnings.append("Recent feedback disliked the color direction; palette fidelity and contrast are acceptance criteria.")

    if any(token in blob for token in ("hyper focuses", "hyper-focuses", "hyper focusing", "hyper-focusing", "specific feature", "one specific feature")):
        push.append(
            "Look at the brand/product from a fresh angle this pass; choose one clear Sage angle, but rotate across capability distribution, library trust, runtime adoption, creator incentives, and governance-as-substrate over multiple outputs."
        )
        ban.append("repeating the same single feature/mechanic as the whole Sage story across consecutive outputs")
        warnings.append("Recent feedback says the pipeline is over-focusing on one feature; broaden product-angle exploration.")

    if any(
        token in blob
        for token in (
            "copying the same style",
            "same style too closely",
            "stylistically repetitive",
            "switch up generation style",
            "not keep repeating the same terracotta/isometric/exchange-node look",
            "same high-reviewed reference style",
        )
    ):
        push.append(
            "Deliberately choose a visibly different art-direction branch this pass while preserving the same Sage product truth; vary medium, camera, texture, and composition rather than only swapping the metaphor."
        )
        ban.append(
            "repeating the dense terracotta/isometric/exchange-node or machine-routing look as the default style unless the user explicitly asks for that benchmark"
        )
        warnings.append(
            "Recent Sage feedback says v189-v191 were only 3/5 because the style repeated too closely; force a style shift before generation."
        )

    if (material_key == "website_hero_illustration" or raw_material_key == "website_hero_illustration") and any(token in blob for token in ("full hero section", "side illustration", "right or left side", "left side", "right side", "sidecar")):
        push.append(
            "Compose as a sidecar hero illustration for the left or right of separate hero text: symbolic product-grounded art, no headline block, no CTA, no full page layout."
        )
        ban.append("full hero section mockup, complete webpage layout, headline/subheadline/CTA inside the illustration, or fake page chrome")
        warnings.append("Website hero illustration feedback: generate the illustration side only, not the full hero section.")
        visual_density_cap = 4 if visual_density_cap is None else min(visual_density_cap, 4)
        complexity_tier_hint = "simple"

    if raw_material_key == "proof_poster" and any(token in blob for token in ("liked the illustration", "like the illustration", "poster craft", "proof-poster direction")):
        push.append(
            "Preserve the illustrated proof-poster craft, but make the next pass quieter: one hero illustration, one proof payload, one small brand mark."
        )
        ban.append("proof poster with many competing text blocks, footer strips, extra cards, or redundant proof rows")
        visual_density_cap = 5 if visual_density_cap is None else min(visual_density_cap, 5)
        if not complexity_tier_hint:
            complexity_tier_hint = "moderate"

    return {
        "material_key": material_key,
        "push": _dedupe_strings(push, limit=6),
        "ban": _dedupe_strings(ban, limit=6),
        "warnings": _dedupe_strings(warnings, limit=5),
        "visual_density_cap": visual_density_cap,
        "complexity_tier_hint": complexity_tier_hint,
    }


def build_blackboard_learning_snippet(
    brand_dir: Path,
    material_type: str | None,
    *,
    board: dict | None = None,
) -> str:
    from .runtime_models import INTERFACE_MATERIAL_KEYS

    context = build_blackboard_learning_context(brand_dir, material_type, board=board)
    summary = context.get("summary") or {}
    recipes = context.get("recipes") or []
    lines: list[str] = []
    if summary.get("avoid"):
        lines.append("Recent blackboard avoid rules:")
        for item in list(summary.get("avoid") or [])[:2]:
            lines.append(f"- {item}")
    if summary.get("prefer"):
        lines.append("Recent blackboard preferred setup:")
        for item in list(summary.get("prefer") or [])[:2]:
            lines.append(f"- {item}")
    if recipes:
        top_recipe = recipes[0]
        hint = str(top_recipe.get("hint") or "").strip()
        line = f"Recent good recipe: {top_recipe.get('label') or 'n/a'}"
        if hint:
            line += f" — {hint}"
        lines.append(line)
    directives = build_blackboard_feedback_directives(brand_dir, material_type, board=board)
    if directives.get("push") or directives.get("ban"):
        lines.append("Feedback directives:")
        for item in list(directives.get("push") or [])[:2]:
            lines.append(f"- Prefer: {item}")
        for item in list(directives.get("ban") or [])[:1]:
            lines.append(f"- Avoid: {item}")
    snippet = "\n".join(lines).strip()
    if not snippet:
        return ""
    material_key = context.get("material_key") or ""
    max_chars = 360 if material_key in INTERFACE_MATERIAL_KEYS else 700
    if len(snippet) <= max_chars:
        return snippet
    return snippet[: max_chars - 1].rstrip() + "…"


def get_blackboard_learning_warnings(
    brand_dir: Path,
    material_type: str | None,
    *,
    proposed_mode: str = "",
    has_reference_roles: bool = False,
    source_version: str = "",
    board: dict | None = None,
) -> list[str]:
    context = build_blackboard_learning_context(brand_dir, material_type, board=board)
    rollup = list((context.get("rollup") or {}).get("recent_feedback") or [])
    summary = context.get("summary") or {}
    warnings = list(context.get("warnings") or [])
    if proposed_mode and summary.get("recent_low_score_count", 0) >= 2:
        proposed_mode_key = proposed_mode.strip().lower()
        mode_stats = [
            item for item in rollup
            if str(item.get("mode") or "").strip().lower() == proposed_mode_key and _is_negative_feedback(item)
        ]
        negative_versions = {_feedback_version_key(item) for item in mode_stats if _feedback_version_key(item)}
        positive_versions = {
            _feedback_version_key(item)
            for item in rollup
            if str(item.get("mode") or "").strip().lower() == proposed_mode_key
            and _is_positive_feedback(item)
            and _feedback_version_key(item)
        }
        if len(negative_versions) >= 2 and not positive_versions:
            warnings.append(f"{proposed_mode} mode has been underperforming for this material recently.")
    if not has_reference_roles and any("without references" in str(item).lower() for item in (summary.get("reference_bias") or [])):
        warnings.append("Prefer a reference-backed setup for the next pass.")
    if source_version:
        source_rejections = [
            item for item in rollup
            if str(item.get("version") or "").strip() == source_version and _is_negative_feedback(item)
        ]
        if source_rejections:
            warnings.append(f"Source version {source_version} was recently rejected; avoid deriving directly from it.")
    return _dedupe_strings(warnings, limit=4)


def get_workflow_lineage(board: dict, workflow_id: str) -> dict:
    board = _normalize_blackboard(board)
    decisions = [item for item in (board.get("decisions") or []) if item.get("workflow_id") == workflow_id]
    assets = [item for item in (board.get("generated_assets") or []) if item.get("workflow_id") == workflow_id]
    return {"workflow_id": workflow_id, "decisions": decisions, "assets": assets}


def load_blackboard(
    brand_dir: Path,
    profile: dict | None = None,
    identity: dict | None = None,
    *,
    default_blackboard: dict | None = None,
    summarize_identity_fn: Callable[[dict, dict], dict] | None = None,
    load_iteration_memory_fn: Callable[[Path], dict] | None = None,
) -> dict:
    defaults = _normalize_blackboard(default_blackboard or DEFAULT_BLACKBOARD)
    path = blackboard_path(brand_dir)
    if path.exists():
        try:
            value = json.loads(path.read_text())
            board = _normalize_blackboard(value if isinstance(value, dict) else defaults)
        except (json.JSONDecodeError, OSError, UnicodeDecodeError) as exc:
            warn(f"Failed to load blackboard at {path}; using defaults. {exc}")
            board = dict(defaults)
    else:
        board = dict(defaults)
    if profile is not None and identity is not None and summarize_identity_fn is not None:
        board["brand_dna"] = summarize_identity_fn(profile, identity)
    if load_iteration_memory_fn is not None:
        board["iteration_history"] = summarize_iteration_memory_for_blackboard(load_iteration_memory_fn(brand_dir))
    return board


def save_blackboard(brand_dir: Path, board: dict, *, default_blackboard: dict | None = None) -> Path:
    path = blackboard_path(brand_dir)
    payload = _normalize_blackboard(default_blackboard or DEFAULT_BLACKBOARD)
    payload.update(_normalize_blackboard(board))
    payload["artifacts"] = dict(DEFAULT_BLACKBOARD["artifacts"])
    payload["artifacts"].update(dict((board or {}).get("artifacts") or {}))
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f"{path.name}.{uuid.uuid4().hex}.tmp")
    tmp_path.write_text(json.dumps(payload, indent=2) + "\n")
    os.replace(tmp_path, path)
    return path


def update_blackboard_active_brief(board: dict, plan: dict, *, stage: str, path: str = "", workflow_id: str = "", source_version: str = "") -> dict:
    board = _prepare_mutable_blackboard(board)
    role_pack = plan.get("role_pack") or {}
    board["active_brief"] = {
        "stage": stage,
        "material_type": plan.get("material_type") or "",
        "mode": plan.get("mode") or "",
        "purpose": plan.get("purpose") or "",
        "target_surface": plan.get("target_surface") or "",
        "product_truth_expression": plan.get("product_truth_expression") or "",
        "abstraction_level": plan.get("abstraction_level") or "",
        "system_mechanic": plan.get("system_mechanic") or "",
        "preserve": plan.get("preserve") or [],
        "push": plan.get("push") or [],
        "ban": plan.get("ban") or [],
        "prompt_seed": plan.get("prompt_seed") or "",
        "path": path,
        "branch_id": plan.get("branch_id") or workflow_id or "",
        "source_version": plan.get("source_version") or source_version or "",
        "branch_status": "active",
    }
    board["reference_assignments"] = {
        item.get("role") or "reference": {
            "source_key": item.get("source_key") or "",
            "source_name": item.get("source_name") or "",
            "path": item.get("path") or "",
            "translation": item.get("translation") or {},
        }
        for item in (role_pack.get("selected_roles") or [])
    }
    return board


def persist_plan_draft_to_blackboard(
    brand_dir: Path,
    profile: dict,
    identity: dict,
    draft: dict,
    *,
    output_path: Path,
    workflow_id: str | None = None,
    default_blackboard: dict | None = None,
    summarize_identity_fn: Callable[[dict, dict], dict] | None = None,
    load_iteration_memory_fn: Callable[[Path], dict] | None = None,
    extract_plan_payload_fn: Callable[[dict], dict] | None = None,
) -> Path:
    if summarize_identity_fn is None:
        from .material_planning import summarize_identity

        summarize_identity_fn = summarize_identity
    if load_iteration_memory_fn is None:
        from .iteration_memory import load_iteration_memory

        load_iteration_memory_fn = load_iteration_memory
    if extract_plan_payload_fn is None:
        from .material_planning import extract_plan_payload

        extract_plan_payload_fn = extract_plan_payload
    board = load_blackboard(
        brand_dir,
        profile,
        identity,
        default_blackboard=default_blackboard,
        summarize_identity_fn=summarize_identity_fn,
        load_iteration_memory_fn=load_iteration_memory_fn,
    )
    plan = extract_plan_payload_fn(draft)
    update_blackboard_active_brief(board, plan, stage="plan_draft", path=str(output_path))
    board["artifacts"]["latest_plan_draft"] = str(output_path)
    append_blackboard_decision(
        board,
        agent="brand_director",
        decision=f"Drafted {plan.get('material_type') or 'material'} brief with mechanic '{plan.get('system_mechanic') or 'n/a'}'.",
        confidence=0.72,
        data={"mode": plan.get("mode"), "missing_required_roles": ((draft.get("derived") or {}).get("missing_required_roles") or [])},
        workflow_id=workflow_id,
    )
    return save_blackboard(brand_dir, board, default_blackboard=default_blackboard)


def persist_plan_critique_to_blackboard(
    brand_dir: Path,
    profile: dict,
    identity: dict,
    critique: dict,
    *,
    output_path: Path,
    workflow_id: str | None = None,
    default_blackboard: dict | None = None,
    summarize_identity_fn: Callable[[dict, dict], dict] | None = None,
    load_iteration_memory_fn: Callable[[Path], dict] | None = None,
    extract_plan_payload_fn: Callable[[dict], dict] | None = None,
) -> Path:
    if summarize_identity_fn is None:
        from .material_planning import summarize_identity

        summarize_identity_fn = summarize_identity
    if load_iteration_memory_fn is None:
        from .iteration_memory import load_iteration_memory

        load_iteration_memory_fn = load_iteration_memory
    if extract_plan_payload_fn is None:
        from .material_planning import extract_plan_payload

        extract_plan_payload_fn = extract_plan_payload
    board = load_blackboard(
        brand_dir,
        profile,
        identity,
        default_blackboard=default_blackboard,
        summarize_identity_fn=summarize_identity_fn,
        load_iteration_memory_fn=load_iteration_memory_fn,
    )
    plan = extract_plan_payload_fn(critique.get("plan") or {})
    if plan:
        update_blackboard_active_brief(board, plan, stage="plan_critique", path=critique.get("plan_path") or "")
    board["artifacts"]["latest_plan_critique"] = str(output_path)
    blocking = ((critique.get("checks") or {}).get("blocking") or [])
    append_blackboard_decision(
        board,
        agent="critic_agent",
        decision=f"Critiqued {plan.get('material_type') or 'material'} plan: {'blocking issues remain' if blocking else 'ready for scratchpad build'}.",
        confidence=0.84 if not blocking else 0.9,
        severity="P1" if blocking else "P2",
        data={
            "blocking": blocking,
            "plan_errors": ((critique.get("plan_validation") or {}).get("errors") or []),
            "prompt_issues": ((critique.get("prompt_review") or {}).get("issues") or []),
            "learned_setup_warnings": list((critique.get("checks") or {}).get("warnings") or []),
        },
        workflow_id=workflow_id,
    )
    return save_blackboard(brand_dir, board, default_blackboard=default_blackboard)


def persist_generation_scratchpad_to_blackboard(
    brand_dir: Path,
    profile: dict,
    identity: dict,
    payload: dict,
    *,
    output_path: Path,
    workflow_id: str | None = None,
    default_blackboard: dict | None = None,
    summarize_identity_fn: Callable[[dict, dict], dict] | None = None,
    load_iteration_memory_fn: Callable[[Path], dict] | None = None,
) -> Path:
    if summarize_identity_fn is None:
        from .material_planning import summarize_identity

        summarize_identity_fn = summarize_identity
    if load_iteration_memory_fn is None:
        from .iteration_memory import load_iteration_memory

        load_iteration_memory_fn = load_iteration_memory
    board = load_blackboard(
        brand_dir,
        profile,
        identity,
        default_blackboard=default_blackboard,
        summarize_identity_fn=summarize_identity_fn,
        load_iteration_memory_fn=load_iteration_memory_fn,
    )
    plan = payload.get("plan") or {}
    if plan:
        update_blackboard_active_brief(board, plan, stage="generation_scratchpad", path=payload.get("plan_path") or "")
    board["artifacts"]["latest_generation_scratchpad"] = str(output_path)
    append_blackboard_decision(
        board,
        agent="visual_composer",
        decision=f"Built generation scratchpad for {payload.get('material_type') or 'material'} using {((payload.get('execution') or {}).get('model') or 'unknown model')}.",
        confidence=0.76,
        severity="P1" if ((payload.get("checks") or {}).get("blocking") or []) else "P3",
        data={
            "workflow_mode": payload.get("workflow_mode"),
            "blocking": ((payload.get("checks") or {}).get("blocking") or []),
            "warnings": ((payload.get("checks") or {}).get("warnings") or []),
            "learning_warnings": list((payload.get("plan") or {}).get("learned_setup_warnings") or []),
        },
        workflow_id=workflow_id,
    )
    return save_blackboard(brand_dir, board, default_blackboard=default_blackboard)


def persist_generated_asset_to_blackboard(
    brand_dir: Path,
    profile: dict,
    identity: dict,
    *,
    version_id: str,
    entry: dict,
    scratchpad_path: str,
    auto_review_path: str = "",
    agent_review_path: str = "",
    critic_summary: dict | None = None,
    workflow_id: str | None = None,
    default_blackboard: dict | None = None,
    summarize_identity_fn: Callable[[dict, dict], dict] | None = None,
    load_iteration_memory_fn: Callable[[Path], dict] | None = None,
) -> Path:
    if summarize_identity_fn is None:
        from .material_planning import summarize_identity

        summarize_identity_fn = summarize_identity
    if load_iteration_memory_fn is None:
        from .iteration_memory import load_iteration_memory

        load_iteration_memory_fn = load_iteration_memory
    board = load_blackboard(
        brand_dir,
        profile,
        identity,
        default_blackboard=default_blackboard,
        summarize_identity_fn=summarize_identity_fn,
        load_iteration_memory_fn=load_iteration_memory_fn,
    )
    board["artifacts"]["latest_generated_version"] = version_id
    if auto_review_path:
        board["artifacts"]["latest_auto_review"] = auto_review_path
    if agent_review_path:
        board["artifacts"]["latest_agent_review_packet"] = agent_review_path
    history = board.setdefault("generated_assets", [])
    history.append(
        {
            "timestamp": _now_timestamp(),
            "workflow_id": workflow_id or "",
            "version": version_id,
            "material_type": entry.get("material_type") or "",
            "files": entry.get("files") or [],
            "scratchpad_path": scratchpad_path,
            "auto_review_path": auto_review_path,
            "agent_review_path": agent_review_path,
            "critic_summary": critic_summary or {},
        }
    )
    board["generated_assets"] = history[-20:]
    append_blackboard_decision(
        board,
        agent="brand_director",
        decision=f"Generated {version_id} ({entry.get('material_type') or 'material'}) and queued critic review.",
        confidence=0.7,
        severity="P2" if (critic_summary or {}).get("p1") else "P3",
        data={"scratchpad_path": scratchpad_path, "auto_review_path": auto_review_path, "agent_review_path": agent_review_path},
        workflow_id=workflow_id,
    )
    return save_blackboard(brand_dir, board, default_blackboard=default_blackboard)
