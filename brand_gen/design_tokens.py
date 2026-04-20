"""Design-token generation — math-based type scale, palette scale, WCAG,
dark-mode derivation, and platform exports (CSS, Tailwind, W3C DTCG JSON).

Source material distilled into
`skills/brand-gen/references/design-tokens.md`:

- dylanfeltus/skills/design-tokens (math + algorithms)
- pbc-os/agent-skills-public/tier-4-growth/brand-identity (W3C structure, exports)
- anthropics/skills/brand-guidelines (font fallback chain)

Pure stdlib. No external deps. Callable directly from
`brand_gen/commands/export_design_tokens.py` and in-process from the
HTML share-card renderer.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from typing import Iterable


# ── §2 Type scale ────────────────────────────────────────────────────────

DEFAULT_TYPE_RATIO = 1.200  # Minor Third — good general-purpose default
DEFAULT_BASE_SIZE_PX = 16
TYPE_STEP_LABELS = ["xs", "sm", "base", "lg", "xl", "2xl", "3xl", "4xl", "5xl"]
TYPE_STEP_INDICES = [-2, -1, 0, 1, 2, 3, 4, 5, 6]


def type_scale(base_px: float = DEFAULT_BASE_SIZE_PX, ratio: float = DEFAULT_TYPE_RATIO) -> dict:
    out = {}
    for label, step in zip(TYPE_STEP_LABELS, TYPE_STEP_INDICES):
        px = base_px * (ratio ** step)
        out[label] = {
            "px": round(px, 2),
            "rem": round(px / 16, 4),
            "line_height": _line_height_for(px),
            "letter_spacing_em": _letter_spacing_for(px),
        }
    return out


def _line_height_for(px: float) -> float:
    if px <= 14:
        return 1.65
    if px <= 20:
        return 1.5
    if px <= 32:
        return 1.35
    if px <= 48:
        return 1.15
    return 1.05


def _letter_spacing_for(px: float) -> float:
    if px <= 14:
        return 0.015
    if px <= 18:
        return 0.0
    if px <= 24:
        return -0.01
    if px <= 48:
        return -0.025
    return -0.04


# ── §3 Color palette scale ───────────────────────────────────────────────

# step → (lightness Δ, saturation Δ) from the base (step 500)
_SHADE_OFFSETS = {
    50:  (+45, -30),
    100: (+38, -25),
    200: (+28, -15),
    300: (+18, -5),
    400: (+8, 0),
    500: (0, 0),
    600: (-8, +5),
    700: (-18, +5),
    800: (-28, 0),
    900: (-38, -10),
    950: (-45, -20),
}


def hex_to_rgb(hex_str: str) -> tuple[int, int, int]:
    s = hex_str.lstrip("#").strip()
    if len(s) == 3:
        s = "".join(c * 2 for c in s)
    if len(s) != 6:
        raise ValueError(f"invalid hex color: {hex_str!r}")
    return int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)


def rgb_to_hex(r: int, g: int, b: int) -> str:
    return "#{:02x}{:02x}{:02x}".format(
        max(0, min(255, int(round(r)))),
        max(0, min(255, int(round(g)))),
        max(0, min(255, int(round(b)))),
    )


def rgb_to_hsl(r: int, g: int, b: int) -> tuple[float, float, float]:
    rf, gf, bf = r / 255, g / 255, b / 255
    cmax, cmin = max(rf, gf, bf), min(rf, gf, bf)
    l = (cmax + cmin) / 2
    d = cmax - cmin
    if d == 0:
        return 0.0, 0.0, l * 100
    s = d / (1 - abs(2 * l - 1)) if l not in (0, 1) else 0
    if cmax == rf:
        h = ((gf - bf) / d) % 6
    elif cmax == gf:
        h = ((bf - rf) / d) + 2
    else:
        h = ((rf - gf) / d) + 4
    return (h * 60) % 360, s * 100, l * 100


def hsl_to_rgb(h: float, s: float, l: float) -> tuple[int, int, int]:
    s /= 100
    l /= 100
    c = (1 - abs(2 * l - 1)) * s
    x = c * (1 - abs(((h / 60) % 2) - 1))
    m = l - c / 2
    if 0 <= h < 60:
        rp, gp, bp = c, x, 0
    elif 60 <= h < 120:
        rp, gp, bp = x, c, 0
    elif 120 <= h < 180:
        rp, gp, bp = 0, c, x
    elif 180 <= h < 240:
        rp, gp, bp = 0, x, c
    elif 240 <= h < 300:
        rp, gp, bp = x, 0, c
    else:
        rp, gp, bp = c, 0, x
    return (
        int(round((rp + m) * 255)),
        int(round((gp + m) * 255)),
        int(round((bp + m) * 255)),
    )


def palette_scale_from_hex(base_hex: str) -> dict[int, str]:
    """Return {50..950 -> '#hex'} shade scale for a single base color."""
    h, s, l = rgb_to_hsl(*hex_to_rgb(base_hex))
    out: dict[int, str] = {}
    for step, (dl, ds) in _SHADE_OFFSETS.items():
        new_l = max(0.0, min(100.0, l + dl))
        new_s = max(0.0, min(100.0, s + ds))
        out[step] = rgb_to_hex(*hsl_to_rgb(h, new_s, new_l))
    return out


# ── §4 WCAG contrast ─────────────────────────────────────────────────────

def relative_luminance(hex_or_rgb) -> float:
    r, g, b = hex_to_rgb(hex_or_rgb) if isinstance(hex_or_rgb, str) else hex_or_rgb

    def chan(c: int) -> float:
        srgb = c / 255
        return srgb / 12.92 if srgb <= 0.03928 else ((srgb + 0.055) / 1.055) ** 2.4

    return 0.2126 * chan(r) + 0.7152 * chan(g) + 0.0722 * chan(b)


def wcag_contrast_ratio(fg, bg) -> float:
    l1 = relative_luminance(fg)
    l2 = relative_luminance(bg)
    lighter, darker = (l1, l2) if l1 >= l2 else (l2, l1)
    return round((lighter + 0.05) / (darker + 0.05), 3)


WCAG_THRESHOLDS = {
    ("AA", "normal"): 4.5,
    ("AA", "large"): 3.0,
    ("AA", "ui"): 3.0,
    ("AAA", "normal"): 7.0,
    ("AAA", "large"): 4.5,
}


def wcag_check(fg, bg, level: str = "AA", size: str = "normal") -> bool:
    threshold = WCAG_THRESHOLDS.get((level, size), 4.5)
    return wcag_contrast_ratio(fg, bg) >= threshold


@dataclass
class AuditResult:
    ok: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    checks: list[dict] = field(default_factory=list)

    def report(self) -> str:
        lines: list[str] = []
        for item in self.checks:
            lines.append(
                f"  {item['name']}: {item['fg']} on {item['bg']} = "
                f"{item['ratio']:.2f}:1 [{item['verdict']}]"
            )
        if self.errors:
            lines.append("ERRORS:")
            lines.extend(f"  {e}" for e in self.errors)
        if self.warnings:
            lines.append("WARNINGS:")
            lines.extend(f"  {w}" for w in self.warnings)
        return "\n".join(lines)


def wcag_audit(tokens: dict) -> AuditResult:
    """Run the five checks listed in §11 of the reference."""
    errors: list[str] = []
    warnings: list[str] = []
    checks: list[dict] = []

    neutral = (tokens.get("color") or {}).get("neutral") or {}
    primary = (tokens.get("color") or {}).get("primary") or {}
    semantic = (tokens.get("color") or {}).get("semantic") or {}

    def _check(name: str, fg: str, bg: str, level: str, size: str, severity: str) -> None:
        if not fg or not bg:
            return
        ratio = wcag_contrast_ratio(fg, bg)
        threshold = WCAG_THRESHOLDS[(level, size)]
        verdict = "pass" if ratio >= threshold else "fail"
        checks.append(
            {"name": name, "fg": fg, "bg": bg, "ratio": ratio,
             "threshold": threshold, "level": level, "size": size, "verdict": verdict}
        )
        if verdict == "fail":
            msg = f"{name}: ratio {ratio:.2f}:1 < {threshold} ({level} {size})"
            (errors if severity == "error" else warnings).append(msg)

    _check("text on bg", neutral.get(900), neutral.get(50), "AA", "normal", "error")
    _check("text-muted on bg", neutral.get(500), neutral.get(50), "AA", "normal", "error")
    _check("primary on white", primary.get(600), "#ffffff", "AA", "normal", "warning")
    _check("primary-button-text on primary",
           semantic.get("primary-text") or "#ffffff", primary.get(600),
           "AA", "normal", "error")
    _check("border on bg", neutral.get(200), neutral.get(50), "AA", "ui", "warning")

    return AuditResult(ok=not errors, errors=errors, warnings=warnings, checks=checks)


# ── §5 Dark-mode derivation ──────────────────────────────────────────────

_DARK_MODE_FLIPS = {
    "bg": ("neutral", 950),
    "bg-subtle": ("neutral", 900),
    "bg-muted": ("neutral", 800),
    "border": ("neutral", 800),
    "border-strong": ("neutral", 700),
    "text-muted": ("neutral", 400),
    "text-subtle": ("neutral", 300),
    "text": ("neutral", 50),
    "text-heading": ("neutral", 50),
    "primary": ("primary", 400),
    "primary-hover": ("primary", 300),
    "primary-bg": ("primary", 900),
    "primary-text": ("neutral", 950),
}


def derive_dark_semantic(tokens: dict) -> dict[str, str]:
    colors = tokens.get("color") or {}
    out: dict[str, str] = {}
    for key, (group, step) in _DARK_MODE_FLIPS.items():
        shade = (colors.get(group) or {}).get(step)
        if shade:
            out[key] = shade
    return out


# ── §6 Spacing / §7 Radii / Motion / Breakpoints ─────────────────────────

SPACING_STEPS = [0, 0.5, 1, 1.5, 2, 3, 4, 5, 6, 8, 10, 12, 16, 20, 24, 32, 40, 48, 64, 80, 96]

RADII = {"none": 0, "sm": 4, "md": 8, "lg": 12, "xl": 16, "2xl": 24, "full": 9999}

ELEVATION = {
    "sm": "0 1px 2px rgba({r}, {g}, {b}, 0.05)",
    "md": "0 4px 6px rgba({r}, {g}, {b}, 0.08)",
    "lg": "0 10px 20px rgba({r}, {g}, {b}, 0.10)",
    "xl": "0 20px 40px rgba({r}, {g}, {b}, 0.12)",
    "2xl": "0 30px 60px rgba({r}, {g}, {b}, 0.15)",
    "inner": "inset 0 2px 4px rgba({r}, {g}, {b}, 0.06)",
}

MOTION = {
    "duration": {"micro": 100, "short": 150, "medium": 250, "long": 400, "xlong": 600, "ambient": 1200},
    "easing": {
        "default": [0.4, 0.0, 0.2, 1.0],
        "entrance": [0.0, 0.0, 0.2, 1.0],
        "exit": [0.4, 0.0, 1.0, 1.0],
        "emphasis": [0.4, 0.0, 0.6, 1.0],
    },
}

BREAKPOINTS = {"sm": 640, "md": 768, "lg": 1024, "xl": 1280, "2xl": 1536}


# ── Font fallback chain (anthropics pattern) ─────────────────────────────

DEFAULT_FONT_FALLBACKS = {
    "display": ["Arial", "Helvetica", "sans-serif"],
    "body": ["Georgia", "Times New Roman", "serif"],
    "mono": ["Menlo", "Consolas", "monospace"],
}


def build_font_family(name: str, role: str) -> str:
    fallback = DEFAULT_FONT_FALLBACKS.get(role, ["sans-serif"])
    if not name or not name.strip():
        return ", ".join(fallback)
    return ", ".join([f'"{name}"'] + fallback)


# ── Top-level token builder ──────────────────────────────────────────────

def build_tokens(identity: dict) -> dict:
    """Map brand-gen's identity.json shape → complete tokens dict (§10)."""
    brand_colors = identity.get("brand_colors") or {}
    typography = identity.get("typography") or {}
    layout = identity.get("layout") or {}

    primary_hex = (brand_colors.get("primary") or "").strip()
    secondary_hex = (brand_colors.get("secondary") or "").strip()
    accents = [str(c).strip() for c in (brand_colors.get("accents") or []) if str(c).strip()]
    neutral_hex = (brand_colors.get("neutral") or "").strip() or _derive_warm_neutral(primary_hex)

    color: dict = {}
    if primary_hex:
        color["primary"] = palette_scale_from_hex(primary_hex)
    if secondary_hex:
        color["secondary"] = palette_scale_from_hex(secondary_hex)
    for i, acc in enumerate(accents[:4], start=1):
        color[f"accent-{i}"] = palette_scale_from_hex(acc)
    color["neutral"] = palette_scale_from_hex(neutral_hex) if neutral_hex else {}

    # Semantic (light mode)
    primary_scale = color.get("primary") or {}
    neutral_scale = color.get("neutral") or {}
    semantic = {
        "bg": neutral_scale.get(50, "#ffffff"),
        "bg-subtle": neutral_scale.get(100, "#f5f5f5"),
        "bg-muted": neutral_scale.get(200, "#e5e5e5"),
        "border": neutral_scale.get(200, "#e5e5e5"),
        "border-strong": neutral_scale.get(300, "#d4d4d4"),
        "text-muted": neutral_scale.get(500, "#737373"),
        "text-subtle": neutral_scale.get(600, "#525252"),
        "text": neutral_scale.get(900, "#171717"),
        "text-heading": neutral_scale.get(950, "#0a0a0a"),
        "primary": primary_scale.get(600, primary_hex or "#000000"),
        "primary-hover": primary_scale.get(700, primary_hex or "#000000"),
        "primary-bg": primary_scale.get(50, "#ffffff"),
        "primary-text": "#ffffff",
    }
    color["semantic"] = semantic

    # Shadow color tied to the neutral 950
    neutral_deep = neutral_scale.get(950, "#0a0a0a")
    sr, sg, sb = hex_to_rgb(neutral_deep)
    elevation = {k: tpl.format(r=sr, g=sg, b=sb) for k, tpl in ELEVATION.items()}

    # Typography
    type_ratio = float(typography.get("type_scale_ratio") or DEFAULT_TYPE_RATIO)
    base_size = float(typography.get("base_size_px") or DEFAULT_BASE_SIZE_PX)
    type_groups = {
        "display": build_font_family(typography.get("headings") or "", "display"),
        "body": build_font_family(typography.get("body") or "", "body"),
        "mono": build_font_family(typography.get("mono") or "", "mono"),
    }

    # Dark mode semantic (derived)
    color["semantic-dark"] = _build_dark_semantic(color)

    return {
        "color": color,
        "typography": {
            "fontFamily": type_groups,
            "fontWeight": {"body": 400, "emphasis": 500, "subheading": 600, "heading": 700, "display": 800},
            "fontSize": type_scale(base_size, type_ratio),
            "ratio": type_ratio,
            "base_px": base_size,
        },
        "spacing": {_spacing_key(s): {"px": s * 4, "rem": (s * 4) / 16} for s in SPACING_STEPS},
        "elevation": elevation,
        "radii": {k: {"px": v, "rem": v / 16} for k, v in RADII.items()},
        "motion": MOTION,
        "breakpoints": {k: {"px": v} for k, v in BREAKPOINTS.items()},
    }


def _spacing_key(value: float) -> str:
    if value == int(value):
        return str(int(value))
    return str(value)


def _derive_warm_neutral(primary_hex: str) -> str:
    """If no neutral is provided, derive a warm grey that feels related to the
    primary color — 5% saturation at 50% lightness."""
    if not primary_hex:
        return "#737373"  # neutral-500 equivalent
    try:
        h, _, _ = rgb_to_hsl(*hex_to_rgb(primary_hex))
    except ValueError:
        return "#737373"
    return rgb_to_hex(*hsl_to_rgb(h, 5, 50))


def _build_dark_semantic(color: dict) -> dict:
    neutral = color.get("neutral") or {}
    primary = color.get("primary") or {}
    return {
        "bg": neutral.get(950, "#0a0a0a"),
        "bg-subtle": neutral.get(900, "#171717"),
        "bg-muted": neutral.get(800, "#262626"),
        "border": neutral.get(800, "#262626"),
        "border-strong": neutral.get(700, "#404040"),
        "text-muted": neutral.get(400, "#a3a3a3"),
        "text-subtle": neutral.get(300, "#d4d4d4"),
        "text": neutral.get(50, "#fafafa"),
        "text-heading": neutral.get(50, "#fafafa"),
        "primary": primary.get(400, ""),
        "primary-hover": primary.get(300, ""),
        "primary-bg": primary.get(900, ""),
        "primary-text": neutral.get(950, "#0a0a0a"),
    }


# ── Exports ──────────────────────────────────────────────────────────────

def emit_css_variables(tokens: dict, *, include_dark_mode: bool = True) -> str:
    lines: list[str] = [":root {"]
    for group_name, scale in (tokens.get("color") or {}).items():
        if group_name in ("semantic", "semantic-dark"):
            continue
        if not isinstance(scale, dict):
            continue
        for step, hex_value in scale.items():
            lines.append(f"  --color-{group_name}-{step}: {hex_value};")
    semantic = (tokens.get("color") or {}).get("semantic") or {}
    for name, value in semantic.items():
        lines.append(f"  --color-{name}: {value};")
    for label, entry in (tokens.get("typography") or {}).get("fontSize", {}).items():
        lines.append(f"  --font-size-{label}: {entry['rem']}rem;")
        lines.append(f"  --line-height-{label}: {entry['line_height']};")
    for role, family in (tokens.get("typography") or {}).get("fontFamily", {}).items():
        lines.append(f"  --font-family-{role}: {family};")
    for key, entry in (tokens.get("spacing") or {}).items():
        lines.append(f"  --space-{key}: {entry['rem']}rem;")
    for key, entry in (tokens.get("radii") or {}).items():
        lines.append(f"  --radius-{key}: {entry['rem']}rem;")
    for key, shadow in (tokens.get("elevation") or {}).items():
        lines.append(f"  --shadow-{key}: {shadow};")
    for key, duration in (tokens.get("motion") or {}).get("duration", {}).items():
        lines.append(f"  --duration-{key}: {duration}ms;")
    for key, curve in (tokens.get("motion") or {}).get("easing", {}).items():
        lines.append(f"  --easing-{key}: cubic-bezier({', '.join(str(x) for x in curve)});")
    for key, entry in (tokens.get("breakpoints") or {}).items():
        lines.append(f"  --breakpoint-{key}: {entry['px']}px;")
    lines.append("}")

    if include_dark_mode and (tokens.get("color") or {}).get("semantic-dark"):
        lines.append("")
        lines.append("@media (prefers-color-scheme: dark) {")
        lines.append("  :root {")
        for name, value in tokens["color"]["semantic-dark"].items():
            if value:
                lines.append(f"    --color-{name}: {value};")
        lines.append("  }")
        lines.append("}")

    return "\n".join(lines) + "\n"


def emit_tailwind_config(tokens: dict) -> str:
    data = {
        "theme": {
            "extend": {
                "colors": _tailwind_colors(tokens),
                "fontSize": {k: v["rem"] for k, v in (tokens.get("typography") or {}).get("fontSize", {}).items()},
                "fontFamily": {k: _family_to_list(v) for k, v in (tokens.get("typography") or {}).get("fontFamily", {}).items()},
                "spacing": {k: f"{v['rem']}rem" for k, v in (tokens.get("spacing") or {}).items()},
                "borderRadius": {k: f"{v['rem']}rem" for k, v in (tokens.get("radii") or {}).items()},
                "boxShadow": tokens.get("elevation") or {},
                "screens": {k: f"{v['px']}px" for k, v in (tokens.get("breakpoints") or {}).items()},
            }
        }
    }
    return "module.exports = " + json.dumps(data, indent=2) + ";\n"


def _tailwind_colors(tokens: dict) -> dict:
    out: dict = {}
    for group_name, scale in (tokens.get("color") or {}).items():
        if group_name in ("semantic", "semantic-dark"):
            continue
        if isinstance(scale, dict) and scale:
            out[group_name] = {str(step): value for step, value in scale.items()}
    return out


def _family_to_list(family: str) -> list[str]:
    return [p.strip().strip('"') for p in family.split(",") if p.strip()]


def emit_json_tokens(tokens: dict) -> str:
    return json.dumps(tokens, indent=2) + "\n"


def emit_w3c_tokens(tokens: dict) -> str:
    """W3C DTCG format with $value / $type / $description fields."""
    out: dict = {}

    color_group: dict = {}
    for group_name, scale in (tokens.get("color") or {}).items():
        if group_name in ("semantic", "semantic-dark"):
            continue
        if not isinstance(scale, dict):
            continue
        color_group[group_name] = {
            str(step): {"$value": value, "$type": "color"}
            for step, value in scale.items()
        }
    semantic = (tokens.get("color") or {}).get("semantic") or {}
    color_group["semantic"] = {
        name: {"$value": value, "$type": "color"}
        for name, value in semantic.items()
    }
    out["color"] = color_group

    out["fontFamily"] = {
        role: {"$value": family, "$type": "fontFamily"}
        for role, family in (tokens.get("typography") or {}).get("fontFamily", {}).items()
    }
    out["fontSize"] = {
        label: {"$value": f"{entry['rem']}rem", "$type": "dimension"}
        for label, entry in (tokens.get("typography") or {}).get("fontSize", {}).items()
    }
    out["spacing"] = {
        key: {"$value": f"{entry['rem']}rem", "$type": "dimension"}
        for key, entry in (tokens.get("spacing") or {}).items()
    }
    out["borderRadius"] = {
        key: {"$value": f"{entry['rem']}rem", "$type": "dimension"}
        for key, entry in (tokens.get("radii") or {}).items()
    }
    out["shadow"] = {
        key: {"$value": shadow, "$type": "shadow"}
        for key, shadow in (tokens.get("elevation") or {}).items()
    }
    out["duration"] = {
        key: {"$value": f"{duration}ms", "$type": "duration"}
        for key, duration in (tokens.get("motion") or {}).get("duration", {}).items()
    }
    out["breakpoint"] = {
        key: {"$value": f"{entry['px']}px", "$type": "dimension"}
        for key, entry in (tokens.get("breakpoints") or {}).items()
    }

    return json.dumps(out, indent=2) + "\n"


EXPORTERS = {
    "css": emit_css_variables,
    "tailwind": emit_tailwind_config,
    "json": emit_json_tokens,
    "w3c": emit_w3c_tokens,
}


def emit(tokens: dict, fmt: str) -> str:
    fmt_key = fmt.strip().lower()
    if fmt_key not in EXPORTERS:
        raise ValueError(f"unknown format: {fmt!r} (known: {sorted(EXPORTERS)})")
    return EXPORTERS[fmt_key](tokens)
