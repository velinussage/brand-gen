from __future__ import annotations

import subprocess
import sys

from .blackboard import blackboard_path, load_blackboard
from .runtime import *
from .runtime_models import recommend_text_model
from .material_planning import *
from .runtime_support import html_escape, version_sort_key as _version_sort_key


def summarize_version_metadata(version_id: str, entry: dict) -> dict:
    prompt_len = entry.get("prompt_char_count") or len(entry.get("prompt") or "")
    raw_prompt = entry.get("raw_prompt") or ""
    prompt_prelude = entry.get("prompt_prelude") or ""
    critic = entry.get("critic_summary") or {}
    prompt_review = entry.get("prompt_review") or {}
    return {
        "version": version_id,
        "material_type": entry.get("material_type") or "",
        "generation_mode": entry.get("generation_mode") or "",
        "mode": entry.get("mode") or "",
        "model": entry.get("model") or "",
        "aspect_ratio": entry.get("aspect_ratio") or "",
        "timestamp": entry.get("timestamp") or "",
        "score": entry.get("score"),
        "status": entry.get("status") or "",
        "workflow_id": entry.get("workflow_id") or "",
        "source_version": entry.get("source_version") or "",
        "scratchpad": entry.get("generation_scratchpad") or "",
        "auto_review_path": entry.get("auto_review_path") or "",
        "files": list(entry.get("files") or []),
        "reference_images": list(entry.get("reference_images") or []),
        "reference_count": entry.get("reference_count") or 0,
        "prompt_chars": prompt_len,
        "raw_prompt_chars": len(raw_prompt),
        "prelude_chars": len(prompt_prelude),
        "critic_issues": list(critic.get("issues") or []),
        "prompt_review_ok": prompt_review.get("ok", True),
        "prompt_review_warnings": list(prompt_review.get("warnings") or []),
        "notes": entry.get("notes") or "",
        "tag": entry.get("tag") or "",
        "prompt": entry.get("prompt") or "",
        "raw_prompt": raw_prompt,
    }


def build_agent_regeneration_prompt(version_id: str, entry: dict) -> str:
    meta = summarize_version_metadata(version_id, entry)
    lines = [
        "Use brand-gen in the current active workspace.",
        f"Start from version {version_id} as the baseline.",
        f"Material type: {meta['material_type'] or 'material'}.",
        f"Workflow mode: {meta['mode'] or 'hybrid'}.",
    ]
    if meta["aspect_ratio"]:
        lines.append(f"Aspect ratio: {meta['aspect_ratio']}.")
    if meta["model"]:
        _vlm_critique_path = entry.get("vlm_critique_path") or ""
        _text_model_rec = None
        if _vlm_critique_path:
            try:
                _critique_data = json.loads(Path(_vlm_critique_path).read_text())
                _text_model_rec = recommend_text_model(
                    _critique_data,
                    meta["model"],
                    meta["material_type"],
                    bool(meta["reference_images"]),
                )
            except (json.JSONDecodeError, OSError):
                pass
        if _text_model_rec:
            _text_issues_str = ", ".join(str(i) for i in (_critique_data.get("text_issues") or [])[:3])
            lines.append(
                f"Switch to {_text_model_rec} for this iteration — the previous model had text rendering issues: {_text_issues_str or 'low text accuracy'}."
            )
        else:
            lines.append(f"Prefer the same model unless there is a clear reason to switch: {meta['model']}.")
    lines.append("Keep the brand direction and any approved messaging that made this version useful.")
    if meta["notes"]:
        lines.append(f"Existing notes to preserve or react to: {meta['notes'][:220]}")
    if meta["critic_issues"]:
        lines.append("Avoid repeating these issues: " + "; ".join(str(item) for item in meta["critic_issues"][:3]))
    if meta["reference_images"]:
        lines.append("Replace the primary product/reference image with <NEW_SCREEN_PATH> if you are using a new screen from the app.")
    else:
        lines.append("If you want to incorporate a new app screen, attach it as <NEW_SCREEN_PATH> and use it as the new primary product truth reference.")
    if meta["material_type"] in {"landing-hero", "social", "campaign-poster", "proof-poster", "merch-poster", "podcast-cover", "podcast-banner", "og-card"}:
        lines.append("If visible copy appears, use explicit user-provided copy or approved messaging only; do not invent new slogans or event names.")
    if meta["raw_prompt"]:
        lines.append(f"Starting prompt seed from {version_id}: {meta['raw_prompt'][:400]}")
    lines.append(f"After generating the new version, compare it against {version_id} and summarize what improved.")
    return "\n".join(lines)


def _build_context_panels(brand_dir: Path) -> str:
    """Build collapsible HTML panels for blackboard, profile, and identity context."""
    parts: list[str] = []

    # Load blackboard
    board = {}
    bp = blackboard_path(brand_dir)
    if bp.exists():
        try:
            board = json.loads(bp.read_text())
        except (json.JSONDecodeError, OSError):
            pass

    # Load profile and identity
    profile: dict = {}
    identity: dict = {}
    try:
        _, _, profile, identity = load_brand_memory(brand_dir)
    except Exception:
        pass

    # ── Brand DNA / Identity Summary ──
    dna = board.get("brand_dna") or {}
    if dna:
        rows = []
        for key in ["brand_name", "summary", "homepage_url", "tone_words", "palette_direction",
                     "typography_cues", "shape_language", "approved_graphic_devices",
                     "forbidden_elements", "prompt_prelude", "inspiration_translation_rule",
                     "non_interface_rule", "copy_rule"]:
            val = dna.get(key)
            if not val:
                continue
            if isinstance(val, list):
                display = ", ".join(str(v) for v in val[:12])
            elif isinstance(val, dict):
                display = json.dumps(val, indent=2)[:500]
            else:
                display = str(val)[:500]
            rows.append(f"<div class='ctx-key'>{html_escape(key)}</div><div class='ctx-val'>{html_escape(display)}</div>")
        if rows:
            parts.append(
                '<details class="context-panel"><summary>Brand DNA</summary>'
                '<div class="ctx-grid">' + "".join(rows) + "</div></details>"
            )

    # ── Active Brief ──
    brief = board.get("active_brief") or {}
    if brief and brief.get("stage"):
        rows = []
        for key in ["stage", "material_type", "mode", "purpose", "target_surface",
                     "product_truth_expression", "abstraction_level", "system_mechanic",
                     "preserve", "push", "ban", "prompt_seed", "branch_id", "source_version"]:
            val = brief.get(key)
            if not val:
                continue
            if isinstance(val, list):
                display = ", ".join(str(v) for v in val[:10])
            else:
                display = str(val)[:400]
            rows.append(f"<div class='ctx-key'>{html_escape(key)}</div><div class='ctx-val'>{html_escape(display)}</div>")
        if rows:
            parts.append(
                '<details class="context-panel"><summary>Active Brief</summary>'
                '<div class="ctx-grid">' + "".join(rows) + "</div></details>"
            )

    # ── Recent Decisions ──
    decisions = (board.get("decisions") or [])[-10:]
    if decisions:
        decision_rows = []
        for d in reversed(decisions):
            ts = html_escape(d.get("timestamp") or "")
            agent = html_escape(d.get("agent") or "")
            text = html_escape(d.get("decision") or "")
            wf = html_escape(d.get("workflow_id") or "")[:12]
            sev = html_escape(d.get("severity") or "")
            badge = f' <span class="sev-badge">{sev}</span>' if sev else ""
            wf_tag = f' <span class="wf-tag">{wf}</span>' if wf else ""
            decision_rows.append(f"<div class='decision-row'><span class='decision-ts'>{ts}</span>{wf_tag}{badge} <strong>{agent}</strong>: {text}</div>")
        parts.append(
            '<details class="context-panel"><summary>Recent Decisions (' + str(len(decisions)) + ')</summary>'
            '<div class="decision-list">' + "".join(decision_rows) + "</div></details>"
        )

    # ── Profile Overview ──
    if profile:
        rows = []
        for key in ["brand_name", "description", "homepage_url", "keywords",
                     "color_candidates", "font_candidates", "logo_candidates",
                     "brand_guardrail_prelude"]:
            val = profile.get(key)
            if not val:
                continue
            if isinstance(val, list):
                display = ", ".join(str(v) for v in val[:12])
            else:
                display = str(val)[:500]
            rows.append(f"<div class='ctx-key'>{html_escape(key)}</div><div class='ctx-val'>{html_escape(display)}</div>")
        if rows:
            parts.append(
                '<details class="context-panel"><summary>Profile</summary>'
                '<div class="ctx-grid">' + "".join(rows) + "</div></details>"
            )

    # ── Identity Highlights ──
    if identity:
        rows = []
        brand = identity.get("brand") or {}
        core = identity.get("identity_core") or {}
        messaging = identity.get("messaging") or {}
        guardrails = identity.get("generation_guardrails") or {}
        for label, val in [
            ("brand.name", brand.get("name")),
            ("brand.summary", brand.get("summary")),
            ("tone_words", core.get("tone_words")),
            ("brand_anchors", core.get("brand_anchors")),
            ("forbidden_elements", core.get("forbidden_elements")),
            ("approved_graphic_devices", core.get("approved_graphic_devices")),
            ("tagline", messaging.get("tagline")),
            ("elevator", messaging.get("elevator")),
            ("prompt_prelude", guardrails.get("prompt_prelude")),
            ("inspiration_translation_rule", guardrails.get("inspiration_translation_rule")),
        ]:
            if not val:
                continue
            if isinstance(val, list):
                display = ", ".join(str(v) for v in val[:12])
            else:
                display = str(val)[:500]
            rows.append(f"<div class='ctx-key'>{html_escape(label)}</div><div class='ctx-val'>{html_escape(display)}</div>")
        if rows:
            parts.append(
                '<details class="context-panel"><summary>Identity</summary>'
                '<div class="ctx-grid">' + "".join(rows) + "</div></details>"
            )

    # ── Generated Assets (recent) ──
    assets = (board.get("generated_assets") or [])[-8:]
    if assets:
        asset_rows = []
        for a in reversed(assets):
            vid = html_escape(a.get("version_id") or "")
            mat = html_escape(a.get("material_type") or "")
            model = html_escape(a.get("model") or "")
            score = a.get("score")
            score_str = f" score={score}" if score is not None else ""
            asset_rows.append(f"<div class='decision-row'><strong>{vid}</strong> {mat} \u00b7 {model}{html_escape(score_str)}</div>")
        parts.append(
            '<details class="context-panel"><summary>Recent Assets (' + str(len(assets)) + ')</summary>'
            '<div class="decision-list">' + "".join(asset_rows) + "</div></details>"
        )

    if not parts:
        return ""
    return '<div class="context-section">' + "".join(parts) + "</div>"


def generate_compare_board(
    brand_dir: Path,
    vids: list[str] | None = None,
    *,
    manifest: dict | None = None,
    embed: bool = False,
    filter_label: str = "all versions",
    output: Path | None = None,
    open_browser: bool = False,
) -> Path:
    """Generate compare.html for the given versions (or all if *vids* is None).

    Returns the path to the written file.
    """
    if manifest is None:
        manifest = load_manifest(brand_dir)
    if vids is None:
        vids = list(manifest["versions"].keys())
    if not vids:
        out = output or (brand_dir / "compare.html")
        return out

    ordered_vids = sorted(vids, key=_version_sort_key, reverse=True)
    latest_selected_version = ordered_vids[0] if ordered_vids else ""
    latest_overall_version = next(
        iter(sorted(manifest["versions"].keys(), key=_version_sort_key, reverse=True)), ""
    )

    cards_html = []
    for vid in ordered_vids:
        version = manifest["versions"].get(vid)
        if not version:
            continue
        media_file = None
        preferred_exts = [".png", ".jpg", ".jpeg", ".gif", ".mp4", ".webm", ".mov", ".svg", ".webp"]
        for ext in preferred_exts:
            for name in version.get("files", []):
                fp = brand_dir / name
                if fp.exists() and fp.suffix.lower() == ext:
                    media_file = fp
                    break
            if media_file:
                break
        if not media_file:
            for name in version.get("files", []):
                fp = brand_dir / name
                if fp.exists():
                    media_file = fp
                    break
        media_html = media_tag(media_file, embed=embed) if media_file and media_file.exists() else '<div class="no-media">No media</div>'
        meta = summarize_version_metadata(vid, version)
        score = meta.get("score")
        stars = ("\u2605" * score + "\u2606" * (5 - score)) if score else "unscored"
        status = meta.get("status") or ""
        prompt = html_escape(meta.get("prompt") or "\u2014")
        raw_prompt = html_escape(meta.get("raw_prompt") or "\u2014")
        notes = html_escape(meta.get("notes") or "")
        prompt_len = meta.get("prompt_chars") or 0
        workflow_id = meta.get("workflow_id") or ""
        scratchpad_path = meta.get("scratchpad") or ""
        source_version = meta.get("source_version") or ""
        critic_issues = meta.get("critic_issues") or []
        pr_ok = meta.get("prompt_review_ok", True)
        pr_warnings = meta.get("prompt_review_warnings") or []
        ref_count = meta.get("reference_count") or 0
        aspect = meta.get("aspect_ratio") or ""
        regen_prompt = html_escape(build_agent_regeneration_prompt(vid, version))
        diag_parts = []
        diag_parts.append(f"prompt: {prompt_len} chars")
        diag_parts.append(f"refs: {ref_count}")
        if aspect:
            diag_parts.append(f"aspect: {aspect}")
        if workflow_id:
            diag_parts.append(f"wf: {workflow_id[:12]}")
        if source_version:
            diag_parts.append(f"from: {source_version}")
        if not pr_ok:
            diag_parts.append("⚠ prompt review failed")
        if pr_warnings:
            diag_parts.append(f"⚠ {len(pr_warnings)} prompt warnings")
        if critic_issues:
            diag_parts.append(f"⚠ {len(critic_issues)} critic issues")
        diag_html = f'<div class="diag">{" \u00b7 ".join(diag_parts)}</div>'
        critic_html = ""
        if critic_issues:
            escaped_issues = [html_escape(i) for i in critic_issues[:3]]
            critic_html = '<div class="critic-issues">' + "<br>".join(f"\u2022 {i}" for i in escaped_issues) + "</div>"
        warnings_html = ""
        if pr_warnings:
            warnings_html = '<div class="prompt-warnings">' + "<br>".join(f"\u2022 {html_escape(i)}" for i in pr_warnings[:3]) + "</div>"
        metadata_rows = [
            ("Timestamp", meta.get("timestamp") or "n/a"),
            ("Material", meta.get("material_type") or "n/a"),
            ("Mode", meta.get("mode") or "n/a"),
            ("Model", meta.get("model") or "n/a"),
            ("Aspect", meta.get("aspect_ratio") or "n/a"),
            ("Refs", str(meta.get("reference_count") or 0)),
            ("Workflow", workflow_id or "n/a"),
            ("Source", source_version or "n/a"),
            ("Scratchpad", scratchpad_path or "n/a"),
            ("Pipeline QA", meta.get("auto_review_path") or "n/a"),
        ]
        metadata_html = "".join(
            f"<div class='meta-key'>{html_escape(label)}</div><div class='meta-value'>{html_escape(value)}</div>"
            for label, value in metadata_rows
        )
        latest_badge = (
            '<div class="latest-badge">Most recent overall</div>' if vid == latest_overall_version
            else ('<div class="latest-badge">Most recent in view</div>' if vid == latest_selected_version else "")
        )
        cards_html.append(f'''
    <div class="card {status}" data-version="{html_escape(vid)}" data-material="{html_escape(meta.get('material_type') or '')}" data-status="{html_escape(status or 'unscored')}" data-score="{html_escape(score or '')}">
      <div class="media expandable" role="button" tabindex="0" aria-label="Expand {vid}" data-version="{vid}">
        <div class="expand-chip">Click to expand</div>
        {latest_badge}
        {media_html}
      </div>
      <div class="meta">
        <div class="version">{vid} <span class="score">{stars}</span></div>
        <div class="info">{version.get('material_type','')} \u00b7 {version.get('generation_mode','')} \u00b7 {version.get('model','')}</div>
        {diag_html}
        {critic_html}
        {warnings_html}
        <div class="meta-grid">{metadata_html}</div>
        <details class="detail-block"><summary>Resolved prompt</summary><div class="prompt">{prompt}</div></details>
        <details class="detail-block"><summary>Raw prompt</summary><div class="prompt">{raw_prompt}</div></details>
        <details class="detail-block openable"><summary>Paste-to-agent regeneration prompt</summary><div class="copy-row"><button class="copy-btn" data-copy="{regen_prompt}">Copy prompt</button></div><textarea class="agent-prompt" readonly>{regen_prompt}</textarea></details>
        {"<div class='notes'>" + notes + "</div>" if notes else ""}
      </div>
    </div>''')

    context_html = _build_context_panels(brand_dir)
    total_versions = len(manifest["versions"])
    scored_versions = sum(1 for v in manifest["versions"].values() if v.get("score") is not None)
    favorite_versions = sum(1 for v in manifest["versions"].values() if v.get("status") == "favorite")
    html = f'''<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Brand Material Comparison</title>
<style>
  :root {{ color-scheme: dark; }}
  body {{ font-family: system-ui, -apple-system, sans-serif; background: #1a1a1a; color: #eee; margin: 2rem; }}
  body.modal-open {{ overflow: hidden; }}
  h1 {{ font-size: 1.5rem; font-weight: 600; margin-bottom: 0.4rem; }}
  .subhead {{ color: #9b9b9b; margin-bottom: 1rem; font-size: 0.92rem; }}
  .toolbar {{ position: sticky; top: 0; z-index: 10; display: flex; flex-wrap: wrap; gap: 0.75rem; align-items: center; background: rgba(26,26,26,0.96); border: 1px solid #333; border-radius: 14px; padding: 0.9rem 1rem; margin-bottom: 1.25rem; }}
  .toolbar .summary {{ color: #bdbdbd; font-size: 0.88rem; }}
  .toolbar input, .toolbar select {{ background: #111; color: #eee; border: 1px solid #3a3a3a; border-radius: 10px; padding: 0.55rem 0.7rem; font: inherit; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(340px, 1fr)); gap: 1.5rem; }}
  .card {{ background: #2a2a2a; border-radius: 12px; overflow: hidden; transition: transform 0.15s, box-shadow 0.15s; box-shadow: 0 10px 24px rgba(0,0,0,0.18); }}
  .card.hidden {{ display: none; }}
  .card:hover {{ transform: translateY(-2px); box-shadow: 0 14px 28px rgba(0,0,0,0.24); }}
  .media {{ position: relative; background: #111; }}
  .media.expandable {{ cursor: zoom-in; outline: none; }}
  .media.expandable:focus-visible {{ box-shadow: inset 0 0 0 2px #f5a623; }}
  .media img, .media video {{ width: 100%; display: block; background: #111; }}
  .media video {{ max-height: 420px; object-fit: contain; }}
  .expand-chip {{ position: absolute; top: 0.7rem; right: 0.7rem; z-index: 2; background: rgba(0,0,0,0.58); color: #fff; font-size: 0.72rem; padding: 0.35rem 0.55rem; border-radius: 999px; pointer-events: none; letter-spacing: 0.02em; }}
  .latest-badge {{ position: absolute; top: 0.7rem; left: 0.7rem; z-index: 2; background: rgba(245,166,35,0.92); color: #1a1a1a; font-size: 0.72rem; font-weight: 700; padding: 0.35rem 0.55rem; border-radius: 999px; pointer-events: none; letter-spacing: 0.02em; }}
  .no-media {{ height: 220px; display: flex; align-items: center; justify-content: center; background: #333; color: #666; }}
  .meta {{ padding: 1rem; }}
  .version {{ font-size: 1.1rem; font-weight: 700; }}
  .score {{ color: #f5a623; font-size: 0.95rem; }}
  .info {{ font-size: 0.8rem; color: #888; margin-top: 0.25rem; }}
  .diag {{ font-size: 0.75rem; color: #7a7a7a; margin-top: 0.3rem; font-family: ui-monospace, 'SF Mono', monospace; }}
  .critic-issues {{ font-size: 0.75rem; color: #e8a040; margin-top: 0.3rem; line-height: 1.3; }}
  .prompt-warnings {{ font-size: 0.75rem; color: #d7c06f; margin-top: 0.3rem; line-height: 1.3; }}
  .meta-grid {{ display: grid; grid-template-columns: 110px 1fr; gap: 0.35rem 0.65rem; margin-top: 0.7rem; font-size: 0.78rem; }}
  .meta-key {{ color: #8a8a8a; }}
  .meta-value {{ color: #ddd; word-break: break-word; }}
  .detail-block {{ margin-top: 0.75rem; background: #232323; border: 1px solid #333; border-radius: 10px; padding: 0.55rem 0.7rem; }}
  .detail-block summary {{ cursor: pointer; color: #ddd; font-size: 0.82rem; }}
  .prompt {{ font-size: 0.82rem; color: #aaa; margin-top: 0.5rem; line-height: 1.4; max-height: 6em; overflow-y: auto; }}
  .copy-row {{ margin-top: 0.55rem; }}
  .copy-btn {{ appearance: none; border: 0; background: #3a3a3a; color: #fff; border-radius: 999px; padding: 0.45rem 0.75rem; cursor: pointer; font: inherit; }}
  .agent-prompt {{ width: 100%; min-height: 12rem; margin-top: 0.6rem; background: #111; color: #ddd; border: 1px solid #3a3a3a; border-radius: 10px; padding: 0.75rem; font: 12px/1.45 ui-monospace, 'SF Mono', monospace; resize: vertical; }}
  .notes {{ font-size: 0.82rem; color: #8f8; margin-top: 0.5rem; font-style: italic; }}
  .card.favorite {{ border: 2px solid #f5a623; }}
  .card.rejected {{ opacity: 0.45; }}
  .context-section {{ margin-bottom: 1.5rem; display: flex; flex-direction: column; gap: 0.5rem; }}
  .context-panel {{ background: #232323; border: 1px solid #333; border-radius: 12px; padding: 0.7rem 1rem; }}
  .context-panel summary {{ cursor: pointer; color: #ccc; font-size: 0.88rem; font-weight: 600; }}
  .ctx-grid {{ display: grid; grid-template-columns: 180px 1fr; gap: 0.3rem 0.75rem; margin-top: 0.6rem; font-size: 0.78rem; }}
  .ctx-key {{ color: #8a8a8a; font-family: ui-monospace, 'SF Mono', monospace; }}
  .ctx-val {{ color: #ddd; word-break: break-word; white-space: pre-wrap; }}
  .decision-list {{ margin-top: 0.5rem; font-size: 0.78rem; }}
  .decision-row {{ padding: 0.3rem 0; border-bottom: 1px solid #2a2a2a; color: #ccc; }}
  .decision-ts {{ color: #777; font-family: ui-monospace, 'SF Mono', monospace; font-size: 0.72rem; margin-right: 0.5rem; }}
  .wf-tag {{ color: #6ba3d6; font-size: 0.7rem; font-family: ui-monospace, 'SF Mono', monospace; }}
  .sev-badge {{ color: #e8a040; font-size: 0.7rem; font-weight: 600; }}
  .lightbox {{ position: fixed; inset: 0; background: rgba(7,7,7,0.82); display: none; align-items: center; justify-content: center; padding: 2rem; z-index: 9999; }}
  .lightbox.open {{ display: flex; }}
  .lightbox-panel {{ position: relative; width: min(92vw, 1600px); max-height: 92vh; background: #111; border-radius: 18px; box-shadow: 0 32px 80px rgba(0,0,0,0.4); overflow: hidden; }}
  .lightbox-topbar {{ display: flex; align-items: center; justify-content: space-between; gap: 1rem; padding: 0.9rem 1rem; background: rgba(255,255,255,0.03); border-bottom: 1px solid rgba(255,255,255,0.08); }}
  .lightbox-title {{ font-size: 0.95rem; color: #ddd; }}
  .lightbox-actions {{ display: flex; gap: 0.75rem; align-items: center; }}
  .lightbox-close {{ appearance: none; border: 0; background: rgba(255,255,255,0.08); color: #fff; padding: 0.55rem 0.8rem; border-radius: 999px; cursor: pointer; font: inherit; }}
  .lightbox-media {{ display: grid; place-items: center; padding: 1rem; max-height: calc(92vh - 72px); overflow: auto; }}
  .lightbox-media img, .lightbox-media video {{ max-width: 100%; max-height: calc(92vh - 120px); width: auto; height: auto; display: block; background: #111; }}
</style></head>
<body>
<h1>Brand Material Comparison \u2014 {len(vids)} versions</h1>
<div class="subhead">Viewing {html_escape(filter_label)}. Most recent versions appear first. The latest overall generation is highlighted directly on the card grid. Click any preview to expand it. Use the copy button to grab a ready-to-paste regeneration prompt for your agent.</div>
<div class="toolbar">
  <div class="summary">History: {total_versions} total \u00b7 {scored_versions} scored \u00b7 {favorite_versions} favorites \u00b7 latest overall: {html_escape(latest_overall_version or 'n/a')} \u00b7 latest in view: {html_escape(latest_selected_version or 'n/a')}</div>
  <input id="filter-search" type="search" placeholder="Filter by version, material, notes, model..." />
  <select id="filter-status">
    <option value="">All statuses</option>
    <option value="favorite">Favorites</option>
    <option value="rejected">Rejected</option>
    <option value="unscored">Unscored</option>
  </select>
</div>
{context_html}
<div class="grid">{"".join(cards_html)}</div>
<div class="lightbox" id="lightbox" aria-hidden="true">
  <div class="lightbox-panel" role="dialog" aria-modal="true" aria-label="Expanded media preview">
    <div class="lightbox-topbar">
      <div class="lightbox-title" id="lightbox-title">Preview</div>
      <div class="lightbox-actions">
        <button class="lightbox-close" id="lightbox-close" type="button">Close</button>
      </div>
    </div>
    <div class="lightbox-media" id="lightbox-media"></div>
  </div>
</div>
<script>
  const lightbox = document.getElementById('lightbox');
  const lightboxMedia = document.getElementById('lightbox-media');
  const lightboxTitle = document.getElementById('lightbox-title');
  const lightboxClose = document.getElementById('lightbox-close');

  function closeLightbox() {{
    lightbox.classList.remove('open');
    lightbox.setAttribute('aria-hidden', 'true');
    document.body.classList.remove('modal-open');
    lightboxMedia.innerHTML = '';
  }}

  function openLightboxFrom(mediaEl) {{
    const version = mediaEl.dataset.version || 'Preview';
    const img = mediaEl.querySelector('img');
    const video = mediaEl.querySelector('video');
    lightboxMedia.innerHTML = '';
    lightboxTitle.textContent = version;
    if (img) {{
      const full = document.createElement('img');
      full.src = img.src;
      full.alt = img.alt || version;
      lightboxMedia.appendChild(full);
    }} else if (video) {{
      const full = document.createElement('video');
      full.src = video.currentSrc || (video.querySelector('source') && video.querySelector('source').src) || '';
      full.controls = true;
      full.autoplay = true;
      full.loop = true;
      full.muted = true;
      full.playsInline = true;
      lightboxMedia.appendChild(full);
    }} else {{
      return;
    }}
    lightbox.classList.add('open');
    lightbox.setAttribute('aria-hidden', 'false');
    document.body.classList.add('modal-open');
  }}

  document.querySelectorAll('.media.expandable').forEach((mediaEl) => {{
    mediaEl.addEventListener('click', () => openLightboxFrom(mediaEl));
    mediaEl.addEventListener('keydown', (event) => {{
      if (event.key === 'Enter' || event.key === ' ') {{
        event.preventDefault();
        openLightboxFrom(mediaEl);
      }}
    }});
  }});

  lightboxClose.addEventListener('click', closeLightbox);
  lightbox.addEventListener('click', (event) => {{
    if (event.target === lightbox) closeLightbox();
  }});
  document.addEventListener('keydown', (event) => {{
    if (event.key === 'Escape') closeLightbox();
  }});

  document.querySelectorAll('.copy-btn').forEach((btn) => {{
    btn.addEventListener('click', async () => {{
      const text = btn.dataset.copy || '';
      try {{
        await navigator.clipboard.writeText(text);
        const previous = btn.textContent;
        btn.textContent = 'Copied';
        setTimeout(() => btn.textContent = previous, 1200);
      }} catch (err) {{
        console.error(err);
      }}
    }});
  }});

  const searchInput = document.getElementById('filter-search');
  const statusSelect = document.getElementById('filter-status');
  const cards = Array.from(document.querySelectorAll('.card'));
  function applyFilters() {{
    const query = (searchInput.value || '').toLowerCase().trim();
    const status = statusSelect.value;
    cards.forEach((card) => {{
      const haystack = card.textContent.toLowerCase();
      const statusMatch = !status || (card.dataset.status || '') === status;
      const queryMatch = !query || haystack.includes(query);
      card.classList.toggle('hidden', !(statusMatch && queryMatch));
    }});
  }}
  searchInput.addEventListener('input', applyFilters);
  statusSelect.addEventListener('change', applyFilters);
</script>
</body></html>'''
    out = output or (brand_dir / "compare.html")
    out.write_text(html)
    if open_browser and sys.platform == "darwin":
        subprocess.run(["open", str(out)], check=False)
    return out
