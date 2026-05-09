"""PR-10 — Iteration-memory dual-write round-trip property.

Asserts that <brand>/iteration-memory.md is byte-identical to
render_iteration_memory_markdown(load_iteration_memory(<brand>)). When this
test fails, the markdown has drifted from the canonical JSON — call
`bgen render-iteration-memory` to bring it back into sync.

This test runs against the active brand workspace by default. If no
brand is selected, it builds a synthetic in-memory payload and verifies
the rendering function is deterministic.
"""
from __future__ import annotations

import tempfile
from pathlib import Path


def test_synthetic_iteration_memory_round_trip():
    """The render function is deterministic: render(normalize(payload)) is stable."""
    from brand_gen.iteration_memory import (
        normalize_iteration_memory,
        render_iteration_memory_markdown,
    )

    payload = {
        "brand_notes": ["test note 1", "test note 2"],
        "positive_examples": [],
        "negative_examples": [],
        "copy_notes": ["copy 1"],
        "messaging_notes": [],
        "material_notes": {"poster": ["poster note"]},
    }
    normalized = normalize_iteration_memory(payload)
    rendered_a = render_iteration_memory_markdown(normalized)
    rendered_b = render_iteration_memory_markdown(normalized)
    assert rendered_a == rendered_b, "render is non-deterministic"
    # Re-normalizing the normalized payload must yield the same payload
    renormalized = normalize_iteration_memory(normalized)
    assert renormalized == normalized, "normalize is non-idempotent"


def test_active_brand_iteration_memory_in_sync():
    """If a brand workspace exists, its iteration-memory.md must equal render(json)."""
    try:
        from brand_gen.runtime_brand import resolve_active_brand_dir
        brand_dir = resolve_active_brand_dir(strict=False)
    except Exception:
        return  # no brand available; skip
    if not brand_dir or not Path(brand_dir).exists():
        return

    from brand_gen.iteration_memory import (
        iteration_memory_paths,
        load_iteration_memory,
        normalize_iteration_memory,
        render_iteration_memory_markdown,
    )

    json_path, md_path = iteration_memory_paths(brand_dir)
    if not json_path.exists() or not md_path.exists():
        return  # nothing to test

    payload = normalize_iteration_memory(load_iteration_memory(brand_dir))
    expected_md = render_iteration_memory_markdown(payload)
    actual_md = md_path.read_text(encoding="utf-8")

    if expected_md != actual_md:
        # Diff hint without dumping the entire file
        for i, (a, b) in enumerate(zip(actual_md.splitlines(), expected_md.splitlines())):
            if a != b:
                raise AssertionError(
                    f"iteration-memory.md drift at line {i + 1}:\n"
                    f"  actual:   {a[:120]!r}\n"
                    f"  expected: {b[:120]!r}\n"
                    f"Run `bgen render-iteration-memory` to resync."
                )
        # length mismatch
        raise AssertionError(
            f"iteration-memory.md length mismatch ({len(actual_md)} vs {len(expected_md)}); "
            "run `bgen render-iteration-memory` to resync."
        )
