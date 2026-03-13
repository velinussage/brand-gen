#!/usr/bin/env python3
"""Helpers for loading and merging design-memory doctrine into brand-gen prompts."""
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


def load_tokens(design_memory_path: Path) -> str:
    for name in ("reference.md", "style.md"):
        path = design_memory_path / name
        text = read_text(path)
        if not text:
            continue
        root_match = re.search(r":root\s*\{.*?\}", text, re.DOTALL)
        sections: list[str] = []
        seen: set[str] = set()
        has_variable_block = False
        if root_match:
            block = root_match.group(0).strip()
            sections.append(block)
            seen.add(block)
            has_variable_block = True
        else:
            block = extract_css_variable_block(text)
            if block:
                sections.append(block)
                seen.add(block)
                has_variable_block = True
        headings = ["color palette", "typography scale", "breakpoints", "tailwind"]
        if not has_variable_block:
            headings.insert(0, "tokens")
        for heading in headings:
            excerpt = section_excerpt(text, (heading,), 450)
            if excerpt and excerpt not in seen:
                sections.append(excerpt)
                seen.add(excerpt)
        block = "\n\n".join(part for part in sections if part).strip()
        if block:
            return compact_text(block, 2000)
    return ""


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
    "load_component_hints",
    "merge_inspiration_doctrine",
]
