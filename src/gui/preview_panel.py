"""
Preview panel — dark canvas + animated drop zone + processing spinner
+ bottom image-list strip. Theme-aware.
"""
from __future__ import annotations
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QHBoxLayout,
    QSizePolicy, QScrollArea, QGraphicsOpacityEffect, QMenu, QWidgetAction,
)
from PyQt6.QtCore import (
    Qt, QSize, QRectF, QRect, QTimer, pyqtSignal,
    QPropertyAnimation, QEasingCurve, pyqtProperty, QEvent,
)
from PyQt6.QtGui import (
    QColor, QPainter, QPen, QBrush, QFont, QFontMetrics, QImage, QPixmap,
    QPainterPath, QRegion,
)

from PIL import Image
import src.gui.theme as T
from src.models.settings import AspectRatioPreset, TemplateStyle


def _tm():
    from src.gui.theme_manager import ThemeManager
    return ThemeManager.instance()


# ── Drop Zone ─────────────────────────────────────────────────────────────────

class DropZone(QWidget):
    clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(300, 200)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._t     = 0.0
        self._drag  = False
        self._hover = False

        self._anim = QPropertyAnimation(self, b"_progress")
        self._anim.setDuration(T.ANIM_FAST)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        _tm().theme_changed.connect(lambda _: self.update())

    def _get_p(self) -> float: return self._t
    def _set_p(self, v: float) -> None: self._t = v; self.update()
    _progress = pyqtProperty(float, _get_p, _set_p)

    def _animate(self, target: float) -> None:
        self._anim.stop()
        self._anim.setStartValue(self._t)
        self._anim.setEndValue(target)
        self._anim.start()

    def set_drag(self, v: bool) -> None:
        self._drag = v
        self._animate(1.0 if v else (0.6 if self._hover else 0.0))

    def enterEvent(self, e) -> None:
        self._hover = True
        if not self._drag: self._animate(0.6)

    def leaveEvent(self, e) -> None:
        self._hover = False
        if not self._drag: self._animate(0.0)

    def mousePressEvent(self, e) -> None:
        if e.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()

    def paintEvent(self, e) -> None:
        """Paper Wireframe 風格 DropZone：手繪感虛線框、方角、炭黑文字。"""
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H, t = self.width(), self.height(), self._t

        # Paper 風格：底色為米紙，邊框為炭黑虛線
        bg_color = QColor(T.PREVIEW_BG)
        if t > 0:
            bg_color = bg_color.lighter(int(102 + t * 4))
        p.fillRect(0, 0, W, H, QBrush(bg_color))

        # 虛線方框（Paper 風格：短虛線、方角、粗一點）
        border_alpha = int(80 + t * 175)
        border_c = QColor(T.BORDER)
        border_c.setAlpha(border_alpha)
        pen = QPen(border_c, 2.0, Qt.PenStyle.DashLine)
        pen.setDashPattern([8, 5])
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        ins = 36
        p.drawRoundedRect(QRectF(ins, ins, W-2*ins, H-2*ins), 16, 16)

        cx = W / 2
        cy = H / 2

        # 箭頭圖示（手繪風格：方形底框 + 粗箭頭）
        icon_sz = 44
        icon_y  = cy - 60
        box_col = QColor(T.SURFACE)
        p.setPen(QPen(QColor(T.BORDER), 2.0))
        p.setBrush(QBrush(box_col))
        p.drawRoundedRect(QRectF(cx - icon_sz/2, icon_y - icon_sz/2, icon_sz, icon_sz), 10, 10)
        # 粗箭頭
        arr_col = QColor(T.TEXT_SECONDARY)
        p.setPen(QPen(arr_col, 2.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.SquareCap))
        p.drawLine(int(cx), int(icon_y - 12), int(cx), int(icon_y + 12))
        p.drawLine(int(cx - 9), int(icon_y - 5), int(cx), int(icon_y - 12))
        p.drawLine(int(cx + 9), int(icon_y - 5), int(cx), int(icon_y - 12))

        # 主文字（粗、大）
        p.setFont(T.ui_font(T.FONT_LG, QFont.Weight.ExtraBold))
        p.setPen(QPen(QColor(T.TEXT_PRIMARY)))
        p.drawText(QRectF(0, cy - 8, W, 28), Qt.AlignmentFlag.AlignCenter, "拖放照片至此")

        # 次要文字
        p.setFont(T.ui_font(T.FONT_SM, QFont.Weight.Normal))
        p.setPen(QPen(QColor(T.TEXT_SECONDARY)))
        p.drawText(QRectF(0, cy + 26, W, 20), Qt.AlignmentFlag.AlignCenter, "或點擊選擇檔案")

        # 格式提示（最小）
        p.setFont(T.ui_font(T.FONT_XS))
        p.setPen(QPen(QColor(T.TEXT_MUTED)))
        p.drawText(QRectF(0, cy + 50, W, 16), Qt.AlignmentFlag.AlignCenter, "JPG  ·  PNG  ·  TIFF  ·  WebP  ·  RAW")
        p.end()


# ── Safe Zone 資料 ────────────────────────────────────────────────────────────

# IG 網格縮圖為 3:4；計算兩側遮罩佔輸出寬度的比例
# 1:1  (1080×1080): visible_w = 1080 × (3/4) = 810px → mask = 135/1080 = 12.5%
# 4:5  (1080×1350): visible_w = 1350 × (3/4) = 1012.5px → mask = 33.75/1080 ≈ 3.125%
_SAFE_ZONE_RATIO: dict[AspectRatioPreset, float] = {
    AspectRatioPreset.SQUARE_1_1:   135 / 1080,
    AspectRatioPreset.PORTRAIT_4_5: 33.75 / 1080,
}

_SAFE_ZONE_TEXT: dict[AspectRatioPreset, str] = {
    AspectRatioPreset.SQUARE_1_1:   "IG 網格縮圖裁切 3:4 ─ 左右各 135 px 為遮罩區（內容放中間 810 px）",
    AspectRatioPreset.PORTRAIT_4_5: "IG 網格縮圖裁切 3:4 ─ 左右各 34 px 為遮罩區（內容放中間 1012 px）",
}


# ── Safe Zone Overlay ─────────────────────────────────────────────────────────

class SafeZoneOverlay(QWidget):
    """在預覽圖上疊加半透明遮罩，標示 IG 網格縮圖的裁切安全區域。"""

    def __init__(self, photo_lbl: QLabel, parent=None):
        super().__init__(parent)
        self._photo_lbl  = photo_lbl
        self._preset: AspectRatioPreset | None = None
        self._visible    = False
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.hide()
        _tm().theme_changed.connect(lambda _: self.update())

    def set_preset(self, preset: AspectRatioPreset) -> None:
        self._preset = preset
        self.update()

    def set_visible(self, v: bool) -> None:
        self._visible = v
        self.setVisible(v and self._preset in _SAFE_ZONE_RATIO)
        self.update()

    def paintEvent(self, _) -> None:
        if self._preset not in _SAFE_ZONE_RATIO:
            return
        pix = self._photo_lbl.pixmap()
        if pix is None or pix.isNull():
            return

        ratio = _SAFE_ZONE_RATIO[self._preset]
        pw, ph = pix.width(), pix.height()
        W, H   = self.width(), self.height()
        # Photo is AlignCenter inside _photo_lbl (same size as this overlay)
        px = (W - pw) // 2
        py = (H - ph) // 2
        mask_w = max(1, int(pw * ratio))

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 半透明遮罩（深色，模擬被裁切區域）
        mask_col = QColor(0, 0, 0, 120)
        p.fillRect(QRect(px,               py, mask_w,      ph), mask_col)
        p.fillRect(QRect(px + pw - mask_w, py, mask_w,      ph), mask_col)

        # 邊界線
        line_col = QColor(T.WARNING)
        line_col.setAlpha(200)
        pen = QPen(line_col, 1.5, Qt.PenStyle.DashLine)
        pen.setDashPattern([6, 4])
        p.setPen(pen)
        p.drawLine(px + mask_w,        py, px + mask_w,        py + ph)
        p.drawLine(px + pw - mask_w,   py, px + pw - mask_w,   py + ph)

        # 標籤文字（左右各一）
        fnt = T.ui_font(T.FONT_XS, QFont.Weight.Medium)
        p.setFont(fnt)
        txt_col = QColor(T.WARNING)
        txt_col.setAlpha(220)
        p.setPen(QPen(txt_col))
        label = "裁切區"
        fm = QFontMetrics(fnt)
        lw = fm.horizontalAdvance(label)

        for bx in (px, px + pw - mask_w):
            if mask_w >= lw + 4:
                cx = bx + (mask_w - lw) // 2
                p.drawText(QRect(cx, py + 6, lw + 2, 16), Qt.AlignmentFlag.AlignCenter, label)

        p.end()


# ── Safe Zone 切換按鈕 ────────────────────────────────────────────────────────

def _draw_safezone_icon(p: QPainter, cx: int, cy: int, col: QColor) -> None:
    """安全區圖示：外框矩形 + 左右半透明遮罩條 + 中間虛線分隔。"""
    pen = QPen(col, 2, Qt.PenStyle.SolidLine,
               Qt.PenCapStyle.SquareCap, Qt.PenJoinStyle.MiterJoin)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    # 外框
    p.drawRect(cx - 9, cy - 6, 18, 12)
    # 左右遮罩色塊
    fill = QColor(col); fill.setAlpha(70)
    p.setBrush(QBrush(fill))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawRect(cx - 9, cy - 6, 4, 12)
    p.drawRect(cx + 5, cy - 6, 4, 12)
    # 分隔虛線
    dash = QPen(col, 1, Qt.PenStyle.DashLine)
    dash.setDashPattern([2, 2])
    p.setPen(dash)
    p.drawLine(cx - 5, cy - 5, cx - 5, cy + 5)
    p.drawLine(cx + 5, cy - 5, cx + 5, cy + 5)


class _SafeZoneToggleBtn(QWidget):
    """顯示/隱藏安全區遮罩的切換按鈕，風格與 _TopBarBtn 完全一致。"""
    toggled = pyqtSignal(bool)

    _H = 36

    def __init__(self, parent=None):
        super().__init__(parent)
        self._on      = False
        self._hovered = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setFixedHeight(self._H)
        # 計算寬度（與 _TopBarBtn 相同邏輯）
        label_on  = "隱藏安全區"
        label_off = "顯示安全區"
        fm = QFontMetrics(T.ui_font(T.FONT_SM))
        w = max(fm.horizontalAdvance(label_on), fm.horizontalAdvance(label_off)) + 32 + 20
        self.setFixedWidth(max(w, 110))
        self.hide()
        _tm().theme_changed.connect(lambda _: self.update())

    def set_on(self, v: bool) -> None:
        self._on = v
        self.update()

    def enterEvent(self, e) -> None:
        self._hovered = True; self.update(); super().enterEvent(e)

    def leaveEvent(self, e) -> None:
        self._hovered = False; self.update(); super().leaveEvent(e)

    def mousePressEvent(self, e) -> None:
        if e.button() == Qt.MouseButton.LeftButton:
            self._on = not self._on
            self.toggled.emit(self._on)
            self.update()

    def paintEvent(self, _) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()
        R = T.R_CHIP
        M = 2

        # ── 背景與邊框（與 _TopBarBtn 邏輯完全對齊）──
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

        # ── 向量圖示（左側）──
        _draw_safezone_icon(p, 18, H // 2, icon_col)

        # ── 文字標籤（圖示右方）──
        p.setFont(T.ui_font(T.FONT_SM, weight))
        p.setPen(QPen(text_col))
        label = "隱藏安全區" if self._on else "顯示安全區"
        p.drawText(
            QRect(34, 0, W - 38, H),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            label,
        )
        p.end()


# ── Safe Zone 資訊列 ──────────────────────────────────────────────────────────

class SafeZoneInfoBar(QWidget):
    """底部提示列，說明目前比例的 IG 網格 safe zone。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._text = ""
        self.setFixedHeight(26)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.hide()
        _tm().theme_changed.connect(lambda _: self.update())

    def set_preset(self, preset: AspectRatioPreset) -> None:
        text = _SAFE_ZONE_TEXT.get(preset, "")
        self._text = text
        self.setVisible(bool(text))
        self.update()

    def paintEvent(self, _) -> None:
        if not self._text:
            return
        p = QPainter(self)
        W, H = self.width(), self.height()

        # 背景
        bg = QColor(T.WARNING)
        bg.setAlpha(25)
        p.fillRect(0, 0, W, H, QBrush(bg))

        # 上邊線
        p.setPen(QPen(QColor(T.WARNING), 1))
        p.drawLine(0, 0, W, 0)

        # 文字
        p.setFont(T.ui_font(T.FONT_XS))
        warn_c = QColor(T.WARNING)
        p.setPen(QPen(warn_c))
        p.drawText(QRect(12, 0, W - 24, H), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, self._text)
        p.end()


# ── Spinner overlay ───────────────────────────────────────────────────────────

class SpinnerOverlay(QWidget):
    """Rotating arc shown in top-right corner during processing."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(28, 28)
        self._angle = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.hide()

    def start(self) -> None:
        self.show()
        self._timer.start(40)   # 25 fps

    def stop(self) -> None:
        self._timer.stop()
        self.hide()

    def _tick(self) -> None:
        self._angle = (self._angle + 14) % 360
        self.update()

    def paintEvent(self, e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QPen(
            QColor(T.PRIMARY), 2.5,
            Qt.PenStyle.SolidLine,
            Qt.PenCapStyle.RoundCap,
        ))
        p.translate(14, 14)
        p.rotate(self._angle)
        p.drawArc(-9, -9, 18, 18, 0, 270 * 16)
        p.end()


# ── SPLIT 移動模式按鈕 ────────────────────────────────────────────────────────

def _draw_move_icon(p: QPainter, cx: int, cy: int, col: QColor) -> None:
    """四向箭頭圖示。"""
    pen = QPen(col, 2, Qt.PenStyle.SolidLine,
               Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    for dx, dy in [(0, -1), (0, 1), (-1, 0), (1, 0)]:
        ax, ay = cx + dx * 8, cy + dy * 8
        p.drawLine(cx, cy, ax, ay)
        p.drawLine(ax, ay, ax - dy * 4 - dx * 4, ay - dx * 4 + dy * 0)
        p.drawLine(ax, ay, ax + dy * 4 - dx * 4, ay + dx * 4 + dy * 0)


class _SplitMoveBtn(QWidget):
    """切換 SPLIT 移動模式的按鈕，風格與 _SafeZoneToggleBtn 一致。"""
    toggled = pyqtSignal(bool)

    _H = 36

    def __init__(self, parent=None):
        super().__init__(parent)
        self._on      = False
        self._hovered = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setFixedHeight(self._H)
        label_on  = "完成移動"
        label_off = "移動圖片"
        fm = QFontMetrics(T.ui_font(T.FONT_SM))
        w = max(fm.horizontalAdvance(label_on), fm.horizontalAdvance(label_off)) + 32 + 20
        self.setFixedWidth(max(w, 100))
        _tm().theme_changed.connect(lambda _: self.update())

    @property
    def is_on(self) -> bool:
        return self._on

    def set_on(self, v: bool) -> None:
        self._on = v
        self.update()

    def enterEvent(self, e) -> None:
        self._hovered = True; self.update(); super().enterEvent(e)

    def leaveEvent(self, e) -> None:
        self._hovered = False; self.update(); super().leaveEvent(e)

    def mousePressEvent(self, e) -> None:
        if e.button() == Qt.MouseButton.LeftButton:
            self._on = not self._on
            self.toggled.emit(self._on)
            self.update()

    def paintEvent(self, _) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()
        R, M = T.R_CHIP, 2

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
        _draw_move_icon(p, 18, H // 2, icon_col)
        p.setFont(T.ui_font(T.FONT_SM, weight))
        p.setPen(QPen(text_col))
        label = "完成移動" if self._on else "移動圖片"
        p.drawText(QRect(34, 0, W - 38, H),
                   Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, label)
        p.end()


# ── SPLIT 拖曳覆蓋層 ──────────────────────────────────────────────────────────

class _SplitDragOverlay(QWidget):
    """移動模式覆蓋層：
    • 照片面板顯示完整原始照片（letterbox），讓使用者看到原圖全貌
    • 橘色虛線框 = 目前裁切框（輸出會顯示的範圍）
    • 框內正常顯示，框外灰色遮罩
    • 拖曳移動裁切框，按「完成移動」才 emit 一次
    """
    dragged = pyqtSignal(float, float)

    _SPLIT_LEFT = 0.35

    def __init__(self, parent, photo_lbl: "QLabel"):
        super().__init__(parent)
        self._photo_lbl = photo_lbl
        self.setMouseTracking(True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self._drag_start = None
        self._crop_x: float = 0.5
        self._crop_y: float = 0.5
        self._cx0:    float = 0.5
        self._cy0:    float = 0.5
        self._photo_pix: "QPixmap | None" = None
        self._photo_w:   int = 1
        self._photo_h:   int = 1
        self.hide()

    def set_crop(self, cx: float, cy: float) -> None:
        self._crop_x = cx
        self._crop_y = cy
        self.update()

    def set_photo(self, pix: "QPixmap", w: int, h: int) -> None:
        self._photo_pix = pix
        self._photo_w   = max(1, w)
        self._photo_h   = max(1, h)

    def get_crop(self) -> tuple[float, float]:
        return self._crop_x, self._crop_y

    def _panel_rect(self) -> "QRect | None":
        pix = self._photo_lbl.pixmap()
        if pix is None or pix.isNull():
            return None
        cw, ch = self.width(), self.height()
        pw, ph = pix.width(), pix.height()
        off_x  = (cw - pw) // 2
        off_y  = (ch - ph) // 2
        left_w = int(pw * self._SPLIT_LEFT)
        return QRect(off_x + left_w, off_y, pw - left_w, ph)

    def _crop_rect(self, panel: "QRect") -> "QRect":
        """裁切框在 overlay 的位置（fill→fit 座標轉換）。"""
        if self._photo_pix is None or self._photo_pix.isNull():
            return panel
        pw, ph       = self._photo_w, self._photo_h
        pan_w, pan_h = panel.width(), panel.height()
        fill_s = max(pan_w / pw, pan_h / ph)
        avail_x = max(0.0, pw * fill_s - pan_w)
        avail_y = max(0.0, ph * fill_s - pan_h)
        fit_s  = min(pan_w / pw, pan_h / ph)
        ratio  = fit_s / fill_s
        fit_w  = int(pw * fit_s)
        fit_h  = int(ph * fit_s)
        fx = panel.x() + (pan_w - fit_w) // 2
        fy = panel.y() + (pan_h - fit_h) // 2
        return QRect(
            fx + int(avail_x * self._crop_x * ratio),
            fy + int(avail_y * self._crop_y * ratio),
            int(pan_w * ratio),
            int(pan_h * ratio),
        )

    def paintEvent(self, _) -> None:
        panel = self._panel_rect()
        if panel is None:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        # 原圖 fill-scale，依 crop 偏移繪製（圖片在固定框內移動）
        if self._photo_pix and not self._photo_pix.isNull():
            pw, ph  = self._photo_w, self._photo_h
            pan_w   = panel.width()
            pan_h   = panel.height()
            fill_s  = max(pan_w / pw, pan_h / ph)
            fill_w  = int(pw * fill_s)
            fill_h  = int(ph * fill_s)
            avail_x = max(0, fill_w - pan_w)
            avail_y = max(0, fill_h - pan_h)
            src_x   = int(avail_x * self._crop_x)
            src_y   = int(avail_y * self._crop_y)
            scaled  = self._photo_pix.scaled(
                fill_w, fill_h,
                Qt.AspectRatioMode.IgnoreAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            p.setClipRect(panel)
            p.drawPixmap(panel.x() - src_x, panel.y() - src_y, scaled)
            p.setClipping(False)

        # 固定橘色虛線框住面板邊緣
        pen = QPen(QColor(255, 140, 0), 2, Qt.PenStyle.DashLine)
        pen.setDashPattern([8, 4])
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(panel.adjusted(1, 1, -1, -1))
        p.end()

    # ── 滑鼠事件 ──────────────────────────────────────────────────────────────

    def enterEvent(self, e) -> None:
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        super().enterEvent(e)

    def mousePressEvent(self, e) -> None:
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag_start = e.pos()
            self._cx0 = self._crop_x
            self._cy0 = self._crop_y
            self.setCursor(Qt.CursorShape.ClosedHandCursor)

    def mouseMoveEvent(self, e) -> None:
        if self._drag_start is None:
            return
        panel = self._panel_rect()
        if panel is None:
            return
        delta  = e.pos() - self._drag_start
        pw     = max(1, panel.width())
        ph     = max(1, panel.height())
        self._crop_x = max(0.0, min(1.0, self._cx0 - delta.x() / pw * 2.0))
        self._crop_y = max(0.0, min(1.0, self._cy0 - delta.y() / ph * 2.0))
        self.update()   # 只重繪覆蓋層，不重新渲染輸出圖

    def mouseReleaseEvent(self, e) -> None:
        if e.button() == Qt.MouseButton.LeftButton and self._drag_start is not None:
            self._drag_start = None
            self.setCursor(Qt.CursorShape.OpenHandCursor)


# ── Thumbnail strip ───────────────────────────────────────────────────────────

class ThumbItem(QWidget):
    """縮圖項目 — QPainter 繪製。
    左鍵：切換預覽並清除多選。Ctrl+點擊：加入/移出多選。Shift+點擊：範圍選取。"""
    clicked        = pyqtSignal(int)
    ctrl_clicked   = pyqtSignal(int)
    shift_clicked  = pyqtSignal(int)
    delete_clicked = pyqtSignal(int)

    _SZ  = 68   # 縮圖本體大小（widget = _SZ + 4px 視覺 margin）
    _DEL = 20   # 刪除按鈕大小

    def __init__(self, idx: int, pixmap: QPixmap, parent=None):
        super().__init__(parent)
        self._idx      = idx
        self._selected = False
        self._synced   = False
        self._hovered  = False
        W = self._SZ + 8   # widget 寬高 = 縮圖 + 上下各 4px 間距
        self.setFixedSize(W, W)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setToolTip("Ctrl＋點擊 加入多選　Shift＋點擊 範圍選取")
        _tm().theme_changed.connect(lambda _: self.update())
        self._set_pixmap(pixmap)

    def _set_pixmap(self, pixmap: QPixmap) -> None:
        """縮放後裁切至中央正方形，避免非正方形照片被拉伸。"""
        _scaled = pixmap.scaled(
            self._SZ, self._SZ,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        ox = (_scaled.width()  - self._SZ) // 2
        oy = (_scaled.height() - self._SZ) // 2
        self._pix = _scaled.copy(ox, oy, self._SZ, self._SZ)

    def update_pixmap(self, pixmap: QPixmap) -> None:
        """替換縮圖（RAW 完整解碼後呼叫）。"""
        self._set_pixmap(pixmap)
        self.update()

    # ── Public ────────────────────────────────────────────────────────────────

    def reindex(self, idx: int) -> None:
        self._idx = idx

    def set_selected(self, v: bool) -> None:
        if self._selected != v:
            self._selected = v
            self.update()

    def set_synced(self, v: bool) -> None:
        if self._synced != v:
            self._synced = v
            self.update()

    # ── Events ────────────────────────────────────────────────────────────────

    def enterEvent(self, e) -> None:
        self._hovered = True;  self.update(); super().enterEvent(e)

    def leaveEvent(self, e) -> None:
        self._hovered = False; self.update(); super().leaveEvent(e)

    def _del_rect(self) -> QRect:
        s = self._DEL
        W = self.width()
        return QRect(W - s - 5, 5, s, s)

    def _del_btn_brightness(self) -> int:
        """Sample average brightness of the pixmap area under the delete button."""
        dr = self._del_rect()
        M  = 4
        # _pix is already _SZ×_SZ; del rect is relative to widget, subtract margin
        sx = max(0, dr.x() - M)
        sy = max(0, dr.y() - M)
        sw = min(dr.width(), self._pix.width()  - sx)
        sh = min(dr.height(), self._pix.height() - sy)
        if sw <= 0 or sh <= 0:
            return 128
        sample = self._pix.copy(sx, sy, sw, sh).toImage()
        total, count = 0, 0
        for x in range(0, sample.width(), 2):
            for y in range(0, sample.height(), 2):
                c = QColor(sample.pixel(x, y))
                total += (c.red() * 299 + c.green() * 587 + c.blue() * 114) // 1000
                count += 1
        return total // max(1, count)

    def mousePressEvent(self, e) -> None:
        if e.button() != Qt.MouseButton.LeftButton:
            return
        mods = e.modifiers()
        if self._hovered and self._del_rect().contains(e.pos()):
            self.delete_clicked.emit(self._idx)
        elif mods & Qt.KeyboardModifier.ShiftModifier:
            self.shift_clicked.emit(self._idx)
        elif mods & Qt.KeyboardModifier.ControlModifier:
            self.ctrl_clicked.emit(self._idx)
        else:
            self.clicked.emit(self._idx)

    # ── Paint ─────────────────────────────────────────────────────────────────

    def paintEvent(self, _) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W = self.width()
        M = 4          # 縮圖四邊 margin
        S = W - M * 2  # 縮圖實際邊長

        # ── 縮圖（圓角裁切）──
        clip = QPainterPath()
        clip.addRoundedRect(QRectF(M, M, S, S), T.R_CHIP, T.R_CHIP)
        p.setClipPath(clip)
        p.drawPixmap(M, M, S, S, self._pix)
        p.setClipping(False)

        # ── 邊框 ──
        if self._selected or self._synced or self._hovered:
            col = QColor(T.TEXT_PRIMARY)
            col.setAlpha(200 if (self._selected or self._synced) else 100)
            pen = QPen(col, 2.0, Qt.PenStyle.DashLine)
            pen.setDashPattern([5, 3])
        else:
            pen = QPen(QColor(T.BORDER_LIGHT), 1.0)

        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        hw = pen.widthF() / 2
        if self._selected or self._synced:
            # 選取框畫在 widget 外圍，利用 M=4px margin 與圖片產生自然間距
            p.drawRoundedRect(
                QRectF(hw, hw, W - pen.widthF(), W - pen.widthF()),
                T.R_CHIP + 2, T.R_CHIP + 2,
            )
        else:
            p.drawRoundedRect(
                QRectF(M + hw, M + hw, S - pen.widthF(), S - pen.widthF()),
                T.R_CHIP, T.R_CHIP,
            )

        # ── 刪除按鈕（左下角，懸停時顯示）── 純 × 符號，自適應黑白
        if self._hovered:
            dr  = self._del_rect()
            cx  = dr.center().x()
            cy  = dr.center().y()
            d   = 4
            bright = self._del_btn_brightness()
            x_color = "#000000" if bright > 160 else "#ffffff"
            xpen = QPen(QColor(x_color), 2.0,
                        Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
            p.setPen(xpen)
            p.drawLine(int(cx - d), int(cy - d), int(cx + d), int(cy + d))
            p.drawLine(int(cx + d), int(cy - d), int(cx - d), int(cy + d))

        p.end()


class ImageStrip(QScrollArea):
    photo_selected = pyqtSignal(int)
    sync_changed   = pyqtSignal(object)   # set[int] — 同步群組索引集合
    delete_requested = pyqtSignal(int)    # 要刪除的照片索引

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(92)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._body = QWidget()
        self._row  = QHBoxLayout(self._body)
        self._row.setContentsMargins(T.S3, 0, T.S3, 0)
        self._row.setSpacing(T.S2)
        self._row.addStretch()
        self.setWidget(self._body)
        self.setWidgetResizable(True)
        self._thumbs: list[ThumbItem] = []
        self._synced: set[int] = set()
        self._cur = 0
        self._anchor = 0   # Shift 選取的起始錨點
        self._apply()
        _tm().theme_changed.connect(lambda _: self._apply())

    def wheelEvent(self, e) -> None:
        """滑鼠滾輪橫向捲動縮圖列。"""
        bar = self.horizontalScrollBar()
        delta = e.angleDelta().y()
        bar.setValue(bar.value() - delta // 2)
        e.accept()

    def _apply(self) -> None:
        self.setStyleSheet(f"""
            QScrollArea {{ background: {T.IMG_LIST_BG}; border: none;
                border-top: 1px solid {T.BORDER}; }}
            QScrollBar:horizontal {{
                height: 6px; background: transparent; margin: 0;
            }}
            QScrollBar::handle:horizontal {{
                background: {T.BORDER_LIGHT}; border-radius: 3px; min-width: 24px;
            }}
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{ background: none; }}
            {T.scrollbar_qss()}
        """)
        self._body.setStyleSheet(f"background: {T.IMG_LIST_BG};")

    # ── Public API ────────────────────────────────────────────────────────────

    def add_photo(self, pil_image: Image.Image) -> int:
        idx = len(self._thumbs)
        th  = ThumbItem(idx, _pil_to_pixmap(pil_image))
        th.clicked.connect(self._on_click)
        th.ctrl_clicked.connect(self._on_ctrl_click)
        th.shift_clicked.connect(self._on_shift_click)
        th.delete_clicked.connect(self.delete_requested)
        self._thumbs.append(th)
        self._row.insertWidget(self._row.count() - 1, th)
        self.set_current(idx)
        return idx

    def update_thumb(self, idx: int, pil_image: Image.Image) -> None:
        """替換指定索引的縮圖圖片（RAW 完整解碼後使用）。"""
        if 0 <= idx < len(self._thumbs):
            self._thumbs[idx].update_pixmap(_pil_to_pixmap(pil_image))

    def set_current(self, idx: int) -> None:
        for i, t in enumerate(self._thumbs):
            t.set_selected(i == idx)
        self._cur = idx

    def remove_photo(self, idx: int) -> None:
        """移除索引 idx 的縮圖並重新編號。"""
        if idx < 0 or idx >= len(self._thumbs):
            return
        th = self._thumbs.pop(idx)
        self._row.removeWidget(th)
        th.deleteLater()
        # 更新同步集合：移除 idx，idx 之後的索引 -1
        self._synced.discard(idx)
        self._synced = {i if i < idx else i - 1 for i in self._synced}
        # 重新給所有後續縮圖編號
        for i in range(idx, len(self._thumbs)):
            self._thumbs[i].reindex(i)
            self._thumbs[i].set_synced(i in self._synced)
        # 修正 _cur
        if self._thumbs:
            self._cur = min(self._cur, len(self._thumbs) - 1)
            if self._cur >= idx:
                self._cur = max(0, self._cur - 1) if self._cur == idx else self._cur - 1
            self.set_current(self._cur)
        self.sync_changed.emit(set(self._synced))

    def synced_indices(self) -> set[int]:
        return set(self._synced)

    def count(self) -> int:
        return len(self._thumbs)

    # ── Slots ─────────────────────────────────────────────────────────────────

    def _on_click(self, idx: int) -> None:
        # 一般點擊：清除所有多選，更新錨點，切換預覽
        if self._synced:
            self._synced.clear()
            for t in self._thumbs:
                t.set_synced(False)
            self.sync_changed.emit(set())
        self._anchor = idx
        self.set_current(idx)
        self.photo_selected.emit(idx)

    def _on_ctrl_click(self, idx: int) -> None:
        # Ctrl：切換單張多選，更新錨點
        if idx in self._synced:
            self._synced.discard(idx)
        else:
            self._synced.add(idx)
        self._thumbs[idx].set_synced(idx in self._synced)
        self._anchor = idx
        self.sync_changed.emit(set(self._synced))

    def _on_shift_click(self, idx: int) -> None:
        # Shift：從錨點到此次點擊的範圍全部加入多選
        lo, hi = min(self._anchor, idx), max(self._anchor, idx)
        for i in range(lo, hi + 1):
            self._synced.add(i)
            self._thumbs[i].set_synced(True)
        # 切換預覽到點擊的那張
        self.set_current(idx)
        self.photo_selected.emit(idx)
        self.sync_changed.emit(set(self._synced))


# ── Zoom Control ─────────────────────────────────────────────────────────────

_ZOOM_PRESETS: list[tuple[str, float]] = [
    ("適合視窗", 1.0),
    ("50%",   0.5),
    ("75%",   0.75),
    ("100%",  1.0),   # alias for 適合視窗
    ("125%",  1.25),
    ("150%",  1.5),
    ("200%",  2.0),
    ("300%",  3.0),
]

_ZOOM_STEP = 0.15   # +/- 按鈕每次增減量


def _zoom_label(zoom: float) -> str:
    """1.0 → '適合'，其他顯示百分比。"""
    if abs(zoom - 1.0) < 0.01:
        return "適合"
    return f"{round(zoom * 100)}%"


class _ZoomControl(QWidget):
    """縮放控制列：[−]  適合 ▾  [+]
    • −/+ 按鈕調整縮放
    • 中間標籤點擊彈出預設清單
    • theme-aware
    """
    zoom_changed = pyqtSignal(float)   # 新的縮放值

    _H  = 30    # 元件高度
    _BW = 28    # −/+ 按鈕寬度
    _R  = 6     # 圓角

    def __init__(self, parent=None):
        super().__init__(parent)
        self._zoom: float = 1.0
        self._hover_zone: int = 0   # 0=none 1=minus 2=label 3=plus
        self.setFixedHeight(self._H)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setMouseTracking(True)
        self.hide()
        _tm().theme_changed.connect(lambda _: self.update())
        self._recalc_width()

    def set_zoom(self, zoom: float) -> None:
        self._zoom = zoom
        self._recalc_width()
        self.update()

    def _recalc_width(self) -> None:
        fm = QFontMetrics(T.ui_font(T.FONT_SM))
        label_w = fm.horizontalAdvance(_zoom_label(self._zoom)) + 24 + 10  # text + arrow gap
        self.setFixedWidth(self._BW * 2 + max(label_w, 52))

    # ── 區域計算 ────────────────────────────────────────────────────────────

    def _minus_rect(self) -> QRect:
        return QRect(0, 0, self._BW, self._H)

    def _plus_rect(self) -> QRect:
        return QRect(self.width() - self._BW, 0, self._BW, self._H)

    def _label_rect(self) -> QRect:
        return QRect(self._BW, 0, self.width() - self._BW * 2, self._H)

    def _zone_at(self, pos) -> int:
        if self._minus_rect().contains(pos): return 1
        if self._plus_rect().contains(pos):  return 3
        if self._label_rect().contains(pos): return 2
        return 0

    # ── 事件 ────────────────────────────────────────────────────────────────

    def mouseMoveEvent(self, e) -> None:
        z = self._zone_at(e.pos())
        if z != self._hover_zone:
            self._hover_zone = z
            self.setCursor(Qt.CursorShape.PointingHandCursor if z else Qt.CursorShape.ArrowCursor)
            self.update()

    def leaveEvent(self, e) -> None:
        self._hover_zone = 0
        self.update()
        super().leaveEvent(e)

    def mousePressEvent(self, e) -> None:
        if e.button() != Qt.MouseButton.LeftButton:
            return
        zone = self._zone_at(e.pos())
        if zone == 1:
            new_z = max(0.3, self._zoom - _ZOOM_STEP)
            self._emit(new_z)
        elif zone == 3:
            new_z = min(6.0, self._zoom + _ZOOM_STEP)
            self._emit(new_z)
        elif zone == 2:
            self._show_presets_menu()

    def _emit(self, zoom: float) -> None:
        self._zoom = zoom
        self._recalc_width()
        self.update()
        self.zoom_changed.emit(zoom)

    def _show_presets_menu(self) -> None:
        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{
                background: {T.SURFACE};
                border: 1px solid {T.BORDER};
                border-radius: 8px;
                padding: 4px 0;
                font-size: {T.FONT_SM}px;
                color: {T.TEXT_PRIMARY};
            }}
            QMenu::item {{
                padding: 6px 20px;
                border-radius: 4px;
                margin: 1px 4px;
            }}
            QMenu::item:selected {{
                background: {T.PRIMARY_ALPHA};
                color: {T.TEXT_PRIMARY};
            }}
            QMenu::item:checked {{
                font-weight: bold;
            }}
        """)
        seen = set()
        for label, val in _ZOOM_PRESETS:
            key = round(val * 100)
            if key in seen:
                continue
            seen.add(key)
            act = menu.addAction(label)
            act.setCheckable(True)
            act.setChecked(abs(self._zoom - val) < 0.01)
            act.setData(val)
        menu.triggered.connect(lambda a: self._emit(a.data()))
        # 在元件左下方彈出
        menu.exec(self.mapToGlobal(self.rect().bottomLeft()))

    # ── 繪製 ────────────────────────────────────────────────────────────────

    def paintEvent(self, _) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H, R = self.width(), self.height(), self._R

        # ── 背景膠囊 ──
        bg = QColor(T.SURFACE)
        bg.setAlpha(220)
        p.setBrush(QBrush(bg))
        p.setPen(QPen(QColor(T.BORDER), 1.0))
        p.drawRoundedRect(QRectF(0.5, 0.5, W - 1, H - 1), R, R)

        # ── 分隔線 ──
        div_col = QColor(T.BORDER)
        div_col.setAlpha(120)
        p.setPen(QPen(div_col, 1))
        bw = self._BW
        p.drawLine(bw, 4, bw, H - 4)
        p.drawLine(W - bw, 4, W - bw, H - 4)

        # ── − 按鈕 ──
        m_col = QColor(T.PRIMARY if self._hover_zone == 1 else T.TEXT_SECONDARY)
        p.setPen(QPen(m_col, 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        cx = bw // 2
        cy = H // 2
        p.drawLine(cx - 5, cy, cx + 5, cy)

        # ── + 按鈕 ──
        p_col = QColor(T.PRIMARY if self._hover_zone == 3 else T.TEXT_SECONDARY)
        p.setPen(QPen(p_col, 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        rx = W - bw // 2
        p.drawLine(rx - 5, cy, rx + 5, cy)
        p.drawLine(rx, cy - 5, rx, cy + 5)

        # ── 標籤文字 + ▾ ──
        lbl = _zoom_label(self._zoom)
        fnt = T.ui_font(T.FONT_SM, QFont.Weight.Medium)
        p.setFont(fnt)
        lbl_col = QColor(T.PRIMARY if self._hover_zone == 2 else T.TEXT_PRIMARY)
        p.setPen(QPen(lbl_col))
        lr = self._label_rect()
        fm = QFontMetrics(fnt)
        tw = fm.horizontalAdvance(lbl)
        arr_gap = 10   # space for ▾
        total   = tw + arr_gap
        tx = lr.x() + (lr.width() - total) // 2
        p.drawText(QRect(tx, 0, tw + 2, H), Qt.AlignmentFlag.AlignVCenter, lbl)

        # 小箭頭 ▾
        arrow_col = QColor(T.PRIMARY if self._hover_zone == 2 else T.TEXT_SECONDARY)
        p.setPen(QPen(arrow_col, 1.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        ax = tx + tw + 6
        ay = H // 2
        path = QPainterPath()
        path.moveTo(ax - 3, ay - 1)
        path.lineTo(ax,     ay + 2)
        path.lineTo(ax + 3, ay - 1)
        p.drawPath(path)

        p.end()


# ── Before/After Compare Overlay ─────────────────────────────────────────────

class _CompareOverlay(QWidget):
    """半屏 Before/After 比較覆蓋層。
    左半：before 圖（原圖）；右半：after 圖（當前 _photo_lbl）。
    中間繪製金色分隔線，左右上角各有文字標籤。
    """

    def __init__(self, parent: QWidget, photo_lbl: QLabel):
        super().__init__(parent)
        self._photo_lbl = photo_lbl
        self._before: QPixmap | None = None
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        _tm().theme_changed.connect(lambda _: self.update())

    def set_before(self, pix: QPixmap) -> None:
        self._before = pix
        self.update()

    def paintEvent(self, _) -> None:
        after_pix = self._photo_lbl.pixmap()
        if after_pix is None or after_pix.isNull():
            return

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        W, H = self.width(), self.height()
        mid = W // 2

        # ── 計算照片顯示區域（KeepAspectRatio AlignCenter，同 _photo_lbl）──
        pw, ph = after_pix.width(), after_pix.height()
        off_x = (W - pw) // 2
        off_y = (H - ph) // 2
        photo_rect = QRect(off_x, off_y, pw, ph)

        # 左半：before 圖
        if self._before and not self._before.isNull():
            # Scale before to same size as the displayed after pixmap
            before_scaled = self._before.scaled(
                pw, ph,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            bw = before_scaled.width()
            bh = before_scaled.height()
            bx = off_x + (pw - bw) // 2
            by = off_y + (ph - bh) // 2
            p.setClipRect(QRect(0, 0, mid, H))
            p.drawPixmap(bx, by, before_scaled)
            p.setClipping(False)

        # 右半：after 圖（來自 _photo_lbl，已渲染好）
        p.setClipRect(QRect(mid, 0, W - mid, H))
        p.drawPixmap(off_x, off_y, after_pix)
        p.setClipping(False)

        # ── 金色分隔線 ──
        gold_col = QColor(T.GOLD)
        p.setPen(QPen(gold_col, 2, Qt.PenStyle.SolidLine))
        p.drawLine(mid, 0, mid, H)

        # ── 文字標籤 ──
        label_font = T.ui_font(T.FONT_SM, QFont.Weight.Bold)
        p.setFont(label_font)

        def _draw_badge(text: str, x: int, align_right: bool) -> None:
            fm = QFontMetrics(label_font)
            tw = fm.horizontalAdvance(text)
            pad_x, pad_y = 8, 4
            bw = tw + pad_x * 2
            bh = fm.height() + pad_y * 2
            by = 16
            bx = x - bw - 8 if align_right else x + 8
            bg = QColor(0, 0, 0, 160)
            p.setBrush(QBrush(bg))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(QRectF(bx, by, bw, bh), 4, 4)
            p.setPen(QPen(gold_col if align_right else QColor("#ffffff")))
            p.drawText(QRect(bx + pad_x, by + pad_y, tw, fm.height()), 0, text)

        _draw_badge("BEFORE", mid, True)
        _draw_badge("AFTER",  mid, False)

        p.end()


# ── Preview Panel ─────────────────────────────────────────────────────────────

class PreviewPanel(QWidget):
    open_file_requested = pyqtSignal()
    photo_switched      = pyqtSignal(int)
    split_crop_changed  = pyqtSignal(float, float)   # (crop_x, crop_y) 0-1
    split_zoom_changed  = pyqtSignal(float)           # zoom 0.5-4.0

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._apply_bg()

        # Canvas widget (holds drop zone, photo label, overlays)
        self._canvas = QWidget(self)
        self._canvas.setStyleSheet(f"background: {T.PREVIEW_BG};")

        self._drop = DropZone(self._canvas)
        self._drop.clicked.connect(self.open_file_requested)

        self._photo_lbl = QLabel(self._canvas)
        self._photo_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._photo_lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._photo_lbl.hide()

        self._opacity = QGraphicsOpacityEffect(self._photo_lbl)
        self._photo_lbl.setGraphicsEffect(self._opacity)
        self._fade = QPropertyAnimation(self._opacity, b"opacity")
        self._fade.setDuration(T.ANIM_SLOW)
        self._fade.setEasingCurve(QEasingCurve.Type.OutCubic)

        # Safe zone overlay（在 photo_lbl 上方）
        self._safe_overlay = SafeZoneOverlay(self._photo_lbl, self._canvas)

        # Safe zone 切換按鈕（左上角）
        self._sz_toggle = _SafeZoneToggleBtn(self._canvas)
        self._sz_toggle.toggled.connect(self._on_sz_toggle)

        self._spinner = SpinnerOverlay(self._canvas)

        # Safe zone 切換按鈕下方：SPLIT 移動模式按鈕
        self._move_btn = _SplitMoveBtn(self._canvas)
        self._move_btn.toggled.connect(self._on_move_toggle)
        self._move_btn.hide()

        # 資訊列（canvas 下方，strip 上方）
        self._info_bar = SafeZoneInfoBar(self)

        self._strip = ImageStrip(self)
        self._strip.hide()
        self._strip.photo_selected.connect(self.photo_switched)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(self._canvas, 1)
        outer.addWidget(self._info_bar, 0)
        outer.addWidget(self._strip, 0)

        # SPLIT 拖曳覆蓋層（canvas 最上層，移動模式才顯示）
        self._split_drag = _SplitDragOverlay(self._canvas, self._photo_lbl)
        # 不直接 connect dragged → split_crop_changed，改由按鈕控制

        # 縮放控制列（右下角浮動）
        self._zoom_ctrl = _ZoomControl(self._canvas)
        self._zoom_ctrl.zoom_changed.connect(self._on_zoom_ctrl_changed)

        # Before/After 浮動指示標籤
        self._ba_label = QLabel(self._canvas)
        self._ba_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._ba_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._ba_label.hide()

        self._pixmap: QPixmap | None = None
        self._has_image = False
        self._sz_preset = None
        self._template: TemplateStyle = TemplateStyle.CLASSIC
        self._zoom: float = 1.0
        self._split_zoom: float = 1.0   # 最終輸出縮放，移動模式滾輪控制

        # Before/After 比較模式
        self._before_image: QPixmap | None = None
        self._compare_mode: bool = False
        # 比較覆蓋層（在 canvas 最上層繪製）
        self._compare_overlay = _CompareOverlay(self._canvas, self._photo_lbl)
        self._compare_overlay.hide()

        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        _tm().theme_changed.connect(self._on_theme)

    # ── 代理 ImageStrip 的同步 / 刪除信號給 MainWindow ────────────────────────

    @property
    def sync_changed(self):
        return self._strip.sync_changed

    @property
    def delete_requested(self):
        return self._strip.delete_requested

    def _apply_bg(self) -> None:
        self.setStyleSheet(f"background: {T.PREVIEW_BG};")

    def _on_theme(self, dark: bool) -> None:
        self._apply_bg()
        self._canvas.setStyleSheet(f"background: {T.PREVIEW_BG};")

    def resizeEvent(self, e) -> None:
        super().resizeEvent(e)
        self._fit()

    def wheelEvent(self, e) -> None:
        if not self._has_image:
            e.ignore()
            return
        delta = e.angleDelta().y()
        factor = 1.12 if delta > 0 else 1 / 1.12
        # 移動模式：滾輪控制最終輸出縮放（split_zoom）
        if self._move_btn.is_on:
            self._split_zoom = max(1.0, min(4.0, self._split_zoom * factor))
            self.split_zoom_changed.emit(self._split_zoom)
        else:
            self._zoom = max(0.3, min(6.0, self._zoom * factor))
            self._zoom_ctrl.set_zoom(self._zoom)
            self._fit()
        e.accept()

    def _on_zoom_ctrl_changed(self, zoom: float) -> None:
        self._zoom = max(0.3, min(6.0, zoom))
        self._fit()

    def set_aspect_ratio(self, preset: AspectRatioPreset) -> None:
        """比例改變時更新 safe zone 顯示。"""
        self._sz_preset = preset
        self._safe_overlay.set_preset(preset)
        self._info_bar.set_preset(preset)
        self._update_sz_toggle_visibility()

    def disable_safezone(self) -> None:
        """永久隱藏安全區按鈕與遮罩（調色步驟使用）。"""
        self._safezone_disabled = True
        self._sz_toggle.hide()
        self._safe_overlay.set_visible(False)

    def _update_sz_toggle_visibility(self) -> None:
        """安全區按鈕：只在有圖片 且 比例有 safe zone 時才顯示。"""
        if getattr(self, "_safezone_disabled", False):
            return
        preset   = getattr(self, "_sz_preset", None)
        has_zone = preset in _SAFE_ZONE_RATIO
        if self._has_image and has_zone:
            self._sz_toggle.show()
        else:
            self._sz_toggle.hide()
            self._safe_overlay.set_visible(False)
            self._sz_toggle.set_on(False)

    def _on_sz_toggle(self, on: bool) -> None:
        self._safe_overlay.set_visible(on)
        self._sz_toggle.set_on(on)

    def set_template(self, style: TemplateStyle) -> None:
        self._template = style
        is_split = style == TemplateStyle.SPLIT and self._has_image
        self._move_btn.setVisible(is_split)
        if not is_split:
            self._move_btn.set_on(False)
            self._split_drag.hide()
        QTimer.singleShot(0, self._fit)

    def _on_move_toggle(self, on: bool) -> None:
        if on:
            self._split_drag.setVisible(True)
            self._split_drag.raise_()
            # 按鈕必須在 overlay 上方，否則點擊被攔截
            self._move_btn.raise_()
        else:
            self._split_drag.hide()
            cx, cy = self._split_drag.get_crop()
            self.split_crop_changed.emit(cx, cy)

    def set_split_crop(self, cx: float, cy: float) -> None:
        """從外部更新 SPLIT 裁切位置，不觸發 emit。"""
        self._split_drag.set_crop(max(0.0, min(1.0, cx)), max(0.0, min(1.0, cy)))

    def set_split_zoom(self, zoom: float) -> None:
        """從外部更新 SPLIT 縮放，不觸發 emit。"""
        self._split_zoom = max(1.0, min(4.0, zoom))

    def show_before_after(self, mode: str | None) -> None:
        """mode: 'BEFORE' | 'AFTER' | None（隱藏）。"""
        if mode is None:
            self._ba_label.hide()
            return
        is_before = (mode == "BEFORE")
        bg   = "rgba(0,0,0,160)"
        text_col = "#ffffff" if is_before else T.PRIMARY
        lbl  = "◀ BEFORE" if is_before else "AFTER ▶"
        self._ba_label.setText(lbl)
        self._ba_label.setStyleSheet(f"""
            QLabel {{
                background: {bg};
                color: {text_col};
                font-size: {T.FONT_BASE}px;
                font-weight: 700;
                padding: 4px 12px;
                border-radius: 6px;
                letter-spacing: 1px;
            }}
        """)
        self._ba_label.adjustSize()
        cw = self._canvas.width()
        ch = self._canvas.height()
        self._ba_label.move(8, ch - self._ba_label.height() - 8)
        self._ba_label.show()
        self._ba_label.raise_()

    def set_split_photo(self, pil_image: "Image.Image") -> None:
        """傳入原始照片供移動模式顯示完整圖片。"""
        img  = pil_image.convert("RGB")
        long = max(img.width, img.height)
        if long > 900:
            s   = 900 / long
            img = img.resize((int(img.width * s), int(img.height * s)), Image.BILINEAR)
        self._split_drag.set_photo(_pil_to_pixmap(img), pil_image.width, pil_image.height)



    # ── Before/After 比較 ────────────────────────────────────────────────────

    def set_before(self, pixmap: "QPixmap") -> None:
        """儲存未調色的原始圖，供比較模式使用。"""
        self._before_image = pixmap
        self._compare_overlay.set_before(pixmap)

    def toggle_compare(self) -> None:
        """切換 Before/After 分割比較模式。"""
        self._compare_mode = not self._compare_mode
        if self._compare_mode and self._has_image:
            cw = self._canvas.width()
            ch = self._canvas.height()
            self._compare_overlay.setGeometry(0, 0, cw, ch)
            self._compare_overlay.show()
            self._compare_overlay.raise_()
            self._zoom_ctrl.raise_()
        else:
            self._compare_overlay.hide()

    def keyPressEvent(self, e) -> None:
        """反斜線（\\）鍵切換比較模式。"""
        if e.key() == Qt.Key.Key_Backslash:
            self.toggle_compare()
            e.accept()
        else:
            super().keyPressEvent(e)

    def current_pixmap(self) -> "QPixmap | None":
        return self._pixmap

    def show_image(self, pil_image: Image.Image) -> None:
        self._has_image = True
        self._pixmap = _pil_to_pixmap(pil_image)
        self._drop.hide()
        self._photo_lbl.show()
        self._move_btn.setVisible(self._template == TemplateStyle.SPLIT)
        self._zoom_ctrl.set_zoom(self._zoom)
        self._zoom_ctrl.show()
        self._update_sz_toggle_visibility()
        # Defer _fit() so the layout (incl. image strip) settles first
        QTimer.singleShot(0, self._fit)
        self._opacity.setOpacity(0.0)
        self._fade.stop()
        self._fade.setStartValue(0.0)
        self._fade.setEndValue(1.0)
        self._fade.start()

    def show_drop_zone(self) -> None:
        self._has_image = False
        self._pixmap = None
        self._photo_lbl.hide()
        self._split_drag.hide()
        self._zoom_ctrl.hide()
        self._move_btn.hide()
        self._move_btn.set_on(False)
        self._drop.show()
        self._update_sz_toggle_visibility()

    def set_drag_highlight(self, v: bool) -> None:
        if self._drop.isVisible():
            self._drop.set_drag(v)

    def start_spinner(self) -> None:
        cw = self._canvas.width()
        self._spinner.move(cw - 36, 8)
        self._spinner.start()

    def stop_spinner(self) -> None:
        self._spinner.stop()

    def add_to_strip(self, pil_image: Image.Image) -> int:
        idx = self._strip.add_photo(pil_image)
        if self._strip.count() >= 1:
            self._strip.show()
            QTimer.singleShot(0, self._fit)
        return idx

    def remove_from_strip(self, idx: int) -> None:
        self._strip.remove_photo(idx)
        if self._strip.count() == 0:
            self._strip.hide()
            QTimer.singleShot(0, self._fit)

    def set_strip_current(self, idx: int) -> None:
        self._strip.set_current(idx)

    def update_strip_thumb(self, idx: int, pil_image: Image.Image) -> None:
        """替換縮圖列中指定索引的縮圖（RAW 完整解碼後使用）。"""
        self._strip.update_thumb(idx, pil_image)

    def _fit(self) -> None:
        cw = max(1, self._canvas.width())
        ch = max(1, self._canvas.height())

        # Always sync child geometries with current canvas size
        self._drop.setGeometry(0, 0, cw, ch)
        self._photo_lbl.setGeometry(0, 0, cw, ch)
        self._safe_overlay.setGeometry(0, 0, cw, ch)
        self._split_drag.setGeometry(0, 0, cw, ch)
        self._split_drag.raise_()
        self._compare_overlay.setGeometry(0, 0, cw, ch)
        if self._compare_mode:
            self._compare_overlay.raise_()
        self._spinner.move(cw - 36, 8)
        self._sz_toggle.move(8, 8)
        # 移動按鈕：safe zone 按鈕下方；若無 safe zone 按鈕則同位置
        if self._sz_toggle.isVisible():
            move_y = 8 + self._sz_toggle.height() + 6
        else:
            move_y = 8
        self._move_btn.move(8, move_y)
        # 縮放控制：右下角，確保在 split_drag 上方
        zw = self._zoom_ctrl.width()
        zh = self._zoom_ctrl.height()
        self._zoom_ctrl.move(cw - zw - 8, ch - zh - 8)
        self._zoom_ctrl.raise_()

        # Before/After 標籤：左上角，safe zone 按鈕對側
        if self._ba_label.isVisible():
            self._ba_label.raise_()
            self._ba_label.move(8, ch - self._ba_label.height() - 8)

        if self._pixmap is None:
            return

        pad  = 24
        base = QSize(max(1, cw - pad), max(1, ch - pad))
        if self._zoom != 1.0:
            base = QSize(int(base.width() * self._zoom),
                         int(base.height() * self._zoom))
        self._photo_lbl.setPixmap(self._pixmap.scaled(
            base,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        ))
        self._safe_overlay.update()
        if self._compare_mode:
            self._compare_overlay.setGeometry(0, 0, cw, ch)
            self._compare_overlay.raise_()
            self._compare_overlay.update()


def _pil_to_pixmap(img: Image.Image) -> QPixmap:
    rgb  = img.convert("RGB")
    w, h = rgb.size
    data = rgb.tobytes("raw", "RGB")
    qi   = QImage(data, w, h, w * 3, QImage.Format.Format_RGB888)
    return QPixmap.fromImage(qi.copy())
