"""Prompt building, review, execution prompt, and text utilities.

Assembles the full effective prompt from brand prelude, material snippet,
reference role pack, inspiration doctrine, iteration memory, and copy
anchors.  Also handles prompt review (architecture analysis) and the
compact execution prompt used at generation time.

Key functions:
    build_effective_prompt         — assemble the full prompt with all context
    review_prompt_architecture     — analyse prompt quality and produce refined/execution prompts
    build_execution_prompt         — build the compact execution prompt for image models
    resolve_material_prompt_snippet — resolve per-material prompt snippet from identity
    cap_text_at_sentence           — truncate text at sentence boundary
    compress_prompt_body           — prioritize and compact prompt body sentences
"""
from __future__ import annotations

import re
from pathlib import Path

from .blackboard import build_blackboard_learning_context, build_blackboard_learning_snippet
from .custom_scratchpad import build_custom_scratchpad_snippet
from .brand_policy import (
    get_base_brand_guardrail_prelude,
    load_inspiration_prompt_context,
    normalize_material_brand_policy,
)
from .reference_role_packs import (
    default_reference_translation,
    evaluate_policy_setup_risks,
    resolve_reference_role_pack,
    select_inspiration_sources,
    stable_mechanic_id,
)
from .runtime import *
from .runtime_brand import load_material_snippets, load_prompt_budget, load_prompt_fragments

__all__ = [
    # Prompt building
    "build_effective_prompt",
    "resolve_material_prompt_snippet",
    "fallback_material_prompt_snippet",
    # Prompt review
    "review_prompt_architecture",
    "evaluate_prompt_review_rules",
    "prompt_review_rule_matches",
    "material_group_for_prompt_review",
    # Execution prompt
    "build_execution_prompt",
    "compact_execution_material_policy",
    "compact_execution_brand_anchor",
    "compact_execution_copy_rule",
    "compact_execution_critical_bans",
    "compact_execution_reference_caveat",
    "compact_execution_selected_inspiration",
    "compact_role_pack_snippet",
    # Text utilities
    "split_prompt_sentences",
    "sentence_join",
    "first_sentence_matching_keywords",
    "cap_text_at_sentence",
    "compress_prompt_body",
    # Budget cap constants
    "NON_INTERFACE_PRELUDE_CAP",
    "NON_INTERFACE_DOCTRINE_CAP",
    "NON_INTERFACE_REF_ANALYSIS_CAP",
    "NON_INTERFACE_TOKEN_BLOCK_CAP",
    "NON_INTERFACE_TOTAL_PRELUDE_CAP",
]


# ── Material prompt snippets ─────────────────────────────────────────

def resolve_material_prompt_snippet(profile: dict, identity: dict, material_type: str | None, workflow_mode: str | None = None) -> tuple[str, str, str]:
    key = MATERIAL_PROMPT_SNIPPET_ALIASES.get((material_type or "").strip().lower(), "")
    if not key:
        return "", "", ""
    snippets = (
        (identity.get("generation_guardrails") or {}).get("material_prompt_snippets")
        or profile.get("material_prompt_snippets")
        or {}
    )
    if not isinstance(snippets, dict):
        return key, "", fallback_material_prompt_snippet(key, workflow_mode)
    value = snippets.get(key) or ""
    if isinstance(value, str):
        stripped = value.strip()
        return key, "default", stripped or fallback_material_prompt_snippet(key, workflow_mode)
    if not isinstance(value, dict):
        return key, "", fallback_material_prompt_snippet(key, workflow_mode)
    requested_mode = (workflow_mode or "").strip().lower()
    if requested_mode in {"reference", "inspiration", "hybrid"}:
        variant = requested_mode
    else:
        variant = "default"
    default_value = value.get("default") or ""
    variant_value = value.get(variant) or ""
    parts = [part.strip() for part in [default_value, variant_value if variant != "default" else ""] if isinstance(part, str) and part.strip()]
    combined = "\n\n".join(parts).strip()
    if combined:
        return key, variant, combined
    return key, variant, fallback_material_prompt_snippet(key, workflow_mode)


def fallback_material_prompt_snippet(material_key: str, workflow_mode: str | None = None) -> str:
    variant = (workflow_mode or "default").strip().lower()
    snippets = load_material_snippets().get("snippets", {})
    entry = snippets.get(material_key, {})
    if not entry:
        return ""
    if isinstance(entry, str):
        return entry
    if variant in {"reference", "inspiration", "hybrid"}:
        parts = [entry.get("default", ""), entry.get(variant, "")]
        return "\n\n".join(p for p in parts if p).strip()
    return entry.get("default", "").strip()


# ── Full prompt assembly ─────────────────────────────────────────────

def build_effective_prompt(
    profile: dict,
    identity: dict,
    body: str,
    *,
    brand_gen_dir: Path | None = None,
    active_brand: str | None = None,
    brand_dir: Path | None = None,
    material_type: str | None = None,
    workflow_mode: str | None = None,
    disable_brand_guardrails: bool = False,
    role_pack_override: dict | None = None,
    reference_analysis: dict | None = None,
    selected_inspiration_sources: list[dict] | None = None,
    selected_inspiration_ids: list[str] | None = None,
    selected_mechanic_ids: list[str] | None = None,
    selected_mechanic_labels: list[str] | None = None,
    inspiration_selection_reason: str | None = None,
    inspiration_selection_mode: str | None = None,
    render_backend: str | None = None,
    source_url: str | None = None,
    entity_type: str | None = None,
    selected_surface_strategy: str | None = None,
    aesthetic_archetype: dict | None = None,
    prompt_subject: str | None = None,
    prompt_style_descriptors: str | None = None,
    prompt_lighting: str | None = None,
    prompt_camera: str | None = None,
    prompt_composition: str | None = None,
    prompt_details: str | None = None,
    visual_density: int | str | None = None,
    aesthetic_commitment: str | None = None,
) -> dict:
    reference_analysis = reference_analysis or {}
    analysis_mode = reference_analysis_mode(reference_analysis)
    analysis_confidence = reference_analysis_confidence(reference_analysis)
    brand_policy = normalize_material_brand_policy(material_type, identity=identity)
    brand_prelude = "" if disable_brand_guardrails else get_base_brand_guardrail_prelude(profile, identity, material_type)
    material_key, material_variant, material_snippet = ("", "", "") if disable_brand_guardrails else resolve_material_prompt_snippet(profile, identity, material_type, workflow_mode)
    iteration_memory_snippet = "" if disable_brand_guardrails or not brand_dir else build_iteration_memory_snippet(brand_dir, material_type)
    custom_scratchpad_snippet = "" if disable_brand_guardrails or not brand_dir else build_custom_scratchpad_snippet(brand_dir, material_type)
    if role_pack_override is not None:
        role_pack = role_pack_override
    elif brand_dir and not disable_brand_guardrails:
        role_pack = resolve_reference_role_pack(brand_dir, material_type)
    else:
        role_pack = {"snippet": "", "roles": [], "paths": [], "motion_paths": [], "missing_roles": [], "required_roles": [], "missing_required_roles": [], "priority": [], "prefer_unique_sources": True, "material_key": ""}
    role_pack_snippet = role_pack.get("snippet", "")
    reference_analysis_snippet = (
        ""
        if disable_brand_guardrails
        else build_reference_analysis_snippet(
            reference_analysis,
            material_type,
            role_pack_material_key_fn=role_pack_material_key,
        )
    )
    reference_analysis_warning = ""
    if not disable_brand_guardrails:
        if analysis_mode == "deterministic_only":
            reference_analysis_warning = (
                f"Reference analysis is deterministic-only (confidence: {analysis_confidence}); "
                "treat role matching and transferable mechanics as approximate."
            )
        elif analysis_mode == "unavailable":
            reference_analysis_warning = (
                "Reference analysis is unavailable; treat reference-role guidance as low-confidence until analysis is attached."
            )
    inspiration = load_inspiration_prompt_context(
        brand_gen_dir=brand_gen_dir,
        active_brand=active_brand,
        material_type=material_type,
        brand_dir=brand_dir,
    )
    doctrine = "" if disable_brand_guardrails else inspiration.get("doctrine", "")
    token_block = "" if disable_brand_guardrails else inspiration.get("token_block", "")
    inspiration_memory_snippet = "" if disable_brand_guardrails else str(inspiration.get("memory_seed_prompt") or "").strip()
    profile_assets = (
        (identity.get("brand_assets") or {})
        if isinstance(identity, dict) and (identity.get("brand_assets") or {})
        else ((profile.get("brand_assets") or {}) if isinstance(profile, dict) else {})
    )
    approved_assets = [str(profile_assets.get(key) or "").strip() for key in ("icon", "wordmark", "lockup")]
    policy_setup_risks = (
        []
        if disable_brand_guardrails
        else evaluate_policy_setup_risks(
            material_type,
            brand_policy=brand_policy,
            selected_roles=role_pack.get("roles", []),
            approved_assets=approved_assets,
            passed_reference_paths=None,
            raw_prompt=body,
            render_backend=render_backend,
            source_url=source_url,
            entity_type=entity_type,
            selected_surface_strategy=selected_surface_strategy,
        )
    )
    chosen_inspiration_sources = list(selected_inspiration_sources or [])
    auto_selection_reason = ""
    auto_selection_mode = inspiration_selection_mode or ""
    if not chosen_inspiration_sources and not disable_brand_guardrails:
        auto_selection = select_inspiration_sources(
            list(inspiration.get("source_records") or []),
            selected_roles=role_pack.get("roles") or [],
            material_type=material_type,
        )
        chosen_inspiration_sources = list(auto_selection.get("records") or [])
        auto_selection_reason = auto_selection.get("reason") or ""
        auto_selection_mode = auto_selection.get("mode") or auto_selection_mode or "auto"
    selected_inspiration_translation_payload = (
        {"translation": "", "mechanics": [], "source_summaries": []}
        if disable_brand_guardrails
        else build_selected_inspiration_translation(chosen_inspiration_sources, material_type=material_type)
    )
    selected_inspiration_translation = selected_inspiration_translation_payload.get("translation") or ""
    if not selected_mechanic_labels:
        selected_mechanic_labels = list(selected_inspiration_translation_payload.get("mechanics") or [])
    if not selected_mechanic_ids:
        selected_mechanic_ids = dedupe_keep_order(
            [
                stable_mechanic_id(str(item.get("source_key") or item.get("source_name") or "source"), label)
                for item in chosen_inspiration_sources
                for label in (selected_mechanic_labels or [])[:2]
            ]
        )[:6]
    resolved_selected_inspiration_ids = list(selected_inspiration_ids or [])
    if not resolved_selected_inspiration_ids:
        resolved_selected_inspiration_ids = [
            str(item.get("source_key") or item.get("source_name") or "").strip()
            for item in chosen_inspiration_sources
            if str(item.get("source_key") or item.get("source_name") or "").strip()
        ]
    resolved_inspiration_selection_reason = inspiration_selection_reason or auto_selection_reason
    resolved_inspiration_selection_mode = inspiration_selection_mode or auto_selection_mode or ("explicit" if selected_inspiration_sources else "auto")

    # Inject compact messaging context so copy-bearing materials use real brand language
    messaging_snippet = ""
    if not disable_brand_guardrails:
        messaging = identity.get("messaging") or {}
        _msg_parts: list[str] = []
        if messaging.get("tagline"):
            _msg_parts.append(f"Tagline: {messaging['tagline']}")
        if messaging.get("elevator"):
            _msg_parts.append(messaging["elevator"])
        voice = messaging.get("voice") or {}
        if voice.get("description"):
            _msg_parts.append(f"Voice: {voice['description']}")
        if brand_dir:
            memory = load_iteration_memory(brand_dir)
            messaging_notes = list(memory.get("messaging_notes") or [])
            if messaging_notes:
                _msg_parts.append("Recent messaging notes: " + " | ".join(messaging_notes[-2:]))
        if _msg_parts:
            messaging_snippet = "Brand context: " + " ".join(_msg_parts)
            # Keep it compact for interface materials
            _msg_cap = _iface("messaging_snippet_cap")
            if material_key in INTERFACE_MATERIAL_KEYS and len(messaging_snippet) > _msg_cap:
                messaging_snippet = messaging_snippet[:_msg_cap].rstrip() + "…"

    _fragments = load_prompt_fragments()
    copy_anchor_snippet = ""
    _copy_anchor_materials = set(_fragments.get("copy_anchor_materials", []))
    if not disable_brand_guardrails and material_key in _copy_anchor_materials:
        messaging = identity.get("messaging") or {}
        copy_bank = messaging.get("approved_copy_bank") or {}
        approved_strings = dedupe_keep_order(
            [messaging.get("tagline") or ""]
            + list(copy_bank.get("headlines") or [])[:3]
            + list(copy_bank.get("subheadlines") or [])[:2]
            + list(copy_bank.get("slogans") or [])[:2]
        )
        if approved_strings:
            quoted = "; ".join(f'"{item}"' for item in approved_strings[:5])
            copy_anchor_snippet = _fragments.get("copy_anchor_with_strings", "").format(quoted_strings=quoted)
        else:
            copy_anchor_snippet = _fragments.get("copy_anchor_no_strings", "")

    image_safety_snippet = ""
    if not disable_brand_guardrails:
        image_safety_snippet = _fragments.get("image_safety", "")

    non_interface_quality_snippet = ""
    if not disable_brand_guardrails and material_key in NON_INTERFACE_MATERIAL_KEYS:
        non_interface_quality_snippet = _fragments.get("non_interface_quality_prelude", "")

    blackboard_learning_context = (
        {}
        if disable_brand_guardrails or not brand_dir
        else build_blackboard_learning_context(brand_dir, material_type)
    )
    blackboard_learning_snippet = (
        ""
        if disable_brand_guardrails or not brand_dir
        else build_blackboard_learning_snippet(brand_dir, material_type)
    )

    # Apply per-part caps for non-interface materials to prevent prelude bloat
    if material_key not in INTERFACE_MATERIAL_KEYS:
        brand_prelude = cap_text_at_sentence(brand_prelude, NON_INTERFACE_PRELUDE_CAP)
        doctrine = cap_text_at_sentence(doctrine, NON_INTERFACE_DOCTRINE_CAP)
        reference_analysis_snippet = cap_text_at_sentence(reference_analysis_snippet, NON_INTERFACE_REF_ANALYSIS_CAP)
        selected_inspiration_translation = cap_text_at_sentence(selected_inspiration_translation, _ni("inspiration_translation_cap"))
        inspiration_memory_snippet = cap_text_at_sentence(inspiration_memory_snippet, _ni("inspiration_memory_cap"))
        blackboard_learning_snippet = cap_text_at_sentence(blackboard_learning_snippet, _ni("compact_memory_cap"))
        custom_scratchpad_snippet = cap_text_at_sentence(custom_scratchpad_snippet, _ni("compact_memory_cap"))
        if len(token_block) > NON_INTERFACE_TOKEN_BLOCK_CAP:
            token_block = token_block[:NON_INTERFACE_TOKEN_BLOCK_CAP].rstrip() + "…"
    elif blackboard_learning_snippet:
        blackboard_learning_snippet = cap_text_at_sentence(blackboard_learning_snippet, _iface("ref_analysis_cap"))

    combined_prelude = "\n\n".join(
        part
        for part in [
            brand_prelude.strip(),
            messaging_snippet.strip(),
            copy_anchor_snippet.strip(),
            iteration_memory_snippet.strip(),
            custom_scratchpad_snippet.strip(),
            blackboard_learning_snippet.strip(),
            material_snippet.strip(),
            role_pack_snippet.strip(),
            reference_analysis_snippet.strip(),
            inspiration_memory_snippet.strip(),
            selected_inspiration_translation.strip(),
            doctrine.strip(),
            image_safety_snippet.strip(),
            non_interface_quality_snippet.strip(),
        ]
        if part and part.strip()
    )
    # Hard cap on total prelude for non-interface materials
    if material_key not in INTERFACE_MATERIAL_KEYS and len(combined_prelude) > NON_INTERFACE_TOTAL_PRELUDE_CAP:
        combined_prelude = cap_text_at_sentence(combined_prelude, NON_INTERFACE_TOTAL_PRELUDE_CAP)
    resolved = prefix_prompt(combined_prelude, body, token_block=token_block)
    return {
        "brand_prelude": brand_prelude,
        "iteration_memory_snippet": iteration_memory_snippet,
        "custom_scratchpad_snippet": custom_scratchpad_snippet,
        "blackboard_learning_snippet": blackboard_learning_snippet,
        "blackboard_learning_summary": blackboard_learning_context.get("summary") or {},
        "blackboard_learning_recipes": blackboard_learning_context.get("recipes") or [],
        "blackboard_learning_warnings": blackboard_learning_context.get("warnings") or [],
        "material_prompt_key": material_key,
        "material_prompt_variant": material_variant,
        "material_prompt_snippet": material_snippet,
        "render_backend": str(render_backend or ""),
        "source_url": str(source_url or ""),
        "entity_type": str(entity_type or ""),
        "selected_surface_strategy": str(selected_surface_strategy or ""),
        "reference_role_pack": role_pack.get("roles", []),
        "reference_role_pack_paths": [str(path) for path in role_pack.get("paths", [])],
        "reference_role_pack_motion_paths": [str(path) for path in role_pack.get("motion_paths", [])],
        "reference_role_pack_snippet": role_pack_snippet,
        "reference_role_pack_missing_roles": role_pack.get("missing_roles", []),
        "reference_role_pack_required_roles": role_pack.get("required_roles", []),
        "reference_role_pack_missing_required_roles": role_pack.get("missing_required_roles", []),
        "reference_role_assignment_warnings": role_pack.get("role_assignment_warnings", []),
        "reference_role_pack_priority": role_pack.get("priority", []),
        "reference_role_pack_prefer_unique_sources": role_pack.get("prefer_unique_sources", True),
        "reference_analysis": reference_analysis,
        "reference_analysis_mode": analysis_mode,
        "reference_analysis_confidence": analysis_confidence,
        "reference_analysis_warning": reference_analysis_warning,
        "policy_setup_risks": policy_setup_risks,
        "reference_analysis_snippet": reference_analysis_snippet,
        "copy_anchor_snippet": copy_anchor_snippet,
        "image_safety_snippet": image_safety_snippet,
        "non_interface_quality_prelude": non_interface_quality_snippet,
        "inspiration_memory_summary": str(inspiration.get("memory_summary") or ""),
        "inspiration_memory_snippet": inspiration_memory_snippet,
        "inspiration_doctrine": doctrine,
        "selected_inspiration_translation": selected_inspiration_translation,
        "selected_inspiration_source_records": chosen_inspiration_sources,
        "selected_inspiration_ids": resolved_selected_inspiration_ids,
        "selected_mechanic_ids": list(selected_mechanic_ids or []),
        "selected_mechanic_labels": list(selected_mechanic_labels or []),
        "inspiration_selection_reason": resolved_inspiration_selection_reason,
        "inspiration_selection_mode": resolved_inspiration_selection_mode,
        "aesthetic_archetype": aesthetic_archetype if isinstance(aesthetic_archetype, dict) else None,
        "aesthetic_archetype_id": (aesthetic_archetype.get("id") if isinstance(aesthetic_archetype, dict) else ""),
        "prompt_subject": (prompt_subject or "").strip(),
        "prompt_style_descriptors": (prompt_style_descriptors or "").strip(),
        "prompt_lighting": (prompt_lighting or "").strip(),
        "prompt_camera": (prompt_camera or "").strip(),
        "prompt_composition": (prompt_composition or "").strip(),
        "prompt_details": (prompt_details or "").strip(),
        "visual_density": visual_density if visual_density not in (None, "") else None,
        "aesthetic_commitment": (aesthetic_commitment or "").strip(),
        "token_block": token_block,
        "token_block_fragments": inspiration.get("token_block_fragments", []),
        "resolved_prompt": resolved,
        "inspiration_sources": inspiration.get("sources", []),
        "inspiration_source_records": inspiration.get("source_records", []),
        "skipped_inspiration_sources": inspiration.get("skipped", []),
        "inspiration_mode": inspiration.get("mode", "principles"),
    }


# ── Text utilities ───────────────────────────────────────────────────

def split_prompt_sentences(text: str) -> list[str]:
    cleaned = re.sub(r"\s+", " ", (text or "").strip())
    if not cleaned:
        return []
    raw_parts = re.split(r"(?<=[.!?])\s+|(?:\s+-\s+)", cleaned)
    out: list[str] = []
    seen: set[str] = set()
    for part in raw_parts:
        part = part.strip(" -\n\t")
        if not part:
            continue
        key = part.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(part)
    return out


def sentence_join(items: list[str]) -> str:
    cleaned = [str(item).strip() for item in items if str(item).strip()]
    if not cleaned:
        return ""
    if len(cleaned) == 1:
        return cleaned[0]
    if len(cleaned) == 2:
        return f"{cleaned[0]} and {cleaned[1]}"
    return ", ".join(cleaned[:-1]) + f", and {cleaned[-1]}"


def first_sentence_matching_keywords(text: str, keywords: list[str]) -> str:
    for sentence in split_prompt_sentences(text):
        lower = sentence.lower()
        if any(keyword in lower for keyword in keywords):
            return sentence
    return ""


# ── Prelude budget caps ──────────────────────────────────────────────

_DEFAULT_BUDGET = {
    "non_interface": {
        "prelude_cap": 1500,
        "doctrine_cap": 600,
        "ref_analysis_cap": 500,
        "token_block_cap": 400,
        "total_prelude_cap": 3000,
        "inspiration_translation_cap": 500,
        "inspiration_memory_cap": 350,
        "selected_inspiration_cap": 500,
        "compact_memory_cap": 500,
        "compress_max_sentences": 6,
        "compress_max_chars": 700,
        "compact_body_max_sentences": 4,
        "compact_body_max_chars": 480,
    },
    "interface": {
        "messaging_snippet_cap": 250,
        "ref_analysis_cap": 250,
        "selected_inspiration_cap": 350,
        "doctrine_cap": 350,
        "compress_max_sentences": 4,
        "compress_max_chars": 400,
        "compact_body_max_sentences": 3,
        "compact_body_max_chars": 320,
    },
    "shared": {
        "copy_rule_cap": 280,
        "execution_inspiration_cap": 320,
    },
}


def _get_budget() -> dict:
    return load_prompt_budget() or _DEFAULT_BUDGET


def _ni(key: str) -> int | float:
    return _get_budget().get("non_interface", {}).get(key, _DEFAULT_BUDGET["non_interface"][key])


def _iface(key: str) -> int | float:
    return _get_budget().get("interface", {}).get(key, _DEFAULT_BUDGET["interface"][key])


def _shared(key: str) -> int | float:
    return _get_budget().get("shared", {}).get(key, _DEFAULT_BUDGET["shared"][key])


# Backward-compatible module-level constants (loaded from JSON)
_b = _get_budget()
NON_INTERFACE_PRELUDE_CAP = _b.get("non_interface", {}).get("prelude_cap", 1500)
NON_INTERFACE_DOCTRINE_CAP = _b.get("non_interface", {}).get("doctrine_cap", 600)
NON_INTERFACE_REF_ANALYSIS_CAP = _b.get("non_interface", {}).get("ref_analysis_cap", 500)
NON_INTERFACE_TOKEN_BLOCK_CAP = _b.get("non_interface", {}).get("token_block_cap", 400)
NON_INTERFACE_TOTAL_PRELUDE_CAP = _b.get("non_interface", {}).get("total_prelude_cap", 3000)


def cap_text_at_sentence(text: str, max_chars: int) -> str:
    """Truncate *text* at the nearest sentence boundary <= *max_chars*.

    Falls back to hard truncation + "..." if no sentence boundary is found.
    """
    text = (text or "").strip()
    if len(text) <= max_chars:
        return text
    sentences = split_prompt_sentences(text)
    if not sentences:
        return text[:max_chars].rstrip() + "…"
    result: list[str] = []
    total = 0
    for s in sentences:
        addition = len(s) + (2 if result else 0)  # account for ". " join
        if total + addition > max_chars:
            break
        result.append(s)
        total += addition
    if not result:
        return text[:max_chars].rstrip() + "…"
    joined = " ".join(result)
    if not joined.endswith((".", "!", "?")):
        joined += "."
    return joined


def compress_prompt_body(body: str, material_key: str, *, max_sentences: int | None = None, max_chars: int | None = None) -> str:
    if max_sentences is None:
        max_sentences = _iface("compress_max_sentences") if material_key in INTERFACE_MATERIAL_KEYS else _ni("compress_max_sentences")
    if max_chars is None:
        max_chars = _iface("compress_max_chars") if material_key in INTERFACE_MATERIAL_KEYS else _ni("compress_max_chars")
    sentences = split_prompt_sentences(body)
    if not sentences:
        return ""
    # If the body fits within budget, return it unchanged — never truncate
    # content that already fits.
    joined_full = " ".join(sentences).strip()
    if len(joined_full) <= max_chars and len(sentences) <= max_sentences:
        return joined_full
    prioritized: list[tuple[int, str]] = []
    keywords = []
    if material_key in INTERFACE_MATERIAL_KEYS:
        keywords = ["real", "product", "ui", "screenshot", "hero", "moment", "crop", "preserve", "logo", "copy", "headline"]
    elif material_key in NON_INTERFACE_MATERIAL_KEYS:
        keywords = ["logo", "mark", "motif", "copy", "headline", "slogan", "brand", "palette", "poster"]
    else:
        keywords = ["brand", "product", "logo", "headline"]
    for idx, sentence in enumerate(sentences):
        score = 0
        lower = sentence.lower()
        for kw in keywords:
            if kw in lower:
                score += 3
        if "do not" in lower or "never" in lower:
            score += 2
        if idx < 3:
            score += 1
        prioritized.append((score, sentence))
    picked: list[str] = []
    total = 0
    for _, sentence in sorted(prioritized, key=lambda item: (-item[0], sentences.index(item[1]))):
        candidate_len = total + len(sentence) + (1 if picked else 0)
        if len(picked) >= max_sentences or candidate_len > max_chars:
            continue
        picked.append(sentence)
        total = candidate_len
    # If keyword-priority picking dropped too much, fall back to keeping
    # sentences in their original order up to the char budget — never
    # hard-truncate mid-sentence.
    if not picked:
        picked = []
        total = 0
        for s in sentences:
            candidate_len = total + len(s) + (1 if picked else 0)
            if candidate_len > max_chars:
                break
            picked.append(s)
            total = candidate_len
    if not picked:
        # Body is a single very long sentence — keep it whole rather than
        # cutting mid-thought.  The model handles long prompts better than
        # truncated fragments.
        return joined_full
    return " ".join(picked).strip()


# ── Compact execution prompt helpers ─────────────────────────────────

def compact_role_pack_snippet(roles: list[dict]) -> str:
    if not roles:
        return ""
    lines = ["Translate references into mechanics only:"]
    for item in roles[:3]:
        translation = item.get("translation") or default_reference_translation(item.get("role") or "", item)
        borrow = translation.get("borrow_mechanics") or []
        avoid = translation.get("avoid_literal") or []
        bits = []
        if borrow:
            bits.append(f"borrow {sentence_join(borrow[:2])}")
        if avoid:
            bits.append(f"avoid {sentence_join(avoid[:2])}")
        source_name = item.get("source_name") or item.get("source_key") or item.get("role") or "reference"
        role = item.get("role") or "reference"
        suffix = f" from {source_name}" if source_name else ""
        detail = "; ".join(bits).strip()
        lines.append(f"- {role}{suffix}: {detail}".rstrip(": "))
    return "\n".join(lines)


def compact_execution_material_policy(material_snippet: str, material_key: str) -> str:
    material_snippet = (material_snippet or "").strip()
    if not material_snippet:
        return ""
    sentences = split_prompt_sentences(material_snippet)
    if not sentences:
        return ""
    keywords = (
        ["browser", "ui", "product", "crop", "frame", "interface", "hero", "proof"]
        if material_key in INTERFACE_MATERIAL_KEYS
        else ["poster", "banner", "card", "cover", "copy", "mark", "motif", "brand"]
    )
    selected: list[str] = []
    for sentence in sentences:
        lower = sentence.lower()
        if any(keyword in lower for keyword in keywords):
            selected.append(sentence)
        if len(selected) >= 2:
            break
    if not selected:
        selected = sentences[:2]
    return "Material policy: " + " ".join(selected[:2]).strip()


def compact_execution_brand_anchor(context: dict, material_key: str) -> str:
    anchor = first_sentence_matching_keywords(
        context.get("brand_prelude") or "",
        [
            "logo",
            "wordmark",
            "icon",
            "mark",
            "clearly branded",
            "palette",
            "product truth",
            "brand name",
        ],
    )
    if not anchor:
        if material_key in INTERFACE_MATERIAL_KEYS:
            anchor = "Keep the output anchored to the real product proof and approved brand mark."
        elif material_key in NON_INTERFACE_MATERIAL_KEYS:
            anchor = "Keep the output anchored to approved brand assets, palette, and mark geometry."
        else:
            anchor = "Keep the output clearly anchored to approved brand assets and product truth."
    return "Brand anchor: " + anchor.rstrip(".") + "."


def compact_execution_copy_rule(context: dict) -> str:
    copy_anchor = (context.get("copy_anchor_snippet") or "").strip()
    if not copy_anchor:
        return ""
    return "Copy rule: " + cap_text_at_sentence(copy_anchor, _shared("copy_rule_cap")).rstrip(".") + "."


def compact_execution_critical_bans(context: dict, material_key: str) -> str:
    bans: list[str] = []
    if material_key in INTERFACE_MATERIAL_KEYS:
        bans.append("Do not redraw the product UI or invent extra interface chrome around the real proof.")
    bans.append(
        "Never render prompt metadata, reference labels, hashes, file paths, callout boxes, or technical annotations as visible content."
    )
    explicit = first_sentence_matching_keywords(
        context.get("brand_prelude") or "",
        ["do not", "never", "avoid", "without", "ban"],
    )
    if explicit:
        bans.insert(0, explicit.rstrip(".") + ".")
    return "Critical bans: " + " ".join(dedupe_keep_order(bans)[:2]).strip()


def compact_execution_reference_caveat(context: dict) -> str:
    mode = str(context.get("reference_analysis_mode") or "")
    confidence = str(context.get("reference_analysis_confidence") or "low")
    if mode == "deterministic_only":
        return (
            f"Reference caveat: deterministic-only analysis ({confidence} confidence); "
            "borrow transferable mechanics only, not literal layout or copy."
        )
    if mode == "unavailable":
        return "Reference caveat: reference analysis unavailable; keep reference translation conservative."
    if mode == "vlm_augmented" and confidence in {"low", "medium"}:
        return f"Reference caveat: {confidence}-confidence reference analysis; keep translation conservative."
    return ""


def compact_execution_selected_inspiration(context: dict) -> str:
    text = str(context.get("selected_inspiration_translation") or "").strip()
    if not text:
        return ""
    return cap_text_at_sentence(text, _shared("execution_inspiration_cap"))


# Short push clauses per overlay axis. Kept compact so the injection
# doesn't bloat the execution prompt (which already runs tight against
# total_cap). The clauses are the positive inversion of the scorer's
# axis definition, because the prompt is push/ban, not rubric prose.
_OVERLAY_AXIS_PUSH_CLAUSES = {
    # landing-hero
    "surface_fit": "prove surface_fit: compose like a landing hero (not a social card or ad) — left-column copy supported by right-column art, or full-bleed with clean headline overlay",
    "meaning_at_glance": "prove meaning_at_glance: a visitor understands the product category in 2-3 seconds; the image does the work, the headline only seals it",
    # concept-illustration
    "system_logic_visible": "prove system_logic_visible: show a visible system (nodes+edges, strata+flow, parts+whole) — not a single symbol floating in space",
    "brand_specificity": "prove brand_specificity: carry THIS brand's declared metaphor vocabulary and material palette, not interchangeable premium-AI-brand art",
    # brand-scene
    "process_implied": "prove process_implied: show evidence of the brand's actual work (tools, materials mid-use, posture of activity) — not pure architectural mood",
}


def compact_execution_aesthetic_commitment(context: dict) -> str:
    """Render the plan's aesthetic_commitment as a compositional directive.

    The planner commits to ONE axis extreme (minimal, maximal,
    editorial, brutalist, organic, industrial, retro_futurist,
    playful, luxury). The prompt surfaces the commitment's grammar
    so the model's aesthetic interpretation is anchored rather than
    averaged across hedge-words.
    """
    from .plan_validation import aesthetic_commitment_grammar

    commitment = context.get("aesthetic_commitment")
    grammar = aesthetic_commitment_grammar(commitment)
    if not grammar:
        return ""
    return f"Aesthetic commitment ({commitment}): {grammar}"


def compact_execution_visual_density(context: dict) -> str:
    """Render the plan's visual_density as a compositional directive.

    visual_density is the SPATIAL dial (airy vs packed) — orthogonal to
    complexity_tier (which caps named-element count). This helper emits
    a short directive per band so the model has explicit spacing
    language instead of inferring from prose mood words.

    Returns empty string when density is absent or at the neutral
    default, so the typical case adds no prompt-budget cost.
    """
    from .plan_validation import normalize_visual_density, visual_density_grammar

    raw = context.get("visual_density")
    if raw is None or raw == "":
        return ""
    density = normalize_visual_density(raw)
    # Only surface the directive when the planner chose a non-default
    # band — band 4 and 5 render the same "daily-app" grammar, so don't
    # bloat the prompt unless the user explicitly pushed to an extreme.
    if 4 <= density <= 5:
        return ""
    return f"Visual density (dial {density}/10): {visual_density_grammar(density)}"


def compact_execution_five_slot_brief(context: dict) -> str:
    """Render the 5-slot prompt template (Subject + Style + Lighting +
    Composition + Details) from explicit plan fields when the planner
    supplied them.

    Rationale (from imagevideogen skill): image models respond to explicit,
    concrete slots ("Kodak Portra 400 film grain", "golden hour backlight",
    "85mm portrait lens") far better than to prose mood words ("warm",
    "editorial", "premium"). When the planner declares these slots, render
    them as a dedicated directive block in the execution prompt.

    Returns empty string when none of the slots are populated. The plan
    keeps these slots OPTIONAL (the archetype library already provides
    good defaults) but when the planner fills them, they override.
    """
    subject = (context.get("prompt_subject") or "").strip()
    style = (context.get("prompt_style_descriptors") or "").strip()
    lighting = (context.get("prompt_lighting") or "").strip()
    camera = (context.get("prompt_camera") or "").strip()
    details = (context.get("prompt_details") or "").strip()
    # Composition may be either an explicit string or inferred from the
    # surface strategy. Prefer the explicit field when set.
    composition = (context.get("prompt_composition") or context.get("selected_surface_strategy_prompt_directive") or "").strip()
    parts: list[str] = []
    if subject:
        parts.append(f"Subject: {subject}")
    if style:
        parts.append(f"Style: {style}")
    if lighting or camera:
        lens_part = ", ".join(p for p in (lighting, camera) if p)
        parts.append(f"Lighting + camera: {lens_part}")
    if composition:
        parts.append(f"Composition: {composition}")
    if details:
        parts.append(f"Details: {details}")
    if not parts:
        return ""
    return "Five-slot brief — " + " | ".join(parts) + "."


def compact_execution_aesthetic_archetype(
    context: dict,
    material_type: str | None,
) -> str:
    """Render the chosen aesthetic archetype as a compositional directive.

    The planner selects an archetype per run (rotating through the material's
    set — see brand_gen.aesthetic_archetypes.pick_rotating_archetype) and
    persists the choice on the plan under `aesthetic_archetype` (either the
    full dict or just the id). This helper materializes it into the prompt
    so the model has concrete handholds (grammar + color + finish) instead
    of the mood words that produced v181/v182-style generic output.

    Returns empty string when no archetype is on the plan or the material
    has no archetype library declared.
    """
    from .aesthetic_archetypes import (
        get_archetype,
        list_archetypes,
        render_archetype_brief,
    )

    archetype = context.get("aesthetic_archetype")
    archetype_id = context.get("aesthetic_archetype_id") or (
        archetype.get("id") if isinstance(archetype, dict) else None
    )
    if isinstance(archetype, dict) and archetype.get("compositional_grammar"):
        return render_archetype_brief(archetype)
    if archetype_id:
        found = get_archetype(material_type, archetype_id)
        if found:
            return render_archetype_brief(found)
    # No explicit pick; fall back to the first archetype if the library has
    # one for this material so the prompt is never completely unopinionated.
    candidates = list_archetypes(material_type)
    if candidates:
        return render_archetype_brief(candidates[0])
    return ""


def compact_execution_rubric_overlay_push(material_type: str | None) -> str:
    """Emit a compact 'Prove axes:' clause for the material's v2 overlay axes.

    Pulls overlay-axis names from brand_gen.scoring.rubric_registry and
    renders one push clause per axis. Returns empty string when the
    material has no overlay (universal-only materials).

    Rationale: the planner's Step 5 already reads show-rubric so the
    PLAN targets the right axes. But the execution_prompt the model
    sees has no rubric content — the model never learns the scorer's
    criteria. Injecting push clauses for the overlay axes closes that
    gap so the generator is biased toward the axes the critic will
    score.
    """
    if not material_type:
        return ""
    try:
        from .scoring.rubric_registry import axes_for, disqualifier_for, material_rubric_key
    except ImportError:
        return ""
    rubric_key = material_rubric_key(material_type)
    if not rubric_key:
        return ""
    # axes_for returns universal + overlay; the overlay axes are the ones
    # whose name matches a key in _OVERLAY_AXIS_PUSH_CLAUSES.
    axes = axes_for(material_type)
    overlay_names = [a["name"] for a in axes if a["name"] in _OVERLAY_AXIS_PUSH_CLAUSES]
    if not overlay_names:
        return ""
    clauses = [_OVERLAY_AXIS_PUSH_CLAUSES[name] for name in overlay_names]
    parts = ["Prove axes: " + "; ".join(clauses) + "."]
    # Also surface the disqualifier so the generator avoids it explicitly.
    dq = disqualifier_for(material_type)
    if dq:
        parts.append(
            f"Avoid the {dq['rule_id']} failure: {dq['description']}"
        )
    return " ".join(parts)


def build_execution_prompt(
    raw_prompt: str,
    context: dict,
    *,
    material_type: str | None = None,
    generation_mode: str = "image",
) -> dict:
    material_key = context.get("material_prompt_key") or role_pack_material_key(material_type)
    fallback_prompt = context.get("refined_prompt") or context.get("resolved_prompt") or raw_prompt
    if generation_mode != "image":
        return {
            "execution_prompt": fallback_prompt,
            "execution_prompt_kind": "review_refined",
            "execution_prompt_compressed": False,
            "execution_prompt_sections": {},
        }

    role_pack = context.get("reference_role_pack") or []
    sections = {
        "material_policy": compact_execution_material_policy(context.get("material_prompt_snippet") or "", material_key),
        "brand_anchor_rule": compact_execution_brand_anchor(context, material_key),
        "role_pack_block": compact_role_pack_snippet(role_pack[:1]),
        "selected_inspiration_block": compact_execution_selected_inspiration(context),
        "aesthetic_commitment_block": compact_execution_aesthetic_commitment(context),
        "five_slot_brief": compact_execution_five_slot_brief(context),
        "visual_density_block": compact_execution_visual_density(context),
        "aesthetic_archetype_block": compact_execution_aesthetic_archetype(context, material_type),
        "rubric_overlay_push": compact_execution_rubric_overlay_push(material_type),
        "critical_bans": compact_execution_critical_bans(context, material_key),
        "explicit_copy_rule": compact_execution_copy_rule(context),
        "reference_analysis_caveat": compact_execution_reference_caveat(context),
    }

    # Compute the total prelude size first.
    prelude_parts = [
        sections["material_policy"],
        sections["brand_anchor_rule"],
        sections["role_pack_block"],
        sections["selected_inspiration_block"],
        sections["aesthetic_commitment_block"],
        sections["five_slot_brief"],
        sections["visual_density_block"],
        sections["aesthetic_archetype_block"],
        sections["rubric_overlay_push"],
        sections["critical_bans"],
        sections["explicit_copy_rule"],
        sections["reference_analysis_caveat"],
    ]
    prelude = "\n\n".join(
        section for section in prelude_parts if section
    )

    # Budget: the body (creative direction) gets at least 40% of the total
    # prompt budget.  The prelude (guardrails) compresses to fit.
    total_cap = _ni("total_prelude_cap") if material_key not in INTERFACE_MATERIAL_KEYS else 2000
    body_max_sentences = _ni("compact_body_max_sentences") if material_key not in INTERFACE_MATERIAL_KEYS else _iface("compact_body_max_sentences")
    body_max_chars = _ni("compact_body_max_chars") if material_key not in INTERFACE_MATERIAL_KEYS else _iface("compact_body_max_chars")
    min_body_budget = max(body_max_chars, int(total_cap * 0.4))

    # Compress the body with its full budget first.
    compact_body = compress_prompt_body(raw_prompt, material_key, max_sentences=body_max_sentences, max_chars=body_max_chars)
    body_was_lossy = len(compact_body) < len(raw_prompt.strip()) and compact_body != raw_prompt.strip()

    # If prelude + body exceeds total cap, shrink the *prelude*, not the body.
    prelude_budget = max(total_cap - len(compact_body) - 4, int(total_cap * 0.3))
    if len(prelude) > prelude_budget:
        prelude = cap_text_at_sentence(prelude, prelude_budget)

    sections["body"] = compact_body
    execution_prompt = prefix_prompt(prelude, compact_body, token_block="")
    return {
        "execution_prompt": execution_prompt or fallback_prompt,
        "execution_prompt_kind": "image_compact",
        "execution_prompt_compressed": True,
        "execution_prompt_sections": sections,
        "body_compressed": body_was_lossy,
        "body_original_chars": len(raw_prompt.strip()),
        "body_compressed_chars": len(compact_body),
        "prelude_chars": len(prelude),
    }


# ── Prompt review ────────────────────────────────────────────────────

def material_group_for_prompt_review(material_key: str) -> str:
    if material_key in INTERFACE_MATERIAL_KEYS:
        return "interface"
    if material_key in NON_INTERFACE_MATERIAL_KEYS:
        return "non_interface"
    return "general"


def detect_prompt_execution_risks(raw_prompt: str, context: dict, *, material_type: str | None = None) -> list[str]:
    material_key = context.get("material_prompt_key") or role_pack_material_key(material_type)
    normalized_material = str(material_type or "").strip().lower().replace("-", "_")
    role_pack = context.get("reference_role_pack") or []
    render_backend = str(context.get("render_backend") or "").strip().lower()
    source_url = str(context.get("source_url") or "").strip()
    entity_type = str(context.get("entity_type") or "").strip().lower()
    selected_surface_strategy = str(context.get("selected_surface_strategy") or "").strip().lower()
    screenshot_terms = [
        "screenshot",
        "screen",
        "proof inset",
        "proof chip",
        "proof panel",
        "product crop",
        "viewport",
        "feed crop",
        "prompt detail",
        "app state",
    ]
    exact_text_terms = [
        "exact text",
        "exact title",
        "exact headline",
        "exact tagline",
        "keep the exact",
        "verbatim",
    ]
    combined = " ".join(
        [
            str(raw_prompt or ""),
            str(context.get("material_prompt_snippet") or ""),
            str(context.get("resolved_prompt") or ""),
            " ".join(str(item.get("role") or "") for item in role_pack),
            " ".join(str(item.get("source_name") or item.get("source_key") or "") for item in role_pack),
        ]
    ).lower()
    structured_governed_html = bool(
        render_backend == "html"
        and source_url
        and entity_type in {"prompt", "skill", "library"}
        and selected_surface_strategy
    )
    screenshot_led = any(term in combined for term in screenshot_terms) or any(
        str(item.get("role") or "").strip() == "product_truth" for item in role_pack
    )
    if structured_governed_html:
        screenshot_led = False
    exact_text_requested = any(term in combined for term in exact_text_terms)

    warnings: list[str] = []
    if normalized_material == "announcement_card" and screenshot_led:
        warnings.append(
            "Announcement-card policy conflicts with the current screenshot-led proof setup. Keep proof to a tiny deterministic chip, switch this run to social/x-feed, or use deterministic composition if exact text must survive."
        )
    if normalized_material in {"x_feed_portrait", "linkedin_feed_portrait", "announcement_card"} and screenshot_led:
        warnings.append(
            "Portrait proof-heavy layouts are high risk for garbled text. Use a tiny proof chip instead of a full screenshot, or switch to deterministic composition/base-image editing."
        )
    if material_key == "social" and screenshot_led:
        warnings.append(
            "Social proof should stay subordinate to the brand field: keep any proof inset to roughly 20–25% of the visual weight instead of letting it dominate the composition."
        )
    if exact_text_requested:
        warnings.append(
            "Exact text request detected. Prefer deterministic composition or base-image editing over image-model text rendering."
        )
    return dedupe_keep_order(warnings)


def prompt_review_rule_matches(rule: dict, *, material_key: str, raw_prompt: str, context: dict) -> bool:
    material_groups = set(rule.get("material_groups") or [])
    materials = set(rule.get("materials") or [])
    current_group = material_group_for_prompt_review(material_key)
    if material_groups and current_group not in material_groups:
        return False
    if materials and material_key not in materials:
        return False
    when = rule.get("when") or {}
    brand_prelude = context.get("brand_prelude") or ""
    resolved_prompt = context.get("resolved_prompt") or ""
    role_pack = context.get("reference_role_pack") or []
    blackboard_learning = context.get("blackboard_learning_summary") or {}
    raw_lower = (raw_prompt or "").lower()

    if "brand_prelude_contains" in when and when["brand_prelude_contains"] not in brand_prelude:
        return False
    if "resolved_prompt_chars_gt" in when and len(resolved_prompt) <= int(when["resolved_prompt_chars_gt"]):
        return False
    if "raw_prompt_chars_gt" in when and len(raw_prompt or "") <= int(when["raw_prompt_chars_gt"]):
        return False
    if when.get("role_pack_empty") is True and role_pack:
        return False
    if "raw_prompt_missing_any_keywords" in when:
        keywords = [str(item).lower() for item in when["raw_prompt_missing_any_keywords"]]
        if any(keyword in raw_lower for keyword in keywords):
            return False
    if "raw_prompt_contains_any_keywords" in when:
        keywords = [str(item).lower() for item in when["raw_prompt_contains_any_keywords"]]
        if not any(keyword in raw_lower for keyword in keywords):
            return False
    if "raw_prompt_phrase_count_gte" in when:
        payload = when["raw_prompt_phrase_count_gte"] or {}
        phrases = [str(item).lower() for item in payload.get("phrases", [])]
        threshold = int(payload.get("count", 1) or 1)
        count = sum(raw_lower.count(phrase) for phrase in phrases)
        if count < threshold:
            return False
    if "recent_low_score_count_gte" in when and int(blackboard_learning.get("recent_low_score_count") or 0) < int(when["recent_low_score_count_gte"]):
        return False
    if "learning_failure_patterns_include_any" in when:
        haystack = " ".join(str(item).lower() for item in (blackboard_learning.get("failure_patterns") or []))
        needles = [str(item).lower() for item in when["learning_failure_patterns_include_any"]]
        if not any(needle in haystack for needle in needles):
            return False
    if "learning_reference_bias_contains_any" in when:
        haystack = " ".join(str(item).lower() for item in (blackboard_learning.get("reference_bias") or []))
        needles = [str(item).lower() for item in when["learning_reference_bias_contains_any"]]
        if not any(needle in haystack for needle in needles):
            return False
    return True


def evaluate_prompt_review_rules(material_key: str, raw_prompt: str, context: dict) -> tuple[list[str], list[str]]:
    issues: list[str] = []
    recommendations: list[str] = []
    for rule in (load_prompt_review_rules().get("rules") or []):
        if not isinstance(rule, dict):
            continue
        if not prompt_review_rule_matches(rule, material_key=material_key, raw_prompt=raw_prompt, context=context):
            continue
        issue = (rule.get("issue") or "").strip()
        recommendation = (rule.get("recommendation") or "").strip()
        if issue and issue not in issues:
            issues.append(issue)
        if recommendation and recommendation not in recommendations:
            recommendations.append(recommendation)
    return issues, recommendations


def review_prompt_architecture(
    profile: dict,
    identity: dict,
    raw_prompt: str,
    context: dict,
    *,
    material_type: str | None = None,
    workflow_mode: str | None = None,
    token_block: str | None = None,
    generation_mode: str = "image",
) -> dict:
    material_key = context.get("material_prompt_key") or role_pack_material_key(material_type)
    analysis_mode = str(context.get("reference_analysis_mode") or reference_analysis_mode(context.get("reference_analysis") or {}))
    analysis_confidence = str(context.get("reference_analysis_confidence") or reference_analysis_confidence(context.get("reference_analysis") or {}))
    analysis_warning = str(context.get("reference_analysis_warning") or "").strip()
    issues, recommendations = evaluate_prompt_review_rules(material_key, raw_prompt, context)
    ref_issues, ref_recommendations = reference_analysis_review_notes(context.get("reference_analysis") or {})
    for issue in ref_issues:
        if issue not in issues:
            issues.append(issue)
    for recommendation in ref_recommendations:
        if recommendation not in recommendations:
            recommendations.append(recommendation)
    if analysis_warning and analysis_warning not in recommendations:
        recommendations.append(analysis_warning)
    # Interface materials: flag too many refs (prefer 1 product + 1 inspiration max)
    role_pack = context.get("reference_role_pack") or []
    role_assignment_warnings = [str(item).strip() for item in (context.get("reference_role_assignment_warnings") or []) if str(item).strip()]
    policy_setup_risks = [str(item).strip() for item in (context.get("policy_setup_risks") or []) if str(item).strip()]
    blackboard_learning_warnings = [str(item).strip() for item in (context.get("blackboard_learning_warnings") or []) if str(item).strip()]
    if material_key in INTERFACE_MATERIAL_KEYS and len(role_pack) > 2:
        note = f"Interface material has {len(role_pack)} refs; prefer 1 product hero + 1 inspiration ref for tighter composition."
        if note not in recommendations:
            recommendations.append(note)
    for warning in role_assignment_warnings:
        if warning not in recommendations:
            recommendations.append(warning)
    for risk in policy_setup_risks:
        if risk not in recommendations:
            recommendations.append(risk)
    for warning in blackboard_learning_warnings:
        if warning not in recommendations:
            recommendations.append(warning)
    for warning in detect_prompt_execution_risks(raw_prompt, context, material_type=material_type):
        if warning not in recommendations:
            recommendations.append(warning)

    messaging = (identity or {}).get("messaging") or {}
    forbidden_claims = [str(item).strip() for item in (messaging.get("forbidden_claims") or []) if str(item).strip()]
    if forbidden_claims and raw_prompt:
        lowered = raw_prompt.lower()
        for claim in forbidden_claims:
            needle = claim.lower()
            if needle and needle in lowered:
                issue = f"Forbidden messaging claim in prompt: '{claim}'. Remove or rephrase before generating."
                if issue not in issues:
                    issues.append(issue)

    base_prelude = get_base_brand_guardrail_prelude(profile, identity, material_type)
    resolved_prompt = context.get("resolved_prompt") or ""

    # Cap base prelude for non-interface materials (was uncapped -> 2000+ chars)
    if material_key not in INTERFACE_MATERIAL_KEYS:
        base_prelude = cap_text_at_sentence(base_prelude, NON_INTERFACE_PRELUDE_CAP)

    compact_parts = [base_prelude.strip()]
    material_snippet = (context.get("material_prompt_snippet") or "").strip()
    if material_snippet:
        compact_parts.append(material_snippet)
    compact_roles = compact_role_pack_snippet(role_pack)
    selected_inspiration_translation = (context.get("selected_inspiration_translation") or "").strip()
    if compact_roles:
        compact_parts.append(compact_roles)
    reference_analysis_snippet = (context.get("reference_analysis_snippet") or "").strip()
    ref_analysis_cap = _iface("ref_analysis_cap") if material_key in INTERFACE_MATERIAL_KEYS else NON_INTERFACE_REF_ANALYSIS_CAP
    if reference_analysis_snippet and len(reference_analysis_snippet) <= ref_analysis_cap:
        compact_parts.append(reference_analysis_snippet)
    elif reference_analysis_snippet:
        compact_parts.append(cap_text_at_sentence(reference_analysis_snippet, ref_analysis_cap))
    if selected_inspiration_translation:
        compact_parts.append(cap_text_at_sentence(selected_inspiration_translation, _iface("selected_inspiration_cap") if material_key in INTERFACE_MATERIAL_KEYS else _ni("selected_inspiration_cap")))
    else:
        doctrine = (context.get("inspiration_doctrine") or "").strip()
        doctrine_cap = _iface("doctrine_cap") if material_key in INTERFACE_MATERIAL_KEYS else NON_INTERFACE_DOCTRINE_CAP
        if doctrine and len(doctrine) <= doctrine_cap:
            compact_parts.append(doctrine)
        elif doctrine:
            compact_parts.append(cap_text_at_sentence(doctrine, doctrine_cap))
    compact_memory = (context.get("iteration_memory_snippet") or "").strip()
    if compact_memory and len(compact_memory) < _ni("compact_memory_cap"):
        compact_parts.append(compact_memory)
    blackboard_memory = (context.get("blackboard_learning_snippet") or "").strip()
    if blackboard_memory and len(blackboard_memory) < _ni("compact_memory_cap"):
        compact_parts.append(blackboard_memory)
    compact_body = compress_prompt_body(raw_prompt, material_key)
    compact_prelude = "\n\n".join(part for part in compact_parts if part)
    # Body-first budgeting: give the creative direction at least 40% of the
    # total budget.  Shrink the prelude to fit, never the body.
    total_cap = NON_INTERFACE_TOTAL_PRELUDE_CAP if material_key not in INTERFACE_MATERIAL_KEYS else 2000
    prelude_budget = max(total_cap - len(compact_body) - 4, int(total_cap * 0.3))
    if len(compact_prelude) > prelude_budget:
        compact_prelude = cap_text_at_sentence(compact_prelude, prelude_budget)
    refined_prompt = prefix_prompt(compact_prelude, compact_body, token_block=token_block or "")
    execution_prompt_payload = build_execution_prompt(
        raw_prompt,
        {
            **context,
            "refined_prompt": refined_prompt,
        },
        material_type=material_type,
        generation_mode=generation_mode,
    )

    # Surface a recommendation when the body was compressed so the agent
    # knows to summarize the prompt seed instead of letting the pipeline
    # silently drop creative direction.
    if execution_prompt_payload.get("body_compressed"):
        orig = execution_prompt_payload.get("body_original_chars", 0)
        comp = execution_prompt_payload.get("body_compressed_chars", 0)
        lost_pct = int((1 - comp / orig) * 100) if orig else 0
        recommendations.append(
            f"Prompt body was compressed from {orig} to {comp} chars ({lost_pct}% lost). "
            f"Summarize or shorten the --prompt-seed to avoid losing creative direction. "
            f"The pipeline preserves full sentences but drops lower-priority ones when over budget."
        )

    return {
        "material_key": material_key,
        "workflow_mode": workflow_mode or "",
        "issues": issues,
        "recommendations": recommendations,
        "reference_analysis_mode": analysis_mode,
        "reference_analysis_confidence": analysis_confidence,
        "reference_analysis_warning": analysis_warning,
        "reference_role_assignment_warnings": role_assignment_warnings,
        "policy_setup_risks": policy_setup_risks,
        "used_refined_prompt": bool(refined_prompt and refined_prompt != resolved_prompt),
        "refined_prompt": refined_prompt or resolved_prompt,
        "execution_prompt": execution_prompt_payload.get("execution_prompt") or refined_prompt or resolved_prompt,
        "execution_prompt_kind": execution_prompt_payload.get("execution_prompt_kind") or "",
        "execution_prompt_compressed": bool(execution_prompt_payload.get("execution_prompt_compressed")),
        "execution_prompt_sections": execution_prompt_payload.get("execution_prompt_sections") or {},
        "body_compressed": execution_prompt_payload.get("body_compressed", False),
        "body_original_chars": execution_prompt_payload.get("body_original_chars", 0),
        "body_compressed_chars": execution_prompt_payload.get("body_compressed_chars", 0),
        "prelude_chars": execution_prompt_payload.get("prelude_chars", 0),
        "resolved_prompt": resolved_prompt,
        "compact_role_pack": compact_roles,
        "reference_analysis_snippet": reference_analysis_snippet,
        "selected_inspiration_translation": selected_inspiration_translation,
        "selected_inspiration_ids": list(context.get("selected_inspiration_ids") or []),
        "selected_mechanic_ids": list(context.get("selected_mechanic_ids") or []),
        "inspiration_selection_reason": str(context.get("inspiration_selection_reason") or ""),
        "inspiration_selection_mode": str(context.get("inspiration_selection_mode") or ""),
        "compact_body": compact_body,
    }
