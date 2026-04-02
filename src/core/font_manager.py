"""
Font manager — discovers system fonts, caches instances.
Supports Latin and CJK (Traditional Chinese) rendering.
"""
from __future__ import annotations
from pathlib import Path
import os
import sys
from functools import lru_cache
from PIL import ImageFont, ImageDraw, Image

_ASSETS   = Path(__file__).parent.parent / "assets" / "fonts"

_SYSTEM_FONTS_DIRS = []
if sys.platform == "win32":
    _SYSTEM_FONTS_DIRS = [Path("C:/Windows/Fonts")]
elif sys.platform == "darwin":
    _SYSTEM_FONTS_DIRS = [Path("/Library/Fonts"), Path("/System/Library/Fonts"), Path(os.path.expanduser("~/Library/Fonts"))]
else:
    _SYSTEM_FONTS_DIRS = [
        Path("/usr/share/fonts"),
        Path("/usr/local/share/fonts"),
        Path(os.path.expanduser("~/.fonts")),
        Path(os.path.expanduser("~/.local/share/fonts")),
    ]

# ── Font search lists ─────────────────────────────────────────────────────────
_REGULAR = [
    "Inter-Regular.ttf",   # Inter — 參考圖片風格最接近的幾何無襯線字體
    "Inter-Medium.ttf",
    "NotoSansTC-Regular.otf",
    "NotoSansTC.ttf",      # Noto Sans TC (CJK + Latin)
    "NotoSansTC-VF.ttf",
    "PingFang.ttc",        # macOS CJK
    "msjh.ttc",            # Microsoft JhengHei (supports CJK)
    "Ubuntu-R.ttf",        # Linux
    "DejaVuSans.ttf",      # Linux
    "NotoSans-Regular.ttf",
    "Roboto-Regular.ttf",
    "segoeui.ttf",
    "Arial.ttf",
]
_BOLD = [
    "Inter-Bold.ttf",
    "Inter-Medium.ttf",
    "NotoSansTC-Bold.otf",
    "NotoSansTC.ttf",
    "NotoSansTC-VF.ttf",
    "PingFang.ttc",
    "msjhbd.ttc",
    "Ubuntu-B.ttf",
    "DejaVuSans-Bold.ttf",
    "NotoSans-Bold.ttf",
    "Roboto-Bold.ttf",
    "segoeuib.ttf",
    "Arialbd.ttf",
]
_LIGHT = [
    "Inter-Light.ttf",
    "Inter-Regular.ttf",
    "NotoSansTC-Light.otf",
    "NotoSansTC.ttf",
    "PingFang.ttc",
    "msjhl.ttc",
    "Ubuntu-L.ttf",
    "NotoSans-Light.ttf",
    "Roboto-Light.ttf",
    "segoeui.ttf",
]
# Fonts explicitly known to support CJK (Traditional Chinese)
_CJK = [
    "NotoSansTC-Regular.otf",
    "NotoSansTC-VF.ttf",
    "NotoSansHK-VF.ttf",
    "PingFang.ttc",
    "msjh.ttc",
    "msjhbd.ttc",
    "msjhl.ttc",
    "wqy-microhei.ttc",    # Linux CJK
    "simsun.ttc",
    "mingliu.ttc",
    "msgothic.ttc",
]


def _find(candidates: list[str]) -> Path | str | None:
    for name in candidates:
        # 1. 優先找專案附帶的 assets
        p = _ASSETS / name
        if p.exists():
            return p
        
        # 2. 找常見的系統根目錄
        for base in _SYSTEM_FONTS_DIRS:
            p = base / name
            if p.exists():
                return p
        
        # 3. 讓 PIL 利用作業系統原生機制尋找 (如 Linux fontconfig)
        try:
            # 若系統底層能讀到，PIL 執行時期不報錯，就直接回傳檔名交由 PIL 處理
            ImageFont.truetype(name, 10)
            return name
        except Exception:
            pass
            
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


def _load(path: Path | str | None, size: int) -> ImageFont.FreeTypeFont:
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
