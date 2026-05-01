"""
color_grader.py — float32 全程調色引擎

輸入：PIL.Image（RGB）+ GradeSettings
輸出：PIL.Image（RGB）

所有操作在 numpy float32 [0.0, 1.0] 空間進行，
最後才轉換回 uint8，消除疊加操作的 banding 問題。

處理順序（同 Lightroom）：
  Transform → WB → Exposure → Tone → Curve → HSL →
  Presence → Treatment(B&W) → Split Tone →
  Noise Reduction → Sharpening → Effects → LUT
"""
from __future__ import annotations

import math
import warnings
from typing import Sequence

import numpy as np
from PIL import Image, ImageFilter

from src.models.grade_settings import GradeSettings, CurvePoints


# ─────────────────────────────────────────────────────────────────────────────
# 型別別名
# ─────────────────────────────────────────────────────────────────────────────
F32 = np.ndarray   # float32, shape (H, W, 3), values [0.0, 1.0]


# ─────────────────────────────────────────────────────────────────────────────
# sRGB ↔ Linear 轉換
# ─────────────────────────────────────────────────────────────────────────────

def _to_linear(arr: F32) -> F32:
    """sRGB → linear light (IEC 61966-2-1)."""
    return np.where(arr <= 0.04045, arr / 12.92, ((arr + 0.055) / 1.055) ** 2.4)


def _to_srgb(arr: F32) -> F32:
    """Linear light → sRGB."""
    return np.clip(
        np.where(arr <= 0.0031308, arr * 12.92, 1.055 * arr ** (1.0 / 2.4) - 0.055),
        0.0, 1.0,
    )


# ─────────────────────────────────────────────────────────────────────────────
# 幾何變換
# ─────────────────────────────────────────────────────────────────────────────

def _apply_transform(arr: F32, rotation: float, flip_h: bool, flip_v: bool) -> F32:
    from PIL import ImageOps
    img = Image.fromarray((arr * 255).astype(np.uint8), "RGB")
    if flip_h:
        img = ImageOps.mirror(img)
    if flip_v:
        img = ImageOps.flip(img)
    if rotation != 0.0:
        img = img.rotate(-rotation, expand=True, resample=Image.BICUBIC)
    return np.array(img, dtype=np.float32) / 255.0


# ─────────────────────────────────────────────────────────────────────────────
# 白平衡
# ─────────────────────────────────────────────────────────────────────────────

def _kelvin_multipliers(kelvin: int) -> tuple[float, float, float]:
    temp = kelvin / 100.0
    if temp <= 66:
        r = 255.0
        g = max(0.0, min(255.0, 99.4708025861 * math.log(temp) - 161.1195681661))
        b = 0.0 if temp <= 19 else max(0.0, min(255.0, 138.5177312231 * math.log(temp - 10) - 305.0447927307))
    else:
        r = max(0.0, min(255.0, 329.698727446 * ((temp - 60) ** -0.1332047592)))
        g = max(0.0, min(255.0, 288.1221695283 * ((temp - 60) ** -0.0755148492)))
        b = 255.0
    g = g or 1.0
    return r / g, 1.0, b / g


def _apply_white_balance(arr: F32, temperature: int, tint: int) -> F32:
    tr, tg, tb = _kelvin_multipliers(temperature)
    nr, ng, nb = _kelvin_multipliers(5500)
    mr = tr / nr if nr else 1.0
    mg = tg / ng if ng else 1.0
    mb = tb / nb if nb else 1.0
    tint_f = tint / 100.0
    mr *= (1.0 - tint_f * 0.15)
    mg *= (1.0 + tint_f * 0.10)
    mb *= (1.0 - tint_f * 0.15)
    out = arr.copy()
    out[:, :, 0] = np.clip(arr[:, :, 0] * mr, 0.0, 1.0)
    out[:, :, 1] = np.clip(arr[:, :, 1] * mg, 0.0, 1.0)
    out[:, :, 2] = np.clip(arr[:, :, 2] * mb, 0.0, 1.0)
    return out


# ─────────────────────────────────────────────────────────────────────────────
# 曝光（線性光空間）
# ─────────────────────────────────────────────────────────────────────────────

def _apply_exposure(arr: F32, ev100: int) -> F32:
    """在線性光空間套用曝光（準確模擬相機曝光）。"""
    if ev100 == 0:
        return arr
    factor = 2.0 ** (ev100 / 100.0)
    linear = _to_linear(arr)
    return _to_srgb(np.clip(linear * factor, 0.0, 1.0))


# ─────────────────────────────────────────────────────────────────────────────
# 對比 / 亮部 / 陰影 / 白點 / 黑點
# ─────────────────────────────────────────────────────────────────────────────

def _apply_tone(arr: F32, contrast: int, highlights: int,
                shadows: int, whites: int, blacks: int) -> F32:
    """所有色調操作在 float32 一次完成，無中間 rounding。"""
    v = arr.copy()

    if contrast != 0:
        k = contrast / 100.0
        x = v - 0.5
        if k > 0:
            v = np.clip(0.5 + x + k * x * (1 - np.abs(x) * 2), 0.0, 1.0)
        else:
            v = np.clip(0.5 + x + k * 0.5 * np.sin(np.pi * x * 2), 0.0, 1.0)

    if highlights != 0:
        hi_mask = np.maximum(0.0, (v - 0.5) * 2.0)
        v = np.clip(v + (highlights / 100.0) * hi_mask * (1.0 - v) * 0.5, 0.0, 1.0)

    if shadows != 0:
        sh_mask = np.maximum(0.0, (0.5 - v) * 2.0)
        v = np.clip(v + (shadows / 100.0) * sh_mask * v * 0.5, 0.0, 1.0)

    if whites != 0:
        w_mask = v ** 2
        v = np.clip(v + (whites / 100.0) * w_mask * 0.3, 0.0, 1.0)

    if blacks != 0:
        b_mask = (1.0 - v) ** 2
        v = np.clip(v + (blacks / 100.0) * b_mask * 0.3, 0.0, 1.0)

    return v


# ─────────────────────────────────────────────────────────────────────────────
# 色調曲線（Catmull-Rom，float32）
# ─────────────────────────────────────────────────────────────────────────────

def _curve_fn(curve: CurvePoints):
    """回傳一個把 float32 array 映射到曲線輸出的函式。"""
    pts = sorted(curve.points, key=lambda p: p[0])
    if pts[0][0] > 0.0:
        pts.insert(0, (0.0, pts[0][1]))
    if pts[-1][0] < 1.0:
        pts.append((1.0, pts[-1][1]))

    xs = np.array([p[0] for p in pts], dtype=np.float64)
    ys = np.array([p[1] for p in pts], dtype=np.float64)

    def _evaluate(t_arr: np.ndarray) -> np.ndarray:
        out = np.empty_like(t_arr)
        for seg in range(len(pts) - 1):
            x0, x1 = xs[seg], xs[seg + 1]
            mask = (t_arr >= x0) & (t_arr <= x1)
            if not mask.any():
                continue
            t = t_arr[mask]
            span = x1 - x0
            tt = (t - x0) / span if span else np.zeros_like(t)
            tt2, tt3 = tt * tt, tt * tt * tt
            p0y = ys[max(0, seg - 1)]
            p1y = ys[seg]
            p2y = ys[min(len(pts) - 1, seg + 1)]
            p3y = ys[min(len(pts) - 1, seg + 2)]
            y = 0.5 * (
                2 * p1y
                + (-p0y + p2y) * tt
                + (2*p0y - 5*p1y + 4*p2y - p3y) * tt2
                + (-p0y + 3*p1y - 3*p2y + p3y) * tt3
            )
            out[mask] = np.clip(y, 0.0, 1.0)
        return out

    return _evaluate


def _apply_curve(arr: F32, curve: CurvePoints) -> F32:
    if curve.is_identity():
        return arr
    fn = _curve_fn(curve)
    flat = arr.reshape(-1)
    return fn(flat.astype(np.float64)).astype(np.float32).reshape(arr.shape)


def _apply_channel_curves(arr: F32, cr: CurvePoints, cg: CurvePoints, cb: CurvePoints) -> F32:
    if cr.is_identity() and cg.is_identity() and cb.is_identity():
        return arr
    out = arr.copy()
    if not cr.is_identity():
        out[:, :, 0] = _apply_curve(arr[:, :, 0:1], cr).squeeze()
    if not cg.is_identity():
        out[:, :, 1] = _apply_curve(arr[:, :, 1:2], cg).squeeze()
    if not cb.is_identity():
        out[:, :, 2] = _apply_curve(arr[:, :, 2:3], cb).squeeze()
    return out


# ─────────────────────────────────────────────────────────────────────────────
# HSL
# ─────────────────────────────────────────────────────────────────────────────

_HSL_HUE_CENTERS = np.array([0, 30, 60, 120, 180, 240, 270, 330], dtype=np.float32)
_HSL_HUE_WIDTH   = 45.0


def _apply_hsl(arr: F32,
               hue_shifts: Sequence[int],
               sat_shifts: Sequence[int],
               lum_shifts: Sequence[int]) -> F32:
    if all(v == 0 for v in (*hue_shifts, *sat_shifts, *lum_shifts)):
        return arr

    hsv_img = Image.fromarray((arr * 255).astype(np.uint8), "RGB").convert("HSV")
    hsv = np.array(hsv_img, dtype=np.float32)

    hue_deg = hsv[:, :, 0] * (360.0 / 255.0)
    s_chan  = hsv[:, :, 1]
    v_chan  = hsv[:, :, 2]

    diff = np.abs(hue_deg[np.newaxis] - _HSL_HUE_CENTERS[:, np.newaxis, np.newaxis])
    diff = np.where(diff > 180.0, 360.0 - diff, diff)
    weights = np.maximum(0.0, 1.0 - diff / _HSL_HUE_WIDTH)
    total_w = np.where(weights.sum(0) > 0, weights.sum(0), 1.0)

    hs = np.array(hue_shifts, dtype=np.float32)
    ss = np.array(sat_shifts, dtype=np.float32)
    ls = np.array(lum_shifts, dtype=np.float32)

    dh = (weights * hs[:, np.newaxis, np.newaxis]).sum(0) / total_w
    ds = (weights * ss[:, np.newaxis, np.newaxis]).sum(0) / total_w
    dl = (weights * ls[:, np.newaxis, np.newaxis]).sum(0) / total_w

    new_h = np.mod((hue_deg + dh * 1.8) * (255.0 / 360.0), 256.0)
    new_s = np.clip(s_chan + ds * 2.55, 0, 255)
    new_v = np.clip(v_chan + dl * 2.55, 0, 255)

    out_hsv = np.stack([new_h, new_s, new_v], axis=-1).astype(np.uint8)
    return np.array(Image.fromarray(out_hsv, "HSV").convert("RGB"), dtype=np.float32) / 255.0


# ─────────────────────────────────────────────────────────────────────────────
# Presence：Clarity / Texture / Dehaze
# ─────────────────────────────────────────────────────────────────────────────

def _apply_clarity_texture(arr: F32, clarity: int, texture: int) -> F32:
    result = arr
    if clarity != 0:
        img = Image.fromarray((arr * 255).astype(np.uint8), "RGB")
        blurred = np.array(img.filter(ImageFilter.GaussianBlur(50)), dtype=np.float32) / 255.0
        amount = clarity / 100.0
        if clarity > 0:
            # 提升中間調對比：原圖 + (原圖 - 模糊) * amount
            result = np.clip(arr + (arr - blurred) * amount, 0.0, 1.0)
        else:
            result = np.clip(arr + (blurred - arr) * abs(amount) * 0.6, 0.0, 1.0)

    if texture != 0:
        img = Image.fromarray((result * 255).astype(np.uint8), "RGB")
        blurred = np.array(img.filter(ImageFilter.GaussianBlur(8)), dtype=np.float32) / 255.0
        amount = texture / 100.0
        if texture > 0:
            result = np.clip(result + (result - blurred) * amount * 0.5, 0.0, 1.0)
        else:
            result = np.clip(result + (blurred - result) * abs(amount) * 0.4, 0.0, 1.0)
    return result


def _apply_dehaze(arr: F32, amount: int) -> F32:
    if amount == 0:
        return arr
    t = amount / 100.0
    if amount > 0:
        # 大氣散射近似：提升對比並去除亮部霧氣
        dark_channel = arr.min(axis=2, keepdims=True)
        atm = np.percentile(arr, 95)
        transmission = 1.0 - t * 0.9 * (dark_channel / (atm + 1e-6))
        transmission = np.clip(transmission, 0.1, 1.0)
        result = (arr - atm) / transmission + atm
        return np.clip(result, 0.0, 1.0)
    else:
        # 加霧：往亮灰色靠近
        haze_color = 0.85
        return np.clip(arr + (haze_color - arr) * abs(t) * 0.4, 0.0, 1.0)


# ─────────────────────────────────────────────────────────────────────────────
# Vibrance / Saturation
# ─────────────────────────────────────────────────────────────────────────────

def _apply_vibrance_saturation(arr: F32, vibrance: int, saturation: int) -> F32:
    if vibrance == 0 and saturation == 0:
        return arr

    r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
    maxc = np.maximum(np.maximum(r, g), b)
    minc = np.minimum(np.minimum(r, g), b)
    chroma = maxc - minc
    s = np.where(maxc > 1e-6, chroma / maxc, 0.0)

    if saturation != 0:
        sat_factor = 1.0 + saturation / 100.0
        s = np.clip(s * sat_factor, 0.0, 1.0)

    if vibrance != 0:
        vib = vibrance / 100.0
        # 已飽和的像素受影響較少（保護鮮豔色彩），膚色（暖色調）受保護
        weight = np.clip((1.0 - s) * 1.5, 0.0, 1.5)
        s = np.clip(s + vib * weight * 0.4, 0.0, 1.0)

    # 以新的 s 重建 RGB
    new_chroma = s * maxc
    old_chroma = np.where(chroma > 1e-6, chroma, 1.0)
    scale = new_chroma / old_chroma
    mid = maxc - new_chroma

    r2 = np.where(chroma < 1e-6, maxc, np.where(r == maxc, maxc, np.where(r == minc, mid, mid + (r - minc) * scale)))
    g2 = np.where(chroma < 1e-6, maxc, np.where(g == maxc, maxc, np.where(g == minc, mid, mid + (g - minc) * scale)))
    b2 = np.where(chroma < 1e-6, maxc, np.where(b == maxc, maxc, np.where(b == minc, mid, mid + (b - minc) * scale)))

    return np.clip(np.stack([r2, g2, b2], axis=2), 0.0, 1.0)


# ─────────────────────────────────────────────────────────────────────────────
# B&W 轉換
# ─────────────────────────────────────────────────────────────────────────────

def _apply_bw(arr: F32, bw_mix: Sequence[int]) -> F32:
    r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
    maxc = np.maximum(np.maximum(r, g), b)
    minc = np.minimum(np.minimum(r, g), b)
    delta = maxc - minc

    h = np.zeros_like(r)
    m = delta > 0
    # 計算色相角度
    h[m & (maxc == r)] = (60 * (((g - b) / (delta + 1e-6)) % 6))[m & (maxc == r)]
    h[m & (maxc == g)] = (60 * ((b - r) / (delta + 1e-6) + 2))[m & (maxc == g)]
    h[m & (maxc == b)] = (60 * ((r - g) / (delta + 1e-6) + 4))[m & (maxc == b)]
    h = h % 360

    centers = [0, 30, 60, 120, 180, 240, 280, 320]
    mix_weight = np.zeros_like(r)
    for i, center in enumerate(centers):
        diff = np.minimum(np.abs(h - center), 360 - np.abs(h - center))
        w = np.maximum(0.0, 1.0 - diff / 40.0)
        mix_weight += w * (bw_mix[i] / 100.0)

    lum = 0.2126 * r + 0.7152 * g + 0.0722 * b
    lum = np.clip(lum + mix_weight * 0.2, 0.0, 1.0)
    return np.stack([lum, lum, lum], axis=2)


# ─────────────────────────────────────────────────────────────────────────────
# Split Toning
# ─────────────────────────────────────────────────────────────────────────────

def _hue_to_rgb(hue_deg: int) -> tuple[float, float, float]:
    hf = (hue_deg % 360) / 60.0
    x = 1.0 - abs(hf % 2 - 1)
    if hf < 1:   return (1.0, x, 0.0)
    elif hf < 2: return (x, 1.0, 0.0)
    elif hf < 3: return (0.0, 1.0, x)
    elif hf < 4: return (0.0, x, 1.0)
    elif hf < 5: return (x, 0.0, 1.0)
    else:        return (1.0, 0.0, x)


def _apply_split_tone(arr: F32, h_hue: int, h_sat: int,
                      s_hue: int, s_sat: int, balance: int) -> F32:
    if h_sat == 0 and s_sat == 0:
        return arr
    lum = 0.2126 * arr[:, :, 0] + 0.7152 * arr[:, :, 1] + 0.0722 * arr[:, :, 2]
    bal = balance / 100.0
    h_mask = np.clip((lum - 0.5 + bal * 0.2) * 2.0, 0.0, 1.0)
    s_mask = np.clip((0.5 - lum + bal * 0.2) * 2.0, 0.0, 1.0)

    result = arr.copy()
    if h_sat > 0:
        hr, hg, hb = _hue_to_rgb(h_hue)
        strength = h_sat / 100.0 * 0.25
        result[:, :, 0] = np.clip(result[:, :, 0] + h_mask * (hr - lum) * strength, 0.0, 1.0)
        result[:, :, 1] = np.clip(result[:, :, 1] + h_mask * (hg - lum) * strength, 0.0, 1.0)
        result[:, :, 2] = np.clip(result[:, :, 2] + h_mask * (hb - lum) * strength, 0.0, 1.0)
    if s_sat > 0:
        sr, sg, sb = _hue_to_rgb(s_hue)
        strength = s_sat / 100.0 * 0.25
        result[:, :, 0] = np.clip(result[:, :, 0] + s_mask * (sr - lum) * strength, 0.0, 1.0)
        result[:, :, 1] = np.clip(result[:, :, 1] + s_mask * (sg - lum) * strength, 0.0, 1.0)
        result[:, :, 2] = np.clip(result[:, :, 2] + s_mask * (sb - lum) * strength, 0.0, 1.0)
    return result


# ─────────────────────────────────────────────────────────────────────────────
# 降噪 / 銳化
# ─────────────────────────────────────────────────────────────────────────────

def _apply_noise_reduction(arr: F32, amount: int) -> F32:
    """
    雜色消除：
    - amount 1~40  → 快速 Bilateral filter（保留邊緣）
    - amount 41~100 → Non-Local Means（LR 同等演算法，效果最佳）
    分離亮度雜訊（L 通道）與色彩雜訊（a/b 通道），各自處理。
    """
    if amount == 0:
        return arr

    try:
        import cv2
        uint8 = (arr * 255).astype(np.uint8)
        # 轉 Lab 分離亮度與色彩雜訊
        lab = cv2.cvtColor(uint8, cv2.COLOR_RGB2Lab)
        L, a, b = lab[:, :, 0], lab[:, :, 1], lab[:, :, 2]

        lum_strength = amount / 100.0
        col_strength = lum_strength * 0.5   # 色彩雜訊通常比亮度少

        if amount <= 40:
            # Bilateral：速度快，保留邊緣
            d = max(3, int(lum_strength * 11) | 1)
            sigma = lum_strength * 80
            L_out = cv2.bilateralFilter(L, d, sigma, sigma)
            cs = col_strength * 40
            cd = max(3, int(col_strength * 7) | 1)
            a_out = cv2.bilateralFilter(a, cd, cs, cs)
            b_out = cv2.bilateralFilter(b, cd, cs, cs)
        else:
            # Non-Local Means：最佳品質，適合高 ISO
            h_lum = 3 + lum_strength * 22   # 3~25，與雜訊強度對應
            h_col = 2 + col_strength * 10
            # 亮度 NLM（L 通道）
            L_out = cv2.fastNlMeansDenoising(
                L, None, h=h_lum, templateWindowSize=7, searchWindowSize=21)
            # 色彩 NLM（a/b 通道，單獨處理避免跨通道干擾）
            a_out = cv2.fastNlMeansDenoising(
                a, None, h=h_col, templateWindowSize=7, searchWindowSize=21)
            b_out = cv2.fastNlMeansDenoising(
                b, None, h=h_col, templateWindowSize=7, searchWindowSize=21)

        lab_out = cv2.merge([L_out, a_out, b_out])
        rgb_out = cv2.cvtColor(lab_out, cv2.COLOR_Lab2RGB)
        return rgb_out.astype(np.float32) / 255.0

    except ImportError:
        # Fallback：cv2 不可用時用 Gaussian blur
        radius = amount / 100.0 * 2.5
        img = Image.fromarray((arr * 255).astype(np.uint8), "RGB")
        return np.array(img.filter(ImageFilter.GaussianBlur(radius)), dtype=np.float32) / 255.0


def _apply_sharpening(arr: F32, amount: int, detail_mask: int) -> F32:
    if amount == 0:
        return arr
    f = amount / 100.0
    radius    = 0.5 + f * 1.5
    percent   = int(f * 180)
    threshold = max(0, int((100 - detail_mask) / 10))
    img = Image.fromarray((arr * 255).astype(np.uint8), "RGB")
    sharpened = img.filter(ImageFilter.UnsharpMask(radius=radius, percent=percent, threshold=threshold))
    return np.array(sharpened, dtype=np.float32) / 255.0


# ─────────────────────────────────────────────────────────────────────────────
# Effects：Vignette / Grain
# ─────────────────────────────────────────────────────────────────────────────

def _apply_vignette(arr: F32, amount: int, midpoint: int, feather: int) -> F32:
    if amount == 0:
        return arr
    h, w = arr.shape[:2]
    cx, cy = w / 2.0, h / 2.0
    Y, X = np.ogrid[:h, :w]
    dist = np.sqrt(((X - cx) / cx) ** 2 + ((Y - cy) / cy) ** 2)
    inner = midpoint / 100.0
    outer = inner + max(feather / 100.0, 0.01)
    mask = np.clip((dist - inner) / (outer - inner), 0.0, 1.0)
    factor = 1.0 + (amount / 100.0) * mask * (-0.9)
    return np.clip(arr * factor[:, :, np.newaxis], 0.0, 1.0)


def _apply_grain(arr: F32, amount: int, size: int, roughness: int) -> F32:
    if amount == 0:
        return arr
    h, w = arr.shape[:2]
    scale = max(1, int(size / 10))
    sh, sw = max(1, h // scale), max(1, w // scale)
    rng = np.random.default_rng(42)
    noise_small = rng.standard_normal((sh, sw)).astype(np.float32)
    noise_img = Image.fromarray(
        np.clip((noise_small + 3) / 6 * 255, 0, 255).astype(np.uint8), "L"
    )
    noise_full = (np.array(noise_img.resize((w, h), Image.BILINEAR), dtype=np.float32) / 255.0 - 0.5) * 2.0
    lum = 0.2126 * arr[:, :, 0] + 0.7152 * arr[:, :, 1] + 0.0722 * arr[:, :, 2]
    lum_weight = np.clip(1.0 - abs(lum - 0.5) * roughness / 100.0, 0.0, 1.0)
    intensity = amount / 100.0 * 0.12   # ±12% 最大強度
    noise_scaled = noise_full * intensity * lum_weight
    return np.clip(arr + noise_scaled[:, :, np.newaxis], 0.0, 1.0)


# ─────────────────────────────────────────────────────────────────────────────
# 主入口
# ─────────────────────────────────────────────────────────────────────────────

def apply(img: Image.Image, settings: GradeSettings) -> Image.Image:
    """
    依序套用所有調色步驟，回傳新的 RGB PIL.Image。
    原始圖片不會被修改。整個 pipeline 在 float32 [0,1] 空間執行。
    """
    if settings.is_identity():
        return img.copy()

    # ── 轉換為 float32 [0, 1] ──
    arr: F32 = np.array(img.convert("RGB"), dtype=np.float32) / 255.0

    # 0. 幾何變換
    if settings.rotation != 0.0 or settings.flip_h or settings.flip_v:
        arr = _apply_transform(arr, settings.rotation, settings.flip_h, settings.flip_v)

    # 1. 白平衡
    if settings.wb_temperature != 5500 or settings.wb_tint != 0:
        arr = _apply_white_balance(arr, settings.wb_temperature, settings.wb_tint)

    # 2. 曝光（線性光空間）
    if settings.exposure != 0:
        arr = _apply_exposure(arr, settings.exposure)

    # 3. 對比 / 亮部 / 陰影 / 白點 / 黑點（一次 pass）
    if any(v != 0 for v in (settings.contrast, settings.highlights,
                             settings.shadows, settings.whites, settings.blacks)):
        arr = _apply_tone(arr, settings.contrast, settings.highlights,
                          settings.shadows, settings.whites, settings.blacks)

    # 4. 色調曲線
    if not settings.curve_rgb.is_identity():
        arr = _apply_curve(arr, settings.curve_rgb)

    if not (settings.curve_r.is_identity() and
            settings.curve_g.is_identity() and
            settings.curve_b.is_identity()):
        arr = _apply_channel_curves(arr, settings.curve_r, settings.curve_g, settings.curve_b)

    # 5. HSL
    if (any(v != 0 for v in settings.hsl_hue)
            or any(v != 0 for v in settings.hsl_saturation)
            or any(v != 0 for v in settings.hsl_luminance)):
        arr = _apply_hsl(arr, settings.hsl_hue, settings.hsl_saturation, settings.hsl_luminance)

    # 6. Presence
    if settings.clarity != 0 or settings.texture != 0:
        arr = _apply_clarity_texture(arr, settings.clarity, settings.texture)

    if settings.dehaze != 0:
        arr = _apply_dehaze(arr, settings.dehaze)

    if settings.vibrance != 0 or settings.saturation != 0:
        arr = _apply_vibrance_saturation(arr, settings.vibrance, settings.saturation)

    # 7. B&W
    if settings.treatment == "bw":
        arr = _apply_bw(arr, settings.bw_mix)

    # 8. Split Toning
    if settings.split_highlights_sat != 0 or settings.split_shadows_sat != 0:
        arr = _apply_split_tone(
            arr,
            settings.split_highlights_hue, settings.split_highlights_sat,
            settings.split_shadows_hue, settings.split_shadows_sat,
            settings.split_balance,
        )

    # 9. 降噪
    if settings.noise_reduction > 0:
        arr = _apply_noise_reduction(arr, settings.noise_reduction)

    # 10. 銳化
    if settings.sharpening > 0:
        arr = _apply_sharpening(arr, settings.sharpening, settings.detail_mask)

    # 11. Effects
    if settings.vignette_amount != 0:
        arr = _apply_vignette(arr, settings.vignette_amount,
                              settings.vignette_midpoint, settings.vignette_feather)

    if settings.grain_amount > 0:
        arr = _apply_grain(arr, settings.grain_amount,
                           settings.grain_size, settings.grain_roughness)

    # 12. Film LUT
    if settings.lut_path and settings.lut_opacity > 0:
        try:
            import src.core.lut_engine as _lut_eng
            # LUT engine 需要 PIL Image
            pil_in = Image.fromarray((arr * 255).astype(np.uint8), "RGB")
            lut_data = _lut_eng.load(settings.lut_path)
            pil_out = _lut_eng.apply(pil_in, lut_data, settings.lut_opacity / 100.0)
            arr = np.array(pil_out, dtype=np.float32) / 255.0
        except Exception as e:
            warnings.warn(f"LUT 套用失敗（{settings.lut_path}）：{e}", stacklevel=2)

    # ── 轉換回 uint8 PIL Image（只在最後做一次取整）──
    return Image.fromarray(np.clip(arr * 255, 0, 255).astype(np.uint8), "RGB")
