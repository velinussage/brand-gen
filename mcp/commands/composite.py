"""Composite illustration command.

Builds feature-highlight browser illustrations by compositing multiple layers
with Pillow rather than relying on a single image model to do everything.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Sequence

from PIL import Image, ImageDraw, ImageFilter, ImageFont

# ---------------------------------------------------------------------------
# Brand defaults
# ---------------------------------------------------------------------------
BRAND_CREAM = (244, 235, 217)          # #f4ebd9
BRAND_CHARCOAL = (43, 45, 47)          # #2b2d2f
BRAND_TEXT_DARK = (42, 35, 26)          # #2a231a
BRAND_TERRACOTTA = (198, 123, 92)      # #c67b5c
BRAND_BORDER = (230, 216, 198)         # #e6d8c6
BRAND_SHADOW_COLOR = (0, 0, 0, 38)     # rgba(0,0,0,0.15)

ASPECT_RATIOS: dict[str, tuple[int, int]] = {
    "16:9": (1920, 1080),
    "4:3":  (1600, 1200),
    "1:1":  (1200, 1200),
    "21:9": (2520, 1080),
}

DEFAULT_LOGO_REL = "brand-materials/logo.png"

# ---------------------------------------------------------------------------
# Font helpers
# ---------------------------------------------------------------------------
_INTER_SEARCH_PATHS: Sequence[str] = (
    "/System/Library/Fonts/Supplemental/Inter.ttc",
    "/System/Library/Fonts/Inter.ttc",
    "/usr/share/fonts/truetype/inter/Inter-Bold.ttf",
    "/usr/share/fonts/truetype/inter/Inter-Regular.ttf",
    str(Path.home() / "Library/Fonts/Inter-Bold.ttf"),
    str(Path.home() / "Library/Fonts/Inter-Regular.ttf"),
    str(Path.home() / ".local/share/fonts/Inter-Bold.ttf"),
)


def _load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Try loading Inter; fall back to Pillow default."""
    for path in _INTER_SEARCH_PATHS:
        p = Path(path)
        if p.exists():
            try:
                return ImageFont.truetype(str(p), size)
            except Exception:
                continue
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


# ---------------------------------------------------------------------------
# Layer helpers
# ---------------------------------------------------------------------------

def _create_background(
    canvas_w: int,
    canvas_h: int,
    pattern_path: str | None = None,
    dark: bool = False,
) -> Image.Image:
    """Solid colour or tiled pattern background."""
    bg_color = BRAND_CHARCOAL if dark else BRAND_CREAM
    bg = Image.new("RGBA", (canvas_w, canvas_h), bg_color + (255,))

    if pattern_path:
        pat_file = Path(pattern_path)
        if pat_file.is_file():
            pat = Image.open(pat_file).convert("RGBA")
            for y in range(0, canvas_h, pat.height):
                for x in range(0, canvas_w, pat.width):
                    bg.paste(pat, (x, y), pat)
    return bg


def _round_corners(img: Image.Image, radius: int) -> Image.Image:
    """Return *img* with rounded corners via an alpha mask."""
    mask = Image.new("L", img.size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle([(0, 0), img.size], radius=radius, fill=255)
    out = img.copy()
    out.putalpha(mask)
    return out


def _add_drop_shadow(
    img: Image.Image,
    offset: tuple[int, int] = (0, 8),
    blur_radius: int = 24,
    shadow_color: tuple[int, int, int, int] = BRAND_SHADOW_COLOR,
) -> Image.Image:
    """Return a new RGBA image that is *img* composited over a blurred shadow."""
    pad = blur_radius * 2
    total_w = img.width + pad * 2
    total_h = img.height + pad * 2

    shadow = Image.new("RGBA", (total_w, total_h), (0, 0, 0, 0))
    shadow_rect = Image.new("RGBA", img.size, shadow_color)
    sx = pad + offset[0]
    sy = pad + offset[1]
    shadow.paste(shadow_rect, (sx, sy))
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=blur_radius))

    shadow.paste(img, (pad, pad), img)
    return shadow


def _place_screenshot(
    canvas: Image.Image,
    screenshot_path: str,
    scale_fraction: float = 0.70,
    corner_radius: int = 12,
    border_width: int = 1,
    border_color: tuple[int, int, int, int] = BRAND_BORDER + (255,),
    vertical_offset: int = 0,
) -> Image.Image:
    """Scale, round, shadow, and center the screenshot on *canvas*."""
    shot = Image.open(screenshot_path).convert("RGBA")

    target_w = int(canvas.width * scale_fraction)
    aspect = shot.height / shot.width
    target_h = int(target_w * aspect)
    shot = shot.resize((target_w, target_h), Image.LANCZOS)

    # Draw thin border onto the shot before rounding
    if border_width > 0:
        draw = ImageDraw.Draw(shot)
        draw.rounded_rectangle(
            [(0, 0), (shot.width - 1, shot.height - 1)],
            radius=corner_radius,
            outline=border_color,
            width=border_width,
        )

    shot = _round_corners(shot, corner_radius)
    shot_with_shadow = _add_drop_shadow(shot)

    cx = (canvas.width - shot_with_shadow.width) // 2
    cy = (canvas.height - shot_with_shadow.height) // 2 + vertical_offset
    canvas.paste(shot_with_shadow, (cx, cy), shot_with_shadow)
    return canvas


def _add_highlight(
    canvas: Image.Image,
    region: tuple[int, int, int, int],
    color: tuple[int, int, int] = BRAND_TERRACOTTA,
    opacity: int = 51,  # ~20%
    border_width: int = 2,
) -> Image.Image:
    """Draw a semi-transparent highlight rectangle on *canvas*."""
    overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    x, y, w, h = region
    fill = color + (opacity,)
    outline = color + (200,)
    draw.rectangle([(x, y), (x + w, y + h)], fill=fill, outline=outline, width=border_width)
    return Image.alpha_composite(canvas, overlay)


def _render_text(
    canvas: Image.Image,
    headline: str | None = None,
    subhead: str | None = None,
    text_color: tuple[int, int, int] = BRAND_TEXT_DARK,
    margin_top: int = 60,
) -> Image.Image:
    """Draw headline and optional subhead at the top-center of *canvas*."""
    overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    y_cursor = margin_top

    if headline:
        font_h = _load_font(48, bold=True)
        bbox = draw.textbbox((0, 0), headline, font=font_h)
        tw = bbox[2] - bbox[0]
        tx = (canvas.width - tw) // 2
        draw.text((tx, y_cursor), headline, fill=text_color + (255,), font=font_h)
        y_cursor += (bbox[3] - bbox[1]) + 16

    if subhead:
        font_s = _load_font(28)
        bbox = draw.textbbox((0, 0), subhead, font=font_s)
        tw = bbox[2] - bbox[0]
        tx = (canvas.width - tw) // 2
        draw.text((tx, y_cursor), subhead, fill=text_color + (180,), font=font_s)

    return Image.alpha_composite(canvas, overlay)


def _place_logo(
    canvas: Image.Image,
    logo_path: str | None = None,
    max_size: int = 48,
    margin: int = 24,
) -> Image.Image:
    """Place a small brand logo in the bottom-right corner."""
    if logo_path is None:
        # Try default relative to project root
        candidate = Path(__file__).resolve().parents[2] / DEFAULT_LOGO_REL
        if candidate.is_file():
            logo_path = str(candidate)
        else:
            return canvas

    p = Path(logo_path)
    if not p.is_file():
        return canvas

    logo = Image.open(p).convert("RGBA")
    aspect = logo.height / logo.width
    new_w = max_size
    new_h = int(max_size * aspect)
    logo = logo.resize((new_w, new_h), Image.LANCZOS)

    x = canvas.width - new_w - margin
    y = canvas.height - new_h - margin
    canvas.paste(logo, (x, y), logo)
    return canvas


# ---------------------------------------------------------------------------
# Public command handler
# ---------------------------------------------------------------------------

def cmd_composite_illustration(args) -> None:
    """Entry point for ``bgen composite-illustration``."""
    screenshot: str = args.screenshot
    if not Path(screenshot).is_file():
        print(f"ERROR: screenshot not found: {screenshot}", file=sys.stderr)
        sys.exit(1)

    aspect_key: str = getattr(args, "aspect_ratio", "16:9") or "16:9"
    canvas_w, canvas_h = ASPECT_RATIOS.get(aspect_key, ASPECT_RATIOS["16:9"])

    headline: str | None = getattr(args, "headline", None)
    subhead: str | None = getattr(args, "subhead", None)
    feature: str | None = getattr(args, "feature", None)
    pattern: str | None = getattr(args, "pattern", None)
    logo: str | None = getattr(args, "logo", None)
    output: str = getattr(args, "output", None) or "composite-illustration.png"

    highlight_raw: str | None = getattr(args, "highlight_region", None)
    highlight_region: tuple[int, int, int, int] | None = None
    if highlight_raw:
        try:
            parts = [int(v.strip()) for v in highlight_raw.split(",")]
            if len(parts) != 4:
                raise ValueError("expected 4 comma-separated ints")
            highlight_region = (parts[0], parts[1], parts[2], parts[3])
        except Exception as exc:
            print(f"ERROR: invalid --highlight-region: {exc}", file=sys.stderr)
            sys.exit(1)

    dark = getattr(args, "dark", False)

    # If no explicit headline but feature text supplied, use feature as headline
    effective_headline = headline or feature

    # --- Compositing pipeline ---
    text_space = 140 if effective_headline else 0
    canvas = _create_background(canvas_w, canvas_h, pattern, dark=dark)
    canvas = _render_text(canvas, headline=effective_headline, subhead=subhead)
    canvas = _place_screenshot(canvas, screenshot, vertical_offset=text_space // 2)

    if highlight_region:
        canvas = _add_highlight(canvas, highlight_region)

    canvas = _place_logo(canvas, logo)

    # --- Save ---
    out_path = Path(output).expanduser().resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(str(out_path), "PNG")
    print(f"Composite illustration saved: {out_path}")
