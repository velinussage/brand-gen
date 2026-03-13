#!/usr/bin/env python3
"""Build a review packet for brand-material critique and refinement."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


def get_brand_dir(args) -> Path:
    if args.brand_dir:
        return Path(args.brand_dir).expanduser().resolve()
    if args.screenshots_dir:
        return Path(args.screenshots_dir).expanduser().resolve() / "brand-materials"
    return Path.cwd()


def load_manifest(brand_dir: Path) -> dict:
    path = brand_dir / "manifest.json"
    if not path.exists():
        raise SystemExit(f"Manifest not found: {path}")
    return json.loads(path.read_text())


def version_sort_key(vid: str) -> int:
    match = re.match(r"v(\d+)", vid)
    return int(match.group(1)) if match else 0


def resolve_version(manifest: dict, requested: str | None) -> str:
    if requested:
        if requested not in manifest["versions"]:
            raise SystemExit(f"Version not found in manifest: {requested}")
        return requested
    versions = sorted(manifest["versions"], key=version_sort_key)
    if not versions:
        raise SystemExit("No versions in manifest")
    return versions[-1]


def sentence_join(items: list[str]) -> str:
    items = [item for item in items if item]
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return ", ".join(items[:-1]) + f", and {items[-1]}"


def load_profile(brand_dir: Path) -> dict:
    path = brand_dir / "brand-profile.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}


def critique_checks(material_type: str) -> list[tuple[str, list[str]]]:
    common = [
        (
            "Strategic / message alignment",
            [
                "Can a skeptical user understand what this product is in under five seconds?",
                "Is the audience explicit, even if implicitly through the wording?",
                "Does the primary claim feel differentiated or could it belong to any generic SaaS tool?",
                "Do the CTA labels naturally follow from the headline claim?",
            ],
        ),
        (
            "Composition / balance",
            [
                "Is there a clear dominant focal point, or do copy and product compete?",
                "Does the whitespace feel intentional rather than accidental?",
                "Is the product visual large enough to earn trust without stealing the headline's job?",
                "Do the header, copy block, CTA row, and proof row feel rhythmically spaced?",
            ],
        ),
        (
            "Product truth / fidelity",
            [
                "Does the artifact preserve the real product UI rather than inventing a simplified fake?",
                "Are references influencing only framing, polish, and layout rather than changing the product itself?",
                "Do any labels, buttons, or cards feel hallucinated?",
            ],
        ),
    ]
    if material_type == "landing-hero":
        common.insert(
            1,
            (
                "Copy / hero structure",
                [
                    "Is the hero using a clear arc: hook → product promise → trust proof → action?",
                    "Is the headline specific enough to be memorable but short enough to scan quickly?",
                    "Does the subheadline add new information rather than repeating the headline?",
                    "Do the trust items prove the claim instead of restating it?",
                ],
            ),
        )
    return common


def build_heuristics(entry: dict) -> list[str]:
    hints: list[str] = []
    structured = entry.get("structured_input") or {}
    headline = structured.get("headline", "")
    subheadline = structured.get("subheadline", "")
    trust_items = structured.get("trust_items", []) or []
    ctas = [structured.get("primary_cta", ""), structured.get("secondary_cta", "")]
    if headline and len(headline.split()) > 6:
        hints.append("Headline may be slightly long; test whether it can lose one abstraction word.")
    if subheadline and len(subheadline.split()) > 14:
        hints.append("Subheadline is dense; consider shortening to one promise + one proof clause.")
    if trust_items and any("govern" in item.lower() for item in trust_items) and headline and "govern" in headline.lower():
        hints.append("Governance is repeated between the headline and trust row; consider using the trust row for proof instead of repeating the category.")
    if len([cta for cta in ctas if cta]) >= 2:
        hints.append("Check whether the secondary CTA is genuinely secondary or competing with the primary CTA.")
    if entry.get("material_type") == "landing-hero":
        hints.append("Landing heroes should be reviewed as a full system: logo/nav, hook, proof, CTA, and product shot balance.")
    return hints


def render_packet(version: str, entry: dict, brand_dir: Path, profile: dict) -> str:
    structured = entry.get("structured_input") or {}
    artifact_files = entry.get("files", [])
    artifact_paths = [str(brand_dir / name) for name in artifact_files]
    refs = entry.get("reference_images", [])
    ref_paths = [str(brand_dir / name) for name in refs]
    checks = critique_checks(entry.get("material_type", ""))
    heuristics = build_heuristics(entry)

    lines = [
        f"# Review packet — {version}",
        "",
        "## Artifact summary",
        f"- Material type: {entry.get('material_type', 'n/a')}",
        f"- Model / mode: {entry.get('model', 'n/a')} / {entry.get('mode', 'n/a')}",
        f"- Aspect ratio: {entry.get('aspect_ratio', 'n/a')}",
        f"- Tag: {entry.get('tag', 'n/a')}",
        f"- Timestamp: {entry.get('timestamp', 'n/a')}",
        "",
        "## Files",
    ]
    for path in artifact_paths:
        lines.append(f"- {path}")
    if ref_paths:
        lines += ["", "## References"]
        for path in ref_paths:
            lines.append(f"- {path}")

    if profile:
        lines += [
            "",
            "## Brand profile context",
            f"- Brand: {profile.get('brand_name', 'n/a')}",
            f"- Description: {profile.get('description', 'n/a')}",
            f"- Keywords: {sentence_join(profile.get('keywords', [])[:8]) or 'n/a'}",
            f"- Colors: {sentence_join(profile.get('color_candidates', [])[:6]) or 'n/a'}",
            f"- Fonts: {sentence_join(profile.get('font_candidates', [])[:4]) or 'n/a'}",
        ]

    if structured:
        lines += [
            "",
            "## Structured input",
            f"- Eyebrow: {structured.get('eyebrow', 'n/a') or 'n/a'}",
            f"- Headline: {structured.get('headline', 'n/a') or 'n/a'}",
            f"- Subheadline: {structured.get('subheadline', 'n/a') or 'n/a'}",
            f"- Nav items: {sentence_join(structured.get('nav_items', [])) or 'n/a'}",
            f"- Header CTA: {structured.get('header_cta', 'n/a') or 'n/a'}",
            f"- Primary CTA: {structured.get('primary_cta', 'n/a') or 'n/a'}",
            f"- Secondary CTA: {structured.get('secondary_cta', 'n/a') or 'n/a'}",
            f"- Trust row: {sentence_join(structured.get('trust_items', [])) or 'n/a'}",
            f"- Layout: {structured.get('layout', 'n/a') or 'n/a'}",
        ]

    lines += [
        "",
        "## Review process",
        "Run these independent critique lenses in parallel, then merge findings by severity.",
        "",
    ]

    for title, questions in checks:
        lines.append(f"### {title}")
        for question in questions:
            lines.append(f"- {question}")
        lines.append("")

    lines += [
        "## Severity buckets",
        "",
        "### P1 — Blocks shipping",
        "- Core message is unclear, misleading, or not differentiated",
        "- Product truth is violated or UI fidelity is lost",
        "- Layout balance makes the hero hard to parse",
        "",
        "### P2 — Should fix",
        "- Headline/subheadline/CTA hierarchy is muddy",
        "- Trust row or proof is weak or repetitive",
        "- Copy is technically correct but not tight or confident",
        "",
        "### P3 — Nice to have",
        "- Minor rhythm, spacing, wording, or polish issues",
        "",
        "## Heuristic watch-outs",
    ]
    if heuristics:
        for hint in heuristics:
            lines.append(f"- {hint}")
    else:
        lines.append("- No obvious heuristic warnings.")

    lines += [
        "",
        "## Review output format",
        "```text",
        "## Review: [artifact]",
        "",
        "### P1 — Blocks shipping",
        "[Critical message, fidelity, or balance issues.]",
        "",
        "### P2 — Should fix",
        "[Important clarity, hierarchy, or composition issues.]",
        "",
        "### P3 — Nice to have",
        "[Minor polish items.]",
        "",
        "### Clean",
        "[What is already working well.]",
        "",
        "### Next refinement",
        "[One change to make next, and why.]",
        "```",
        "",
        "## Refine rule",
        "After the review, make only one substantive improvement at a time, then re-review.",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a review packet for brand-material critique")
    parser.add_argument("--brand-dir", help="Brand materials directory")
    parser.add_argument("--screenshots-dir", help="Base screenshots directory; review packet uses $DIR/brand-materials")
    parser.add_argument("--version", help="Version id to review; defaults to latest")
    parser.add_argument("--output", required=True, help="Output markdown path")
    args = parser.parse_args()

    brand_dir = get_brand_dir(args)
    manifest = load_manifest(brand_dir)
    version = resolve_version(manifest, args.version)
    entry = manifest["versions"][version]
    profile = load_profile(brand_dir)
    output = Path(args.output).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_packet(version, entry, brand_dir, profile))
    print(f"Brand review packet: {output}")
    print(f"Version: {version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
