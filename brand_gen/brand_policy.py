"""Brand policies, identity summary, copy candidates, and inspiration context.

This is a leaf module in the material-planning split — it depends only on
``runtime`` and has no imports from any other new module.  This breaks the
circular-import chain that would otherwise arise when ``prompt_assembly``
or ``plan_validation`` need brand-policy helpers.

Key functions:
    normalize_material_brand_policy  — build per-material brand policy dict
    summarize_brand_anchor_policy    — one-line human-readable policy summary
    summarize_identity               — flatten identity + profile into a summary dict
    get_brand_guardrail_prelude      — full brand guardrail prelude (base + doctrine)
    derive_copy_candidates           — build copy bank for copy-bearing materials
    load_inspiration_prompt_context  — load configured inspiration doctrine + tokens
"""
from __future__ import annotations

from pathlib import Path

from .inspiration_sources import load_configured_source_records
from .runtime import *
from .runtime_brand import load_prompt_fragments

__all__ = [
    "normalize_material_brand_policy",
    "summarize_brand_anchor_policy",
    "get_base_brand_guardrail_prelude",
    "get_brand_guardrail_prelude",
    "summarize_identity",
    "derive_copy_candidates",
    "load_inspiration_prompt_context",
]


def normalize_material_brand_policy(material_type: str | None, *, identity: dict | None = None) -> dict:
    """Build the brand policy for a material type.

    Starts from ``MATERIAL_BRAND_POLICIES`` defaults, then overlays any
    per-material overrides stored in ``identity["material_policies"]``.
    This lets each brand customize ``product_truth_expression``, ``purpose``,
    ``target_surface``, etc. without editing source code.

    ``identity["material_policies"]`` schema (optional)::

        {
            "browser_illustration": {
                "product_truth_expression": "a real Acme dashboard with the timeline visible",
                "purpose": "package one real Acme moment inside a branded frame"
            }
        }
    """
    normalized = str(material_type or "").strip().lower().replace("-", "_")
    key = normalized if normalized in MATERIAL_BRAND_POLICIES else role_pack_material_key(material_type)
    base = dict(MATERIAL_BRAND_POLICIES.get(key, {}))
    # Merge per-brand overrides from identity if available
    if identity:
        brand_overrides = (identity.get("material_policies") or {}).get(key)
        if isinstance(brand_overrides, dict):
            base.update({k: v for k, v in brand_overrides.items() if v})
    _fragments = load_prompt_fragments()
    acceptable = _fragments.get("brand_anchor_acceptable", [
        "logo or wordmark",
        "exact brand palette",
        "exact mark geometry or approved motif",
        "real product surface or workflow proof",
        "brand name or approved product phrase",
        "approved carrier or composition pattern",
    ])
    logo_mode = base.get("logo_mode", "preferred")
    min_without_logo = int(base.get("clearly_branded_without_logo_min", 3) or 3)
    base.update(
        {
            "material_key": key,
            "logo_mode": logo_mode,
            "clearly_branded_without_logo_min": min_without_logo,
            "acceptable_anchors": acceptable,
            "rule": (
                "Show the stored logo or wordmark clearly."
                if logo_mode == "required"
                else f"If the logo is not visible, make the piece clearly branded with at least {min_without_logo} anchors from palette, mark geometry, product truth, name, or approved carriers."
            ),
        }
    )
    return base


def summarize_brand_anchor_policy(policy: dict) -> str:
    if not policy:
        return "Keep the output clearly branded."
    pieces = []
    if policy.get("purpose"):
        pieces.append(f"Material job: {policy['purpose']}")
    if policy.get("target_surface"):
        pieces.append(f"Surface: {policy['target_surface']}")
    if policy.get("product_truth_expression"):
        pieces.append(f"Product truth: {policy['product_truth_expression']}")
    if policy.get("rule"):
        pieces.append(f"Branding rule: {policy['rule']}")
    if policy.get("abstraction_level"):
        pieces.append(f"Abstraction: {policy['abstraction_level']}")
    return ". ".join(piece.rstrip(".") for piece in pieces if piece).strip() + "."


def get_base_brand_guardrail_prelude(profile: dict, identity: dict, material_type: str | None = None) -> str:
    guardrails = identity.get("generation_guardrails") or {}
    material_key = role_pack_material_key(material_type)
    if material_key in INTERFACE_MATERIAL_KEYS:
        return (
            guardrails.get("interface_prompt_prelude")
            or guardrails.get("prompt_prelude")
            or profile.get("brand_guardrail_prelude")
            or (profile.get("identity") or {}).get("brand_guardrail_prelude")
            or ""
        )
    if material_key in NON_INTERFACE_MATERIAL_KEYS:
        return (
            guardrails.get("non_interface_prompt_prelude")
            or guardrails.get("prompt_prelude")
            or profile.get("brand_guardrail_prelude")
            or (profile.get("identity") or {}).get("brand_guardrail_prelude")
            or ""
        )
    return (
        guardrails.get("prompt_prelude")
        or profile.get("brand_guardrail_prelude")
        or (profile.get("identity") or {}).get("brand_guardrail_prelude")
        or ""
    )


def get_brand_guardrail_prelude(profile: dict, identity: dict, brand_gen_dir: Path | None = None, active_brand: str | None = None) -> str:
    brand_prelude = get_base_brand_guardrail_prelude(profile, identity)
    context = load_inspiration_prompt_context(brand_gen_dir=brand_gen_dir, active_brand=active_brand)
    doctrine = context.get("doctrine", "")
    parts = [part.strip() for part in [brand_prelude, doctrine] if part and part.strip()]
    return "\n\n".join(parts)


def summarize_identity(profile: dict, identity: dict) -> dict:
    brand = identity.get("brand") or {}
    identity_core = identity.get("identity_core") or {}
    must_preserve = identity_core.get("must_preserve") or {}
    design_language = identity.get("design_language") or profile.get("design_language") or {}
    tokens = identity.get("design_tokens") or profile.get("design_tokens") or {}
    design_memory = identity.get("design_memory") or profile.get("design_memory") or {}
    guardrails = identity.get("generation_guardrails") or {}
    material_prompt_snippets = ((identity.get("generation_guardrails") or {}).get("material_prompt_snippets") or profile.get("material_prompt_snippets") or {})
    material_set_templates = identity.get("material_set_templates") or {}
    messaging = identity.get("messaging") or {}
    return {
        "brand_name": brand.get("name") or profile.get("brand_name") or "",
        "summary": brand.get("summary") or profile.get("description") or "",
        "homepage_url": brand.get("homepage_url") or profile.get("homepage_url") or "",
        "approved_claims": [str(item).strip() for item in (messaging.get("approved_claims") or []) if str(item).strip()],
        "forbidden_claims": [str(item).strip() for item in (messaging.get("forbidden_claims") or []) if str(item).strip()],
        "tone_words": identity_core.get("tone_words") or profile.get("keywords") or [],
        "brand_anchors": identity_core.get("brand_anchors") or profile.get("logo_candidates") or [],
        "palette_direction": must_preserve.get("palette_direction") or profile.get("color_candidates") or [],
        "typography_cues": must_preserve.get("typography_cues") or profile.get("font_candidates") or [],
        "typography_roles": must_preserve.get("typography_roles") or design_language.get("typography_roles") or profile.get("font_roles") or {},
        "shape_language": must_preserve.get("shape_language") or profile.get("radius_tokens") or [],
        "approved_graphic_devices": identity_core.get("approved_graphic_devices") or [],
        "forbidden_elements": identity_core.get("forbidden_elements") or [],
        "semantic_palette_roles": design_language.get("semantic_palette_roles") or [],
        "component_cues": design_language.get("component_cues") or [],
        "framework_cues": design_language.get("framework_cues") or [],
        "spacing_scale": design_language.get("spacing_scale") or [],
        "design_memory_source": design_memory.get("source_dir") or "",
        "design_memory_principles": design_memory.get("principles") or [],
        "design_memory_components": design_memory.get("components") or [],
        "material_prompt_snippet_keys": sorted(material_prompt_snippets.keys()) if isinstance(material_prompt_snippets, dict) else [],
        "material_set_template_keys": sorted(material_set_templates.keys()) if isinstance(material_set_templates, dict) else [],
        "prompt_prelude": get_brand_guardrail_prelude(profile, identity),
        "inspiration_translation_rule": guardrails.get("inspiration_translation_rule") or "",
        "non_interface_rule": guardrails.get("non_interface_rule") or "",
        "copy_rule": guardrails.get("copy_rule") or "",
        "token_sources": {
            "source_file": tokens.get("source_file") or "",
            "source_url": tokens.get("source_url") or "",
            "has_tokens": bool(tokens),
        },
    }


def derive_copy_candidates(profile: dict, identity: dict, material_type: str, goal: str = "", surface: str = "", *, brand_dir: Path | None = None) -> dict:
    brand_name = ((identity.get("brand") or {}).get("name") or profile.get("brand_name") or "Brand").strip()
    summary = ((identity.get("brand") or {}).get("summary") or profile.get("description") or "").strip()
    tone_words = (identity.get("identity_core") or {}).get("tone_words") or profile.get("keywords") or []
    tone_words = [str(item).strip() for item in tone_words if str(item).strip()]
    memory = load_iteration_memory(brand_dir) if brand_dir else normalize_iteration_memory(None)
    messaging_notes = list(memory.get("messaging_notes") or [])
    copy_notes = list(memory.get("copy_notes") or [])

    # Read from messaging section in brand identity (preferred) with hardcoded fallbacks
    messaging = identity.get("messaging") or {}
    copy_bank = messaging.get("approved_copy_bank") or {}

    hooks = dedupe_keep_order(copy_bank.get("headlines") or [
        f"Welcome to {brand_name}",
        f"What {brand_name} does, in one line",
        f"The core promise of {brand_name}",
    ])
    # Supplement from brand name if copy bank is thin
    if len(hooks) < 3:
        hooks.append(f"Learn more about {brand_name}")
        hooks = dedupe_keep_order(hooks)
    hooks = dedupe_keep_order(hooks + [note for note in messaging_notes if len(note.split()) <= 10])

    subheads = dedupe_keep_order(copy_bank.get("subheadlines") or [
        f"A short description of what {brand_name} offers and why it matters.",
        f"Explain {brand_name} in one sentence that a new visitor can scan.",
    ])
    if messaging.get("elevator"):
        subheads.insert(0, str(messaging["elevator"]).strip())
    subheads = dedupe_keep_order(subheads + [note for note in messaging_notes if len(note.split()) > 10][:2])
    slogans = dedupe_keep_order(copy_bank.get("slogans") or [
        f"{brand_name} — your tagline here",
        f"Built for [audience]. Made by [team].",
    ])
    if messaging.get("tagline"):
        slogans.insert(0, str(messaging["tagline"]).strip())
    slogans = dedupe_keep_order(slogans + [note for note in messaging_notes if len(note.split()) <= 8][:2])
    ctas = copy_bank.get("cta_pairs") or [
        {"primary": "Explore skills", "secondary": "View libraries"},
        {"primary": "Get Started", "secondary": "See communities"},
        {"primary": "Browse skills", "secondary": "Learn how it works"},
    ]
    _copy_defaults = load_prompt_fragments().get("copy_candidate_defaults", {})
    visual_angles = list(_copy_defaults.get("visual_angles", [
        "Wordmark + one strong product crop + one proof line",
        "Logo-led ad illustration + short slogan + one UI proof inset",
        "Quiet product frame + bold headline + minimal proof chips",
    ]))
    if role_pack_material_key(material_type) in {"campaign_poster", "proof_poster", "merch_poster", "social"}:
        visual_angles.insert(0, "Ad illustration with slogan + visible brand wordmark + one proof cue")
    if goal:
        slogans.insert(0, goal.strip())

    # Include messaging context so agents can use product voice
    messaging_context = {}
    if messaging.get("tagline"):
        messaging_context["tagline"] = messaging["tagline"]
    if messaging.get("elevator"):
        messaging_context["elevator"] = messaging["elevator"]
    if messaging.get("value_propositions"):
        messaging_context["value_propositions"] = messaging["value_propositions"][:4]
    if messaging.get("voice"):
        messaging_context["voice"] = messaging["voice"]
    if messaging_notes:
        messaging_context["iteration_notes"] = messaging_notes[-4:]
    if copy_notes:
        messaging_context["copy_notes"] = copy_notes[-3:]

    forbidden_claims = [str(item).strip() for item in (messaging.get("forbidden_claims") or []) if str(item).strip()]
    approved_claims = [str(item).strip() for item in (messaging.get("approved_claims") or []) if str(item).strip()]
    if approved_claims:
        subheads = dedupe_keep_order(approved_claims + subheads)

    return {
        "brand_name": brand_name,
        "material_type": material_type,
        "goal": goal,
        "surface": surface,
        "messaging": messaging_context,
        "headlines": hooks[:8],
        "slogans": slogans[:8],
        "subheadlines": subheads[:8],
        "cta_pairs": ctas,
        "visual_angles": visual_angles,
        "approved_claims": approved_claims[:8],
        "forbidden_claims": forbidden_claims[:8],
        "anti_patterns": list(_copy_defaults.get("anti_patterns", [
            "screenshot-only composition with no brand copy",
            "headline text invented by the image model",
            "generic AI dashboard marketing phrasing",
            "social card without visible brand anchor",
        ])),
    }


def load_inspiration_prompt_context(
    brand_gen_dir: Path | None = None,
    active_brand: str | None = None,
    material_type: str | None = None,
    brand_dir: Path | None = None,
) -> dict:
    resolved = brand_gen_dir or get_brand_gen_dir()
    brand_key = active_brand or resolve_active_brand_key(brand_gen_dir=resolved, repo_root=REPO_ROOT)
    default_payload = {
        "doctrine": "",
        "token_block": "",
        "token_block_fragments": [],
        "sources": [],
        "skipped": [],
        "mode": "principles",
        "source_records": [],
        "memory": dict(DEFAULT_INSPIRATION_MEMORY),
        "memory_summary": "",
        "memory_seed_prompt": "",
    }
    if not resolved or not brand_key:
        return default_payload

    config = load_brand_gen_config(brand_gen_dir=resolved, repo_root=REPO_ROOT)
    source_records, skipped = load_configured_source_records(
        brand_dir=Path(brand_dir).expanduser().resolve() if brand_dir else (resolved / "brands" / brand_key),
        brand_gen_dir=resolved,
        active_brand=brand_key,
    )
    available_paths: list[Path] = [Path(str(item.get("design_memory_path") or "")).expanduser().resolve() for item in source_records]
    used_sources: list[str] = [str(item.get("source_key") or "").strip() for item in source_records if str(item.get("source_key") or "").strip()]

    doctrine = merge_inspiration_doctrine(available_paths, material_type=material_type) if available_paths else ""
    token_fragments = []
    if config.get("inspirationMode"):
        for path in available_paths:
            token_payload = load_token_fragments(path)
            if any(token_payload.get(key) for key in ("css_vars", "color_palette", "typography_scale", "notes")):
                token_fragments.append(token_payload)
        merged_tokens = merge_token_fragments(token_fragments)
        token_block = merged_tokens.get("token_block", "")
        token_block_fragments = merged_tokens.get("source_fragments", [])
    else:
        token_block = ""
        token_block_fragments = []
    resolved_brand_dir = Path(brand_dir).expanduser().resolve() if brand_dir else (resolved / "brands" / brand_key)
    memory = load_inspiration_memory(resolved_brand_dir) if resolved_brand_dir.exists() else dict(DEFAULT_INSPIRATION_MEMORY)
    return {
        "doctrine": doctrine,
        "token_block": token_block,
        "token_block_fragments": token_block_fragments,
        "sources": used_sources,
        "source_records": source_records,
        "skipped": skipped,
        "mode": "full" if config.get("inspirationMode") else "principles",
        "memory": memory,
        "memory_summary": str(memory.get("summary") or ""),
        "memory_seed_prompt": str(memory.get("seed_prompt") or ""),
    }
