"""Sage-specific source/vault brief and generation contract helpers.

The generic brand-gen pipeline already carries brand guardrails, material
profiles, product-truth contracts, and iteration memory. Sage still needs a
shorter, higher-priority contract because the useful source language lives in
the Obsidian/docs vault and long prompt prose is routinely compressed before
generation. This module keeps that contract deterministic and compact.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .context_surfaces import build_source_knowledge_payload
from .product_truth import is_sage_capability_context
from .runtime_io import load_json_file
from .runtime_models import role_pack_material_key
from .runtime_support import dedupe_keep_order


SAGE_APPROVED_PHRASES: tuple[str, ...] = (
    "skill layer for AI agents",
    "Steer the Default",
    "curated skills improve agent performance by +16.2pp",
    "fat skills / thin harness",
    "someone has to govern the standard library",
    "agents find and use better workflows with less repeated setup",
)

SAGE_ILLUSTRATION_CONCEPTS: tuple[str, ...] = (
    "standard library / canon",
    "agent runtime receiving a default",
    "skill layer above thin harnesses",
    "curated capability selected from library, then used",
    "switchboard / exchange node",
    "control-room routing grid",
    "transit grid / route map",
)

SAGE_NEGATIVE_CONSTRAINTS: tuple[str, ...] = (
    "no thread/loom/wardrobe/textile/closet metaphor",
    "no trust layer as hero",
    "no governance process hero",
    "no generic marketplace/platform framing",
    "no raw prompt dump / random capability card deck / glowing light-bulb idea icon",
    "no repeated logos",
)

SAGE_BRAND_ANCHOR_SOURCES: tuple[str, ...] = (
    "palette",
    "routed/lattice/path motifs",
    "source/library/manifest object",
    "agent adoption/use scene",
    "deterministic typography or approved phrase",
)

SAGE_SWITCHBOARD_ADOPTION_SCENE = (
    "a Sage Manifest switchboard selects one reusable Behavior as the agent default; "
    "the thin harness immediately uses it to finish a visible task"
)

SAGE_SWITCHBOARD_STYLE_ANCHOR = (
    "editorial metaphor illustration: switchboard/control-room routing grid, "
    "warm palette, tactile print restraint"
)

_SAGE_STALE_POSITIVE_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    (
        "routing loom threads one reusable Behavior into a thin agent harness; the agent uses it as the default path to finish work",
        SAGE_SWITCHBOARD_ADOPTION_SCENE,
    ),
    (
        "routing loom threads one reusable Behavior into a thin agent harness",
        "Sage Manifest switchboard selects one reusable Behavior as the agent default",
    ),
    (
        "crafted routing loom where a Sage Manifest threads a reusable Behavior",
        "crafted switchboard/control-room routing grid where a Sage Manifest selects a reusable Behavior",
    ),
    ("routing loom / Behavior into harness", "switchboard / Behavior into harness"),
)

_SAGE_STALE_POSITIVE_TERMS: tuple[str, ...] = (
    "routing loom",
    "wardrobe",
    "threading",
    "threads ",
    "textile",
    "closet",
    "fabric",
    "sewing",
)

_SAGE_NEGATIVE_CONTEXT_TERMS: tuple[str, ...] = (
    "no ",
    "do not",
    "don't",
    "avoid",
    "ban",
    "banned",
    "without",
    "not from",
    "not a",
    "not the",
)

_DISCOURAGED_SAGE_CAPABILITY_MATERIALS = {
    "poster",
    "campaign_poster",
    "merch-poster",
    "merch_poster",
    "feature-illustration",
    "feature_illustration",
    "state-card",
    "state_card",
    "badge-family",
    "badge_family",
    "x-feed-square",
    "x_feed_square",
}

_SAGE_SYSTEM_HINTS = (
    "system",
    "workflow",
    "routing",
    "route",
    "runtime",
    "mechanism",
    "mechanic",
    "flow",
    "causal",
    "explainer",
    "manifest",
    "harness",
    "default path",
)

_SAGE_EDITORIAL_HINTS = (
    "metaphor",
    "editorial",
    "essay",
    "canon",
    "standard library",
    "story",
    "symbolic",
)

_SAGE_ACTION_HINTS = (
    "adopt",
    "adoption",
    "install",
    "installed",
    "use",
    "used",
    "using",
    "finish work",
    "completed output",
    "receiving",
    "selected",
    "powers",
    "powering",
)


def _clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def _haystack(*parts: Any) -> str:
    return " ".join(_clean_text(part).lower() for part in parts if _clean_text(part))


def _load_profile(brand_dir: Path, profile: dict[str, Any] | None = None) -> dict[str, Any]:
    if isinstance(profile, dict) and profile:
        return profile
    payload = load_json_file(brand_dir / "brand-profile.json")
    return payload if isinstance(payload, dict) else {}


def _source_knowledge_for_sage(
    brand_dir: Path,
    profile: dict[str, Any],
    identity: dict[str, Any],
) -> dict[str, Any]:
    try:
        return build_source_knowledge_payload(
            brand_dir,
            profile,
            identity,
            query=(
                "Sage skill layer AI agents Steer the Default fat skills thin harness "
                "standard library canon switchboard exchange node control room transit grid "
                "curated skills improve performance"
            ),
            limit=12,
            max_chars=900,
        )
    except Exception:
        return {"configured": False, "scanned_markdown_files": 0, "results": []}


def _matched_items(items: tuple[str, ...], source_payload: dict[str, Any]) -> list[str]:
    source_text = " ".join(str(item.get("excerpt") or "") for item in source_payload.get("results") or []).lower()
    matches = [item for item in items if item.lower() in source_text]
    return dedupe_keep_order(matches)


def _select_source_truth_phrase(text: str) -> str:
    lower = text.lower()
    if "16.2" in lower or "performance" in lower or "benchmark" in lower:
        return "curated skills improve agent performance by +16.2pp"
    if "default" in lower:
        return "Steer the Default"
    if "harness" in lower or "behavior" in lower or "runtime" in lower:
        return "fat skills / thin harness"
    if "canon" in lower or "standard library" in lower:
        return "someone has to govern the standard library"
    if "workflow" in lower or "less repeated setup" in lower:
        return "agents find and use better workflows with less repeated setup"
    return "skill layer for AI agents"


def _select_adoption_scene(text: str, material_type: str) -> str:
    lower = text.lower()
    material_key = role_pack_material_key(material_type) or str(material_type or "").lower()
    if "runtime" in lower or "default" in lower or "behavior" in lower or material_key == "editorial_metaphor_illustration":
        return SAGE_SWITCHBOARD_ADOPTION_SCENE
    if "standard library" in lower or "canon" in lower:
        return "a standard-library/canon object selects one capability and an agent uses it to complete work"
    if "mcp" in lower or "tool" in lower:
        return "a Sage Manifest exposes an MCP tool in the agent workbench and the agent uses it"
    return "curated capability is selected from a library, installed into an agent, then visibly used"


def _select_style_anchor(text: str, material_type: str) -> str:
    material_key = role_pack_material_key(material_type) or str(material_type or "").lower()
    if material_key == "system_explainer_illustration":
        return "mechanism-led system explainer with routed paths, library object, and agent use outcome"
    if material_key == "illustrated_brand_world":
        return "illustrated brand-world only where process/action is concrete; routed paths connect source to use"
    return SAGE_SWITCHBOARD_STYLE_ANCHOR


def _is_negative_constraint_text(text: str) -> bool:
    lowered = text.lower()
    return any(term in lowered for term in _SAGE_NEGATIVE_CONTEXT_TERMS)


def repair_stale_sage_contract_text(value: Any) -> tuple[str, bool]:
    """Repair stale positive Sage loom/thread wording without erasing bans.

    The v185-v188 traces showed that old positive contract language could keep
    re-entering fresh plans even after loom/wardrobe/thread metaphors were
    banned. Negative constraints such as "no thread/loom" should remain intact;
    only positive scene/style language is rewritten to the switchboard/default
    contract.
    """
    text = str(value or "")
    if not text:
        return "", False
    repaired = text
    for old, new in _SAGE_STALE_POSITIVE_REPLACEMENTS:
        repaired = re.sub(re.escape(old), new, repaired, flags=re.IGNORECASE)

    parts = re.split(r"([.!?;]\s+|\n+)", repaired)
    changed = repaired != text
    out_parts: list[str] = []
    for idx in range(0, len(parts), 2):
        sentence = parts[idx]
        sep = parts[idx + 1] if idx + 1 < len(parts) else ""
        lowered = sentence.lower()
        if not _is_negative_constraint_text(sentence) and any(term in lowered for term in _SAGE_STALE_POSITIVE_TERMS):
            new_sentence = sentence
            new_sentence = re.sub(r"\brouting loom\b", "switchboard/control-room routing grid", new_sentence, flags=re.IGNORECASE)
            new_sentence = re.sub(r"\bwardrobe\b", "standard-library shelf", new_sentence, flags=re.IGNORECASE)
            new_sentence = re.sub(r"\bthreads?\b", "routes", new_sentence, flags=re.IGNORECASE)
            new_sentence = re.sub(r"\btextile\b|\bfabric\b|\bsewing\b", "capability-routing", new_sentence, flags=re.IGNORECASE)
            new_sentence = re.sub(r"\bcloset\b", "library", new_sentence, flags=re.IGNORECASE)
            if new_sentence != sentence:
                changed = True
            sentence = new_sentence
        out_parts.append(sentence + sep)
    repaired = "".join(out_parts)
    return repaired, changed


def _normalize_sage_hard_bans(items: list[Any] | tuple[Any, ...] | None) -> list[str]:
    bans: list[str] = []
    for item in items or []:
        ban = _clean_text(item)
        if not ban:
            continue
        if "raw prompt dump" in ban.lower() and "random capability card deck" in ban.lower():
            ban = "no raw prompt dump / random capability card deck / glowing light-bulb idea icon"
        bans.append(ban)
    # Canonical order matters because the compact contract only carries the
    # first few bans through prompt compression.
    return dedupe_keep_order(list(SAGE_NEGATIVE_CONSTRAINTS) + bans)


def repair_stale_sage_plan_contract(plan: dict[str, Any] | None) -> tuple[dict[str, Any], list[str]]:
    """Return a plan with stale Sage loom/thread contract contamination repaired.

    This is intentionally a runtime guard as well as a planning helper: old
    plan artifacts may be reused as source traces, so scratchpad generation
    needs to normalize them before prompt assembly.
    """
    if not isinstance(plan, dict):
        return {}, []
    out = dict(plan)
    warnings: list[str] = []
    changed_fields: list[str] = []

    for key in ("prompt_seed", "product_truth_expression", "system_mechanic", "purpose", "target_surface", "briefing"):
        if key in out:
            repaired, changed = repair_stale_sage_contract_text(out.get(key) or "")
            if changed:
                out[key] = repaired
                changed_fields.append(key)

    for key in ("push", "preserve"):
        values = out.get(key)
        if isinstance(values, list):
            repaired_values = []
            changed_any = False
            for item in values:
                repaired, changed = repair_stale_sage_contract_text(item)
                repaired_values.append(repaired)
                changed_any = changed_any or changed
            if changed_any:
                out[key] = repaired_values
                changed_fields.append(key)

    ban_values = out.get("ban")
    if isinstance(ban_values, list):
        out["ban"] = dedupe_keep_order([str(item) for item in ban_values if str(item).strip()] + list(SAGE_NEGATIVE_CONSTRAINTS))
    elif "ban" in out:
        out["ban"] = dedupe_keep_order([str(ban_values)] + list(SAGE_NEGATIVE_CONSTRAINTS))

    for key in ("sage_generation_contract", "sage_vault_brief"):
        contract = out.get(key)
        if not isinstance(contract, dict) or not contract.get("applies"):
            continue
        next_contract = dict(contract)
        for field in ("adoption_scene", "style_anchor", "source_truth_phrase", "prompt_block"):
            if field in next_contract:
                repaired, changed = repair_stale_sage_contract_text(next_contract.get(field) or "")
                if changed:
                    next_contract[field] = repaired
                    changed_fields.append(f"{key}.{field}")
        adoption_scene = str(next_contract.get("adoption_scene") or "")
        if not adoption_scene or any(term in adoption_scene.lower() for term in ("routing loom", "thread", "wardrobe", "textile", "closet")):
            next_contract["adoption_scene"] = SAGE_SWITCHBOARD_ADOPTION_SCENE
            changed_fields.append(f"{key}.adoption_scene")
        style_anchor = str(next_contract.get("style_anchor") or "")
        if not style_anchor or any(term in style_anchor.lower() for term in ("routing loom", "thread", "wardrobe", "textile", "closet")):
            next_contract["style_anchor"] = SAGE_SWITCHBOARD_STYLE_ANCHOR
            changed_fields.append(f"{key}.style_anchor")
        next_contract["hard_bans"] = _normalize_sage_hard_bans(next_contract.get("hard_bans") or [])
        next_contract["negative_constraints"] = _normalize_sage_hard_bans(next_contract.get("negative_constraints") or [])
        next_contract["prompt_block"] = render_sage_generation_contract(next_contract)
        out[key] = next_contract

    if changed_fields:
        out["sage_contract_repair"] = {
            "applied": True,
            "changed_fields": dedupe_keep_order(changed_fields),
            "replacement_scene": SAGE_SWITCHBOARD_ADOPTION_SCENE,
            "reason": "Repaired stale v185-v188 routing-loom/thread contract contamination before generation.",
        }
        warnings.append(
            "Sage stale-contract repair: replaced old routing-loom/thread positive language with switchboard/default/adoption-use contract."
        )
    return out, warnings


def render_sage_generation_contract(brief: dict[str, Any] | None) -> str:
    if not isinstance(brief, dict) or not brief.get("applies"):
        return ""
    bans = _normalize_sage_hard_bans(brief.get("hard_bans") or [])
    return _clean_text(
        "Sage generation contract: "
        f"truth=\"{brief.get('source_truth_phrase') or 'skill layer for AI agents'}\"; "
        f"scene={brief.get('adoption_scene') or 'curated capability selected from library, then used'}; "
        f"style={brief.get('style_anchor') or 'editorial metaphor illustration'}; "
        f"logo={brief.get('logo_rule') or 'one small provenance seal only, never repeated'}; "
        f"bans={'; '.join(bans[:5])}."
    )


def build_sage_vault_brief(
    *,
    brand_dir: Path,
    identity: dict[str, Any],
    profile: dict[str, Any] | None = None,
    material_type: str = "",
    purpose: str = "",
    target_surface: str = "",
    product_truth_expression: str = "",
    prompt_seed: str = "",
    briefing: str = "",
) -> dict[str, Any]:
    plan_stub = {
        "brand_dir": str(brand_dir),
        "material_type": material_type,
        "purpose": purpose,
        "target_surface": target_surface,
        "product_truth_expression": product_truth_expression,
        "prompt_seed": prompt_seed or briefing,
    }
    if not is_sage_capability_context(identity=identity, plan=plan_stub):
        return {"applies": False}

    resolved_profile = _load_profile(brand_dir, profile)
    source_payload = _source_knowledge_for_sage(brand_dir, resolved_profile, identity)
    text = _haystack(
        material_type,
        purpose,
        target_surface,
        product_truth_expression,
        prompt_seed,
        briefing,
        " ".join(str(item.get("excerpt") or "") for item in source_payload.get("results") or []),
    )
    brief: dict[str, Any] = {
        "applies": True,
        "source": "source_knowledge" if source_payload.get("configured") else "canonical_sage_contract",
        "source_truth_phrase": _select_source_truth_phrase(text),
        "adoption_scene": _select_adoption_scene(text, material_type),
        "style_anchor": _select_style_anchor(text, material_type),
        "logo_rule": "one small Sage provenance/source seal only; never repeated, never the hero",
        "hard_bans": list(SAGE_NEGATIVE_CONSTRAINTS),
        "approved_phrases": list(SAGE_APPROVED_PHRASES),
        "illustration_concepts": list(SAGE_ILLUSTRATION_CONCEPTS),
        "negative_constraints": list(SAGE_NEGATIVE_CONSTRAINTS),
        "brand_anchor_sources": list(SAGE_BRAND_ANCHOR_SOURCES),
        "source_knowledge": {
            "configured": bool(source_payload.get("configured")),
            "scanned_markdown_files": int(source_payload.get("scanned_markdown_files") or 0),
            "matched_phrases": _matched_items(SAGE_APPROVED_PHRASES, source_payload),
            "matched_concepts": _matched_items(SAGE_ILLUSTRATION_CONCEPTS, source_payload),
            "result_titles": [
                str(item.get("title") or item.get("relpath") or "").strip()
                for item in (source_payload.get("results") or [])[:5]
                if str(item.get("title") or item.get("relpath") or "").strip()
            ],
        },
    }
    brief["prompt_block"] = render_sage_generation_contract(brief)
    return brief


def sage_generation_contract_seed(brief: dict[str, Any] | None) -> str:
    if not isinstance(brief, dict) or not brief.get("applies"):
        return ""
    bans = _normalize_sage_hard_bans(brief.get("hard_bans") or [])
    return _clean_text(
        f"Sage source truth: {brief.get('source_truth_phrase')}. "
        f"Adoption/use scene: {brief.get('adoption_scene')}. "
        f"Logo rule: {brief.get('logo_rule')}. "
        "Hard bans: " + "; ".join(bans[:5]) + "."
    )


def apply_sage_brand_anchor_policy(policy: dict[str, Any], brief: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(brief, dict) or not brief.get("applies"):
        return policy
    out = dict(policy or {})
    out["logo_mode"] = "preferred"
    out["clearly_branded_without_logo_min"] = 4
    out["acceptable_anchors"] = list(SAGE_BRAND_ANCHOR_SOURCES)
    out["logo_rule"] = brief.get("logo_rule") or "one small Sage provenance/source seal only"
    out["rule"] = (
        "For Sage explanatory/capability assets, branding comes from palette, "
        "routed/lattice/path motifs, source/library/manifest objects, an agent "
        "adoption/use scene, and deterministic typography or approved phrases. "
        "Use at most one small Sage logo/mark as provenance, not as the story."
    )
    return out


def rewrite_sage_explanatory_brand_prelude(prelude: str, brief: dict[str, Any] | None) -> str:
    """Neutralize older Sage guardrail copy that made the logo the primary symbol."""
    if not prelude or not isinstance(brief, dict) or not brief.get("applies"):
        return prelude
    rewritten = prelude.replace(
        "preserve approved brand devices such as the stored logo or mark silhouette as the primary symbol,",
        (
            "preserve approved brand devices while making palette, routed/lattice/path motifs, "
            "source/library objects, and agent adoption scenes the primary brand anchors; "
            "keep any stored logo or mark silhouette as a small provenance seal,"
        ),
    )
    if rewritten == prelude:
        rewritten = (
            prelude.rstrip()
            + " Sage explanatory/capability override: brand from palette, routed/lattice/path motifs, "
            "source/library/manifest objects, and agent adoption/use scenes; at most one small logo as provenance."
        )
    return rewritten


def resolve_sage_capability_material_type(
    material_type: str,
    *,
    brand_dir: Path,
    identity: dict[str, Any],
    purpose: str = "",
    target_surface: str = "",
    prompt_seed: str = "",
    briefing: str = "",
    product_truth_expression: str = "",
    render_backend: str | None = None,
    source_url: str | None = None,
    entity_type: str | None = None,
) -> tuple[str, str]:
    """Route Sage capability illustration work away from card/template defaults."""
    key = str(material_type or "").strip().lower()
    if not key:
        return key, ""
    plan_stub = {
        "brand_dir": str(brand_dir),
        "material_type": key,
        "purpose": purpose,
        "target_surface": target_surface,
        "product_truth_expression": product_truth_expression,
        "prompt_seed": prompt_seed or briefing,
        "source_url": source_url or "",
        "entity_type": entity_type or "",
    }
    if not is_sage_capability_context(identity=identity, plan=plan_stub):
        return key, ""
    if str(render_backend or "").strip().lower() == "html":
        return key, ""

    material_key = role_pack_material_key(key) or key.replace("-", "_")
    text = _haystack(key, purpose, target_surface, prompt_seed, briefing, product_truth_expression)
    brief_text = _haystack(purpose, target_surface, prompt_seed, briefing, product_truth_expression)
    wants_native_illustration = any(
        token in text
        for token in (
            "illustration",
            "native",
            "artwork",
            "metaphor",
            "explainer",
            "brand world",
            "capability work",
        )
    )
    source_brief_strong = any(
        token in brief_text
        for token in (
            "skill layer",
            "steer the default",
            "fat skills",
            "thin harness",
            "standard library",
            "canon",
            "manifest",
            "behavior",
            "runtime",
            "curated capability",
            "agent",
        )
    )
    has_real_product_carrier = bool(str(source_url or "").strip()) or any(
        token in brief_text for token in ("screenshot", "screen", "actual ui", "real product")
    )

    if material_key == "illustrated_brand_world" and not any(token in brief_text for token in _SAGE_ACTION_HINTS):
        return (
            "editorial-metaphor-illustration",
            "Sage illustrated-brand-world was routed to editorial-metaphor-illustration because brand-world work needs a concrete adoption/use action; otherwise it drifts into mood.",
        )

    if material_key == "system_explainer_illustration" and not (
        source_brief_strong and any(token in brief_text for token in _SAGE_SYSTEM_HINTS)
    ):
        return (
            "editorial-metaphor-illustration",
            "Sage system-explainer-illustration was routed to editorial-metaphor-illustration because system explainers need a strong sourced mechanism brief.",
        )

    if material_key == "feature_illustration" and not has_real_product_carrier:
        if source_brief_strong and any(token in brief_text for token in _SAGE_SYSTEM_HINTS):
            return (
                "system-explainer-illustration",
                "Sage feature-illustration was routed to system-explainer-illustration because there is no real base/product screenshot; use a sourced mechanism instead of an interface/base-image path.",
            )
        return (
            "editorial-metaphor-illustration",
            "Sage feature-illustration was routed to editorial-metaphor-illustration because there is no real base/product screenshot; avoid fake interface/product surfaces.",
        )

    if material_key in _DISCOURAGED_SAGE_CAPABILITY_MATERIALS and (wants_native_illustration or material_key in {"poster", "merch_poster"}):
        if source_brief_strong and any(token in brief_text for token in _SAGE_SYSTEM_HINTS) and not any(token in brief_text for token in _SAGE_EDITORIAL_HINTS):
            return (
                "system-explainer-illustration",
                "Sage capability work was routed away from generic card/poster/template materials toward a sourced system explainer.",
            )
        return (
            "editorial-metaphor-illustration",
            "Sage capability work was routed away from generic card/poster/template materials toward an editorial metaphor illustration.",
        )

    return key, ""


__all__ = [
    "SAGE_APPROVED_PHRASES",
    "SAGE_BRAND_ANCHOR_SOURCES",
    "SAGE_ILLUSTRATION_CONCEPTS",
    "SAGE_NEGATIVE_CONSTRAINTS",
    "apply_sage_brand_anchor_policy",
    "build_sage_vault_brief",
    "repair_stale_sage_contract_text",
    "repair_stale_sage_plan_contract",
    "render_sage_generation_contract",
    "resolve_sage_capability_material_type",
    "rewrite_sage_explanatory_brand_prelude",
    "sage_generation_contract_seed",
]
