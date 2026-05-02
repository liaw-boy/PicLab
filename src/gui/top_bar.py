"""
TopBar — Aurelian Dark 頂部工具列。高度 44px。
全部按鈕使用 QPainter 自訂繪製，零 Qt stylesheet 按鈕依賴。
"""
from __future__ import annotations

from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel, QFrame
from PyQt6.QtCore import Qt, pyqtSignal, QRect, QRectF
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QFont, QPainterPath

import src.gui.theme as T
from src.models.settings import TemplateStyle


def _tm():
    from src.gui.theme_manager import ThemeManager
    return ThemeManager.instance()


# ── Icon painters ──────────────────────────────────────────────────────────────

def _draw_half_circle(p: QPainter, cx: int, cy: int, col: QColor) -> None:
    """外觀按鈕圖示：半實心圓 ◑"""
    r = 6
    path = QPainterPath()
    path.moveTo(cx, cy - r)
    path.arcTo(QRectF(cx - r, cy - r, r * 2, r * 2), 90, 180)
    path.closeSubpath()
    p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(col)); p.drawPath(path)
    p.setPen(QPen(col, 1.5)); p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawEllipse(QRectF(cx - r, cy - r, r * 2, r * 2))


def _draw_export_icon(p: QPainter, cx: int, cy: int, col: QColor) -> None:
    pen = QPen(col, 2, Qt.PenStyle.SolidLine,
               Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.drawLine(cx - 6, cy + 5, cx + 6, cy + 5)
    p.drawLine(cx, cy + 2, cx, cy - 5)
    p.drawLine(cx - 4, cy - 1, cx, cy - 5)
    p.drawLine(cx + 4, cy - 1, cx, cy - 5)


# ── Traffic-light window buttons ───────────────────────────────────────────────

class _WinBtn(QWidget):
    clicked = pyqtSignal()
    _ROLES = {
        "close":    ("#FF5F57", "#E0443E"),
        "minimize": ("#FEBC2E", "#D4A020"),
        "maximize": ("#28C840", "#1DAA32"),
    }
    _D = 13

    def __init__(self, role: str, parent=None):
        super().__init__(parent)
        self._role = role; self._hovered = False
        self.setFixedSize(self._D + 4, self._D + 4)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)

    def enterEvent(self, e) -> None:
        self._hovered = True;  self.update(); super().enterEvent(e)
    def leaveEvent(self, e) -> None:
        self._hovered = False; self.update(); super().leaveEvent(e)
    def mousePressEvent(self, e) -> None:
        if e.button() == Qt.MouseButton.LeftButton: self.clicked.emit()

    def paintEvent(self, _) -> None:
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        cx, cy = self.width() // 2, self.height() // 2; r = self._D // 2
        normal, hover_c = self._ROLES[self._role]
        col = QColor(hover_c if self._hovered else normal)
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(col))
        p.drawEllipse(cx - r, cy - r, self._D, self._D)
        if self._hovered:
            p.setPen(QPen(QColor(0, 0, 0, 90), 1.4,
                          Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            if self._role == "close":
                d = 3
                p.drawLine(cx - d, cy - d, cx + d, cy + d)
                p.drawLine(cx + d, cy - d, cx - d, cy + d)
            elif self._role == "minimize":
                p.drawLine(cx - 3, cy, cx + 3, cy)
            else:
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawRect(cx - 3, cy - 3, 6, 6)
        p.end()


# ── Step tab pill ──────────────────────────────────────────────────────────────

class _StepTab(QWidget):
    clicked = pyqtSignal(int)

    def __init__(self, step: int, label: str, parent=None):
        super().__init__(parent)
        self._step = step; self._label = label
        self._active = self._hovered = False
        self.setFixedSize(68, 30)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        _tm().theme_changed.connect(lambda _: self.update())

    def set_active(self, v: bool) -> None:
        self._active = v; self.update()

    def enterEvent(self, e) -> None:
        self._hovered = True;  self.update(); super().enterEvent(e)
    def leaveEvent(self, e) -> None:
        self._hovered = False; self.update(); super().leaveEvent(e)
    def mousePressEvent(self, e) -> None:
        if e.button() == Qt.MouseButton.LeftButton: self.clicked.emit(self._step)

    def paintEvent(self, _) -> None:
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H, R, M = self.width(), self.height(), 6, 1
        if self._active:
            p.setBrush(QBrush(QColor(T.GOLD))); p.setPen(Qt.PenStyle.NoPen)
            text_col = QColor(T.TEXT_ON_PRIMARY); weight = QFont.Weight.Bold
        elif self._hovered:
            p.setBrush(QBrush(QColor(T.GLASS_2))); p.setPen(QPen(QColor(T.BORDER), 1.0))
            text_col = QColor(T.TEXT_PRIMARY); weight = QFont.Weight.Medium
        else:
            p.setBrush(Qt.BrushStyle.NoBrush); p.setPen(QPen(QColor(T.BORDER), 1.0))
            text_col = QColor("#BBBAC4"); weight = QFont.Weight.Medium
        p.drawRoundedRect(M, M, W - M * 2, H - M * 2, R, R)
        p.setFont(T.ui_font(T.FONT_SM, weight)); p.setPen(QPen(text_col))
        p.drawText(QRect(0, 0, W, H), Qt.AlignmentFlag.AlignCenter, self._label)
        p.end()


# ── Template chip ──────────────────────────────────────────────────────────────

class _TplChip(QWidget):
    clicked = pyqtSignal(object)

    def __init__(self, style: TemplateStyle, label: str, parent=None):
        super().__init__(parent)
        self._style = style; self._label = label
        self._active = self._hovered = False
        self.setFixedSize(64, 28)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        _tm().theme_changed.connect(lambda _: self.update())

    def set_active(self, v: bool) -> None:
        self._active = v; self.update()

    def enterEvent(self, e) -> None:
        self._hovered = True;  self.update(); super().enterEvent(e)
    def leaveEvent(self, e) -> None:
        self._hovered = False; self.update(); super().leaveEvent(e)
    def mousePressEvent(self, e) -> None:
        if e.button() == Qt.MouseButton.LeftButton: self.clicked.emit(self._style)

    def paintEvent(self, _) -> None:
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H, R, M = self.width(), self.height(), 6, 1
        if self._active:
            p.setBrush(QBrush(QColor(T.GOLD))); p.setPen(Qt.PenStyle.NoPen)
            text_col = QColor(T.TEXT_ON_PRIMARY); weight = QFont.Weight.Bold
        elif self._hovered:
            p.setBrush(QBrush(QColor(T.GLASS_2))); p.setPen(QPen(QColor(T.BORDER), 1.0))
            text_col = QColor(T.TEXT_PRIMARY); weight = QFont.Weight.Medium
        else:
            p.setBrush(Qt.BrushStyle.NoBrush); p.setPen(QPen(QColor(T.BORDER), 1.0))
            text_col = QColor(T.TEXT_SECONDARY); weight = QFont.Weight.Medium
        p.drawRoundedRect(M, M, W - M * 2, H - M * 2, R, R)
        p.setFont(T.ui_font(T.FONT_SM, weight)); p.setPen(QPen(text_col))
        p.drawText(QRect(0, 0, W, H), Qt.AlignmentFlag.AlignCenter, self._label)
        p.end()


# ── Generic icon+label button ──────────────────────────────────────────────────

class _IconBtn(QWidget):
    """圖示 + 文字按鈕。primary=金色填充，否則 outlined 樣式。"""
    clicked = pyqtSignal()
    _H = 30

    def __init__(self, label: str, draw_fn, width: int,
                 primary: bool = False, parent=None):
        super().__init__(parent)
        self._label = label; self._draw_fn = draw_fn; self._primary = primary
        self._hovered = False
        self.setFixedSize(width, self._H)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        _tm().theme_changed.connect(lambda _: self.update())

    def setEnabled(self, enabled: bool) -> None:
        self.setCursor(Qt.CursorShape.PointingHandCursor if enabled
                       else Qt.CursorShape.ArrowCursor)
        super().setEnabled(enabled); self.update()

    def enterEvent(self, e) -> None:
        self._hovered = True;  self.update(); super().enterEvent(e)
    def leaveEvent(self, e) -> None:
        self._hovered = False; self.update(); super().leaveEvent(e)
    def mousePressEvent(self, e) -> None:
        if e.button() == Qt.MouseButton.LeftButton and self.isEnabled():
            self.clicked.emit()

    def paintEvent(self, _) -> None:
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H, R, M = self.width(), self.height(), 6, 1
        if not self.isEnabled():
            p.setBrush(Qt.BrushStyle.NoBrush); p.setPen(QPen(QColor(T.BORDER), 1.0))
            icon_col = text_col = QColor(T.TEXT_DISABLED); weight = QFont.Weight.Medium
        elif self._primary:
            bg = QColor(T.PRIMARY_HOVER if self._hovered else T.GOLD)
            p.setBrush(QBrush(bg)); p.setPen(Qt.PenStyle.NoPen)
            icon_col = text_col = QColor(T.TEXT_ON_PRIMARY); weight = QFont.Weight.Bold
        elif self._hovered:
            p.setBrush(QBrush(QColor(T.GLASS_2))); p.setPen(QPen(QColor(T.BORDER), 1.0))
            icon_col = text_col = QColor(T.TEXT_PRIMARY); weight = QFont.Weight.Medium
        else:
            p.setBrush(Qt.BrushStyle.NoBrush); p.setPen(QPen(QColor(T.BORDER), 1.0))
            icon_col = text_col = QColor(T.TEXT_SECONDARY); weight = QFont.Weight.Medium
        p.drawRoundedRect(M, M, W - M * 2, H - M * 2, R, R)
        self._draw_fn(p, 16, H // 2, icon_col)
        p.setFont(T.ui_font(T.FONT_SM, weight)); p.setPen(QPen(text_col))
        p.drawText(QRect(28, 0, W - 32, H),
                   Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                   self._label)
        p.end()


# ── Sync toggle button ─────────────────────────────────────────────────────────

class _SyncBtn(QWidget):
    """同步全部切換按鈕。off=outlined，on=金色邊框+tint 背景。"""
    toggled = pyqtSignal(bool)
    _H = 30

    def __init__(self, parent=None):
        super().__init__(parent)
        self._on = self._hovered = False
        self.setFixedSize(80, self._H)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setToolTip("開啟後，更改設定將同步套用至所有照片")
        _tm().theme_changed.connect(lambda _: self.update())

    def is_on(self) -> bool: return self._on
    def set_on(self, v: bool) -> None: self._on = v; self.update()

    def enterEvent(self, e) -> None:
        self._hovered = True;  self.update(); super().enterEvent(e)
    def leaveEvent(self, e) -> None:
        self._hovered = False; self.update(); super().leaveEvent(e)
    def mousePressEvent(self, e) -> None:
        if e.button() == Qt.MouseButton.LeftButton:
            self._on = not self._on; self.toggled.emit(self._on); self.update()

    def paintEvent(self, _) -> None:
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H, R, M = self.width(), self.height(), 6, 1
        if self._on:
            p.setBrush(QBrush(QColor(T.GOLD_DIM))); p.setPen(QPen(QColor(T.GOLD), 1.0))
            text_col = QColor(T.GOLD); weight = QFont.Weight.Bold
        elif self._hovered:
            p.setBrush(QBrush(QColor(T.GLASS_2))); p.setPen(QPen(QColor(T.BORDER), 1.0))
            text_col = QColor(T.TEXT_PRIMARY); weight = QFont.Weight.Medium
        else:
            p.setBrush(Qt.BrushStyle.NoBrush); p.setPen(QPen(QColor(T.BORDER), 1.0))
            text_col = QColor(T.TEXT_SECONDARY); weight = QFont.Weight.Medium
        p.drawRoundedRect(M, M, W - M * 2, H - M * 2, R, R)
        label = "同步開" if self._on else "同步關"
        p.setFont(T.ui_font(T.FONT_SM, weight)); p.setPen(QPen(text_col))
        p.drawText(QRect(0, 0, W, H), Qt.AlignmentFlag.AlignCenter, label)
        p.end()


# ── Helpers ────────────────────────────────────────────────────────────────────

def _sep() -> QFrame:
    f = QFrame(); f.setObjectName("BarSep")
    f.setFrameShape(QFrame.Shape.VLine); f.setFixedHeight(24)
    return f


# ── TopBar ─────────────────────────────────────────────────────────────────────

class TopBar(QWidget):
    template_changed       = pyqtSignal(object)
    export_requested       = pyqtSignal()
    batch_export_requested = pyqtSignal()
    sync_all_toggled       = pyqtSignal(bool)
    step_changed           = pyqtSignal(int)

    _TEMPLATES = [
        (TemplateStyle.CLASSIC, "經典"),
        (TemplateStyle.ROUNDED, "圓角"),
        (TemplateStyle.SPLIT,   "分割"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("TopBar")
        self.setFixedHeight(44)
        self._selected = TemplateStyle.CLASSIC
        self._step = 1
        self._build()
        self._apply_style()
        _tm().theme_changed.connect(lambda _: self._apply_style())

    def _build(self) -> None:
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 0, 12, 0)
        lay.setSpacing(0)

        # Traffic-light controls
        self._btn_close = _WinBtn("close")
        self._btn_min   = _WinBtn("minimize")
        self._btn_max   = _WinBtn("maximize")
        self._btn_close.clicked.connect(self._on_close)
        self._btn_min.clicked.connect(self._on_minimize)
        self._btn_max.clicked.connect(self._on_maximize)
        lay.addWidget(self._btn_close); lay.addSpacing(8)
        lay.addWidget(self._btn_min);   lay.addSpacing(8)
        lay.addWidget(self._btn_max)

        # Separator + app name
        lay.addSpacing(12); lay.addWidget(_sep()); lay.addSpacing(12)
        name = QLabel("PicLab"); name.setObjectName("AppName")
        lay.addWidget(name)

        # Step tabs
        lay.addSpacing(16)
        self._tab1 = _StepTab(1, "調色"); self._tab2 = _StepTab(2, "加框")
        self._tab1.set_active(True)
        self._tab1.clicked.connect(self._go_step)
        self._tab2.clicked.connect(self._go_step)
        lay.addWidget(self._tab1); lay.addSpacing(6)
        arrow = QLabel("→"); arrow.setObjectName("StepArrow")
        lay.addWidget(arrow); lay.addSpacing(6)
        lay.addWidget(self._tab2)

        # Template area (shown only in step 2)
        self._tpl_sep   = _sep()
        self._tpl_label = QLabel("版型"); self._tpl_label.setObjectName("BarLabel")
        self._tpl_btns: list[_TplChip] = []
        lay.addSpacing(10); lay.addWidget(self._tpl_sep)
        lay.addSpacing(10); lay.addWidget(self._tpl_label); lay.addSpacing(8)
        for i, (style, label) in enumerate(self._TEMPLATES):
            btn = _TplChip(style, label)
            btn.clicked.connect(self._on_template_click)
            self._tpl_btns.append(btn)
            lay.addWidget(btn)
            if i < len(self._TEMPLATES) - 1: lay.addSpacing(6)
        self._tpl_btns[0].set_active(True)
        self._set_template_area_visible(False)

        lay.addStretch()

        # Right: theme / sync / export
        self._theme_btn = _IconBtn("外觀", _draw_half_circle, width=80)
        self._theme_btn.clicked.connect(_tm().cycle_theme)
        lay.addWidget(self._theme_btn)
        lay.addSpacing(8); lay.addWidget(_sep()); lay.addSpacing(8)

        self._sync_btn = _SyncBtn()
        self._sync_btn.toggled.connect(self.sync_all_toggled)
        lay.addWidget(self._sync_btn); lay.addSpacing(8)

        self._batch_btn = _IconBtn("全部匯出", _draw_export_icon, width=90)
        self._batch_btn.setEnabled(False)
        self._batch_btn.clicked.connect(self.batch_export_requested)
        lay.addWidget(self._batch_btn); lay.addSpacing(6)

        self._export_btn = _IconBtn("匯出", _draw_export_icon, width=80, primary=True)
        self._export_btn.setEnabled(False)
        self._export_btn.clicked.connect(self.export_requested)
        lay.addWidget(self._export_btn)

    def _apply_style(self) -> None:
        self.setStyleSheet(f"""
            QWidget#TopBar {{
                background: #222222;
                border-bottom: 1px solid #3E3E3E;
            }}
            QLabel#AppName {{
                color: {T.GOLD};
                font-size: 15px;
                font-weight: 700;
                letter-spacing: 1px;
                background: transparent;
            }}
            QFrame#BarSep {{
                color: #3E3E3E;
                background: #3E3E3E;
                max-width: 1px;
            }}
            QLabel#BarLabel {{
                color: {T.TEXT_SECONDARY};
                font-size: {T.FONT_SM}px;
                font-weight: 700;
                background: transparent;
            }}
            QLabel#StepArrow {{
                color: #7A7888;
                font-size: {T.FONT_BASE}px;
                background: transparent;
            }}
        """)

    def _set_template_area_visible(self, visible: bool) -> None:
        self._tpl_sep.setVisible(visible)
        self._tpl_label.setVisible(visible)
        for btn in self._tpl_btns: btn.setVisible(visible)

    def _on_close(self) -> None:
        w = self.window()
        if w: w.close()

    def _on_minimize(self) -> None:
        w = self.window()
        if w: w.showMinimized()

    def _on_maximize(self) -> None:
        w = self.window()
        if w: w.showNormal() if w.isMaximized() else w.showMaximized()

    def _go_step(self, step: int) -> None:
        self._step = step
        self._tab1.set_active(step == 1)
        self._tab2.set_active(step == 2)
        self._set_template_area_visible(step == 2)
        self.step_changed.emit(step)

    def _on_template_click(self, style: TemplateStyle) -> None:
        self._selected = style
        for btn in self._tpl_btns: btn.set_active(btn._style == style)
        self.template_changed.emit(style)

    # ── Public API ─────────────────────────────────────────────────────────────

    def set_step(self, step: int) -> None:
        """Silent step update — does not emit step_changed."""
        self._step = step
        self._tab1.set_active(step == 1)
        self._tab2.set_active(step == 2)
        self._set_template_area_visible(step == 2)

    def current_template(self) -> TemplateStyle:
        return self._selected

    def set_template(self, style: TemplateStyle) -> None:
        """Silent template update — does not emit template_changed."""
        self._selected = style
        for btn in self._tpl_btns: btn.set_active(btn._style == style)

    def enable_export(self, enabled: bool) -> None:
        self._export_btn.setEnabled(enabled)
        self._batch_btn.setEnabled(enabled)
