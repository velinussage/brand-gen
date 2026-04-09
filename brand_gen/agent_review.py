from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .runtime import SUPPORTED_IMAGE_EXTS, load_blackboard, load_manifest
from .runtime_io import load_json_file
from .share_card_renderer import taste_design_directives


def _brand_dna_summary(board: dict[str, Any]) -> dict[str, str]:
    brand_dna = board.get("brand_dna") or {}
    palette = ", ".join(str(color) for color in (brand_dna.get("palette_direction") or [])[:6])
    approved = "; ".join(str(item) for item in (brand_dna.get("approved_graphic_devices") or [])[:4])
    forbidden = "; ".join(str(item) for item in (brand_dna.get("forbidden_elements") or [])[:4])
    return {
        "palette": palette,
        "approved_devices": approved,
        "forbidden_elements": forbidden,
    }


def _resolve_brief(brand_dir: Path, version_id: str, entry: dict[str, Any]) -> str:
    scratchpad_path = Path(str(entry.get("generation_scratchpad") or "")).expanduser()
    if scratchpad_path and not scratchpad_path.is_absolute():
        scratchpad_path = (brand_dir / scratchpad_path).resolve()
    scratchpad = load_json_file(scratchpad_path)
    sidecar = load_json_file(brand_dir / f"{version_id}.prompts.json")
    prompt_review = sidecar.get("prompt_review") or {}
    prompt_context = scratchpad.get("prompt_context") or {}
    candidates = [
        entry.get("execution_prompt"),
        sidecar.get("execution_prompt"),
        scratchpad.get("execution_prompt"),
        sidecar.get("effective_prompt"),
        scratchpad.get("effective_prompt"),
        prompt_review.get("resolved_prompt"),
        scratchpad.get("raw_prompt"),
        entry.get("prompt"),
        entry.get("effective_prompt"),
        entry.get("raw_prompt"),
        ((scratchpad.get("plan") or {}).get("prompt_seed")),
        prompt_context.get("resolved_prompt"),
    ]
    for candidate in candidates:
        text = str(candidate or "").strip()
        if text:
            return text
    return ""


def _summarize_review_intent(entry: dict[str, Any], scratchpad: dict[str, Any], sidecar: dict[str, Any]) -> dict[str, Any]:
    plan = scratchpad.get("plan") or {}
    prompt_review = sidecar.get("prompt_review") or scratchpad.get("prompt_review") or {}
    checks = scratchpad.get("checks") or {}
    purpose = str(plan.get("purpose") or "").strip()
    target_surface = str(plan.get("target_surface") or "").strip()
    product_truth = str(plan.get("product_truth_expression") or "").strip()
    preserve = [str(item).strip() for item in (plan.get("preserve") or []) if str(item).strip()]
    avoid = [str(item).strip() for item in (plan.get("ban") or []) if str(item).strip()]
    review_focus: list[str] = []
    for item in list(prompt_review.get("recommendations") or []) + list(checks.get("warnings") or []):
        text = str(item).strip()
        lower = text.lower()
        if not text:
            continue
        if any(token in lower for token in ["proof inset", "secondary", "screenshot-dominant", "logo", "brand field", "headline"]):
            if text not in review_focus:
                review_focus.append(text)
    if preserve and not any("proof" in item.lower() for item in review_focus):
        review_focus.extend(item for item in preserve if "proof" in item.lower())
    if avoid and not any("screenshot" in item.lower() for item in review_focus):
        review_focus.extend(item for item in avoid if "screenshot" in item.lower())
    return {
        "intent_summary": purpose,
        "target_surface": target_surface,
        "product_truth": product_truth,
        "must_preserve": preserve,
        "must_avoid": avoid,
        "review_focus": review_focus[:5],
    }


def _render_review_brief(summary: dict[str, Any], fallback_brief: str) -> str:
    lines: list[str] = []
    if summary.get("intent_summary"):
        lines.append(f"Intent: {summary['intent_summary']}")
    if summary.get("target_surface"):
        lines.append(f"Surface: {summary['target_surface']}")
    if summary.get("product_truth"):
        lines.append(f"Product truth: {summary['product_truth']}")
    preserve = list(summary.get("must_preserve") or [])
    avoid = list(summary.get("must_avoid") or [])
    focus = list(summary.get("review_focus") or [])
    if preserve:
        lines.append("Preserve: " + "; ".join(preserve[:3]))
    if avoid:
        lines.append("Avoid: " + "; ".join(avoid[:3]))
    if focus:
        lines.append("Review focus: " + "; ".join(focus[:3]))
    if lines:
        return "\n".join(lines)
    return fallback_brief


def build_agent_visual_review_packet(
    brand_dir: Path,
    version_id: str,
    *,
    manifest: dict[str, Any] | None = None,
    board: dict[str, Any] | None = None,
) -> dict[str, Any]:
    brand_dir = Path(brand_dir).expanduser().resolve()
    manifest = manifest or load_manifest(brand_dir)
    entry = ((manifest.get("versions") or {}).get(version_id) or {})
    if not entry:
        raise SystemExit(f"Version {version_id} not found")

    image_files = [
        brand_dir / name
        for name in (entry.get("files") or [])
        if Path(name).suffix.lower() in SUPPORTED_IMAGE_EXTS
    ]
    image_path = next((path for path in image_files if path.exists()), None)
    if image_path is None:
        raise SystemExit(f"No image file found for {version_id}")

    board = board or load_blackboard(brand_dir)
    scratchpad_path = Path(str(entry.get("generation_scratchpad") or "")).expanduser()
    if scratchpad_path and not scratchpad_path.is_absolute():
        scratchpad_path = (brand_dir / scratchpad_path).resolve()
    scratchpad = load_json_file(scratchpad_path)
    sidecar = load_json_file(brand_dir / f"{version_id}.prompts.json")
    fallback_brief = _resolve_brief(brand_dir, version_id, entry)
    review_summary = _summarize_review_intent(entry, scratchpad, sidecar)
    brief = _render_review_brief(review_summary, fallback_brief)
    suggested_output = brand_dir / "reviews" / f"{version_id}-agent-critique.json"

    # Include design system context for HTML share cards
    is_html_card = entry.get("render_backend") == "html" or entry.get("material_type") in ("social", "announcement-card", "x-feed")
    design_system_context = taste_design_directives(
        int(entry.get("design_variance") or scratchpad.get("design_variance") or 5)
    ) if is_html_card else ""

    return {
        "schema_type": "agent_visual_review_packet",
        "schema_version": 1,
        "version": version_id,
        "image_path": str(image_path),
        "brief": brief[:1500],
        "intent_summary": review_summary.get("intent_summary") or "",
        "target_surface": review_summary.get("target_surface") or "",
        "must_preserve": list(review_summary.get("must_preserve") or []),
        "must_avoid": list(review_summary.get("must_avoid") or []),
        "review_focus": list(review_summary.get("review_focus") or []),
        "brand_dna": _brand_dna_summary(board),
        "design_system": design_system_context,
        "review_status": "pending",
        "preferred_reviewer": "agent",
        "submission": {
            "suggested_output_path": str(suggested_output),
            "command": f"bgen submit-critique {version_id} --critique-json {suggested_output} --format json",
        },
        "rubric": {
            "instructions": (
                "Look at the image and evaluate it against the brand DNA, brief, and design system. "
                "Return your critique as JSON with these keys."
            ),
            "schema": {
                "approved": "boolean — true only if all P1 checks pass",
                "p1": "list of blocking issues (wrong palette, hallucinated UI, missing logo when required, invented text)",
                "p2": "list of should-fix issues (composition, hierarchy, whitespace, brand fit)",
                "p3": "list of nice-to-have polish items",
                "clean": "list of things that are working well",
                "palette_match": "float 0-1 — how well dominant colors match brand hex values",
                "logo_visible": "boolean — whether the brand mark/logo is recognizable",
                "hallucinated_elements": "list of UI elements or text that appear invented",
                "text_accuracy": "float 0-1 — how accurately visible text matches intended copy",
                "text_issues": "list of specific text rendering problems",
                "composition_notes": "string — brief composition assessment",
                "refinement_suggestion": "string — one concrete change for the next iteration",
            },
        },
        "next_steps": [
            "An agent should open the image and review it visually.",
            "Save the critique JSON using the schema above.",
            "Submit it with the provided submit-critique command.",
        ],
    }


def write_agent_visual_review_packet(
    brand_dir: Path,
    version_id: str,
    *,
    manifest: dict[str, Any] | None = None,
    board: dict[str, Any] | None = None,
    output: Path | None = None,
) -> tuple[dict[str, Any], Path]:
    brand_dir = Path(brand_dir).expanduser().resolve()
    packet = build_agent_visual_review_packet(
        brand_dir,
        version_id,
        manifest=manifest,
        board=board,
    )
    out_path = Path(output).expanduser().resolve() if output else brand_dir / "reviews" / f"{version_id}-agent-review.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(packet, indent=2) + "\n")
    return packet, out_path
