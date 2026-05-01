"""
color_grader.py — 純函式調色引擎

輸入：PIL.Image（RGB）+ GradeSettings
輸出：PIL.Image（RGB）

所有操作皆使用 Pillow + numpy（numpy 為 Pillow 隱性依賴，可直接使用）。
處理順序依業界慣例：白平衡 → 曝光 → 曲線 → HSL → 銳化/降噪
"""
from __future__ import annotations

import math
import array
from typing import Sequence

from PIL import Image, ImageFilter, ImageEnhance

from src.models.grade_settings import GradeSettings, CurvePoints


# ─────────────────────────────────────────────────────────────────────────────
# 工具函式
# ─────────────────────────────────────────────────────────────────────────────

def _clamp(v: float, lo: float = 0.0, hi: float = 255.0) -> float:
    return max(lo, min(hi, v))


def _build_lut(curve: CurvePoints) -> array.array:
    """
    從 CurvePoints 建立 256 項整數 LUT（0-255）。
    使用 Catmull-Rom 樣條插值，確保曲線通過所有控制點。
    """
    pts = sorted(curve.points, key=lambda p: p[0])

    # 確保端點存在
    if pts[0][0] > 0.0:
        pts.insert(0, (0.0, pts[0][1]))
    if pts[-1][0] < 1.0:
        pts.append((1.0, pts[-1][1]))

    lut = array.array("B", [0] * 256)

    def _catmull_y(t: float) -> float:
        """在 pts 中找 t 所在區間，並以 Catmull-Rom 計算 y。"""
        # 找到左側控制點索引
        idx = 0
        for i in range(len(pts) - 1):
            if pts[i][0] <= t <= pts[i + 1][0]:
                idx = i
                break

        p0 = pts[max(0, idx - 1)]
        p1 = pts[idx]
        p2 = pts[min(len(pts) - 1, idx + 1)]
        p3 = pts[min(len(pts) - 1, idx + 2)]

        span = p2[0] - p1[0]
        if span == 0:
            return p1[1]
        tt = (t - p1[0]) / span
        tt2 = tt * tt
        tt3 = tt2 * tt

        # Catmull-Rom 公式
        y = (
            0.5 * (
                (2 * p1[1])
                + (-p0[1] + p2[1]) * tt
                + (2*p0[1] - 5*p1[1] + 4*p2[1] - p3[1]) * tt2
                + (-p0[1] + 3*p1[1] - 3*p2[1] + p3[1]) * tt3
            )
        )
        return max(0.0, min(1.0, y))

    for i in range(256):
        t = i / 255.0
        lut[i] = round(_catmull_y(t) * 255)

    return lut


def _apply_lut(img: Image.Image, lut: array.array) -> Image.Image:
    """對 RGB 三通道統一套用 LUT。"""
    r, g, b = img.split()
    r = r.point(lut)
    g = g.point(lut)
    b = b.point(lut)
    return Image.merge("RGB", (r, g, b))


def _apply_channel_luts(
    img: Image.Image,
    lut_r: array.array,
    lut_g: array.array,
    lut_b: array.array,
) -> Image.Image:
    """對 R、G、B 分別套用不同 LUT。"""
    r, g, b = img.split()
    r = r.point(lut_r)
    g = g.point(lut_g)
    b = b.point(lut_b)
    return Image.merge("RGB", (r, g, b))


# ─────────────────────────────────────────────────────────────────────────────
# 白平衡
# ─────────────────────────────────────────────────────────────────────────────

def _kelvin_to_rgb_multipliers(kelvin: int) -> tuple[float, float, float]:
    """
    將色溫（K）轉換為 RGB 倍增係數（白點調整）。
    基於 Tanner Helland 的公式，精度足夠後製用途。
    """
    temp = kelvin / 100.0

    if temp <= 66:
        r = 255.0
        g = max(0.0, min(255.0, 99.4708025861 * math.log(temp) - 161.1195681661))
        if temp <= 19:
            b = 0.0
        else:
            b = max(0.0, min(255.0, 138.5177312231 * math.log(temp - 10) - 305.0447927307))
    else:
        r = max(0.0, min(255.0, 329.698727446 * ((temp - 60) ** -0.1332047592)))
        g = max(0.0, min(255.0, 288.1221695283 * ((temp - 60) ** -0.0755148492)))
        b = 255.0

    # 正規化讓 G=1.0（保持亮度）
    if g > 0:
        nr = r / g
        ng = 1.0
        nb = b / g
    else:
        nr, ng, nb = r / 255, 1.0, b / 255

    return nr, ng, nb


def _apply_white_balance(img: Image.Image, temperature: int, tint: int) -> Image.Image:
    """套用白平衡（色溫 + 色調）。"""
    # 色溫：計算目標白點 vs 中性白點（5500K）的比值
    target_r, target_g, target_b = _kelvin_to_rgb_multipliers(temperature)
    neutral_r, neutral_g, neutral_b = _kelvin_to_rgb_multipliers(5500)

    mr = target_r / neutral_r if neutral_r else 1.0
    mg = target_g / neutral_g if neutral_g else 1.0
    mb = target_b / neutral_b if neutral_b else 1.0

    # 色調（tint）：-100=洋紅(+R+B)，+100=綠(+G)
    tint_f = tint / 100.0
    mr *= (1.0 - tint_f * 0.15)
    mg *= (1.0 + tint_f * 0.10)
    mb *= (1.0 - tint_f * 0.15)

    lut_r = array.array("B", [min(255, round(i * mr)) for i in range(256)])
    lut_g = array.array("B", [min(255, round(i * mg)) for i in range(256)])
    lut_b = array.array("B", [min(255, round(i * mb)) for i in range(256)])

    return _apply_channel_luts(img, lut_r, lut_g, lut_b)


# ─────────────────────────────────────────────────────────────────────────────
# 曝光 / 對比 / 亮部 / 陰影 / 白點 / 黑點
# ─────────────────────────────────────────────────────────────────────────────

def _exposure_lut(exposure_ev100: int) -> array.array:
    """EV × 100 → 256 項 LUT（線性空間近似）。"""
    factor = 2.0 ** (exposure_ev100 / 100.0)
    return array.array("B", [min(255, round(i * factor)) for i in range(256)])


def _contrast_lut(contrast: int) -> array.array:
    """S 型對比曲線，contrast -100~+100。"""
    if contrast == 0:
        return array.array("B", list(range(256)))
    k = contrast / 100.0
    lut = array.array("B")
    for i in range(256):
        x = i / 255.0 - 0.5     # 中心化
        if k > 0:
            y = x + k * x * (1 - abs(x) * 2)
        else:
            y = x + k * 0.5 * math.sin(math.pi * x * 2)
        lut.append(min(255, max(0, round((y + 0.5) * 255))))
    return lut


def _highlights_shadows_lut(highlights: int, shadows: int,
                              whites: int, blacks: int) -> array.array:
    """
    亮部/陰影/白點/黑點 → 分區 LUT。
    亮部：影響 128-255；陰影：影響 0-128；
    白點/黑點：夾緊端點輸出。
    """
    lut = array.array("B")
    for i in range(256):
        v = i / 255.0

        # 亮部（高光區）
        if highlights != 0:
            hi_mask = max(0.0, (v - 0.5) * 2)     # 0→0, 1→1
            v += (highlights / 100.0) * hi_mask * (1 - v) * 0.5

        # 陰影（暗部）
        if shadows != 0:
            sh_mask = max(0.0, (0.5 - v) * 2)     # 0→0, 1→1
            v += (shadows / 100.0) * sh_mask * v * 0.5

        # 白點（壓縮最亮端）
        if whites != 0:
            w_mask = v ** 2
            v += (whites / 100.0) * w_mask * 0.3

        # 黑點（抬升最暗端）
        if blacks != 0:
            b_mask = (1 - v) ** 2
            v += (blacks / 100.0) * b_mask * 0.3

        lut.append(min(255, max(0, round(v * 255))))
    return lut


# ─────────────────────────────────────────────────────────────────────────────
# HSL 調整
# ─────────────────────────────────────────────────────────────────────────────

# HSL 色相區間邊界（度），8 個區間：紅橙黃綠青藍紫洋紅
_HSL_HUE_CENTERS = (0, 30, 60, 120, 180, 240, 270, 330)
_HSL_HUE_WIDTH   = 45.0   # 每個區間的影響半徑（度）


def _hue_weight(hue_deg: float, center: float, width: float) -> float:
    """計算 hue_deg 對某個中心的影響權重（三角形視窗）。"""
    diff = abs(hue_deg - center)
    if diff > 180:
        diff = 360 - diff
    return max(0.0, 1.0 - diff / width)


def _apply_hsl(img: Image.Image,
               hue_shifts: tuple[int, ...],
               sat_shifts: tuple[int, ...],
               lum_shifts: tuple[int, ...]) -> Image.Image:
    """
    HSL 分色相調整（numpy 向量化，支援大圖）。
    對每個像素計算 8 個色相區間的加權混合，批次套用偏移。
    """
    if all(v == 0 for v in hue_shifts + sat_shifts + lum_shifts):
        return img

    import numpy as np

    hsv_img = img.convert("HSV")
    hsv = np.asarray(hsv_img, dtype=np.float32)   # (H, W, 3)  值域 0-255

    h_chan = hsv[:, :, 0]   # 色相 0-255 → 0-360°
    s_chan = hsv[:, :, 1]
    v_chan = hsv[:, :, 2]

    hue_deg = h_chan * (360.0 / 255.0)   # (H, W)

    # 預計算 8 個區間的權重 → (8, H, W)
    centers = np.array(_HSL_HUE_CENTERS, dtype=np.float32)  # (8,)
    # 角度差（處理環繞）
    diff = np.abs(hue_deg[np.newaxis, :, :] - centers[:, np.newaxis, np.newaxis])  # (8,H,W)
    diff = np.where(diff > 180.0, 360.0 - diff, diff)
    weights = np.maximum(0.0, 1.0 - diff / _HSL_HUE_WIDTH)   # (8, H, W) 三角視窗

    total_w = weights.sum(axis=0)   # (H, W)
    safe_w  = np.where(total_w > 0, total_w, 1.0)

    hs = np.array(hue_shifts,  dtype=np.float32)   # (8,)
    ss = np.array(sat_shifts,  dtype=np.float32)
    ls = np.array(lum_shifts,  dtype=np.float32)

    # 加權平均偏移量
    dh = (weights * hs[:, np.newaxis, np.newaxis]).sum(axis=0) / safe_w   # (H,W)
    ds = (weights * ss[:, np.newaxis, np.newaxis]).sum(axis=0) / safe_w
    dl = (weights * ls[:, np.newaxis, np.newaxis]).sum(axis=0) / safe_w

    # 套用偏移
    new_h = np.mod((hue_deg + dh * 1.8) * (255.0 / 360.0), 256.0)
    new_s = (s_chan + ds * 2.55).clip(0, 255)
    new_v = (v_chan + dl * 2.55).clip(0, 255)

    out = np.stack([new_h, new_s, new_v], axis=-1).astype(np.uint8)
    return Image.fromarray(out, mode="HSV").convert("RGB")


# ─────────────────────────────────────────────────────────────────────────────
# 銳化 / 降噪
# ─────────────────────────────────────────────────────────────────────────────

def _apply_sharpening(img: Image.Image, amount: int, detail_mask: int) -> Image.Image:
    """
    Unsharp Mask 銳化。
    amount 0-100 → radius 0.5-2.0, percent 0-200%。
    """
    if amount == 0:
        return img
    f = amount / 100.0
    radius  = 0.5 + f * 1.5
    percent = int(f * 180)
    threshold = max(0, int((100 - detail_mask) / 10))
    return img.filter(ImageFilter.UnsharpMask(radius=radius, percent=percent, threshold=threshold))


def _apply_noise_reduction(img: Image.Image, amount: int) -> Image.Image:
    """
    以 GaussianBlur 近似降噪。
    amount 0-100 → radius 0-2.0。
    """
    if amount == 0:
        return img
    radius = amount / 100.0 * 2.0
    return img.filter(ImageFilter.GaussianBlur(radius=radius))


# ─────────────────────────────────────────────────────────────────────────────
# 主入口
# ─────────────────────────────────────────────────────────────────────────────

def apply(img: Image.Image, settings: GradeSettings) -> Image.Image:
    """
    依序套用所有調色步驟，回傳新的 RGB PIL.Image。
    原始圖片不會被修改。

    處理順序：
      1. 白平衡
      2. 曝光
      3. 對比
      4. 亮部 / 陰影 / 白點 / 黑點
      5. 色調曲線（RGB 通道，再分色）
      6. HSL
      7. 降噪（先降噪再銳化）
      8. 銳化
    """
    if settings.is_identity():
        return img.copy()

    result = img.convert("RGB")

    # 1. 白平衡
    if settings.wb_temperature != 5500 or settings.wb_tint != 0:
        result = _apply_white_balance(result, settings.wb_temperature, settings.wb_tint)

    # 2. 曝光
    if settings.exposure != 0:
        lut = _exposure_lut(settings.exposure)
        result = _apply_lut(result, lut)

    # 3. 對比
    if settings.contrast != 0:
        lut = _contrast_lut(settings.contrast)
        result = _apply_lut(result, lut)

    # 4. 亮部 / 陰影 / 白點 / 黑點
    if any(v != 0 for v in (settings.highlights, settings.shadows,
                             settings.whites, settings.blacks)):
        lut = _highlights_shadows_lut(
            settings.highlights, settings.shadows,
            settings.whites, settings.blacks,
        )
        result = _apply_lut(result, lut)

    # 5. 色調曲線
    if not settings.curve_rgb.is_identity():
        lut = _build_lut(settings.curve_rgb)
        result = _apply_lut(result, lut)

    any_channel = (
        not settings.curve_r.is_identity()
        or not settings.curve_g.is_identity()
        or not settings.curve_b.is_identity()
    )
    if any_channel:
        result = _apply_channel_luts(
            result,
            _build_lut(settings.curve_r),
            _build_lut(settings.curve_g),
            _build_lut(settings.curve_b),
        )

    # 6. HSL
    if (any(v != 0 for v in settings.hsl_hue)
            or any(v != 0 for v in settings.hsl_saturation)
            or any(v != 0 for v in settings.hsl_luminance)):
        result = _apply_hsl(
            result,
            settings.hsl_hue,
            settings.hsl_saturation,
            settings.hsl_luminance,
        )

    # 7. 降噪
    if settings.noise_reduction > 0:
        result = _apply_noise_reduction(result, settings.noise_reduction)

    # 8. 銳化
    if settings.sharpening > 0:
        result = _apply_sharpening(result, settings.sharpening, settings.detail_mask)

    # 9. LUT
    if settings.lut_path and settings.lut_opacity > 0:
        try:
            import src.core.lut_engine as _lut_eng
            lut = _lut_eng.load(settings.lut_path)
            result = _lut_eng.apply(result, lut, settings.lut_opacity / 100.0)
        except Exception as e:
            import warnings
            warnings.warn(f"LUT 套用失敗（{settings.lut_path}）：{e}", stacklevel=2)

    return result
