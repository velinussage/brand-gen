"""Tests for the composite-illustration command."""
from __future__ import annotations

import argparse
import tempfile
from pathlib import Path

import pytest
from PIL import Image

from brand_gen.commands.composite import (
    ASPECT_RATIOS,
    BRAND_CHARCOAL,
    BRAND_CREAM,
    _add_drop_shadow,
    _add_highlight,
    _create_background,
    _load_font,
    _place_logo,
    _place_screenshot,
    _render_text,
    _round_corners,
    cmd_composite_illustration,
)


@pytest.fixture()
def tmp_screenshot(tmp_path: Path) -> Path:
    """Create a small dummy screenshot PNG."""
    img = Image.new("RGB", (800, 600), (100, 150, 200))
    p = tmp_path / "screenshot.png"
    img.save(str(p))
    return p


@pytest.fixture()
def tmp_logo(tmp_path: Path) -> Path:
    """Create a small dummy logo PNG."""
    img = Image.new("RGBA", (64, 64), (255, 0, 0, 255))
    p = tmp_path / "logo.png"
    img.save(str(p))
    return p


@pytest.fixture()
def tmp_pattern(tmp_path: Path) -> Path:
    """Create a tiny tileable pattern."""
    img = Image.new("RGBA", (32, 32), (200, 200, 200, 128))
    p = tmp_path / "pattern.png"
    img.save(str(p))
    return p


# ---------------------------------------------------------------------------
# Unit: background
# ---------------------------------------------------------------------------

class TestCreateBackground:
    def test_solid_light(self):
        bg = _create_background(400, 300)
        assert bg.size == (400, 300)
        # Top-left pixel should be cream
        r, g, b, a = bg.getpixel((0, 0))
        assert (r, g, b) == BRAND_CREAM

    def test_solid_dark(self):
        bg = _create_background(400, 300, dark=True)
        r, g, b, a = bg.getpixel((0, 0))
        assert (r, g, b) == BRAND_CHARCOAL

    def test_tiled_pattern(self, tmp_pattern: Path):
        bg = _create_background(200, 200, pattern_path=str(tmp_pattern))
        assert bg.size == (200, 200)

    def test_missing_pattern_falls_back(self):
        bg = _create_background(200, 200, pattern_path="/nonexistent/pat.png")
        assert bg.size == (200, 200)


# ---------------------------------------------------------------------------
# Unit: round corners
# ---------------------------------------------------------------------------

class TestRoundCorners:
    def test_produces_rgba(self):
        img = Image.new("RGBA", (100, 100), (255, 0, 0, 255))
        out = _round_corners(img, 12)
        assert out.mode == "RGBA"
        assert out.size == (100, 100)

    def test_corner_is_transparent(self):
        img = Image.new("RGBA", (100, 100), (255, 0, 0, 255))
        out = _round_corners(img, 20)
        # Top-left corner pixel should be fully transparent
        _, _, _, a = out.getpixel((0, 0))
        assert a == 0


# ---------------------------------------------------------------------------
# Unit: drop shadow
# ---------------------------------------------------------------------------

class TestDropShadow:
    def test_larger_than_source(self):
        img = Image.new("RGBA", (100, 100), (255, 0, 0, 255))
        out = _add_drop_shadow(img, blur_radius=10)
        assert out.width > 100
        assert out.height > 100


# ---------------------------------------------------------------------------
# Unit: place screenshot
# ---------------------------------------------------------------------------

class TestPlaceScreenshot:
    def test_screenshot_composited(self, tmp_screenshot: Path):
        canvas = Image.new("RGBA", (800, 600), (255, 255, 255, 255))
        out = _place_screenshot(canvas, str(tmp_screenshot), scale_fraction=0.5)
        assert out.size == (800, 600)


# ---------------------------------------------------------------------------
# Unit: highlight
# ---------------------------------------------------------------------------

class TestHighlight:
    def test_highlight_region(self):
        canvas = Image.new("RGBA", (400, 300), (255, 255, 255, 255))
        out = _add_highlight(canvas, (50, 50, 100, 100))
        assert out.size == (400, 300)
        # Pixel inside highlight should differ from pure white
        r, g, b, a = out.getpixel((60, 60))
        assert (r, g, b) != (255, 255, 255)


# ---------------------------------------------------------------------------
# Unit: text
# ---------------------------------------------------------------------------

class TestRenderText:
    def test_headline_only(self):
        canvas = Image.new("RGBA", (800, 600), (255, 255, 255, 255))
        out = _render_text(canvas, headline="Hello")
        assert out.size == (800, 600)

    def test_headline_and_subhead(self):
        canvas = Image.new("RGBA", (800, 600), (255, 255, 255, 255))
        out = _render_text(canvas, headline="Title", subhead="Subtitle")
        assert out.size == (800, 600)

    def test_no_text(self):
        canvas = Image.new("RGBA", (800, 600), (255, 255, 255, 255))
        out = _render_text(canvas)
        assert out.size == (800, 600)


# ---------------------------------------------------------------------------
# Unit: logo
# ---------------------------------------------------------------------------

class TestPlaceLogo:
    def test_with_logo(self, tmp_logo: Path):
        canvas = Image.new("RGBA", (400, 300), (255, 255, 255, 255))
        out = _place_logo(canvas, logo_path=str(tmp_logo), max_size=32)
        assert out.size == (400, 300)

    def test_missing_logo_no_crash(self):
        canvas = Image.new("RGBA", (400, 300), (255, 255, 255, 255))
        out = _place_logo(canvas, logo_path="/nonexistent/logo.png")
        assert out.size == (400, 300)


# ---------------------------------------------------------------------------
# Unit: font loader
# ---------------------------------------------------------------------------

class TestFontLoader:
    def test_returns_something(self):
        font = _load_font(24)
        assert font is not None


# ---------------------------------------------------------------------------
# Integration: full command
# ---------------------------------------------------------------------------

class TestCmdCompositeIllustration:
    def test_minimal(self, tmp_screenshot: Path, tmp_path: Path):
        out = tmp_path / "out.png"
        args = argparse.Namespace(
            screenshot=str(tmp_screenshot),
            headline="Test Headline",
            subhead=None,
            feature=None,
            pattern=None,
            logo=None,
            output=str(out),
            aspect_ratio="16:9",
            highlight_region=None,
            dark=False,
        )
        cmd_composite_illustration(args)
        assert out.exists()
        img = Image.open(str(out))
        assert img.size == (1920, 1080)

    def test_dark_mode(self, tmp_screenshot: Path, tmp_path: Path):
        out = tmp_path / "dark.png"
        args = argparse.Namespace(
            screenshot=str(tmp_screenshot),
            headline="Dark",
            subhead="Subtitle",
            feature=None,
            pattern=None,
            logo=None,
            output=str(out),
            aspect_ratio="16:9",
            highlight_region=None,
            dark=True,
        )
        cmd_composite_illustration(args)
        assert out.exists()

    def test_with_highlight(self, tmp_screenshot: Path, tmp_path: Path):
        out = tmp_path / "hl.png"
        args = argparse.Namespace(
            screenshot=str(tmp_screenshot),
            headline=None,
            subhead=None,
            feature="Library sync",
            pattern=None,
            logo=None,
            output=str(out),
            aspect_ratio="4:3",
            highlight_region="100,100,200,150",
            dark=False,
        )
        cmd_composite_illustration(args)
        assert out.exists()
        img = Image.open(str(out))
        assert img.size == (1600, 1200)

    def test_with_pattern_and_logo(self, tmp_screenshot: Path, tmp_pattern: Path, tmp_logo: Path, tmp_path: Path):
        out = tmp_path / "full.png"
        args = argparse.Namespace(
            screenshot=str(tmp_screenshot),
            headline="Full Feature",
            subhead="With all layers",
            feature=None,
            pattern=str(tmp_pattern),
            logo=str(tmp_logo),
            output=str(out),
            aspect_ratio="1:1",
            highlight_region=None,
            dark=False,
        )
        cmd_composite_illustration(args)
        assert out.exists()
        img = Image.open(str(out))
        assert img.size == (1200, 1200)

    def test_feature_as_headline_fallback(self, tmp_screenshot: Path, tmp_path: Path):
        out = tmp_path / "feat.png"
        args = argparse.Namespace(
            screenshot=str(tmp_screenshot),
            headline=None,
            subhead=None,
            feature="Discovering New Capabilities",
            pattern=None,
            logo=None,
            output=str(out),
            aspect_ratio="16:9",
            highlight_region=None,
            dark=False,
        )
        cmd_composite_illustration(args)
        assert out.exists()

    def test_missing_screenshot_exits(self, tmp_path: Path):
        out = tmp_path / "nope.png"
        args = argparse.Namespace(
            screenshot="/nonexistent/screen.png",
            headline="X",
            subhead=None,
            feature=None,
            pattern=None,
            logo=None,
            output=str(out),
            aspect_ratio="16:9",
            highlight_region=None,
            dark=False,
        )
        with pytest.raises(SystemExit):
            cmd_composite_illustration(args)

    def test_bad_highlight_region_exits(self, tmp_screenshot: Path, tmp_path: Path):
        out = tmp_path / "bad.png"
        args = argparse.Namespace(
            screenshot=str(tmp_screenshot),
            headline=None,
            subhead=None,
            feature=None,
            pattern=None,
            logo=None,
            output=str(out),
            aspect_ratio="16:9",
            highlight_region="not,valid",
            dark=False,
        )
        with pytest.raises(SystemExit):
            cmd_composite_illustration(args)
