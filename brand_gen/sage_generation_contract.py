"""Sage-specific source/vault brief and generation contract helpers.

The generic brand-gen pipeline already carries brand guardrails, material
profiles, product-truth contracts, and iteration memory. Sage still needs a
shorter, higher-priority contract because the useful source language lives in
the Obsidian/docs vault and long prompt prose is routinely compressed before
generation. This module keeps that contract deterministic and compact.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .context_surfaces import build_source_knowledge_payload
from .product_truth import is_sage_capability_context
from .runtime_io import load_json_file
from .runtime_models import role_pack_material_key
from .runtime_paths import SCRIPT_DIR
from .runtime_support import dedupe_keep_order


_BRAND_CONTRACT_PATH = SCRIPT_DIR.parent / "data" / "sage_brand_contract.json"


def _load_brand_contract_overrides() -> dict[str, Any]:
    """Load the JSON sidecar that overrides the hard-coded fallbacks below.

    Returns an empty dict if the file is missing or unreadable. The hard-coded
    tuples below stay in place as the last-resort fallback so prompt assembly
    keeps working even if the JSON is deleted or malformed.
    """
    if not _BRAND_CONTRACT_PATH.exists():
        return {}
    try:
        return json.loads(_BRAND_CONTRACT_PATH.read_text())
    except (OSError, json.JSONDecodeError):
        return {}


_BRAND_CONTRACT = _load_brand_contract_overrides()


def _override_tuple(key: str, fallback: tuple[str, ...]) -> tuple[str, ...]:
    raw = _BRAND_CONTRACT.get(key)
    if not isinstance(raw, list):
        return fallback
    items = tuple(str(item) for item in raw if str(item or "").strip())
    return items or fallback


_FALLBACK_APPROVED_PHRASES: tuple[str, ...] = (
    "skill layer for AI agents",
    "Steer the Default",
    "curated skills improve agent performance by +16.2pp",
    "fat skills / thin harness",
    "someone has to govern the standard library",
    "agents find and use better workflows with less repeated setup",
)

_FALLBACK_ILLUSTRATION_CONCEPTS: tuple[str, ...] = (
    "standard library / canon",
    "abstract runtime default state",
    "skill layer above thin harnesses",
    "curated capability selected from library, then used",
    "library shelf / capability slots / finished artifact",
    "routed lattice / path motif derived from the mark",
    "transit grid / route map",
)

_FALLBACK_NEGATIVE_CONSTRAINTS: tuple[str, ...] = (
    "no thread/loom/wardrobe/textile/closet metaphor",
    "do not default to semi-realistic 3D/isometric robot or humanoid agent scenes unless explicitly requested",
    "do not default to robots or people editing/pushing artifacts into a central hub unless explicitly requested",
    "do not default to a central switchboard/control-room composition unless explicitly requested",
    "no trust layer as hero",
    "no governance process hero",
    "no generic marketplace/platform framing",
    "no raw prompt dump / random capability card deck / glowing light-bulb idea icon",
    "no repeated logos",
)


SAGE_APPROVED_PHRASES: tuple[str, ...] = _override_tuple("approved_phrases", _FALLBACK_APPROVED_PHRASES)
SAGE_ILLUSTRATION_CONCEPTS: tuple[str, ...] = _override_tuple("illustration_concepts", _FALLBACK_ILLUSTRATION_CONCEPTS)
SAGE_NEGATIVE_CONSTRAINTS: tuple[str, ...] = _override_tuple("negative_constraints", _FALLBACK_NEGATIVE_CONSTRAINTS)

_FALLBACK_FRAMING_DIRECTIONS: tuple[dict[str, str], ...] = (
    {
        "id": "chosen-not-collected-sieve",
        "label": "chosen-not-collected editorial sieve",
        "keywords": "chosen not collected selection curation judgment good bad worse mismatch focused sets",
        "source_cues": "Chosen, not collected; gap is selection; bad skills make agents worse; focused sets outperform comprehensive dumps",
        "adoption_scene": "an editorial selection sieve rejects noisy/generated skills and lets one curated capability become a runtime default",
        "style_anchor": "flat editorial sieve/gate composition with rejected noise outside the frame, one chosen capability artifact, restrained proof typography",
        "directive": "Frame Sage as selection rather than storage: a visible editorial sieve chooses one good capability and filters out harmful skill noise.",
    },
    {
        "id": "fat-skills-thin-harness-layer",
        "label": "fat-skills / thin-harness missing layer",
        "keywords": "fat skills thin harness missing layer hermes tan architecture whose skills should agent use",
        "source_cues": "Tan named thin harness/fat skills; Hermes named per-agent loop; Sage names the missing layer above both",
        "adoption_scene": "a thin runtime harness sits below a maintained layer of fat skills; one governed skill drops into the harness as the default",
        "style_anchor": "layered architectural section drawing: thin base harness, thick curated skill layer above, one active default slot, no character workshop",
        "directive": "Frame Sage as the missing layer above thin harnesses: maintained fat skills become trusted defaults for runtimes.",
    },
    {
        "id": "tokenized-taste-canon",
        "label": "tokenized taste canon",
        "keywords": "tokenized taste canon editorial function attributed funded tipped economic value value capture",
        "source_cues": "Sage scales tokenized taste; people who know what's good can be attributed, funded, tipped, and governed into the canon",
        "adoption_scene": "curator taste signals become attributed economic value: one judgment is funded, promoted into canon, and visibly rewarded",
        "style_anchor": "premium editorial/economic-value composition with taste signals, attribution marks, value flow, and one promoted capability; not an installation pipeline",
        "directive": "Frame Sage as tokenized taste becoming economic value: human editorial judgment gets attributed, rewarded, and turned into shared canon.",
        "source_priority": "220",
    },
    {
        "id": "curator-compensation-flywheel",
        "label": "curator compensation flywheel",
        "keywords": "curator compensation compensated labor tips bounties paid libraries creator value capture rewards economic incentives",
        "source_cues": "Curation is compensated labor; creators capture value through tips, bounties, paid libraries, governed canon, and reflections",
        "adoption_scene": "a curator's judgment moves through attribution, tip/bounty reward, paid-library inclusion, and visible value capture",
        "style_anchor": "editorial economic flywheel / value ledger composition: curator signal, reward markers, paid library, canon seal; no runtime process diagram",
        "directive": "Frame Sage as the economics of curation: good judgment becomes compensated labor and repeatable value capture.",
        "source_priority": "260",
    },
    {
        "id": "market-knowledge-ledger",
        "label": "market knowledge ledger",
        "keywords": "market knowledge repeated use visible authorship purchases bounty wins forks trusted curators evidence graph",
        "source_cues": "Skill effectiveness is emergent market knowledge: repeated use, visible authorship, tips, purchases, bounty wins, forks, governed inclusion, trusted curators",
        "adoption_scene": "signals of use, authorship, purchases, tips, forks, and governed inclusion accumulate into a market-knowledge ledger around a capability",
        "style_anchor": "premium editorial ledger/evidence-map composition with sparse value signals and provenance marks; no fake dashboard, no process pipeline",
        "directive": "Frame Sage as market knowledge: value emerges from repeated use, visible authorship, purchases, forks, tips, and trusted curation.",
        "source_priority": "240",
    },
    {
        "id": "ownership-steering-rights",
        "label": "ownership as steering rights",
        "keywords": "ownership steering rights economic committee",
        "source_cues": "Ownership as steering rights — economic framing, not committee framing",
        "adoption_scene": "ownership tokens act as steering rights over which capabilities become defaults, with value flowing to the curators who steer well",
        "style_anchor": "editorial ownership/steering-rights composition: directional rights, value allocation, canon boundary; no proposal/vote theatre",
        "directive": "Frame Sage as ownership/steering rights: economic control over default capabilities, not a governance-process scene.",
        "source_priority": "230",
    },
    {
        "id": "execution-dag-compounds",
        "label": "execution DAG compounds",
        "keywords": "dag dependency molecule compound orchestrator graph retrieval semantic seeding execution metadata atoms compounds",
        "source_cues": "Graph retrieval combines semantic seeding, dependency resolution, execution DAG metadata, and molecule/compound orchestrators",
        "adoption_scene": "small capability atoms resolve into a compound execution DAG, and the compound becomes the reusable default workflow",
        "style_anchor": "clear DAG/compound diagram with few nodes, dependency paths, one highlighted reusable workflow, no generic network cloud",
        "directive": "Frame Sage as execution compounds: atoms stay legible, but governed DAGs make the reusable workflow dependable.",
    },
    {
        "id": "rlm-memory-loop",
        "label": "RLM memory loop",
        "keywords": "rlm reinforcement learning memory prompt response captures suggestion weights local retrieval usage evidence",
        "source_cues": "RLM captures prompt-response pairs and improves future skill suggestions; confidence is local retrieval evidence, not protocol ranking",
        "adoption_scene": "local usage traces form a memory loop that suggests a better capability default next time without pretending to be a global ranking",
        "style_anchor": "quiet memory-loop diagram: captured traces, local suggestion weights, chosen capability, bounded evidence labels",
        "directive": "Frame Sage as memory improving future defaults: local traces inform suggestions while governance/provenance remains separate.",
    },
    {
        "id": "standard-library-canon",
        "label": "standard-library canon",
        "keywords": "standard library canon shelf shelves library maintained shared infrastructure",
        "source_cues": "Someone has to govern the standard library; communities govern skill libraries once work becomes shared infrastructure",
        "adoption_scene": "a maintained canon/standard-library object supplies one governed capability as the runtime default",
        "style_anchor": "flat editorial canon/library composition with maintained shelves, one promoted artifact, warm palette, print restraint",
        "directive": "Frame Sage as the governed standard library: maintained canon, not random marketplace inventory.",
    },
    {
        "id": "category-constellation-map",
        "label": "category-creator constellation map",
        "keywords": "category creator constellation white-space landscape adjacent projects agent-native skill improvement network",
        "source_cues": "Sage is a category creator above adjacent projects: agent-native skill improvement network with value capture",
        "adoption_scene": "a constellation of adjacent tools sits below a newly named Sage category layer that routes capability defaults",
        "style_anchor": "editorial category map/constellation with whitespace, named category boundary, no competitor dashboard or feature race",
        "directive": "Frame Sage as category creation: a new named layer organizes adjacent tools rather than competing as another feature box.",
    },
    {
        "id": "transit-route-map",
        "label": "transit route map",
        "keywords": "transit route map subway metro path lattice",
        "adoption_scene": "capability routes branch from a governed library map into runtime default paths and finished outputs",
        "style_anchor": "flat transit-map/system-diagram illustration with routed lattice paths, strong negative space, restrained labels",
        "directive": "Frame Sage as a route map: governed library as the station/source, capability paths as selectable defaults, finished outcomes at endpoints.",
    },
    {
        "id": "capability-specimen-sheet",
        "label": "capability specimen sheet",
        "keywords": "specimen sheet catalog index cards tiles archive proof sheet",
        "adoption_scene": "a curated capability specimen is selected from a governed catalog and appears as an abstract runtime default",
        "style_anchor": "editorial specimen-sheet composition: catalog tiles, one selected capability, deterministic type, no fake UI chrome",
        "directive": "Frame Sage as a catalog/specimen sheet: many governed capabilities exist, one is selected and becomes the default.",
    },
    {
        "id": "proof-poster",
        "label": "proof poster",
        "keywords": "proof poster benchmark evidence metric claim",
        "adoption_scene": "a proof claim and library manifest demonstrate how a capability becomes a default and improves the finished workflow",
        "style_anchor": "message-first proof poster with one artifact, one metric/proof payload, one small provenance mark",
        "directive": "Frame Sage as a proof poster: one library artifact plus one concrete evidence payload, not a dashboard.",
    },
    {
        "id": "runtime-slot-blueprint",
        "label": "runtime slot blueprint",
        "keywords": "slot blueprint harness schematic",
        "adoption_scene": "an abstract runtime blueprint exposes empty default slots; a governed capability fills one slot and produces a finished artifact",
        "style_anchor": "blueprint/system schematic with large abstract slots, thin connector paths, no humanoid character hero",
        "directive": "Frame Sage as a runtime-slot blueprint: abstract slots make the default-setting mechanism visible without staging agents as characters.",
    },
    {
        "id": "explicit-switchboard-only",
        "label": "explicit switchboard only",
        "keywords": "switchboard exchange control-room control room routing board hub",
        "source_cues": "conversation fallback only; too general for default Sage framing",
        "adoption_scene": "an exchange/routing board selects a governed capability as a runtime default; the finished work appears downstream",
        "style_anchor": "graphic exchange-board composition with distributed routes, not a character workshop or centered logo",
        "directive": "Use switchboard/routing-board framing only when explicitly requested; it is too general to be the default Sage idea.",
    },
    {
        "id": "abstract-agent-workbench",
        "label": "abstract agent workbench",
        "keywords": "robot humanoid workshop workbench assistant",
        "adoption_scene": "a deliberately abstract workbench shows capability artifacts becoming defaults for a runtime, with any agent presence subordinate",
        "style_anchor": "flat/productive workbench abstraction; if characters appear, keep them symbolic and secondary, not semi-realistic robots",
        "directive": "Use an agent/workbench framing only if specifically requested; keep any characters abstract and subordinate to the capability artifact.",
    },
)

_FALLBACK_BRAND_ANCHOR_SOURCES: tuple[str, ...] = (
    "palette",
    "routed/lattice/path motifs",
    "source/library/manifest object",
    "abstract capability-default state",
    "deterministic typography or approved phrase",
)

SAGE_BRAND_ANCHOR_SOURCES: tuple[str, ...] = _override_tuple("brand_anchor_sources", _FALLBACK_BRAND_ANCHOR_SOURCES)


def _safe_resolve_brand_dir() -> Path | None:
    """Module-load-safe brand-dir resolver.

    Module import must not raise even when no brand is selected (e.g. on
    first run, in tests). Returns None when nothing is resolvable; the
    framing-direction loader treats None as "no markdown prose available"
    and falls back to JSON-inline prose.
    """
    try:
        from .runtime_brand import resolve_active_brand_dir
        path = resolve_active_brand_dir(strict=False)
    except Exception:
        return None
    return path if path and Path(path).exists() else None


def _resolve_framing_directions() -> tuple[dict[str, Any], ...]:
    """Resolve framing directions from JSON-structured + per-id markdown prose.

    Order of precedence per field:
      1. Markdown prose at <brand>/voice/framing/<id>.md (if present)
      2. JSON-inline prose in sage_brand_contract.json::framing_directions[]
      3. Hard-coded Python fallback in this module
    """
    from .framing_directions import load_framing_directions

    raw = _BRAND_CONTRACT.get("framing_directions")
    if isinstance(raw, list) and raw:
        structured = [dict(item) for item in raw if isinstance(item, dict)]
    else:
        structured = [dict(item) for item in _FALLBACK_FRAMING_DIRECTIONS]

    brand_dir = _safe_resolve_brand_dir()
    return load_framing_directions(structured, brand_dir)


SAGE_FRAMING_DIRECTIONS: tuple[dict[str, Any], ...] = _resolve_framing_directions()

SAGE_DEFAULT_ADOPTION_SCENE = (
    "a library manifest opens a default capability slot in an abstract thin harness; "
    "a finished work artifact appears downstream without showing robots or humanoid agents"
)

SAGE_DEFAULT_STYLE_ANCHOR = (
    "flat editorial system illustration: standard-library shelf, routed lattice/path motifs, "
    "warm palette, print restraint, no semi-realistic robot workshop"
)

_SAGE_STALE_POSITIVE_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    (
        "routing loom threads one reusable Behavior into a thin agent harness; the agent uses it as the default path to finish work",
        SAGE_DEFAULT_ADOPTION_SCENE,
    ),
    (
        "routing loom threads one reusable Behavior into a thin agent harness",
        "library manifest opens a default capability slot in an abstract thin harness",
    ),
    (
        "crafted routing loom where a Sage Manifest threads a reusable Behavior",
        "crafted standard-library shelf and routed lattice where a manifest selects a reusable Behavior",
    ),
    ("routing loom / Behavior into harness", "library manifest / Behavior into abstract harness"),
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
                "chosen not collected tokenized taste fat skills thin harness execution DAG RLM memory "
                "standard library canon capability slots curated skills improve performance category creator"
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


def ideate_sage_source_framings(source_payload: dict[str, Any], *, limit: int = 5) -> list[dict[str, str]]:
    """Return Obsidian/source-derived Sage framing candidates.

    These are not generic style metaphors. Each candidate maps to a concrete
    vault/source phrase via `source_cues`, so planning can experiment with new
    framings grounded in the actual Sage conversation and notes.
    """
    results = source_payload.get("results") if isinstance(source_payload, dict) else []
    source_text = " ".join(
        " ".join([str(item.get("title") or ""), str(item.get("relpath") or ""), str(item.get("excerpt") or "")])
        for item in (results or [])
        if isinstance(item, dict)
    ).lower()
    candidates: list[dict[str, str]] = []
    for direction in SAGE_FRAMING_DIRECTIONS:
        direction_id = str(direction.get("id") or "")
        if direction_id in {"explicit-switchboard-only", "abstract-agent-workbench"}:
            continue
        cues = " ".join([str(direction.get("source_cues") or ""), str(direction.get("keywords") or "")]).lower()
        tokens = [token for token in re.split(r"[^a-z0-9.+-]+", cues) if len(token) > 3]
        score = sum(source_text.count(token) for token in tokens)
        if score <= 0:
            continue
        item = dict(direction)
        priority = int(str(direction.get("source_priority") or "0") or 0)
        item["source_score"] = str(score)
        item["source_priority"] = str(priority)
        item["source_total_score"] = str(score + priority)
        item["selection_reason"] = "source_ideated"
        candidates.append(item)
    candidates.sort(key=lambda item: int(item.get("source_total_score") or item.get("source_score") or 0), reverse=True)
    return candidates[: max(1, int(limit or 5))]


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
        return SAGE_DEFAULT_ADOPTION_SCENE
    if "standard library" in lower or "canon" in lower:
        return "a standard-library/canon object selects one capability and an agent uses it to complete work"
    if "mcp" in lower or "tool" in lower:
        return "a Sage Manifest exposes an MCP tool as an abstract capability slot; a finished work artifact appears downstream"
    return "curated capability is selected from a library, installed into an agent, then visibly used"


def _select_style_anchor(text: str, material_type: str) -> str:
    material_key = role_pack_material_key(material_type) or str(material_type or "").lower()
    if material_key == "system_explainer_illustration":
        return "mechanism-led system explainer with routed paths, library object, and abstract runtime-default outcome"
    if material_key == "illustrated_brand_world":
        return "illustrated brand-world only where process/action is concrete; routed paths connect source to use"
    return SAGE_DEFAULT_STYLE_ANCHOR


def _direction_keywords(direction: dict[str, str]) -> list[str]:
    return [item for item in re.split(r"[\s,/|-]+", str(direction.get("keywords") or "")) if item]


def _explicit_direction_match(text: str) -> dict[str, str] | None:
    lowered = str(text or "").lower()
    if not lowered or _is_negative_constraint_text(lowered):
        return None
    for direction in SAGE_FRAMING_DIRECTIONS:
        if any(keyword and keyword in lowered for keyword in _direction_keywords(direction)):
            return dict(direction, selection_reason="explicit_user_request")
    return None


def select_sage_framing_direction(
    *,
    text: str,
    material_type: str,
    recent_framings: list[str] | tuple[str, ...] | None = None,
    source_ideas: list[dict[str, str]] | tuple[dict[str, str], ...] | None = None,
) -> dict[str, str]:
    """Pick the Sage visual/product framing for a plan.

    Explicit user framing wins. Otherwise rotate through a small library so
    Sage does not fossilize around whatever metaphor performed well last week.
    """
    explicit = _explicit_direction_match(text)
    if explicit:
        return explicit
    material_key = role_pack_material_key(material_type) or str(material_type or "").strip().lower().replace("_", "-")
    recent = [str(item or "").strip() for item in (recent_framings or []) if str(item or "").strip()]
    source_pool = [
        dict(item)
        for item in (source_ideas or [])
        if isinstance(item, dict)
        and str(item.get("id") or "")
        and str(item.get("id") or "") not in {"explicit-switchboard-only", "abstract-agent-workbench"}
    ]
    default_pool = [
        d for d in SAGE_FRAMING_DIRECTIONS
        if d.get("id") not in {"abstract-agent-workbench", "explicit-switchboard-only"}
    ]
    pool = source_pool or default_pool
    candidates = [d for d in pool if d.get("id") not in recent] or list(pool) or list(default_pool)
    chosen = dict(candidates[0])
    chosen["selection_reason"] = "source_ideated_rotation" if source_pool else "rotated_novel_framing"
    if recent:
        chosen["recent_avoided"] = ", ".join(recent[-3:])
    return chosen


def _is_negative_constraint_text(text: str) -> bool:
    lowered = text.lower()
    return any(term in lowered for term in _SAGE_NEGATIVE_CONTEXT_TERMS)


def repair_stale_sage_contract_text(value: Any) -> tuple[str, bool]:
    """Repair stale positive Sage loom/thread wording without erasing bans.

    The v185-v188 traces showed that old positive contract language could keep
    re-entering fresh plans even after loom/wardrobe/thread metaphors were
    banned. Negative constraints such as "no thread/loom" should remain intact;
    only positive scene/style language is rewritten to the standard-library/default-state
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
            new_sentence = re.sub(r"\brouting loom\b", "standard-library shelf with routed lattice paths", new_sentence, flags=re.IGNORECASE)
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
            next_contract["adoption_scene"] = SAGE_DEFAULT_ADOPTION_SCENE
            changed_fields.append(f"{key}.adoption_scene")
        style_anchor = str(next_contract.get("style_anchor") or "")
        if not style_anchor or any(term in style_anchor.lower() for term in ("routing loom", "thread", "wardrobe", "textile", "closet")):
            next_contract["style_anchor"] = SAGE_DEFAULT_STYLE_ANCHOR
            changed_fields.append(f"{key}.style_anchor")
        next_contract["hard_bans"] = _normalize_sage_hard_bans(next_contract.get("hard_bans") or [])
        next_contract["negative_constraints"] = _normalize_sage_hard_bans(next_contract.get("negative_constraints") or [])
        next_contract["prompt_block"] = render_sage_generation_contract(next_contract)
        out[key] = next_contract

    if changed_fields:
        out["sage_contract_repair"] = {
            "applied": True,
            "changed_fields": dedupe_keep_order(changed_fields),
            "replacement_scene": SAGE_DEFAULT_ADOPTION_SCENE,
            "reason": "Repaired stale v185-v188 routing-loom/thread contract contamination before generation.",
        }
        warnings.append(
            "Sage stale-contract repair: replaced old routing-loom/thread positive language with standard-library/default-state contract."
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
    source_framing_ideas = ideate_sage_source_framings(source_payload, limit=5)
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
        "source_framing_ideas": source_framing_ideas,
        "negative_constraints": list(SAGE_NEGATIVE_CONSTRAINTS),
        "brand_anchor_sources": list(SAGE_BRAND_ANCHOR_SOURCES),
        "source_knowledge": {
            "configured": bool(source_payload.get("configured")),
            "scanned_markdown_files": int(source_payload.get("scanned_markdown_files") or 0),
            "matched_phrases": _matched_items(SAGE_APPROVED_PHRASES, source_payload),
            "matched_concepts": _matched_items(SAGE_ILLUSTRATION_CONCEPTS, source_payload),
            "matched_framing_ids": [str(item.get("id") or "") for item in source_framing_ideas if str(item.get("id") or "")],
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
        "routed/lattice/path motifs, source/library/manifest objects, abstract "
        "capability-default states, and deterministic typography or approved phrases. "
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
            "source/library objects, and abstract capability-default states the primary brand anchors; "
            "keep any stored logo or mark silhouette as a small provenance seal,"
        ),
    )
    if rewritten == prelude:
        rewritten = (
            prelude.rstrip()
            + " Sage explanatory/capability override: brand from palette, routed/lattice/path motifs, "
            "source/library/manifest objects, and abstract capability-default states; at most one small logo as provenance."
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
    "SAGE_FRAMING_DIRECTIONS",
    "SAGE_ILLUSTRATION_CONCEPTS",
    "SAGE_NEGATIVE_CONSTRAINTS",
    "apply_sage_brand_anchor_policy",
    "build_sage_vault_brief",
    "repair_stale_sage_contract_text",
    "repair_stale_sage_plan_contract",
    "render_sage_generation_contract",
    "ideate_sage_source_framings",
    "resolve_sage_capability_material_type",
    "select_sage_framing_direction",
    "rewrite_sage_explanatory_brand_prelude",
    "sage_generation_contract_seed",
]
