"""
LR-style Auto Tone — analyze a histogram + chrominance and propose grade settings.

Algorithm (matches Lightroom Classic's spirit, not the exact ML model):

  Tonal targets:
    - Exposure   : shift so 50th-percentile luma → ~0.45 (mid-gray)
    - Whites     : 99th-percentile → ~0.95 (just shy of clipping)
    - Blacks     : 1st-percentile  → ~0.02 (just shy of crushing)
    - Highlights : if 99th percentile clipping > 1%, pull highlights
    - Shadows    : if 1st percentile clipping > 1%, lift shadows

  Color targets:
    - WB Temperature/Tint : gray-world — neutralize average chroma
    - Vibrance            : if global saturation low/high, nudge

All outputs are integers in the same scale GradeSettings uses, so the result
plugs directly into `dataclasses.replace(settings, ...)`.
"""
from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

import numpy as np
from PIL import Image

if TYPE_CHECKING:
    from src.models.grade_settings import GradeSettings


# ── Targets (in 0..1 luma space) ──────────────────────────────────────────────
TARGET_MID = 0.45          # LR aims slightly below mid-gray for film-like density
TARGET_WHITES = 0.95
TARGET_BLACKS = 0.02
TARGET_SAT_MEAN = 0.30     # ITU-R BT.601 saturation mean target


def _to_luma(arr: np.ndarray) -> np.ndarray:
    """Rec.709 luma in [0, 1] from a uint8 RGB array."""
    return (
        0.2126 * arr[..., 0] + 0.7152 * arr[..., 1] + 0.0722 * arr[..., 2]
    ) / 255.0


def _stops_from_ratio(target: float, current: float) -> float:
    """How many stops to shift exposure so current → target (log2 ratio)."""
    if current <= 1e-4:
        return 0.0
    return float(np.log2(target / current))


def _gray_world_kelvin(rgb_mean: np.ndarray) -> tuple[int, int]:
    """Estimate temperature/tint shift to neutralize a non-neutral cast.

    Returns (kelvin_offset, tint_offset) where:
      kelvin_offset shifts wb_temperature from 5500.
      tint_offset adjusts wb_tint (-100..+100).
    """
    r, g, b = rgb_mean / max(rgb_mean.max(), 1.0)  # normalize so brightest channel = 1
    # Warmth axis: R vs B. If R > B → image is warm → cool it (lower K).
    warm_excess = float(r - b)  # +0.2 = clearly warm
    kelvin_shift = int(-warm_excess * 2500)  # max ±2500K from neutral
    kelvin = max(2000, min(10000, 5500 + kelvin_shift))
    # Tint axis: G vs (R+B)/2. Excess green → +tint correction toward magenta
    green_excess = float(g - (r + b) / 2)
    tint = int(-green_excess * 100)  # ±100 cap
    tint = max(-100, min(100, tint))
    return kelvin - 5500, tint  # caller adds offset to defaults


def analyze(img: Image.Image) -> dict[str, int]:
    """Compute proposed delta values for each tonal/color slider.

    Returns a dict that can be merged into GradeSettings via `dataclasses.replace`.
    """
    arr = np.asarray(img.convert("RGB"), dtype=np.uint8)
    luma = _to_luma(arr)

    # Robust percentiles
    p1 = float(np.percentile(luma, 1))
    p50 = float(np.percentile(luma, 50))
    p99 = float(np.percentile(luma, 99))

    # ── Exposure: aim mid-gray
    ev_stops = _stops_from_ratio(TARGET_MID, max(p50, 0.01))
    # Soft-clip so we don't over-correct extreme cases
    ev_stops = float(np.clip(ev_stops, -2.0, 2.0))
    exposure = int(round(ev_stops * 100))  # GradeSettings stores EV × 100

    # ── Whites / Blacks: nudge endpoints toward targets
    # If p99 is well below target → push whites up; if above → pull down.
    whites = int(round((TARGET_WHITES - p99) * 200))
    whites = int(np.clip(whites, -100, 100))
    blacks = int(round((TARGET_BLACKS - p1) * 200))
    blacks = int(np.clip(blacks, -100, 100))

    # ── Highlights / Shadows: only fire if there is actual clipping
    clip_high_pct = float((luma > 0.98).mean() * 100)
    clip_low_pct = float((luma < 0.02).mean() * 100)
    highlights = int(round(-clip_high_pct * 8)) if clip_high_pct > 1.0 else 0
    highlights = int(np.clip(highlights, -100, 0))
    shadows = int(round(clip_low_pct * 8)) if clip_low_pct > 1.0 else 0
    shadows = int(np.clip(shadows, 0, 100))

    # ── White balance via gray world
    rgb_mean = arr.reshape(-1, 3).mean(axis=0)
    k_off, tint = _gray_world_kelvin(rgb_mean)
    wb_temperature = int(np.clip(5500 + k_off, 2000, 10000))
    wb_tint = int(np.clip(tint, -100, 100))

    # ── Vibrance: nudge toward target saturation mean
    # Saturation in HSV terms: max - min over max
    rgb_f = arr.astype(np.float32) / 255.0
    mx = rgb_f.max(axis=-1)
    mn = rgb_f.min(axis=-1)
    sat = np.where(mx > 1e-4, (mx - mn) / np.maximum(mx, 1e-4), 0.0)
    sat_mean = float(sat.mean())
    vibrance = int(round((TARGET_SAT_MEAN - sat_mean) * 200))
    vibrance = int(np.clip(vibrance, -50, 50))  # gentler than tonal

    return {
        "exposure": exposure,
        "highlights": highlights,
        "shadows": shadows,
        "whites": whites,
        "blacks": blacks,
        "wb_temperature": wb_temperature,
        "wb_tint": wb_tint,
        "vibrance": vibrance,
    }


def apply(settings: "GradeSettings", img: Image.Image) -> "GradeSettings":
    """Return a new GradeSettings with auto-tone deltas merged in.

    Preserves any non-tonal user choices (LUT, HSL, curves, split tone, etc.).
    """
    deltas = analyze(img)
    return replace(settings, **deltas)
