"""
Font manager — discovers system fonts, caches instances.
Supports Latin and CJK (Traditional Chinese) rendering.
"""
from __future__ import annotations
from pathlib import Path
from functools import lru_cache
from PIL import ImageFont, ImageDraw, Image

_ASSETS   = Path(__file__).parent.parent / "assets" / "fonts"
_WIN_FONTS = Path("C:/Windows/Fonts")

# ── Font search lists ─────────────────────────────────────────────────────────
_REGULAR = [
    "Inter-Regular.ttf",   # Inter — 參考圖片風格最接近的幾何無襯線字體
    "Inter-Medium.ttf",
    "NotoSansTC.ttf",      # Noto Sans TC (CJK + Latin)
    "NotoSansTC-VF.ttf",
    "msjh.ttc",            # Microsoft JhengHei (supports CJK)
    "NotoSans-Regular.ttf",
    "Roboto-Regular.ttf",
    "segoeui.ttf",
    "Arial.ttf",
]
_BOLD = [
    "Inter-Bold.ttf",
    "Inter-Medium.ttf",
    "NotoSansTC.ttf",
    "NotoSansTC-VF.ttf",
    "msjhbd.ttc",
    "NotoSans-Bold.ttf",
    "Roboto-Bold.ttf",
    "segoeuib.ttf",
    "Arialbd.ttf",
]
_LIGHT = [
    "Inter-Light.ttf",
    "Inter-Regular.ttf",
    "NotoSansTC.ttf",
    "msjhl.ttc",
    "NotoSans-Light.ttf",
    "Roboto-Light.ttf",
    "segoeui.ttf",
]
# Fonts explicitly known to support CJK (Traditional Chinese)
_CJK = [
    "NotoSansTC-VF.ttf",
    "NotoSansHK-VF.ttf",
    "msjh.ttc",
    "msjhbd.ttc",
    "msjhl.ttc",
    "simsun.ttc",
    "mingliu.ttc",
    "msgothic.ttc",
]


def _find(candidates: list[str]) -> Path | None:
    for name in candidates:
        for base in [_ASSETS, _WIN_FONTS]:
            p = base / name
            if p.exists():
                return p
    return None


_REG_PATH  = _find(_REGULAR)
_BOLD_PATH = _find(_BOLD)
_LITE_PATH = _find(_LIGHT)
_CJK_PATH  = _find(_CJK)

# ── Public API ─────────────────────────────────────────────────────────────────

@lru_cache(maxsize=128)
def get_font(size: int, weight: str = "regular") -> ImageFont.FreeTypeFont:
    """Return a cached PIL font for the given size and weight."""
    path = {
        "regular": _REG_PATH  or _BOLD_PATH,
        "bold":    _BOLD_PATH or _REG_PATH,
        "light":   _LITE_PATH or _REG_PATH,
    }.get(weight, _REG_PATH)
    return _load(path, size)


@lru_cache(maxsize=64)
def get_cjk_font(size: int) -> ImageFont.FreeTypeFont:
    """Return a font guaranteed to render CJK characters."""
    return _load(_CJK_PATH or _REG_PATH, size)


def _load(path: Path | None, size: int) -> ImageFont.FreeTypeFont:
    if path is None:
        return ImageFont.load_default()
    try:
        return ImageFont.truetype(str(path), size)
    except Exception:
        return ImageFont.load_default()


# Reusable draw surface for measuring text (avoids creating Image per call)
_MEASURE_IMG  = Image.new("RGB", (1, 1))
_MEASURE_DRAW = ImageDraw.Draw(_MEASURE_IMG)


def text_size(text: str, font) -> tuple[int, int]:
    """Return (width, height) pixel dimensions of rendered text."""
    bbox = _MEASURE_DRAW.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]
