#!/usr/bin/env python3
"""Extract a structured brand profile plus richer design-language storage from a project folder."""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
import urllib.error
from collections import Counter
from pathlib import Path
from typing import Any

from design_memory_lite import normalize_lines, parse_design_memory  # type: ignore

TEXT_EXTS = {'.md', '.txt', '.json', '.css', '.scss', '.sass', '.less', '.js', '.jsx', '.ts', '.tsx', '.html', '.erb'}
ASSET_EXTS = {'.png', '.jpg', '.jpeg', '.webp', '.svg', '.gif', '.pdf'}
COLOR_RE = re.compile(r'#[0-9a-fA-F]{3,8}\b')
CSS_VAR_RE = re.compile(r'(--[a-zA-Z0-9-]+)\s*:\s*([^;]+);')
FONT_RE = re.compile(r'font-family\s*:\s*([^;]+);', re.IGNORECASE)
TAILWIND_FONT_RE = re.compile(r'fontFamily\s*:\s*\{([^}]+)\}', re.DOTALL)
ROUNDED_RE = re.compile(r'rounded(?:-[a-z0-9]+)?')
TOKEN_RE = re.compile(r'[a-zA-Z][a-zA-Z-]{3,}')
RGB_RE = re.compile(r'rgba?\((\d+),\s*(\d+),\s*(\d+)(?:,\s*([\d.]+))?\)')
BRAND_WORDS = {
    'premium', 'playful', 'bold', 'editorial', 'minimal', 'modern', 'technical', 'trust', 'warm',
    'friendly', 'luxury', 'geometric', 'fluid', 'elegant', 'clean', 'confident', 'serious', 'expressive',
    'creative', 'innovative', 'fast', 'simple', 'powerful', 'professional', 'sophisticated', 'calm', 'dark', 'light',
    'approachable', 'intelligent', 'governed', 'community', 'network', 'system', 'curated', 'knowledge'
}
PACKAGE_NAME_SUFFIXES = ('-web-app', '-webapp', '-frontend', '-client', '-site', '-app', '-ui')
UPPER_WORDS = {'ai', 'ui', 'ux', 'dao', 'mcp', 'api', 'sdk', 'ipfs'}

LOGO_LINK_RE = re.compile(
    r'<link[^>]+rel=["\'](?:icon|shortcut icon|apple-touch-icon)["\'][^>]*>',
    re.IGNORECASE,
)
HREF_RE = re.compile(r'href=["\']([^"\']+)["\']', re.IGNORECASE)
OG_IMAGE_RE = re.compile(
    r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
    re.IGNORECASE,
)
OG_IMAGE_RE_ALT = re.compile(
    r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',
    re.IGNORECASE,
)


def _url_join(base: str, href: str) -> str:
    """Join a base URL with a potentially relative href."""
    if href.startswith(('http://', 'https://', '//')):
        if href.startswith('//'):
            return 'https:' + href
        return href
    from urllib.parse import urljoin
    return urljoin(base, href)


def _guess_ext(url: str, content_type: str) -> str:
    """Guess a file extension from URL or Content-Type header."""
    url_lower = url.lower().split('?')[0].split('#')[0]
    for ext in ('.svg', '.png', '.ico', '.jpg', '.jpeg', '.webp', '.gif'):
        if url_lower.endswith(ext):
            return ext
    ct = content_type.lower()
    if 'svg' in ct:
        return '.svg'
    if 'png' in ct:
        return '.png'
    if 'ico' in ct or 'x-icon' in ct:
        return '.ico'
    if 'jpeg' in ct or 'jpg' in ct:
        return '.jpg'
    if 'webp' in ct:
        return '.webp'
    if 'gif' in ct:
        return '.gif'
    return '.png'


def fetch_logo_from_url(homepage_url: str, output_dir: Path) -> Path | None:
    """Fetch a logo/favicon/og:image from a homepage URL and save it locally.

    Tries (in order): og:image, apple-touch-icon, favicon link, /favicon.ico fallback.
    Returns the saved file path, or None on failure.
    """
    if not homepage_url:
        return None
    homepage_url = homepage_url.rstrip('/')
    if not homepage_url.startswith(('http://', 'https://')):
        homepage_url = 'https://' + homepage_url

    try:
        req = urllib.request.Request(homepage_url, headers={'User-Agent': 'brand-gen/1.0'})
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode('utf-8', errors='ignore')
    except Exception as exc:
        print(f"WARNING: Could not fetch {homepage_url} for logo discovery: {exc}", file=sys.stderr)
        return None

    # Collect candidate URLs in priority order
    candidates: list[tuple[str, str]] = []

    # 1. apple-touch-icon (high quality square PNG, usually 180x180+)
    # 2. Other link[rel=icon] entries (square logo marks)
    for link_match in LOGO_LINK_RE.finditer(html):
        link_tag = link_match.group(0)
        href_match = HREF_RE.search(link_tag)
        if not href_match:
            continue
        href = href_match.group(1)
        full_url = _url_join(homepage_url, href)
        if 'apple-touch-icon' in link_tag.lower():
            candidates.append((full_url, 'apple-touch-icon'))
        else:
            candidates.append((full_url, 'favicon'))

    # 3. og:image (often a wide social banner — less ideal as logo mark, but
    #    still useful if no square icon was found)
    og_match = OG_IMAGE_RE.search(html) or OG_IMAGE_RE_ALT.search(html)
    if og_match:
        candidates.append((_url_join(homepage_url, og_match.group(1)), 'og-image'))

    # 4. Fallback: /favicon.ico
    candidates.append((_url_join(homepage_url, '/favicon.ico'), 'favicon-fallback'))

    # Try each candidate until one downloads successfully
    output_dir.mkdir(parents=True, exist_ok=True)
    for url, source_label in candidates:
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'brand-gen/1.0'})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = resp.read()
                content_type = resp.headers.get('Content-Type', '')
            if len(data) < 100:
                continue  # too small to be a real image
            ext = _guess_ext(url, content_type)
            out_path = output_dir / f'logo-fetched{ext}'
            out_path.write_bytes(data)
            print(f"Fetched logo from {source_label}: {url} -> {out_path}", file=sys.stderr)
            return out_path
        except Exception:
            continue

    print(f"WARNING: No logo could be fetched from {homepage_url}", file=sys.stderr)
    return None


def read_text(path: Path) -> str:
    try:
        return path.read_text(errors='ignore')
    except Exception:
        return ''


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text())
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


def dedupe_keep_order(items: list[Any]) -> list[Any]:
    out: list[Any] = []
    seen: set[str] = set()
    for item in items:
        key = json.dumps(item, sort_keys=True) if isinstance(item, (dict, list)) else str(item).strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def derive_brand_assets(logo_files: list[str]) -> dict[str, Any]:
    candidates = dedupe_keep_order(logo_files)[:20]
    lowered = [(item, item.lower()) for item in candidates]
    def pick(matchers: tuple[str, ...]) -> str:
        for original, low in lowered:
            if any(token in low for token in matchers):
                return original
        return ""
    icon = pick(("icon", "mark", "symbol", "logo.png", "logo.svg")) or (candidates[0] if candidates else "")
    wordmark = pick(("wordmark", "logotype", "typemark"))
    lockup = pick(("lockup", "logo-lockup", "brand-lockup", "horizontal-logo", "full-logo"))
    return {
        "icon": icon,
        "wordmark": wordmark,
        "lockup": lockup,
        "icon_candidates": candidates,
        "wordmark_candidates": [item for item, low in lowered if any(token in low for token in ("wordmark", "logotype", "typemark"))][:10],
        "lockup_candidates": [item for item, low in lowered if any(token in low for token in ("lockup", "logo-lockup", "brand-lockup", "horizontal-logo", "full-logo"))][:10],
        "allow_synthetic_lockup": False,
    }


def sentence_join(items: list[Any]) -> str:
    values = [str(item).strip() for item in items if str(item).strip()]
    if not values:
        return ''
    if len(values) == 1:
        return values[0]
    if len(values) == 2:
        return f'{values[0]} and {values[1]}'
    return ', '.join(values[:-1]) + f', and {values[-1]}'


def rgb_to_hex(value: str) -> str | None:
    match = RGB_RE.search(value or '')
    if not match:
        return None
    r, g, b = (max(0, min(255, int(match.group(i)))) for i in range(1, 4))
    return f'#{r:02x}{g:02x}{b:02x}'


def normalize_color_candidate(value: Any) -> str | None:
    if not value:
        return None
    if isinstance(value, dict):
        value = value.get('normalized') or value.get('color') or value.get('hex') or value.get('value')
    if not isinstance(value, str):
        return None
    value = value.strip()
    if value.startswith('#'):
        return value.lower()
    rgb_hex = rgb_to_hex(value)
    if rgb_hex:
        return rgb_hex.lower()
    return None


def find_package_name(project_root: Path) -> tuple[str | None, str | None]:
    package_json = project_root / 'package.json'
    if not package_json.exists():
        return None, None
    try:
        data = json.loads(package_json.read_text())
    except Exception:
        return None, None
    return data.get('name'), data.get('description')


def humanize_brand_name(raw: str | None) -> str:
    value = (raw or '').strip()
    if not value:
        return ''
    normalized = value.replace('_', '-')
    lower = normalized.lower()
    for suffix in PACKAGE_NAME_SUFFIXES:
        if lower.endswith(suffix) and len(normalized) > len(suffix):
            normalized = normalized[:-len(suffix)]
            break
    parts = [part for part in re.split(r'[-\s]+', normalized) if part]
    if not parts:
        return value
    out = []
    for part in parts:
        low = part.lower()
        if low in UPPER_WORDS:
            out.append(low.upper())
        elif part.isupper():
            out.append(part)
        else:
            out.append(part.capitalize())
    return ' '.join(out)


def iter_candidate_files(project_root: Path):
    for path in project_root.rglob('*'):
        if not path.is_file():
            continue
        if any(part.startswith('.') and part not in {'.github'} for part in path.parts):
            continue
        if path.suffix.lower() in TEXT_EXTS or path.name.lower().startswith('readme') or path.name.startswith('tailwind.config'):
            yield path


def first_readme(project_root: Path) -> tuple[str, list[str]]:
    readmes = sorted([p for p in project_root.rglob('*') if p.is_file() and p.name.lower().startswith('readme')])
    if not readmes:
        return '', []
    main = read_text(readmes[0])
    return main, [str(p.relative_to(project_root)) for p in readmes[:10]]


# Generic/fallback fonts that are CSS defaults, not brand choices.
# Keep them as fallbacks in the raw list but filter from brand-level typography cues.
GENERIC_FONT_FAMILIES = {
    'system-ui', '-apple-system', 'blinkmacsystemfont', 'sans-serif', 'serif',
    'monospace', 'cursive', 'fantasy', 'ui-sans-serif', 'ui-serif', 'ui-monospace',
    'ui-rounded', 'inherit', 'initial', 'unset', 'revert',
}

# Common CSS variable patterns → resolved font names.
# Populated from project CSS vars during extraction; this is the static fallback map.
CSS_VAR_FONT_MAP: dict[str, str] = {
    'var(--font-inter)': 'Inter',
    'var(--font-fraunces)': 'Fraunces',
    'var(--font-mono)': 'monospace',
    'var(--font-sans)': 'sans-serif',
    'var(--font-serif)': 'serif',
}
CSS_VAR_FONT_RE = re.compile(r'var\(\s*(--[a-zA-Z0-9-]+)\s*\)')


def resolve_css_var_font(token: str, css_vars: dict[str, str] | None = None) -> str:
    """Resolve a CSS variable font reference to an actual font name.

    Checks the project's own CSS vars first, then a static fallback map,
    then strips the var() wrapper and infers the font name from the variable name.
    """
    if not token.startswith('var('):
        return token
    m = CSS_VAR_FONT_RE.match(token)
    if not m:
        return token
    var_name = m.group(1)  # e.g. --font-inter
    # Check project CSS vars
    if css_vars:
        value = css_vars.get(var_name, '').strip().strip('"\'').strip()
        if value and not value.startswith('var('):
            # Take the first font family from a comma-separated list
            first = value.split(',')[0].strip().strip('"\'').strip()
            if first:
                return first
    # Check static map
    low = token.lower().strip()
    if low in CSS_VAR_FONT_MAP:
        return CSS_VAR_FONT_MAP[low]
    # Infer from variable name: --font-inter → Inter, --sage-font-sans → sans
    name_part = var_name.split('font-')[-1] if 'font-' in var_name else ''
    if name_part:
        cleaned = name_part.replace('-', ' ').strip()
        # If it resolves to a generic family, return the generic (will be filtered later)
        if cleaned.lower() in GENERIC_FONT_FAMILIES:
            return cleaned.lower()
        if cleaned:
            return cleaned.title()
    return token


def classify_font_role(font_name: str, index: int, total: int) -> str:
    """Heuristic classification of a font's semantic role based on name and position."""
    low = font_name.lower()
    if any(kw in low for kw in ['mono', 'code', 'fira code', 'jetbrains', 'consolas', 'courier', 'source code']):
        return 'mono'
    if any(kw in low for kw in ['display', 'playfair', 'fraunces', 'crimson', 'lora', 'merriweather', 'georgia', 'garamond']):
        return 'display'
    if any(kw in low for kw in ['heading', 'title', 'hero']):
        return 'heading'
    # First font in the list is typically body/primary; second is often heading/display
    if index == 0:
        return 'body'
    if index == 1 and total > 2:
        return 'heading'
    return 'body'


def extract_fonts(text: str, css_vars: dict[str, str] | None = None) -> list[str]:
    fonts = []
    for match in FONT_RE.findall(text):
        fonts.extend(part.strip().strip('"\'') for part in match.split(',') if part.strip())
    tailwind_match = TAILWIND_FONT_RE.search(text)
    if tailwind_match:
        fonts.extend(re.findall(r'"([^"]+)"|\'([^\']+)\'', tailwind_match.group(1)))
    normalized = []
    seen = set()
    for item in fonts:
        if isinstance(item, tuple):
            item = next((x for x in item if x), '')
        item = str(item).strip()
        if not item:
            continue
        # Resolve CSS variables to actual font names
        item = resolve_css_var_font(item, css_vars)
        low = item.lower()
        if low in seen:
            continue
        seen.add(low)
        normalized.append(item)
    return normalized[:16]


# Short/meaningless names that result from poorly-resolved CSS variable inference.
# These are not real font names and should be filtered alongside generics.
INFERRED_JUNK_NAMES = {'family', 'sans', 'mono', 'body', 'heading', 'display', 'text', 'base', 'default', 'primary', 'secondary'}


def filter_generic_fonts(fonts: list[str]) -> list[str]:
    """Remove generic CSS fallback families and junk inferred names, keeping only named brand fonts."""
    return [f for f in fonts if f.lower() not in GENERIC_FONT_FAMILIES and f.lower() not in INFERRED_JUNK_NAMES]


def build_font_roles(fonts: list[str]) -> dict[str, str]:
    """Assign semantic roles (body, heading, display, mono) to brand fonts.

    Returns a dict like {"body": "Inter", "display": "Fraunces", "mono": "JetBrains Mono"}.
    """
    brand_fonts = filter_generic_fonts(fonts)
    if not brand_fonts:
        return {}
    roles: dict[str, str] = {}
    assigned: set[str] = set()
    for idx, font in enumerate(brand_fonts):
        role = classify_font_role(font, idx, len(brand_fonts))
        if role not in roles:
            roles[role] = font
            assigned.add(font)
    # If we have 2+ fonts and no heading, promote the second to heading
    if len(brand_fonts) >= 2 and 'heading' not in roles and 'display' not in roles:
        for font in brand_fonts[1:]:
            if font not in assigned:
                roles['heading'] = font
                break
    return roles


def extract_keywords(texts: list[str]) -> list[str]:
    counter = Counter()
    for text in texts:
        for token in TOKEN_RE.findall(text.lower()):
            if token in BRAND_WORDS:
                counter[token] += 1
    return [word for word, _ in counter.most_common(16)]


def simplify_typography_style(style: dict[str, Any]) -> dict[str, Any]:
    return {
        'font_family': style.get('fontFamily') or style.get('family') or '',
        'font_size': style.get('fontSize') or style.get('size') or '',
        'font_weight': style.get('fontWeight') or style.get('weight') or '',
        'line_height': style.get('lineHeight') or '',
        'contexts': style.get('contexts') or style.get('context') or [],
        'confidence': style.get('confidence') or '',
    }


def normalize_component_map(components: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in (components or {}).items():
        out[key] = value[:8] if isinstance(value, list) else value
    return out


def normalize_collection(value: Any, *, limit: int = 20) -> list[Any] | dict[str, Any]:
    if isinstance(value, list):
        return value[:limit]
    if isinstance(value, dict):
        return dict(list(value.items())[:limit])
    return []


def load_design_tokens(path: Path | None) -> dict[str, Any]:
    if not path or not path.exists():
        return {}
    raw = read_json(path)
    if not raw:
        return {}

    colors = raw.get('colors') or {}
    typography = raw.get('typography') or {}
    spacing = raw.get('spacing') or {}
    border_radius = raw.get('borderRadius') or raw.get('border_radius') or {}
    components = raw.get('components') or {}

    palette = colors.get('palette') or []
    semantic = colors.get('semantic') or {}
    css_variables = colors.get('cssVariables') or colors.get('css_variables') or {}
    styles = [simplify_typography_style(item) for item in (typography.get('styles') or [])[:24] if isinstance(item, dict)]
    font_families = dedupe_keep_order([item.get('font_family') for item in styles if item.get('font_family')])[:12]

    return {
        'source_file': str(path.resolve()),
        'source_url': raw.get('url') or '',
        'extracted_at': raw.get('extractedAt') or '',
        'logo': raw.get('logo'),
        'colors': {
            'semantic': semantic,
            'palette': palette[:24],
            'css_variables': dict(list(css_variables.items())[:40]),
        },
        'typography': {
            'styles': styles,
            'sources': normalize_collection(typography.get('sources') or [], limit=12),
            'font_families': font_families,
        },
        'spacing': {
            'scale_type': spacing.get('scaleType') or '',
            'common_values': (spacing.get('commonValues') or [])[:20],
        },
        'border_radius': {
            'values': (border_radius.get('values') or [])[:20],
        },
        'borders': raw.get('borders') or {},
        'shadows': (raw.get('shadows') or [])[:20],
        'components': normalize_component_map(components),
        'breakpoints': (raw.get('breakpoints') or [])[:20],
        'icon_system': (raw.get('iconSystem') or raw.get('icon_system') or [])[:20],
        'frameworks': (raw.get('frameworks') or [])[:20],
    }


def resolve_design_memory_path(project_root: Path, explicit: Path | None) -> Path | None:
    if explicit and explicit.exists():
        return explicit
    candidate = project_root / '.design-memory'
    if candidate.exists():
        return candidate
    return None


def load_design_memory_summary(path: Path | None) -> dict[str, Any]:
    if not path:
        return {}
    try:
        return parse_design_memory(str(path))
    except Exception:
        return {}


def normalize_design_memory(summary: dict[str, Any]) -> dict[str, Any]:
    if not summary:
        return {}
    css_variables = summary.get('css_variables') or []
    return {
        'source_dir': summary.get('design_memory_dir') or '',
        'files_present': summary.get('files_present') or [],
        'principles': normalize_lines(summary.get('principles', ''))[:10],
        'components': normalize_lines(summary.get('components', ''))[:12],
        'layout': normalize_lines(summary.get('layout', ''))[:10],
        'motion': normalize_lines(summary.get('motion', ''))[:8],
        'color_palette': normalize_lines(summary.get('color_palette', ''))[:10],
        'typography_scale': normalize_lines(summary.get('typography_scale', ''))[:10],
        'breakpoints': normalize_lines(summary.get('breakpoints', ''))[:8],
        'css_variables': {item.get('name', ''): item.get('value', '') for item in css_variables if item.get('name')},
        'css_variables_block': summary.get('css_variables_block') or '',
        'summary': summary.get('summary') or {},
    }


def colors_from_design_memory(summary: dict[str, Any]) -> list[str]:
    if not summary:
        return []
    colors: list[str] = []
    for item in summary.get('css_variables') or []:
        normalized = normalize_color_candidate(item.get('value'))
        if normalized:
            colors.append(normalized)
    palette_text = summary.get('color_palette') or ''
    colors.extend(match.lower() for match in COLOR_RE.findall(palette_text))
    return dedupe_keep_order([item for item in colors if item])


def summarize_design_language(*, colors: list[str], fonts: list[str], radius: list[str], design_tokens: dict[str, Any]) -> dict[str, Any]:
    semantic_names = list((design_tokens.get('colors') or {}).get('semantic', {}).keys())[:12]
    typography_styles = (design_tokens.get('typography') or {}).get('styles', [])[:8]
    spacing_values = (design_tokens.get('spacing') or {}).get('common_values', [])[:12]
    border_radius = (design_tokens.get('border_radius') or {}).get('values', [])[:12]
    components = design_tokens.get('components') or {}
    component_cues = [key for key, value in components.items() if value]
    # Filter generics and build semantic font roles
    brand_fonts = filter_generic_fonts(fonts)
    font_roles = build_font_roles(brand_fonts)
    return {
        'palette_direction': colors[:10],
        'semantic_palette_roles': semantic_names,
        'typography_voice': brand_fonts[:10],
        'typography_roles': font_roles,
        'typography_styles': typography_styles,
        'shape_language': {
            'radius_tokens': radius[:10],
            'border_radius_values': border_radius,
            'shadow_examples': (design_tokens.get('shadows') or [])[:6],
        },
        'spacing_scale': spacing_values,
        'component_cues': component_cues[:12],
        'framework_cues': [item.get('name', '') for item in (design_tokens.get('frameworks') or []) if isinstance(item, dict)][:8],
        'icon_systems': [item.get('name', '') if isinstance(item, dict) else str(item) for item in (design_tokens.get('icon_system') or [])][:8],
    }


def build_guardrail_prelude(brand_name: str, description: str, keywords: list[str], colors: list[str], fonts: list[str], radius: list[str], design_language: dict[str, Any], design_memory: dict[str, Any] | None = None) -> str:
    tone = ', '.join(keywords[:5]) or 'clear, confident, and specific'
    palette = ', '.join(colors[:6]) or 'the existing brand palette'
    # Use semantic font roles when available, fall back to raw list
    font_roles = design_language.get('typography_roles') or build_font_roles(filter_generic_fonts(fonts))
    if font_roles:
        role_parts = []
        for role in ['body', 'heading', 'display', 'mono']:
            if role in font_roles:
                role_parts.append(f'{font_roles[role]} ({role})')
        typography = ', '.join(role_parts) if role_parts else ', '.join(filter_generic_fonts(fonts)[:4]) or 'the existing typography'
    else:
        brand_fonts = filter_generic_fonts(fonts)
        typography = ', '.join(brand_fonts[:4]) or 'the existing typography'
    shape = ', '.join(radius[:4]) or 'the existing interface geometry'
    component_cues = ', '.join(design_language.get('component_cues', [])[:4]) or 'the brand\'s UI components'
    parts = [
        f'Preserve the brand truth of {brand_name} before adding any presentation treatment. '
        f'{brand_name} should feel {tone}. It represents {description or "a modern digital product"}. '
        f'Keep palette direction anchored in {palette}, typography cues anchored in {typography}, '
        f'shape language anchored in {shape}, and component behavior anchored in {component_cues}. '
        f'External references may influence framing, campaign treatment, and composition, but they must not replace the brand\'s aesthetic, tone, or design language.'
    ]
    if design_memory:
        principles = sentence_join((design_memory.get('principles') or [])[:3])
        layout_cues = sentence_join((design_memory.get('layout') or [])[:2])
        memory_components = sentence_join((design_memory.get('components') or [])[:3])
        if principles:
            parts.append(f'Honor the extracted design doctrine: {principles}.')
        if layout_cues:
            parts.append(f'Keep layout discipline aligned with {layout_cues}.')
        if memory_components:
            parts.append(f'Preserve component cues such as {memory_components}.')
    return ' '.join(part.strip() for part in parts if part.strip())


def extract_profile(project_root: Path, brand_name: str | None, homepage_url: str | None, notes_text: str, reference_dir: Path | None, design_tokens_json: Path | None, design_memory_path: Path | None) -> dict[str, Any]:
    pkg_name, pkg_description = find_package_name(project_root)
    readme_text, readme_files = first_readme(project_root)
    description = pkg_description
    if not description and readme_text:
        paragraphs = [p.strip() for p in readme_text.split('\n\n') if p.strip() and not p.strip().startswith('#')]
        description = paragraphs[0] if paragraphs else ''

    color_counter = Counter()
    css_vars = {}
    fonts = []
    rounded = Counter()
    evidence_files = []
    marketing_files = []
    logo_files = []
    collected_texts = [readme_text, notes_text, description or '']

    for path in iter_candidate_files(project_root):
        rel = str(path.relative_to(project_root))
        text = read_text(path)
        if not text:
            continue
        if any(part in rel.lower() for part in ['landing', 'marketing', 'hero', 'pricing', 'blog', 'changelog', 'brand']):
            marketing_files.append(rel)
        colors = COLOR_RE.findall(text)
        color_counter.update(color.lower() for color in colors)
        css_vars.update({name: value.strip() for name, value in CSS_VAR_RE.findall(text)})
        fonts.extend(extract_fonts(text, css_vars))
        rounded.update(ROUNDED_RE.findall(text))
        if colors or 'font-family' in text or rel.lower().startswith('tailwind.config'):
            evidence_files.append(rel)
        if rel.lower().endswith(('.md', '.txt')):
            collected_texts.append(text)

    for asset_root in [project_root / 'public', project_root / 'assets', project_root / 'src' / 'assets']:
        if not asset_root.exists():
            continue
        for path in asset_root.rglob('*'):
            if path.is_file() and any(term in path.name.lower() for term in ['logo', 'brand', 'icon']):
                logo_files.append(str(path.relative_to(project_root)))

    if reference_dir and reference_dir.exists():
        for path in sorted(reference_dir.iterdir()):
            if path.is_file():
                logo_files.append(str(path))

    # Auto-fetch logo from homepage if none found locally
    if not logo_files and homepage_url:
        brand_materials_dir = project_root / 'brand-materials'
        fetched = fetch_logo_from_url(homepage_url, brand_materials_dir)
        if fetched:
            try:
                logo_files.append(str(fetched.relative_to(project_root)))
            except ValueError:
                logo_files.append(str(fetched))

    design_tokens = load_design_tokens(design_tokens_json)
    design_memory_summary = load_design_memory_summary(resolve_design_memory_path(project_root, design_memory_path))
    design_memory = normalize_design_memory(design_memory_summary)

    unique_fonts = []
    seen_fonts = set()
    for font in fonts + (design_tokens.get('typography', {}).get('font_families', []) if design_tokens else []):
        key = font.lower()
        if key in seen_fonts:
            continue
        seen_fonts.add(key)
        unique_fonts.append(font)

    token_palette = [normalize_color_candidate(item) for item in (design_tokens.get('colors', {}).get('palette', []) if design_tokens else [])]
    token_semantic = [normalize_color_candidate(v) for v in (design_tokens.get('colors', {}).get('semantic', {}).values() if design_tokens else [])]
    design_memory_palette = colors_from_design_memory(design_memory_summary)
    detected_colors = [color for color, _ in color_counter.most_common(14)]
    top_colors = dedupe_keep_order([c for c in token_palette + token_semantic + design_memory_palette + detected_colors if c])[:16]

    token_radius = []
    if design_tokens:
        for item in design_tokens.get('border_radius', {}).get('values', []):
            if isinstance(item, dict):
                value = item.get('value') or item.get('px') or item.get('name')
                if value:
                    token_radius.append(str(value))
    top_radius = dedupe_keep_order([token for token, _ in rounded.most_common(6)] + token_radius)[:10]
    keywords = extract_keywords(collected_texts)
    design_language = summarize_design_language(colors=top_colors, fonts=unique_fonts, radius=top_radius, design_tokens=design_tokens)
    if design_memory:
        design_language['palette_direction'] = dedupe_keep_order((design_language.get('palette_direction') or []) + (design_memory.get('color_palette') or []))[:12]
        design_language['semantic_palette_roles'] = dedupe_keep_order((design_language.get('semantic_palette_roles') or []) + (design_memory.get('color_palette') or []))[:12]
        design_language['typography_voice'] = dedupe_keep_order((design_language.get('typography_voice') or []) + (design_memory.get('typography_scale') or []))[:12]
        design_language['component_cues'] = dedupe_keep_order((design_language.get('component_cues') or []) + (design_memory.get('components') or []))[:12]
        design_language['layout_cues'] = (design_memory.get('layout') or [])[:10]
        design_language['motion_cues'] = (design_memory.get('motion') or [])[:8]
        design_language['design_memory_principles'] = (design_memory.get('principles') or [])[:10]
        if design_memory.get('source_dir'):
            design_language['design_memory_source'] = design_memory['source_dir']
    brand_name_final = humanize_brand_name(brand_name or pkg_name or project_root.name)
    guardrail_prelude = build_guardrail_prelude(brand_name_final, description or '', keywords, top_colors, unique_fonts, top_radius, design_language, design_memory=design_memory)
    merged_css_vars = dict(list({**css_vars, **(design_memory.get('css_variables') or {})}.items())[:40])

    brand_assets = derive_brand_assets(sorted(dict.fromkeys(logo_files))[:20])

    return {
        'profile_version': 2,
        'brand_name': brand_name_final,
        'homepage_url': homepage_url or (design_tokens.get('source_url', '') if design_tokens else ''),
        'project_root': str(project_root),
        'description': description or '',
        'keywords': keywords,
        'color_candidates': top_colors,
        'css_variables': merged_css_vars,
        'font_candidates': filter_generic_fonts(unique_fonts)[:12],
        'font_roles': build_font_roles(filter_generic_fonts(unique_fonts)),
        'radius_tokens': top_radius,
        'logo_candidates': sorted(dict.fromkeys(logo_files))[:20],
        'brand_assets': brand_assets,
        'marketing_files': sorted(dict.fromkeys(marketing_files))[:20],
        'readme_files': readme_files,
        'evidence_files': sorted(dict.fromkeys(evidence_files))[:25],
        'notes_excerpt': notes_text[:1000].strip(),
        'design_tokens': design_tokens,
        'design_memory': design_memory,
        'design_language': design_language,
        'brand_guardrail_prelude': guardrail_prelude,
        'identity': {
            'summary': description or '',
            'tone_words': keywords[:10],
            'existing_brand_anchors': sorted(dict.fromkeys(logo_files))[:8],
            'presentation_rule': 'External references may influence framing and campaign treatment, but they must not erase the brand tone, palette direction, or shape language.',
            'product_truth_rule': 'Real product screenshots and actual product structure remain the source of truth unless explicit redesign is requested.',
            'design_memory_rule': (
                f"Borrow doctrine from {design_memory.get('source_dir')} only to strengthen the stored brand language."
                if design_memory.get('source_dir')
                else ''
            ),
            'brand_guardrail_prelude': guardrail_prelude,
        },
    }


def to_markdown(profile: dict[str, Any]) -> str:
    lines = [
        f"# {profile['brand_name']} brand profile",
        '',
        '## Summary',
        f"- Project root: {profile['project_root']}",
        f"- Homepage URL: {profile['homepage_url'] or 'n/a'}",
        f"- Description: {profile['description'] or 'n/a'}",
        f"- Tone words: {', '.join(profile.get('keywords', [])) or 'n/a'}",
        '',
        '## Visual candidates',
        f"- Colors: {', '.join(profile.get('color_candidates', [])) or 'n/a'}",
        f"- Fonts: {', '.join(profile.get('font_candidates', [])) or 'n/a'}",
        f"- Radius / shape hints: {', '.join(profile.get('radius_tokens', [])) or 'n/a'}",
        '',
        '## Global brand guardrail prelude',
        '```text',
        profile.get('brand_guardrail_prelude', ''),
        '```',
        '',
        '## Brand truth rules',
        f"- Presentation rule: {profile.get('identity', {}).get('presentation_rule', 'n/a')}",
        f"- Product truth rule: {profile.get('identity', {}).get('product_truth_rule', 'n/a')}",
        '',
        '## Assets and evidence',
        f"- Logo / icon candidates: {', '.join(profile.get('logo_candidates', [])) or 'n/a'}",
        f"- Brand assets: icon={((profile.get('brand_assets') or {}).get('icon') or 'n/a')}, wordmark={((profile.get('brand_assets') or {}).get('wordmark') or 'n/a')}, lockup={((profile.get('brand_assets') or {}).get('lockup') or 'n/a')}",
        f"- Marketing files: {', '.join(profile.get('marketing_files', [])) or 'n/a'}",
        f"- Readme files: {', '.join(profile.get('readme_files', [])) or 'n/a'}",
        f"- Evidence files: {', '.join(profile.get('evidence_files', [])) or 'n/a'}",
    ]
    if profile.get('css_variables'):
        lines += ['', '## CSS variable samples']
        for key, value in profile['css_variables'].items():
            lines.append(f'- `{key}` = `{value}`')
    lang = profile.get('design_language') or {}
    if lang:
        lines += [
            '', '## Design language',
            f"- Palette direction: {', '.join(lang.get('palette_direction', [])) or 'n/a'}",
            f"- Semantic roles: {', '.join(lang.get('semantic_palette_roles', [])) or 'n/a'}",
            f"- Typography voice: {', '.join(lang.get('typography_voice', [])) or 'n/a'}",
            f"- Component cues: {', '.join(lang.get('component_cues', [])) or 'n/a'}",
            f"- Framework cues: {', '.join(lang.get('framework_cues', [])) or 'n/a'}",
        ]
        if lang.get('layout_cues'):
            lines.append(f"- Layout cues: {', '.join(lang.get('layout_cues', [])) or 'n/a'}")
        if lang.get('motion_cues'):
            lines.append(f"- Motion cues: {', '.join(lang.get('motion_cues', [])) or 'n/a'}")
    design_memory = profile.get('design_memory') or {}
    if design_memory:
        lines += [
            '', '## Parsed design memory',
            f"- Source dir: {design_memory.get('source_dir', 'n/a') or 'n/a'}",
            f"- Files present: {', '.join(design_memory.get('files_present', [])) or 'n/a'}",
            f"- Principles: {sentence_join(design_memory.get('principles', [])[:6]) or 'n/a'}",
            f"- Components: {sentence_join(design_memory.get('components', [])[:6]) or 'n/a'}",
            f"- Layout cues: {sentence_join(design_memory.get('layout', [])[:6]) or 'n/a'}",
            f"- Motion cues: {sentence_join(design_memory.get('motion', [])[:6]) or 'n/a'}",
            f"- Typography cues: {sentence_join(design_memory.get('typography_scale', [])[:6]) or 'n/a'}",
            f"- Breakpoints: {sentence_join(design_memory.get('breakpoints', [])[:6]) or 'n/a'}",
        ]
    tokens = profile.get('design_tokens') or {}
    if tokens:
        lines += [
            '', '## Imported design tokens',
            f"- Source file: {tokens.get('source_file', 'n/a')}",
            f"- Source URL: {tokens.get('source_url', 'n/a') or 'n/a'}",
            f"- Extracted at: {tokens.get('extracted_at', 'n/a') or 'n/a'}",
            f"- Palette entries: {len(tokens.get('colors', {}).get('palette', []))}",
            f"- Typography styles: {len(tokens.get('typography', {}).get('styles', []))}",
            f"- Spacing values: {len(tokens.get('spacing', {}).get('common_values', []))}",
            f"- Shadow examples: {len(tokens.get('shadows', []))}",
            f"- Breakpoints: {len(tokens.get('breakpoints', []))}",
            f"- Frameworks: {', '.join(item.get('name', '') for item in tokens.get('frameworks', []) if isinstance(item, dict)) or 'n/a'}",
        ]
    if profile.get('notes_excerpt'):
        lines += ['', '## Notes excerpt', profile['notes_excerpt']]
    lines.append('')
    return '\n'.join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description='Extract a structured brand profile with optional imported design tokens')
    parser.add_argument('--project-root', default='.', help='Project root to inspect')
    parser.add_argument('--brand-name', help='Explicit brand name override')
    parser.add_argument('--homepage-url', help='Homepage or product URL')
    parser.add_argument('--notes-file', help='Optional notes/brief file to include')
    parser.add_argument('--reference-dir', help='Optional reference asset directory')
    parser.add_argument('--design-tokens-json', help='Optional dembrandt-style extracted design tokens JSON to merge into the profile')
    parser.add_argument('--design-memory-path', help='Optional .design-memory folder or project root containing one; defaults to <project-root>/.design-memory when present')
    parser.add_argument('--output-json', required=True, help='Output profile JSON path')
    parser.add_argument('--output-markdown', required=True, help='Output profile markdown path')
    args = parser.parse_args()

    project_root = Path(args.project_root).expanduser().resolve()
    notes_text = read_text(Path(args.notes_file).expanduser()) if args.notes_file else ''
    reference_dir = Path(args.reference_dir).expanduser() if args.reference_dir else None
    design_tokens_json = Path(args.design_tokens_json).expanduser().resolve() if args.design_tokens_json else None
    design_memory_path = Path(args.design_memory_path).expanduser().resolve() if args.design_memory_path else None

    profile = extract_profile(project_root, args.brand_name, args.homepage_url, notes_text, reference_dir, design_tokens_json, design_memory_path)
    output_json = Path(args.output_json).expanduser().resolve()
    output_markdown = Path(args.output_markdown).expanduser().resolve()
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_markdown.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(profile, indent=2) + '\n')
    output_markdown.write_text(to_markdown(profile))

    print(f'Brand profile JSON: {output_json}')
    print(f'Brand profile markdown: {output_markdown}')
    print(f"Brand: {profile['brand_name']}")
    if profile.get('color_candidates'):
        print(f"Top colors: {', '.join(profile['color_candidates'][:5])}")
    if profile.get('font_candidates'):
        print(f"Fonts: {', '.join(profile['font_candidates'][:5])}")
    if profile.get('design_tokens'):
        print(f"Imported design tokens: {profile['design_tokens'].get('source_file', 'n/a')}")
    if profile.get('design_memory', {}).get('source_dir'):
        print(f"Parsed design memory: {profile['design_memory'].get('source_dir')}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
