"""
LeftNavBar — 重新設計的左側導覽列。
每個按鈕用 QPainter 繪製清晰向量圖示，寬度 72px。
"""
from __future__ import annotations

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QFrame, QSizePolicy, QMenu
from PyQt6.QtCore import Qt, pyqtSignal, QRect, QRectF, QPointF
from PyQt6.QtGui import (
    QPainter, QColor, QPen, QBrush, QFont, QPolygonF,
)

import src.gui.theme as T


def _tm():
    from src.gui.theme_manager import ThemeManager
    return ThemeManager.instance()


# ── 向量圖示繪製函式 ──────────────────────────────────────────────────────────

def _draw_ratio(p: QPainter, cx: int, cy: int, col: QColor) -> None:
    """比例：一個正方形 + 一個直式矩形並排"""
    pen = QPen(col, 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.SquareCap)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    # 左：正方形 1:1
    p.drawRect(cx - 18, cy - 10, 14, 14)
    # 右：直式矩形 4:5
    p.drawRect(cx + 4, cy - 12, 11, 16)


def _draw_border(p: QPainter, cx: int, cy: int, col: QColor) -> None:
    """邊框：外框粗線 + 內部留白"""
    # 外框（粗）
    pen_outer = QPen(col, 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.SquareCap)
    p.setPen(pen_outer)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawRect(cx - 14, cy - 12, 28, 24)
    # 內部虛線（代表邊框空間）
    pen_inner = QPen(col, 1, Qt.PenStyle.DotLine)
    p.setPen(pen_inner)
    p.drawRect(cx - 8, cy - 7, 16, 14)


def _draw_color(p: QPainter, cx: int, cy: int, col: QColor) -> None:
    """顏色：四個色塊 2×2 排列"""
    pen = QPen(col, 1.5)
    p.setPen(pen)
    sz = 9
    gap = 3
    colors_opacity = [0.9, 0.6, 0.4, 0.15]
    positions = [
        (cx - sz - gap//2, cy - sz - gap//2),
        (cx + gap//2,      cy - sz - gap//2),
        (cx - sz - gap//2, cy + gap//2),
        (cx + gap//2,      cy + gap//2),
    ]
    for (x, y), alpha in zip(positions, colors_opacity):
        fill = QColor(col)
        fill.setAlphaF(alpha)
        p.setBrush(QBrush(fill))
        p.drawRoundedRect(QRectF(x, y, sz, sz), 2, 2)


def _draw_brand(p: QPainter, cx: int, cy: int, col: QColor) -> None:
    """品牌：攝影機鏡頭圓圈 + 機身矩形"""
    pen = QPen(col, 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    # 機身
    p.drawRoundedRect(cx - 14, cy - 7, 28, 18, 3, 3)
    # 鏡頭（圓形）
    p.drawEllipse(QRectF(cx - 7, cy - 7 + 2, 14, 14))
    # 快門按鈕（小圓）
    p.setBrush(QBrush(col))
    p.drawEllipse(QRectF(cx + 7, cy - 9, 5, 5))


def _draw_export(p: QPainter, cx: int, cy: int, col: QColor) -> None:
    """匯出：向上箭頭 + 底部橫線"""
    pen = QPen(col, 2.5, Qt.PenStyle.SolidLine,
               Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    # 底線
    p.drawLine(cx - 12, cy + 10, cx + 12, cy + 10)
    # 箭頭竿
    p.drawLine(cx, cy + 6, cx, cy - 8)
    # 箭頭頭
    p.drawLine(cx - 8, cy - 1, cx, cy - 9)
    p.drawLine(cx + 8, cy - 1, cx, cy - 9)


def _draw_open(p: QPainter, cx: int, cy: int, col: QColor) -> None:
    """開啟照片：資料夾圖示"""
    pen = QPen(col, 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.SquareCap)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    # 資料夾底部
    p.drawRect(cx - 13, cy - 5, 26, 16)
    # 資料夾頂部標籤
    points = QPolygonF([
        QPointF(cx - 13, cy - 5),
        QPointF(cx - 13, cy - 10),
        QPointF(cx - 4,  cy - 10),
        QPointF(cx,      cy - 5),
    ])
    p.drawPolyline(points)
    # 中間加號
    pen2 = QPen(col, 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
    p.setPen(pen2)
    p.drawLine(cx, cy + 1, cx, cy + 9)
    p.drawLine(cx - 4, cy + 5, cx + 4, cy + 5)


# ── 圖示映射 ──────────────────────────────────────────────────────────────────

_ICON_DRAW = {
    "ratio":    _draw_ratio,
    "border":   _draw_border,
    "color":    _draw_color,
    "brand":    _draw_brand,
    "export":   _draw_export,
    "__open__": _draw_open,
}

_NAV_ITEMS = [
    ("ratio",    "輸出比例"),
    ("border",   "邊框設定"),
    ("color",    "外框顏色"),
    ("brand",    "品牌資訊"),
    ("export",   "匯出設定"),
]


# ── 單一導覽按鈕 ──────────────────────────────────────────────────────────────

class _NavBtn(QWidget):
    clicked = pyqtSignal(str)

    BTN_W = 72
    BTN_H = 68

    def __init__(self, section: str, label: str, parent=None):
        super().__init__(parent)
        self._section = section
        self._label   = label
        self._active  = False
        self._hovered = False
        self.setFixedSize(self.BTN_W, self.BTN_H)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(label)
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
            self.clicked.emit(self._section)

    def paintEvent(self, e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()
        R = T.R_CHIP
        M = 5   # margin

        # ── 背景 ──────────────────────────────────────────────────────────────
        if self._active:
            p.setBrush(QBrush(QColor(T.PRIMARY)))
            p.setPen(QPen(QColor(T.BORDER), 2))
            p.drawRoundedRect(M, M, W-M*2, H-M*2, R, R)
            icon_col = QColor(T.TEXT_ON_PRIMARY)
            text_col = QColor(T.TEXT_ON_PRIMARY)
        elif self._hovered:
            p.setBrush(QBrush(QColor(T.SURFACE_2)))
            p.setPen(QPen(QColor(T.BORDER_LIGHT), 1.5))
            p.drawRoundedRect(M, M, W-M*2, H-M*2, R, R)
            icon_col = QColor(T.TEXT_PRIMARY)
            text_col = QColor(T.TEXT_PRIMARY)
        else:
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(Qt.PenStyle.NoPen)
            icon_col = QColor(T.TEXT_SECONDARY)
            text_col = QColor(T.TEXT_MUTED)

        # ── 圖示區（上 3/4）──────────────────────────────────────────────────
        cx = W // 2
        cy = H // 2 - 6     # 圖示往上偏移，留空間給標籤

        draw_fn = _ICON_DRAW.get(self._section)
        if draw_fn:
            draw_fn(p, cx, cy, icon_col)

        # ── 標籤文字（下方）──────────────────────────────────────────────────
        p.setFont(T.ui_font(T.FONT_XS, QFont.Weight.Bold if self._active else QFont.Weight.Medium))
        p.setPen(QPen(text_col))
        p.drawText(
            QRect(0, H - 22, W, 18),
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter,
            self._label
        )

        p.end()


# ── 開啟照片按鈕（底部，特殊樣式）────────────────────────────────────────────

class _OpenBtn(QWidget):
    # action: "files" | "folder"
    open_requested = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._hovered = False
        self.setFixedSize(72, 64)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("開啟照片 / 資料夾")
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        _tm().theme_changed.connect(lambda _: self.update())

    def enterEvent(self, e) -> None:
        self._hovered = True; self.update(); super().enterEvent(e)

    def leaveEvent(self, e) -> None:
        self._hovered = False; self.update(); super().leaveEvent(e)

    def mousePressEvent(self, e) -> None:
        if e.button() != Qt.MouseButton.LeftButton:
            return
        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{
                background: {T.SURFACE};
                border: 1.5px solid {T.BORDER};
                border-radius: 6px;
                padding: 4px;
                color: {T.TEXT_PRIMARY};
                font-size: {T.FONT_BASE}px;
            }}
            QMenu::item {{ padding: 7px 18px; border-radius: 4px; }}
            QMenu::item:selected {{ background: {T.SURFACE_2}; }}
        """)
        act_files  = menu.addAction("選擇照片…")
        act_folder = menu.addAction("選擇資料夾…")
        menu_h = menu.sizeHint().height()
        pos = self.mapToGlobal(self.rect().topLeft())
        pos.setY(pos.y() - menu_h)
        chosen = menu.exec(pos)
        if chosen == act_files:
            self.open_requested.emit("files")
        elif chosen == act_folder:
            self.open_requested.emit("folder")

    def paintEvent(self, e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()
        M = 5

        # 背景（虛線框，強調可點擊）
        if self._hovered:
            p.setBrush(QBrush(QColor(T.SURFACE_2)))
            pen = QPen(QColor(T.BORDER), 2, Qt.PenStyle.SolidLine)
        else:
            p.setBrush(Qt.BrushStyle.NoBrush)
            pen = QPen(QColor(T.BORDER_LIGHT), 1.5, Qt.PenStyle.DashLine)
            pen.setDashPattern([4, 3])
        p.setPen(pen)
        p.drawRoundedRect(M, M, W-M*2, H-M*2, T.R_CHIP, T.R_CHIP)

        # 圖示
        col = QColor(T.TEXT_PRIMARY if self._hovered else T.TEXT_SECONDARY)
        _draw_open(p, W//2, H//2 - 6, col)

        # 標籤
        p.setFont(T.ui_font(T.FONT_XS, QFont.Weight.Medium))
        p.setPen(QPen(col))
        p.drawText(
            QRect(0, H-22, W, 18),
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter,
            "開啟照片"
        )
        p.end()


# ── 主導覽列 ─────────────────────────────────────────────────────────────────

class LeftNavBar(QWidget):
    section_requested = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("LeftNavBar")
        self.setFixedWidth(72)
        self._btns: dict[str, _NavBtn] = {}

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 10, 0, 10)
        lay.setSpacing(4)
        lay.setAlignment(Qt.AlignmentFlag.AlignTop)

        for section, label in _NAV_ITEMS:
            btn = _NavBtn(section, label)
            btn.clicked.connect(self._on_nav_click)
            self._btns[section] = btn
            lay.addWidget(btn, 0, Qt.AlignmentFlag.AlignHCenter)

        lay.addStretch()

        # 分隔線
        div = QFrame()
        div.setFrameShape(QFrame.Shape.HLine)
        div.setFixedHeight(1)
        div.setStyleSheet(f"background: {T.BORDER_LIGHT}; margin: 0 10px;")
        lay.addWidget(div)
        lay.addSpacing(6)

        # 開啟照片按鈕
        self._open_btn = _OpenBtn()
        self._open_btn.open_requested.connect(self._on_open_requested)
        lay.addWidget(self._open_btn, 0, Qt.AlignmentFlag.AlignHCenter)

        self._apply_bg()
        _tm().theme_changed.connect(lambda _: self._apply_bg())

    def _apply_bg(self) -> None:
        self.setStyleSheet(f"""
            QWidget#LeftNavBar {{
                background: {T.SIDEBAR};
                border-right: 2px solid {T.BORDER};
            }}
        """)

    def _on_nav_click(self, section: str) -> None:
        for k, btn in self._btns.items():
            btn.set_active(k == section)
        self.section_requested.emit(section)

    def _on_open_requested(self, action: str) -> None:
        self.section_requested.emit(f"__open__{action}")

    def set_active_section(self, section: str) -> None:
        for k, btn in self._btns.items():
            btn.set_active(k == section)
