#!/usr/bin/env python3
"""Design-memory-lite helpers for brand-gen.

Inspired by Dembrandt design-memory (MIT), but intentionally limited to the
highest-value local functions brand-gen can reuse without the full crawler +
LLM pipeline.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

TEXT_EXTENSIONS = {
    ".css",
    ".scss",
    ".sass",
    ".less",
    ".styl",
    ".html",
    ".htm",
    ".md",
    ".txt",
}
IGNORED_DIRS = {
    ".git",
    "node_modules",
    "dist",
    "build",
    "target",
    ".next",
    "coverage",
    ".venv",
    "venv",
    "site-packages",
    "__pycache__",
}
CORE_DESIGN_MEMORY_FILES = [
    "reference.md",
    "style.md",
    "principles.md",
    "components.md",
    "layout.md",
    "motion.md",
    "qa.md",
]
MAX_SCAN_FILES = 250
MAX_FILE_BYTES = 1_000_000


def read_text(path: Path) -> str:
    try:
        if path.stat().st_size > MAX_FILE_BYTES:
            return ""
        return path.read_text(errors="ignore")
    except Exception:
        return ""


def compact_text(text: str, limit: int = 2000) -> str:
    text = re.sub(r"\n{3,}", "\n\n", (text or "").strip())
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "…"


def extract_markdown_section(text: str, heading_terms: tuple[str, ...], limit: int, *, fallback_to_full: bool = False) -> str:
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


def extract_css_variables_from_text(text: str) -> list[dict[str, str]]:
    variables: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for match in re.finditer(r"(--[A-Za-z0-9_-]+)\s*:\s*([^;}{\n]+)\s*;?", text or ""):
        name = match.group(1).strip()
        value = re.sub(r"\s+", " ", match.group(2).strip())
        if not name or not value:
            continue
        key = (name, value)
        if key in seen:
            continue
        seen.add(key)
        variables.append({"name": name, "value": value})
    return variables


def render_css_variables_block(variables: list[dict[str, str]]) -> str:
    if not variables:
        return ""
    lines = [":root {"]
    for item in variables:
        lines.append(f"  {item['name']}: {item['value']};")
    lines.append("}")
    return "\n".join(lines)


def normalize_lines(text: str) -> list[str]:
    lines: list[str] = []
    seen: set[str] = set()
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        line = re.sub(r"^[\-\*•\d\.\)\(\s]+", "", line).strip()
        line = re.sub(r"\s+", " ", line)
        if not line or line in seen:
            continue
        seen.add(line)
        lines.append(line)
    return lines


def compare_line_sets(before: list[str], after: list[str]) -> dict[str, object]:
    before_set = set(before)
    after_set = set(after)
    return {
        "added": [item for item in after if item not in before_set],
        "removed": [item for item in before if item not in after_set],
        "shared_count": len(before_set & after_set),
    }


def resolve_design_memory_dir(path_str: str) -> Path:
    path = Path(path_str).expanduser().resolve()
    if path.is_dir():
        if path.name == ".design-memory":
            return path
        candidate = path / ".design-memory"
        if candidate.exists():
            return candidate
    if path.is_file():
        if path.parent.name == ".design-memory":
            return path.parent
        for parent in path.parents:
            if parent.name == ".design-memory":
                return parent
            candidate = parent / ".design-memory"
            if candidate.exists():
                return candidate
    raise SystemExit(f"Could not resolve a .design-memory directory from: {path_str}")


def scan_text_files(path_str: str, *, max_files: int = MAX_SCAN_FILES) -> list[Path]:
    path = Path(path_str).expanduser().resolve()
    if path.is_file():
        return [path] if path.suffix.lower() in TEXT_EXTENSIONS else []

    try:
        design_memory_dir = resolve_design_memory_dir(path_str)
    except SystemExit:
        design_memory_dir = None

    if design_memory_dir:
        files = [design_memory_dir / name for name in CORE_DESIGN_MEMORY_FILES]
        return [item for item in files if item.exists()]

    files: list[Path] = []
    stack = [path]
    while stack and len(files) < max_files:
        current = stack.pop()
        try:
            children = sorted(current.iterdir(), reverse=True)
        except Exception:
            continue
        for item in children:
            if len(files) >= max_files:
                break
            if item.is_dir():
                if item.name in IGNORED_DIRS or item.name.startswith('.'):
                    continue
                stack.append(item)
                continue
            if item.suffix.lower() not in TEXT_EXTENSIONS:
                continue
            files.append(item)
    return files


def parse_design_memory(path_str: str) -> dict:
    design_memory_dir = resolve_design_memory_dir(path_str)
    files_present = [name for name in CORE_DESIGN_MEMORY_FILES if (design_memory_dir / name).exists()]

    reference_text = read_text(design_memory_dir / "reference.md")
    style_text = read_text(design_memory_dir / "style.md")
    principles_text = read_text(design_memory_dir / "principles.md")
    components_text = read_text(design_memory_dir / "components.md")
    layout_text = read_text(design_memory_dir / "layout.md")
    motion_text = read_text(design_memory_dir / "motion.md")

    css_variables = extract_css_variables_from_text(reference_text)
    if not css_variables:
        css_variables = extract_css_variables_from_text(style_text)

    principles = extract_markdown_section(
        principles_text,
        ("doctrine", "principle", "constraint", "anti-pattern", "hierarchy", "guideline"),
        1800,
        fallback_to_full=True,
    )
    components = extract_markdown_section(
        components_text,
        ("component", "button", "card", "navigation", "form", "hero", "recipe"),
        1600,
        fallback_to_full=True,
    )
    layout = extract_markdown_section(
        layout_text,
        ("layout", "hero", "section", "structure", "grid", "breakpoint"),
        1600,
        fallback_to_full=True,
    )
    motion = extract_markdown_section(
        motion_text,
        ("motion", "animation", "transition", "timing"),
        1200,
        fallback_to_full=True,
    )
    combined_reference = "\n\n".join(part for part in [reference_text, style_text] if part.strip())
    color_palette = extract_markdown_section(combined_reference, ("color palette", "palette"), 1200)
    typography_scale = extract_markdown_section(combined_reference, ("typography scale", "typography", "font"), 1200)
    breakpoints = extract_markdown_section(combined_reference, ("breakpoints", "responsive"), 800)

    result = {
        "input_path": str(Path(path_str).expanduser().resolve()),
        "design_memory_dir": str(design_memory_dir),
        "files_present": files_present,
        "principles": principles,
        "components": components,
        "layout": layout,
        "motion": motion,
        "color_palette": color_palette,
        "typography_scale": typography_scale,
        "breakpoints": breakpoints,
        "css_variables": css_variables,
        "css_variables_block": render_css_variables_block(css_variables),
        "summary": {
            "file_count": len(files_present),
            "css_variable_count": len(css_variables),
            "principle_line_count": len(normalize_lines(principles)),
            "component_line_count": len(normalize_lines(components)),
            "layout_line_count": len(normalize_lines(layout)),
            "motion_line_count": len(normalize_lines(motion)),
        },
    }
    return result


def extract_css_variables(path_str: str, *, max_files: int = MAX_SCAN_FILES) -> dict:
    files = scan_text_files(path_str, max_files=max_files)
    if not files:
        raise SystemExit(f"No supported text files found under: {path_str}")

    merged: dict[str, dict[str, object]] = {}
    scanned: list[str] = []
    for file in files:
        text = read_text(file)
        if not text:
            continue
        scanned.append(str(file))
        for item in extract_css_variables_from_text(text):
            existing = merged.get(item["name"])
            if not existing:
                merged[item["name"]] = {
                    "name": item["name"],
                    "value": item["value"],
                    "sources": [str(file)],
                }
                continue
            sources = existing.setdefault("sources", [])
            if str(file) not in sources:
                sources.append(str(file))
            if existing.get("value") != item["value"]:
                conflicts = existing.setdefault("conflicts", [])
                conflict = {"value": item["value"], "source": str(file)}
                if conflict not in conflicts:
                    conflicts.append(conflict)

    variables = sorted(merged.values(), key=lambda item: item["name"])
    block = render_css_variables_block([
        {"name": item["name"], "value": str(item["value"])} for item in variables
    ])
    return {
        "input_path": str(Path(path_str).expanduser().resolve()),
        "scanned_files": scanned,
        "count": len(variables),
        "variables": variables,
        "css_variables_block": block,
    }


def diff_design_memory(before_path: str, after_path: str) -> dict:
    before = parse_design_memory(before_path)
    after = parse_design_memory(after_path)

    before_vars = {item["name"]: item["value"] for item in before["css_variables"]}
    after_vars = {item["name"]: item["value"] for item in after["css_variables"]}

    css_added = [{"name": key, "value": after_vars[key]} for key in sorted(after_vars) if key not in before_vars]
    css_removed = [{"name": key, "value": before_vars[key]} for key in sorted(before_vars) if key not in after_vars]
    css_changed = [
        {"name": key, "before": before_vars[key], "after": after_vars[key]}
        for key in sorted(before_vars)
        if key in after_vars and before_vars[key] != after_vars[key]
    ]

    sections = {}
    total_changes = len(css_added) + len(css_removed) + len(css_changed)
    for field in ["principles", "components", "layout", "motion", "color_palette", "typography_scale", "breakpoints"]:
        diff = compare_line_sets(normalize_lines(before.get(field, "")), normalize_lines(after.get(field, "")))
        sections[field] = diff
        total_changes += len(diff["added"]) + len(diff["removed"])

    if total_changes == 0:
        verdict = "identical"
    elif total_changes <= 5:
        verdict = "minor"
    elif total_changes <= 20:
        verdict = "moderate"
    else:
        verdict = "major"

    return {
        "before": before["design_memory_dir"],
        "after": after["design_memory_dir"],
        "css_variables": {
            "added": css_added,
            "removed": css_removed,
            "changed": css_changed,
        },
        "sections": sections,
        "summary": {
            "total_changes": total_changes,
            "verdict": verdict,
            "css_variable_changes": len(css_added) + len(css_removed) + len(css_changed),
        },
    }


def emit_payload(payload: dict, fmt: str, output_json: str | None = None) -> None:
    if output_json:
        path = Path(output_json).expanduser().resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2) + "\n")
    if fmt == "json":
        print(json.dumps(payload, indent=2))
        return
    if "design_memory_dir" in payload:
        print("Design memory summary\n")
        print(f"Input: {payload['input_path']}")
        print(f"Resolved .design-memory: {payload['design_memory_dir']}")
        print(f"Files: {', '.join(payload['files_present']) or 'none'}")
        print(f"CSS variables: {payload['summary']['css_variable_count']}")
        for key in ["principles", "components", "layout", "motion", "color_palette", "typography_scale", "breakpoints"]:
            value = payload.get(key, "")
            if value:
                title = key.replace("_", " ").title()
                print(f"\n{title}:\n")
                print(value)
        return
    if "variables" in payload:
        print("CSS variables\n")
        print(f"Input: {payload['input_path']}")
        print(f"Files scanned: {len(payload['scanned_files'])}")
        print(f"Variables: {payload['count']}\n")
        for item in payload["variables"]:
            conflict = " (conflicts)" if item.get("conflicts") else ""
            print(f"- {item['name']}: {item['value']}{conflict}")
        if payload.get("css_variables_block"):
            print("\nCSS block:\n")
            print(payload["css_variables_block"])
        return
    print("Design memory diff\n")
    print(f"Before: {payload['before']}")
    print(f"After: {payload['after']}")
    print(f"Verdict: {payload['summary']['verdict']}")
    print(f"Total changes: {payload['summary']['total_changes']}\n")
    if payload["css_variables"]["added"] or payload["css_variables"]["removed"] or payload["css_variables"]["changed"]:
        print("CSS variable changes:")
        for item in payload["css_variables"]["added"]:
            print(f"- added {item['name']} = {item['value']}")
        for item in payload["css_variables"]["removed"]:
            print(f"- removed {item['name']} = {item['value']}")
        for item in payload["css_variables"]["changed"]:
            print(f"- changed {item['name']}: {item['before']} -> {item['after']}")
    for key, diff in payload["sections"].items():
        if not diff["added"] and not diff["removed"]:
            continue
        print(f"\n{key.replace('_', ' ').title()}:")
        for item in diff["added"]:
            print(f"- added {item}")
        for item in diff["removed"]:
            print(f"- removed {item}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Design-memory-lite helpers for brand-gen")
    sub = parser.add_subparsers(dest="command", required=True)

    parse = sub.add_parser("parse", help="Parse an existing .design-memory directory into a compact structured summary")
    parse.add_argument("--path", required=True, help="Path to a .design-memory folder, a file inside it, or a project root containing one")
    parse.add_argument("--format", choices=["text", "json"], default="text")
    parse.add_argument("--output-json")

    extract = sub.add_parser("extract-css", help="Extract CSS custom properties from .design-memory files or local CSS/HTML/Markdown files")
    extract.add_argument("--path", required=True, help="Path to a file, .design-memory folder, or project root")
    extract.add_argument("--format", choices=["text", "json"], default="text")
    extract.add_argument("--output-json")
    extract.add_argument("--max-files", type=int, default=MAX_SCAN_FILES)

    diff = sub.add_parser("diff", help="Diff two .design-memory directories")
    diff.add_argument("--before", required=True, help="Earlier .design-memory path")
    diff.add_argument("--after", required=True, help="Later .design-memory path")
    diff.add_argument("--format", choices=["text", "json"], default="text")
    diff.add_argument("--output-json")

    args = parser.parse_args()
    if args.command == "parse":
        emit_payload(parse_design_memory(args.path), args.format, args.output_json)
        return 0
    if args.command == "extract-css":
        emit_payload(extract_css_variables(args.path, max_files=args.max_files), args.format, args.output_json)
        return 0
    if args.command == "diff":
        emit_payload(diff_design_memory(args.before, args.after), args.format, args.output_json)
        return 0
    raise SystemExit(f"Unknown command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
