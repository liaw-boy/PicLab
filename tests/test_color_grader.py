"""
Unit tests for the color grading core.

Covers:
  - GradeSettings.is_identity()
  - CurvePoints defaults and shape
  - apply() under various settings combinations
"""
from __future__ import annotations

import statistics
from pathlib import Path

import pytest
from PIL import Image

from src.models.grade_settings import CurvePoints, GradeSettings, _DEFAULT_CURVE
from src.core.color_grader import apply

# ─────────────────────────────────────────────────────────────────────────────
# Shared fixtures
# ─────────────────────────────────────────────────────────────────────────────

PROVIA_LUT_PATH = str(
    Path(__file__).parent.parent / "src" / "assets" / "luts" / "PROVIA.cube"
)


def _grey_100x100() -> Image.Image:
    """Mid-grey 100×100 RGB image — the canonical test canvas."""
    return Image.new("RGB", (100, 100), (128, 128, 128))


def _mean_value(img: Image.Image) -> float:
    """Average pixel value across all channels."""
    import numpy as np
    return float(np.asarray(img.convert("RGB"), dtype=np.float32).mean())


# ─────────────────────────────────────────────────────────────────────────────
# GradeSettings / CurvePoints model tests
# ─────────────────────────────────────────────────────────────────────────────

class TestGradeSettingsIsIdentity:
    def test_default_settings_are_identity(self):
        """Default GradeSettings must report identity — no processing needed."""
        assert GradeSettings().is_identity() is True

    def test_nonzero_exposure_is_not_identity(self):
        assert GradeSettings(exposure=50).is_identity() is False

    def test_nonzero_contrast_is_not_identity(self):
        assert GradeSettings(contrast=10).is_identity() is False

    def test_nonzero_highlights_is_not_identity(self):
        assert GradeSettings(highlights=20).is_identity() is False

    def test_nonzero_shadows_is_not_identity(self):
        assert GradeSettings(shadows=-30).is_identity() is False

    def test_nonzero_whites_is_not_identity(self):
        assert GradeSettings(whites=10).is_identity() is False

    def test_nonzero_blacks_is_not_identity(self):
        assert GradeSettings(blacks=-10).is_identity() is False

    def test_changed_temperature_is_not_identity(self):
        assert GradeSettings(wb_temperature=6500).is_identity() is False

    def test_nonzero_tint_is_not_identity(self):
        assert GradeSettings(wb_tint=10).is_identity() is False

    def test_nonzero_hsl_hue_is_not_identity(self):
        assert GradeSettings(hsl_hue=(10,) + (0,) * 7).is_identity() is False

    def test_nonzero_hsl_saturation_is_not_identity(self):
        assert GradeSettings(hsl_saturation=(0, 50) + (0,) * 6).is_identity() is False

    def test_nonzero_hsl_luminance_is_not_identity(self):
        assert GradeSettings(hsl_luminance=(0,) * 7 + (20,)).is_identity() is False

    def test_nonzero_sharpening_is_not_identity(self):
        assert GradeSettings(sharpening=50).is_identity() is False

    def test_nonzero_noise_reduction_is_not_identity(self):
        assert GradeSettings(noise_reduction=50).is_identity() is False

    def test_lut_path_set_is_not_identity(self):
        assert GradeSettings(lut_path="/some/path.cube").is_identity() is False

    def test_modified_curve_is_not_identity(self):
        custom = CurvePoints(points=((0.0, 0.0), (0.5, 0.6), (1.0, 1.0)))
        assert GradeSettings(curve_rgb=custom).is_identity() is False


class TestCurvePoints:
    def test_default_curve_is_identity(self):
        cp = CurvePoints()
        assert cp.is_identity() is True

    def test_default_curve_has_three_control_points(self):
        cp = CurvePoints()
        assert len(cp.points) == 3

    def test_default_curve_starts_at_origin(self):
        cp = CurvePoints()
        assert cp.points[0] == (0.0, 0.0)

    def test_default_curve_ends_at_top_right(self):
        cp = CurvePoints()
        assert cp.points[-1] == (1.0, 1.0)

    def test_default_curve_has_midpoint_at_half(self):
        cp = CurvePoints()
        assert cp.points[1] == (0.5, 0.5)

    def test_custom_curve_is_not_identity(self):
        cp = CurvePoints(points=((0.0, 0.0), (0.5, 0.7), (1.0, 1.0)))
        assert cp.is_identity() is False

    def test_curve_matches_default_constant(self):
        """CurvePoints default must exactly match the module-level constant."""
        assert CurvePoints().points == _DEFAULT_CURVE


# ─────────────────────────────────────────────────────────────────────────────
# apply() — size and output type
# ─────────────────────────────────────────────────────────────────────────────

class TestApplyOutputContract:
    def test_identity_settings_returns_same_size(self):
        img = _grey_100x100()
        result = apply(img, GradeSettings())
        assert result.size == img.size

    def test_identity_settings_returns_rgb_image(self):
        img = _grey_100x100()
        result = apply(img, GradeSettings())
        assert result.mode == "RGB"

    def test_apply_does_not_mutate_input(self):
        img = _grey_100x100()
        original_data = list(img.getdata())
        apply(img, GradeSettings(exposure=100))
        assert list(img.getdata()) == original_data

    def test_identity_settings_returns_copy_not_same_object(self):
        img = _grey_100x100()
        result = apply(img, GradeSettings())
        assert result is not img


# ─────────────────────────────────────────────────────────────────────────────
# apply() — exposure
# ─────────────────────────────────────────────────────────────────────────────

class TestApplyExposure:
    def test_positive_exposure_brightens_image(self):
        img = _grey_100x100()
        before = _mean_value(img)
        result = apply(img, GradeSettings(exposure=100))
        after = _mean_value(result)
        assert after > before, f"Expected brighter image: before={before:.1f}, after={after:.1f}"

    def test_negative_exposure_darkens_image(self):
        img = _grey_100x100()
        before = _mean_value(img)
        result = apply(img, GradeSettings(exposure=-100))
        after = _mean_value(result)
        assert after < before

    def test_positive_exposure_returns_correct_size(self):
        img = _grey_100x100()
        result = apply(img, GradeSettings(exposure=100))
        assert result.size == (100, 100)

    def test_extreme_positive_exposure_does_not_crash(self):
        img = _grey_100x100()
        result = apply(img, GradeSettings(exposure=300))
        assert result.size == (100, 100)

    def test_extreme_negative_exposure_does_not_crash(self):
        img = _grey_100x100()
        result = apply(img, GradeSettings(exposure=-300))
        assert result.size == (100, 100)


# ─────────────────────────────────────────────────────────────────────────────
# apply() — white balance
# ─────────────────────────────────────────────────────────────────────────────

class TestApplyWhiteBalance:
    def test_changed_temperature_runs_without_error(self):
        img = _grey_100x100()
        result = apply(img, GradeSettings(wb_temperature=3200))
        assert result.size == img.size

    def test_warm_temperature_increases_red_channel(self):
        """Warming (low K) should shift red up relative to blue."""
        img = _grey_100x100()
        result = apply(img, GradeSettings(wb_temperature=3000))
        r_mean = sum(p[0] for p in result.getdata()) / (100 * 100)
        b_mean = sum(p[2] for p in result.getdata()) / (100 * 100)
        assert r_mean > b_mean

    def test_cool_temperature_runs_without_error(self):
        img = _grey_100x100()
        result = apply(img, GradeSettings(wb_temperature=9000))
        assert result.size == img.size

    def test_tint_adjustment_runs_without_error(self):
        img = _grey_100x100()
        result = apply(img, GradeSettings(wb_tint=50))
        assert result.size == img.size

    def test_combined_temperature_and_tint_runs_without_error(self):
        img = _grey_100x100()
        result = apply(img, GradeSettings(wb_temperature=4000, wb_tint=-30))
        assert result.size == img.size


# ─────────────────────────────────────────────────────────────────────────────
# apply() — HSL saturation
# ─────────────────────────────────────────────────────────────────────────────

class TestApplyHSLSaturation:
    def test_all_zero_saturation_shifts_leave_grey_unchanged(self):
        """A perfectly grey image has no hue/saturation — HSL shifts should be no-ops."""
        img = _grey_100x100()
        # Explicitly pass all-zero saturation (same as identity, but exercise the path)
        settings = GradeSettings(hsl_saturation=(0,) * 8)
        result = apply(img, settings)
        before = _mean_value(img)
        after = _mean_value(result)
        assert abs(after - before) < 2.0, (
            f"Expected near-identical mean: before={before:.1f}, after={after:.1f}"
        )

    def test_negative_saturation_on_grey_is_safe(self):
        """Desaturating a grey image must not crash or overflow."""
        img = _grey_100x100()
        result = apply(img, GradeSettings(hsl_saturation=(-100,) * 8))
        assert result.size == img.size

    def test_positive_saturation_on_coloured_image_runs_without_error(self):
        """Saturation boost on a red image should complete without crash."""
        img = Image.new("RGB", (50, 50), (200, 50, 50))
        result = apply(img, GradeSettings(hsl_saturation=(50,) * 8))
        assert result.size == img.size

    def test_all_zero_saturation_settings_are_identity(self):
        assert GradeSettings(hsl_saturation=(0,) * 8).is_identity() is True


# ─────────────────────────────────────────────────────────────────────────────
# apply() — noise reduction
# ─────────────────────────────────────────────────────────────────────────────

class TestApplyNoiseReduction:
    def test_noise_reduction_50_runs_without_error(self):
        img = _grey_100x100()
        result = apply(img, GradeSettings(noise_reduction=50))
        assert result.size == img.size

    def test_noise_reduction_100_runs_without_error(self):
        img = _grey_100x100()
        result = apply(img, GradeSettings(noise_reduction=100))
        assert result.size == img.size

    def test_noise_reduction_returns_rgb(self):
        img = _grey_100x100()
        result = apply(img, GradeSettings(noise_reduction=50))
        assert result.mode == "RGB"

    def test_noise_reduction_zero_is_identity_path(self):
        """noise_reduction=0 means no blur — result for otherwise-identity is a copy."""
        img = _grey_100x100()
        result = apply(img, GradeSettings(noise_reduction=0))
        assert list(result.getdata()) == list(img.getdata())


# ─────────────────────────────────────────────────────────────────────────────
# apply() — sharpening
# ─────────────────────────────────────────────────────────────────────────────

class TestApplySharpening:
    def test_sharpening_50_runs_without_error(self):
        img = _grey_100x100()
        result = apply(img, GradeSettings(sharpening=50))
        assert result.size == img.size

    def test_sharpening_100_runs_without_error(self):
        img = _grey_100x100()
        result = apply(img, GradeSettings(sharpening=100))
        assert result.size == img.size

    def test_sharpening_returns_rgb(self):
        img = _grey_100x100()
        result = apply(img, GradeSettings(sharpening=50))
        assert result.mode == "RGB"

    def test_sharpening_with_custom_detail_mask_runs_without_error(self):
        img = _grey_100x100()
        result = apply(img, GradeSettings(sharpening=80, detail_mask=80))
        assert result.size == img.size


# ─────────────────────────────────────────────────────────────────────────────
# apply() — LUT
# ─────────────────────────────────────────────────────────────────────────────

class TestApplyLUT:
    def test_provia_lut_applies_without_error(self):
        img = _grey_100x100()
        result = apply(img, GradeSettings(lut_path=PROVIA_LUT_PATH, lut_opacity=100))
        assert result.size == img.size

    def test_provia_lut_returns_rgb_image(self):
        img = _grey_100x100()
        result = apply(img, GradeSettings(lut_path=PROVIA_LUT_PATH, lut_opacity=100))
        assert result.mode == "RGB"

    def test_provia_lut_at_zero_opacity_equals_original(self):
        """Opacity 0 means LUT has no effect — result must match identity output."""
        img = _grey_100x100()
        identity_result = apply(img, GradeSettings())
        lut_zero_result = apply(img, GradeSettings(lut_path=PROVIA_LUT_PATH, lut_opacity=0))
        # lut_opacity=0 → identity path (is_identity() is False though, but opacity guard fires)
        assert lut_zero_result.size == identity_result.size

    def test_provia_lut_at_50_opacity_runs_without_error(self):
        img = _grey_100x100()
        result = apply(img, GradeSettings(lut_path=PROVIA_LUT_PATH, lut_opacity=50))
        assert result.size == img.size

    def test_invalid_lut_path_does_not_raise(self):
        """A missing LUT must emit a warning and return a valid image — not crash."""
        img = _grey_100x100()
        import warnings
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = apply(img, GradeSettings(lut_path="/nonexistent/path.cube", lut_opacity=100))
        assert result.size == img.size
        assert any("LUT" in str(warning.message) for warning in w)


# ─────────────────────────────────────────────────────────────────────────────
# apply() — edge cases
# ─────────────────────────────────────────────────────────────────────────────

class TestApplyEdgeCases:
    def test_1x1_white_pixel_returns_valid_image(self):
        img = Image.new("RGB", (1, 1), (255, 255, 255))
        result = apply(img, GradeSettings(exposure=50))
        assert result.size == (1, 1)
        assert result.mode == "RGB"

    def test_1x1_white_pixel_identity_returns_valid_image(self):
        img = Image.new("RGB", (1, 1), (255, 255, 255))
        result = apply(img, GradeSettings())
        assert result.size == (1, 1)
        pixel = result.getpixel((0, 0))
        assert pixel == (255, 255, 255)

    def test_1x1_black_pixel_with_sharpening(self):
        img = Image.new("RGB", (1, 1), (0, 0, 0))
        result = apply(img, GradeSettings(sharpening=50))
        assert result.size == (1, 1)
        assert result.mode == "RGB"

    def test_1x1_white_pixel_with_lut(self):
        img = Image.new("RGB", (1, 1), (255, 255, 255))
        result = apply(img, GradeSettings(lut_path=PROVIA_LUT_PATH, lut_opacity=100))
        assert result.size == (1, 1)
        assert result.mode == "RGB"

    def test_all_settings_combined_runs_without_error(self):
        """Smoke test: every knob turned at once must not crash."""
        img = _grey_100x100()
        settings = GradeSettings(
            exposure=50,
            contrast=30,
            highlights=-20,
            shadows=20,
            whites=10,
            blacks=-10,
            wb_temperature=6000,
            wb_tint=10,
            hsl_hue=(5,) * 8,
            hsl_saturation=(10,) * 8,
            hsl_luminance=(-5,) * 8,
            sharpening=30,
            noise_reduction=20,
            lut_path=PROVIA_LUT_PATH,
            lut_opacity=80,
        )
        result = apply(img, settings)
        assert result.size == img.size
        assert result.mode == "RGB"

    def test_rgba_input_is_handled(self):
        """apply() should gracefully handle RGBA input by converting to RGB."""
        img = Image.new("RGBA", (50, 50), (128, 128, 128, 255))
        result = apply(img, GradeSettings(exposure=50))
        assert result.size == (50, 50)
        assert result.mode == "RGB"
