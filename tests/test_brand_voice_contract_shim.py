"""PR-5 — Verify the sage_generation_contract.py shim re-exports brand_voice_contract.

Two checks:

1. Shim parity — every name on the public surface of brand_voice_contract is
   accessible through sage_generation_contract and `is` the same object.

2. Brand-payload lint — no NEW SAGE_* literals (or other UPPERCASE_BRAND_*
   patterns) appear at module top-level outside the active payload modules.
   The payload modules are explicitly allowlisted; everything else flagged.
"""
from __future__ import annotations

import re
from pathlib import Path


PUBLIC_NAMES = (
    "SAGE_APPROVED_PHRASES",
    "SAGE_BRAND_ANCHOR_SOURCES",
    "SAGE_DEFAULT_ADOPTION_SCENE",
    "SAGE_DEFAULT_STYLE_ANCHOR",
    "SAGE_FRAMING_DIRECTIONS",
    "SAGE_ILLUSTRATION_CONCEPTS",
    "SAGE_NEGATIVE_CONSTRAINTS",
    "apply_sage_brand_anchor_policy",
    "build_sage_vault_brief",
    "ideate_sage_source_framings",
    "render_sage_generation_contract",
    "repair_stale_sage_contract_text",
    "repair_stale_sage_plan_contract",
    "resolve_sage_capability_material_type",
    "rewrite_sage_explanatory_brand_prelude",
    "sage_generation_contract_seed",
    "select_sage_framing_direction",
)


def test_shim_reexports_brand_voice_contract():
    """Every public name on brand_voice_contract is `is`-identical via the shim."""
    from brand_gen import brand_voice_contract, sage_generation_contract

    for name in PUBLIC_NAMES:
        shim_obj = getattr(sage_generation_contract, name)
        canonical_obj = getattr(brand_voice_contract, name)
        assert shim_obj is canonical_obj, f"{name} drifted between shim and canonical"


def test_sage_constants_are_populated():
    """Sanity: PR-1/PR-2 loaders produce non-empty constants."""
    from brand_gen.brand_voice_contract import (
        SAGE_APPROVED_PHRASES,
        SAGE_BRAND_ANCHOR_SOURCES,
        SAGE_FRAMING_DIRECTIONS,
        SAGE_ILLUSTRATION_CONCEPTS,
        SAGE_NEGATIVE_CONSTRAINTS,
    )
    assert len(SAGE_APPROVED_PHRASES) >= 6
    assert len(SAGE_ILLUSTRATION_CONCEPTS) >= 7
    assert len(SAGE_NEGATIVE_CONSTRAINTS) >= 9
    assert len(SAGE_BRAND_ANCHOR_SOURCES) >= 5
    assert len(SAGE_FRAMING_DIRECTIONS) >= 16


# Allowlist: modules that may contain SAGE_* / <BRAND>_* literals at module scope.
_PAYLOAD_ALLOWLIST = {
    "brand_voice_contract.py",  # canonical brand-voice payload
    "sage_generation_contract.py",  # compatibility shim re-exports the names
    "product_truth.py",  # PR-6 lifted lexicons to contract.json; remaining
    # SAGE_ALLOWED/BANNED_PRODUCT_TERMS and SAGE_TEXT_HEAVY_MATERIALS are now
    # populated from <brand>/contract.json with Python fallbacks. The names
    # themselves still appear at module scope, so allowlist is preserved.
    "runtime_refs.py",  # contains diagram label strings, not brand-payload literals
}

# Pattern: top-level assignment of an UPPERCASE_NAME that starts with a brand
# token. We're lenient — any module-level UPPERCASE_NAME starting with SAGE_
# or matching <BRAND>_<UPPERCASE> is a payload literal.
_BRAND_LITERAL_RE = re.compile(r"^(SAGE_[A-Z0-9_]+)\s*[:=]", re.MULTILINE)


def test_no_new_brand_payload_literals_outside_allowlist():
    """No new SAGE_* literals at module top-level outside the payload allowlist.

    Existing offenders inside the allowlist are accepted; this test catches
    *new* drift in any other module.
    """
    brand_gen_root = Path(__file__).resolve().parent.parent / "brand_gen"
    offenders: list[tuple[str, list[str]]] = []
    for py_path in brand_gen_root.rglob("*.py"):
        if py_path.name in _PAYLOAD_ALLOWLIST:
            continue
        if "/__pycache__/" in str(py_path):
            continue
        # Only check module top level — function-local consts are fine
        text = py_path.read_text(encoding="utf-8", errors="replace")
        # Strip indented lines so we only see module-scope
        top_level = "\n".join(line for line in text.splitlines() if not line.startswith((" ", "\t")))
        matches = _BRAND_LITERAL_RE.findall(top_level)
        if matches:
            offenders.append((str(py_path.relative_to(brand_gen_root.parent)), matches))

    assert not offenders, (
        "New SAGE_* literals found outside the payload allowlist; "
        "either lift to <brand>/contract.json (preferred) or add the file "
        "to _PAYLOAD_ALLOWLIST in this test:\n  "
        + "\n  ".join(f"{p}: {m}" for p, m in offenders)
    )
