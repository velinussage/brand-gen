from __future__ import annotations

import json
import re
import time
import urllib.parse
import urllib.request
from collections import Counter
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

USER_AGENT = "brand-gen semantic extractor/1.0"
MAX_HTML_BYTES = 1_000_000
MAX_CSS_BYTES = 400_000
MAX_STYLESHEETS = 6
MAX_CSS_VARIABLES = 24
MAX_HEADINGS = 10
HEX_COLOR_RE = re.compile(r"#[0-9a-fA-F]{3,8}\b")
CSS_VAR_RE = re.compile(r"(--[A-Za-z0-9_-]+)\s*:\s*([^;}{\n]+)\s*;?")
FONT_FAMILY_RE = re.compile(r"font-family\s*:\s*([^;}{]+)", re.IGNORECASE)
BORDER_RADIUS_RE = re.compile(r"border-radius\s*:\s*([0-9.]+)\s*px", re.IGNORECASE)
TRANSITION_RE = re.compile(r"\b(?:transition|animation|transform)\b", re.IGNORECASE)
TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9_-]{2,}")

COMPONENT_HINTS = {
    "button": "Buttons and chips stay minimal and secondary to the main proof surface.",
    "cta": "Calls-to-action should be sparse, clear, and visually subordinate to the main carrier.",
    "card": "Cards should feel clean, quiet, and structurally consistent rather than decorative.",
    "hero": "Use one dominant hero carrier instead of many equal-weight focal points.",
    "nav": "Navigation chrome should stay restrained and low-noise.",
    "menu": "Menus should support hierarchy without becoming a visual motif.",
    "header": "Top framing should establish trust quickly and then get out of the way.",
    "footer": "Footers should remain simple and structurally clear.",
    "dashboard": "Dashboard/product surfaces should feel crisp, legible, and proof-oriented.",
    "chart": "Data views should emphasize readability over ornamental treatment.",
    "table": "Tabular surfaces should stay calm, aligned, and function-first.",
    "form": "Forms should use low-friction fields with clear hierarchy and minimal decoration.",
    "input": "Inputs should stay quiet and support a trust-heavy UI rhythm.",
    "gallery": "Gallery/case-study surfaces should feel curated, not crowded.",
    "project": "Project showcases should prioritize one convincing proof move per frame.",
    "case": "Case-study carriers should read as editorial proof, not mosaics.",
}


def dedupe_keep_order(items: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        value = str(item or "").strip()
        if not value or value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def compact_text(text: str, limit: int = 2400) -> str:
    text = re.sub(r"\n{3,}", "\n\n", (text or "").strip())
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "…"


def _normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", unescape(text or "")).strip()


def _tokenize_text(text: str) -> list[str]:
    return [token.lower() for token in TOKEN_RE.findall(text or "")]


def _extract_css_variables(text: str) -> list[dict[str, str]]:
    variables: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for match in CSS_VAR_RE.finditer(text or ""):
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


def _extract_font_families(text: str) -> list[str]:
    families: list[str] = []
    for match in FONT_FAMILY_RE.finditer(text or ""):
        value = match.group(1).strip()
        primary = value.split(",")[0].strip().strip("'\"")
        if primary and not primary.startswith("var("):
            families.append(primary)
    return dedupe_keep_order(families)


def _extract_heading_tokens(headings: list[str]) -> list[str]:
    tokens: list[str] = []
    for heading in headings[:MAX_HEADINGS]:
        tokens.extend(_tokenize_text(heading))
    return tokens


def _hex_to_rgb(color: str) -> tuple[int, int, int] | None:
    value = color.lstrip("#")
    if len(value) == 3:
        value = "".join(ch * 2 for ch in value)
    if len(value) != 6:
        return None
    try:
        return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)
    except ValueError:
        return None


def _brightness(color: str) -> float | None:
    rgb = _hex_to_rgb(color)
    if not rgb:
        return None
    r, g, b = rgb
    return ((0.299 * r) + (0.587 * g) + (0.114 * b)) / 255.0


def _saturation(color: str) -> float | None:
    rgb = _hex_to_rgb(color)
    if not rgb:
        return None
    r, g, b = [channel / 255.0 for channel in rgb]
    maximum = max(r, g, b)
    minimum = min(r, g, b)
    if maximum == minimum:
        return 0.0
    lightness = (maximum + minimum) / 2.0
    delta = maximum - minimum
    denominator = 1 - abs(2 * lightness - 1)
    if denominator <= 0:
        return 0.0
    return delta / denominator


def _palette_summary(colors: list[str], metadata_text: str) -> list[str]:
    lines: list[str] = []
    if colors:
        brightness_values = [value for value in (_brightness(color) for color in colors[:12]) if value is not None]
        saturation_values = [value for value in (_saturation(color) for color in colors[:12]) if value is not None]
        neutral_count = sum(1 for value in saturation_values if value <= 0.12)
        vivid_count = sum(1 for value in saturation_values if value >= 0.45)
        dark_count = sum(1 for value in brightness_values if value < 0.35)
        light_count = sum(1 for value in brightness_values if value > 0.8)
        if neutral_count >= max(2, len(saturation_values) // 2):
            lines.append("Neutral-led palette with restrained chroma.")
        if dark_count and light_count:
            lines.append("Strong dark/light contrast carries the hierarchy.")
        elif dark_count > light_count:
            lines.append("Surface treatment leans darker and trust-heavy.")
        elif light_count:
            lines.append("Surface treatment stays light, open, and calm.")
        if vivid_count <= 2 and len(colors) >= 3:
            lines.append("One restrained accent should carry emphasis rather than many competing tones.")
        elif vivid_count >= 3:
            lines.append("Accent color should stay disciplined so the system does not become noisy.")
    lower = metadata_text.lower()
    if not lines and any(term in lower for term in ("premium", "editorial", "clean", "minimal")):
        lines.append("Quiet neutrals with one controlled accent read best.")
    if not lines and any(term in lower for term in ("bold", "interactive", "growth")):
        lines.append("High-contrast accents should be concentrated into one focal move.")
    return dedupe_keep_order(lines[:3]) or ["Keep palette emphasis disciplined and subordinate to hierarchy."]


def _radius_profile(radius_values: list[float], metadata_text: str) -> str:
    if radius_values:
        average = sum(radius_values[:8]) / max(1, min(len(radius_values), 8))
        if average >= 18:
            return "rounded"
        if average >= 8:
            return "soft"
        return "sharp"
    lower = metadata_text.lower()
    if "rounded" in lower:
        return "rounded"
    if any(term in lower for term in ("clean", "minimal", "editorial")):
        return "soft"
    return "mixed"


def _safe_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n")


class _HTMLSignalParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title = ""
        self.meta_description = ""
        self.og_title = ""
        self.og_description = ""
        self.headings: list[str] = []
        self.stylesheets: list[str] = []
        self.inline_styles: list[str] = []
        self.class_tokens: Counter[str] = Counter()
        self._capture_tag: str | None = None
        self._buffer: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = {str(key).lower(): (value or "") for key, value in attrs}
        rel = attr_map.get("rel", "").lower()
        if tag == "link" and "stylesheet" in rel and attr_map.get("href"):
            self.stylesheets.append(attr_map["href"])
        if tag == "meta":
            name = attr_map.get("name", "").lower()
            prop = attr_map.get("property", "").lower()
            content = _normalize_whitespace(attr_map.get("content", ""))
            if name == "description" and content:
                self.meta_description = self.meta_description or content
            if prop == "og:title" and content:
                self.og_title = self.og_title or content
            if prop == "og:description" and content:
                self.og_description = self.og_description or content
        for key in ("class", "id"):
            for token in _tokenize_text(attr_map.get(key, "")):
                self.class_tokens[token] += 1
        if tag in {"title", "style", "h1", "h2", "h3"}:
            self._capture_tag = tag
            self._buffer = []

    def handle_data(self, data: str) -> None:
        if self._capture_tag:
            self._buffer.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag != self._capture_tag:
            return
        text = _normalize_whitespace("".join(self._buffer))
        if not text:
            self._capture_tag = None
            self._buffer = []
            return
        if tag == "title":
            self.title = self.title or text
        elif tag == "style":
            self.inline_styles.append(text)
        else:
            if len(self.headings) < MAX_HEADINGS:
                self.headings.append(text)
        self._capture_tag = None
        self._buffer = []


def _fetch_url_text(url: str, *, timeout: int, max_bytes: int, accept: str) -> tuple[str, str, str]:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": accept,
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read(max_bytes)
        final_url = getattr(response, "geturl", lambda: url)()
        headers = getattr(response, "headers", None)
        content_type = ""
        charset = None
        if headers is not None:
            content_type = headers.get("Content-Type", "") or ""
            get_charset = getattr(headers, "get_content_charset", None)
            if callable(get_charset):
                charset = get_charset()
        decoded = raw.decode(charset or "utf-8", errors="ignore")
        return decoded, str(final_url), content_type


def capture_web_snapshot(url: str, *, timeout: int = 30) -> dict[str, Any]:
    html, final_url, content_type = _fetch_url_text(
        url,
        timeout=timeout,
        max_bytes=MAX_HTML_BYTES,
        accept="text/html,application/xhtml+xml",
    )
    parser = _HTMLSignalParser()
    parser.feed(html)
    css_texts = list(parser.inline_styles)
    stylesheet_urls: list[str] = []
    warnings: list[str] = []
    for href in parser.stylesheets:
        absolute = urllib.parse.urljoin(final_url, href)
        if absolute in stylesheet_urls:
            continue
        stylesheet_urls.append(absolute)
        if len(stylesheet_urls) >= MAX_STYLESHEETS:
            break
    for stylesheet_url in stylesheet_urls:
        try:
            css_text, _, _ = _fetch_url_text(
                stylesheet_url,
                timeout=max(5, min(timeout, 20)),
                max_bytes=MAX_CSS_BYTES,
                accept="text/css,*/*;q=0.1",
            )
        except Exception as exc:  # pragma: no cover - network failures are exercised via degraded path tests
            warnings.append(f"stylesheet fetch failed for {stylesheet_url}: {exc}")
            continue
        if css_text:
            css_texts.append(css_text)
    return {
        "requested_url": url,
        "final_url": final_url,
        "content_type": content_type,
        "title": parser.title,
        "meta_description": parser.meta_description,
        "og_title": parser.og_title,
        "og_description": parser.og_description,
        "headings": parser.headings,
        "class_tokens": dict(parser.class_tokens.most_common(40)),
        "stylesheets": stylesheet_urls,
        "css_texts": css_texts,
        "warnings": warnings,
    }


def analyze_snapshot(source: dict[str, Any], snapshot: dict[str, Any], *, degraded: bool = False) -> dict[str, Any]:
    tags = [str(item).strip().lower() for item in (source.get("tags") or []) if str(item).strip()]
    metadata_parts = [
        str(source.get("name") or ""),
        str(source.get("notes") or ""),
        " ".join(tags),
        " ".join(str(item) for item in (source.get("borrow_mechanics") or [])),
        " ".join(str(item) for item in (source.get("avoid_literal") or [])),
        " ".join(str(item) for item in (source.get("best_for") or [])),
        str(snapshot.get("title") or ""),
        str(snapshot.get("meta_description") or ""),
        str(snapshot.get("og_title") or ""),
        str(snapshot.get("og_description") or ""),
        " ".join(str(item) for item in (snapshot.get("headings") or [])[:MAX_HEADINGS]),
    ]
    metadata_text = " ".join(part for part in metadata_parts if part).strip().lower()
    css_corpus = "\n\n".join(str(item) for item in (snapshot.get("css_texts") or []))
    css_variables = _extract_css_variables(css_corpus)
    colors = dedupe_keep_order([match.lower() for match in HEX_COLOR_RE.findall(css_corpus)])[:12]
    fonts = _extract_font_families(css_corpus)[:4]
    radius_values = [float(match.group(1)) for match in BORDER_RADIUS_RE.finditer(css_corpus)][:12]
    has_motion = bool(TRANSITION_RE.search(css_corpus))
    component_counter: Counter[str] = Counter()
    for token in _extract_heading_tokens(snapshot.get("headings") or []):
        component_counter[token] += 2
    for token, count in (snapshot.get("class_tokens") or {}).items():
        component_counter[str(token).lower()] += int(count)

    airy = any(term in metadata_text for term in ("premium", "editorial", "clean", "minimal", "luxury", "calm"))
    product_heavy = any(term in metadata_text for term in ("saas", "product", "mockup", "mockups", "dashboard", "platform", "app", "ui"))
    bold = any(term in metadata_text for term in ("bold", "interactive", "conversion", "growth"))
    branding = any(term in metadata_text for term in ("brand", "branding", "identity"))
    gallery_like = any(term in metadata_text for term in ("gallery", "work", "project", "projects", "case", "portfolio"))
    type_led = any(term in metadata_text for term in ("editorial", "type", "typography"))

    doctrine: list[str] = []
    constraints: list[str] = []
    anti_patterns: list[str] = []
    component_cues: list[str] = []
    layout_cues: list[str] = []
    motion_cues: list[str] = []

    if source.get("borrow_mechanics"):
        doctrine.append(
            "Borrow mechanics such as " + ", ".join(str(item) for item in list(source.get("borrow_mechanics") or [])[:4]) + "."
        )
    if product_heavy:
        doctrine.append("Lead with crisp product proof and keep decorative atmosphere secondary.")
    if airy or type_led:
        doctrine.append("Build confidence through whitespace, pacing, and calm editorial hierarchy.")
    if gallery_like:
        doctrine.append("Use one convincing showcase move per frame instead of equal-weight mosaics.")
    if bold:
        doctrine.append("Use one confident scale shift or crop move rather than many competing gestures.")
    if branding and not product_heavy:
        doctrine.append("Translate identity through repeatable carriers so the system feels deployable across surfaces.")

    if source.get("avoid_literal"):
        constraints.append(
            "Do not borrow literal elements such as " + ", ".join(str(item) for item in list(source.get("avoid_literal") or [])[:4]) + "."
        )
    risk = str(source.get("direct_generation_risk") or "").strip().lower()
    if risk in {"medium", "high"} or source.get("translation_only"):
        constraints.append("Treat this as transferable mechanics only, not direct brand truth or copy.")
    if product_heavy:
        constraints.append("Keep supporting surfaces subordinate to the main product carrier.")
    if airy or type_led:
        constraints.append("Prefer restraint over visual chatter, crowded proof rows, or ornamental chrome.")

    anti_patterns.extend(
        item
        for item in [
            "Avoid collage layouts, equal-weight panels, or too many simultaneous focal points.",
            "Avoid generic gradients, novelty effects, or decorative chrome that weakens trust.",
            "Avoid foreign logos, literal copy, or source-specific brand assets in generated work.",
        ]
        if item
    )

    for key, description in COMPONENT_HINTS.items():
        if component_counter.get(key, 0) > 0 or key in metadata_text:
            component_cues.append(description)
    if not component_cues and gallery_like:
        component_cues.append("Showcase carriers should feel curated, low-count, and hierarchically obvious.")
    if not component_cues and product_heavy:
        component_cues.append("Use one dominant application window with sparse supporting surfaces.")

    if gallery_like:
        layout_cues.append("Layouts should read as curated proof sequences with strong margins and clear grouping.")
    if product_heavy:
        layout_cues.append("Composition should anchor around one product frame or proof surface before any supporting insets.")
    if airy or type_led:
        layout_cues.append("Spacing should stay generous enough that the focal move reads in under five seconds.")
    if snapshot.get("headings"):
        layout_cues.append(
            "Observed section language suggests a structured page rhythm around "
            + ", ".join(snapshot["headings"][:3])
            + "."
        )

    if has_motion or bold:
        motion_cues.append("Motion should stay restrained and support the main reveal instead of becoming the story.")
    if has_motion:
        motion_cues.append("Use brief transitions and gentle transforms rather than long ambient animation loops.")
    if not motion_cues:
        motion_cues.append("Prefer minimal motion; let composition and hierarchy do most of the work.")

    palette_lines = _palette_summary(colors, metadata_text)
    typography_lines = []
    if fonts:
        typography_lines.append("Observed type families include " + ", ".join(fonts[:2]) + ".")
    if type_led:
        typography_lines.append("Type should carry hierarchy through scale contrast and restrained support copy.")
    elif product_heavy:
        typography_lines.append("Use a direct headline with quieter secondary copy and labels.")
    else:
        typography_lines.append("Keep typography hierarchy clear and low-noise.")

    density = "airy" if airy else "dense" if "dashboard" in metadata_text or "data" in metadata_text else "balanced"
    product_proof = "high" if product_heavy else "medium" if gallery_like else "low"
    hierarchy_mode = "editorial" if type_led else "product" if product_heavy else "system"
    accent_mode = "restrained" if len(palette_lines) and any("restrained" in line.lower() for line in palette_lines) else "expressive" if bold else "controlled"
    shape = _radius_profile(radius_values, metadata_text)

    synthetic_css_variables = [
        {"name": "--ref-visual-density", "value": density},
        {"name": "--ref-product-proof-emphasis", "value": product_proof},
        {"name": "--ref-shape-language", "value": shape},
        {"name": "--ref-hierarchy-mode", "value": hierarchy_mode},
        {"name": "--ref-accent-handling", "value": accent_mode},
    ]
    merged_css_variables = dedupe_keep_order(
        [f"{item['name']}: {item['value']};" for item in synthetic_css_variables]
        + [f"{item['name']}: {item['value']};" for item in css_variables[:MAX_CSS_VARIABLES]]
    )

    if degraded:
        constraints.append("Remote page fetch was unavailable, so this extraction relies more heavily on curated registry metadata.")

    return {
        "doctrine": dedupe_keep_order(doctrine)[:5] or ["Keep the composition clear, low-noise, and focused on one dominant proof move."],
        "constraints": dedupe_keep_order(constraints)[:5] or ["Use the source for mechanics, not literal brand assets."],
        "anti_patterns": dedupe_keep_order(anti_patterns)[:5],
        "component_cues": dedupe_keep_order(component_cues)[:6],
        "layout_cues": dedupe_keep_order(layout_cues)[:5],
        "motion_cues": dedupe_keep_order(motion_cues)[:4],
        "palette_lines": dedupe_keep_order(palette_lines)[:4],
        "typography_lines": dedupe_keep_order(typography_lines)[:4],
        "css_variables": css_variables[:MAX_CSS_VARIABLES],
        "synthetic_css_variables": synthetic_css_variables,
        "merged_css_variables": merged_css_variables,
        "colors": colors,
        "fonts": fonts,
        "radius_values": radius_values[:6],
        "summary": {
            "density": density,
            "product_proof": product_proof,
            "shape_language": shape,
            "hierarchy_mode": hierarchy_mode,
            "degraded": degraded,
        },
    }


def _render_css_block(merged_css_variables: list[str]) -> str:
    if not merged_css_variables:
        return ""
    return ":root {\n" + "\n".join(f"  {line}" for line in merged_css_variables) + "\n}"


def render_reference(source: dict[str, Any], snapshot: dict[str, Any], analysis: dict[str, Any], *, degraded: bool = False) -> str:
    lines = ["# Reference", ""]
    lines.append(f"- Source: {source.get('name') or source.get('key') or 'reference'}")
    lines.append(f"- URL: {snapshot.get('final_url') or source.get('url') or ''}")
    lines.append("- Extractor: built-in semantic extraction")
    lines.append(f"- Mode: {'metadata-plus-fetch' if not degraded else 'metadata-first fallback'}")
    if source.get("best_for"):
        lines.append("- Best for: " + ", ".join(str(item) for item in list(source.get("best_for") or [])[:4]))
    if source.get("borrow_mechanics"):
        lines.append("- Borrow mechanics: " + ", ".join(str(item) for item in list(source.get("borrow_mechanics") or [])[:4]))
    if source.get("avoid_literal"):
        lines.append("- Avoid literal: " + ", ".join(str(item) for item in list(source.get("avoid_literal") or [])[:4]))
    lines.append("")
    css_block = _render_css_block(list(analysis.get("merged_css_variables") or []))
    if css_block:
        lines.append(css_block)
        lines.append("")
    lines.append("## Color palette")
    for item in analysis.get("palette_lines") or []:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("## Typography scale")
    for item in analysis.get("typography_lines") or []:
        lines.append(f"- {item}")
    if snapshot.get("headings"):
        lines.append("")
        lines.append("## Section cues")
        for item in (snapshot.get("headings") or [])[:4]:
            lines.append(f"- {item}")
    return "\n".join(lines)


def render_principles(source: dict[str, Any], analysis: dict[str, Any]) -> str:
    lines = ["# Principles", "", "## Doctrine"]
    for item in analysis.get("doctrine") or []:
        lines.append(f"- {item}")
    lines.extend(["", "## Constraints"])
    for item in analysis.get("constraints") or []:
        lines.append(f"- {item}")
    lines.extend(["", "## Anti-patterns"])
    for item in analysis.get("anti_patterns") or []:
        lines.append(f"- {item}")
    if source.get("best_for"):
        lines.extend(["", "## Best for"])
        for item in list(source.get("best_for") or [])[:4]:
            lines.append(f"- {item}")
    return "\n".join(lines)


def render_components(analysis: dict[str, Any]) -> str:
    lines = ["# Components", "", "## Component cues"]
    for item in analysis.get("component_cues") or []:
        lines.append(f"- {item}")
    lines.extend(["", "## Layout cues"])
    for item in analysis.get("layout_cues") or []:
        lines.append(f"- {item}")
    return "\n".join(lines)


def render_style(analysis: dict[str, Any]) -> str:
    lines = ["# Style", ""]
    css_block = _render_css_block(list(analysis.get("merged_css_variables") or []))
    if css_block:
        lines.append(css_block)
        lines.append("")
    lines.append("## Color palette")
    for item in analysis.get("palette_lines") or []:
        lines.append(f"- {item}")
    lines.extend(["", "## Typography"])
    for item in analysis.get("typography_lines") or []:
        lines.append(f"- {item}")
    return "\n".join(lines)


def render_layout(snapshot: dict[str, Any], analysis: dict[str, Any]) -> str:
    lines = ["# Layout", "", "## Structure"]
    for item in analysis.get("layout_cues") or []:
        lines.append(f"- {item}")
    if snapshot.get("headings"):
        lines.extend(["", "## Sections"])
        for item in (snapshot.get("headings") or [])[:5]:
            lines.append(f"- {item}")
    return "\n".join(lines)


def render_motion(analysis: dict[str, Any]) -> str:
    lines = ["# Motion", "", "## Motion cues"]
    for item in analysis.get("motion_cues") or []:
        lines.append(f"- {item}")
    return "\n".join(lines)


def render_instructions() -> str:
    return "\n".join(
        [
            "# INSTRUCTIONS",
            "",
            "Use `reference.md` first for prompt context, then pull specific doctrine from `principles.md` and concrete carriers from `components.md`.",
            "Treat this inspiration as transferable mechanics, not literal brand truth.",
        ]
    )


def render_qa() -> str:
    return "\n".join(
        [
            "# QA",
            "",
            "- Keep one focal move dominant.",
            "- Keep borrowed mechanics translated, not literal.",
            "- Preserve spacing discipline and hierarchy before adding decorative detail.",
            "- Ensure foreign logos, copy, and source-specific brand assets are removed.",
        ]
    )


def write_semantic_design_memory(
    target_root: Path,
    source: dict[str, Any],
    snapshot: dict[str, Any],
    analysis: dict[str, Any],
    *,
    degraded: bool = False,
) -> Path:
    design_memory_dir = target_root / ".design-memory"
    design_memory_dir.mkdir(parents=True, exist_ok=True)
    _safe_write(design_memory_dir / "INSTRUCTIONS.md", render_instructions())
    _safe_write(design_memory_dir / "reference.md", render_reference(source, snapshot, analysis, degraded=degraded))
    _safe_write(design_memory_dir / "principles.md", render_principles(source, analysis))
    _safe_write(design_memory_dir / "components.md", render_components(analysis))
    _safe_write(design_memory_dir / "style.md", render_style(analysis))
    _safe_write(design_memory_dir / "layout.md", render_layout(snapshot, analysis))
    _safe_write(design_memory_dir / "motion.md", render_motion(analysis))
    _safe_write(design_memory_dir / "qa.md", render_qa())
    source_summary = {
        "source": {
            "key": source.get("key"),
            "name": source.get("name"),
            "category": source.get("category"),
            "url": source.get("url"),
            "notes": source.get("notes"),
            "tags": list(source.get("tags") or []),
            "borrow_mechanics": list(source.get("borrow_mechanics") or []),
            "avoid_literal": list(source.get("avoid_literal") or []),
            "best_for": list(source.get("best_for") or []),
            "direct_generation_risk": source.get("direct_generation_risk") or "",
        },
        "snapshot": {
            "requested_url": snapshot.get("requested_url"),
            "final_url": snapshot.get("final_url"),
            "title": snapshot.get("title"),
            "meta_description": snapshot.get("meta_description"),
            "headings": list(snapshot.get("headings") or [])[:MAX_HEADINGS],
            "stylesheets": list(snapshot.get("stylesheets") or [])[:MAX_STYLESHEETS],
            "warnings": list(snapshot.get("warnings") or [])[:8],
        },
        "analysis": analysis,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "degraded": degraded,
    }
    _safe_write(design_memory_dir / "source-summary.json", json.dumps(source_summary, indent=2))
    return design_memory_dir


def extract_inspiration_source(source: dict[str, Any], target_root: Path, *, timeout: int = 120) -> dict[str, Any]:
    start = time.time()
    key = str(source.get("key") or "").strip()
    category = str(source.get("category") or "").strip()
    url = str(source.get("url") or "").strip()
    if not key or not category or not url:
        missing = [name for name, value in (("key", key), ("category", category), ("url", url)) if not value]
        return {
            "key": key or "(unknown)",
            "status": "failed",
            "error": "source is missing required fields: " + ", ".join(missing),
            "warning": None,
            "duration": round(time.time() - start, 2),
            "designMemoryPath": str((target_root / category / key / ".design-memory").resolve()),
            "extractor": "builtin-semantic",
            "mode": "invalid-source",
        }

    target = target_root / category / key
    target.mkdir(parents=True, exist_ok=True)
    warning = None
    degraded = False
    try:
        snapshot = capture_web_snapshot(url, timeout=max(5, min(timeout, 60)))
        mode = "metadata-plus-fetch"
    except Exception as exc:
        degraded = True
        warning = f"remote fetch unavailable; extracted from curated metadata only ({exc})"
        snapshot = {
            "requested_url": url,
            "final_url": url,
            "content_type": "",
            "title": source.get("name") or key,
            "meta_description": source.get("notes") or "",
            "og_title": "",
            "og_description": "",
            "headings": [],
            "class_tokens": {},
            "stylesheets": [],
            "css_texts": [],
            "warnings": [warning],
        }
        mode = "metadata-only"

    try:
        analysis = analyze_snapshot(source, snapshot, degraded=degraded)
        design_memory_dir = write_semantic_design_memory(target, source, snapshot, analysis, degraded=degraded)
    except Exception as exc:
        return {
            "key": key,
            "status": "failed",
            "error": compact_text(str(exc), 500),
            "warning": warning,
            "duration": round(time.time() - start, 2),
            "designMemoryPath": str((target / ".design-memory").resolve()),
            "extractor": "builtin-semantic",
            "mode": mode,
        }

    return {
        "key": key,
        "status": "complete",
        "error": None,
        "warning": warning,
        "duration": round(time.time() - start, 2),
        "designMemoryPath": str(design_memory_dir.resolve()),
        "extractor": "builtin-semantic",
        "mode": mode,
    }
