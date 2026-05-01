"""
Reusable animated UI components.
All painted/styled widgets connect to ThemeManager for live theme switching.

  AnimatedButton    — colour-transition hover via QVariantAnimation
  GhostButton       — outline secondary button
  SegmentedControl  — iOS-style pill selector
  TemplateCard      — painted layout preview with scale hover
  RatioCard         — painted aspect-ratio thumbnail with scale hover
  SectionHeader     — small uppercase label
"""
from __future__ import annotations
from typing import Any

from PyQt6.QtWidgets import QPushButton, QWidget, QHBoxLayout, QButtonGroup, QLabel, QSizePolicy
from PyQt6.QtCore import (
    Qt, QRectF, pyqtSignal, QVariantAnimation, QEasingCurve,
    QPropertyAnimation, pyqtProperty,
)
from PyQt6.QtGui import QColor, QPainter, QPen, QBrush, QFont

import src.gui.theme as T
from src.models.settings import AspectRatioPreset, TemplateStyle


# ── helpers ───────────────────────────────────────────────────────────────────

def _tm():
    """Lazy import to avoid circular dependency at module load."""
    from src.gui.theme_manager import ThemeManager
    return ThemeManager.instance()


# ── AnimatedButton ─────────────────────────────────────────────────────────────

class AnimatedButton(QPushButton):
    """
    Hover: smooth colour transition via QVariantAnimation.
    Click: brief scale-down pulse (0.96 → 1.0).
    """
    def __init__(
        self, text: str = "", parent=None, *,
        color_normal: str = "",
        color_hover:  str = "",
        text_color:   str = "",
        radius: int        = T.R_BUTTON,
        font_size: int     = T.FONT_MD,
        bold: bool         = True,
        padding: str       = "9px 16px",
    ):
        super().__init__(text, parent)
        self._radius    = radius
        self._font_size = font_size
        self._bold      = bold
        self._padding   = padding
        self._cn        = color_normal or T.PRIMARY
        self._ch        = color_hover  or T.PRIMARY_HOVER
        self._ct        = text_color   or T.TEXT_ON_PRIMARY
        self.setMinimumHeight(34)
        self._cur       = QColor(self._cn)

        # Colour animation
        self._canim = QVariantAnimation(self)
        self._canim.setDuration(T.ANIM_FAST)
        self._canim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._canim.valueChanged.connect(self._apply_color)

        # Scale animation (click pulse)
        self._scale_val: float = 1.0
        self._sanim = QVariantAnimation(self)
        self._sanim.setDuration(90)
        self._sanim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._sanim.valueChanged.connect(self._on_scale)

        self._apply_color(QColor(self._cn))
        _tm().theme_changed.connect(self._on_theme)

    def _apply_color(self, color: QColor) -> None:
        self._cur = color
        w = "700" if self._bold else "500"
        self.setStyleSheet(f"""
            QPushButton {{
                background: {color.name()};
                color: {self._ct};
                border: none;
                border-radius: {T.R_BUTTON}px;
                padding: {self._padding};
                font-family: "{T.ui_font_family()}";
                font-size: {self._font_size}px;
                font-weight: {w};
                letter-spacing: 0.5px;
                text-align: center;
            }}
            QPushButton:disabled {{
                background: {T.SURFACE_2};
                color: {T.TEXT_DISABLED};
                border: none;
            }}
        """)

    def _on_scale(self, v: float) -> None:
        self._scale_val = v
        # Scale via stylesheet font trick isn't possible; use QTransform on paint
        # For simplicity: shrink padding slightly to simulate press
        shrink = max(0, int((1.0 - v) * 3))
        parts  = self._padding.split()
        if len(parts) == 2:
            vp = max(2, int(parts[0].replace("px", "")) - shrink)
            hp = max(4, int(parts[1].replace("px", "")) - shrink)
            pad = f"{vp}px {hp}px"
        else:
            pad = self._padding
        w = "600" if self._bold else "400"
        self.setStyleSheet(f"""
            QPushButton {{
                background: {self._cur.name()};
                color: {self._ct};
                border: none;
                border-radius: {self._radius}px;
                padding: {pad};
                font-size: {self._font_size}px;
                font-weight: {w};
            }}
        """)

    def _on_theme(self, dark: bool) -> None:
        self._cn  = T.PRIMARY if self.__class__ is AnimatedButton else T.SURFACE_2
        self._ch  = T.PRIMARY_HOVER if self.__class__ is AnimatedButton else T.SURFACE_3
        self._apply_color(QColor(self._cn))

    def enterEvent(self, e) -> None:
        if self.isEnabled():
            self._canim.stop()
            self._canim.setStartValue(self._cur)
            self._canim.setEndValue(QColor(self._ch))
            self._canim.start()
        super().enterEvent(e)

    def leaveEvent(self, e) -> None:
        self._canim.stop()
        self._canim.setStartValue(self._cur)
        self._canim.setEndValue(QColor(self._cn))
        self._canim.start()
        super().leaveEvent(e)

    def mousePressEvent(self, e) -> None:
        if e.button() == Qt.MouseButton.LeftButton and self.isEnabled():
            self._sanim.stop()
            self._sanim.setStartValue(1.0)
            self._sanim.setEndValue(0.96)
            self._sanim.start()
        super().mousePressEvent(e)

    def mouseReleaseEvent(self, e) -> None:
        self._sanim.stop()
        self._sanim.setStartValue(self._scale_val)
        self._sanim.setEndValue(1.0)
        self._sanim.start()
        super().mouseReleaseEvent(e)


class GhostButton(AnimatedButton):
    def __init__(self, text: str = "", parent=None, **kw):
        super().__init__(
            text, parent,
            color_normal = T.SURFACE_2,
            color_hover  = T.SURFACE_3,
            text_color   = T.TEXT_PRIMARY,
            **kw,
        )
        self._apply_ghost()

    def _apply_ghost(self) -> None:
        w = "600" if self._bold else "400"
        self.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {T.TEXT_SECONDARY};
                border: 1px solid {T.BORDER};
                border-radius: {T.R_BUTTON}px;
                padding: {self._padding};
                font-size: {self._font_size}px;
                font-weight: {w};
                text-align: center;
            }}
            QPushButton:hover {{
                background: {T.GLASS_2};
                color: {T.TEXT_PRIMARY};
                border-color: {T.BORDER_LIGHT};
            }}
            QPushButton:disabled {{
                color: {T.TEXT_DISABLED};
                border-color: {T.BORDER};
            }}
        """)

    def _apply_color(self, color: QColor) -> None:
        self._cur = color

    def _on_theme(self, dark: bool) -> None:
        self._apply_ghost()


# ── SegmentedControl ───────────────────────────────────────────────────────────

class SegmentedControl(QWidget):
    value_changed = pyqtSignal(object)

    def __init__(self, options: list[tuple[Any, str]], parent=None):
        super().__init__(parent)
        self._options = options
        self._sel = 0
        self._btns: list[QPushButton] = []
        self.setFixedHeight(32)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(2, 2, 2, 2)
        lay.setSpacing(0)
        grp = QButtonGroup(self)
        grp.setExclusive(True)
        for i, (val, lbl) in enumerate(options):
            b = QPushButton(lbl)
            b.setCheckable(True)
            b.setProperty("v", val)
            b.setProperty("i", i)
            if i == 0:
                b.setChecked(True)
            grp.addButton(b, i)
            self._btns.append(b)
            lay.addWidget(b)
        grp.buttonClicked.connect(self._on_click)
        self._refresh()
        _tm().theme_changed.connect(lambda _: self._refresh())

    def _on_click(self, b: QPushButton) -> None:
        self._sel = b.property("i")
        self._refresh()
        self.value_changed.emit(b.property("v"))

    def _refresh(self) -> None:
        # Dark luxury: subtle glass container, gold active state
        self.setStyleSheet(f"""
            QWidget {{
                background: {T.SURFACE_3};
                border: 1px solid {T.BORDER};
                border-radius: {T.R_BUTTON}px;
            }}
        """)
        for i, b in enumerate(self._btns):
            if i == self._sel:
                b.setStyleSheet(f"""
                    QPushButton {{
                        background: {T.GOLD_DIM};
                        color: {T.GOLD};
                        border: none;
                        border-radius: {T.R_BUTTON}px;
                        font-size: {T.FONT_SM}px;
                        font-weight: 600;
                        padding: 2px 8px;
                    }}
                """)
            else:
                b.setStyleSheet(f"""
                    QPushButton {{
                        background: transparent;
                        color: {T.TEXT_MUTED};
                        border: none;
                        border-radius: {T.R_BUTTON}px;
                        font-size: {T.FONT_SM}px;
                        font-weight: 500;
                        padding: 2px 8px;
                    }}
                    QPushButton:hover {{
                        color: {T.TEXT_SECONDARY};
                        background: {T.GLASS_1};
                    }}
                """)

    def set_value(self, val: Any) -> None:
        for i, (v, _) in enumerate(self._options):
            if v == val:
                self._sel = i
                self._btns[i].setChecked(True)
                self._refresh()
                return

    def current_value(self) -> Any:
        return self._options[self._sel][0] if self._options else None


# ── _ScalableCard base ─────────────────────────────────────────────────────────

class _ScalableCard(QWidget):
    """Base class adding a scale hover micro-animation via QPainter transform."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scale:  float = 1.0
        self._sanim = QVariantAnimation(self)
        self._sanim.setDuration(T.ANIM_FAST)
        self._sanim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._sanim.valueChanged.connect(self._on_scale_anim)

    def _on_scale_anim(self, v: float) -> None:
        self._scale = v
        self.update()

    def _scale_animate(self, target: float) -> None:
        self._sanim.stop()
        self._sanim.setStartValue(self._scale)
        self._sanim.setEndValue(target)
        self._sanim.start()

    def _apply_scale(self, painter: QPainter) -> None:
        """Call at the start of paintEvent to apply scale from centre."""
        if abs(self._scale - 1.0) < 0.001:
            return
        W, H = self.width(), self.height()
        painter.translate(W / 2, H / 2)
        painter.scale(self._scale, self._scale)
        painter.translate(-W / 2, -H / 2)

    def enterEvent(self, e) -> None:
        self._scale_animate(1.04)
        super().enterEvent(e)

    def leaveEvent(self, e) -> None:
        self._scale_animate(1.0)
        super().leaveEvent(e)


# ── TemplateCard ───────────────────────────────────────────────────────────────

class TemplateCard(_ScalableCard):
    clicked = pyqtSignal(object)

    def __init__(self, style: TemplateStyle, label: str, parent=None):
        super().__init__(parent)
        self._style    = style
        self._label    = label
        self._selected = False
        self._hovered  = False
        self.setFixedHeight(92)
        self.setMinimumWidth(72)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        _tm().theme_changed.connect(lambda _: self.update())

    def set_selected(self, v: bool) -> None:
        if self._selected != v:
            self._selected = v
            self.update()

    def mousePressEvent(self, e) -> None:
        if e.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._style)

    def enterEvent(self, e) -> None:
        self._hovered = True
        super().enterEvent(e)

    def leaveEvent(self, e) -> None:
        self._hovered = False
        super().leaveEvent(e)

    def paintEvent(self, e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        self._apply_scale(p)

        W, H = self.width(), self.height()
        LH = 20

        if self._selected:
            bg, border, bw = QColor(T.GOLD_DIM),  QColor(T.GOLD),   1.5
        elif self._hovered:
            bg, border, bw = QColor(T.SURFACE_3), QColor(T.BORDER), 1.0
        else:
            bg, border, bw = QColor(T.SURFACE_2), QColor(T.BORDER), 1.0

        p.setPen(QPen(border, bw))
        p.setBrush(QBrush(bg))
        p.drawRoundedRect(QRectF(bw/2, bw/2, W-bw, H-bw), T.R_CARD, T.R_CARD)

        m  = 8
        th = H - LH - m
        tw = W - 2 * m

        if   self._style == TemplateStyle.CLASSIC: self._thumb_classic(p, m, m, tw, th)
        elif self._style == TemplateStyle.ROUNDED: self._thumb_rounded(p, m, m, tw, th)
        elif self._style == TemplateStyle.SPLIT:   self._thumb_split(p, m, m, tw, th)

        p.setFont(T.ui_font(T.FONT_SM, QFont.Weight.Medium))
        p.setPen(QPen(QColor(T.GOLD if self._selected else T.TEXT_SECONDARY)))
        p.drawText(QRectF(0, H-LH, W, LH), Qt.AlignmentFlag.AlignCenter, self._label)
        p.end()

    def _pc(self) -> QColor:
        return QColor(T.GOLD_DIM) if self._selected else QColor(T.SURFACE_3)
    def _pb(self) -> QColor:
        return QColor(T.GOLD) if self._selected else QColor(T.BORDER)

    def _thumb_classic(self, p, x, y, w, h) -> None:
        p.setPen(QPen(self._pb(), 1)); p.setBrush(QBrush(QColor(T.SURFACE if T.is_dark() else "#ffffff")))
        p.drawRect(QRectF(x, y, w, h))
        bdr = max(3, int(w*0.06)); strip = max(4, int(h*0.22))
        p.setBrush(QBrush(self._pc())); p.setPen(Qt.PenStyle.NoPen)
        p.drawRect(QRectF(x+bdr, y+bdr, w-2*bdr, max(1, h-2*bdr-strip)))
        p.setBrush(QBrush(QColor(T.SURFACE_3)))
        p.drawRect(QRectF(x, y+h-strip, w, strip))

    def _thumb_rounded(self, p, x, y, w, h) -> None:
        p.setPen(QPen(self._pb(), 1)); p.setBrush(QBrush(QColor(T.SURFACE if T.is_dark() else "#ffffff")))
        p.drawRect(QRectF(x, y, w, h))
        bdr = max(3, int(w*0.07)); strip = max(3, int(h*0.18))
        pw, ph = max(1, w-2*bdr), max(1, h-2*bdr-strip-2)
        r = max(2, int(min(pw, ph)*0.10))
        p.setBrush(QBrush(self._pc())); p.setPen(QPen(self._pb(), 1))
        p.drawRoundedRect(QRectF(x+bdr, y+bdr, pw, ph), r, r)

    def _thumb_split(self, p, x, y, w, h) -> None:
        p.setBrush(QBrush(QColor(T.SURFACE_3))); p.setPen(Qt.PenStyle.NoPen)
        p.drawRect(QRectF(x, y, w, h))
        lw = max(1, int(w*0.35))
        p.setBrush(QBrush(self._pc())); p.drawRect(QRectF(x, y, lw, h))
        p.setPen(QPen(QColor(T.BORDER_LIGHT), 1))
        p.drawLine(int(x+lw), y, int(x+lw), y+h)
        p.setPen(QPen(QColor(T.TEXT_MUTED), 1))
        for i in range(4):
            ly = y + 4 + i*5
            p.drawLine(x+3, ly, x+lw-3, ly)


# ── RatioCard ──────────────────────────────────────────────────────────────────

_RATIO_DIMS = {
    AspectRatioPreset.SQUARE_1_1:      (1.000, 1.000),
    AspectRatioPreset.PORTRAIT_4_5:    (0.800, 1.000),
    AspectRatioPreset.LANDSCAPE_191_1: (1.000, 0.524),
    AspectRatioPreset.STORIES_9_16:    (0.562, 1.000),
    AspectRatioPreset.PORTRAIT_3_4:    (0.750, 1.000),
    AspectRatioPreset.PORTRAIT_2_3:    (0.667, 1.000),
    AspectRatioPreset.LANDSCAPE_16_9:  (1.000, 0.562),
    AspectRatioPreset.LANDSCAPE_5_4:   (1.000, 0.800),
    AspectRatioPreset.FREE:            (1.000, 0.720),
}


class RatioCard(_ScalableCard):
    clicked = pyqtSignal(object)

    def __init__(self, preset: AspectRatioPreset, label: str, parent=None):
        super().__init__(parent)
        self._preset   = preset
        self._label    = label
        self._selected = False
        self._hovered  = False
        self.setFixedHeight(78)
        self.setMinimumWidth(60)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        _tm().theme_changed.connect(lambda _: self.update())

    def set_selected(self, v: bool) -> None:
        if self._selected != v:
            self._selected = v
            self.update()

    def mousePressEvent(self, e) -> None:
        if e.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._preset)

    def enterEvent(self, e) -> None:
        self._hovered = True
        super().enterEvent(e)

    def leaveEvent(self, e) -> None:
        self._hovered = False
        super().leaveEvent(e)

    def paintEvent(self, e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        self._apply_scale(p)

        W, H = self.width(), self.height()
        LH = 18

        # Dark luxury: gold-dim bg with gold text on selected, subtle surfaces elsewhere
        if self._selected:
            bg       = QColor(T.GOLD_DIM)
            border_c = QColor(T.GOLD)
            bw       = 1.5
            txt_c    = QColor(T.GOLD)
        elif self._hovered:
            bg       = QColor(T.SURFACE_3)
            border_c = QColor(T.BORDER)
            bw       = 1.0
            txt_c    = QColor(T.TEXT_PRIMARY)
        else:
            bg       = QColor(T.SURFACE_2)
            border_c = QColor(T.BORDER)
            bw       = 1.0
            txt_c    = QColor(T.TEXT_SECONDARY)

        p.setPen(QPen(border_c, bw))
        p.setBrush(QBrush(bg))
        p.drawRoundedRect(QRectF(bw/2, bw/2, W-bw, H-bw), T.R_CARD, T.R_CARD)

        # 比例縮圖
        rw, rh = _RATIO_DIMS.get(self._preset, (1.0, 1.0))
        ta_w, ta_h = W-14, H-LH-8
        sc   = min(ta_w/rw, ta_h/rh)
        tw_  = max(3, int(rw*sc*0.72))
        th_  = max(3, int(rh*sc*0.72))
        tx, ty = (W-tw_)//2, 4+(ta_h-th_)//2

        if self._selected:
            thumb_fill   = QColor(T.GOLD)
            thumb_fill.setAlpha(40)
            thumb_border = QColor(T.GOLD)
        else:
            thumb_fill   = QColor(T.SURFACE_3)
            thumb_border = QColor(T.BORDER)

        p.setPen(QPen(thumb_border, 1.2))
        p.setBrush(QBrush(thumb_fill))
        p.drawRoundedRect(QRectF(tx, ty, tw_, th_), 2, 2)

        # 標籤文字
        p.setFont(T.ui_font(T.FONT_SM, QFont.Weight.Bold if self._selected else QFont.Weight.Normal))
        p.setPen(QPen(txt_c))
        p.drawText(QRectF(0, H-LH, W, LH), Qt.AlignmentFlag.AlignCenter, self._label)
        p.end()


# ── ColorSwatch ────────────────────────────────────────────────────────────────

class ColorSwatch(QWidget):
    """Circular colour selector with selection ring."""
    clicked = pyqtSignal(tuple)   # emits (r, g, b)

    _SIZE = 34

    def __init__(self, color: tuple[int, int, int], parent=None):
        super().__init__(parent)
        self._color    = color
        self._selected = False
        self._hovered  = False
        self.setFixedSize(self._SIZE, self._SIZE)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        _tm().theme_changed.connect(lambda _: self.update())

    def set_selected(self, v: bool) -> None:
        if self._selected != v:
            self._selected = v
            self.update()

    def enterEvent(self, e) -> None:
        self._hovered = True
        self.update()
        super().enterEvent(e)

    def leaveEvent(self, e) -> None:
        self._hovered = False
        self.update()
        super().leaveEvent(e)

    def mousePressEvent(self, e) -> None:
        if e.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._color)

    def paintEvent(self, e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        S = self._SIZE

        if self._selected:
            # outer selection ring
            p.setPen(QPen(QColor(T.PRIMARY), 2))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QRectF(1, 1, S - 2, S - 2))
            inner = 5
        elif self._hovered:
            p.setPen(QPen(QColor(T.BORDER_LIGHT), 1.5))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QRectF(0.75, 0.75, S - 1.5, S - 1.5))
            inner = 4
        else:
            inner = 3

        # colour fill circle
        r, g, b = self._color
        p.setPen(QPen(QColor(T.BORDER), 1))
        p.setBrush(QBrush(QColor(r, g, b)))
        p.drawEllipse(QRectF(inner, inner, S - 2 * inner, S - 2 * inner))
        p.end()


# ── BrandButton ────────────────────────────────────────────────────────────────

class BrandButton(QPushButton):
    """Compact checkable button that shows a brand name in brand colour."""

    def __init__(self, label: str, brand_color: tuple[int, int, int], parent=None):
        super().__init__(label, parent)
        self._bc = brand_color
        self.setCheckable(True)
        self.setFixedHeight(28)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._apply()
        _tm().theme_changed.connect(lambda _: self._apply())

    def _apply(self) -> None:
        r, g, b = self._bc
        self.setStyleSheet(f"""
            QPushButton {{
                color: rgb({r},{g},{b});
                background: {T.SURFACE_2};
                border: 1px solid {T.BORDER};
                border-radius: {T.R_INPUT}px;
                font-size: {T.FONT_SM}px;
                font-weight: 700;
                padding: 2px 6px;
            }}
            QPushButton:checked {{
                background: rgba({r},{g},{b},0.18);
                border: 1.5px solid rgb({r},{g},{b});
            }}
            QPushButton:hover:!checked {{
                border-color: {T.BORDER_LIGHT};
                background: {T.SURFACE_3};
            }}
        """)


# ── SectionHeader ──────────────────────────────────────────────────────────────

class SectionHeader(QLabel):
    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self._apply()
        _tm().theme_changed.connect(lambda _: self._apply())

    def _apply(self) -> None:
        self.setStyleSheet(f"""
            QLabel {{
                color: {T.TEXT_MUTED};
                font-size: {T.FONT_XS}px;
                font-weight: 600;
                letter-spacing: 1.5px;
                padding: 0 0 4px 0;
                background: transparent;
                border: none;
                border-bottom: 1px solid {T.BORDER};
            }}
        """)
