"""Aesthetic archetype library — named compositional grammars per material.

Why this exists: brand-gen's prompt_seed used to be prose ("calm branded
illustration, restrained, premium editorial"). Image models need concrete
handholds — compositional grammar, color rule, rendering finish — not mood
words. This module loads `data/aesthetic_archetypes.json` and exposes
lookup + rotation helpers that mirror the style-anchor rotation design
(see `iteration_memory.pick_rotating_style_anchor`).

Per-material archetype sets live in data/aesthetic_archetypes.json and are
rotated across runs so the pipeline doesn't fossilize on one paradigm.
"""
from __future__ import annotations

import json
from pathlib import Path

from .runtime_paths import SCRIPT_DIR


_ARCHETYPES_PATH = SCRIPT_DIR.parent / "data" / "aesthetic_archetypes.json"


def _load_archetypes() -> dict:
    if not _ARCHETYPES_PATH.exists():
        return {"archetypes_by_material": {}}
    return json.loads(_ARCHETYPES_PATH.read_text())


_ARCHETYPE_DATA = _load_archetypes()


def _material_key(material_type: str | None) -> str:
    if not material_type:
        return ""
    return str(material_type).strip().lower().replace("_", "-")


def list_archetypes(material_type: str | None) -> list[dict]:
    """Return the archetype list for a material type.

    Accepts hyphen or underscore form. Returns [] when the material has
    no declared archetypes.
    """
    key = _material_key(material_type)
    if not key:
        return []
    archetypes = (
        _ARCHETYPE_DATA.get("archetypes_by_material", {}).get(key)
        or []
    )
    return list(archetypes)


def get_archetype(material_type: str | None, archetype_id: str | None) -> dict | None:
    """Lookup a specific archetype by id within a material. Returns None when
    the id doesn't match.
    """
    if not archetype_id:
        return None
    for a in list_archetypes(material_type):
        if a.get("id") == archetype_id:
            return a
    return None


def pick_rotating_archetype(
    material_type: str | None,
    iteration_memory: dict | None,
) -> dict | None:
    """Pick an archetype for a run that differs from the most recent N-1 picks
    for this material. Mirrors `pick_rotating_style_anchor` logic so the
    pipeline cycles the full archetype set before repeating.

    Returns the chosen archetype dict or None when no archetypes are declared
    for the material.
    """
    archetypes = list_archetypes(material_type)
    if not archetypes:
        return None
    material_key = _material_key(material_type)
    recent = []
    if isinstance(iteration_memory, dict):
        recent = list(
            (iteration_memory.get("recent_archetypes_by_material") or {}).get(material_key) or []
        )
    candidates = [a for a in archetypes if a.get("id") not in recent]
    if not candidates:
        candidates = list(archetypes)
    return candidates[0]


def record_archetype_choice(
    iteration_memory: dict,
    *,
    material_type: str,
    archetype_id: str,
    archetype_set_size: int | None = None,
) -> dict:
    """Persist chosen archetype so rotation works across runs. Callers must
    save_iteration_memory after.
    """
    from .iteration_memory import normalize_iteration_memory

    memory = normalize_iteration_memory(iteration_memory)
    memory.setdefault("recent_archetypes_by_material", {})
    key = _material_key(material_type)
    history = [h for h in list(memory["recent_archetypes_by_material"].get(key) or []) if h != archetype_id]
    history.append(archetype_id)
    window = max((archetype_set_size or len(history)) - 1, 1)
    memory["recent_archetypes_by_material"][key] = history[-window:]
    return memory


def render_archetype_brief(archetype: dict) -> str:
    """Render an archetype as a compact compositional brief for the prompt.

    Image models respond to concrete compositional grammar and specific
    references — not mood words. This rendering emits the brief in the
    shape of a directive ("Compose in the spirit of <name> — <grammar>.
    Color: <rule>. Finish: <finish>. Signature moves: <...>. Avoid: <...>.").
    """
    if not isinstance(archetype, dict):
        return ""
    name = archetype.get("name") or archetype.get("id") or ""
    grammar = archetype.get("compositional_grammar") or ""
    color = archetype.get("color_rule") or ""
    finish = archetype.get("rendering_finish") or ""
    moves = archetype.get("signature_moves") or []
    bans = archetype.get("example_bans") or []
    parts: list[str] = []
    if name:
        parts.append(f"Compose in the spirit of {name}.")
    if grammar:
        parts.append(f"Composition: {grammar}")
    if color:
        parts.append(f"Color: {color}")
    if finish:
        parts.append(f"Finish: {finish}")
    if moves:
        parts.append("Signature moves: " + "; ".join(moves) + ".")
    if bans:
        parts.append("Avoid: " + "; ".join(bans) + ".")
    return " ".join(parts)
