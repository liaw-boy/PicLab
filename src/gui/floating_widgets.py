"""
Floating overlay widgets — radical redesign components.

These widgets are positioned absolutely on top of the preview panel,
giving the app a cinema/editorial feel instead of classic three-pane layout.

Components:
  - FloatingHistogram: glass-morphic histogram in top-right corner
  - DrawerToggle: floating gold pin button to collapse/expand right panels
  - FloatingDock: bottom-center pill-shaped tool dock
"""
from __future__ import annotations
from typing import Callable, Optional

from PyQt6.QtWidgets import QWidget, QPushButton, QHBoxLayout, QFrame
from PyQt6.QtCore import (
    Qt, QSize, QPoint, QPointF, QRect, QRectF, QPropertyAnimation,
    QEasingCurve, pyqtSignal, pyqtProperty,
)
from PyQt6.QtGui import (
    QPainter, QColor, QBrush, QPen, QFont, QPainterPath, QPolygonF,
)

import src.gui.theme as T


# ─────────────────────────────────────────────────────────────────────────────
# Glass surface helper
# ─────────────────────────────────────────────────────────────────────────────

def _draw_glass_card(p: QPainter, rect: QRect, radius: int = 12,
                     fill_alpha: int = 200, border: bool = True) -> None:
    """Paint a frosted-glass card with subtle gold border."""
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    bg = QColor(28, 28, 30, fill_alpha)
    p.setBrush(QBrush(bg))
    if border:
        pen = QPen(QColor(197, 164, 106, 90), 1)
        pen.setCosmetic(True)
        p.setPen(pen)
    else:
        p.setPen(Qt.PenStyle.NoPen)
    p.drawRoundedRect(QRectF(rect), radius, radius)


# ─────────────────────────────────────────────────────────────────────────────
# DrawerToggle — gold circular pin button
# ─────────────────────────────────────────────────────────────────────────────

class DrawerToggle(QPushButton):
    """Circular toggle button. Gold when expanded, hollow when collapsed."""

    _SIZE = 36

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._expanded = True
        self._hovered = False
        self.setFixedSize(self._SIZE, self._SIZE)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMouseTracking(True)
        self.setToolTip("折疊面板 / 展開面板")
        self.setStyleSheet("background: transparent; border: none;")

    def set_expanded(self, expanded: bool) -> None:
        if self._expanded != expanded:
            self._expanded = expanded
            self.update()

    def is_expanded(self) -> bool:
        return self._expanded

    def enterEvent(self, e):
        self._hovered = True
        self.update()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self._hovered = False
        self.update()
        super().leaveEvent(e)

    def paintEvent(self, _) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W = self.width()
        H = self.height()
        cx, cy = W // 2, H // 2

        # Outer ring
        if self._expanded:
            p.setBrush(QBrush(QColor(T.GOLD)))
            p.setPen(Qt.PenStyle.NoPen)
        else:
            p.setBrush(QBrush(QColor(28, 28, 30, 220)))
            pen = QPen(QColor(T.GOLD), 1.5)
            pen.setCosmetic(True)
            p.setPen(pen)
        p.drawEllipse(QPoint(cx, cy), 14, 14)

        # Chevron arrow (▶ when collapsed → expand, ◀ when expanded → collapse)
        arrow_col = QColor("#1A1A1A") if self._expanded else QColor(T.GOLD)
        pen = QPen(arrow_col, 2, Qt.PenStyle.SolidLine,
                   Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        if self._expanded:
            # ▶  (point right = collapse panel which is on the right)
            poly = QPolygonF([
                QPointF(cx - 3, cy - 5),
                QPointF(cx + 4, cy),
                QPointF(cx - 3, cy + 5),
            ])
        else:
            # ◀
            poly = QPolygonF([
                QPointF(cx + 3, cy - 5),
                QPointF(cx - 4, cy),
                QPointF(cx + 3, cy + 5),
            ])
        p.drawPolyline(poly)

        # Hover halo
        if self._hovered:
            halo = QPen(QColor(T.GOLD), 1)
            halo.setCosmetic(True)
            p.setPen(halo)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QPoint(cx, cy), 17, 17)

        p.end()


# ─────────────────────────────────────────────────────────────────────────────
# FloatingDock — pill-shaped tool launcher at bottom-center
# ─────────────────────────────────────────────────────────────────────────────

class _DockButton(QPushButton):
    """Single tool button inside FloatingDock."""

    def __init__(self, glyph: str, label: str, parent=None):
        super().__init__(parent)
        self._glyph = glyph
        self._label = label
        self._hovered = False
        self._active = False
        self.setFixedSize(46, 46)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMouseTracking(True)
        self.setToolTip(label)
        self.setStyleSheet("background: transparent; border: none;")

    def set_active(self, active: bool) -> None:
        if self._active != active:
            self._active = active
            self.update()

    def enterEvent(self, e):
        self._hovered = True
        self.update()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self._hovered = False
        self.update()
        super().leaveEvent(e)

    def paintEvent(self, _) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()
        cx, cy = W // 2, H // 2

        if self._active:
            p.setBrush(QBrush(QColor(T.GOLD)))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QPoint(cx, cy), 18, 18)
            color = QColor("#1A1A1A")
        elif self._hovered:
            p.setBrush(QBrush(QColor(255, 255, 255, 18)))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QPoint(cx, cy), 18, 18)
            color = QColor(T.GOLD)
        else:
            color = QColor(T.TEXT_SECONDARY)

        p.setPen(QPen(color))
        font = QFont("Inter", 16, QFont.Weight.Medium)
        p.setFont(font)
        p.drawText(QRect(0, 0, W, H),
                   Qt.AlignmentFlag.AlignCenter, self._glyph)
        p.end()


class FloatingDock(QWidget):
    """Bottom-center floating glass dock with tool buttons."""

    tool_clicked = pyqtSignal(str)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._buttons: dict[str, _DockButton] = {}

        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 6, 10, 6)
        lay.setSpacing(2)

        # Tool definitions: (id, glyph, label)
        # Using simple Unicode geometric glyphs — distinctive vs. generic icon fonts
        tools = [
            ("wb",       "◐",  "白平衡"),
            ("exposure", "☀",  "曝光"),
            ("hsl",      "◉",  "HSL"),
            ("curve",    "∿",  "曲線"),
            ("detail",   "◇",  "細節"),
            ("bw",       "◑",  "黑白"),
            ("film",     "▤",  "底片"),
        ]
        for tid, glyph, label in tools:
            btn = _DockButton(glyph, label, self)
            btn.clicked.connect(lambda _=False, t=tid: self.tool_clicked.emit(t))
            lay.addWidget(btn)
            self._buttons[tid] = btn

        self.setFixedHeight(58)
        self.setFixedWidth(46 * len(tools) + 20 + 2 * (len(tools) - 1))

    def set_active(self, tool_id: str) -> None:
        for tid, btn in self._buttons.items():
            btn.set_active(tid == tool_id)

    def paintEvent(self, _) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect().adjusted(0, 0, -1, -1)
        # Pill shape — large radius
        radius = self.height() // 2
        bg = QColor(20, 20, 22, 230)
        p.setBrush(QBrush(bg))
        pen = QPen(QColor(197, 164, 106, 70), 1)
        pen.setCosmetic(True)
        p.setPen(pen)
        p.drawRoundedRect(QRectF(rect), radius, radius)
        p.end()


# ─────────────────────────────────────────────────────────────────────────────
# FloatingHistogram — glass card top-right corner
# ─────────────────────────────────────────────────────────────────────────────

class FloatingHistogram(QFrame):
    """Compact glass-morphic histogram for the cinema overlay."""

    _W = 220
    _H = 110

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setFixedSize(self._W, self._H)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._r = [0.0] * 64
        self._g = [0.0] * 64
        self._b = [0.0] * 64

    def set_data(self, r: list[float], g: list[float], b: list[float]) -> None:
        self._r = r[:64] if len(r) >= 64 else r + [0.0] * (64 - len(r))
        self._g = g[:64] if len(g) >= 64 else g + [0.0] * (64 - len(g))
        self._b = b[:64] if len(b) >= 64 else b + [0.0] * (64 - len(b))
        self.update()

    def paintEvent(self, _) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        _draw_glass_card(p, self.rect(), radius=10, fill_alpha=210)

        # Title strip
        title_rect = QRect(10, 6, self._W - 20, 14)
        p.setPen(QPen(QColor(T.GOLD)))
        p.setFont(QFont("Inter", 9, QFont.Weight.DemiBold))
        p.drawText(title_rect, Qt.AlignmentFlag.AlignLeft, "HISTOGRAM")
        p.drawText(title_rect, Qt.AlignmentFlag.AlignRight, "RGB")

        # Plot area
        plot = QRect(10, 26, self._W - 20, self._H - 36)
        p.setPen(Qt.PenStyle.NoPen)
        bw = plot.width() / 64.0
        max_v = max(max(self._r or [0]), max(self._g or [0]),
                    max(self._b or [0]), 1e-6)

        # Draw R, G, B with screen-blend feel via alpha
        for series, color in [
            (self._r, QColor(220, 90, 90, 180)),
            (self._g, QColor(120, 220, 120, 180)),
            (self._b, QColor(110, 150, 220, 180)),
        ]:
            p.setBrush(QBrush(color))
            for i, v in enumerate(series):
                h = (v / max_v) * plot.height()
                p.drawRect(QRectF(
                    plot.x() + i * bw,
                    plot.bottom() - h,
                    bw - 0.4,
                    h,
                ))
        p.end()
