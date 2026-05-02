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


# ── Develop 模式圖示 ──────────────────────────────────────────────────────────

def _draw_curve(p: QPainter, cx: int, cy: int, col: QColor) -> None:
    """Tone Curve：S 型曲線"""
    from PyQt6.QtGui import QPainterPath
    pen = QPen(col, 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    # 邊框
    p.drawRect(cx - 13, cy - 12, 26, 24)
    # S 型曲線
    path = QPainterPath()
    path.moveTo(cx - 13, cy + 12)
    path.cubicTo(cx - 6, cy + 12, cx - 6, cy, cx, cy)
    path.cubicTo(cx + 6, cy, cx + 6, cy - 12, cx + 13, cy - 12)
    p.drawPath(path)


def _draw_wb(p: QPainter, cx: int, cy: int, col: QColor) -> None:
    """White Balance：太陽 + 色溫箭頭"""
    pen = QPen(col, 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    # 太陽圓圈
    p.drawEllipse(QRectF(cx - 6, cy - 6, 12, 12))
    # 8 條放射光線
    import math
    for i in range(8):
        angle = i * math.pi / 4
        x1 = cx + math.cos(angle) * 8
        y1 = cy + math.sin(angle) * 8
        x2 = cx + math.cos(angle) * 11
        y2 = cy + math.sin(angle) * 11
        p.drawLine(int(x1), int(y1), int(x2), int(y2))


def _draw_light(p: QPainter, cx: int, cy: int, col: QColor) -> None:
    """Light：曝光表（垂直漸層條 + 指針）"""
    pen = QPen(col, 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.SquareCap)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    # 外框
    p.drawRect(cx - 10, cy - 12, 20, 24)
    # 中線
    pen_dash = QPen(col, 1, Qt.PenStyle.DashLine)
    p.setPen(pen_dash)
    p.drawLine(cx - 10, cy, cx + 10, cy)
    # 指針（向上偏，代表 +EV）
    pen2 = QPen(col, 2.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
    p.setPen(pen2)
    p.drawLine(cx, cy - 6, cx, cy - 1)


def _draw_hsl(p: QPainter, cx: int, cy: int, col: QColor) -> None:
    """HSL：色相環（圓弧 + 飽和度點）"""
    from PyQt6.QtGui import QPainterPath
    pen = QPen(col, 2.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    # 外圓環
    p.drawEllipse(QRectF(cx - 11, cy - 11, 22, 22))
    # 內部飽和度方塊
    p.drawRect(cx - 6, cy - 6, 12, 12)
    # 中心點
    p.setBrush(QBrush(col))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawEllipse(QRectF(cx - 2, cy - 2, 4, 4))


def _draw_detail(p: QPainter, cx: int, cy: int, col: QColor) -> None:
    """Detail：放大鏡 + 銳化虛線"""
    pen = QPen(col, 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawEllipse(QRectF(cx - 12, cy - 12, 16, 16))
    p.drawLine(cx + 4, cy + 4, cx + 12, cy + 12)
    pen2 = QPen(col, 1.5, Qt.PenStyle.DotLine)
    p.setPen(pen2)
    p.drawLine(cx - 8, cy - 4, cx + 2, cy - 4)
    p.drawLine(cx - 8, cy,     cx + 2, cy)
    p.drawLine(cx - 8, cy + 4, cx + 2, cy + 4)


def _draw_film(p: QPainter, cx: int, cy: int, col: QColor) -> None:
    """底片模擬：底片捲軸外框 + 齒孔"""
    pen = QPen(col, 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap,
               Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    # 底片外框
    p.drawRoundedRect(QRectF(cx - 13, cy - 9, 26, 18), 3, 3)
    # 左側齒孔（兩個小方塊）
    p.setBrush(QBrush(col))
    p.setPen(Qt.PenStyle.NoPen)
    for dy in (-4, 4):
        p.drawRoundedRect(QRectF(cx - 16, cy + dy - 2.5, 5, 5), 1, 1)
        p.drawRoundedRect(QRectF(cx + 11, cy + dy - 2.5, 5, 5), 1, 1)
    # 中央圓形（鏡頭暗示）
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.setPen(QPen(col, 1.5))
    p.drawEllipse(QRectF(cx - 5, cy - 5, 10, 10))


# ── 圖示映射 ──────────────────────────────────────────────────────────────────

_ICON_DRAW = {
    # Print 模式
    "ratio":    _draw_ratio,
    "border":   _draw_border,
    "color":    _draw_color,
    "brand":    _draw_brand,
    "export":   _draw_export,
    "__open__": _draw_open,
    # Develop 模式
    "wb":       _draw_wb,
    "light":    _draw_light,
    "hsl":      _draw_hsl,
    "curve":    _draw_curve,
    "detail":   _draw_detail,
    "film":     _draw_film,
}

_NAV_ITEMS_PRINT = [
    ("ratio",  "比例"),
    ("border", "邊框"),
    ("color",  "顏色"),
    ("brand",  "品牌"),
    ("export", "匯出"),
]

_NAV_ITEMS_DEVELOP = [
    ("wb",     "白平衡"),
    ("light",  "亮度"),
    ("hsl",    "飽和度"),
    ("curve",  "色調曲線"),
    ("detail", "細節"),
    ("film",   "底片"),
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
            # Dark luxury: gold-dim bg with gold icon — subtle glow rather than solid fill
            p.setBrush(QBrush(QColor(T.GOLD_DIM)))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(M, M, W-M*2, H-M*2, R, R)
            icon_col = QColor(T.GOLD)
            text_col = QColor(T.GOLD)
        elif self._hovered:
            p.setBrush(QBrush(QColor(T.GLASS_2)))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(M, M, W-M*2, H-M*2, R, R)
            icon_col = QColor(T.TEXT_PRIMARY)
            text_col = QColor(T.TEXT_SECONDARY)
        else:
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(Qt.PenStyle.NoPen)
            icon_col = QColor(T.TEXT_SECONDARY)
            text_col = QColor(T.TEXT_SECONDARY)

        # ── 圖示區（上 3/4）──────────────────────────────────────────────────
        cx = W // 2
        cy = H // 2 - 8     # 圖示往上偏移，留空間給標籤

        draw_fn = _ICON_DRAW.get(self._section)
        if draw_fn:
            draw_fn(p, cx, cy, icon_col)

        # ── 標籤文字（下方）──────────────────────────────────────────────────
        p.setFont(T.ui_font(T.FONT_XS, QFont.Weight.Medium))
        p.setPen(QPen(text_col))
        p.drawText(
            QRect(0, H - 24, W, 20),
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
                background: {T.SURFACE_2};
                border: 1px solid {T.BORDER};
                border-radius: {T.R_CARD}px;
                padding: {T.S1}px;
                color: {T.TEXT_PRIMARY};
                font-size: {T.FONT_SM}px;
            }}
            QMenu::item {{ padding: {T.S2}px {T.S4}px; border-radius: {T.R_BUTTON}px; }}
            QMenu::item:selected {{ background: {T.GOLD_DIM}; color: {T.GOLD}; }}
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
            p.setBrush(QBrush(QColor(T.GOLD_DIM)))
            pen = QPen(QColor(T.GOLD), 1.5, Qt.PenStyle.SolidLine)
        else:
            p.setBrush(Qt.BrushStyle.NoBrush)
            pen = QPen(QColor(T.BORDER), 1, Qt.PenStyle.DashLine)
            pen.setDashPattern([4, 3])
        p.setPen(pen)
        p.drawRoundedRect(M, M, W-M*2, H-M*2, T.R_CHIP, T.R_CHIP)

        # 圖示
        col = QColor(T.GOLD if self._hovered else T.TEXT_SECONDARY)
        _draw_open(p, W//2, H//2 - 6, col)

        # 標籤
        lbl_col = QColor(T.GOLD if self._hovered else T.TEXT_SECONDARY)
        p.setFont(T.ui_font(T.FONT_XS, QFont.Weight.Medium))
        p.setPen(QPen(lbl_col))
        p.drawText(
            QRect(0, H-22, W, 18),
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter,
            "開啟照片"
        )
        p.end()


# ── 主導覽列 ─────────────────────────────────────────────────────────────────

class LeftNavBar(QWidget):
    section_requested = pyqtSignal(str)

    def __init__(self, mode: str = "print", parent=None):
        """
        mode: "print"   → ratio / border / color / brand / export
              "develop" → curve / wb / light / hsl / detail
        """
        super().__init__(parent)
        self.setObjectName("LeftNavBar")
        self.setFixedWidth(72)
        self._btns: dict[str, _NavBtn] = {}

        nav_items = _NAV_ITEMS_DEVELOP if mode == "develop" else _NAV_ITEMS_PRINT

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 10, 0, 10)
        lay.setSpacing(4)
        lay.setAlignment(Qt.AlignmentFlag.AlignTop)

        for section, label in nav_items:
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
                background: {T.SURFACE};
                border-right: 1px solid {T.BORDER};
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
