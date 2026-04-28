"""Card payload construction and entity defaults.

Depends on: ``card_engine``, ``card_text``, ``card_plugins``,
``surface_strategy``, ``runtime``, ``runtime_refs``.
"""
from __future__ import annotations

import re
from pathlib import Path
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
    if not str(url or "").strip():
        return "artifact"
    path = urlparse(url).path.lower()
    for key in ("prompt", "skill", "library", "proposal", "community", "dao", "update"):
        if key in path:
            return key
    if "governance" in path:
        return "proposal"
    return "artifact"


def _slugify_sage_key(value: str) -> str:
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", str(value or "").lower())).strip("-")


def _local_sage_skill_keys() -> list[str]:
    """Return locally installed Sage/Codex skill keys for source-url inference."""
    home = Path.home()
    keys: set[str] = set()
    for base in [
        home / ".local/share/sage/skills",
        home / ".local/share/sage/skills/index",
        home / ".codex/skills",
        home / ".pi/agent/skills",
    ]:
        if not base.exists():
            continue
        try:
            for child in base.iterdir():
                name = child.stem if child.suffix == ".json" else child.name
                slug = _slugify_sage_key(name)
                if slug and not slug.startswith(".") and slug not in {"index", "versions"}:
                    keys.add(slug)
        except OSError:
            continue
    return sorted(keys)


def _candidate_skill_slugs_from_payload(payload: dict) -> list[str]:
    """Infer likely skill keys from explicit skill/bundle language."""
    texts = [
        payload.get("source_key"),
        payload.get("skill_key"),
        payload.get("proof_title"),
        payload.get("headline"),
        payload.get("raw_prompt"),
        payload.get("effective_prompt"),
        payload.get("execution_prompt"),
    ]
    candidates: list[str] = []

    def add(value: str) -> None:
        slug = _slugify_sage_key(value)
        if slug and 3 <= len(slug) <= 80 and slug not in candidates:
            candidates.append(slug)

    for raw in texts:
        text = str(raw or "")
        if not text:
            continue
        for match in re.finditer(r"\b(?:skill|source)\s*(?:key|id|slug)?\s*[:=]\s*([a-z0-9][a-z0-9_.-]{2,80})", text, re.I):
            add(match.group(1))
        for match in re.finditer(r"/skills/([a-z0-9][a-z0-9_.-]{2,80})", text, re.I):
            add(match.group(1))
        for match in re.finditer(r"\b([a-z0-9][a-z0-9_.-]{2,80})\s+(?:skill|skill\s+bundle|bundle)\b", text, re.I):
            add(match.group(1))

    # Titles are useful when they are clearly a named skill, e.g. "X Intel Briefing".
    title = str(payload.get("proof_title") or "").strip()
    if title:
        add(title)
    return candidates


def _best_local_skill_key(candidates: list[str]) -> str:
    local_keys = _local_sage_skill_keys()
    if not candidates:
        return ""
    if not local_keys:
        return candidates[0]
    best_key = ""
    best_score = 0.0
    for candidate in candidates:
        cand_tokens = set(candidate.split("-"))
        for key in local_keys:
            key_tokens = set(key.split("-"))
            score = 0.0
            if key == candidate:
                score += 100
            if key.startswith(candidate + "-") or candidate.startswith(key + "-"):
                score += 60
            overlap = len(cand_tokens & key_tokens)
            score += overlap * 12
            if cand_tokens and cand_tokens <= key_tokens:
                score += 25
            if score > best_score:
                best_key = key
                best_score = score
    return best_key if best_score >= 24 else ""


def _infer_sage_skill_source_url(payload: dict, *, material_type: str, entity_type: str) -> str:
    """Auto-link skill proof posters to the real skill page when the prompt names it."""
    if entity_type != "skill" or material_type != "proof-poster":
        return ""
    key = _best_local_skill_key(_candidate_skill_slugs_from_payload(payload))
    return f"https://app.sageprotocol.io/skills/{key}" if key else ""


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
        "artifact": "",
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
        "artifact": ["Capability", "Portable", "Agent-ready"],
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
        "artifact": "Reusable capabilities packaged for agent runtimes through Sage libraries and manifests.",
    }.get(entity_type, "Trusted capabilities distributed through the current CLI and MCP tools.")


_PRIVATE_META_RE = re.compile(
    r"\b(private\s+preview|preview\s+code|access\s+password|password|sign\s*in|log\s*in|login|auth|authentication)\b",
    re.IGNORECASE,
)
_GENERIC_PROOF_TITLES = {
    "prompt coverage",
    "skill coverage",
    "library snapshot",
    "artifact snapshot",
    "capability proof",
}


def _payload_plan_blob(payload: dict, plan: dict | None = None) -> str:
    plan = plan or {}
    values = [
        payload.get("headline"),
        payload.get("subhead"),
        payload.get("proof_title"),
        payload.get("proof_excerpt"),
        payload.get("proof_row"),
        payload.get("raw_prompt"),
        payload.get("effective_prompt"),
        payload.get("execution_prompt"),
        plan.get("purpose"),
        plan.get("target_surface"),
        plan.get("product_truth_expression"),
        plan.get("prompt_seed"),
    ]
    return " ".join(str(value or "") for value in values if str(value or "").strip()).lower()


def _material_default_strategy(material_type: str, payload: dict, plan: dict | None = None) -> str:
    """Choose a material-first HTML strategy when no explicit strategy exists.

    Brand share templates are entity defaults; they should not turn every
    no-source social/editorial/proof request into the same prompt-detail card.
    """
    material = str(material_type or "").strip().lower()
    blob = _payload_plan_blob(payload, plan)
    if material == "proof-poster":
        return "operator_proof_board"
    if material in {"social", "x-feed"}:
        if any(token in blob for token in ("capability", "skill", "mcp", "behavior", "workflow", "manifest")):
            return "capability_card"
        return "compact_proof_card"
    if material in {"editorial-card", "content-card", "content-card-square", "info-card", "data-card", "process-card", "quote-card", "linkedin-card", "og-card", "carousel-slide"}:
        return "editorial_poster"
    return ""


def _artifact_title_from_context(payload: dict, plan: dict | None = None) -> str:
    blob = _payload_plan_blob(payload, plan)
    if "manifest" in blob:
        return "Sage Manifest"
    if "behavior" in blob:
        return "Behavior"
    if "mcp" in blob or "tool" in blob:
        return "MCP Tool"
    if "skill" in blob:
        return "Skill"
    if "prompt" in blob:
        return "Prompt"
    if "library" in blob:
        return "Library"
    return "Capability Proof"


def _artifact_excerpt_from_context(payload: dict, plan: dict | None = None) -> str:
    blob = _payload_plan_blob(payload, plan)
    if "manifest" in blob:
        return "A Sage manifest packages prompts, skills, MCP tools, and behaviors as portable capability artifacts for agents."
    if all(token in blob for token in ("prompt", "skill")) or "capability family" in blob or "capability-family" in blob:
        return "Prompts, skills, MCP tools, and behaviors become reusable capabilities agents can discover and run."
    if "library" in blob:
        return "A Sage library turns curated prompts and skills into governed capabilities agents can reuse."
    if "skill" in blob:
        return "A Sage skill captures repeatable workflow judgment so agents can reuse it across sessions."
    return _default_proof_excerpt("artifact")


def _looks_like_operator_workflow_payload(payload: dict, plan: dict | None = None) -> bool:
    plan = plan or {}
    blob = " ".join(
        str(value or "")
        for value in [
            payload.get("headline"),
            payload.get("subhead"),
            payload.get("proof_title"),
            payload.get("proof_excerpt"),
            payload.get("proof_row"),
            payload.get("raw_prompt"),
            payload.get("effective_prompt"),
            payload.get("execution_prompt"),
            plan.get("purpose"),
            plan.get("target_surface"),
            plan.get("product_truth_expression"),
        ]
    ).lower()
    return (
        "→" in blob
        or "->" in blob
        or any(token in blob for token in ("workflow", "operator", "briefing", "brief", "artifact extraction", "corroboration", "signal scoring", "x-feed", "x intel"))
    )


def _sanitize_proof_meta(items: list[str], *, material_type: str = "") -> list[str]:
    banned = {
        "when to use",
        "when not to use",
        "don't use when",
        "do not use when",
        "overview",
        "procedure",
        "workflow",
        "pitfalls",
        "requirements",
        "setup",
        "the important mental model",
        "important mental model",
        "mental model",
    }
    out: list[str] = []
    for item in items or []:
        text = str(item or "").strip()
        if not text or _PRIVATE_META_RE.search(text):
            continue
        if material_type == "proof-poster" and text.strip().lower() in banned:
            continue
        if material_type == "proof-poster" and len(text) > 34:
            continue
        if text not in out:
            out.append(text)
    return out


_WORKFLOW_LABEL_CANON = {
    "ingest": "Ingest",
    "clean": "Clean",
    "extract": "Extract",
    "score": "Score",
    "corroborate": "Corroborate",
    "brief": "Brief",
}
_WORKFLOW_LABEL_BODIES = {
    "Ingest": "timeline, bookmarks, targeted source set",
    "Clean": "dedupe, normalize, remove feed noise",
    "Extract": "claims, artifacts, capability clues",
    "Score": "relevance, confidence, operator priority",
    "Corroborate": "repo/docs evidence check",
    "Brief": "operator-ready guidance",
}


def _extract_requested_workflow_labels(*texts: str) -> list[str]:
    """Pull explicit deterministic proof-poster row labels from the operator prompt."""
    for raw in texts:
        text = str(raw or "")
        if not text:
            continue
        for match in re.finditer(
            r"\b(?:five|5)?\s*(?:evidence|workflow|proof|step)\s+rows?\s*:\s*([^.\n]+)",
            text,
            flags=re.IGNORECASE,
        ):
            labels: list[str] = []
            for part in re.split(r"\s*(?:,|→|->|;|\band\b)\s*", match.group(1)):
                key = re.sub(r"[^a-z]+", " ", part.lower()).strip()
                if key in _WORKFLOW_LABEL_CANON:
                    label = _WORKFLOW_LABEL_CANON[key]
                    if label not in labels:
                        labels.append(label)
            if 4 <= len(labels) <= 6:
                return labels[:5]
    return []


def _workflow_excerpt_from_labels(labels: list[str]) -> str:
    return " → ".join(
        f"{label}: {_WORKFLOW_LABEL_BODIES.get(label, 'workflow evidence')}"
        for label in labels[:5]
    )


def _looks_like_instruction_headline(text: str) -> bool:
    value = str(text or "").strip().lower()
    if len(value) > 96 and re.match(r"^(create|generate|make|design|build|turn|show)\b", value):
        return True
    return len(value) > 120 and any(token in value for token in (" supplied ", " requested ", " using ", " into a "))


def _extract_subject_from_instruction(*texts: str) -> str:
    for raw in texts:
        text = str(raw or "").strip()
        if not text:
            continue
        match = re.search(
            r"\bsupplied\s+(.{8,96}?)(?:\s+(?:skill|prompt|library|bundle|workflow)\b|\s+into\b|[:.])",
            text,
            flags=re.IGNORECASE,
        )
        if not match:
            continue
        subject = match.group(1).strip(" .:;—-")
        subject = re.split(r"\s*/\s*|\s+\+\s+|\s+&\s+", subject)[0].strip(" .:;—-")
        if 4 <= len(subject) <= 48 and not _looks_like_instruction_headline(subject):
            return subject
    return ""


def _curate_proof_poster_headline(headline: str, payload: dict, *, proof_title: str = "", proof_excerpt: str = "") -> str:
    raw = str(headline or "").strip()
    proof_title_norm = _slugify_sage_key(proof_title)
    raw_norm = _slugify_sage_key(raw)
    if raw and len(raw) <= 72 and not _looks_like_instruction_headline(raw) and raw_norm != proof_title_norm:
        return raw
    blob = " ".join(
        str(value or "")
        for value in [
            raw,
            proof_title,
            proof_excerpt,
            payload.get("proof_row"),
            payload.get("raw_prompt"),
            payload.get("effective_prompt"),
            payload.get("execution_prompt"),
        ]
    ).lower()
    if any(token in blob for token in ("x intel", "x-feed", "twitter", "feed noise", "artifact-led")):
        return "Artifact-led intelligence beats feed noise."
    if "p2p" in blob or "peer" in blob or "connection string" in blob:
        return "Private capabilities sync across trusted agents."
    if "publish" in blob or "ipfs" in blob or "library push" in blob:
        return "Libraries become reusable agent capabilities."
    if "governance" in blob or "dao" in blob or "proposal" in blob or "vote" in blob:
        return "Governed capabilities move with consensus."
    if "discover" in blob or "adopt" in blob or "install" in blob or "expose" in blob:
        return "Find the right skill, then wire it in."
    if "prompt builder" in blob or "behavior" in blob or "compose" in blob:
        return "Reusable workflows start as structured prompts."
    if "manifest" in blob and "agent" in blob:
        return "Governed capabilities reach every agent."
    if "brief" in blob and any(token in blob for token in ("workflow", "operator", "signal")):
        return "From noisy signals to operator brief."
    if proof_title and proof_title.strip().lower() not in _GENERIC_PROOF_TITLES:
        return f"{proof_title.strip()} as a reusable agent capability."
    subject = _extract_subject_from_instruction(raw, str(payload.get("raw_prompt") or ""), str(payload.get("execution_prompt") or ""))
    if subject:
        return f"{subject} as a reusable agent capability."
    return "Source-linked skills agents can reuse."


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
    if selected_strategy == "operator_proof_board":
        index = 0
    elif design_variance <= 3:
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
    if not source_url:
        inferred_source_url = _infer_sage_skill_source_url(
            payload,
            material_type=material_type,
            entity_type=entity_type,
        )
        if inferred_source_url:
            source_url = inferred_source_url
            entity_type = _infer_entity_type(source_url, entity_type)

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
    explicit_selected_strategy = str(
        payload.get("selected_surface_strategy")
        or plan.get("selected_surface_strategy")
        or ""
    ).strip()
    template_selected_strategy = str(template.get("selected_surface_strategy") or "").strip()
    selected_strategy = str(
        explicit_selected_strategy
        or _material_default_strategy(material_type, payload, plan)
        or template_selected_strategy
        or ""
    ).strip()
    strategy_overridden = False
    if selected_strategy and not explicit_selected_strategy and selected_strategy != template_selected_strategy:
        strategy_overridden = True
    if material_type == "proof-poster" and _looks_like_operator_workflow_payload(payload, plan) and not explicit_selected_strategy:
        # Workflow/proof-heavy posters need a landscape proof-board layout, not
        # the generic portrait poster or QR/share-card strategies.
        selected_strategy = "operator_proof_board"
        strategy_overridden = True
    strategy_definition = load_surface_strategy_definition(selected_strategy)
    selected_strategy_label = str(
        ("" if strategy_overridden else payload.get("selected_surface_strategy_label"))
        or ("" if strategy_overridden else plan.get("selected_surface_strategy_label"))
        or strategy_definition.get("label")
        or ""
    ).strip()
    selected_strategy_summary = str(
        ("" if strategy_overridden else payload.get("selected_surface_strategy_summary"))
        or ("" if strategy_overridden else plan.get("selected_surface_strategy_summary"))
        or strategy_definition.get("summary")
        or ""
    ).strip()
    selected_strategy_layout_family = str(
        ("" if strategy_overridden else payload.get("selected_surface_strategy_layout_family"))
        or ("" if strategy_overridden else plan.get("selected_surface_strategy_layout_family"))
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
    preferred_mode = "" if strategy_overridden else str(template.get("preferred_composition_mode") or "").strip()
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
    if entity_type == "artifact" and (not raw_proof_title or proof_title.strip().lower() in _GENERIC_PROOF_TITLES):
        proof_title = _artifact_title_from_context(payload, plan)
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
    if entity_type == "artifact" and proof_excerpt == _default_proof_excerpt("artifact"):
        proof_excerpt = _artifact_excerpt_from_context(payload, plan)
    if material_type == "proof-poster":
        requested_labels = _extract_requested_workflow_labels(
            payload.get("raw_prompt"),
            payload.get("effective_prompt"),
            payload.get("execution_prompt"),
        )
        if requested_labels:
            proof_blob = proof_excerpt.lower()
            if not all(label.lower() in proof_blob for label in requested_labels):
                proof_excerpt = _workflow_excerpt_from_labels(requested_labels)
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
            "artifact": "Prompts · Skills · MCP tools · Behaviors",
        }.get(entity_type, "Trusted distribution through the current CLI and MCP tools")
    if material_type == "proof-poster":
        extracted_title = _extract_subject_from_instruction(
            headline,
            str(payload.get("raw_prompt") or ""),
            str(payload.get("execution_prompt") or ""),
        )
        if extracted_title and proof_title.strip().lower() in _GENERIC_PROOF_TITLES:
            proof_title = extracted_title
        headline = _curate_proof_poster_headline(
            headline,
            payload,
            proof_title=proof_title,
            proof_excerpt=proof_excerpt,
        )
    proof_meta = _sanitize_proof_meta(proof_meta, material_type=material_type)
    if material_type == "proof-poster":
        proof_meta = [
            item for item in proof_meta
            if not item.endswith(":") and "source" not in item.lower()
        ]
        if len(proof_meta) < 3:
            proof_meta = _default_proof_meta(entity_type)
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
