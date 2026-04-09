from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any

from .agent_review import write_agent_visual_review_packet
from .pipeline_qa import write_pipeline_qa_report
from .run_ledger import append_run_event
from .runtime import load_manifest, validate_brand_workspace_dir
from .card_engine import (
    ALLOWED_HTML_MATERIALS,
    DEFAULT_DESIGN_VARIANCE,
    _copy_asset,
    _generate_composition_assets,
    _headline_font_size,
    _qr_code_url,
    _reserve_manifest_version,
    _surface_size,
    _update_manifest_version,
    _verify_render,
    compose_share_card_html,
    render_html_to_png,
)
from .card_text import _truncate_multiline_copy
from .card_builder import _proof_weight_for, build_web_app_share_card_payload

ALLOWED_HTML_MATERIALS = set(ALLOWED_HTML_MATERIALS)


def evaluate_html_layout_warnings(card: Any) -> list[str]:
    warnings: list[str] = []
    headline_len = len(str(card.headline or ""))
    excerpt_len = len(str(card.proof_excerpt or ""))
    row_len = len(str(card.proof_row or ""))
    family = str(card.composition_mode or "")
    if headline_len > 44:
        warnings.append("Headline is long for social-card rendering; composition may compress hierarchy.")
    if excerpt_len > 420:
        warnings.append("Prompt detail is dense; renderer will truncate or compress for fit.")
    if row_len > 180:
        warnings.append("Secondary detail row is long; lower proof rows may become less legible.")
    if family in {"scan_card", "utility_sidebar"} and card.entity_type in {"prompt", "skill"} and excerpt_len < 80:
        warnings.append("Utility-led family has limited source detail; the card may feel too sparse.")
    if family == "statement_poster" and headline_len < 10:
        warnings.append("Statement poster family works best with a stronger title phrase.")
    if card.entity_type in {"prompt", "skill", "library"} and not str(card.source_url or "").strip():
        warnings.append("Governed artifact card is missing a source URL; QR and source truth affordance are unavailable.")
    return warnings


def execute_html_share_card_scratchpad(payload: dict, workflow_id: str | None = None) -> str:
    if payload.get("schema_type") != "generation_scratchpad":
        raise SystemExit("Scratchpad is not a generation_scratchpad payload.")
    brand_dir = validate_brand_workspace_dir(payload.get("brand_dir") or "", label="generation scratchpad brand_dir")
    material_type = str(payload.get("material_type") or "").strip()
    if material_type not in ALLOWED_HTML_MATERIALS:
        raise SystemExit(f"HTML share-card backend only supports: {', '.join(sorted(ALLOWED_HTML_MATERIALS))}.")

    workflow_ref = workflow_id or str(payload.get("workflow_id") or "")
    tag = str(payload.get("tag") or material_type or "share-card").replace(" ", "-").lower()
    vid = _reserve_manifest_version(brand_dir, material_type=material_type, workflow_id=workflow_ref, tag=tag)
    card = build_web_app_share_card_payload(payload)

    out_dir = brand_dir / "html-cards" / vid
    assets_dir = out_dir / "assets"
    out_dir.mkdir(parents=True, exist_ok=True)
    assets_dir.mkdir(parents=True, exist_ok=True)

    asset_names = {
        "logo": _copy_asset(card.logo_path, assets_dir, fallback_name="brand-logo.png"),
        "proof_crop": _copy_asset(card.proof_crop_path, assets_dir, fallback_name="proof-crop.png"),
    }
    asset_names.update(_generate_composition_assets(card, assets_dir))

    share_payload_path = out_dir / "share-card-payload.json"
    share_payload_path.write_text(json.dumps(card.to_dict(), indent=2) + "\n")

    width, height = _surface_size(material_type, layout_spec=card.layout_spec, entity_type=card.entity_type)
    png_path = brand_dir / f"{vid}-{tag}.png"
    html_path = brand_dir / f"{vid}-{tag}.html"
    html_text = compose_share_card_html(card, material_type=material_type, asset_names=asset_names, assets_dir=str(assets_dir.resolve()))
    html_path.write_text(html_text)
    rendered = render_html_to_png(html_path, png_path, width=width, height=height)
    if not rendered:
        raise SystemExit("Failed to render HTML share-card output. Google Chrome headless is required.")

    render_verification = _verify_render(
        png_path,
        html_text,
        expected_width=width,
        expected_height=height,
        headline=card.headline,
    )
    layout_warnings = evaluate_html_layout_warnings(card)
    files = [png_path.name]
    composition_family = str(card.composition_mode or "")
    composition_summary = str(card.composition_summary or "")

    manifest, _ = _update_manifest_version(
        brand_dir,
        vid,
        {
            "prompt_char_count": len(str(payload.get("execution_prompt") or payload.get("effective_prompt") or "")),
            "raw_prompt": str(payload.get("execution_prompt") or payload.get("effective_prompt") or payload.get("raw_prompt") or ""),
            "model": "html:chromium",
            "mode": payload.get("workflow_mode") or "hybrid",
            "material_type": material_type,
            "generation_mode": "html-share-card",
            "aspect_ratio": f"{width}:{height}",
            "tag": payload.get("tag") or "",
            "files": files,
            "reference_images": [],
            "reference_count": 0,
            "reference_dir": "",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "score": None,
            "notes": "",
            "status": None,
            "generation_scratchpad": payload.get("_scratchpad_path") or "",
            "workflow_id": workflow_ref,
            "source_version": payload.get("_previous_vid") or payload.get("source_version") or "",
            "branch_id": payload.get("branch_id") or workflow_ref,
            "parent_branch_id": payload.get("parent_branch_id") or "",
            "branch_status": payload.get("branch_status") or "active",
            "html_path": str(html_path),
            "render_source": "html_browser",
            "render_backend": "html",
            "share_card_payload_path": str(share_payload_path),
            "source_url": card.source_url,
            "entity_type": card.entity_type,
            "render_verification": render_verification,
            "selected_reference_ids": list(payload.get("selected_reference_ids") or []),
            "selected_inspiration_ids": list(payload.get("selected_inspiration_ids") or []),
            "critique_policy": dict(payload.get("critique_policy") or {}),
            "composition_family": composition_family,
            "composition_summary": composition_summary,
            "html_layout_warnings": layout_warnings,
        },
    )

    append_run_event(
        brand_dir,
        workflow_ref,
        stage="generate",
        event_type="generation_completed",
        attempt_id=vid,
        material_type=material_type,
        mode=payload.get("workflow_mode") or "",
        model="html:chromium",
        provider="html_browser",
        prompt=str(payload.get("execution_prompt") or payload.get("effective_prompt") or payload.get("raw_prompt") or ""),
        source_version=payload.get("_previous_vid") or payload.get("source_version") or "",
        output_version=vid,
        duration_ms=0,
        status="ok",
        branch_id=payload.get("branch_id") or workflow_ref,
        parent_branch_id=payload.get("parent_branch_id") or "",
        branch_status=payload.get("branch_status") or "active",
        data={
            "files": files,
            "html_path": str(html_path),
            "share_card_payload_path": str(share_payload_path),
            "render_source": "html_browser",
            "composition_family": composition_family,
            "layout_warnings": layout_warnings,
        },
    )

    agent_review_path = ""
    agent_review_ok = False
    try:
        _, agent_review_output = write_agent_visual_review_packet(brand_dir, vid, manifest=manifest)
        agent_review_path = str(agent_review_output)
        agent_review_ok = True
    except Exception as exc:
        print(f"WARNING: failed to build agent review packet for {vid}: {exc}", file=sys.stderr)
    manifest, _ = _update_manifest_version(
        brand_dir,
        vid,
        {
            "agent_review_path": agent_review_path if agent_review_ok else "",
            "agent_review_kind": "critique_rubric" if agent_review_ok else "",
            "visual_review_status": (
                "render_suspect" if not render_verification.get("passed")
                else ("pending" if agent_review_ok else "")
            ),
            "visual_review_provider": "agent" if agent_review_ok else "",
        },
    )
    try:
        report, output = write_pipeline_qa_report(brand_dir, vid)
        auto_review_path = str(output) if report else ""
        auto_review_ok = bool(report)
    except Exception as exc:
        print(f"WARNING: failed to build pipeline QA report for {vid}: {exc}", file=sys.stderr)
        auto_review_path = ""
        auto_review_ok = False
    _update_manifest_version(
        brand_dir,
        vid,
        {
            "auto_review_path": auto_review_path if auto_review_ok else "",
            "auto_review_kind": "pipeline_qa" if auto_review_ok else "",
        },
    )
    return vid

