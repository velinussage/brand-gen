"""Generic product-truth helpers.

Brand-gen must not carry hard-coded product knowledge for one specific brand.
Historically this module contained Sage-specific lexicons and prompt injections;
those are now inert compatibility shims so old imports keep working without
adding Sage terms, source-knowledge contracts, or product-specific copy to other
brands.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .runtime_models import role_pack_material_key
from .runtime_paths import brand_contract_path
from .runtime_support import dedupe_keep_order


def _safe_resolve_brand_dir_for_lexicons() -> Path | None:
    try:
        from .runtime_brand import resolve_active_brand_dir
        path = resolve_active_brand_dir(strict=False)
    except Exception:
        return None
    return path if path and Path(path).exists() else None


def _load_brand_contract_for_lexicons() -> dict[str, Any]:
    path = brand_contract_path(_safe_resolve_brand_dir_for_lexicons(), brand_name="sage")
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return {}


_BRAND_CONTRACT_FOR_LEXICONS = _load_brand_contract_for_lexicons()


def _override_list(section: str, key: str, fallback: tuple[str, ...]) -> tuple[str, ...]:
    block = _BRAND_CONTRACT_FOR_LEXICONS.get(section)
    if not isinstance(block, dict):
        return fallback
    raw = block.get(key)
    if not isinstance(raw, list):
        return fallback
    items = tuple(str(item) for item in raw if str(item or "").strip())
    return items or fallback


_FALLBACK_ALLOWED_PRODUCT_TERMS: tuple[str, ...] = (
    "skill libraries",
    "prompt libraries",
    "skills",
    "prompts",
    "MCP tools",
    "agents",
    "runtime defaults",
    "default capability slots",
    "library manifests",
    "curated capabilities",
    "reusable capabilities",
    "agent workflows",
    "Skill Library",
    "MCP Tool",
    "Agent Workflow",
    "Curated Skill",
    "Reusable Capability",
)

_FALLBACK_BANNED_PRODUCT_TERMS: tuple[str, ...] = (
    "Prompt Pack",
    "System of Provenance",
    "Approved Library Update",
)


SAGE_ALLOWED_PRODUCT_TERMS: tuple[str, ...] = _override_list("product_terms", "allowed", _FALLBACK_ALLOWED_PRODUCT_TERMS)
SAGE_BANNED_PRODUCT_TERMS: tuple[str, ...] = _override_list("product_terms", "banned", _FALLBACK_BANNED_PRODUCT_TERMS)

SAGE_TEXT_HEAVY_MATERIALS = {
    "data-card",
    "data_card",
    "process-card",
    "process_card",
    "badge-family",
    "badge_family",
    "social",
    "proof-poster",
    "proof_poster",
    "campaign-poster",
    "campaign_poster",
    "content-card",
    "content_card",
    "quote-card",
    "quote_card",
}

_FALLBACK_CAPABILITY_TOKENS = (
    "skill",
    "skills",
    "prompt librar",
    "skill librar",
    "mcp",
    "tool",
    "agent",
    "library manifest",
    "curated capabil",
    "reusable capabil",
    "workflow",
    "runtime",
    "default slot",
    "default state",
    "discover",
    "install",
    "sync",
    "distribution",
)

_FALLBACK_GOVERNANCE_PROCESS_TOKENS = (
    "proposal",
    "review",
    "publish",
    "promote",
    "promotion",
    "approve",
    "approval",
    "vote",
    "voting",
    "governance",
    "dao",
    "quorum",
)

_FALLBACK_GOVERNANCE_EDUCATION_TOKENS = (
    "governance education",
    "governance explainer",
    "governance snapshot",
    "proposal detail",
    "proposal page",
    "proposal card",
    "voting guide",
    "vote guide",
    "dao explainer",
)


_CAPABILITY_TOKENS = _override_list("lexicon", "capability", _FALLBACK_CAPABILITY_TOKENS)
_GOVERNANCE_PROCESS_TOKENS = _override_list("lexicon", "governance_process", _FALLBACK_GOVERNANCE_PROCESS_TOKENS)
_GOVERNANCE_EDUCATION_TOKENS = _override_list("lexicon", "governance_education", _FALLBACK_GOVERNANCE_EDUCATION_TOKENS)

_FAKE_PRODUCT_SCREEN_RE = re.compile(
    r"\b(fake|invented|fictional|imaginary|made[- ]?up)\s+"
    r"(app|module|screen|dashboard|product|feature)s?\b",
    flags=re.IGNORECASE,
)

_NEGATED_TERM_PREFIX_RE = re.compile(
    r"(?:^|[\s,;:.()\[\]{}\"'“”‘’/-])"
    r"(?:no|not|never|avoid|avoids|avoiding|without|exclude|excluding|"
    r"remove|removing|ban|banned|forbid|forbidden|disallow|disallowed|"
    r"do\s+not|don't|dont|must\s+not|should\s+not|rather\s+than|instead\s+of)"
    r"(?:[\s,;:.=()\[\]{}\"'“”‘’/-]+[\w'-]+){0,32}"
    r"[\s,;:.=()\[\]{}\"'“”‘’/-]*$",
    flags=re.IGNORECASE,
)

_NEGATED_TERM_SUFFIX_RE = re.compile(
    r"^\s*(?:is|are|was|were|as)?\s*(?:not|n't|never)\s+"
    r"(?:a\s+|an\s+|the\s+)?(?:real|actual|approved|valid|allowed|supported)\b",
    flags=re.IGNORECASE,
)

_NEGATION_CUE_RE = re.compile(
    r"(?:^|[\s,;:.=()\[\]{}\"'“”‘’/-])"
    r"(?:no|not|never|avoid|avoids|avoiding|without|exclude|excluding|"
    r"remove|removing|ban|banned|forbid|forbidden|disallow|disallowed|"
    r"do\s+not|don't|dont|must\s+not|should\s+not|rather\s+than|instead\s+of)"
    r"(?:$|[\s,;:.=()\[\]{}\"'“”‘’/-])",
    flags=re.IGNORECASE,
)

_CONTRAST_AFTER_NEGATION_RE = re.compile(
    r"\b(?:but|however|except|instead\s+show|instead\s+use|rather\s+show|rather\s+use)\b",
    flags=re.IGNORECASE,
)


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return " ".join(_as_text(v) for v in value.values())
    if isinstance(value, (list, tuple, set)):
        return " ".join(_as_text(v) for v in value)
    return str(value)


def plan_product_truth_haystack(plan: dict[str, Any] | None) -> str:
    if not isinstance(plan, dict):
        return ""
    fields = [
        "brand_dir",
        "material_type",
        "purpose",
        "target_surface",
        "product_truth_expression",
        "prompt_seed",
        "system_mechanic",
        "briefing",
        "selected_surface_strategy",
        "selected_surface_strategy_label",
        "selected_surface_strategy_layout_family",
        "entity_type",
        "source_shape",
        "artifact_scope",
    ]
    parts = [_as_text(plan.get(field)) for field in fields]
    # `ban` is deliberately excluded: product-truth validators care about
    # affirmative intent, not terms that appear only in "avoid/no/ban X"
    # guardrails. Including the ban list caused the Sage contract itself
    # ("no Prompt Pack...") to trip the invented-taxonomy blocker.
    parts.extend(_as_text(plan.get(field)) for field in ("preserve", "push"))
    return " ".join(part for part in parts if part).strip()


def _is_negated_mention(text: str, start: int, end: int) -> bool:
    before = text[max(0, start - 220): start]
    after = text[end: min(len(text), end + 72)]
    if _NEGATED_TERM_SUFFIX_RE.search(after):
        return True
    prefix_match = _NEGATED_TERM_PREFIX_RE.search(before)
    if prefix_match:
        matched_prefix = prefix_match.group(0)
        cue_matches = list(_NEGATION_CUE_RE.finditer(matched_prefix))
        if cue_matches and _CONTRAST_AFTER_NEGATION_RE.search(matched_prefix[cue_matches[-1].end() :]):
            return False
        return True

    # Banned terms often appear inside long guardrail lists generated by the
    # pipeline or supplied by the user, e.g. "No QR code, source URL block,
    # private preview badge, ..., or fake app screen."  The old fixed six-word
    # prefix window made those lists self-trigger as affirmative asks.  Treat a
    # sentence/clause as negated when a negation cue appears before the hit and
    # no contrastive turn ("but create ...") appears after that cue.
    sentence_start = max(
        text.rfind(".", 0, start),
        text.rfind("!", 0, start),
        text.rfind("?", 0, start),
        text.rfind("\n", 0, start),
        text.rfind(";", 0, start),
    )
    segment = text[sentence_start + 1 : start]
    cue_matches = list(_NEGATION_CUE_RE.finditer(segment))
    if not cue_matches:
        return False
    last_cue = cue_matches[-1]
    return not bool(_CONTRAST_AFTER_NEGATION_RE.search(segment[last_cue.end() :]))


def _affirmative_term_hits(text: str, terms: tuple[str, ...]) -> list[str]:
    hits: list[str] = []
    for term in terms:
        pattern = re.compile(rf"(?<![\w-]){re.escape(term)}(?![\w-])", flags=re.IGNORECASE)
        for match in pattern.finditer(text):
            if _is_negated_mention(text, match.start(), match.end()):
                continue
            hits.append(term)
            break
    return hits


def is_sage_capability_context(
    *,
    identity: dict[str, Any] | None = None,
    plan: dict[str, Any] | None = None,
    text: str = "",
) -> bool:
    """Deprecated compatibility shim.

    Brand-gen no longer detects or injects product-specific Sage behavior.
    Product truth must come from the active brand profile/identity, explicit
    user brief, references, or per-brand contract files — never hard-coded
    global brand knowledge.
    """
    return False


def governance_education_requested(plan: dict[str, Any] | None) -> bool:
    plan = plan or {}
    haystack = plan_product_truth_haystack(plan).lower()
    entity_type = str(plan.get("entity_type") or "").strip().lower()
    strategy = str(plan.get("selected_surface_strategy") or "").strip().lower()
    layout = str(plan.get("selected_surface_strategy_layout_family") or "").strip().lower()
    if entity_type == "proposal":
        return True
    if "governance" in strategy or layout == "governance":
        return True
    return any(token in haystack for token in _GOVERNANCE_EDUCATION_TOKENS)


def value_focus_counts(plan: dict[str, Any] | None) -> dict[str, int]:
    haystack = plan_product_truth_haystack(plan).lower()
    return {
        "capability": sum(1 for token in _CAPABILITY_TOKENS if token in haystack),
        "governance_process": sum(1 for token in _GOVERNANCE_PROCESS_TOKENS if token in haystack),
    }


def _contains_generic_trust_layer(text: str) -> bool:
    lower = text.lower()
    idx = lower.find("trust layer")
    while idx != -1:
        if _is_negated_mention(text, idx, idx + len("trust layer")):
            idx = lower.find("trust layer", idx + 1)
            continue
        window = lower[max(0, idx - 48): idx + 80]
        # "trust and distribution layer for agent capability" is an approved
        # Sage positioning line; generic "trust layer" by itself is not.
        if not any(token in window for token in ("distribution", "agent", "capabil", "library", "skill")):
            return True
        idx = lower.find("trust layer", idx + 1)
    return False


def _wrong_value_hero(plan: dict[str, Any] | None) -> bool:
    if governance_education_requested(plan):
        return False
    haystack = plan_product_truth_haystack(plan).lower()
    counts = value_focus_counts(plan)
    has_process_sequence = (
        ("proposal" in haystack and "review" in haystack and ("publish" in haystack or "promote" in haystack))
        or ("publish" in haystack and ("review" in haystack or "approve" in haystack) and ("promote" in haystack or "proposal" in haystack))
    )
    capability_anchor_count = sum(1 for token in ("agent", "capabil", "skill", "mcp", "library manifest") if token in haystack)
    process_dominant = (
        counts["governance_process"] >= 3
        and counts["governance_process"] > counts["capability"] + 1
    )
    return bool((has_process_sequence and capability_anchor_count < 2) or process_dominant)


def validate_product_truth_plan(
    plan: dict[str, Any] | None,
    *,
    identity: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Deprecated compatibility shim; no global product-specific validation."""
    plan = plan or {}
    return {"applies": False, "errors": [], "warnings": [], "counts": value_focus_counts(plan)}


def _validate_product_truth_plan_legacy_sage(
    plan: dict[str, Any] | None,
    *,
    identity: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Legacy Sage-specific validator retained only for historical reference."""
    plan = plan or {}
    if not is_sage_capability_context(identity=identity, plan=plan):
        return {"applies": False, "errors": [], "warnings": [], "counts": value_focus_counts(plan)}

    haystack = plan_product_truth_haystack(plan)
    lower = haystack.lower()
    errors: list[str] = []
    warnings: list[str] = []

    banned_hits = _affirmative_term_hits(haystack, SAGE_BANNED_PRODUCT_TERMS)
    if banned_hits:
        errors.append(
            "invented_product_taxonomy: remove invented Sage product terms "
            f"({', '.join(banned_hits)}). Use allowed nouns such as skill libraries, "
            "prompt libraries, skills, prompts, MCP tools, agents, library manifests, "
            "curated capabilities, and reusable capabilities."
        )

    if _contains_generic_trust_layer(haystack):
        errors.append(
            "invented_product_taxonomy: generic 'trust layer' framing is too vague here. "
            "Name the concrete Sage value: governed libraries provide reusable capabilities as agent defaults."
        )

    fake_product_hit = next(
        (
            match
            for match in _FAKE_PRODUCT_SCREEN_RE.finditer(haystack)
            if not _is_negated_mention(haystack, match.start(), match.end())
        ),
        None,
    )
    if fake_product_hit:
        errors.append(
            "invented_product_taxonomy: do not ask for fake product modules or fake app screens. "
            "Use real capability artifacts or abstract textless tiles instead."
        )

    if _wrong_value_hero(plan):
        errors.append(
            "wrong_value_hero: proposal_process_instead_of_capability_distribution. "
            "Unless this is explicitly governance education, the hero value must be governed libraries providing reusable capability defaults, not proposal/review/publish mechanics."
        )

    counts = value_focus_counts(plan)
    material_key = role_pack_material_key(plan.get("material_type") or "")
    identity_material = material_key in {"logo", "lockup", "icon", "icon_family", "sticker_family"}
    if counts["capability"] == 0 and not identity_material:
        warnings.append(
            "Sage product-truth warning: no allowed capability noun is visible. Prefer skill libraries, prompt libraries, skills, prompts, MCP tools, agents, library manifests, curated capabilities, or reusable capabilities."
        )
    if "logo" in lower and any(token in lower for token in ("centerpiece", "giant", "dominant", "repeated logo", "logo hub")):
        warnings.append(
            "Sage logo-dominance warning: for explanatory assets the mark should be a small provenance seal/corner mark, not the content substitute."
        )
    return {"applies": True, "errors": dedupe_keep_order(errors), "warnings": dedupe_keep_order(warnings), "counts": counts}


def sage_product_truth_prompt_moves(
    plan: dict[str, Any] | None,
    *,
    identity: dict[str, Any] | None = None,
) -> dict[str, list[str]]:
    """Deprecated compatibility shim; no global brand-specific prompt moves."""
    return {"push": [], "ban": []}


def render_product_truth_contract(
    plan: dict[str, Any] | None,
    *,
    identity: dict[str, Any] | None = None,
) -> str:
    """Deprecated compatibility shim; no global brand-specific prompt block."""
    return ""


def _render_product_truth_contract_legacy_sage(
    plan: dict[str, Any] | None,
    *,
    identity: dict[str, Any] | None = None,
) -> str:
    if not is_sage_capability_context(identity=identity, plan=plan or {}):
        return ""
    plan = plan or {}
    material_key = role_pack_material_key(plan.get("material_type") or "")
    parts = [
        "Sage product-truth contract: the hero value is governed skill/prompt libraries turning trusted reusable capabilities into agent defaults.",
        "Allowed Sage nouns: skill libraries, prompt libraries, skills, prompts, MCP tools, agents, library manifests, curated capabilities, reusable capabilities, runtime defaults, and agent workflows.",
        "Prefer visible capability artifacts: skill card, MCP tool card, library manifest, curated capability tile, default capability slot, or reusable workflow card; represent agents as abstract runtime slots/paths unless a character/agent framing is explicitly requested.",
        "Governance/review/promotion is a reason to trust the library, not the primary thing being demonstrated unless the material explicitly asks for governance education.",
        "Avoid invented taxonomy: no Prompt Pack, no System of Provenance, no Approved Library Update, no generic trust-layer claim, no fake product modules or fake app screens.",
        "Novel-framing rule: rotate the visual/product framing across runs; do not default to semi-realistic robots/humanoid agents, robot workshop scenes, or central hub/switchboard compositions unless explicitly requested.",
    ]
    if material_key not in {"logo", "lockup", "icon", "icon_family", "badge_family", "sticker_family"}:
        parts.append(
            "Logo rule for explanatory assets: one small Sage mark only, as a provenance seal/corner/source marker (about 5-8% visual weight); never repeat the logo inside every object or use it as the centerpiece."
        )
    if material_key in {role_pack_material_key(item) for item in SAGE_TEXT_HEAVY_MATERIALS}:
        parts.append(
            "Text-heavy material rule: make native image art mostly textless; compose exact labels, stats, captions, badges, or card copy deterministically with HTML/SVG/composite overlays."
        )
    return " ".join(parts)


def build_product_truth_metadata(
    plan: dict[str, Any] | None,
    *,
    identity: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return generic structured product-truth metadata for prompt assembly."""
    plan = plan or {}
    return {"applies": False, "value_focus_counts": value_focus_counts(plan)}


def _build_product_truth_metadata_legacy_sage(
    plan: dict[str, Any] | None,
    *,
    identity: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not is_sage_capability_context(identity=identity, plan=plan or {}):
        return {"applies": False}
    plan = plan or {}
    material_key = role_pack_material_key(plan.get("material_type") or "")
    metadata: dict[str, Any] = {
        "applies": True,
        "hero_value": "governed skill/prompt libraries turning trusted reusable capabilities into agent defaults",
        "proof_artifacts": [
            "library manifest",
            "skill card",
            "MCP tool card",
            "curated capability tile",
            "default capability slot",
            "reusable workflow card",
            "abstract runtime path",
        ],
        "trust_role": (
            "governance/review/promotion is trust substrate, not the visual hero, "
            "unless governance education is explicitly requested"
        ),
        "avoid": [
            "defaulting to semi-realistic robots/humanoid agents unless requested",
            "defaulting to central hub/switchboard composition unless requested",
            "Prompt Pack",
            "System of Provenance",
            "Approved Library Update",
            "generic trust-layer claim",
            "fake product modules or fake app screens",
        ],
        "logo_rule": "",
        "text_rule": "",
    }
    if material_key not in {"logo", "lockup", "icon", "icon_family", "badge_family", "sticker_family"}:
        metadata["logo_rule"] = "one small Sage mark as provenance/source seal; never the centerpiece"
    if material_key in {role_pack_material_key(item) for item in SAGE_TEXT_HEAVY_MATERIALS}:
        metadata["text_rule"] = "exact labels/stats/captions/badges/card copy must be deterministic HTML/SVG/composite overlays"
    return metadata


__all__ = [
    "SAGE_ALLOWED_PRODUCT_TERMS",
    "SAGE_BANNED_PRODUCT_TERMS",
    "SAGE_TEXT_HEAVY_MATERIALS",
    "build_product_truth_metadata",
    "governance_education_requested",
    "is_sage_capability_context",
    "plan_product_truth_haystack",
    "render_product_truth_contract",
    "sage_product_truth_prompt_moves",
    "validate_product_truth_plan",
    "value_focus_counts",
]
