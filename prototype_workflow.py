"""
prototype_workflow.py — 分層工作流介面 Prototype（滑動動畫版）

兩個完整畫面：
  畫面 1：調色（色調曲線、白平衡、HSL、降噪）
  畫面 2：加框（邊框、顏色、EXIF、匯出）

透過滑動動畫（QPropertyAnimation）水平切換。

執行：python prototype_workflow.py
"""
from __future__ import annotations

import sys
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QLabel, QFrame, QScrollArea, QSlider, QSizePolicy,
    QComboBox, QPushButton,
)
from PyQt6.QtCore import (
    Qt, pyqtSignal, QRect, QRectF, QPointF, QSize,
    QPropertyAnimation, QEasingCurve, QPoint, QParallelAnimationGroup,
)
from PyQt6.QtGui import (
    QPainter, QColor, QPen, QBrush, QFont, QPainterPath,
    QLinearGradient, QPolygonF,
)

import src.gui.theme as T
from src.gui.theme_manager import ThemeManager


# ─────────────────────────────────────────────────────────────────────────────
# 工具函式
# ─────────────────────────────────────────────────────────────────────────────

def _section_label(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet(
        f"color: {T.TEXT_PRIMARY}; font-size: {T.FONT_SM}px; font-weight: 700; "
        f"background: transparent; padding: 2px 0;"
    )
    return lbl


def _divider() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.Shape.HLine)
    f.setFixedHeight(1)
    f.setStyleSheet(f"background: {T.BORDER_LIGHT}; border: none; margin: 2px 0;")
    return f


def _make_slider_row(label: str, mn: int, mx: int, val: int) -> QWidget:
    w = QWidget()
    lay = QHBoxLayout(w)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(8)

    lbl = QLabel(label)
    lbl.setFixedWidth(52)
    lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    lbl.setStyleSheet(
        f"color: {T.TEXT_SECONDARY}; font-size: {T.FONT_SM}px; background: transparent;"
    )

    slider = QSlider(Qt.Orientation.Horizontal)
    slider.setRange(mn, mx)
    slider.setValue(val)
    slider.setFixedHeight(18)

    val_lbl = QLabel(str(val))
    val_lbl.setFixedWidth(34)
    val_lbl.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
    val_lbl.setStyleSheet(
        f"color: {T.TEXT_MUTED}; font-size: {T.FONT_XS}px; background: transparent;"
    )
    slider.valueChanged.connect(lambda v: val_lbl.setText(str(v)))

    lay.addWidget(lbl)
    lay.addWidget(slider, 1)
    lay.addWidget(val_lbl)
    return w


_PANEL_QSS = lambda: f"""
    QWidget#RightPanel {{
        background: {T.SURFACE};
        border-left: 2px solid {T.BORDER};
    }}
    QComboBox {{
        background: {T.SURFACE_2};
        color: {T.TEXT_PRIMARY};
        border: 1.5px solid {T.BORDER};
        border-radius: {T.R_INPUT}px;
        font-size: {T.FONT_SM}px;
        padding: 0 8px;
        height: 28px;
    }}
    QComboBox::drop-down {{ border: none; width: 20px; }}
    QSlider::groove:horizontal {{
        height: 4px; background: {T.SURFACE_3}; border-radius: 2px;
    }}
    QSlider::handle:horizontal {{
        width: 14px; height: 14px;
        background: {T.SURFACE};
        border: 2px solid {T.PRIMARY};
        border-radius: 7px;
        margin: -5px 0;
    }}
    QSlider::sub-page:horizontal {{
        background: {T.PRIMARY}; border-radius: 2px;
    }}
    QPushButton#ChipBtn {{
        background: {T.SURFACE_2};
        color: {T.TEXT_SECONDARY};
        border: 1.5px solid {T.BORDER_LIGHT};
        border-radius: {T.R_CHIP}px;
        font-size: {T.FONT_SM}px;
        padding: 0 10px;
    }}
    QPushButton#ChipBtn:hover {{
        background: {T.SURFACE_3};
        color: {T.TEXT_PRIMARY};
        border-color: {T.BORDER};
    }}
    QPushButton#ChipBtn:checked {{
        background: {T.PRIMARY};
        color: {T.TEXT_ON_PRIMARY};
        border-color: {T.BORDER};
    }}
    QPushButton#SmallBtn {{
        background: transparent;
        color: {T.TEXT_SECONDARY};
        border: 1.5px solid {T.BORDER_LIGHT};
        border-radius: {T.R_CHIP}px;
        font-size: {T.FONT_XS}px;
        padding: 0 10px;
    }}
    QPushButton#SmallBtn:hover {{
        background: {T.SURFACE_2};
        color: {T.TEXT_PRIMARY};
    }}
    QPushButton#ActionBtn {{
        background: {T.PRIMARY};
        color: {T.TEXT_ON_PRIMARY};
        border: 2px solid {T.BORDER};
        border-radius: {T.R_BUTTON}px;
        font-size: {T.FONT_BASE}px;
        font-weight: 700;
        height: 40px;
    }}
    QPushButton#ActionBtn:hover {{
        background: {T.PRIMARY_HOVER};
    }}
"""


# ─────────────────────────────────────────────────────────────────────────────
# 色調曲線元件
# ─────────────────────────────────────────────────────────────────────────────

class CurveWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(170)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._pts = [(0.0, 0.0), (0.5, 0.5), (1.0, 1.0)]
        self._drag_idx = -1
        self._channel = "RGB"
        ThemeManager.instance().theme_changed.connect(lambda _: self.update())

    def set_channel(self, ch: str):
        self._channel = ch
        self.update()

    def _to_w(self, px, py):
        m = 14
        W, H = self.width() - m*2, self.height() - m*2
        return int(m + px * W), int(m + (1 - py) * H)

    def _from_w(self, wx, wy):
        m = 14
        W, H = self.width() - m*2, self.height() - m*2
        return max(0., min(1., (wx - m) / W)), max(0., min(1., 1 - (wy - m) / H))

    def mousePressEvent(self, e):
        if e.button() != Qt.MouseButton.LeftButton:
            return
        wx, wy = e.position().x(), e.position().y()
        for i, (px, py) in enumerate(self._pts):
            cx, cy = self._to_w(px, py)
            if abs(wx - cx) < 10 and abs(wy - cy) < 10:
                self._drag_idx = i
                return
        nx, ny = self._from_w(int(wx), int(wy))
        self._pts.append((nx, ny))
        self._pts.sort(key=lambda p: p[0])
        self.update()

    def mouseMoveEvent(self, e):
        if self._drag_idx < 0:
            return
        nx, ny = self._from_w(int(e.position().x()), int(e.position().y()))
        if self._drag_idx in (0, len(self._pts) - 1):
            nx = self._pts[self._drag_idx][0]
        self._pts[self._drag_idx] = (nx, ny)
        self.update()

    def mouseReleaseEvent(self, e):
        self._drag_idx = -1

    def mouseDoubleClickEvent(self, e):
        wx, wy = e.position().x(), e.position().y()
        for i in range(1, len(self._pts) - 1):
            cx, cy = self._to_w(*self._pts[i])
            if abs(wx - cx) < 10 and abs(wy - cy) < 10:
                self._pts.pop(i)
                self.update()
                return

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()
        m = 14

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(QColor(T.SURFACE_2)))
        p.drawRoundedRect(0, 0, W, H, 8, 8)

        grid = QPen(QColor(T.BORDER_LIGHT), 1, Qt.PenStyle.DotLine)
        p.setPen(grid)
        for i in range(1, 4):
            f = i / 4
            p.drawLine(*self._to_w(f, 0), *self._to_w(f, 1))
            p.drawLine(*self._to_w(0, f), *self._to_w(1, f))

        p.setPen(QPen(QColor(T.BORDER), 1, Qt.PenStyle.DashLine))
        p.drawLine(*self._to_w(0, 0), *self._to_w(1, 1))

        ch_colors = {"RGB": T.TEXT_PRIMARY, "R": "#f87171", "G": "#4ade80", "B": "#60a5fa"}
        curve_col = QColor(ch_colors.get(self._channel, T.TEXT_PRIMARY))

        if len(self._pts) >= 2:
            pts_px = [self._to_w(px, py) for px, py in self._pts]
            path = QPainterPath()
            path.moveTo(*pts_px[0])
            if len(pts_px) == 2:
                path.lineTo(*pts_px[1])
            else:
                for i in range(len(pts_px) - 1):
                    p0 = pts_px[max(0, i-1)]
                    p1 = pts_px[i]
                    p2 = pts_px[i+1]
                    p3 = pts_px[min(len(pts_px)-1, i+2)]
                    cp1x = p1[0] + (p2[0] - p0[0]) / 6
                    cp1y = p1[1] + (p2[1] - p0[1]) / 6
                    cp2x = p2[0] - (p3[0] - p1[0]) / 6
                    cp2y = p2[1] - (p3[1] - p1[1]) / 6
                    path.cubicTo(cp1x, cp1y, cp2x, cp2y, p2[0], p2[1])
            pen = QPen(curve_col, 2.5, Qt.PenStyle.SolidLine,
                       Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
            p.strokePath(path, pen)

        for px, py in self._pts:
            cx, cy = self._to_w(px, py)
            p.setPen(QPen(curve_col, 2))
            p.setBrush(QBrush(QColor(T.SURFACE)))
            p.drawEllipse(QRectF(cx - 5, cy - 5, 10, 10))

        p.end()


# ─────────────────────────────────────────────────────────────────────────────
# 預覽區
# ─────────────────────────────────────────────────────────────────────────────

class PreviewArea(QWidget):
    def __init__(self, step: int = 1, parent=None):
        super().__init__(parent)
        self._step = step
        ThemeManager.instance().theme_changed.connect(lambda _: self.update())

    def set_step(self, step: int):
        self._step = step
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()

        p.fillRect(0, 0, W, H, QColor(T.PREVIEW_BG))

        pad = max(40, int(W * 0.1))
        ph_w = W - pad * 2
        ph_h = int(ph_w * 0.72)
        ph_x = pad
        ph_y = max(pad, (H - ph_h) // 2 - 20)

        # 邊框白底（步驟 2）
        if self._step == 2:
            bsz = max(16, int(ph_w * 0.04))
            exif_h = max(28, int(ph_w * 0.06))
            frame_rect = QRectF(
                ph_x - bsz, ph_y - bsz,
                ph_w + bsz * 2, ph_h + bsz * 2 + exif_h
            )
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(QColor(T.SURFACE)))
            p.drawRoundedRect(frame_rect, 6, 6)

        # 照片漸層
        grad = QLinearGradient(ph_x, ph_y, ph_x, ph_y + ph_h)
        grad.setColorAt(0, QColor("#3a4a6b"))
        grad.setColorAt(1, QColor("#2a3a2a"))
        p.setBrush(QBrush(grad))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRect(ph_x, ph_y, ph_w, ph_h)

        # 山形
        mtn = QPolygonF([
            QPointF(ph_x,              ph_y + ph_h * 0.9),
            QPointF(ph_x + ph_w * 0.3, ph_y + ph_h * 0.42),
            QPointF(ph_x + ph_w * 0.5, ph_y + ph_h * 0.6),
            QPointF(ph_x + ph_w * 0.7, ph_y + ph_h * 0.36),
            QPointF(ph_x + ph_w,       ph_y + ph_h * 0.78),
            QPointF(ph_x + ph_w,       ph_y + ph_h),
            QPointF(ph_x,              ph_y + ph_h),
        ])
        p.setBrush(QBrush(QColor("#2d4a2d")))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawPolygon(mtn)

        # 步驟 1：調色色彩疊加
        if self._step == 1:
            ov = QColor(T.PRIMARY)
            ov.setAlpha(22)
            p.fillRect(ph_x, ph_y, ph_w, ph_h, ov)

        # 步驟 2：EXIF 條
        if self._step == 2:
            bsz = max(16, int(ph_w * 0.04))
            exif_h = max(28, int(ph_w * 0.06))
            exif_y = ph_y + ph_h + bsz
            p.fillRect(ph_x - bsz, exif_y, ph_w + bsz * 2, exif_h, QColor(T.SURFACE))

            p.setFont(T.ui_font(T.FONT_XS))
            p.setPen(QPen(QColor(T.TEXT_SECONDARY)))
            p.drawText(
                QRect(ph_x - bsz + 10, exif_y, ph_w // 2, exif_h),
                Qt.AlignmentFlag.AlignVCenter,
                "35mm  f/2.8  1/250s  ISO 800"
            )
            p.setFont(T.ui_font(T.FONT_SM, QFont.Weight.Bold))
            p.setPen(QPen(QColor(T.TEXT_PRIMARY)))
            p.drawText(
                QRect(ph_x + ph_w // 2, exif_y, ph_w // 2 + bsz - 8, exif_h),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
                "SONY  |  ILCE-7RM4"
            )

        # 步驟標籤
        step_text = "步驟 1：調色" if self._step == 1 else "步驟 2：加框"
        badge_col = QColor(T.PRIMARY)
        badge_col.setAlpha(220)
        p.setBrush(QBrush(badge_col))
        p.setPen(Qt.PenStyle.NoPen)
        lbl_w, lbl_h = 120, 26
        lbl_x = (W - lbl_w) // 2
        if self._step == 2:
            bsz = max(16, int(ph_w * 0.04))
            exif_h = max(28, int(ph_w * 0.06))
            lbl_y = ph_y + ph_h + bsz + exif_h + 14
        else:
            lbl_y = ph_y + ph_h + 16
        p.drawRoundedRect(lbl_x, lbl_y, lbl_w, lbl_h, 13, 13)
        p.setFont(T.ui_font(T.FONT_XS, QFont.Weight.Bold))
        p.setPen(QPen(QColor(T.TEXT_ON_PRIMARY)))
        p.drawText(QRect(lbl_x, lbl_y, lbl_w, lbl_h), Qt.AlignmentFlag.AlignCenter, step_text)

        # 底部拖放提示
        p.setFont(T.ui_font(T.FONT_XS))
        p.setPen(QPen(QColor(T.TEXT_MUTED)))
        p.drawText(
            QRect(0, H - 32, W, 24),
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter,
            "拖放照片到這裡，或點選左側「開啟照片」"
        )
        p.end()


# ─────────────────────────────────────────────────────────────────────────────
# 左側導覽（靜態示意）
# ─────────────────────────────────────────────────────────────────────────────

class ProtoLeftNav(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ProtoLeftNav")
        self.setFixedWidth(72)
        self._build()
        self._apply_style()
        ThemeManager.instance().theme_changed.connect(lambda _: self._apply_style())

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 12, 0, 12)
        lay.setSpacing(4)
        lay.setAlignment(Qt.AlignmentFlag.AlignTop)

        icons = [("比\n例", "比例"), ("框", "邊框"), ("色", "顏色"), ("牌", "品牌")]
        for icon_text, label in icons:
            btn = self._make_nav_btn(icon_text, label)
            lay.addWidget(btn, 0, Qt.AlignmentFlag.AlignHCenter)

        lay.addStretch()

        div = QFrame()
        div.setFrameShape(QFrame.Shape.HLine)
        div.setFixedHeight(1)
        div.setStyleSheet(f"background: {T.BORDER_LIGHT}; margin: 0 10px;")
        lay.addWidget(div)
        lay.addSpacing(6)

        open_btn = self._make_open_btn()
        lay.addWidget(open_btn, 0, Qt.AlignmentFlag.AlignHCenter)

    def _make_nav_btn(self, icon_text: str, label: str) -> QWidget:
        btn = QWidget()
        btn.setFixedSize(62, 64)
        btn.setObjectName("NavBtn")
        lay = QVBoxLayout(btn)
        lay.setContentsMargins(0, 6, 0, 4)
        lay.setSpacing(2)
        icon_lbl = QLabel(icon_text)
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_lbl.setStyleSheet(
            f"color: {T.TEXT_SECONDARY}; font-size: {T.FONT_BASE}px; "
            f"font-weight: 700; background: transparent;"
        )
        lbl = QLabel(label)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet(
            f"color: {T.TEXT_MUTED}; font-size: {T.FONT_XS}px; background: transparent;"
        )
        lay.addWidget(icon_lbl)
        lay.addWidget(lbl)
        return btn

    def _make_open_btn(self) -> QWidget:
        btn = QWidget()
        btn.setFixedSize(62, 58)
        btn.setObjectName("OpenBtn")
        lay = QVBoxLayout(btn)
        lay.setContentsMargins(0, 4, 0, 4)
        lay.setSpacing(2)
        icon_lbl = QLabel("+")
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_lbl.setStyleSheet(
            f"color: {T.TEXT_SECONDARY}; font-size: 18px; font-weight: 700; background: transparent;"
        )
        lbl = QLabel("開啟照片")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet(
            f"color: {T.TEXT_MUTED}; font-size: {T.FONT_XS}px; background: transparent;"
        )
        lay.addWidget(icon_lbl)
        lay.addWidget(lbl)
        return btn

    def _apply_style(self):
        self.setStyleSheet(f"""
            QWidget#ProtoLeftNav {{
                background: {T.SIDEBAR};
                border-right: 2px solid {T.BORDER};
            }}
            QWidget#NavBtn {{
                background: transparent;
                border-radius: {T.R_CHIP}px;
            }}
            QWidget#NavBtn:hover {{
                background: {T.SURFACE_2};
            }}
            QWidget#OpenBtn {{
                background: transparent;
                border: 1.5px dashed {T.BORDER_LIGHT};
                border-radius: {T.R_CHIP}px;
            }}
            QWidget#OpenBtn:hover {{
                background: {T.SURFACE_2};
            }}
        """)


# ─────────────────────────────────────────────────────────────────────────────
# 調色面板
# ─────────────────────────────────────────────────────────────────────────────

class ColorGradePanel(QWidget):
    go_next = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("RightPanel")
        self.setFixedWidth(320)
        self._build()
        self._apply_style()
        ThemeManager.instance().theme_changed.connect(lambda _: self._apply_style())

    def _build(self):
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        content = QWidget()
        lay = QVBoxLayout(content)
        lay.setContentsMargins(T.S4, T.S4, T.S4, T.S6)
        lay.setSpacing(T.S3)

        # 標題
        title = QLabel("調色")
        title.setStyleSheet(
            f"color: {T.TEXT_PRIMARY}; font-size: {T.FONT_LG}px; "
            f"font-weight: 800; background: transparent;"
        )
        lay.addWidget(title)
        lay.addWidget(_divider())

        # 曲線
        lay.addWidget(_section_label("色調曲線"))
        ch_row = QWidget()
        ch_lay = QHBoxLayout(ch_row)
        ch_lay.setContentsMargins(0, 0, 0, 0)
        ch_lay.setSpacing(6)
        self._curve = CurveWidget()
        self._channel_combo = QComboBox()
        self._channel_combo.addItems(["RGB", "R（紅）", "G（綠）", "B（藍）"])
        self._channel_combo.setFixedHeight(28)
        self._channel_combo.currentTextChanged.connect(
            lambda t: self._curve.set_channel(t.split("（")[0])
        )
        reset_btn = QPushButton("重置")
        reset_btn.setObjectName("SmallBtn")
        reset_btn.setFixedHeight(28)
        reset_btn.clicked.connect(self._reset_curve)
        ch_lay.addWidget(self._channel_combo)
        ch_lay.addWidget(reset_btn)
        lay.addWidget(ch_row)
        lay.addWidget(self._curve)
        hint = QLabel("拖曳控制點調整曲線　雙擊刪除")
        hint.setStyleSheet(
            f"color: {T.TEXT_MUTED}; font-size: {T.FONT_XS}px; background: transparent;"
        )
        lay.addWidget(hint)
        lay.addWidget(_divider())

        # 白平衡
        lay.addWidget(_section_label("白平衡"))
        wb_row = QWidget()
        wb_lay = QHBoxLayout(wb_row)
        wb_lay.setContentsMargins(0, 0, 0, 0)
        wb_lay.setSpacing(5)
        for preset in ["自動", "日光", "陰天", "鎢絲"]:
            btn = QPushButton(preset)
            btn.setObjectName("ChipBtn")
            btn.setFixedHeight(26)
            wb_lay.addWidget(btn)
        wb_lay.addStretch()
        lay.addWidget(wb_row)
        lay.addWidget(_make_slider_row("色溫", 2000, 10000, 5500))
        lay.addWidget(_make_slider_row("色調", -100, 100, 0))
        lay.addWidget(_divider())

        # 曝光
        lay.addWidget(_section_label("曝光"))
        for name, mn, mx, val in [
            ("曝光值", -300, 300, 0), ("對比度", -100, 100, 0),
            ("亮部",   -100, 100, 0), ("陰影",   -100, 100, 0),
            ("白點",   -100, 100, 0), ("黑點",   -100, 100, 0),
        ]:
            lay.addWidget(_make_slider_row(name, mn, mx, val))
        lay.addWidget(_divider())

        # HSL
        lay.addWidget(_section_label("HSL 色彩"))
        self._hsl_mode = QComboBox()
        self._hsl_mode.addItems(["色相（H）", "飽和度（S）", "亮度（L）"])
        self._hsl_mode.setFixedHeight(28)
        lay.addWidget(self._hsl_mode)
        for color in ["紅", "橙", "黃", "綠", "青", "藍", "紫", "洋紅"]:
            lay.addWidget(_make_slider_row(color, -100, 100, 0))
        lay.addWidget(_divider())

        # 降噪 & 銳化
        lay.addWidget(_section_label("降噪 & 銳化"))
        lay.addWidget(_make_slider_row("降噪", 0, 100, 0))
        lay.addWidget(_make_slider_row("銳化", 0, 150, 0))
        lay.addWidget(_make_slider_row("細節", 0, 100, 20))
        lay.addWidget(_divider())

        # 預設值
        lay.addWidget(_section_label("套用預設"))
        pr_row = QWidget()
        pr_lay = QHBoxLayout(pr_row)
        pr_lay.setContentsMargins(0, 0, 0, 0)
        pr_lay.setSpacing(6)
        for name in ["電影感", "清新", "黑白", "日系"]:
            btn = QPushButton(name)
            btn.setObjectName("ChipBtn")
            btn.setFixedHeight(30)
            pr_lay.addWidget(btn)
        lay.addWidget(pr_row)

        lay.addStretch()

        # 下一步
        next_btn = QPushButton("下一步：加框  →")
        next_btn.setObjectName("ActionBtn")
        next_btn.clicked.connect(self.go_next)
        lay.addWidget(next_btn)

        scroll.setWidget(content)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    def _reset_curve(self):
        self._curve._pts = [(0.0, 0.0), (0.5, 0.5), (1.0, 1.0)]
        self._curve.update()

    def _apply_style(self):
        self.setStyleSheet(_PANEL_QSS())


# ─────────────────────────────────────────────────────────────────────────────
# 加框面板
# ─────────────────────────────────────────────────────────────────────────────

class BorderPanel(QWidget):
    go_back = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("RightPanel")
        self.setFixedWidth(320)
        self._build()
        self._apply_style()
        ThemeManager.instance().theme_changed.connect(lambda _: self._apply_style())

    def _build(self):
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        content = QWidget()
        lay = QVBoxLayout(content)
        lay.setContentsMargins(T.S4, T.S4, T.S4, T.S6)
        lay.setSpacing(T.S3)

        # 標題列 + 返回
        title_row = QWidget()
        tr_lay = QHBoxLayout(title_row)
        tr_lay.setContentsMargins(0, 0, 0, 0)
        title_lbl = QLabel("加框")
        title_lbl.setStyleSheet(
            f"color: {T.TEXT_PRIMARY}; font-size: {T.FONT_LG}px; "
            f"font-weight: 800; background: transparent;"
        )
        back_btn = QPushButton("← 返回調色")
        back_btn.setObjectName("SmallBtn")
        back_btn.setFixedHeight(28)
        back_btn.clicked.connect(self.go_back)
        tr_lay.addWidget(title_lbl)
        tr_lay.addStretch()
        tr_lay.addWidget(back_btn)
        lay.addWidget(title_row)
        lay.addWidget(_divider())

        # 輸出比例
        lay.addWidget(_section_label("輸出比例"))
        ratio_row = QWidget()
        r_lay = QHBoxLayout(ratio_row)
        r_lay.setContentsMargins(0, 0, 0, 0)
        r_lay.setSpacing(5)
        for ratio in ["1:1", "4:5", "9:16", "3:4", "自由"]:
            btn = QPushButton(ratio)
            btn.setObjectName("ChipBtn")
            btn.setCheckable(True)
            btn.setChecked(ratio == "1:1")
            btn.setFixedHeight(30)
            r_lay.addWidget(btn)
        lay.addWidget(ratio_row)
        lay.addWidget(_divider())

        # 邊框設定
        lay.addWidget(_section_label("邊框設定"))
        preset_row = QWidget()
        p_lay = QHBoxLayout(preset_row)
        p_lay.setContentsMargins(0, 0, 0, 0)
        p_lay.setSpacing(5)
        for name in ["細", "中", "粗", "自訂"]:
            btn = QPushButton(name)
            btn.setObjectName("ChipBtn")
            btn.setCheckable(True)
            btn.setChecked(name == "中")
            btn.setFixedHeight(30)
            p_lay.addWidget(btn)
        lay.addWidget(preset_row)
        lay.addWidget(_make_slider_row("上下", 0, 200, 40))
        lay.addWidget(_make_slider_row("左右", 0, 200, 40))
        lay.addWidget(_make_slider_row("EXIF條", 0, 200, 76))
        lay.addWidget(_divider())

        # 外框顏色
        lay.addWidget(_section_label("外框顏色"))
        color_row = QWidget()
        c_lay = QHBoxLayout(color_row)
        c_lay.setContentsMargins(0, 0, 0, 0)
        c_lay.setSpacing(7)
        for hex_col in ["#ffffff", "#f5f0e8", "#f0f0f0", "#e8e0d8",
                         "#1c1c1e", "#1a1a2e", "#fce4ec", "#e8f5e9"]:
            sw = QWidget()
            sw.setFixedSize(26, 26)
            sw.setStyleSheet(
                f"background: {hex_col}; border: 1.5px solid {T.BORDER}; border-radius: 5px;"
            )
            c_lay.addWidget(sw)
        c_lay.addStretch()
        lay.addWidget(color_row)

        blur_btn = QPushButton("模糊背景")
        blur_btn.setObjectName("ChipBtn")
        blur_btn.setCheckable(True)
        blur_btn.setFixedHeight(30)
        lay.addWidget(blur_btn)
        lay.addWidget(_divider())

        # 品牌 & EXIF
        lay.addWidget(_section_label("品牌 & EXIF"))
        brand_combo = QComboBox()
        brand_combo.addItems([
            "自動偵測", "Sony", "Canon", "Nikon", "Fujifilm",
            "Leica", "Panasonic", "OM System", "Ricoh", "自訂 Logo"
        ])
        brand_combo.setFixedHeight(28)
        lay.addWidget(brand_combo)
        toggle_row = QWidget()
        t_lay = QHBoxLayout(toggle_row)
        t_lay.setContentsMargins(0, 0, 0, 0)
        t_lay.setSpacing(6)
        for name in ["顯示品牌 Logo", "顯示拍攝參數"]:
            btn = QPushButton(name)
            btn.setObjectName("ChipBtn")
            btn.setCheckable(True)
            btn.setChecked(True)
            btn.setFixedHeight(30)
            t_lay.addWidget(btn)
        t_lay.addStretch()
        lay.addWidget(toggle_row)
        lay.addWidget(_divider())

        # 匯出設定
        lay.addWidget(_section_label("匯出設定"))
        fmt_row = QWidget()
        f_lay = QHBoxLayout(fmt_row)
        f_lay.setContentsMargins(0, 0, 0, 0)
        f_lay.setSpacing(5)
        for fmt in ["JPEG", "PNG", "WebP"]:
            btn = QPushButton(fmt)
            btn.setObjectName("ChipBtn")
            btn.setCheckable(True)
            btn.setChecked(fmt == "JPEG")
            btn.setFixedHeight(28)
            f_lay.addWidget(btn)
        f_lay.addStretch()
        lay.addWidget(fmt_row)
        lay.addWidget(_make_slider_row("品質", 60, 100, 95))
        lay.addWidget(_make_slider_row("長邊 px", 1080, 4096, 2048))

        lay.addStretch()

        # 匯出按鈕
        export_btn = QPushButton("匯出照片")
        export_btn.setObjectName("ActionBtn")
        lay.addWidget(export_btn)

        scroll.setWidget(content)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    def _apply_style(self):
        self.setStyleSheet(_PANEL_QSS())


# ─────────────────────────────────────────────────────────────────────────────
# SlidingBody — 水平滑動容器
#   畫面 1：[左導覽 | 調色預覽 | 調色面板]
#   畫面 2：[左導覽 | 加框預覽 | 加框面板]
# ─────────────────────────────────────────────────────────────────────────────

class SlidingBody(QWidget):
    """裁切視窗，內部放兩個並排 screen，透過動畫滑入滑出。"""

    def __init__(self, screen1: QWidget, screen2: QWidget, parent=None):
        super().__init__(parent)
        self._s1 = screen1
        self._s2 = screen2
        self._current = 0          # 0=畫面1, 1=畫面2
        self._animating = False

        # 兩個 screen 直接成為此 widget 的子控件（不用 layout）
        screen1.setParent(self)
        screen2.setParent(self)
        self.setClipping(True)

    def setClipping(self, _):
        pass  # 靠 resizeEvent 控制位置

    def resizeEvent(self, e):
        W, H = self.width(), self.height()
        self._s1.setGeometry(0, 0, W, H)
        if self._current == 0:
            self._s2.setGeometry(W, 0, W, H)
        else:
            self._s2.setGeometry(0, 0, W, H)
            self._s1.setGeometry(-W, 0, W, H)

    def slide_to(self, screen_idx: int):
        """滑動到指定畫面（0 或 1）。"""
        if screen_idx == self._current or self._animating:
            return
        self._animating = True

        W = self.width()
        going_right = screen_idx == 1  # True = 向左滑（顯示右邊的畫面）

        # 確保目標畫面在正確的起始位置
        if going_right:
            self._s2.setGeometry(W, 0, W, self.height())
        else:
            self._s1.setGeometry(-W, 0, W, self.height())
        self._s1.show()
        self._s2.show()

        anim_out = QPropertyAnimation(self._s1 if going_right else self._s2, b"pos")
        anim_out.setDuration(320)
        anim_out.setEasingCurve(QEasingCurve.Type.InOutCubic)
        anim_out.setStartValue(QPoint(0, 0))
        anim_out.setEndValue(QPoint(-W if going_right else W, 0))

        anim_in = QPropertyAnimation(self._s2 if going_right else self._s1, b"pos")
        anim_in.setDuration(320)
        anim_in.setEasingCurve(QEasingCurve.Type.InOutCubic)
        anim_in.setStartValue(QPoint(W if going_right else -W, 0))
        anim_in.setEndValue(QPoint(0, 0))

        self._group = QParallelAnimationGroup()
        self._group.addAnimation(anim_out)
        self._group.addAnimation(anim_in)

        def _done():
            self._current = screen_idx
            self._animating = False
            # 隱藏不顯示的畫面
            self._s1.setVisible(screen_idx == 0)
            self._s2.setVisible(screen_idx == 1)

        self._group.finished.connect(_done)
        self._group.start()


# ─────────────────────────────────────────────────────────────────────────────
# 頂部工具列（含步驟指示器）
# ─────────────────────────────────────────────────────────────────────────────

class ProtoTopBar(QWidget):
    step_changed = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ProtoTopBar")
        self.setFixedHeight(52)
        self._step = 1
        self._build()
        self._apply_style()
        ThemeManager.instance().theme_changed.connect(lambda _: self._apply_style())

    def _build(self):
        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 0, 16, 0)
        lay.setSpacing(0)

        name = QLabel("PicLab")
        name.setObjectName("AppName")
        lay.addWidget(name)
        lay.addSpacing(14)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setFixedHeight(28)
        sep.setObjectName("BarSep")
        lay.addWidget(sep)
        lay.addSpacing(14)

        # 步驟 1 按鈕
        self._btn1 = self._make_step_btn("1", "調色")
        lay.addWidget(self._btn1)
        lay.addSpacing(4)

        # 箭頭
        arrow = QLabel("→")
        arrow.setObjectName("Arrow")
        lay.addWidget(arrow)
        lay.addSpacing(4)

        # 步驟 2 按鈕
        self._btn2 = self._make_step_btn("2", "加框")
        lay.addWidget(self._btn2)

        lay.addStretch()

        # 主題切換
        theme_btn = QPushButton("切換主題")
        theme_btn.setObjectName("TopBtn")
        theme_btn.setFixedHeight(34)
        theme_btn.clicked.connect(ThemeManager.instance().cycle_theme)
        lay.addWidget(theme_btn)
        lay.addSpacing(10)

        # 匯出
        export_btn = QPushButton("匯出照片")
        export_btn.setObjectName("ExportBtn")
        export_btn.setFixedHeight(34)
        lay.addWidget(export_btn)

        self._update_buttons()

    def _make_step_btn(self, num: str, label: str) -> QPushButton:
        btn = QPushButton(f"  {num}  {label}")
        btn.setObjectName(f"StepBtn{num}")
        btn.setFixedHeight(34)
        btn.setMinimumWidth(88)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        if num == "1":
            btn.clicked.connect(lambda: self._go_step(1))
        else:
            btn.clicked.connect(lambda: self._go_step(2))
        return btn

    def _go_step(self, step: int):
        if step == self._step:
            return
        self._step = step
        self._update_buttons()
        self.step_changed.emit(step)

    def go_step(self, step: int):
        self._go_step(step)

    def _update_buttons(self):
        for btn, step in [(self._btn1, 1), (self._btn2, 2)]:
            active = (self._step == step)
            btn.setProperty("active", active)
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        self._apply_style()

    def _apply_style(self):
        step = self._step
        a1 = step == 1
        a2 = step == 2

        def _btn_style(active: bool) -> str:
            if active:
                return (f"background: {T.PRIMARY}; color: {T.TEXT_ON_PRIMARY}; "
                        f"border: 2px solid {T.BORDER}; border-radius: {T.R_CHIP}px; "
                        f"font-size: {T.FONT_SM}px; font-weight: 700;")
            return (f"background: {T.SURFACE_2}; color: {T.TEXT_SECONDARY}; "
                    f"border: 1.5px solid {T.BORDER_LIGHT}; border-radius: {T.R_CHIP}px; "
                    f"font-size: {T.FONT_SM}px;")

        self._btn1.setStyleSheet(_btn_style(a1))
        self._btn2.setStyleSheet(_btn_style(a2))

        self.setStyleSheet(f"""
            QWidget#ProtoTopBar {{
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
            QLabel#Arrow {{
                color: {T.TEXT_MUTED};
                font-size: {T.FONT_BASE}px;
                background: transparent;
            }}
            QPushButton#TopBtn {{
                background: {T.SURFACE_2};
                color: {T.TEXT_SECONDARY};
                border: 1.5px solid {T.BORDER_LIGHT};
                border-radius: {T.R_CHIP}px;
                font-size: {T.FONT_SM}px;
                padding: 0 12px;
            }}
            QPushButton#TopBtn:hover {{
                background: {T.SURFACE_3};
                color: {T.TEXT_PRIMARY};
                border-color: {T.BORDER};
            }}
            QPushButton#ExportBtn {{
                background: {T.PRIMARY};
                color: {T.TEXT_ON_PRIMARY};
                border: 2px solid {T.BORDER};
                border-radius: {T.R_CHIP}px;
                font-size: {T.FONT_SM}px;
                font-weight: 700;
                padding: 0 16px;
            }}
            QPushButton#ExportBtn:hover {{
                background: {T.PRIMARY_HOVER};
            }}
        """)


# ─────────────────────────────────────────────────────────────────────────────
# 主視窗
# ─────────────────────────────────────────────────────────────────────────────

class PrototypeWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PicLab — 分層工作流 Prototype")
        self.setMinimumSize(1100, 680)
        self.resize(1380, 840)
        self._build_ui()
        self._apply_style()
        ThemeManager.instance().theme_changed.connect(lambda _: self._apply_style())

    def _apply_style(self):
        self.setStyleSheet(f"QMainWindow {{ background: {T.BG}; }}")
        self.statusBar().setStyleSheet(
            f"QStatusBar {{ background: {T.MENUBAR}; color: {T.TEXT_SECONDARY}; "
            f"font-size: {T.FONT_SM}px; border-top: 2px solid {T.BORDER}; "
            f"padding: 0 16px; }}"
        )

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)

        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # TopBar
        self._top_bar = ProtoTopBar()
        self._top_bar.step_changed.connect(self._on_step_changed)
        root.addWidget(self._top_bar)

        # 建立兩個 Screen
        screen1 = self._build_screen1()
        screen2 = self._build_screen2()

        # 滑動容器
        self._slider = SlidingBody(screen1, screen2)
        root.addWidget(self._slider, 1)

        self.statusBar().showMessage(
            "步驟 1：調色 — 完成後按「下一步：加框」切換畫面"
        )

    def _build_screen1(self) -> QWidget:
        w = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(ProtoLeftNav())
        self._preview1 = PreviewArea(step=1)
        lay.addWidget(self._preview1, 1)
        self._grade_panel = ColorGradePanel()
        self._grade_panel.go_next.connect(lambda: self._on_step_changed(2))
        lay.addWidget(self._grade_panel)
        return w

    def _build_screen2(self) -> QWidget:
        w = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(ProtoLeftNav())
        self._preview2 = PreviewArea(step=2)
        lay.addWidget(self._preview2, 1)
        self._border_panel = BorderPanel()
        self._border_panel.go_back.connect(lambda: self._on_step_changed(1))
        lay.addWidget(self._border_panel)
        return w

    def _on_step_changed(self, step: int):
        self._top_bar.go_step(step)
        self._slider.slide_to(step - 1)
        if step == 1:
            self.statusBar().showMessage(
                "步驟 1：調色 — 完成後按「下一步：加框」切換畫面"
            )
        else:
            self.statusBar().showMessage(
                "步驟 2：加框 — 設定邊框與 EXIF 資訊後按「匯出照片」"
            )


# ─────────────────────────────────────────────────────────────────────────────
# 啟動
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName("PicLab Prototype")
    T.apply_paper()
    win = PrototypeWindow()
    win.show()
    sys.exit(app.exec())
