"""
Cinema Cockpit layout — radical UI redesign.

Replaces the classic three-pane editor (left nav | preview | right panel)
with an editorial / cinematic workspace:

  ┌──────────────────────────────────────────────────────┐
  │ ⚪⚪⚪    PicLab Studio          ⌘K  ⚙  ⬆ Share       │  CinemaTopBar (38px)
  ├──────────────────────────────────────────────────────┤
  │                                                      │
  │           ┌──────────────────────────┐               │
  │           │                          │               │
  │           │       HERO PHOTO CARD    │← HeroPhotoCard│
  │           │      (centered, ~70%)    │               │
  │           │                          │               │
  │           └──────────────────────────┘               │
  │                                                      │
  │       ┌─ Light · Color · Detail · Effects ─┐          │  PillTabBar
  │                                                      │
  │       ─────── Exposure ───────  +0.3                 │
  │       ─────── Contrast ───────  +12                  │  InlineControlTray
  │       ─────── Highlights ──────  -8                  │
  │       ─────── Shadows ────────  +5                   │
  │                                                      │
  │   ◀  📷📷📷📷📷📷📷📷📷  ▶                          │  Filmstrip
  └──────────────────────────────────────────────────────┘
"""
from __future__ import annotations
from typing import Optional, Callable

from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QFrame, QLabel,
    QGraphicsDropShadowEffect, QSizePolicy, QSlider,
)
from PyQt6.QtCore import (
    Qt, QSize, QPoint, QPointF, QRect, QRectF, pyqtSignal,
    QPropertyAnimation, QEasingCurve,
)
from PyQt6.QtGui import (
    QPainter, QColor, QBrush, QPen, QFont, QPainterPath, QFontMetrics,
)

import src.gui.theme as T


# ─────────────────────────────────────────────────────────────────────────────
# Color tokens (Cinema Cockpit override of the global theme)
# ─────────────────────────────────────────────────────────────────────────────

C_BG       = "#0E0E0F"
C_SURFACE  = "#1A1A1A"
C_SURFACE2 = "#232325"
C_GOLD     = "#C5A46A"
C_GOLD_DIM = "#8A7A5F"
C_TEXT     = "#F0EAD8"
C_TEXT_MUT = "#7A786E"
C_DARK_INK = "#0E0E0F"


# ─────────────────────────────────────────────────────────────────────────────
# CinemaTopBar — 38px ultrathin
# ─────────────────────────────────────────────────────────────────────────────

class _TrafficLight(QWidget):
    """One small circular traffic light button."""

    clicked = pyqtSignal()
    _SIZE = 13

    def __init__(self, color: str, parent=None):
        super().__init__(parent)
        self._color = QColor(color)
        self._hovered = False
        self.setFixedSize(self._SIZE, self._SIZE)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def enterEvent(self, e):
        self._hovered = True
        self.update()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self._hovered = False
        self.update()
        super().leaveEvent(e)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(e)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        col = self._color.lighter(120) if self._hovered else self._color
        p.setBrush(QBrush(col))
        p.setPen(QPen(col.darker(140), 0.5))
        p.drawEllipse(0, 0, self._SIZE - 1, self._SIZE - 1)
        p.end()


class _PillIconButton(QPushButton):
    """Pill-shaped icon button used in the cinema top bar."""

    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(26)
        self.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {C_GOLD};
                border: 1px solid rgba(197, 164, 106, 100);
                border-radius: 13px;
                padding: 0 12px;
                font-family: 'Inter';
                font-size: 11px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background: rgba(197, 164, 106, 30);
                color: {C_TEXT};
                border-color: {C_GOLD};
            }}
        """)


class CinemaTopBar(QWidget):
    """38px ultrathin bar: traffic lights LEFT, italic wordmark CENTER, pill buttons RIGHT."""

    minimize_requested = pyqtSignal()
    maximize_requested = pyqtSignal()
    close_requested    = pyqtSignal()
    palette_requested  = pyqtSignal()
    settings_requested = pyqtSignal()
    share_requested    = pyqtSignal()

    HEIGHT = 38

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setFixedHeight(self.HEIGHT)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"background: {C_BG};")

        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 0, 14, 0)
        lay.setSpacing(8)

        # Traffic lights LEFT
        red    = _TrafficLight("#FF5F57"); red.clicked.connect(self.close_requested.emit)
        yellow = _TrafficLight("#FEBC2E"); yellow.clicked.connect(self.minimize_requested.emit)
        green  = _TrafficLight("#28C840"); green.clicked.connect(self.maximize_requested.emit)
        for tl in (red, yellow, green):
            lay.addWidget(tl)
        lay.addSpacing(12)

        lay.addStretch(1)

        # Wordmark CENTER (italic Playfair-ish — fall back to italic serif on Linux)
        self._wordmark = QLabel("PicLab Studio")
        f = QFont()
        f.setFamily("Playfair Display, EB Garamond, Bodoni Moda, serif")
        f.setItalic(True)
        f.setPointSize(13)
        f.setWeight(QFont.Weight.Medium)
        self._wordmark.setFont(f)
        self._wordmark.setStyleSheet(f"color: {C_GOLD}; background: transparent;")
        self._wordmark.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        lay.addWidget(self._wordmark)

        lay.addStretch(1)

        # Three pill icon buttons RIGHT
        self.btn_palette = _PillIconButton("⌘K")
        self.btn_palette.clicked.connect(self.palette_requested.emit)
        self.btn_settings = _PillIconButton("⚙")
        self.btn_settings.clicked.connect(self.settings_requested.emit)
        self.btn_share = _PillIconButton("⬆ Share")
        self.btn_share.clicked.connect(self.share_requested.emit)
        for b in (self.btn_palette, self.btn_settings, self.btn_share):
            lay.addWidget(b)


# ─────────────────────────────────────────────────────────────────────────────
# HeroPhotoCard — wraps a content widget with margin + shadow + gold border
# ─────────────────────────────────────────────────────────────────────────────

class HeroPhotoCard(QFrame):
    """Centered card with breathing room — wraps the preview content."""

    def __init__(self, content: QWidget, parent: Optional[QWidget] = None,
                 side_margin: int = 110, top_margin: int = 32,
                 bottom_margin: int = 24):
        super().__init__(parent)
        self._side = side_margin
        self._top = top_margin
        self._bottom = bottom_margin
        self.setStyleSheet(f"background: {C_BG};")

        outer = QHBoxLayout(self)
        outer.setContentsMargins(side_margin, top_margin, side_margin, bottom_margin)
        outer.setSpacing(0)

        # Inner card frame
        self._card = QFrame()
        self._card.setObjectName("HeroCard")
        self._card.setStyleSheet(f"""
            QFrame#HeroCard {{
                background: {C_SURFACE};
                border-radius: 14px;
                border: 1px solid rgba(197, 164, 106, 50);
            }}
        """)
        # Soft drop shadow
        shadow = QGraphicsDropShadowEffect(self._card)
        shadow.setBlurRadius(40)
        shadow.setOffset(0, 12)
        shadow.setColor(QColor(0, 0, 0, 180))
        self._card.setGraphicsEffect(shadow)

        card_lay = QVBoxLayout(self._card)
        card_lay.setContentsMargins(2, 2, 2, 2)
        card_lay.setSpacing(0)
        card_lay.addWidget(content)

        outer.addWidget(self._card)


# ─────────────────────────────────────────────────────────────────────────────
# PillTabBar — horizontal pill-shaped tab bar
# ─────────────────────────────────────────────────────────────────────────────

class PillTabBar(QWidget):
    """Horizontal pill tab bar with active gold-fill state and keyboard hints."""

    tab_changed = pyqtSignal(str)   # emits tab id

    HEIGHT = 56

    def __init__(self, tabs: list[tuple[str, str, str]], parent: Optional[QWidget] = None):
        """tabs: list of (id, label, hint) tuples."""
        super().__init__(parent)
        self._tabs = tabs
        self._active = tabs[0][0] if tabs else ""
        self._hovered: Optional[str] = None
        self._rects: dict[str, QRect] = {}
        self.setFixedHeight(self.HEIGHT)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"background: {C_BG};")

    def active_tab(self) -> str:
        return self._active

    def set_active(self, tab_id: str) -> None:
        if tab_id != self._active and any(t[0] == tab_id for t in self._tabs):
            self._active = tab_id
            self.update()
            self.tab_changed.emit(tab_id)

    def mouseMoveEvent(self, e):
        prev = self._hovered
        new_h = None
        for tid, r in self._rects.items():
            if r.contains(e.pos()):
                new_h = tid
                break
        if new_h != prev:
            self._hovered = new_h
            self.update()
        super().mouseMoveEvent(e)

    def leaveEvent(self, e):
        self._hovered = None
        self.update()
        super().leaveEvent(e)

    def mousePressEvent(self, e):
        if e.button() != Qt.MouseButton.LeftButton:
            return super().mousePressEvent(e)
        for tid, r in self._rects.items():
            if r.contains(e.pos()):
                self.set_active(tid)
                return
        super().mousePressEvent(e)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()

        # Container pill
        n = max(1, len(self._tabs))
        tab_w = 96
        bar_w = tab_w * n + 16
        bar_h = 38
        bx = (W - bar_w) // 2
        by = 6
        bar_rect = QRectF(bx, by, bar_w, bar_h)

        # Bar background
        p.setBrush(QBrush(QColor(C_SURFACE)))
        pen = QPen(QColor(197, 164, 106, 70), 1)
        pen.setCosmetic(True)
        p.setPen(pen)
        p.drawRoundedRect(bar_rect, bar_h / 2, bar_h / 2)

        self._rects.clear()
        # Render each tab
        font_label = QFont("Inter", 10, QFont.Weight.Medium)
        font_hint  = QFont("Inter", 7, QFont.Weight.Medium)

        for i, (tid, label, hint) in enumerate(self._tabs):
            tx = bx + 8 + i * tab_w
            tr = QRect(int(tx), int(by + 4), tab_w, bar_h - 8)
            self._rects[tid] = tr

            is_active = tid == self._active
            is_hover  = tid == self._hovered

            if is_active:
                p.setBrush(QBrush(QColor(C_GOLD)))
                p.setPen(Qt.PenStyle.NoPen)
                p.drawRoundedRect(QRectF(tr), (bar_h - 8) / 2, (bar_h - 8) / 2)
                text_col = QColor(C_DARK_INK)
                weight = QFont.Weight.DemiBold
            elif is_hover:
                p.setBrush(QBrush(QColor(255, 255, 255, 12)))
                p.setPen(Qt.PenStyle.NoPen)
                p.drawRoundedRect(QRectF(tr), (bar_h - 8) / 2, (bar_h - 8) / 2)
                text_col = QColor(C_TEXT)
                weight = QFont.Weight.Medium
            else:
                text_col = QColor(C_TEXT_MUT)
                weight = QFont.Weight.Medium

            font_label.setWeight(weight)
            p.setFont(font_label)
            p.setPen(QPen(text_col))
            p.drawText(tr, Qt.AlignmentFlag.AlignCenter, label)

        # Keyboard hint row below the bar
        p.setFont(font_hint)
        p.setPen(QPen(QColor(C_TEXT_MUT)))
        for i, (tid, label, hint) in enumerate(self._tabs):
            tx = bx + 8 + i * tab_w
            hr = QRect(int(tx), int(by + bar_h + 2), tab_w, 12)
            p.drawText(hr, Qt.AlignmentFlag.AlignCenter, hint)

        p.end()


# ─────────────────────────────────────────────────────────────────────────────
# CinemaSliderRow — horizontal slider row (label / track / value)
# ─────────────────────────────────────────────────────────────────────────────

class CinemaSliderRow(QWidget):
    """One row: italic small-caps label LEFT, gold slider, numeric value RIGHT."""

    value_changed = pyqtSignal(int)

    def __init__(self, label: str, vmin: int, vmax: int, val: int = 0,
                 parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._label = label
        self.setFixedHeight(36)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)

        lbl = QLabel(label)
        lbl.setFixedWidth(86)
        f = QFont("Inter", 10, QFont.Weight.Medium)
        f.setItalic(True)
        lbl.setFont(f)
        lbl.setStyleSheet(f"color: {C_TEXT_MUT}; background: transparent;")
        lay.addWidget(lbl)

        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setRange(vmin, vmax)
        self._slider.setValue(val)
        self._slider.setStyleSheet(f"""
            QSlider::groove:horizontal {{
                background: {C_SURFACE2};
                height: 4px;
                border-radius: 2px;
            }}
            QSlider::sub-page:horizontal {{
                background: {C_GOLD};
                height: 4px;
                border-radius: 2px;
            }}
            QSlider::add-page:horizontal {{
                background: #2A2A2C;
                height: 4px;
                border-radius: 2px;
            }}
            QSlider::handle:horizontal {{
                background: {C_GOLD};
                width: 14px;
                height: 14px;
                border-radius: 7px;
                margin: -5px 0;
                border: 2px solid {C_SURFACE};
            }}
            QSlider::handle:horizontal:hover {{
                background: #D6B57F;
                width: 16px;
                height: 16px;
                border-radius: 8px;
                margin: -6px 0;
            }}
        """)
        self._slider.valueChanged.connect(self._on_changed)
        lay.addWidget(self._slider, 1)

        self._val = QLabel(str(val))
        self._val.setFixedWidth(48)
        vf = QFont("Inter", 11, QFont.Weight.DemiBold)
        self._val.setFont(vf)
        self._val.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._val.setStyleSheet(f"color: {C_GOLD}; background: transparent;")
        lay.addWidget(self._val)

    def _on_changed(self, v: int) -> None:
        sign = "+" if v > 0 else ""
        self._val.setText(f"{sign}{v}")
        self.value_changed.emit(v)

    def value(self) -> int:
        return self._slider.value()

    def set_value(self, v: int) -> None:
        self._slider.setValue(v)


# ─────────────────────────────────────────────────────────────────────────────
# InlineControlTray — horizontal tray that swaps content per active tab
# ─────────────────────────────────────────────────────────────────────────────

class InlineControlTray(QFrame):
    """Wide horizontal panel that morphs based on the active PillTabBar tab."""

    slider_changed = pyqtSignal(str, int)   # (slider_id, value)
    reset_requested = pyqtSignal(str)        # active section id

    HEIGHT = 200

    # Schema: tab id → list of (slider_id, label, min, max, default)
    SCHEMA = {
        "light": [
            ("exposure",   "Exposure",   -100, 100, 0),
            ("contrast",   "Contrast",   -100, 100, 0),
            ("highlights", "Highlights", -100, 100, 0),
            ("shadows",    "Shadows",    -100, 100, 0),
            ("whites",     "Whites",     -100, 100, 0),
            ("blacks",     "Blacks",     -100, 100, 0),
            ("clarity",    "Clarity",    -100, 100, 0),
            ("dehaze",     "Dehaze",     -100, 100, 0),
        ],
        "color": [
            ("temperature", "Temp",       -100, 100, 0),
            ("tint",        "Tint",       -100, 100, 0),
            ("vibrance",    "Vibrance",   -100, 100, 0),
            ("saturation",  "Saturation", -100, 100, 0),
            ("hue_shift",   "Hue Shift",  -100, 100, 0),
            ("split_warm",  "Split Warm", -100, 100, 0),
            ("split_cool",  "Split Cool", -100, 100, 0),
            ("color_mix",   "Color Mix",     0, 100, 0),
        ],
        "detail": [
            ("sharpening", "Sharpen",      0, 100, 25),
            ("radius",     "Radius",       0, 100, 50),
            ("masking",    "Masking",      0, 100, 0),
            ("noise_lum",  "Lum NR",       0, 100, 0),
            ("noise_col",  "Color NR",     0, 100, 25),
            ("texture",    "Texture",   -100, 100, 0),
        ],
        "effects": [
            ("vignette",     "Vignette",   -100, 100, 0),
            ("grain",        "Grain",         0, 100, 0),
            ("grain_size",   "Grain Size",    0, 100, 25),
            ("vignette_mid", "Mid Point",     0, 100, 50),
            ("vignette_round", "Roundness", -100, 100, 0),
            ("post_crop_v",  "Post Vignette",-100, 100, 0),
        ],
        "geometry": [
            ("crop_x",   "Crop X",   -100, 100, 0),
            ("crop_y",   "Crop Y",   -100, 100, 0),
            ("zoom",     "Zoom",        0, 200, 100),
            ("rotate",   "Rotate",   -180, 180, 0),
            ("perspect", "Perspective", -100, 100, 0),
            ("skew",     "Skew",     -100, 100, 0),
        ],
    }

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setFixedHeight(self.HEIGHT)
        self.setObjectName("CinemaTray")
        self.setStyleSheet(f"""
            QFrame#CinemaTray {{
                background: {C_SURFACE};
                border-radius: 14px;
                border: 1px solid rgba(197, 164, 106, 30);
            }}
        """)
        self._active = "light"
        self._sliders: dict[str, CinemaSliderRow] = {}

        self._root = QVBoxLayout(self)
        self._root.setContentsMargins(28, 16, 28, 16)
        self._root.setSpacing(8)

        # Header row: italic section title + reset pill
        self._header = QHBoxLayout()
        self._header.setContentsMargins(0, 0, 0, 0)
        self._title = QLabel("Light")
        f = QFont()
        f.setFamily("Playfair Display, EB Garamond, Bodoni Moda, serif")
        f.setItalic(True)
        f.setPointSize(15)
        f.setWeight(QFont.Weight.Medium)
        self._title.setFont(f)
        self._title.setStyleSheet(f"color: {C_GOLD}; background: transparent;")
        self._header.addWidget(self._title)

        # Gold dot decorator
        self._dot = QLabel("•")
        self._dot.setStyleSheet(f"color: {C_GOLD}; background: transparent; font-size: 18px;")
        self._header.addWidget(self._dot)
        self._header.addStretch(1)

        self._reset = QPushButton("↺ Reset")
        self._reset.setCursor(Qt.CursorShape.PointingHandCursor)
        self._reset.setFixedHeight(24)
        self._reset.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {C_GOLD};
                border: 1px solid rgba(197, 164, 106, 100);
                border-radius: 12px;
                padding: 0 12px;
                font-family: 'Inter';
                font-size: 10px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background: rgba(197, 164, 106, 30);
                color: {C_TEXT};
                border-color: {C_GOLD};
            }}
        """)
        self._reset.clicked.connect(lambda: self.reset_requested.emit(self._active))
        self._header.addWidget(self._reset)
        self._root.addLayout(self._header)

        # Two-column slider grid
        self._grid = QHBoxLayout()
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setSpacing(36)
        self._col_l = QVBoxLayout()
        self._col_l.setContentsMargins(0, 0, 0, 0)
        self._col_l.setSpacing(2)
        self._col_r = QVBoxLayout()
        self._col_r.setContentsMargins(0, 0, 0, 0)
        self._col_r.setSpacing(2)
        self._grid.addLayout(self._col_l, 1)
        self._grid.addLayout(self._col_r, 1)
        self._root.addLayout(self._grid, 1)

        self.set_active("light")

    def _clear_grid(self) -> None:
        for col in (self._col_l, self._col_r):
            while col.count():
                item = col.takeAt(0)
                w = item.widget()
                if w is not None:
                    w.setParent(None)
                    w.deleteLater()
        self._sliders.clear()

    def set_active(self, tab_id: str) -> None:
        schema = self.SCHEMA.get(tab_id)
        if schema is None:
            return
        self._active = tab_id
        self._title.setText(tab_id.capitalize())
        self._clear_grid()

        half = (len(schema) + 1) // 2
        for i, (sid, label, lo, hi, default) in enumerate(schema):
            row = CinemaSliderRow(label, lo, hi, default)
            row.value_changed.connect(lambda v, _id=sid: self.slider_changed.emit(_id, v))
            self._sliders[sid] = row
            target = self._col_l if i < half else self._col_r
            target.addWidget(row)

        # Pad to fill column
        for col in (self._col_l, self._col_r):
            col.addStretch(1)

    def set_slider(self, slider_id: str, value: int) -> None:
        row = self._sliders.get(slider_id)
        if row is not None:
            row.set_value(value)


# ─────────────────────────────────────────────────────────────────────────────
# CinemaFilmstrip — horizontal photo thumbnail strip at very bottom
# ─────────────────────────────────────────────────────────────────────────────

class CinemaFilmstrip(QFrame):
    """Thin horizontal strip with photo thumbnails."""

    photo_selected = pyqtSignal(int)   # index

    HEIGHT = 78

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setFixedHeight(self.HEIGHT)
        self.setStyleSheet(f"background: {C_BG};")
        self._thumbs: list[QColor] = [
            QColor(40 + i * 12, 30 + i * 6, 24 + i * 4) for i in range(8)
        ]
        self._current = 2
        self._rects: list[QRect] = []
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def set_thumbs(self, n: int, current: int = 0) -> None:
        self._thumbs = [
            QColor(45 + i * 8, 32 + i * 4, 20 + i * 3) for i in range(n)
        ]
        self._current = max(0, min(n - 1, current))
        self.update()

    def mousePressEvent(self, e):
        for i, r in enumerate(self._rects):
            if r.contains(e.pos()):
                self._current = i
                self.update()
                self.photo_selected.emit(i)
                return
        super().mousePressEvent(e)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()

        # Compute thumbnail layout
        thumb_w = 56
        thumb_h = 44
        gap = 8
        n = len(self._thumbs)
        total_w = thumb_w * n + gap * (n - 1)
        x0 = (W - total_w) // 2
        y0 = (H - thumb_h) // 2

        self._rects = []
        for i, color in enumerate(self._thumbs):
            x = x0 + i * (thumb_w + gap)
            r = QRect(x, y0, thumb_w, thumb_h)
            self._rects.append(r)

            # Subtle inner gradient
            p.setBrush(QBrush(color))
            if i == self._current:
                pen = QPen(QColor(C_GOLD), 2)
                pen.setCosmetic(True)
                p.setPen(pen)
            else:
                pen = QPen(QColor(255, 255, 255, 30), 1)
                pen.setCosmetic(True)
                p.setPen(pen)
            p.drawRoundedRect(QRectF(r), 6, 6)

        # Chevrons
        p.setPen(QPen(QColor(C_GOLD_DIM)))
        p.setFont(QFont("Inter", 14))
        p.drawText(QRect(x0 - 36, y0, 24, thumb_h),
                   Qt.AlignmentFlag.AlignCenter, "◀")
        p.drawText(QRect(x0 + total_w + 12, y0, 24, thumb_h),
                   Qt.AlignmentFlag.AlignCenter, "▶")
        p.end()
