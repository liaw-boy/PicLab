"""
Unit tests for src/core/image_processor.py

RED  → These tests are written first, before any changes to implementation.
GREEN → Run: cd /home/lbw/project/project_PicLab && QT_QPA_PLATFORM=offscreen python3 -m pytest tests/test_image_processor.py -v
"""
from __future__ import annotations

import pytest
from pathlib import Path
from PIL import Image

from src.models.photo import Photo, ExifData
from src.models.settings import (
    BorderSettings,
    TemplateStyle,
    AspectRatioPreset,
    BorderPreset,
    LogoStyle,
)
from src.core.image_processor import process


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

INPUT_W = 800
INPUT_H = 600


def _make_photo(width: int = INPUT_W, height: int = INPUT_H) -> Photo:
    """Create a minimal Photo fixture with a synthetic PIL image."""
    img = Image.new("RGB", (width, height), (100, 100, 100))
    return Photo(
        file_path=Path("/tmp/test_image.jpg"),
        image=img,
        exif=ExifData(),
    )


def _default_settings(**overrides) -> BorderSettings:
    """Return a BorderSettings with sensible defaults, allowing field overrides."""
    defaults = dict(
        template=TemplateStyle.CLASSIC,
        aspect_ratio=AspectRatioPreset.FREE,
        border_preset=BorderPreset.MEDIUM,
        show_logo=False,
        show_exif=False,
        bg_color=(255, 255, 255),
        blur_background=False,
        export_long_edge=None,   # disable resize for unit tests
        output_sharpening=False,
    )
    defaults.update(overrides)
    return BorderSettings(**defaults)


# ---------------------------------------------------------------------------
# 1. process() with default BorderSettings returns a PIL Image
# ---------------------------------------------------------------------------

class TestProcessReturnType:
    def test_returns_pil_image(self):
        photo = _make_photo()
        settings = _default_settings()
        result = process(photo, settings)
        assert isinstance(result, Image.Image), (
            "process() must return a PIL.Image.Image instance"
        )

    def test_returns_rgb_mode(self):
        photo = _make_photo()
        settings = _default_settings()
        result = process(photo, settings)
        assert result.mode == "RGB", "Output image must be in RGB mode"

    def test_result_is_not_same_object_as_input(self):
        photo = _make_photo()
        settings = _default_settings()
        result = process(photo, settings)
        assert result is not photo.image, (
            "process() must return a new image, not the original"
        )


# ---------------------------------------------------------------------------
# 2. process() output is larger than input (border added)
# ---------------------------------------------------------------------------

class TestBorderAdded:
    def test_output_wider_than_input_in_free_mode(self):
        """FREE aspect ratio: canvas = photo + borders on left/right."""
        photo = _make_photo(800, 600)
        settings = _default_settings(aspect_ratio=AspectRatioPreset.FREE)
        result = process(photo, settings)
        assert result.size[0] > INPUT_W, (
            f"Output width {result.size[0]} should be greater than input {INPUT_W}"
        )

    def test_output_taller_than_input_in_free_mode(self):
        """FREE aspect ratio: canvas = photo + borders top/bottom."""
        photo = _make_photo(800, 600)
        settings = _default_settings(aspect_ratio=AspectRatioPreset.FREE)
        result = process(photo, settings)
        assert result.size[1] > INPUT_H, (
            f"Output height {result.size[1]} should be greater than input {INPUT_H}"
        )

    def test_border_thickness_reflected_in_size(self):
        """A THICK border preset must produce a larger canvas than a THIN one."""
        photo = _make_photo(800, 600)
        thin_settings = _default_settings(
            aspect_ratio=AspectRatioPreset.FREE,
            border_preset=BorderPreset.THIN,
        )
        thick_settings = _default_settings(
            aspect_ratio=AspectRatioPreset.FREE,
            border_preset=BorderPreset.THICK,
        )
        thin_result = process(photo, thin_settings)
        thick_result = process(photo, thick_settings)
        assert thick_result.size[0] >= thin_result.size[0], (
            "THICK border should produce canvas at least as wide as THIN"
        )
        assert thick_result.size[1] >= thin_result.size[1], (
            "THICK border should produce canvas at least as tall as THIN"
        )


# ---------------------------------------------------------------------------
# 3. process() with white border color returns image with white corners
# ---------------------------------------------------------------------------

class TestBorderColor:
    def test_white_border_produces_white_corners(self):
        """Top-left corner pixel should be white when bg_color is white."""
        photo = _make_photo(800, 600)
        settings = _default_settings(
            aspect_ratio=AspectRatioPreset.FREE,
            bg_color=(255, 255, 255),
        )
        result = process(photo, settings)
        corner_pixel = result.getpixel((0, 0))
        assert corner_pixel == (255, 255, 255), (
            f"Top-left corner pixel {corner_pixel} should be white (255,255,255) "
            "with a white border"
        )

    def test_dark_border_produces_dark_corners(self):
        """Top-left corner pixel should be near-black when bg_color is black."""
        photo = _make_photo(800, 600)
        settings = _default_settings(
            aspect_ratio=AspectRatioPreset.FREE,
            bg_color=(10, 10, 10),
        )
        result = process(photo, settings)
        corner_pixel = result.getpixel((0, 0))
        # Allow a small tolerance (blur may slightly alter exact shade)
        assert all(c < 50 for c in corner_pixel), (
            f"Top-left corner pixel {corner_pixel} should be dark (<50) "
            "with a black border"
        )

    def test_colored_border_produces_colored_corners(self):
        """Top-left corner should reflect the configured background color."""
        photo = _make_photo(800, 600)
        target_color = (200, 50, 50)
        settings = _default_settings(
            aspect_ratio=AspectRatioPreset.FREE,
            bg_color=target_color,
        )
        result = process(photo, settings)
        corner_pixel = result.getpixel((0, 0))
        assert corner_pixel == target_color, (
            f"Corner pixel {corner_pixel} should match bg_color {target_color}"
        )


# ---------------------------------------------------------------------------
# 4. process() with ratio 1:1 produces square output
# ---------------------------------------------------------------------------

class TestAspectRatio:
    def test_square_1_1_produces_square_canvas(self):
        photo = _make_photo(800, 600)
        settings = _default_settings(aspect_ratio=AspectRatioPreset.SQUARE_1_1)
        result = process(photo, settings)
        w, h = result.size
        assert w == h, f"1:1 output must be square, got {w}×{h}"

    def test_square_1_1_width_matches_preset(self):
        """SQUARE_1_1 maps to 1080×1080 per ASPECT_RATIO_SIZES."""
        from src.models.settings import ASPECT_RATIO_SIZES
        expected_w, expected_h = ASPECT_RATIO_SIZES[AspectRatioPreset.SQUARE_1_1]
        photo = _make_photo(800, 600)
        settings = _default_settings(aspect_ratio=AspectRatioPreset.SQUARE_1_1)
        result = process(photo, settings)
        assert result.size == (expected_w, expected_h), (
            f"Expected {expected_w}×{expected_h}, got {result.size}"
        )

    def test_portrait_4_5_has_correct_dimensions(self):
        from src.models.settings import ASPECT_RATIO_SIZES
        expected = ASPECT_RATIO_SIZES[AspectRatioPreset.PORTRAIT_4_5]
        photo = _make_photo(800, 600)
        settings = _default_settings(aspect_ratio=AspectRatioPreset.PORTRAIT_4_5)
        result = process(photo, settings)
        assert result.size == expected


# ---------------------------------------------------------------------------
# 5. process() with border_size=0 (CUSTOM preset, zeros) returns same-size output
# ---------------------------------------------------------------------------

class TestZeroBorder:
    def test_zero_border_in_free_mode_matches_input_width(self):
        """
        With a zero-pixel side border in FREE mode the canvas width should
        equal the photo width (borders add no pixels).
        """
        photo = _make_photo(800, 600)
        settings = _default_settings(
            aspect_ratio=AspectRatioPreset.FREE,
            border_preset=BorderPreset.CUSTOM,
            custom_top=0,
            custom_side=0,
            custom_exif_strip=0,
            show_logo=False,
            show_exif=False,
        )
        result = process(photo, settings)
        # border_dims clamps to max(1, ...) so effective border = 1px minimum
        # The canvas width should be very close to input width (within 2px each side)
        assert abs(result.size[0] - INPUT_W) <= 4, (
            f"Zero-border output width {result.size[0]} should be ~{INPUT_W}"
        )

    def test_zero_border_does_not_enlarge_significantly(self):
        """Zero border should not add substantial padding."""
        photo = _make_photo(800, 600)
        settings = _default_settings(
            aspect_ratio=AspectRatioPreset.FREE,
            border_preset=BorderPreset.CUSTOM,
            custom_top=0,
            custom_side=0,
            custom_exif_strip=0,
        )
        result = process(photo, settings)
        # Allow up to 4px growth per axis (clamped minimum of 1px per side)
        assert result.size[0] <= INPUT_W + 4
        assert result.size[1] <= INPUT_H + 4


# ---------------------------------------------------------------------------
# Edge-case tests
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_very_small_photo(self):
        """1×1 pixel photo should not crash."""
        photo = _make_photo(1, 1)
        settings = _default_settings(aspect_ratio=AspectRatioPreset.FREE)
        result = process(photo, settings)
        assert isinstance(result, Image.Image)

    def test_landscape_photo(self):
        photo = _make_photo(1920, 1080)
        settings = _default_settings(aspect_ratio=AspectRatioPreset.FREE)
        result = process(photo, settings)
        assert isinstance(result, Image.Image)
        assert result.size[0] > 0 and result.size[1] > 0

    def test_portrait_photo(self):
        photo = _make_photo(600, 900)
        settings = _default_settings(aspect_ratio=AspectRatioPreset.FREE)
        result = process(photo, settings)
        assert isinstance(result, Image.Image)

    def test_rounded_template_returns_image(self):
        photo = _make_photo(800, 600)
        settings = _default_settings(
            template=TemplateStyle.ROUNDED,
            aspect_ratio=AspectRatioPreset.SQUARE_1_1,
        )
        result = process(photo, settings)
        assert isinstance(result, Image.Image)

    def test_split_template_returns_image(self):
        photo = _make_photo(800, 600)
        settings = _default_settings(
            template=TemplateStyle.SPLIT,
            aspect_ratio=AspectRatioPreset.SQUARE_1_1,
        )
        result = process(photo, settings)
        assert isinstance(result, Image.Image)

    def test_blur_background_returns_image(self):
        photo = _make_photo(800, 600)
        settings = _default_settings(
            aspect_ratio=AspectRatioPreset.SQUARE_1_1,
            blur_background=True,
        )
        result = process(photo, settings)
        assert isinstance(result, Image.Image)

    def test_show_exif_with_empty_data_does_not_crash(self):
        """show_exif=True with all-empty ExifData should still produce a valid image."""
        photo = _make_photo()
        settings = _default_settings(show_exif=True, show_logo=True)
        result = process(photo, settings)
        assert isinstance(result, Image.Image)

    def test_show_exif_with_full_data_does_not_crash(self):
        img = Image.new("RGB", (800, 600), (100, 100, 100))
        photo = Photo(
            file_path=Path("/tmp/test.jpg"),
            image=img,
            exif=ExifData(
                camera_make="Sony",
                camera_model="ILCE-7RM2",
                lens_model="FE 35mm F2.8 ZA",
                focal_length="35mm",
                aperture="ƒ/2.8",
                shutter_speed="1/250s",
                iso="ISO800",
                date_taken="2025-01-13 14:22:50",
            ),
        )
        settings = _default_settings(
            show_exif=True,
            show_logo=True,
            logo_brand_override="Sony",
        )
        result = process(photo, settings)
        assert isinstance(result, Image.Image)
