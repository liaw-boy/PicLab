from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional

# LUT 資產目錄（相對於此檔案的絕對路徑在執行期解析）
import pathlib
LUT_ASSETS_DIR = pathlib.Path(__file__).parent.parent / "assets" / "luts"

# 內建 LUT 列表（顯示名稱 → 檔名）
BUILTIN_LUTS: dict[str, str] = {
    "PROVIA / Standard": "PROVIA.cube",
    "Velvia / Vivid":    "Velvia.cube",
    "ASTIA / Soft":      "ASTIA.cube",
    "Classic Chrome":    "CC.cube",
    "Classic Neg.":      "CN.cube",
    "PRO Neg. Hi":       "PRO_Neg.cube",
    "ETERNA Cinema":     "ETERNA.cube",
    "ETERNA Bleach":     "ETERNA-BB.cube",
    "Reala ACE":         "REALA-ACE.cube",
}


# 曲線控制點：list of (input, output) 各 0.0-1.0
# 預設對角線 = 不調整
_DEFAULT_CURVE: tuple[tuple[float, float], ...] = (
    (0.0, 0.0), (0.5, 0.5), (1.0, 1.0)
)


@dataclass(frozen=True)
class CurvePoints:
    """單一色版曲線控制點。"""
    points: tuple[tuple[float, float], ...] = _DEFAULT_CURVE

    def is_identity(self) -> bool:
        return self.points == _DEFAULT_CURVE


@dataclass(frozen=True)
class GradeSettings:
    """
    調色設定（全部預設值 = 無調整）。

    曝光值單位：EV × 100（整數），例如 +100 = +1 EV。
    色溫單位：Kelvin（2000-10000），預設 5500（日光）。
    色調偏移：-100 to +100（洋紅←→綠）。
    其餘滑桿：-100 to +100，0 = 無調整。
    銳化/降噪：0-100，0 = 不套用。
    """

    # ── 曲線 ──────────────────────────────────────────────────────────────────
    curve_rgb: CurvePoints = field(default_factory=CurvePoints)
    curve_r:   CurvePoints = field(default_factory=CurvePoints)
    curve_g:   CurvePoints = field(default_factory=CurvePoints)
    curve_b:   CurvePoints = field(default_factory=CurvePoints)

    # ── 白平衡 ────────────────────────────────────────────────────────────────
    wb_temperature: int = 5500   # Kelvin
    wb_tint:        int = 0      # -100 (洋紅) ~ +100 (綠)

    # ── 曝光基礎 ──────────────────────────────────────────────────────────────
    exposure:  int = 0    # EV × 100，-300 ~ +300
    contrast:  int = 0    # -100 ~ +100
    highlights:int = 0    # -100 ~ +100
    shadows:   int = 0    # -100 ~ +100
    whites:    int = 0    # -100 ~ +100
    blacks:    int = 0    # -100 ~ +100

    # ── HSL（每個色相 8 個區間）──────────────────────────────────────────────
    # 順序：紅、橙、黃、綠、青、藍、紫、洋紅
    hsl_hue:        tuple[int, ...] = (0,) * 8
    hsl_saturation: tuple[int, ...] = (0,) * 8
    hsl_luminance:  tuple[int, ...] = (0,) * 8

    # ── 細節 ──────────────────────────────────────────────────────────────────
    sharpening:      int = 0    # 0-100
    noise_reduction: int = 0    # 0-100
    detail_mask:     int = 20   # 銳化細節遮罩 0-100

    # ── LUT ───────────────────────────────────────────────────────────────────
    lut_path:    Optional[str] = None   # .cube 檔絕對路徑，None = 不套用
    lut_opacity: int           = 100   # 0-100

    def is_identity(self) -> bool:
        """若所有值皆為預設，則不需要調色處理。"""
        return (
            self.curve_rgb.is_identity()
            and self.curve_r.is_identity()
            and self.curve_g.is_identity()
            and self.curve_b.is_identity()
            and self.wb_temperature == 5500
            and self.wb_tint == 0
            and self.exposure == 0
            and self.contrast == 0
            and self.highlights == 0
            and self.shadows == 0
            and self.whites == 0
            and self.blacks == 0
            and all(v == 0 for v in self.hsl_hue)
            and all(v == 0 for v in self.hsl_saturation)
            and all(v == 0 for v in self.hsl_luminance)
            and self.sharpening == 0
            and self.noise_reduction == 0
            and self.lut_path is None
        )
