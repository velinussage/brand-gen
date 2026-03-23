#!/usr/bin/env python3
"""Compose a deterministic square social card from a real product screenshot."""
from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps


BG = "#f2ddc3"
CARD = "#fbf7f1"
INK = "#241c14"
MUTED = "#6c6257"
ACCENT = "#a24916"
BORDER = "#eadfce"
GREEN_BG = "#e6efdf"
GREEN_TXT = "#58704f"

FONT_CANDIDATES = {
    "serif_bold": [
        "/System/Library/Fonts/Supplemental/Georgia Bold.ttf",
        "/Library/Fonts/Georgia Bold.ttf",
    ],
    "sans": [
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/Library/Fonts/Arial.ttf",
    ],
    "sans_bold": [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/Library/Fonts/Arial Bold.ttf",
    ],
}


def load_font(kind: str, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for candidate in FONT_CANDIDATES[kind]:
        path = Path(candidate)
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def rounded_mask(size: tuple[int, int], radius: int) -> Image.Image:
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle((0, 0, size[0], size[1]), radius=radius, fill=255)
    return mask


def add_shadow(base: Image.Image, box: tuple[int, int, int, int], radius: int = 24) -> None:
    shadow = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(shadow)
    x0, y0, x1, y1 = box
    draw.rounded_rectangle((x0 + 6, y0 + 10, x1 + 6, y1 + 10), radius=radius, fill=(52, 32, 16, 28))
    shadow = shadow.filter(ImageFilter.GaussianBlur(18))
    base.alpha_composite(shadow)


def draw_pill(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    text: str,
    font: ImageFont.ImageFont,
    fill: str,
    text_fill: str,
    pad_x: int = 18,
    pad_y: int = 10,
    radius: int = 18,
) -> tuple[int, int, int, int]:
    bbox = draw.textbbox((0, 0), text, font=font)
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    rect = (x, y, x + w + pad_x * 2, y + h + pad_y * 2)
    draw.rounded_rectangle(rect, radius=radius, fill=fill)
    draw.text((x + pad_x, y + pad_y - 1), text, font=font, fill=text_fill)
    return rect


def wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_width: int) -> list[str]:
    words = text.split()
    if not words:
        return [""]
    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        if draw.textbbox((0, 0), candidate, font=font)[2] <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def fit_screenshot(path: Path, size: tuple[int, int], radius: int) -> Image.Image:
    shot = Image.open(path).convert("RGB")
    contained = ImageOps.contain(shot, size, method=Image.Resampling.LANCZOS)
    inset = Image.new("RGBA", size, CARD)
    offset = ((size[0] - contained.width) // 2, (size[1] - contained.height) // 2)
    inset.paste(contained, offset)
    inset.putalpha(rounded_mask(size, radius))
    return inset


def build_card(args: argparse.Namespace) -> None:
    canvas = Image.new("RGBA", (args.canvas_size, args.canvas_size), BG)
    card_box = (60, 60, args.canvas_size - 60, args.canvas_size - 60)
    add_shadow(canvas, card_box, radius=38)

    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle(card_box, radius=38, fill=CARD, outline=BORDER, width=2)

    serif = load_font("serif_bold", 70)
    sans = load_font("sans", 30)
    sans_bold = load_font("sans_bold", 28)
    pill_font = load_font("sans_bold", 24)

    left = 110
    top = 108

    if args.logo:
        logo = Image.open(args.logo).convert("RGBA")
        logo.thumbnail((54, 54), Image.Resampling.LANCZOS)
        canvas.alpha_composite(logo, (left, top))
        top += 2

    meta_x = left + (70 if args.logo else 0)
    draw.text((meta_x, top), args.eyebrow.upper(), font=sans_bold, fill=ACCENT)
    draw.text((args.canvas_size - 350, top), args.community, font=sans, fill=MUTED)

    pill_y = top + 52
    pill_end = draw_pill(draw, meta_x, pill_y, args.badge, pill_font, GREEN_BG, GREEN_TXT)

    title_y = pill_y + 74
    max_text_width = args.canvas_size - 2 * left - 40
    title_lines = wrap_text(draw, args.title, serif, max_text_width)
    current_y = title_y
    for line in title_lines[:2]:
        draw.text((left, current_y), line, font=serif, fill=INK)
        current_y += 74

    subtitle_font = load_font("sans", 34)
    subtitle_lines = wrap_text(draw, args.subtitle, subtitle_font, max_text_width)
    current_y += 8
    for line in subtitle_lines[:3]:
        draw.text((left, current_y), line, font=subtitle_font, fill=MUTED)
        current_y += 46

    screenshot_top = max(current_y + 28, pill_end[3] + 190)
    screenshot_left = left
    screenshot_width = args.canvas_size - 2 * left
    screenshot_height = args.canvas_size - screenshot_top - 110
    screenshot = fit_screenshot(Path(args.screenshot), (screenshot_width, screenshot_height), radius=28)
    draw.rounded_rectangle(
        (screenshot_left, screenshot_top, screenshot_left + screenshot_width, screenshot_top + screenshot_height),
        radius=28,
        outline=BORDER,
        width=2,
    )
    canvas.alpha_composite(screenshot, (screenshot_left, screenshot_top))

    footer_y = screenshot_top + screenshot_height - 58
    draw.rounded_rectangle(
        (screenshot_left + 26, footer_y, screenshot_left + 312, footer_y + 34),
        radius=16,
        fill=(251, 247, 241, 220),
    )
    footer_font = load_font("sans_bold", 20)
    draw.text((screenshot_left + 42, footer_y + 6), args.screenshot_label, font=footer_font, fill=INK)

    output = Path(args.output).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(output, quality=95)
    print(output)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compose a deterministic live-share social card.")
    parser.add_argument("--screenshot", required=True, help="Path to the real product screenshot")
    parser.add_argument("--output", required=True, help="Output PNG path")
    parser.add_argument("--title", required=True, help="Short deterministic title")
    parser.add_argument("--subtitle", required=True, help="Short deterministic subtitle")
    parser.add_argument("--community", default="Protocol Community", help="Right-aligned top metadata")
    parser.add_argument("--eyebrow", default="Live update", help="Small top-left label")
    parser.add_argument("--badge", default="Skill", help="Small metadata pill")
    parser.add_argument("--screenshot-label", default="Live product detail", help="Inset footer label")
    parser.add_argument("--logo", help="Optional logo path")
    parser.add_argument("--canvas-size", type=int, default=1200, help="Square canvas size in pixels")
    return parser.parse_args()


def main() -> int:
    build_card(parse_args())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
