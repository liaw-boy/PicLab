from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional


class TemplateStyle(Enum):
    CLASSIC = "classic"    # White border + EXIF strip at bottom
    ROUNDED = "rounded"    # Equal border + rounded photo corners + EXIF below
    SPLIT   = "split"      # Left info panel + right photo (PS-boot style)


class AspectRatioPreset(Enum):
    SQUARE_1_1      = "1:1"      # Instagram square post
    PORTRAIT_4_5    = "4:5"      # Instagram portrait post (max height)
    LANDSCAPE_191_1 = "1.91:1"  # Instagram landscape post (max width)
    STORIES_9_16    = "9:16"    # Stories / Reels vertical
    PORTRAIT_3_4    = "3:4"     # Tall portrait
    PORTRAIT_2_3    = "2:3"     # Classic photography portrait
    LANDSCAPE_16_9  = "16:9"    # Reels horizontal / widescreen
    LANDSCAPE_5_4   = "5:4"     # Horizontal variant
    FREE            = "Free"


class BorderPreset(Enum):
    THIN = "細"
    MEDIUM = "中"
    THICK = "粗"
    CUSTOM = "自訂"


class LogoStyle(Enum):
    TEXT     = "text"
    BADGE    = "badge"
    WORDMARK = "wordmark"
    LOGO     = "logo"


class TextAlign(Enum):
    LEFT   = "left"
    CENTER = "center"
    RIGHT  = "right"


# Border thickness in pixels at 1080px output width.
# exif_strip 依照參考圖比例設計 (約 strip/width ≈ 3.5–5%):
#   THIN   56/1080 = 5.2%
#   MEDIUM 76/1080 = 7.0%  ← 預設，比參考略大保持可讀性
#   THICK  116/1080 = 10.7%
BORDER_SIZES = {
    BorderPreset.THIN:   {"top": 20, "side": 20, "exif_strip": 56},
    BorderPreset.MEDIUM: {"top": 40, "side": 40, "exif_strip": 76},
    BorderPreset.THICK:  {"top": 80, "side": 80, "exif_strip": 116},
}

# Instagram canvas dimensions (width x height) at 1080px base
ASPECT_RATIO_SIZES: dict[AspectRatioPreset, tuple[int, int] | None] = {
    AspectRatioPreset.SQUARE_1_1:      (1080, 1080),
    AspectRatioPreset.PORTRAIT_4_5:    (1080, 1350),
    AspectRatioPreset.LANDSCAPE_191_1: (1080, 566),
    AspectRatioPreset.STORIES_9_16:    (1080, 1920),
    AspectRatioPreset.PORTRAIT_3_4:    (1080, 1440),
    AspectRatioPreset.PORTRAIT_2_3:    (1080, 1620),
    AspectRatioPreset.LANDSCAPE_16_9:  (1080, 608),
    AspectRatioPreset.LANDSCAPE_5_4:   (1080, 864),
    AspectRatioPreset.FREE:            None,  # computed from photo
}


@dataclass(frozen=True)
class BorderSettings:
    template: TemplateStyle = TemplateStyle.CLASSIC
    aspect_ratio: AspectRatioPreset = AspectRatioPreset.SQUARE_1_1
    border_preset: BorderPreset = BorderPreset.MEDIUM
    custom_top: int = 40
    custom_side: int = 40
    custom_exif_strip: int = 110
    show_logo: bool = False
    show_exif: bool = False
    logo_style: LogoStyle = LogoStyle.LOGO
    logo_brand_override: Optional[str] = None   # None → auto-detect from EXIF
    text_align: TextAlign = TextAlign.CENTER
    custom_logo_path: Optional[Path] = None
    output_format: str = "JPEG"
    jpeg_quality: int = 95
    bg_color: tuple[int, int, int] = (255, 255, 255)  # white
    blur_background: bool = False   # 模糊背景：用照片模糊版本填充邊框區域
    export_long_edge: Optional[int] = 2048
    output_sharpening: bool = True
    split_crop_x: float = 0.5   # SPLIT 版型橫向裁切位置 0.0-1.0
    split_crop_y: float = 0.5   # SPLIT 版型縱向裁切位置 0.0-1.0
    split_zoom:   float = 1.0   # SPLIT 版型縮放（1.0 = fill，>1 = 放大）

    def border_dims(self, output_width: int = 1080) -> dict[str, int]:
        scale = output_width / 1080
        if self.border_preset == BorderPreset.CUSTOM:
            raw = {
                "top": self.custom_top,
                "side": self.custom_side,
                "exif_strip": self.custom_exif_strip,
            }
        else:
            raw = BORDER_SIZES[self.border_preset]
        return {k: max(1, round(v * scale)) for k, v in raw.items()}
