"""
auto_grade.py — 自動調色參數計算

分析圖片直方圖，回傳建議的 GradeSettings 調整值。
演算法：基於亮度統計（均值、標準差、百分位數）推算各參數。
"""
from __future__ import annotations

import numpy as np
from PIL import Image


def compute_auto_grade(img: Image.Image) -> dict:
    """
    分析圖片，回傳建議的調色參數 dict。
    只調整：exposure, contrast, highlights, shadows, whites, blacks。
    """
    rgb = img.convert("RGB")
    arr = np.array(rgb, dtype=np.float32)

    # 亮度通道（ITU-R BT.601 加權）
    lum = arr[:, :, 0] * 0.299 + arr[:, :, 1] * 0.587 + arr[:, :, 2] * 0.114

    mean = float(np.mean(lum))
    std  = float(np.std(lum))

    p02  = float(np.percentile(lum,  2))    # 暗部代表值
    p98  = float(np.percentile(lum, 98))    # 亮部代表值
    p001 = float(np.percentile(lum,  0.1))  # 黑點
    p999 = float(np.percentile(lum, 99.9))  # 白點

    # ── 曝光：讓中間亮度趨近 128 ─────────────────────────────────────────────
    exposure_raw = (128.0 - mean) / 128.0 * 200.0
    exposure = int(max(-250, min(250, round(exposure_raw / 10) * 10)))

    # ── 對比：標準差太低→加對比，太高→微降 ──────────────────────────────────
    target_std = 52.0
    contrast_raw = (target_std - std) / target_std * 50.0
    contrast = int(max(-60, min(60, round(contrast_raw / 5) * 5)))

    # ── 亮部：p98 太高→壓亮部 ────────────────────────────────────────────────
    if p98 > 235:
        highlights = int(max(-80, round(-(p98 - 235) / 20 * 40)))
    elif p98 < 180:
        highlights = int(min(40, round((180 - p98) / 50 * 30)))
    else:
        highlights = 0

    # ── 陰影：p02 太低→提陰影 ────────────────────────────────────────────────
    if p02 < 25:
        shadows = int(min(60, round((25 - p02) / 25 * 50)))
    elif p02 > 80:
        shadows = int(max(-30, round(-(p02 - 80) / 80 * 20)))
    else:
        shadows = 0

    # ── 白點 / 黑點 ──────────────────────────────────────────────────────────
    whites = int(max(-50, min(50, round((245 - p999) / 245 * -30))))
    blacks = int(max(-50, min(50, round((p001 - 10) / 10 * -20))))

    return {
        "exposure":   exposure,
        "contrast":   contrast,
        "highlights": highlights,
        "shadows":    shadows,
        "whites":     whites,
        "blacks":     blacks,
    }


def compute_auto_wb(img: Image.Image) -> dict:
    """
    自動白平衡：Gray World 假設。
    分析 RGB 均值，推算色溫（Kelvin）和色調（Tint）。
    回傳 {"wb_temperature": int, "wb_tint": int}。
    """
    rgb = img.convert("RGB")
    arr = np.array(rgb, dtype=np.float32)

    avg_r = float(np.mean(arr[:, :, 0]))
    avg_g = float(np.mean(arr[:, :, 1]))
    avg_b = float(np.mean(arr[:, :, 2]))

    # 避免除以零
    if avg_g < 1:
        avg_g = 1.0

    # ── 色溫：根據 R/B 比值推算 ──────────────────────────────────────────────
    # R/B > 1 → 偏暖（色溫高，需降低色溫補償）
    # R/B < 1 → 偏冷（色溫低，需升高色溫補償）
    rb_ratio = avg_r / max(avg_b, 1.0)

    # 對數映射到 Kelvin 範圍
    # rb_ratio ≈ 1.0 → 5500K（日光）
    # rb_ratio > 1.0 → 偏暖場景，需要降溫（<5500K 補償）
    # rb_ratio < 1.0 → 偏冷場景，需要升溫（>5500K 補償）
    import math
    temp_offset = -math.log(rb_ratio) * 3000
    temperature = int(max(2500, min(9500, round((5500 + temp_offset) / 100) * 100)))

    # ── 色調：根據 G 相對於 R+B 均值推算 ─────────────────────────────────────
    # G 偏高 → 偏綠（tint 正值補洋紅）
    # G 偏低 → 偏洋紅（tint 負值補綠）
    rb_avg = (avg_r + avg_b) / 2.0
    g_ratio = avg_g / max(rb_avg, 1.0)
    tint_raw = (g_ratio - 1.0) * 80
    tint = int(max(-80, min(80, round(tint_raw / 5) * 5)))

    return {
        "wb_temperature": temperature,
        "wb_tint": tint,
    }
