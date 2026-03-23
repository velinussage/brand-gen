#!/usr/bin/env python3
"""Package helpers for loading and merging design-memory doctrine into brand-gen prompts."""
from __future__ import annotations

import re
from pathlib import Path


def read_text(path: Path) -> str:
    try:
        return path.read_text(errors="ignore")
    except Exception:
        return ""


def compact_text(text: str, limit: int) -> str:
    text = re.sub(r"\n{3,}", "\n\n", (text or "").strip())
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "…"


def extract_css_variable_block(text: str) -> str:
    variables: list[str] = []
    seen: set[str] = set()
    for line in (text or "").splitlines():
        stripped = line.strip()
        if not stripped.startswith("--") or ":" not in stripped:
            continue
        normalized = stripped if stripped.endswith(";") else f"{stripped};"
        if normalized in seen:
            continue
        seen.add(normalized)
        variables.append(f"  {normalized}")
    if not variables:
        return ""
    return ":root {\n" + "\n".join(variables) + "\n}"


def section_excerpt(text: str, heading_terms: tuple[str, ...], limit: int, *, fallback_to_full: bool = False) -> str:
    lines = (text or "").splitlines()
    if not lines:
        return ""
    captures: list[str] = []
    active = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#"):
            active = any(term in stripped.lower() for term in heading_terms)
            if active:
                captures.append(stripped)
            continue
        if active and stripped:
            captures.append(stripped)
    joined = "\n".join(captures).strip()
    if joined:
        return compact_text(joined, limit)
    return compact_text(text, limit) if fallback_to_full else ""


def load_principles(design_memory_path: Path) -> str:
    path = design_memory_path / "principles.md"
    text = read_text(path)
    if not text:
        return ""
    return section_excerpt(
        text,
        ("doctrine", "principle", "constraint", "anti-pattern", "hierarchy", "guideline"),
        1400,
        fallback_to_full=True,
    )


def _dedupe_keep_order(items: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        normalized = str(item or "").strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        out.append(normalized)
    return out


def _extract_css_declarations(text: str) -> list[str]:
    root_match = re.search(r":root\s*\{.*?\}", text, re.DOTALL)
    block = root_match.group(0).strip() if root_match else extract_css_variable_block(text)
    declarations: list[str] = []
    seen_names: set[str] = set()
    for line in (block or "").splitlines():
        stripped = line.strip().rstrip(";")
        if not stripped.startswith("--") or ":" not in stripped:
            continue
        name, value = stripped.split(":", 1)
        normalized_name = name.strip()
        if normalized_name in seen_names:
            continue
        seen_names.add(normalized_name)
        declarations.append(f"{normalized_name}: {value.strip()};")
    return declarations


def _extract_section_lines(text: str, heading_terms: tuple[str, ...], limit: int) -> list[str]:
    excerpt = section_excerpt(text, heading_terms, limit)
    if not excerpt:
        return []
    lines: list[str] = []
    for line in excerpt.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        lines.append(stripped)
    return _dedupe_keep_order(lines)


def load_token_fragments(design_memory_path: Path) -> dict:
    css_vars: list[str] = []
    color_palette: list[str] = []
    typography_scale: list[str] = []
    notes: list[str] = []
    file_fragments: list[dict[str, object]] = []

    for name in ("reference.md", "style.md"):
        path = design_memory_path / name
        text = read_text(path)
        if not text:
            continue

        file_css = _extract_css_declarations(text)
        file_palette = _extract_section_lines(text, ("color palette",), 450)
        file_typography = _extract_section_lines(text, ("typography scale",), 450)
        file_notes = _dedupe_keep_order(
            _extract_section_lines(text, ("tokens",), 450)
            + _extract_section_lines(text, ("breakpoints",), 450)
            + _extract_section_lines(text, ("tailwind",), 450)
        )

        css_vars = _dedupe_keep_order(css_vars + file_css)
        color_palette = _dedupe_keep_order(color_palette + file_palette)
        typography_scale = _dedupe_keep_order(typography_scale + file_typography)
        notes = _dedupe_keep_order(notes + file_notes)

        if file_css or file_palette or file_typography or file_notes:
            file_fragments.append(
                {
                    "file": name,
                    "css_vars": file_css,
                    "color_palette": file_palette,
                    "typography_scale": file_typography,
                    "notes": file_notes,
                }
            )

    return {
        "source": str(design_memory_path),
        "css_vars": css_vars,
        "color_palette": color_palette,
        "typography_scale": typography_scale,
        "notes": notes,
        "files": file_fragments,
    }


def merge_token_fragments(fragments: list[dict]) -> dict:
    merged_css: list[str] = []
    merged_color_palette: list[str] = []
    merged_typography_scale: list[str] = []
    merged_notes: list[str] = []
    source_fragments: list[dict] = []
    seen_css_names: set[str] = set()

    for fragment in fragments:
        for declaration in fragment.get("css_vars") or []:
            name = str(declaration).split(":", 1)[0].strip()
            if not name or name in seen_css_names:
                continue
            seen_css_names.add(name)
            merged_css.append(str(declaration).strip())
        merged_color_palette = _dedupe_keep_order(merged_color_palette + list(fragment.get("color_palette") or []))
        merged_typography_scale = _dedupe_keep_order(merged_typography_scale + list(fragment.get("typography_scale") or []))
        merged_notes = _dedupe_keep_order(merged_notes + list(fragment.get("notes") or []))
        if any(fragment.get(key) for key in ("css_vars", "color_palette", "typography_scale", "notes")):
            source_fragments.append(
                {
                    "source": fragment.get("source") or "",
                    "css_vars": list(fragment.get("css_vars") or []),
                    "color_palette": list(fragment.get("color_palette") or []),
                    "typography_scale": list(fragment.get("typography_scale") or []),
                    "notes": list(fragment.get("notes") or []),
                    "files": list(fragment.get("files") or []),
                }
            )

    parts: list[str] = []
    if merged_css:
        parts.append(":root {\n" + "\n".join(f"  {item}" for item in merged_css) + "\n}")
    if merged_color_palette:
        parts.append("## Color palette\n" + "\n".join(merged_color_palette))
    if merged_typography_scale:
        parts.append("## Typography scale\n" + "\n".join(merged_typography_scale))
    if merged_notes:
        parts.append("## Notes\n" + "\n".join(merged_notes))

    token_block = compact_text("\n\n".join(part for part in parts if part).strip(), 2000) if parts else ""
    return {
        "token_block": token_block,
        "source_fragments": source_fragments,
        "css_vars": merged_css,
        "color_palette": merged_color_palette,
        "typography_scale": merged_typography_scale,
        "notes": merged_notes,
    }


def load_tokens(design_memory_path: Path) -> str:
    return merge_token_fragments([load_token_fragments(design_memory_path)]).get("token_block", "")


def load_component_hints(design_memory_path: Path, material_type: str) -> str:
    material = (material_type or "").lower()
    files: list[tuple[str, tuple[str, ...], int]] = []
    if "animation" in material or "motion" in material or material == "gif":
        files.append(("motion.md", ("motion", "animation", "transition"), 500))
    if "hero" in material or "banner" in material or "layout" in material:
        files.append(("layout.md", ("hero", "section", "layout"), 650))
    files.append(("components.md", ("button", "card", "navigation", "component"), 650))

    excerpts: list[str] = []
    for filename, headings, limit in files:
        text = read_text(design_memory_path / filename)
        if not text:
            continue
        excerpt = section_excerpt(text, headings, limit)
        if excerpt and excerpt not in excerpts:
            excerpts.append(excerpt)
    return compact_text("\n\n".join(excerpts), 1000) if excerpts else ""


def extract_bullet_lines(text: str, *, limit: int = 6, exclude_negative: bool = False) -> list[str]:
    lines: list[str] = []
    for raw in (text or "").splitlines():
        stripped = raw.strip()
        if not stripped.startswith("- "):
            continue
        bullet = stripped[2:].strip()
        lower = bullet.lower()
        if exclude_negative and (
            lower.startswith("avoid ")
            or lower.startswith("do not ")
            or lower.startswith("don't ")
            or " avoid " in lower
            or " do not " in lower
        ):
            continue
        lines.append(bullet.rstrip("."))
        if len(lines) >= limit:
            break
    return _dedupe_keep_order(lines)


def summarize_inspiration_source(design_memory_path: Path, source_name: str, material_type: str | None = None) -> dict:
    principles = load_principles(design_memory_path)
    component_hints = load_component_hints(design_memory_path, material_type or "")
    mechanics = _dedupe_keep_order(
        extract_bullet_lines(principles, limit=4, exclude_negative=True)
        + extract_bullet_lines(component_hints, limit=3, exclude_negative=True)
    )
    summary_parts = mechanics[:3]
    summary = f"{source_name}: " + "; ".join(summary_parts) if summary_parts else f"{source_name}: translated mechanics only"
    return {
        "source_name": source_name,
        "mechanics": mechanics[:5],
        "summary": summary.strip(),
    }


def build_selected_inspiration_translation(selected_sources: list[dict], material_type: str | None = None) -> dict:
    summaries: list[dict] = []
    mechanics: list[str] = []
    for item in selected_sources or []:
        path = Path(str(item.get("design_memory_path") or "")).expanduser()
        if not path.exists():
            continue
        source_name = str(item.get("source_name") or item.get("source_key") or "Inspiration source")
        summary = summarize_inspiration_source(path, source_name, material_type=material_type)
        summaries.append(summary)
        mechanics.extend(summary.get("mechanics") or [])
    lines: list[str] = []
    if summaries:
        lines.append("Selected inspiration translation:")
        for item in summaries[:2]:
            lines.append(f"- {item['summary']}")
        lines.append("Use these as mechanics only; do not borrow foreign logos, typography, copy, or product structure.")
    return {
        "translation": compact_text("\n".join(lines).strip(), 700) if lines else "",
        "mechanics": _dedupe_keep_order(mechanics)[:6],
        "source_summaries": summaries,
    }


def merge_inspiration_doctrine(sources: list[Path], material_type: str | None = None) -> str:
    blocks: list[str] = []
    seen: set[str] = set()
    for source in sources:
        principles = load_principles(source)
        component_hints = load_component_hints(source, material_type or "")
        for block in (principles, component_hints):
            normalized = block.strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            blocks.append(normalized)
    merged = "\n\n".join(blocks).strip()
    return compact_text(merged, 2000) if merged else ""


__all__ = [
    "load_principles",
    "load_tokens",
    "load_token_fragments",
    "merge_token_fragments",
    "load_component_hints",
    "extract_bullet_lines",
    "summarize_inspiration_source",
    "build_selected_inspiration_translation",
    "merge_inspiration_doctrine",
]
