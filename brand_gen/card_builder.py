"""Card payload construction and entity defaults.

Depends on: ``card_engine``, ``card_text``, ``card_plugins``,
``surface_strategy``, ``runtime``, ``runtime_refs``.
"""
from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

from .card_engine import (
    DEFAULT_DESIGN_VARIANCE,
    DEFAULT_HTML_MODEL,
    LayoutSpec,
    ShareCardPayload,
    _entity_proof_title,
    _surface_label,
    default_layout_spec,
)
from .card_plugins import fetch_card_page_data
from .card_text import (
    _clean_sage_title,
    _is_procedural_line,
    _prompt_body_lines,
    _rank_share_card_lines,
    _select_excerpt,
    _select_row,
    _select_short_lines,
    _truncate_multiline_copy,
)
from .runtime import load_brand_memory, validate_brand_workspace_dir
from .runtime_refs import resolve_brand_asset_paths
from .surface_strategy import (
    load_composition_profile,
    load_surface_strategy_definition,
    resolve_share_template_preferences,
)


# ---------------------------------------------------------------------------
# Entity inference
# ---------------------------------------------------------------------------

def _infer_entity_type(url: str, explicit: str | None = None) -> str:
    if explicit:
        return explicit.strip().lower()
    path = urlparse(url).path.lower()
    for key in ("prompt", "skill", "library", "proposal", "community", "dao", "update"):
        if key in path:
            return key
    if "governance" in path:
        return "proposal"
    return "prompt"


# ---------------------------------------------------------------------------
# Entity default helpers
# ---------------------------------------------------------------------------

def _cta_for_entity(entity_type: str) -> str:
    return {
        "prompt": "Open prompt",
        "skill": "Open skill",
        "library": "Open library",
        "profile": "Open profile",
        "proposal": "View proposal",
        "community": "View community",
        "dao": "View DAO",
        "update": "Read update",
    }.get(entity_type, "Open source artifact")


def _proof_weight_for(material_type: str) -> str:
    if material_type == "social":
        return "Proof should occupy roughly 28–35% of the composition and stay fully readable."
    if material_type == "x-feed":
        return "Proof should occupy a clear right-side module with readable text and no overlapping decorative render."
    return "Proof should be medium-sized and legible; do not reduce it to a tiny chip or bury it near the edge."


def _default_proof_meta(entity_type: str) -> list[str]:
    return {
        "prompt": ["Prompt", "Governed", "Reusable capability"],
        "skill": ["Skill", "Composable", "Agent-ready"],
        "library": ["Library", "Versioned", "Governed collection"],
        "proposal": ["Proposal", "Governance", "On-chain vote"],
        "community": ["Community", "Collaborative", "Open membership"],
        "dao": ["DAO", "Decentralized", "Token-governed"],
        "update": ["Update", "Changelog", "Protocol news"],
    }.get(entity_type, ["Governed", "Trusted", "Distributed"])


def _default_proof_excerpt(entity_type: str) -> str:
    return {
        "prompt": "Reusable prompts and capabilities distributed through the current CLI and MCP tools.",
        "skill": "Composable agent skills governed on-chain and installed through the current CLI tooling.",
        "library": "Curated prompt libraries versioned and governed through the current protocol.",
        "proposal": "Community governance proposals decided through on-chain voting.",
        "community": "Open communities collaborating through shared prompt libraries and governance.",
        "dao": "Decentralized organizations governing shared prompt infrastructure.",
        "update": "Protocol updates and feature announcements from the current team.",
    }.get(entity_type, "Trusted capabilities distributed through the current CLI and MCP tools.")


def _select_composition_profile(
    *,
    material_type: str,
    entity_type: str,
    selected_strategy: str,
    design_variance: int,
) -> dict[str, Any]:
    strategy = load_surface_strategy_definition(selected_strategy)
    modes = list(strategy.get("composition_modes") or [])
    if not modes:
        modes = ["artifact_sheet"] if material_type == "announcement-card" else ["excerpt_card"]
    if design_variance <= 3:
        index = 0
    elif design_variance <= 5:
        index = 1
    elif design_variance <= 7:
        index = 2
    else:
        index = 3
    index = min(index, len(modes) - 1)
    mode = str(modes[index] or modes[0])
    profile = dict(load_composition_profile(mode) or load_composition_profile("artifact_sheet"))
    profile["mode"] = str(profile.get("key") or mode)
    profile["asset_slots"] = list(strategy.get("asset_slots") or profile.get("asset_slots") or [])
    return profile


# ---------------------------------------------------------------------------
# Main payload builder
# ---------------------------------------------------------------------------

def build_web_app_share_card_payload(payload: dict) -> ShareCardPayload:
    material_type = str(payload.get("material_type") or "social").strip()
    source_url = str(payload.get("source_url") or "").strip()
    entity_type = _infer_entity_type(source_url, payload.get("entity_type"))

    # --- Plugin-based data fetching ---
    page = (
        fetch_card_page_data(source_url, entity_type)
        or ({"title": "", "description": "", "h1": "", "h2": "", "lines": []})
    )

    source_domain = urlparse(source_url).netloc or "app.sageprotocol.io"

    profile_path = payload.get("profile_path") or None
    identity_path = payload.get("identity_path") or None
    brand_dir = validate_brand_workspace_dir(payload.get("brand_dir") or "", label="html share-card brand_dir")
    _, _, profile, identity = load_brand_memory(brand_dir, profile_path, identity_path)
    brand_name = str(profile.get("brand_name") or (identity.get("brand", {}) or {}).get("name", "")).strip()
    logo_candidates = resolve_brand_asset_paths(profile, identity, brand_dir=brand_dir)
    logo_path = str(logo_candidates[0]) if logo_candidates else ""
    template = resolve_share_template_preferences(
        entity_type,
        source_url=source_url,
        brand_dir=brand_dir,
        identity=identity,
    )
    structured_card = page.get("share_card") if isinstance(page.get("share_card"), dict) else {}

    plan = payload.get("plan") or {}
    selected_strategy = str(
        payload.get("selected_surface_strategy")
        or plan.get("selected_surface_strategy")
        or template.get("selected_surface_strategy")
        or ""
    ).strip()
    strategy_definition = load_surface_strategy_definition(selected_strategy)
    selected_strategy_label = str(
        payload.get("selected_surface_strategy_label")
        or plan.get("selected_surface_strategy_label")
        or strategy_definition.get("label")
        or ""
    ).strip()
    selected_strategy_summary = str(
        payload.get("selected_surface_strategy_summary")
        or plan.get("selected_surface_strategy_summary")
        or strategy_definition.get("summary")
        or ""
    ).strip()
    selected_strategy_layout_family = str(
        payload.get("selected_surface_strategy_layout_family")
        or plan.get("selected_surface_strategy_layout_family")
        or strategy_definition.get("layout_family")
        or ""
    ).strip()
    surface_strategy_reason = str(
        payload.get("surface_strategy_reason")
        or plan.get("surface_strategy_reason")
        or ""
    ).strip()
    composition_profile = _select_composition_profile(
        material_type=material_type,
        entity_type=entity_type,
        selected_strategy=selected_strategy,
        design_variance=int(payload.get("design_variance") or DEFAULT_DESIGN_VARIANCE),
    )
    preferred_mode = str(template.get("preferred_composition_mode") or "").strip()
    if preferred_mode:
        preferred_profile = dict(load_composition_profile(preferred_mode) or {})
        if preferred_profile:
            preferred_profile["mode"] = str(preferred_profile.get("key") or preferred_mode)
            composition_profile = preferred_profile
    headline = str(
        payload.get("headline")
        or structured_card.get("headline")
        or page.get("h1")
        or page.get("title")
        or plan.get("purpose")
        or "Governed share card"
    ).strip()
    if entity_type == "prompt":
        normalized_headline = _clean_sage_title(headline)
        if " - " in normalized_headline:
            head_prefix = normalized_headline.split(" - ", 1)[0].strip()
            if len(head_prefix) >= 6:
                normalized_headline = head_prefix
        headline = normalized_headline or headline
    subhead = str(
        payload.get("subhead")
        or structured_card.get("subhead")
        or page.get("description")
        or page.get("h2")
        or ""
    ).strip()
    exclusions = {headline, subhead, page.get("title") or "", page.get("h1") or "", page.get("h2") or ""}
    ranked_lines = _rank_share_card_lines(page.get("lines") or [], entity_type=entity_type, exclusions=exclusions)
    prompt_body_lines = (
        _prompt_body_lines(
            page.get("lines") or [],
            exclusions,
            limit=12 if material_type == "announcement-card" else 7,
        )
        if entity_type == "prompt"
        else []
    )
    proof_meta = [item for item in (payload.get("proof_meta") or structured_card.get("proof_meta") or []) if str(item).strip()]
    if entity_type == "prompt" and not payload.get("proof_meta"):
        proof_meta = []
    if not proof_meta and entity_type != "prompt":
        proof_meta = [line for line in ranked_lines if 10 <= len(line) <= 52][:3]
    if not proof_meta and entity_type != "prompt":
        proof_meta = _select_short_lines(page.get("lines") or [], exclusions)
    if not proof_meta and entity_type != "prompt":
        proof_meta = _default_proof_meta(entity_type)
    raw_proof_title = str(payload.get("proof_title") or structured_card.get("proof_title") or "").strip()
    if not raw_proof_title:
        for candidate in [page.get("h2"), page.get("h1"), page.get("title")]:
            candidate_str = str(candidate or "").strip()
            normalized_candidate = _clean_sage_title(candidate_str).lower()
            normalized_headline = _clean_sage_title(headline).lower()
            if (
                candidate_str
                and normalized_candidate != normalized_headline
                and not re.fullmatch(r"[a-z0-9._-]+", candidate_str.lower())
                and not _is_procedural_line(candidate_str)
            ):
                raw_proof_title = candidate_str
                break
    proof_title = raw_proof_title or ("" if entity_type == "prompt" and prompt_body_lines else _entity_proof_title(entity_type))
    prompt_excerpt = "\n".join(prompt_body_lines[:7]).strip()
    proof_excerpt = str(
        payload.get("proof_excerpt")
        or structured_card.get("proof_excerpt")
        or (prompt_excerpt if entity_type == "prompt" and prompt_excerpt else "")
        or next((line for line in ranked_lines if 34 <= len(line) <= 180 and line not in proof_meta), "")
        or _select_excerpt(page.get("lines") or [], exclusions, fallback="")
        or subhead
        or _default_proof_excerpt(entity_type)
    ).strip()
    prompt_row = ""
    if entity_type == "prompt" and prompt_body_lines:
        remaining_prompt_lines = prompt_body_lines[7:10]
        if remaining_prompt_lines:
            prompt_row = "\n".join(remaining_prompt_lines)
        elif page.get("cid"):
            prompt_row = f"CID: {str(page.get('cid'))[:16]}…"
    proof_row = str(
        payload.get("proof_row")
        or structured_card.get("proof_row")
        or prompt_row
        or next(
            (
                line
                for line in ranked_lines
                if 18 <= len(line) <= 96 and line not in proof_meta and line != proof_excerpt
            ),
            "",
        )
        or _select_row(page.get("lines") or [], exclusions)
    ).strip()
    if not proof_row or proof_row == proof_excerpt:
        proof_row = {
            "prompt": "Curated prompt coverage for UI systems, interaction, and implementation detail.",
            "skill": "Reusable skill coverage for real agent workflows and implementation detail.",
            "library": "Governed library context surfaced for scanning and feed-speed recognition.",
        }.get(entity_type, "Trusted distribution through the current CLI and MCP tools")
    cta = str(payload.get("cta") or template.get("cta") or structured_card.get("cta") or _cta_for_entity(entity_type)).strip()
    detail_label = str(template.get("detail_label") or structured_card.get("detail_label") or "").strip()
    detail_blocks = payload.get("detail_blocks") or structured_card.get("detail_blocks") or []
    if not isinstance(detail_blocks, list):
        detail_blocks = []
    proof_crop_path = str(payload.get("proof_crop_path") or "").strip()
    support_crop_path = proof_crop_path

    design_variance = int(payload.get("design_variance") or DEFAULT_DESIGN_VARIANCE)
    raw_layout = payload.get("layout_spec")
    layout = (
        LayoutSpec.from_dict(raw_layout)
        if isinstance(raw_layout, dict)
        else default_layout_spec(
            material_type,
            design_variance,
            entity_type=entity_type,
            selected_strategy=selected_strategy,
        )
    )
    if material_type == "announcement-card" and entity_type in {"prompt", "skill", "library", "profile", "community", "dao"}:
        layout.columns = 2
        layout.alignment = "left"
        if not str(layout.canvas_preset or "").strip():
            layout.canvas_preset = "document"

    return ShareCardPayload(
        material_type=material_type,
        surface=_surface_label(material_type, entity_type=entity_type, layout_spec=layout),
        entity_type=entity_type,
        source_url=source_url,
        source_domain=source_domain,
        page_title=str(page.get("title") or headline).strip(),
        headline=headline,
        subhead=subhead,
        cta=cta,
        detail_label=detail_label,
        detail_blocks=detail_blocks[:6],
        logo_path=logo_path,
        proof_title=proof_title,
        proof_meta=proof_meta[:3],
        proof_excerpt=proof_excerpt,
        proof_row=proof_row,
        proof_crop_path=proof_crop_path,
        proof_weight_guidance=_proof_weight_for(material_type),
        support_crop_path=support_crop_path,
        brand_name=brand_name,
        render_model=str(payload.get("render_model") or DEFAULT_HTML_MODEL),
        selected_surface_strategy=selected_strategy,
        selected_surface_strategy_label=selected_strategy_label,
        selected_surface_strategy_summary=selected_strategy_summary,
        selected_surface_strategy_layout_family=selected_strategy_layout_family,
        surface_strategy_reason=surface_strategy_reason,
        design_variance=design_variance,
        composition_mode=str(composition_profile.get("mode") or ""),
        composition_summary=str(composition_profile.get("summary") or ""),
        composition_asset_slots=list(composition_profile.get("asset_slots") or []),
        layout_spec=layout,
        skip_proof=bool(payload.get("skip_proof")),
        dark_mode=bool(payload.get("dark_mode")),
    )
