"""Card rendering engine — dataclasses, HTML/CSS composition, PNG render.

Depends on: ``runtime``, ``runtime_io``, ``runtime_refs``, ``surface_strategy``
and the leaf ``card_text`` module.
"""
from __future__ import annotations

import fcntl
import html
import json
import re
import shutil
import subprocess
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote

from .runtime import get_manifest_path, load_manifest, next_version_num, save_manifest
from .surface_strategy import load_composition_profile, load_surface_strategy_definition
from .card_text import (
    _detail_card_budget,
    _prompt_detail_items,
    _truncate_multiline_copy,
)


ALLOWED_HTML_MATERIALS = {"social", "x-feed", "announcement-card"}
DEFAULT_HTML_MODEL = "html:chromium"
DEFAULT_DESIGN_VARIANCE = 5

_PROMPT_FRAGMENTS_PATH = Path(__file__).resolve().parent.parent / "data" / "prompt_fragments.json"


# ---------------------------------------------------------------------------
# Taste directives
# ---------------------------------------------------------------------------

def _load_taste_directives() -> dict[str, Any]:
    try:
        data = json.loads(_PROMPT_FRAGMENTS_PATH.read_text())
        return data.get("html_taste_directives") or {}
    except (OSError, json.JSONDecodeError):
        return {}


def _variance_band(design_variance: int) -> str:
    if design_variance <= 3:
        return "low"
    if design_variance <= 7:
        return "mid"
    return "high"


def taste_design_directives(design_variance: int = DEFAULT_DESIGN_VARIANCE) -> str:
    taste = _load_taste_directives()
    if not taste:
        return ""
    band = _variance_band(design_variance)
    variance_text = (taste.get("variance_guidance") or {}).get(band, "")
    anti = taste.get("anti_patterns") or []
    anti_text = ", ".join(anti[:6]) if anti else ""
    parts = [
        f"Design variance: {design_variance}/10 ({band}).",
    ]
    if variance_text:
        parts.append(f"Layout direction: {variance_text}")
    if taste.get("typography"):
        parts.append(f"Typography: {taste['typography']}")
    if taste.get("color"):
        parts.append(f"Color: {taste['color']}")
    if taste.get("surfaces"):
        parts.append(f"Card surfaces: {taste['surfaces']}")
    if taste.get("border_radius_hierarchy"):
        parts.append(f"Border-radius: {taste['border_radius_hierarchy']}")
    if taste.get("shadow_system"):
        parts.append(f"Shadows: {taste['shadow_system']}")
    if taste.get("type_scale"):
        parts.append(f"Type scale: {taste['type_scale']}")
    if taste.get("spacing"):
        parts.append(f"Spacing: {taste['spacing']}")
    if anti_text:
        parts.append(f"Banned patterns: {anti_text}.")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Manifest helpers
# ---------------------------------------------------------------------------

@contextmanager
def _manifest_write_lock(brand_dir: Path):
    lock_path = Path(str(get_manifest_path(brand_dir)) + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _reserve_manifest_version(brand_dir: Path, *, material_type: str, workflow_id: str, tag: str) -> str:
    with _manifest_write_lock(brand_dir):
        manifest = load_manifest(brand_dir)
        vnum = next_version_num(manifest, brand_dir)
        vid = f"v{vnum:03d}"
        manifest.setdefault("versions", {})
        manifest["versions"].setdefault(
            vid,
            {
                "status": "reserved",
                "material_type": material_type,
                "tag": tag,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "workflow_id": workflow_id,
            },
        )
        save_manifest(manifest, brand_dir)
        return vid


def _update_manifest_version(brand_dir: Path, version_id: str, updates: dict) -> tuple[dict, dict]:
    with _manifest_write_lock(brand_dir):
        manifest = load_manifest(brand_dir)
        manifest.setdefault("versions", {})
        current = dict((manifest.get("versions") or {}).get(version_id) or {})
        current.update(updates or {})
        manifest["versions"][version_id] = current
        save_manifest(manifest, brand_dir)
        return manifest, current


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class ShareCardPayload:
    material_type: str
    surface: str
    entity_type: str
    source_url: str
    source_domain: str
    page_title: str
    headline: str
    subhead: str
    cta: str
    logo_path: str
    proof_title: str
    proof_meta: list[str]
    proof_excerpt: str
    proof_row: str
    proof_crop_path: str
    proof_weight_guidance: str
    support_crop_path: str
    detail_label: str = ""
    detail_blocks: list[dict[str, Any]] | None = None
    brand_name: str = ""
    render_model: str = DEFAULT_HTML_MODEL
    selected_surface_strategy: str = ""
    selected_surface_strategy_label: str = ""
    selected_surface_strategy_summary: str = ""
    selected_surface_strategy_layout_family: str = ""
    surface_strategy_reason: str = ""
    design_variance: int = DEFAULT_DESIGN_VARIANCE
    composition_mode: str = ""
    composition_summary: str = ""
    composition_asset_slots: list[str] | None = None
    skip_proof: bool = False
    dark_mode: bool = False

    layout_spec: "LayoutSpec | None" = None


    def to_dict(self) -> dict[str, Any]:
        return {
            "material_type": self.material_type,
            "surface": self.surface,
            "entity_type": self.entity_type,
            "source_url": self.source_url,
            "source_domain": self.source_domain,
            "page_title": self.page_title,
            "headline": self.headline,
            "subhead": self.subhead,
            "cta": self.cta,
            "detail_label": self.detail_label,
            "brand_name": self.brand_name,
            "logo_path": self.logo_path,
            "proof_title": self.proof_title,
            "proof_meta": list(self.proof_meta),
            "proof_excerpt": self.proof_excerpt,
            "proof_row": self.proof_row,
            "proof_crop_path": self.proof_crop_path,
            "proof_weight_guidance": self.proof_weight_guidance,
            "support_crop_path": self.support_crop_path,
            "render_model": self.render_model,
            "detail_blocks": list(self.detail_blocks or []),
            "selected_surface_strategy": self.selected_surface_strategy,
            "selected_surface_strategy_label": self.selected_surface_strategy_label,
            "selected_surface_strategy_summary": self.selected_surface_strategy_summary,
            "selected_surface_strategy_layout_family": self.selected_surface_strategy_layout_family,
            "surface_strategy_reason": self.surface_strategy_reason,
            "design_variance": self.design_variance,
            "composition_mode": self.composition_mode,
            "composition_summary": self.composition_summary,
            "composition_asset_slots": list(self.composition_asset_slots or []),
            "skip_proof": self.skip_proof,
            "dark_mode": self.dark_mode,
            "layout_spec": self.layout_spec.to_dict() if self.layout_spec else None,
        }


@dataclass
class LayoutSpec:
    columns: int = 1
    alignment: str = "left"
    proof_position: str = "below"
    accent_style: str = "none"
    headline_size: str = "lg"
    padding: str = "generous"
    proof_style: str = "card"
    canvas_preset: str = "auto"

    def to_dict(self) -> dict[str, Any]:
        return {
            "columns": self.columns,
            "alignment": self.alignment,
            "proof_position": self.proof_position,
            "accent_style": self.accent_style,
            "headline_size": self.headline_size,
            "padding": self.padding,
            "proof_style": self.proof_style,
            "canvas_preset": self.canvas_preset,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "LayoutSpec":
        if not data:
            return cls()
        return cls(
            columns=int(data.get("columns") or 1),
            alignment=str(data.get("alignment") or "left"),
            proof_position=str(data.get("proof_position") or "below"),
            accent_style=str(data.get("accent_style") or "none"),
            headline_size=str(data.get("headline_size") or "lg"),
            padding=str(data.get("padding") or "generous"),
            proof_style=str(data.get("proof_style") or "card"),
            canvas_preset=str(data.get("canvas_preset") or "auto"),
        )


def default_layout_spec(
    material_type: str,
    design_variance: int = DEFAULT_DESIGN_VARIANCE,
    *,
    entity_type: str = "",
    selected_strategy: str = "",
) -> LayoutSpec:
    if material_type == "social":
        return LayoutSpec(columns=2, alignment="left", proof_position="right", accent_style="none", headline_size="xl", padding="generous", canvas_preset="square")
    if material_type == "x-feed":
        return LayoutSpec(columns=2, alignment="left", proof_position="right", accent_style="none", headline_size="lg", padding="normal", canvas_preset="wide")
    if material_type == "announcement-card" and entity_type in {"prompt", "skill", "library"}:
        return LayoutSpec(
            columns=2,
            alignment="left",
            proof_position="right",
            accent_style="none",
            headline_size="lg",
            padding="normal",
            proof_style="document",
            canvas_preset="document",
        )
    # announcement-card and everything else: single column
    if design_variance >= 7:
        return LayoutSpec(columns=1, alignment="left", proof_position="below", accent_style="left-strip", headline_size="lg", padding="generous", canvas_preset="portrait")
    return LayoutSpec(columns=1, alignment="center", proof_position="below", accent_style="none", headline_size="lg", padding="generous", canvas_preset="portrait")


# ---------------------------------------------------------------------------
# HTML detail renderers
# ---------------------------------------------------------------------------

def _render_prompt_detail_html(text: str, *, variant: str = "stack") -> str:
    lead, items = _prompt_detail_items(text, max_items=10 if variant in {"matrix", "sheet"} else 8)
    if not lead:
        return ""
    lead_html = f"<p class=\"prompt-detail-lead\">{html.escape(lead)}</p>"
    rows: list[str] = []
    for kind, primary, secondary in items:
        if kind == "section":
            rows.append(f"<div class=\"prompt-detail-section\">{html.escape(primary)}</div>")
            continue
        if kind in {"kv", "pair"}:
            rows.append(
                "<article class=\"prompt-detail-tile\">"
                f"<div class=\"prompt-detail-kicker\">{html.escape(primary)}</div>"
                f"<div class=\"prompt-detail-value\">{html.escape(secondary)}</div>"
                "</article>"
            )
            continue
        rows.append(f"<div class=\"prompt-detail-note\">{html.escape(primary)}</div>")
    if variant == "matrix":
        list_class = "prompt-detail-matrix"
    elif variant == "sheet":
        list_class = "prompt-detail-sheet"
    else:
        list_class = "prompt-detail-list"
    return (
        f"<div class=\"prompt-detail-stack\">"
        f"{lead_html}"
        f"<div class=\"{list_class}\">{''.join(rows)}</div>"
        f"</div>"
    )


def _render_detail_blocks_html(blocks: list[dict[str, Any]], *, variant: str = "matrix") -> str:
    normalized: list[dict[str, str]] = []
    for block in blocks or []:
        if not isinstance(block, dict):
            continue
        label = str(block.get("label") or "").strip()
        value = str(block.get("value") or "").strip()
        body = str(block.get("body") or "").strip()
        if not any((label, value, body)):
            continue
        normalized.append({"label": label, "value": value, "body": body})
    if not normalized:
        return ""
    if variant in {"sheet", "stack"}:
        grid_class = "detail-block-grid detail-block-grid-sheet"
    elif variant == "matrix":
        grid_class = "detail-block-grid detail-block-grid-matrix"
    else:
        grid_class = "detail-block-grid"
    items: list[str] = []
    for block in normalized:
        label = html.escape(block["label"])
        value = html.escape(block["value"])
        body = html.escape(block["body"])
        value_html = f'<div class="detail-block-value">{value}</div>' if value else ""
        body_html = f'<div class="detail-block-body">{body}</div>' if body else ""
        items.append(
            '<article class="detail-block">'
            f'<div class="detail-block-label">{label}</div>'
            f'{value_html}{body_html}'
            '</article>'
        )
    return f'<div class="{grid_class}">{"".join(items)}</div>'


def _render_entity_detail_html(card: ShareCardPayload, *, variant: str = "matrix", fallback_text: str = "") -> str:
    if card.detail_blocks:
        return _render_detail_blocks_html(card.detail_blocks, variant=variant)
    return _render_prompt_detail_html(fallback_text, variant=variant)


# ---------------------------------------------------------------------------
# Label / entity helpers
# ---------------------------------------------------------------------------

def _surface_label(material_type: str, *, entity_type: str = "", layout_spec: LayoutSpec | None = None) -> str:
    if material_type == "announcement-card" and entity_type in {"prompt", "skill", "library"}:
        preset = str((layout_spec.canvas_preset if layout_spec else "") or "").strip().lower()
        if preset == "document":
            return {
                "prompt": "prompt artifact share card",
                "skill": "skill artifact share card",
                "library": "library artifact share card",
            }.get(entity_type, "artifact share card")
    return {
        "social": "social share card",
        "x-feed": "wide share card",
        "announcement-card": "portrait announcement card",
    }.get(material_type, material_type.replace("-", " "))


def _entity_proof_title(entity_type: str) -> str:
    return {
        "prompt": "Prompt Coverage",
        "skill": "Skill Coverage",
        "library": "Library Snapshot",
        "proposal": "Proposal Snapshot",
        "community": "Community Snapshot",
        "dao": "DAO Snapshot",
        "update": "Update Snapshot",
    }.get(entity_type, "Artifact Snapshot")


def _entity_proof_label(entity_type: str) -> str:
    return {
        "prompt": "Prompt details",
        "skill": "Skill detail",
        "library": "Library detail",
        "proposal": "Proposal detail",
        "community": "Community",
        "dao": "DAO detail",
        "update": "Update",
    }.get(entity_type, "Detail")


def _qr_code_url(source_url: str, *, size: int = 132) -> str:
    data = quote(source_url, safe="")
    return (
        "https://api.qrserver.com/v1/create-qr-code/"
        f"?data={data}&size={size}x{size}&format=png&margin=0&qzone=1&charset-source=UTF-8"
        "&color=42-35-26&bgcolor=255-255-255"
    )


def _headline_font_size(text: str, *, base: int = 82) -> int:
    """Scale headline font size down for longer text to prevent ugly wrapping."""
    length = len(text)
    if length <= 18:
        return base
    if length <= 32:
        return max(base - 8, 56)
    if length <= 48:
        return max(base - 18, 56)
    return max(base - 26, 52)


def _escape_list(items: list[str]) -> str:
    return "".join(f"<span class=\"meta-pill\">{html.escape(item)}</span>" for item in items if item)


_DIV_TOKEN_RE = re.compile(r"<div\b|</div>")


def _find_matching_div_end(html_text: str, start: int) -> int:
    depth = 0
    for match in _DIV_TOKEN_RE.finditer(html_text, start):
        token = match.group(0)
        if token.startswith("</"):
            depth -= 1
            if depth == 0:
                return match.end()
            continue
        depth += 1
    return -1


def _strip_proof_blocks(html_text: str) -> str:
    marker = '<div class="proof"'
    parts: list[str] = []
    cursor = 0
    while True:
        start = html_text.find(marker, cursor)
        if start == -1:
            parts.append(html_text[cursor:])
            return "".join(parts)
        parts.append(html_text[cursor:start])
        end = _find_matching_div_end(html_text, start)
        if end == -1:
            parts.append(html_text[start:])
            return "".join(parts)
        cursor = end


def _apply_dark_mode_overrides(html_text: str) -> str:
    replacements = {
        ":root { --rust:#c67b5c; --ink:#2a231a; --charcoal:#2b2d2f; --cream:#f4ebd9; --sage:#9caf99; --sand:#eadbcc; --line:rgba(42,35,26,.10); }": ":root { --rust:#c67b5c; --ink:#f4ebd9; --charcoal:#2b2d2f; --cream:#1a1a1e; --sage:#9caf99; --sand:#eadbcc; --line:rgba(244,235,217,.10); }",
        ".subhead { color:rgba(42,35,26,.68); line-height:1.55; font-weight:500; }": ".subhead { color:rgba(244,235,217,.68); line-height:1.55; font-weight:500; }",
        ".proof { background:rgba(255,255,255,.88); border:1px solid rgba(198,123,92,.14); border-radius:22px; box-shadow:0 20px 48px rgba(42,35,26,.10), 0 2px 8px rgba(42,35,26,.06), inset 0 1px 1px rgba(255,255,255,.22); padding:24px; position:relative; }": ".proof { background:rgba(255,255,255,.06); border:1px solid rgba(244,235,217,.10); border-radius:22px; box-shadow:0 20px 48px rgba(42,35,26,.10), 0 2px 8px rgba(42,35,26,.06), inset 0 1px 1px rgba(255,255,255,.22); padding:24px; position:relative; }",
        ".meta-pill { display:inline-flex; align-items:center; padding:8px 10px; border-radius:999px; background:rgba(42,35,26,.05); color:rgba(42,35,26,.65); font-size:12px; font-weight:600; }": ".meta-pill { display:inline-flex; align-items:center; padding:8px 10px; border-radius:999px; background:rgba(244,235,217,.08); color:rgba(244,235,217,.52); font-size:12px; font-weight:600; }",
    }
    for old, new in replacements.items():
        html_text = html_text.replace(old, new)
    return html_text


def _finalize_share_card_html(html_text: str, card: ShareCardPayload) -> str:
    if card.skip_proof:
        return _strip_proof_blocks(html_text)
    return html_text


# ---------------------------------------------------------------------------
# Asset management
# ---------------------------------------------------------------------------

def _write_generated_svg(path: Path, svg_text: str) -> str:
    path.write_text(svg_text)
    return path.name


def _generate_composition_assets(card: ShareCardPayload, assets_dir: Path) -> dict[str, str]:
    mode = str(card.composition_mode or "editorial_sheet")
    generated: dict[str, str] = {}
    if "brand_motif" in (card.composition_asset_slots or []):
        motif_svg = f"""<svg width="240" height="240" viewBox="0 0 240 240" fill="none" xmlns="http://www.w3.org/2000/svg">
  <rect width="240" height="240" rx="36" fill="#F4EBD9"/>
  <path d="M62 62H178" stroke="#C67B5C" stroke-width="8" stroke-linecap="round" opacity=".55"/>
  <path d="M86 62V178" stroke="#C67B5C" stroke-width="10" stroke-linecap="round" opacity=".48"/>
  <path d="M120 62V178" stroke="#C67B5C" stroke-width="10" stroke-linecap="round" opacity=".48"/>
  <path d="M154 62V178" stroke="#C67B5C" stroke-width="10" stroke-linecap="round" opacity=".48"/>
  <path d="M74 98H166" stroke="#2A231A" stroke-width="4" stroke-linecap="round" opacity=".18"/>
</svg>"""
        generated["brand_motif"] = _write_generated_svg(assets_dir / f"{mode}-brand-motif.svg", motif_svg)
    if "accent_rule" in (card.composition_asset_slots or []):
        accent_svg = f"""<svg width="220" height="120" viewBox="0 0 220 120" fill="none" xmlns="http://www.w3.org/2000/svg">
  <path d="M22 20H198V98" stroke="#C67B5C" stroke-width="3" opacity=".48"/>
  <circle cx="32" cy="20" r="4" fill="#C67B5C" opacity=".72"/>
</svg>"""
        generated["accent_rule"] = _write_generated_svg(assets_dir / f"{mode}-accent-rule.svg", accent_svg)
    return generated


def _copy_asset(src: str | Path | None, dest_dir: Path, *, fallback_name: str) -> str:
    raw = str(src or "").strip()
    if not raw:
        return ""
    path = Path(raw).expanduser()
    if not path.exists():
        return ""
    dest = dest_dir / (path.name or fallback_name)
    shutil.copy2(path, dest)
    return dest.name


# ---------------------------------------------------------------------------
# Surface sizing
# ---------------------------------------------------------------------------

def _surface_size(material_type: str, *, layout_spec: LayoutSpec | None = None, entity_type: str = "") -> tuple[int, int]:
    preset = str((layout_spec.canvas_preset if layout_spec else "") or "").strip().lower()
    if preset == "document":
        return (1600, 1000)
    if preset == "wide":
        return (1600, 900)
    if preset == "square":
        return (1200, 1200)
    if preset == "portrait":
        return (1200, 1500)
    if material_type == "announcement-card" and entity_type == "prompt":
        return (1600, 1000)
    return {
        "social": (1200, 1200),
        "x-feed": (1600, 900),
        "announcement-card": (1200, 1500),
    }.get(material_type, (1200, 1200))


# ---------------------------------------------------------------------------
# compose_share_card_html  (the big template function)
# ---------------------------------------------------------------------------

def compose_share_card_html(card: ShareCardPayload, *, material_type: str, asset_names: dict[str, str], assets_dir: str = "") -> str:
    logo = asset_names.get("logo", "")
    proof_crop = asset_names.get("proof_crop", "")
    brand_motif = asset_names.get("brand_motif", "")
    accent_rule = asset_names.get("accent_rule", "")
    headline = html.escape(card.headline)
    subhead = html.escape(card.subhead)
    cta = html.escape(card.cta)
    raw_proof_title = "" if card.skip_proof else card.proof_title
    raw_proof_excerpt = "" if card.skip_proof else card.proof_excerpt
    raw_proof_row = "" if card.skip_proof else card.proof_row
    proof_title = html.escape(raw_proof_title)
    proof_excerpt = html.escape(raw_proof_excerpt)
    proof_row = html.escape(raw_proof_row)
    page_title = html.escape(card.page_title)
    source_domain = html.escape(card.source_domain)
    source_url = html.escape(card.source_url)
    entity_type = html.escape(card.entity_type)
    proof_label = "" if card.skip_proof else html.escape(_entity_proof_label(card.entity_type))
    if material_type == "announcement-card" and card.entity_type in {"prompt", "skill", "library", "profile", "community", "dao"}:
        proof_label = ""
    meta_html = "" if card.skip_proof else _escape_list(card.proof_meta)
    qr_url = html.escape(_qr_code_url(card.source_url))
    use_qr = card.entity_type in {"prompt", "skill", "library"}
    qr_html = (
        f'<div class="qr-wrap"><img src="{qr_url}" alt="QR code linking to source" class="qr-code" />'
        f'<div class="qr-caption">{cta}</div></div>'
        if use_qr and card.source_url
        else ""
    )
    qr_doc_html = (
        f'''<div class="qr-inline">
  <img src="{qr_url}" alt="QR code linking to source" class="qr-inline-code" />
  <div class="qr-inline-copy">
    <div class="qr-inline-label">{cta}</div>
    <a class="source-link" href="{source_url}">{source_domain} →</a>
  </div>
</div>'''
        if use_qr and card.source_url
        else (f'<a class="cta" href="{source_url}">{cta}</a>' if source_url else "")
    )
    qr_doc_large_html = (
        f'''<div style="display:flex;flex-direction:column;align-items:flex-end;gap:12px;">
  <img src="{qr_url}" alt="QR code linking to source" class="qr-inline-code" style="width:108px;height:108px;border-radius:18px;padding:8px;" />
  <div class="qr-inline-label" style="font-size:11px;text-align:right;">{cta}</div>
</div>'''
        if use_qr and card.source_url
        else qr_doc_html
    )
    strategy_note = html.escape(card.selected_surface_strategy_summary)
    # Use absolute paths so headless Chrome resolves images correctly
    assets_base = assets_dir.rstrip("/") + "/" if assets_dir else "assets/"
    proof_image_html = (
        f'<img src="{assets_base}{proof_crop}" alt="" class="proof-crop" />'
        if proof_crop and not use_qr and not card.skip_proof
        else ""
    )
    composition_support_html = ""
    if brand_motif:
        composition_support_html += f'<img src="{assets_base}{brand_motif}" alt="" style="position:absolute;right:48px;bottom:48px;width:132px;height:132px;opacity:.26;pointer-events:none;" />'
    if accent_rule:
        composition_support_html += f'<img src="{assets_base}{accent_rule}" alt="" style="position:absolute;right:112px;top:72px;width:136px;opacity:.34;pointer-events:none;" />'
    # Use brand name from profile for the badge label, not the scraped page
    # title. The page title may be a tagline ("Govern Your Autonomy") rather
    # than the brand name ("Sage").
    _brand_name = html.escape(str(card.brand_name).strip()) if hasattr(card, "brand_name") and card.brand_name else ""
    brand_label = _brand_name or html.escape((source_domain or "Brand").split(".")[0].capitalize()[:24] or "Brand")
    logo_html = f'<img src="{assets_base}{logo}" alt="{brand_label}" class="logo-img" />' if logo else '<div class="logo-fallback">B</div>'
    plain_logo_html = f'<img src="{assets_base}{logo}" alt="{brand_label}" class="logo-plain" />' if logo else ""
    common_head = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@500;600;700&family=Manrope:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<style>
:root {{ --rust:#c67b5c; --ink:#2a231a; --charcoal:#2b2d2f; --cream:#f4ebd9; --sage:#9caf99; --sand:#eadbcc; --line:rgba(42,35,26,.10); }}
* {{ box-sizing:border-box; }}
html,body {{ margin:0; padding:0; background:var(--cream); }}
body {{ font-family:Manrope,'Geist',sans-serif; text-rendering:optimizeLegibility; -webkit-font-smoothing:antialiased; -moz-osx-font-smoothing:grayscale; }}
.frame {{ position:relative; overflow:hidden; background:var(--cream); border:1px solid var(--line); }}
/* Subtle noise grain overlay for tactile depth */
.frame::after {{ content:''; position:absolute; inset:0; opacity:0.028; background-image:url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' %73titchTiles='%73titch'/%3E%3C/filter%3E%3Crect width='256' height='256' filter='url(%23n)' opacity='1'/%3E%3C/svg%3E"); background-repeat:repeat; background-size:256px 256px; pointer-events:none; z-index:99; }}
.serif {{ font-family:'Cormorant Garamond',serif; }}
.logo-tile {{ width:72px; height:72px; border-radius:20px; background:transparent; display:flex; align-items:center; justify-content:center; box-shadow:0 12px 28px rgba(42,35,26,.12); overflow:hidden; }}
.logo-img {{ width:100%; height:auto; max-height:100%; object-fit:contain; display:block; }}
.logo-plain {{ display:block; width:100%; height:100%; object-fit:cover; border-radius:24px; box-shadow:0 10px 24px rgba(42,35,26,.10); }}
.logo-fallback {{ color:white; font-weight:700; font-size:34px; }}
.badge {{ display:inline-flex; align-items:center; gap:10px; padding:12px 18px; border-radius:999px; border:1px solid rgba(198,123,92,.2); background:rgba(255,255,255,.72); color:var(--rust); font-size:14px; font-weight:700; letter-spacing:.12em; text-transform:uppercase; }}
.kicker {{ color:var(--rust); font-size:13px; font-weight:700; letter-spacing:.18em; text-transform:uppercase; }}
.headline {{ color:var(--ink); letter-spacing:-.035em; line-height:.94; margin:0; font-weight:700; }}
.subhead {{ color:rgba(42,35,26,.68); line-height:1.55; font-weight:500; }}
.cta {{ display:inline-flex; align-items:center; justify-content:center; padding:14px 22px; border-radius:999px; background:var(--rust); color:#fff; font-size:14px; font-weight:700; letter-spacing:.06em; text-transform:uppercase; text-decoration:none; box-shadow:0 4px 14px rgba(198,123,92,.22); }}
/* Double-bezel proof card: outer border ring + inner highlight for physical edge refraction */
.proof {{ background:rgba(255,255,255,.88); border:1px solid rgba(198,123,92,.14); border-radius:22px; box-shadow:0 20px 48px rgba(42,35,26,.10), 0 2px 8px rgba(42,35,26,.06), inset 0 1px 1px rgba(255,255,255,.22); padding:24px; position:relative; }}
.proof::before {{ content:''; position:absolute; inset:-1px; border-radius:23px; border:1px solid rgba(42,35,26,.04); pointer-events:none; }}
.proof-label {{ color:var(--rust); font-size:12px; font-weight:700; letter-spacing:.16em; text-transform:uppercase; }}
.proof-title {{ margin:12px 0 0; color:var(--ink); font-size:30px; line-height:1.02; letter-spacing:-.025em; font-weight:700; }}
.proof-meta {{ display:flex; flex-wrap:wrap; gap:8px; margin-top:14px; }}
.meta-pill {{ display:inline-flex; align-items:center; padding:8px 10px; border-radius:999px; background:rgba(42,35,26,.05); color:rgba(42,35,26,.65); font-size:12px; font-weight:600; }}
.proof-excerpt {{ margin:16px 0 0; color:rgba(42,35,26,.76); font-size:17px; line-height:1.6; max-width:65ch; white-space:pre-line; }}
.proof-row {{ margin-top:14px; padding-top:14px; border-top:1px solid rgba(42,35,26,.08); color:rgba(42,35,26,.58); font-size:13px; font-weight:600; white-space:pre-line; line-height:1.55; }}
.proof-crop {{ margin-top:18px; width:100%; height:112px; object-fit:cover; border-radius:18px; border:1px solid rgba(42,35,26,.08); display:block; }}
.prompt-detail-stack {{ display:flex; flex-direction:column; gap:18px; }}
.prompt-detail-lead {{ margin:0; color:rgba(42,35,26,.88); font-size:24px; line-height:1.34; font-weight:600; max-width:34ch; }}
.prompt-detail-list, .prompt-detail-matrix, .prompt-detail-sheet {{ display:grid; gap:14px 18px; align-items:start; }}
.prompt-detail-list {{ grid-template-columns:repeat(2,minmax(0,1fr)); }}
.prompt-detail-matrix {{ grid-template-columns:repeat(2,minmax(0,1fr)); }}
.prompt-detail-sheet {{ grid-template-columns:minmax(0,1fr); }}
.prompt-detail-tile {{ padding:15px 16px 16px; border-radius:20px; background:rgba(42,35,26,.03); border:1px solid rgba(42,35,26,.08); box-shadow:inset 0 1px 0 rgba(255,255,255,.52); min-height:100%; }}
.prompt-detail-kicker {{ color:rgba(198,123,92,.88); font-size:11px; font-weight:800; letter-spacing:.14em; text-transform:uppercase; }}
.prompt-detail-value {{ margin-top:8px; color:rgba(42,35,26,.82); font-size:16px; line-height:1.48; }}
.prompt-detail-note {{ color:rgba(42,35,26,.76); font-size:16px; line-height:1.52; padding-top:12px; border-top:1px solid rgba(42,35,26,.08); }}
.prompt-detail-section {{ grid-column:1 / -1; color:rgba(42,35,26,.52); font-size:11px; font-weight:800; letter-spacing:.16em; text-transform:uppercase; padding-top:8px; }}
.detail-block-grid {{ display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:14px 16px; align-items:start; }}
.detail-block-grid-sheet {{ grid-template-columns:repeat(2,minmax(0,1fr)); }}
.detail-block-grid-matrix {{ grid-template-columns:repeat(3,minmax(0,1fr)); }}
.detail-block {{ padding:15px 16px 16px; border-radius:20px; background:rgba(42,35,26,.03); border:1px solid rgba(42,35,26,.08); box-shadow:inset 0 1px 0 rgba(255,255,255,.52); min-height:100%; }}
.detail-block-label {{ color:rgba(198,123,92,.88); font-size:11px; font-weight:800; letter-spacing:.14em; text-transform:uppercase; }}
.detail-block-value {{ margin-top:8px; color:rgba(42,35,26,.90); font-size:34px; line-height:1; font-weight:800; letter-spacing:-.04em; }}
.detail-block-body {{ margin-top:8px; color:rgba(42,35,26,.78); font-size:15px; line-height:1.45; white-space:pre-line; }}
.domain {{ color:rgba(42,35,26,.44); font-size:13px; font-weight:700; letter-spacing:.08em; text-transform:uppercase; }}
.source-link {{ color:rgba(198,123,92,.86); font-size:14px; font-weight:600; text-decoration:none; }}
.qr-wrap {{ display:flex; flex-direction:column; align-items:center; gap:10px; }}
.qr-code {{ width:132px; height:132px; border-radius:18px; border:1px solid rgba(42,35,26,.10); background:#fff; padding:10px; display:block; }}
.qr-caption {{ color:rgba(42,35,26,.62); font-size:11px; font-weight:700; letter-spacing:.14em; text-transform:uppercase; }}
.qr-inline {{ display:flex; align-items:flex-end; gap:16px; }}
.qr-inline-code {{ width:96px; height:96px; border-radius:16px; border:1px solid rgba(42,35,26,.10); background:#fff; padding:8px; display:block; flex:none; }}
.qr-inline-copy {{ display:flex; flex-direction:column; gap:6px; align-items:flex-start; }}
.qr-inline-label {{ color:rgba(42,35,26,.62); font-size:11px; font-weight:700; letter-spacing:.14em; text-transform:uppercase; }}
.strategy-chip {{ display:inline-flex; align-items:center; padding:9px 12px; border-radius:999px; background:rgba(42,35,26,.06); color:rgba(42,35,26,.62); font-size:11px; font-weight:700; letter-spacing:.12em; text-transform:uppercase; }}
.strategy-note {{ color:rgba(42,35,26,.56); font-size:12px; line-height:1.45; max-width:28ch; text-align:right; }}
</style>
</head>
<body>'''
    if card.dark_mode:
        common_head = _apply_dark_mode_overrides(common_head)
    # --- LayoutSpec-driven rendering ---
    spec = card.layout_spec or default_layout_spec(material_type, card.design_variance)
    family = str(card.composition_mode or "").strip().lower()
    hl_base = {"xl": 88, "lg": 80, "md": 72, "sm": 64}.get(spec.headline_size, 80)
    hl_size = _headline_font_size(card.headline, base=hl_base)
    pad_h, pad_v = {"generous": (84, 84), "normal": (68, 80), "tight": (48, 56)}.get(spec.padding, (84, 84))
    text_align = "center" if spec.alignment == "center" else "left"
    headline_margin = "margin:0 auto;" if spec.alignment == "center" else ""
    subhead_margin = f"margin:22px auto 0;" if spec.alignment == "center" else "margin-top:22px;"
    accent_html = ""
    if spec.accent_style == "left-strip":
        accent_html = '<div style="position:absolute;left:0;top:0;bottom:0;width:5px;background:var(--rust);opacity:.18;"></div>'
        pad_h = max(pad_h, 96)  # extra left padding for accent strip
    elif spec.accent_style == "top-bar":
        accent_html = '<div style="position:absolute;left:0;right:0;top:0;height:5px;background:var(--rust);opacity:.18;"></div>'

    if spec.columns == 2:
        if material_type == "announcement-card" and card.entity_type in {"prompt", "skill", "library", "profile", "community", "dao"}:
            width, height = _surface_size(material_type, layout_spec=spec, entity_type=card.entity_type)
            bg_overlay = 'linear-gradient(180deg, rgba(255,255,255,.5), rgba(255,255,255,0) 34%), radial-gradient(circle at 82% 18%, rgba(198,123,92,.10), transparent 24%)'
            utility_col = "132px" if card.entity_type in {"prompt", "skill", "library"} else "124px"
            proof_min_height = "0"
            detail_lines, detail_chars = _detail_card_budget(family)
            prompt_card_text = _truncate_multiline_copy(
                "\n".join(part for part in [raw_proof_excerpt, raw_proof_row] if str(part or "").strip()),
                max_lines=detail_lines,
                max_chars=detail_chars,
            )
            detail_html_stack = _render_entity_detail_html(card, variant="stack", fallback_text=prompt_card_text)
            detail_html_matrix = _render_entity_detail_html(card, variant="matrix", fallback_text=prompt_card_text)
            detail_html_sheet = _render_entity_detail_html(card, variant="sheet", fallback_text=prompt_card_text)
            _has_blocks = bool(card.detail_blocks)
            detail_label = card.detail_label or {
                "prompt": "From the prompt",
                "skill": "From the skill",
                "library": "From the library",
                "community": "Community snapshot",
                "dao": "Community snapshot",
                "profile": "Creator profile",
            }.get(card.entity_type, "From the source")
            if family == "statement_poster":
                return _finalize_share_card_html(common_head + f'''
<div class="frame" style="width:{width}px;height:{height}px;margin:0 auto;">
  <div style="position:absolute;inset:0;background:{bg_overlay};"></div>
  {composition_support_html}
  {accent_html}
  <div style="position:absolute;left:{pad_h}px;top:{pad_v}px;right:{pad_h}px;bottom:{pad_v}px;display:grid;grid-template-columns:minmax(0,1fr) 148px;grid-template-rows:auto 1fr;gap:34px 28px;">
    <div style="display:flex;flex-direction:column;align-items:flex-start;justify-content:flex-start;max-width:920px;">
      <div style="width:112px;height:112px;display:flex;align-items:flex-start;justify-content:flex-start;margin-bottom:22px;">{plain_logo_html if logo else '<div class="logo-tile" style="width:112px;height:112px;border-radius:28px;">'+logo_html+'</div>'}</div>
      <h1 class="headline serif" style="font-size:{max(min(hl_size, 96), 80)}px;margin-top:0;max-width:880px;">{headline}</h1>
      <p class="subhead" style="font-size:22px;max-width:760px;margin-top:18px;">{subhead}</p>
    </div>
    <div style="display:flex;align-items:flex-start;justify-content:flex-end;">{qr_doc_large_html}</div>
    <div style="grid-column:1 / span 2;align-self:end;">
      <div class="proof" style="padding:28px 34px 24px;width:100%;display:grid;grid-template-columns:minmax(0,1.1fr) minmax(0,.95fr);gap:18px 28px;">
        <div style="grid-column:1 / span 2;display:flex;align-items:center;justify-content:space-between;gap:20px;">
          <div class="proof-label">{detail_label}</div>
          <div class="domain">{source_domain}</div>
        </div>
        <div>
          <p class="proof-excerpt" style="margin:0;font-size:18px;line-height:1.45;max-width:none;">{html.escape(_truncate_multiline_copy(raw_proof_excerpt, max_lines=4, max_chars=240))}</p>
        </div>
        <div>
          {detail_html_sheet}
        </div>
      </div>
    </div>
  </div>
</div>
</body></html>''', card)
            if family == "artifact_monolith":
                return _finalize_share_card_html(common_head + f'''
<div class="frame" style="width:{width}px;height:{height}px;margin:0 auto;">
  <div style="position:absolute;inset:0;background:{bg_overlay};"></div>
  {composition_support_html}
  {accent_html}
  <div style="position:absolute;left:{pad_h}px;top:{pad_v}px;right:{pad_h}px;bottom:{pad_v}px;display:grid;grid-template-columns:minmax(0,1fr) 164px;grid-template-rows:auto 1fr;gap:26px 24px;">
    <div style="display:flex;flex-direction:column;align-items:flex-start;max-width:980px;">
      <div style="width:108px;height:108px;margin-bottom:20px;">{plain_logo_html if logo else '<div class="logo-tile" style="width:108px;height:108px;border-radius:28px;">'+logo_html+'</div>'}</div>
      <h1 class="headline serif" style="font-size:{max(min(hl_size, 104), 82)}px;margin-top:0;max-width:920px;">{headline}</h1>
      <p class="subhead" style="font-size:22px;max-width:720px;margin-top:18px;">{subhead}</p>
    </div>
    <div style="display:flex;align-items:flex-start;justify-content:flex-end;">{qr_doc_large_html}</div>
    <div style="grid-column:1 / span 2;align-self:end;">
      <div class="proof" style="padding:30px 32px 26px;width:100%;display:grid;grid-template-columns:minmax(0,.7fr) minmax(0,1fr);gap:18px 24px;">
        <div style="grid-column:1 / span 2;display:flex;align-items:center;justify-content:space-between;gap:18px;">
          <div class="proof-label">{detail_label}</div>
          <div class="domain">{source_domain}</div>
        </div>
        {'<div><p class="proof-excerpt" style="margin:0;font-size:18px;line-height:1.5;max-width:none;">' + html.escape(_truncate_multiline_copy(raw_proof_excerpt, max_lines=5, max_chars=300)) + '</p></div>' if _has_blocks else ''}
        <div>
          {detail_html_matrix}
        </div>
        {'<div class="proof-row" style="grid-column:1 / span 2;">' + proof_row + '</div>' if _has_blocks and proof_row else ''}
      </div>
    </div>
  </div>
</div>
</body></html>''', card)
            if family == "split_editorial":
                return _finalize_share_card_html(common_head + f'''
<div class="frame" style="width:{width}px;height:{height}px;margin:0 auto;">
  <div style="position:absolute;inset:0;background:{bg_overlay};"></div>
  {composition_support_html}
  {accent_html}
  <div style="position:absolute;left:{pad_h}px;top:{pad_v}px;right:{pad_h}px;bottom:{pad_v}px;display:grid;grid-template-columns:minmax(0,.92fr) minmax(380px,.86fr);gap:34px;">
    <div style="display:flex;flex-direction:column;align-items:flex-start;justify-content:flex-start;">
      <div style="width:108px;height:108px;margin-bottom:22px;">{plain_logo_html if logo else '<div class="logo-tile" style="width:108px;height:108px;border-radius:26px;">'+logo_html+'</div>'}</div>
      <h1 class="headline serif" style="font-size:{max(min(hl_size, 88), 72)}px;margin-top:0;max-width:700px;">{headline}</h1>
      <p class="subhead" style="font-size:22px;max-width:620px;margin-top:18px;">{subhead}</p>
      <div style="margin-top:auto;padding-top:28px;">{qr_doc_html}</div>
    </div>
    <div style="display:flex;flex-direction:column;gap:18px;align-items:stretch;">
      <div class="proof" style="padding:30px 34px 28px;min-height:0;">
        <div class="proof-label">{detail_label}</div>
        {detail_html_stack}
        {'<div class="proof-row">' + proof_row + '</div>' if _has_blocks and proof_row else ''}
      </div>
    </div>
  </div>
</div>
</body></html>''', card)
            if family == "utility_sidebar":
                return _finalize_share_card_html(common_head + f'''
<div class="frame" style="width:{width}px;height:{height}px;margin:0 auto;">
  <div style="position:absolute;inset:0;background:{bg_overlay};"></div>
  {composition_support_html}
  {accent_html}
  <div style="position:absolute;left:{pad_h}px;top:{pad_v}px;right:{pad_h}px;bottom:{pad_v}px;display:grid;grid-template-columns:minmax(0,1fr) 196px;gap:28px;">
    <div style="display:flex;flex-direction:column;min-width:0;">
      <div style="width:104px;height:104px;margin-bottom:18px;">{plain_logo_html if logo else '<div class="logo-tile" style="width:104px;height:104px;border-radius:24px;">'+logo_html+'</div>'}</div>
      <h1 class="headline serif" style="font-size:{max(min(hl_size, 84), 68)}px;margin-top:0;max-width:820px;">{headline}</h1>
      <p class="subhead" style="font-size:22px;max-width:760px;margin-top:18px;">{subhead}</p>
      <div class="proof" style="margin-top:34px;padding:26px 28px 24px;">
        <div class="proof-label">{detail_label}</div>
        {detail_html_stack}
        {'<div class="proof-row">' + proof_row + '</div>' if _has_blocks and proof_row else ''}
      </div>
    </div>
    <div style="display:flex;flex-direction:column;align-items:flex-end;justify-content:flex-start;gap:18px;">
      {qr_doc_large_html}
    </div>
  </div>
</div>
</body></html>''', card)
            if family == "scan_card":
                return _finalize_share_card_html(common_head + f'''
<div class="frame" style="width:{width}px;height:{height}px;margin:0 auto;">
  <div style="position:absolute;inset:0;background:{bg_overlay};"></div>
  {composition_support_html}
  {accent_html}
  <div style="position:absolute;left:{pad_h}px;top:{pad_v}px;right:{pad_h}px;bottom:{pad_v}px;display:grid;grid-template-columns:minmax(0,1fr) 188px;grid-template-rows:auto 1fr;gap:30px 28px;">
    <div style="display:flex;flex-direction:column;align-items:flex-start;">
      <div style="width:96px;height:96px;margin-bottom:18px;">{plain_logo_html if logo else '<div class="logo-tile" style="width:96px;height:96px;border-radius:24px;">'+logo_html+'</div>'}</div>
      <h1 class="headline serif" style="font-size:{max(min(hl_size, 82), 68)}px;margin-top:0;max-width:780px;">{headline}</h1>
      <p class="subhead" style="font-size:21px;max-width:720px;margin-top:16px;">{subhead}</p>
    </div>
    <div style="display:flex;align-items:flex-start;justify-content:flex-end;">{qr_doc_large_html}</div>
    <div style="grid-column:1 / span 2;">
      <div class="proof" style="padding:28px 30px 24px;display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:16px 24px;">
        <div class="proof-label" style="grid-column:1 / span 2;">{detail_label}</div>
        {detail_html_matrix}
      </div>
    </div>
  </div>
</div>
</body></html>''', card)
            if family == "detail_matrix":
                _has_blocks = bool(card.detail_blocks)
                _excerpt_html = f'<p class="proof-excerpt" style="margin-top:14px;font-size:17px;line-height:1.48;max-width:70ch;">{html.escape(_truncate_multiline_copy(raw_proof_excerpt, max_lines=3, max_chars=260))}</p>' if _has_blocks else ""
                _row_html = f'<div class="proof-row">{proof_row}</div>' if _has_blocks and proof_row else ""
                return _finalize_share_card_html(common_head + f'''
<div class="frame" style="width:{width}px;height:{height}px;margin:0 auto;">
  <div style="position:absolute;inset:0;background:{bg_overlay};"></div>
  {composition_support_html}
  {accent_html}
  <div style="position:absolute;left:{pad_h}px;top:{pad_v}px;right:{pad_h}px;bottom:{pad_v}px;display:grid;grid-template-columns:minmax(0,1fr) {utility_col};grid-template-rows:1fr auto;gap:24px 20px;">
    <div style="display:flex;align-items:center;gap:20px;align-self:center;">
      <div style="width:88px;height:88px;flex:none;">{plain_logo_html if logo else '<div class="logo-tile" style="width:88px;height:88px;border-radius:22px;">'+logo_html+'</div>'}</div>
      <div style="max-width:780px;">
        <h1 class="headline serif" style="font-size:{max(min(hl_size, 78), 64)}px;margin-top:0;max-width:760px;">{headline}</h1>
        <p class="subhead" style="font-size:20px;max-width:720px;margin-top:14px;">{subhead}</p>
      </div>
    </div>
    <div style="display:flex;align-items:center;justify-content:flex-end;">{qr_doc_large_html}</div>
    <div class="proof" style="grid-column:1 / span 2;padding:28px 32px 26px;">
      <div class="proof-label">{detail_label}</div>
      {_excerpt_html}
      <div style="margin-top:18px;">{detail_html_matrix}</div>
      {_row_html}
    </div>
  </div>
</div>
</body></html>''', card)
            if family == "excerpt_sheet":
                return _finalize_share_card_html(common_head + f'''
<div class="frame" style="width:{width}px;height:{height}px;margin:0 auto;">
  <div style="position:absolute;inset:0;background:{bg_overlay};"></div>
  {composition_support_html}
  {accent_html}
  <div style="position:absolute;left:{pad_h}px;top:{pad_v}px;right:{pad_h}px;bottom:{pad_v}px;display:flex;flex-direction:column;">
    <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:20px;">
      <div style="width:96px;height:96px;">{plain_logo_html if logo else '<div class="logo-tile" style="width:96px;height:96px;border-radius:24px;">'+logo_html+'</div>'}</div>
      {qr_doc_large_html}
    </div>
    <div style="margin-top:28px;max-width:920px;">
      <h1 class="headline serif" style="font-size:{max(min(hl_size, 84), 68)}px;margin-top:0;max-width:820px;">{headline}</h1>
      <p class="subhead" style="font-size:21px;max-width:760px;margin-top:18px;">{subhead}</p>
    </div>
    <div class="proof" style="margin-top:34px;padding:30px 34px 26px;width:100%;">
      <div class="proof-label">{detail_label}</div>
      {detail_html_stack}
    </div>
  </div>
</div>
</body></html>''', card)
            if family == "reference_sheet":
                return _finalize_share_card_html(common_head + f'''
<div class="frame" style="width:{width}px;height:{height}px;margin:0 auto;">
  <div style="position:absolute;inset:0;background:{bg_overlay};"></div>
  {composition_support_html}
  {accent_html}
  <div style="position:absolute;left:{pad_h}px;top:{pad_v}px;right:{pad_h}px;bottom:{pad_v}px;display:grid;grid-template-columns:minmax(0,1fr) {utility_col};grid-template-rows:auto 1fr;gap:14px 18px;">
    <div style="display:flex;flex-direction:column;gap:18px;min-width:0;max-width:900px;">
      <div style="width:96px;height:96px;flex:none;">{plain_logo_html if logo else '<div class="logo-tile" style="width:96px;height:96px;border-radius:24px;">'+logo_html+'</div>'}</div>
      <h1 class="headline serif" style="font-size:{max(min(hl_size, 78), 64)}px;margin-top:0;max-width:860px;">{headline}</h1>
      <p class="subhead" style="font-size:20px;max-width:780px;margin-top:0;">{subhead}</p>
    </div>
    <div style="display:flex;align-items:flex-start;justify-content:flex-end;">
      {f"""<div style="display:flex;flex-direction:column;align-items:flex-end;gap:8px;margin-top:4px;">
        <img src="{qr_url}" alt="QR code linking to source" class="qr-inline-code" style="width:96px;height:96px;border-radius:16px;padding:7px;" />
        <div class="qr-inline-label" style="font-size:11px;text-align:right;">{cta}</div>
      </div>""" if use_qr and card.source_url else qr_doc_html}
    </div>
    <div style="grid-column:1 / span 2;align-self:stretch;">
      <div class="proof" style="padding:26px 30px 24px;display:flex;flex-direction:column;gap:14px;min-height:{proof_min_height};">
        <div style="display:flex;align-items:center;gap:18px;">
          <div class="proof-label">{detail_label}</div>
        </div>
        <div style="max-width:980px;">
          {detail_html_matrix}
        </div>
        {'<div class="proof-row" style="font-size:12px;margin-top:4px;">' + proof_row + '</div>' if _has_blocks and proof_row else ''}
      </div>
    </div>
  </div>
</div>
</body></html>''', card)
            return _finalize_share_card_html(common_head + f'''
<div class="frame" style="width:{width}px;height:{height}px;margin:0 auto;">
  <div style="position:absolute;inset:0;background:{bg_overlay};"></div>
  {composition_support_html}
  {accent_html}
  <div style="position:absolute;left:{pad_h}px;top:{pad_v}px;right:{pad_h}px;bottom:{pad_v}px;display:grid;grid-template-columns:minmax(0,1fr) 140px;grid-template-rows:auto auto;gap:34px 28px;">
    <div style="max-width:920px;display:flex;flex-direction:column;align-items:flex-start;justify-content:flex-start;">
      <div style="width:120px;height:120px;display:flex;align-items:flex-start;justify-content:flex-start;margin-bottom:20px;">{plain_logo_html if logo else '<div class="logo-tile" style="width:120px;height:120px;border-radius:30px;">'+logo_html+'</div>'}</div>
      <h1 class="headline serif" style="font-size:{max(min(hl_size, 82), 72)}px;margin-top:0;max-width:840px;">{headline}</h1>
      <p class="subhead" style="font-size:23px;max-width:760px;margin-top:18px;">{subhead}</p>
    </div>
    <div style="display:flex;align-items:flex-start;justify-content:flex-end;">
      {qr_doc_large_html}
    </div>
    <div style="grid-column:1 / span 2;align-self:start;">
      <div class="proof" style="padding:34px 40px 30px;min-height:0;width:100%;overflow:hidden;position:relative;">
        <div class="proof-label" style="margin-bottom:18px;">From the prompt</div>
        <div class="proof-meta">{meta_html}</div>
        {detail_html_stack}
        {proof_image_html}
      </div>
    </div>
  </div>
</div>
</body></html>''', card)

        # --- Two-column grid layout (social / x-feed) ---
        width, height = _surface_size(material_type, layout_spec=spec, entity_type=card.entity_type)
        bg_overlay = (
            'radial-gradient(circle at 78% 24%, rgba(156,175,153,.16), transparent 22%), linear-gradient(180deg, rgba(255,255,255,.45), rgba(255,255,255,0))'
            if material_type == "social"
            else 'linear-gradient(135deg, rgba(255,255,255,.52), rgba(255,255,255,0) 44%), radial-gradient(circle at 82% 20%, rgba(198,123,92,.10), transparent 22%)'
        )

        # --- Social entity cards: stacked layout with full-width proof ---
        is_entity_social = material_type == "social" and card.entity_type in {"prompt", "skill", "library"}
        if is_entity_social:
            return _finalize_share_card_html(common_head + f'''
<div class="frame" style="width:{width}px;height:{height}px;margin:0 auto;">
  <div style="position:absolute;inset:0;background:{bg_overlay};"></div>
  {accent_html}
  <div style="position:absolute;left:{pad_h}px;top:{pad_h}px;right:{pad_h}px;bottom:{pad_h}px;display:flex;flex-direction:column;">
    <div style="display:flex;align-items:center;gap:16px;">
      {f'<img src="{assets_base}{logo}" alt="{brand_label}" class="logo-plain" style="width:56px;height:56px;border-radius:16px;" />' if logo else '<div class="logo-tile" style="width:56px;height:56px;border-radius:16px;">'+logo_html+'</div>'}
      <div>
        <div class="kicker" style="font-size:12px;">{entity_type.upper()}</div>
        <div style="font-size:15px;color:rgba(42,35,26,.58);font-weight:600;">{source_domain}</div>
      </div>
    </div>
    <div style="flex:1;display:flex;flex-direction:column;justify-content:center;padding:18px 0 24px;">
      <h1 class="headline serif" style="font-size:{hl_size}px;max-width:960px;">{headline}</h1>
      <p class="subhead" style="font-size:22px;max-width:880px;margin-top:14px;">{subhead}</p>
    </div>
    <div class="proof" style="flex:none;padding:28px 32px 24px;">
      <div class="proof-label">{proof_label}</div>
      <h2 class="proof-title serif" style="font-size:28px;">{proof_title}</h2>
      <div class="proof-meta">{meta_html}</div>
      <p class="proof-excerpt" style="font-size:18px;line-height:1.52;">{proof_excerpt}</p>
      <div class="proof-row">{proof_row}</div>
      {proof_image_html}
    </div>
    <div style="display:flex;align-items:center;justify-content:space-between;gap:16px;padding-top:18px;">
      {f"""<div style="display:flex;align-items:center;gap:12px;">
        <img src="{qr_url}" alt="QR code" style="width:56px;height:56px;border-radius:12px;border:1px solid rgba(42,35,26,.10);background:#fff;padding:4px;flex:none;" />
        <div style="display:flex;flex-direction:column;gap:2px;">
          <div class="qr-inline-label">{cta}</div>
          <div class="domain" style="font-size:12px;">{source_domain}</div>
        </div>
      </div>""" if use_qr else f'<div class="domain">{source_domain}</div>'}
      <a class="source-link" href="{source_url}">{source_domain} &rarr;</a>
    </div>
  </div>
</div>
</body></html>''', card)

        # --- Standard two-column social / x-feed / announcement ---
        if material_type == "announcement-card":
            grid_cols = "0.76fr 1.24fr"
            subhead_size = 22
            proof_max_w = "100%"
            proof_title_size = "font-size:28px;"
            proof_style = "padding:34px 34px 28px;min-height:420px;"
        else:
            grid_cols = "1fr .88fr" if material_type == "social" else "1.1fr .72fr"
            subhead_size = 26 if material_type == "social" else 24
            proof_max_w = "440px" if material_type == "social" else "430px"
            proof_title_size = "font-size:34px;" if material_type == "x-feed" else ""
            proof_style = ""
        right_panel = (
            f'<div style="position:absolute;right:0;top:0;bottom:0;width:37%;background:rgba(234,219,204,.58);"></div>'
            if material_type == "x-feed" else ""
        )
        if material_type == "social":
            _entity_label = html.escape(card.entity_type.replace("_", " ").title()) if card.entity_type else ""
            _header_sub = html.escape(_brand_name) if _brand_name and _entity_label else (html.escape(_brand_name) or source_domain)
            _header_kicker = _entity_label or brand_label
            header_html = f'''<div style="display:flex;align-items:center;gap:18px;">{f'<img src="{assets_base}{logo}" alt="{brand_label}" class="logo-plain" style="width:72px;height:72px;border-radius:20px;" />' if logo else '<div class="logo-tile">'+logo_html+'</div>'}<div><div class="kicker">{_header_kicker}</div><div style="font-size:18px;color:rgba(42,35,26,.62);font-weight:600;">{_header_sub}</div></div></div>'''
        elif material_type == "announcement-card":
            header_html = "<div></div><div></div>"
        else:
            header_html = f'''<div style="display:flex;align-items:center;gap:18px;">{f'<img src="{assets_base}{logo}" alt="{brand_label}" class="logo-plain" style="width:72px;height:72px;border-radius:20px;" />' if logo else '<div class="logo-tile">'+logo_html+'</div>'}</div>
      <div class="domain">{source_domain}</div>'''
        kicker_line = f'<div class="kicker">{brand_label}</div>' if material_type == "x-feed" else ""
        hl_pad_top = "padding-top:8px;" if material_type == "social" else ""
        cta_margin = "margin-top:30px;" if material_type == "social" else ("margin-top:34px;" if material_type == "announcement-card" else "margin-top:28px;")
        if material_type == "social" and use_qr:
            utility_html = f'''<div style="margin-top:auto;padding-top:24px;display:flex;align-items:center;gap:14px;">
  <img src="{qr_url}" alt="QR code" style="width:72px;height:72px;border-radius:14px;border:1px solid rgba(42,35,26,.10);background:#fff;padding:5px;flex:none;" />
  <div style="display:flex;flex-direction:column;gap:3px;">
    <div class="qr-inline-label">{cta}</div>
    <div class="domain">{source_domain}</div>
  </div>
</div>'''
        elif material_type == "announcement-card":
            utility_html = f'''<div style="margin-top:auto;padding-top:28px;display:flex;align-items:end;justify-content:flex-start;">{qr_doc_html}</div>'''
        else:
            utility_html = f'''<div style="{cta_margin}">{qr_html or f'<a class="cta" href="{source_url}">{cta}</a>'}</div>'''
        footer_domain_size = "" if material_type == "social" else 'style="font-size:14px;"'
        footer_left = "" if material_type == "announcement-card" else f'<div class="domain" {footer_domain_size}>{source_domain}</div>'
        if material_type == "social" and use_qr:
            footer_left = ""
            footer_right = f'<a class="source-link" href="{source_url}">{source_domain} →</a>'
        elif material_type == "announcement-card":
            footer_right = ""
        else:
            footer_right = f'<a class="source-link" href="{source_url}">{source_domain} →</a>'
        floating_logo_html = (
            f'<div style="position:absolute;right:{pad_h + 18}px;bottom:{pad_v + 18}px;z-index:2;">{f'<img src="{assets_base}{logo}" alt="{brand_label}" class="logo-plain" style="width:64px;height:64px;border-radius:20px;" />' if logo else '<div class="logo-tile" style="width:64px;height:64px;">'+logo_html+'</div>'}</div>'
            if material_type == "announcement-card"
            else ""
        )
        return _finalize_share_card_html(common_head + f'''
<div class="frame" style="width:{width}px;height:{height}px;margin:0 auto;">
  <div style="position:absolute;inset:0;background:{bg_overlay};"></div>
  {right_panel}
  {accent_html}
  {floating_logo_html}
  <div style="position:absolute;left:{pad_h}px;top:{pad_v}px;right:{pad_h}px;bottom:{pad_v}px;display:grid;grid-template-columns:{grid_cols};grid-template-rows:auto 1fr auto;gap:24px;">
    <div style="grid-column:1 / span 2;display:flex;align-items:center;justify-content:space-between;gap:20px;">
      {header_html}
    </div>
    <div style="{hl_pad_top}display:flex;flex-direction:column;justify-content:center;">
      {kicker_line}
      <h1 class="headline serif" style="font-size:{hl_size}px;margin-top:14px;max-width:{int(width * 0.52)}px;">{headline}</h1>
      <p class="subhead" style="font-size:{subhead_size}px;max-width:{int(width * 0.46)}px;margin-top:18px;">{subhead}</p>
      {utility_html}
    </div>
    <div style="display:flex;align-items:center;justify-content:flex-end;">
      <div class="proof" style="width:100%;max-width:{proof_max_w};{proof_style}">
        <div class="proof-label">{proof_label}</div>
        <h2 class="proof-title serif" style="{proof_title_size}">{proof_title}</h2>
        <div class="proof-meta">{meta_html}</div>
        <p class="proof-excerpt">{proof_excerpt}</p>
        <div class="proof-row">{proof_row}</div>
        {proof_image_html}
      </div>
    </div>
    <div style="grid-column:1 / span 2;display:flex;align-items:end;justify-content:space-between;gap:24px;">
      {footer_left}
      {footer_right}
    </div>
  </div>
</div>
</body></html>''', card)

    # --- Single-column flex layout (announcement-card, qr_spotlight, compact_proof_card, etc.) ---
    width, height = _surface_size(material_type, layout_spec=spec, entity_type=card.entity_type)
    bg_gradient = "linear-gradient(180deg, rgba(255,255,255,.12) 0%, var(--cream) 100%)"
    bg_radial = (
        'radial-gradient(circle at 14% 16%, rgba(156,175,153,.16), transparent 22%), radial-gradient(circle at 84% 18%, rgba(198,123,92,.14), transparent 24%)'
        if spec.accent_style == "left-strip"
        else 'radial-gradient(circle at 20% 12%, rgba(156,175,153,.12), transparent 18%), radial-gradient(circle at 82% 18%, rgba(198,123,92,.11), transparent 22%)'
    )
    left_pad = f"{pad_h + 8}px" if spec.accent_style == "left-strip" else f"{pad_h}px"
    right_pad = f"{pad_h - 16}px" if spec.accent_style == "left-strip" else f"{pad_h}px"
    if card.selected_surface_strategy == "qr_spotlight":
        proof_width = "width:82%;max-width:860px;"
        proof_padding = "padding:28px 32px;"
        proof_margin = "margin-top:auto;margin-bottom:18px;"
    elif card.selected_surface_strategy == "compact_proof_card":
        proof_width = "width:72%;max-width:760px;"
        proof_padding = "padding:26px 30px;"
        proof_margin = "margin-top:auto;"
    else:
        proof_width = "width:100%;"
        proof_padding = "padding:28px 32px;" if spec.accent_style == "left-strip" else "padding:30px 34px;"
        proof_margin = "margin-top:40px;"
    proof_title_font = "font-size:28px;" if spec.accent_style == "left-strip" or card.selected_surface_strategy == "qr_spotlight" else ("font-size:24px;" if card.selected_surface_strategy == "compact_proof_card" else "font-size:26px;")
    if card.selected_surface_strategy == "qr_spotlight":
        right_top = f'''<div style="display:flex;flex-direction:column;align-items:flex-end;gap:14px;">
        {qr_html}
      </div>'''
    elif card.selected_surface_strategy == "compact_proof_card":
        right_top = ""
    else:
        right_top = f'''<div style="display:flex;flex-direction:column;align-items:flex-end;gap:12px;">{qr_html or f'<a class="cta" href="{source_url}">{cta}</a>' if spec.alignment == "center" else qr_html}</div>'''
    if card.selected_surface_strategy == "compact_proof_card":
        footer_html = f'''<div style="margin-top:22px;display:flex;align-items:end;justify-content:space-between;gap:24px;">
      <div class="domain">{source_domain}</div>
      <div style="display:flex;align-items:end;gap:18px;">
        {qr_html}
        <div style="display:flex;flex-direction:column;align-items:flex-end;gap:8px;">
          <a class="source-link" href="{source_url}">{source_domain} →</a>
        </div>
      </div>
    </div>'''
    else:
        footer_html = f'''<div style="margin-top:auto;padding-top:28px;display:flex;align-items:end;justify-content:space-between;gap:24px;">
      <div class="domain">{source_domain}</div>
      <div style="display:flex;flex-direction:column;align-items:flex-end;gap:8px;"><a class="source-link" href="{source_url}">{source_domain} →</a></div>
    </div>'''
    return _finalize_share_card_html(common_head + f'''
<div class="frame" style="width:{width}px;height:{height}px;margin:0 auto;background:{bg_gradient};">
  <div style="position:absolute;inset:0;background:{bg_radial};"></div>
  {composition_support_html}
  {accent_html}
  <div style="position:absolute;left:{left_pad};right:{right_pad};top:{pad_v}px;bottom:{pad_v}px;display:flex;flex-direction:column;">
    <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:20px;">
      <div style="display:flex;align-items:center;gap:18px;">{f'<img src="{assets_base}{logo}" alt="{brand_label}" class="logo-plain" style="width:72px;height:72px;border-radius:20px;" />' if logo else '<div class="logo-tile">'+logo_html+'</div>'}<div><div class="kicker" style="margin-bottom:4px;">{source_domain}</div><div class="domain">{page_title}</div></div></div>
      {right_top}
    </div>
    <div style="margin-top:56px;text-align:{text_align};">
      <h1 class="headline serif" style="font-size:{hl_size}px;max-width:960px;{headline_margin}">{headline}</h1>
      <p class="subhead" style="font-size:27px;max-width:820px;{subhead_margin}">{subhead}</p>
    </div>
    <div class="proof" style="{proof_width}border-radius:34px;{proof_padding}{proof_margin}">
      <div class="proof-label">{proof_label}</div>
      <h2 class="proof-title serif" style="{proof_title_font}">{proof_title}</h2>
      <div class="proof-meta" style="margin-top:14px;">{meta_html}</div>
      <p class="proof-excerpt" style="font-size:17px;line-height:1.58;">{proof_excerpt}</p>
      <div class="proof-row" style="font-size:13px;">{proof_row}</div>
      {proof_image_html}
    </div>
    {footer_html}
  </div>
</div>
</body></html>''', card)


# ---------------------------------------------------------------------------
# Chrome rendering + verification
# ---------------------------------------------------------------------------

def _find_chrome_binary() -> str | None:
    candidates = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        shutil.which("google-chrome"),
        shutil.which("chromium"),
        shutil.which("chromium-browser"),
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return str(candidate)
    return None


def render_html_to_png(html_path: Path, png_path: Path, *, width: int, height: int) -> bool:
    chrome = _find_chrome_binary()
    if not chrome:
        return False
    cmd = [
        chrome,
        "--headless=new",
        "--disable-gpu",
        "--hide-scrollbars",
        "--allow-file-access-from-files",
        f"--window-size={width},{height}",
        f"--screenshot={png_path}",
        html_path.resolve().as_uri(),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode == 0 and png_path.exists()


_PNG_MAGIC = b'\x89PNG\r\n\x1a\n'
_MIN_RENDER_BYTES = 8192


def _verify_render(
    png_path: Path | str,
    html_text: str,
    *,
    expected_width: int,
    expected_height: int,
    headline: str = "",
) -> dict[str, Any]:
    checks: dict[str, bool] = {}
    path = Path(png_path)
    # File exists and is large enough
    checks["file_exists"] = path.exists()
    if not checks["file_exists"]:
        return {"passed": False, "checks": checks}
    file_size = path.stat().st_size
    checks["min_size"] = file_size >= _MIN_RENDER_BYTES
    # PNG magic bytes
    raw = path.read_bytes()
    checks["png_magic"] = raw[:8] == _PNG_MAGIC
    # IHDR dimensions (bytes 16-23, big-endian uint32 width then height)
    if len(raw) >= 24:
        actual_w = int.from_bytes(raw[16:20], "big")
        actual_h = int.from_bytes(raw[20:24], "big")
        checks["dimensions"] = (actual_w == expected_width and actual_h == expected_height)
    else:
        checks["dimensions"] = False
    # Headline present in HTML source
    if headline:
        checks["headline_in_html"] = html.escape(headline) in html_text
    passed = all(checks.values())
    return {"passed": passed, "checks": checks}
