"""
TopBar — Paper Wireframe 風格頂部工具列。高度 52px。
所有按鈕使用 QPainter 自訂繪製，風格與左側 LeftNavBar 完全一致。
"""
from __future__ import annotations

from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QLabel, QFrame,
)
from PyQt6.QtCore import Qt, pyqtSignal, QRect, QRectF
from PyQt6.QtGui import (
    QPainter, QColor, QPen, QBrush, QFont, QFontMetrics, QPainterPath,
)

import src.gui.theme as T
from src.models.settings import TemplateStyle


def _tm():
    from src.gui.theme_manager import ThemeManager
    return ThemeManager.instance()


# ── 圖示繪製函式 ──────────────────────────────────────────────────────────────

def _draw_theme_icon(p: QPainter, cx: int, cy: int, col: QColor) -> None:
    """主題切換：半實心圓（◑）"""
    r = 6
    path = QPainterPath()
    path.moveTo(cx, cy - r)
    path.arcTo(QRectF(cx - r, cy - r, r * 2, r * 2), 90, 180)
    path.closeSubpath()
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(col))
    p.drawPath(path)
    pen = QPen(col, 1.5)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawEllipse(QRectF(cx - r, cy - r, r * 2, r * 2))


def _draw_export_icon(p: QPainter, cx: int, cy: int, col: QColor) -> None:
    """匯出：向上箭頭 + 底線"""
    pen = QPen(col, 2, Qt.PenStyle.SolidLine,
               Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.drawLine(cx - 7, cy + 6, cx + 7, cy + 6)
    p.drawLine(cx, cy + 2, cx, cy - 5)
    p.drawLine(cx - 5, cy - 1, cx, cy - 6)
    p.drawLine(cx + 5, cy - 1, cx, cy - 6)


# ── 版型選擇按鈕（文字 Chip，QPainter，可選取）────────────────────────────────

class _TplBtn(QWidget):
    """版型 chip 按鈕 — QPainter 繪製，風格與 _NavBtn 一致。"""
    clicked = pyqtSignal(object)   # emits TemplateStyle value

    def __init__(self, style: TemplateStyle, label: str, parent=None):
        super().__init__(parent)
        self._style = style
        self._label = label
        self._active = False
        self._hovered = False
        self.setFixedSize(80, 32)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        _tm().theme_changed.connect(lambda _: self.update())

    def set_active(self, v: bool) -> None:
        self._active = v
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
            self.clicked.emit(self._style)

    def paintEvent(self, _) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()
        R = T.R_CHIP
        M = 2

        if self._active:
            p.setBrush(QBrush(QColor(T.PRIMARY)))
            p.setPen(QPen(QColor(T.BORDER), 2))
            text_col = QColor(T.TEXT_ON_PRIMARY)
            weight = QFont.Weight.Bold
        elif self._hovered:
            p.setBrush(QBrush(QColor(T.SURFACE_2)))
            p.setPen(QPen(QColor(T.BORDER), 1.5))
            text_col = QColor(T.TEXT_PRIMARY)
            weight = QFont.Weight.Medium
        else:
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(QColor(T.BORDER_LIGHT), 1.5))
            text_col = QColor(T.TEXT_SECONDARY)
            weight = QFont.Weight.Medium

        p.drawRoundedRect(M, M, W - M * 2, H - M * 2, R, R)

        p.setFont(T.ui_font(T.FONT_SM, weight))
        p.setPen(QPen(text_col))
        p.drawText(QRect(0, 0, W, H), Qt.AlignmentFlag.AlignCenter, self._label)
        p.end()


# ── 頂部功能按鈕（圖示 + 文字，QPainter，風格與 _NavBtn 一致）────────────────

class _TopBarBtn(QWidget):
    """頂部工具列按鈕 — 圖示(左) + 文字(右)，QPainter 繪製。"""
    clicked = pyqtSignal()

    _H = 36

    def __init__(self, label: str, draw_fn, primary: bool = False, parent=None):
        super().__init__(parent)
        self._label = label
        self._draw_fn = draw_fn
        self._primary = primary
        self._hovered = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setFixedHeight(self._H)
        w = QFontMetrics(T.ui_font(T.FONT_SM)).horizontalAdvance(label) + 32 + 20
        self.setFixedWidth(max(w, 90))
        _tm().theme_changed.connect(lambda _: self.update())

    def setEnabled(self, enabled: bool) -> None:
        self.setCursor(
            Qt.CursorShape.PointingHandCursor if enabled
            else Qt.CursorShape.ArrowCursor
        )
        super().setEnabled(enabled)
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
        if e.button() == Qt.MouseButton.LeftButton and self.isEnabled():
            self.clicked.emit()

    def paintEvent(self, _) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()
        R = T.R_CHIP
        M = 2

        enabled = self.isEnabled()

        if not enabled:
            p.setBrush(QBrush(QColor(T.SURFACE_2)))
            p.setPen(QPen(QColor(T.BORDER_LIGHT), 1.5))
            icon_col = QColor(T.TEXT_DISABLED)
            text_col = QColor(T.TEXT_DISABLED)
            weight = QFont.Weight.Medium
        elif self._primary:
            bg = QColor(T.PRIMARY_HOVER if self._hovered else T.PRIMARY)
            p.setBrush(QBrush(bg))
            p.setPen(QPen(QColor(T.BORDER), 2))
            icon_col = QColor(T.TEXT_ON_PRIMARY)
            text_col = QColor(T.TEXT_ON_PRIMARY)
            weight = QFont.Weight.Bold
        elif self._hovered:
            p.setBrush(QBrush(QColor(T.SURFACE_2)))
            p.setPen(QPen(QColor(T.BORDER), 1.5))
            icon_col = QColor(T.TEXT_PRIMARY)
            text_col = QColor(T.TEXT_PRIMARY)
            weight = QFont.Weight.Medium
        else:
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(QColor(T.BORDER_LIGHT), 1.5))
            icon_col = QColor(T.TEXT_SECONDARY)
            text_col = QColor(T.TEXT_SECONDARY)
            weight = QFont.Weight.Medium

        p.drawRoundedRect(M, M, W - M * 2, H - M * 2, R, R)

        # 圖示（左側）
        self._draw_fn(p, 18, H // 2, icon_col)

        # 文字標籤（圖示右方）
        p.setFont(T.ui_font(T.FONT_SM, weight))
        p.setPen(QPen(text_col))
        p.drawText(
            QRect(34, 0, W - 38, H),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            self._label,
        )
        p.end()


# ── 頂部工具列 ────────────────────────────────────────────────────────────────

def _draw_link_on(p: QPainter, cx: int, cy: int, col: QColor) -> None:
    """連接狀態：兩個相扣的鏈環（實線）"""
    pen = QPen(col, 2.0, Qt.PenStyle.SolidLine,
               Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    # 左鏈環（水平膠囊形，右側進入右環）
    p.drawRoundedRect(QRectF(cx - 12, cy - 4, 13, 8), 4, 4)
    # 右鏈環（覆蓋左環右側，形成相扣效果）
    p.drawRoundedRect(QRectF(cx - 1, cy - 4, 13, 8), 4, 4)
    # 遮住左環右半多餘的線（用背景色填充中心重疊區）
    overlap_col = QColor(col); overlap_col.setAlpha(0)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(QColor(col)))
    # 在兩環交叉處畫一條實色遮蓋線，產生「環扣」立體感
    bar_pen = QPen(col, 2.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.FlatCap)
    p.setPen(bar_pen)
    p.drawLine(cx - 1, cy - 2, cx - 1, cy + 2)


def _draw_link_off(p: QPainter, cx: int, cy: int, col: QColor) -> None:
    """斷開狀態：兩個分離的鏈環 + 斜線斷口"""
    pen = QPen(col, 2.0, Qt.PenStyle.SolidLine,
               Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    # 左鏈環（向左偏移，留出斷口）
    p.drawRoundedRect(QRectF(cx - 13, cy - 4, 11, 8), 4, 4)
    # 右鏈環（向右偏移）
    p.drawRoundedRect(QRectF(cx + 2, cy - 4, 11, 8), 4, 4)
    # 斷口斜線（代表斷裂）
    slash = QPen(col, 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
    p.setPen(slash)
    p.drawLine(cx - 1, cy + 4, cx + 1, cy - 4)


class _SyncToggleBtn(QWidget):
    """同步所有圖片設定的切換開關，風格與 _TopBarBtn 一致。"""
    toggled = pyqtSignal(bool)

    _H = 36

    def __init__(self, parent=None):
        super().__init__(parent)
        self._on      = False
        self._hovered = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setFixedHeight(self._H)
        fm = QFontMetrics(T.ui_font(T.FONT_SM))
        w = max(fm.horizontalAdvance("設定已連結"),
                fm.horizontalAdvance("設定未連結")) + 32 + 20
        self.setFixedWidth(max(w, 110))
        self.setToolTip("開啟後，更改設定將同步套用至所有照片")
        _tm().theme_changed.connect(lambda _: self.update())

    def is_on(self) -> bool:
        return self._on

    def enterEvent(self, e) -> None:
        self._hovered = True;  self.update(); super().enterEvent(e)

    def leaveEvent(self, e) -> None:
        self._hovered = False; self.update(); super().leaveEvent(e)

    def mousePressEvent(self, e) -> None:
        if e.button() == Qt.MouseButton.LeftButton:
            self._on = not self._on
            self.toggled.emit(self._on)
            self.update()

    def set_on(self, v: bool) -> None:
        self._on = v
        self.update()

    def paintEvent(self, _) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()
        R = T.R_CHIP
        M = 2

        if self._on:
            p.setBrush(QBrush(QColor(T.PRIMARY)))
            p.setPen(QPen(QColor(T.BORDER), 2))
            icon_col = QColor(T.TEXT_ON_PRIMARY)
            text_col = QColor(T.TEXT_ON_PRIMARY)
            weight   = QFont.Weight.Bold
        elif self._hovered:
            p.setBrush(QBrush(QColor(T.SURFACE_2)))
            p.setPen(QPen(QColor(T.BORDER), 1.5))
            icon_col = QColor(T.TEXT_PRIMARY)
            text_col = QColor(T.TEXT_PRIMARY)
            weight   = QFont.Weight.Medium
        else:
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(QColor(T.BORDER_LIGHT), 1.5))
            icon_col = QColor(T.TEXT_SECONDARY)
            text_col = QColor(T.TEXT_SECONDARY)
            weight   = QFont.Weight.Medium

        p.drawRoundedRect(M, M, W - M * 2, H - M * 2, R, R)

        label = "設定已連結" if self._on else "設定未連結"

        # 計算圖示 + 文字的整體寬度，置中對齊
        font = T.ui_font(T.FONT_SM, weight)
        p.setFont(font)
        from PyQt6.QtGui import QFontMetrics
        text_w  = QFontMetrics(font).horizontalAdvance(label)
        icon_w  = 26   # _draw_link_* 圖示寬度約 26px
        gap     = 6
        total_w = icon_w + gap + text_w
        start_x = (W - total_w) // 2

        if self._on:
            _draw_link_on(p, start_x + icon_w // 2, H // 2, icon_col)
        else:
            _draw_link_off(p, start_x + icon_w // 2, H // 2, icon_col)

        p.setPen(QPen(text_col))
        p.drawText(
            QRect(start_x + icon_w + gap, 0, text_w + 2, H),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            label,
        )
        p.end()


class TopBar(QWidget):
    template_changed  = pyqtSignal(object)
    export_requested  = pyqtSignal()
    sync_all_toggled  = pyqtSignal(bool)   # 同步所有圖片設定開關

    _TEMPLATES = [
        (TemplateStyle.CLASSIC, "白邊框"),
        (TemplateStyle.ROUNDED, "圓　角"),
        (TemplateStyle.SPLIT,   "分　割"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("TopBar")
        self.setFixedHeight(52)
        self._selected = TemplateStyle.CLASSIC
        self._build()
        self._apply_style()
        _tm().theme_changed.connect(lambda _: self._apply_style())

    def _build(self) -> None:
        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 0, 16, 0)
        lay.setSpacing(0)

        # App name
        name = QLabel("照片白邊工具")
        name.setObjectName("AppName")
        lay.addWidget(name)
        lay.addSpacing(20)

        # 分隔線
        sep1 = QFrame()
        sep1.setObjectName("BarSep")
        sep1.setFrameShape(QFrame.Shape.VLine)
        sep1.setFixedHeight(28)
        lay.addWidget(sep1)
        lay.addSpacing(16)

        # 版型標籤
        tpl_label = QLabel("版型")
        tpl_label.setObjectName("BarLabel")
        lay.addWidget(tpl_label)
        lay.addSpacing(10)

        # ── 版型按鈕（QPainter chip，間距 8px）──
        self._tpl_btns: list[_TplBtn] = []
        for i, (style, label) in enumerate(self._TEMPLATES):
            btn = _TplBtn(style, label)
            btn.clicked.connect(self._on_template_click)
            self._tpl_btns.append(btn)
            lay.addWidget(btn)
            if i < len(self._TEMPLATES) - 1:
                lay.addSpacing(8)

        self._tpl_btns[0].set_active(True)

        lay.addStretch()

        # ── 主題循環按鈕（QPainter NavBtn 風格）──
        self._theme_btn = _TopBarBtn("切換主題", _draw_theme_icon, primary=False)
        self._theme_btn.clicked.connect(_tm().cycle_theme)
        lay.addWidget(self._theme_btn)
        lay.addSpacing(10)

        # ── 同步所有圖片設定開關 ──
        self._sync_btn = _SyncToggleBtn()
        self._sync_btn.toggled.connect(self.sync_all_toggled)
        lay.addWidget(self._sync_btn)
        lay.addSpacing(10)

        # ── 匯出按鈕（QPainter NavBtn 風格，PRIMARY 配色）──
        self._export_btn = _TopBarBtn("匯出照片", _draw_export_icon, primary=True)
        self._export_btn.setEnabled(False)
        self._export_btn.clicked.connect(self.export_requested)
        lay.addWidget(self._export_btn)

    def _apply_style(self) -> None:
        self.setStyleSheet(f"""
            QWidget#TopBar {{
                background: {T.MENUBAR};
                border-bottom: 2px solid {T.BORDER};
            }}
            QLabel#AppName {{
                color: {T.TEXT_PRIMARY};
                font-size: {T.FONT_LG}px;
                font-weight: 800;
                letter-spacing: 1px;
                background: transparent;
            }}
            QFrame#BarSep {{
                color: {T.BORDER_LIGHT};
                background: {T.BORDER_LIGHT};
                max-width: 1px;
            }}
            QLabel#BarLabel {{
                color: {T.TEXT_SECONDARY};
                font-size: {T.FONT_SM}px;
                font-weight: 700;
                letter-spacing: 0.5px;
                background: transparent;
            }}
        """)

    def _on_template_click(self, style: TemplateStyle) -> None:
        self._selected = style
        for btn in self._tpl_btns:
            btn.set_active(btn._style == style)
        self.template_changed.emit(style)

    def current_template(self) -> TemplateStyle:
        return self._selected

    def set_template(self, style: TemplateStyle) -> None:
        """靜默切換版型按鈕狀態（不觸發 template_changed 信號）。"""
        self._selected = style
        for btn in self._tpl_btns:
            btn.set_active(btn._style == style)

    def enable_export(self, enabled: bool) -> None:
        self._export_btn.setEnabled(enabled)
