"""Compatibility shim — see brand_voice_contract.py for the implementation.

The mechanism is now brand-agnostic and lives in `brand_voice_contract.py`.
Sage-specific payload (SAGE_* tuples, SAGE_FRAMING_DIRECTIONS, etc.) is
loaded from `<brand>/contract.json` (and per-id markdown under
`<brand>/voice/framing/<id>.md` for prose) at module import time.

This file exists only to preserve `from .sage_generation_contract import ...`
import statements scattered through the codebase. New code should import
from `brand_voice_contract` directly.
"""
from __future__ import annotations

from .brand_voice_contract import *  # noqa: F401,F403
from .brand_voice_contract import (  # noqa: F401  — explicit re-export
    SAGE_APPROVED_PHRASES,
    SAGE_BRAND_ANCHOR_SOURCES,
    SAGE_DEFAULT_ADOPTION_SCENE,
    SAGE_DEFAULT_STYLE_ANCHOR,
    SAGE_FRAMING_DIRECTIONS,
    SAGE_ILLUSTRATION_CONCEPTS,
    SAGE_NEGATIVE_CONSTRAINTS,
    apply_sage_brand_anchor_policy,
    build_sage_vault_brief,
    ideate_sage_source_framings,
    render_sage_generation_contract,
    repair_stale_sage_contract_text,
    repair_stale_sage_plan_contract,
    resolve_sage_capability_material_type,
    rewrite_sage_explanatory_brand_prelude,
    sage_generation_contract_seed,
    select_sage_framing_direction,
)
