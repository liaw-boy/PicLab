"""
Unit tests for src/core/brand_renderer.py

RED  → Written before verifying pass/fail.
GREEN → Run: cd /home/lbw/project/project_PicLab && QT_QPA_PLATFORM=offscreen python3 -m pytest tests/test_brand_renderer.py -v
"""
from __future__ import annotations

import pytest
from pathlib import Path
from PIL import Image

from src.core.brand_renderer import BRANDS, LOGO_FILES, render_brand


REQUIRED_BRAND_KEYS = {"text", "short", "weight", "color", "styles"}
SLOT_HEIGHT = 60  # typical strip height used in tests


# ---------------------------------------------------------------------------
# 1. BRANDS is a non-empty dict
# ---------------------------------------------------------------------------

class TestBrandsDict:
    def test_brands_is_dict(self):
        assert isinstance(BRANDS, dict), "BRANDS must be a dict"

    def test_brands_is_non_empty(self):
        assert len(BRANDS) > 0, "BRANDS must contain at least one entry"

    def test_brands_contains_known_makes(self):
        """Spot-check that the most common camera makes are registered."""
        common_makes = ["Sony", "Canon", "Nikon", "Fujifilm"]
        for make in common_makes:
            assert make in BRANDS, f"'{make}' is missing from BRANDS"


# ---------------------------------------------------------------------------
# 2. Each brand has the required keys
# ---------------------------------------------------------------------------

class TestBrandStructure:
    @pytest.mark.parametrize("brand_name", list(BRANDS.keys()))
    def test_brand_has_required_keys(self, brand_name: str):
        entry = BRANDS[brand_name]
        missing = REQUIRED_BRAND_KEYS - set(entry.keys())
        assert not missing, (
            f"BRANDS['{brand_name}'] is missing keys: {missing}"
        )

    @pytest.mark.parametrize("brand_name", list(BRANDS.keys()))
    def test_brand_text_is_string(self, brand_name: str):
        assert isinstance(BRANDS[brand_name]["text"], str), (
            f"BRANDS['{brand_name}']['text'] must be a str"
        )

    @pytest.mark.parametrize("brand_name", list(BRANDS.keys()))
    def test_brand_text_is_non_empty(self, brand_name: str):
        assert BRANDS[brand_name]["text"].strip(), (
            f"BRANDS['{brand_name}']['text'] must not be empty or whitespace"
        )

    @pytest.mark.parametrize("brand_name", list(BRANDS.keys()))
    def test_brand_color_is_rgb_tuple(self, brand_name: str):
        color = BRANDS[brand_name]["color"]
        assert isinstance(color, tuple) and len(color) == 3, (
            f"BRANDS['{brand_name}']['color'] must be a 3-tuple RGB"
        )
        for channel in color:
            assert 0 <= channel <= 255, (
                f"BRANDS['{brand_name}']['color'] channel {channel} out of range [0,255]"
            )

    @pytest.mark.parametrize("brand_name", list(BRANDS.keys()))
    def test_brand_styles_is_list(self, brand_name: str):
        styles = BRANDS[brand_name]["styles"]
        assert isinstance(styles, list) and len(styles) > 0, (
            f"BRANDS['{brand_name}']['styles'] must be a non-empty list"
        )

    @pytest.mark.parametrize("brand_name", list(BRANDS.keys()))
    def test_brand_weight_is_valid(self, brand_name: str):
        valid_weights = {"bold", "regular", "light"}
        weight = BRANDS[brand_name]["weight"]
        assert weight in valid_weights, (
            f"BRANDS['{brand_name}']['weight'] = '{weight}' not in {valid_weights}"
        )

    @pytest.mark.parametrize("brand_name", list(BRANDS.keys()))
    def test_brand_short_is_string(self, brand_name: str):
        short = BRANDS[brand_name]["short"]
        assert isinstance(short, str) and short.strip(), (
            f"BRANDS['{brand_name}']['short'] must be a non-empty string"
        )


# ---------------------------------------------------------------------------
# 3. render_brand returns a PIL Image when called with a test image
# ---------------------------------------------------------------------------

class TestRenderBrand:
    # ── "text" style (always available — no asset file needed) ───────────────

    def test_render_brand_returns_pil_image(self):
        result = render_brand("Sony", SLOT_HEIGHT, style="text")
        assert isinstance(result, Image.Image), (
            "render_brand() must return a PIL.Image.Image"
        )

    def test_render_brand_height_matches_slot(self):
        result = render_brand("Sony", SLOT_HEIGHT, style="text")
        assert result.height == SLOT_HEIGHT, (
            f"render_brand() height {result.height} must equal slot_height {SLOT_HEIGHT}"
        )

    def test_render_brand_width_is_positive(self):
        result = render_brand("Sony", SLOT_HEIGHT, style="text")
        assert result.width > 0, "render_brand() must return positive width"

    def test_render_brand_is_rgba(self):
        """Brand images use RGBA for alpha-compositing on the canvas."""
        result = render_brand("Sony", SLOT_HEIGHT, style="text")
        assert result.mode == "RGBA", (
            f"render_brand() must return RGBA image, got {result.mode!r}"
        )

    # ── Badge style ───────────────────────────────────────────────────────────

    def test_render_badge_returns_image(self):
        result = render_brand("Canon", SLOT_HEIGHT, style="badge")
        assert isinstance(result, Image.Image)
        assert result.height == SLOT_HEIGHT

    def test_render_badge_is_rgba(self):
        result = render_brand("Nikon", SLOT_HEIGHT, style="badge")
        assert result.mode == "RGBA"

    # ── Wordmark style ────────────────────────────────────────────────────────

    def test_render_wordmark_returns_image(self):
        result = render_brand("Fujifilm", SLOT_HEIGHT, style="wordmark")
        assert isinstance(result, Image.Image)
        assert result.height == SLOT_HEIGHT

    # ── Logo style (falls back to text if asset missing) ─────────────────────

    def test_render_logo_style_returns_image(self):
        result = render_brand("Sony", SLOT_HEIGHT, style="logo")
        assert isinstance(result, Image.Image)
        assert result.height == SLOT_HEIGHT

    # ── Unknown brand ─────────────────────────────────────────────────────────

    def test_unknown_brand_returns_image(self):
        """render_brand with an unregistered make should not raise."""
        result = render_brand("UnknownCamera9000", SLOT_HEIGHT, style="text")
        assert isinstance(result, Image.Image)
        assert result.height == SLOT_HEIGHT

    # ── Empty make ────────────────────────────────────────────────────────────

    def test_empty_make_returns_transparent_placeholder(self):
        result = render_brand("", SLOT_HEIGHT, style="text")
        assert isinstance(result, Image.Image)
        # Per source: returns 1×slot_height transparent image
        assert result.size == (1, SLOT_HEIGHT)

    # ── Slot height variations ────────────────────────────────────────────────

    @pytest.mark.parametrize("height", [20, 40, 60, 100, 200])
    def test_render_brand_respects_slot_height(self, height: int):
        result = render_brand("Canon", height, style="text")
        assert result.height == height, (
            f"Expected height {height}, got {result.height}"
        )

    # ── All registered brands render without exception ────────────────────────

    @pytest.mark.parametrize("brand_name", list(BRANDS.keys()))
    def test_all_brands_render_text_style(self, brand_name: str):
        """Every brand in BRANDS must produce a valid image with 'text' style."""
        result = render_brand(brand_name, SLOT_HEIGHT, style="text")
        assert isinstance(result, Image.Image), (
            f"render_brand('{brand_name}') returned {type(result)}"
        )
        assert result.height == SLOT_HEIGHT

    @pytest.mark.parametrize("brand_name", list(BRANDS.keys()))
    def test_all_brands_render_badge_style(self, brand_name: str):
        """Every brand in BRANDS must produce a valid image with 'badge' style."""
        result = render_brand(brand_name, SLOT_HEIGHT, style="badge")
        assert isinstance(result, Image.Image), (
            f"render_brand('{brand_name}', style='badge') failed"
        )
        assert result.height == SLOT_HEIGHT


# ---------------------------------------------------------------------------
# LOGO_FILES structure checks
# ---------------------------------------------------------------------------

class TestLogoFiles:
    def test_logo_files_is_dict(self):
        assert isinstance(LOGO_FILES, dict)

    def test_logo_files_non_empty(self):
        assert len(LOGO_FILES) > 0

    def test_logo_file_values_are_strings(self):
        for brand, filename in LOGO_FILES.items():
            assert isinstance(filename, str), (
                f"LOGO_FILES['{brand}'] must be a str filename, got {type(filename)}"
            )

    def test_logo_file_values_have_extensions(self):
        for brand, filename in LOGO_FILES.items():
            assert "." in filename, (
                f"LOGO_FILES['{brand}'] = '{filename}' has no file extension"
            )
