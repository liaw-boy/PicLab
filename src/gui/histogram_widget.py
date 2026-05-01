"""
histogram_widget.py — RGB 直方圖顯示元件

支援：
  - R / G / B 三色重疊直方圖
  - 亮度（Luminance）灰色直方圖
  - 即時更新（呼叫 update_image(PIL.Image)）
  - 滑鼠懸停顯示游標所在亮度的像素數
"""
from __future__ import annotations

import array
from typing import Optional

from PyQt6.QtWidgets import QWidget, QSizePolicy
from PyQt6.QtCore import Qt, QRect, QRectF, QPointF
from PyQt6.QtGui import (
    QPainter, QColor, QPen, QBrush, QPainterPath, QLinearGradient, QImage,
)

import src.gui.theme as T


def _tm():
    from src.gui.theme_manager import ThemeManager
    return ThemeManager.instance()


def _compute_histogram(img) -> dict[str, list[int]]:
    """
    計算 RGB 各通道直方圖（256 bins）。
    回傳 {"r": [...], "g": [...], "b": [...], "lum": [...]}
    """
    rgb = img.convert("RGB")
    r_hist = [0] * 256
    g_hist = [0] * 256
    b_hist = [0] * 256
    lum_hist = [0] * 256

    # 使用 PIL histogram()（快速，內建 C 實作）
    raw = rgb.histogram()   # 長度 768：R[0-255] G[256-511] B[512-767]
    r_hist = raw[0:256]
    g_hist = raw[256:512]
    b_hist = raw[512:768]

    # 亮度：簡易加權平均
    for v in range(256):
        lum_hist[v] = int(r_hist[v] * 0.299 + g_hist[v] * 0.587 + b_hist[v] * 0.114)

    return {"r": r_hist, "g": g_hist, "b": b_hist, "lum": lum_hist}


class HistogramWidget(QWidget):
    """
    RGB 重疊直方圖。
    固定高度 110px，寬度自適應。
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(110)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._hists: Optional[dict] = None
        self._hover_x: Optional[int] = None
        self.setMouseTracking(True)
        _tm().theme_changed.connect(lambda _: self.update())

    def update_image(self, img) -> None:
        """傳入 PIL.Image，重新計算並重繪直方圖。"""
        if img is None:
            self._hists = None
        else:
            self._hists = _compute_histogram(img)
        self.update()

    def clear(self) -> None:
        self._hists = None
        self.update()

    # ── 滑鼠 ──────────────────────────────────────────────────────────────────

    def mouseMoveEvent(self, e):
        self._hover_x = int(e.position().x())
        self.update()

    def leaveEvent(self, e):
        self._hover_x = None
        self.update()

    # ── 繪製 ─────────────────────────────────────────────────────────────────

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()

        # 背景（跟隨主題）
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(QColor(T.SURFACE_2)))
        p.drawRoundedRect(0, 0, W, H, 6, 6)

        if not self._hists:
            # 空狀態提示
            p.setPen(QPen(QColor(T.TEXT_MUTED)))
            p.setFont(T.ui_font(T.FONT_XS))
            p.drawText(QRect(0, 0, W, H), Qt.AlignmentFlag.AlignCenter, "尚無圖片")
            p.end()
            return

        pad_l, pad_r, pad_t, pad_b = 8, 8, 8, 20
        graph_w = W - pad_l - pad_r
        graph_h = H - pad_t - pad_b

        # 最大值（用於正規化，排除最暗/最亮端的極端值）
        all_vals = (
            self._hists["r"][1:-1]
            + self._hists["g"][1:-1]
            + self._hists["b"][1:-1]
        )
        max_val = max(all_vals) if all_vals else 1
        if max_val == 0:
            max_val = 1

        def _bar_height(v: int) -> float:
            return min(graph_h, (v / max_val) ** 0.6 * graph_h)

        # Lightroom 風格：加色混合直方圖
        # 用 QImage + CompositionMode_Plus 自動產生加色混合
        # R+G=黃, G+B=青, R+B=洋紅, R+G+B=白

        img_w = max(1, int(graph_w))
        img_h = max(1, int(graph_h))
        hist_img = QImage(img_w, img_h, QImage.Format.Format_ARGB32_Premultiplied)
        hist_img.fill(QColor(0, 0, 0, 0))

        # Gaussian 平滑（σ≈3，11-tap 加權核）
        _kernel = [0.02, 0.04, 0.08, 0.12, 0.16, 0.16, 0.16, 0.12, 0.08, 0.04, 0.02]
        _klen = len(_kernel)
        _khalf = _klen // 2

        def _smooth(data: list[int]) -> list[float]:
            out = [0.0] * 256
            for i in range(256):
                s = 0.0
                w = 0.0
                for k in range(_klen):
                    j = i + k - _khalf
                    if 0 <= j < 256:
                        s += data[j] * _kernel[k]
                        w += _kernel[k]
                out[i] = s / w if w > 0 else 0
            return out

        # 純色通道，CompositionMode_Plus 自動加色混合
        channels = [
            (_smooth(self._hists["r"]), QColor(200, 0, 0)),
            (_smooth(self._hists["g"]), QColor(0, 185, 0)),
            (_smooth(self._hists["b"]), QColor(0, 0, 210)),
        ]

        ip = QPainter(hist_img)
        ip.setRenderHint(QPainter.RenderHint.Antialiasing)

        for ch_data, color in channels:
            ip.setCompositionMode(QPainter.CompositionMode.CompositionMode_Plus)
            path = QPainterPath()
            path.moveTo(0, img_h)
            for i in range(256):
                x = i / 255 * img_w
                bh = _bar_height(ch_data[i])
                path.lineTo(x, img_h - bh)
            path.lineTo(img_w, img_h)
            path.closeSubpath()
            ip.setPen(Qt.PenStyle.NoPen)
            ip.setBrush(QBrush(color))
            ip.drawPath(path)

        ip.end()

        p.drawImage(QRectF(pad_l, pad_t, graph_w, graph_h), hist_img)

        # 底部漸層尺標（暗→亮）
        grad = QLinearGradient(pad_l, 0, pad_l + graph_w, 0)
        grad.setColorAt(0.0, QColor(T.SURFACE_3))
        grad.setColorAt(1.0, QColor(T.TEXT_PRIMARY))
        p.setBrush(QBrush(grad))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRect(QRectF(pad_l, pad_t + graph_h + 4, graph_w, 4))

        # 遊標線
        if self._hover_x is not None and pad_l <= self._hover_x <= pad_l + graph_w:
            bin_idx = int((self._hover_x - pad_l) / graph_w * 255)
            bin_idx = max(0, min(255, bin_idx))

            # 垂直線
            p.setPen(QPen(QColor(T.TEXT_MUTED), 1, Qt.PenStyle.DashLine))
            p.drawLine(self._hover_x, pad_t, self._hover_x, pad_t + graph_h)

            # 數值標籤
            r_v = self._hists["r"][bin_idx]
            g_v = self._hists["g"][bin_idx]
            b_v = self._hists["b"][bin_idx]
            label = f"{bin_idx}   R:{r_v}  G:{g_v}  B:{b_v}"
            p.setPen(QPen(QColor(T.TEXT_SECONDARY)))
            p.setFont(T.ui_font(T.FONT_XS))
            lbl_x = self._hover_x + 6 if self._hover_x < W - 120 else self._hover_x - 130
            p.drawText(QRect(lbl_x, pad_t + 2, 130, 14),
                       Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                       label)

        p.end()
