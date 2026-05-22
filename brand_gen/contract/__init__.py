"""Brand contract — rendered BRAND.md dossier over canonical JSON state.

JSON remains canonical (per AGENTS.md). Typed `bgen` verbs mutate structured
state with `mutations.jsonl` audit. This module renders a human/agent-readable
BRAND.md dossier from the canonical files. Mutators call `render_brand_md()`
synchronously inside their handler so the dossier never drifts.

Per PR-6 decision Q14: synchronous regen on every typed verb.
Explicit non-goal: BRAND.md is NOT canonical; do not parse user edits from it.
"""

from brand_gen.contract.brand_md import (
    BRAND_MD_FILENAME,
    BrandDossier,
    build_dossier,
    render_brand_md,
)

__all__ = [
    "BRAND_MD_FILENAME",
    "BrandDossier",
    "build_dossier",
    "render_brand_md",
]
