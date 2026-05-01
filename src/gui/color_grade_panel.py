"""
ColorGradePanel — 步驟 1 調色設定面板（右側，320px）

發出 grade_changed(GradeSettings) 信號，由主視窗驅動 GradeWorker。
"""
from __future__ import annotations
import dataclasses

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QScrollArea, QSlider, QComboBox, QPushButton, QSizePolicy, QFileDialog,
)
from PyQt6.QtCore import Qt, pyqtSignal, QRectF
from PyQt6.QtGui import (
    QPainter, QColor, QPen, QBrush, QPainterPath, QFont,
)

import src.gui.theme as T
from src.models.grade_settings import GradeSettings, CurvePoints, BUILTIN_LUTS, LUT_ASSETS_DIR
from src.gui.histogram_widget import HistogramWidget
from src.core.auto_grade import compute_auto_grade, compute_auto_wb


def _tm():
    from src.gui.theme_manager import ThemeManager
    return ThemeManager.instance()


# ─────────────────────────────────────────────────────────────────────────────
# 共用輔助
# ─────────────────────────────────────────────────────────────────────────────

def _section_label(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet(
        f"color: {T.TEXT_PRIMARY}; font-size: {T.FONT_LG}px; font-weight: 800; "
        f"border-bottom: 2px solid {T.BORDER}; "
        f"padding-bottom: 6px; padding-top: 2px; background: transparent;"
    )
    return lbl


def _divider() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.Shape.HLine)
    f.setFixedHeight(1)
    f.setStyleSheet(f"background: {T.BORDER_LIGHT}; border: none;")
    return f


class _SliderRow(QWidget):
    """標籤 + 滑桿 + 數值，發出 value_changed(int)。"""
    value_changed = pyqtSignal(int)

    def __init__(self, label: str, mn: int, mx: int, default: int, parent=None):
        super().__init__(parent)
        self._default = default
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)

        lbl = QLabel(label)
        lbl.setFixedWidth(80)
        lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        lbl.setStyleSheet(
            f"color: {T.TEXT_PRIMARY}; font-size: {T.FONT_BASE}px; background: transparent;"
        )

        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setRange(mn, mx)
        self._slider.setValue(default)
        self._slider.setFixedHeight(22)

        self._val_lbl = QLabel(str(default))
        self._val_lbl.setFixedWidth(40)
        self._val_lbl.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self._val_lbl.setStyleSheet(
            f"color: {T.TEXT_SECONDARY}; font-size: {T.FONT_SM}px; font-weight: 600; background: transparent;"
        )
        self._val_lbl.setToolTip("雙擊恢復預設值")
        self._val_lbl.mouseDoubleClickEvent = lambda _: self._reset_and_emit()
        self._slider.valueChanged.connect(self._on_change)

        lay.addWidget(lbl)
        lay.addWidget(self._slider, 1)
        lay.addWidget(self._val_lbl)

    def _on_change(self, v: int) -> None:
        self._val_lbl.setText(str(v))
        self.value_changed.emit(v)

    def value(self) -> int:
        return self._slider.value()

    def set_value(self, v: int) -> None:
        self._slider.blockSignals(True)
        self._slider.setValue(v)
        self._val_lbl.setText(str(v))
        self._slider.blockSignals(False)

    def reset(self) -> None:
        self.set_value(self._default)

    def _reset_and_emit(self) -> None:
        self._slider.blockSignals(False)
        self._slider.setValue(self._default)
        self._val_lbl.setText(str(self._default))


# ─────────────────────────────────────────────────────────────────────────────
# 可互動曲線元件
# ─────────────────────────────────────────────────────────────────────────────

class CurveWidget(QWidget):
    """可拖曳曲線，發出 curve_changed(CurvePoints)。"""
    curve_changed = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(160)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._pts: list[tuple[float, float]] = [(0.0, 0.0), (0.5, 0.5), (1.0, 1.0)]
        self._drag_idx = -1
        self._channel_color = T.TEXT_PRIMARY
        _tm().theme_changed.connect(lambda _: self.update())
        self.setMouseTracking(True)

    def set_channel_color(self, css_color: str) -> None:
        self._channel_color = css_color
        self.update()

    def set_curve(self, curve: CurvePoints) -> None:
        self._pts = list(curve.points)
        self.update()

    def get_curve(self) -> CurvePoints:
        return CurvePoints(tuple(sorted(self._pts, key=lambda p: p[0])))

    def reset(self) -> None:
        self._pts = [(0.0, 0.0), (0.5, 0.5), (1.0, 1.0)]
        self.update()
        self.curve_changed.emit(self.get_curve())

    # ── 座標轉換 ──────────────────────────────────────────────────────────────

    def _to_w(self, px: float, py: float) -> tuple[int, int]:
        m = 14
        W, H = self.width() - m*2, self.height() - m*2
        return int(m + px * W), int(m + (1 - py) * H)

    def _from_w(self, wx: float, wy: float) -> tuple[float, float]:
        m = 14
        W, H = self.width() - m*2, self.height() - m*2
        return max(0., min(1., (wx - m) / W)), max(0., min(1., 1 - (wy - m) / H))

    # ── 滑鼠事件 ──────────────────────────────────────────────────────────────

    def mousePressEvent(self, e):
        if e.button() != Qt.MouseButton.LeftButton:
            return
        wx, wy = e.position().x(), e.position().y()
        for i, (px, py) in enumerate(self._pts):
            cx, cy = self._to_w(px, py)
            if abs(wx - cx) < 10 and abs(wy - cy) < 10:
                self._drag_idx = i
                return
        nx, ny = self._from_w(wx, wy)
        self._pts.append((nx, ny))
        self._pts.sort(key=lambda p: p[0])
        self.update()
        self.curve_changed.emit(self.get_curve())

    def mouseMoveEvent(self, e):
        if self._drag_idx < 0:
            return
        nx, ny = self._from_w(e.position().x(), e.position().y())
        if self._drag_idx in (0, len(self._pts) - 1):
            nx = self._pts[self._drag_idx][0]
        self._pts[self._drag_idx] = (nx, ny)
        self.update()
        self.curve_changed.emit(self.get_curve())

    def mouseReleaseEvent(self, e):
        self._drag_idx = -1

    def mouseDoubleClickEvent(self, e):
        wx, wy = e.position().x(), e.position().y()
        for i in range(1, len(self._pts) - 1):
            cx, cy = self._to_w(*self._pts[i])
            if abs(wx - cx) < 10 and abs(wy - cy) < 10:
                self._pts.pop(i)
                self.update()
                self.curve_changed.emit(self.get_curve())
                return

    # ── 繪製 ─────────────────────────────────────────────────────────────────

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()
        m = 14

        # 背景
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(QColor(T.SURFACE_2)))
        p.drawRoundedRect(0, 0, W, H, 8, 8)

        # 格線
        p.setPen(QPen(QColor(T.BORDER_LIGHT), 1, Qt.PenStyle.DotLine))
        for i in range(1, 4):
            f = i / 4
            p.drawLine(*self._to_w(f, 0), *self._to_w(f, 1))
            p.drawLine(*self._to_w(0, f), *self._to_w(1, f))

        # 對角線
        p.setPen(QPen(QColor(T.BORDER), 1, Qt.PenStyle.DashLine))
        p.drawLine(*self._to_w(0, 0), *self._to_w(1, 1))

        # 曲線
        col = QColor(self._channel_color)
        if len(self._pts) >= 2:
            pts_px = [self._to_w(px, py) for px, py in sorted(self._pts, key=lambda p: p[0])]
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
            pen = QPen(col, 2.5, Qt.PenStyle.SolidLine,
                       Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
            p.strokePath(path, pen)

        # 控制點
        for px, py in self._pts:
            cx, cy = self._to_w(px, py)
            p.setPen(QPen(col, 2))
            p.setBrush(QBrush(QColor(T.SURFACE)))
            p.drawEllipse(QRectF(cx - 5, cy - 5, 10, 10))

        p.end()


# ─────────────────────────────────────────────────────────────────────────────
# 主面板
# ─────────────────────────────────────────────────────────────────────────────

class ColorGradePanel(QWidget):
    """右側調色設定面板，寬 320px。"""
    grade_changed = pyqtSignal(object)   # GradeSettings
    go_next       = pyqtSignal()         # 切換到加框步驟

    _CHANNEL_COLORS = {
        "RGB（主通道）": None,   # 使用主題色
        "R（紅）": "#f87171",
        "G（綠）": "#4ade80",
        "B（藍）": "#60a5fa",
    }
    _HSL_COLORS = ["紅色", "橙色", "黃色", "綠色", "青色", "藍色", "紫色", "洋紅"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ColorGradePanel")
        self.setFixedWidth(320)
        self._settings = GradeSettings()
        self._section_anchors: dict[str, QWidget] = {}
        self._current_image = None
        self._build()
        self._apply_style()
        _tm().theme_changed.connect(lambda _: self._apply_style())

    # ── 建立 UI ──────────────────────────────────────────────────────────────

    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ── 固定在頂部的直方圖 ────────────────────────────────────────────────
        hist_wrap = QWidget()
        hist_wrap.setObjectName("HistWrap")
        hw_lay = QVBoxLayout(hist_wrap)
        hw_lay.setContentsMargins(T.S4, T.S3, T.S4, T.S2)
        hw_lay.setSpacing(0)
        self._histogram = HistogramWidget()
        hw_lay.addWidget(self._histogram)

        # EXIF 資訊列
        self._exif_camera_lbl = QLabel("")
        self._exif_camera_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._exif_camera_lbl.setStyleSheet(
            f"color: {T.TEXT_PRIMARY}; font-size: {T.FONT_SM}px; font-weight: 600; "
            f"background: transparent; padding-top: 4px;"
        )
        self._exif_camera_lbl.setVisible(False)
        hw_lay.addWidget(self._exif_camera_lbl)

        self._exif_params_lbl = QLabel("")
        self._exif_params_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._exif_params_lbl.setStyleSheet(
            f"color: {T.TEXT_SECONDARY}; font-size: {T.FONT_XS}px; "
            f"background: transparent; padding-bottom: 4px;"
        )
        self._exif_params_lbl.setVisible(False)
        hw_lay.addWidget(self._exif_params_lbl)

        outer.addWidget(hist_wrap)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setObjectName("GradeScroll")
        self._scroll = scroll

        content = QWidget()
        lay = QVBoxLayout(content)
        lay.setContentsMargins(T.S4, T.S5, T.S4, T.S6)
        lay.setSpacing(T.S4)

        self._build_wb_section(lay)
        lay.addWidget(_divider())
        self._build_exposure_section(lay)
        lay.addWidget(_divider())
        self._build_hsl_section(lay)
        lay.addWidget(_divider())
        self._build_curve_section(lay)
        lay.addWidget(_divider())
        self._build_detail_section(lay)
        lay.addWidget(_divider())
        self._build_film_section(lay)
        lay.addSpacing(T.S4)

        # 下一步按鈕
        self._next_btn = QPushButton("繼續加框  →")
        self._next_btn.setObjectName("ActionBtn")
        self._next_btn.setFixedHeight(46)
        self._next_btn.clicked.connect(self.go_next)
        lay.addWidget(self._next_btn)

        lay.addStretch()
        scroll.setWidget(content)
        outer.addWidget(scroll)

    # ── Film Simulation ───────────────────────────────────────────────────────

    def _build_film_section(self, lay: QVBoxLayout) -> None:
        anchor = _section_label("底片模擬")
        self._section_anchors["film"] = anchor
        lay.addWidget(anchor)

        # 下拉選單：內建預設 + 自訂
        self._lut_combo = QComboBox()
        self._lut_combo.addItem("── 無 ──", userData=None)
        for display_name, filename in BUILTIN_LUTS.items():
            lut_path = str(LUT_ASSETS_DIR / filename)
            self._lut_combo.addItem(display_name, userData=lut_path)
        self._lut_combo.addItem("載入自訂 LUT…", userData="__custom__")
        self._lut_combo.setFixedHeight(28)
        self._lut_combo.currentIndexChanged.connect(self._on_lut_changed)
        lay.addWidget(self._lut_combo)

        # 不透明度滑桿
        self._lut_opacity = _SliderRow("不透明度", 0, 100, 100)
        self._lut_opacity.value_changed.connect(
            lambda v: self._update("lut_opacity", v))
        lay.addWidget(self._lut_opacity)

        # 目前已載入的自訂路徑（供 combo 記憶用）
        self._custom_lut_path: str | None = None

    def _on_lut_changed(self, _: int) -> None:
        data = self._lut_combo.currentData()
        if data == "__custom__":
            path, _ = QFileDialog.getOpenFileName(
                self, "選擇 LUT 檔案", "", "LUT 檔案 (*.cube);;所有檔案 (*)"
            )
            if path:
                self._custom_lut_path = path
                # 若已有自訂項目就更新，否則插入
                custom_idx = self._lut_combo.findData("__custom_loaded__")
                if custom_idx >= 0:
                    self._lut_combo.setItemText(custom_idx, f"自訂：{path.split('/')[-1]}")
                    self._lut_combo.setItemData(custom_idx, "__custom_loaded__")
                    self._lut_combo.blockSignals(True)
                    self._lut_combo.setCurrentIndex(custom_idx)
                    self._lut_combo.blockSignals(False)
                else:
                    self._lut_combo.blockSignals(True)
                    self._lut_combo.insertItem(
                        self._lut_combo.count() - 1,
                        f"自訂：{path.split('/')[-1]}",
                        userData="__custom_loaded__",
                    )
                    self._lut_combo.setCurrentIndex(self._lut_combo.count() - 2)
                    self._lut_combo.blockSignals(False)
                self._update("lut_path", path)
            else:
                # 取消選擇，回到原本
                self._lut_combo.blockSignals(True)
                cur_path = self._settings.lut_path
                idx = self._lut_combo.findData(cur_path) if cur_path else 0
                self._lut_combo.setCurrentIndex(max(0, idx))
                self._lut_combo.blockSignals(False)
        elif data == "__custom_loaded__":
            self._update("lut_path", self._custom_lut_path)
        else:
            self._update("lut_path", data)   # None or builtin path

    # ── 曲線 ─────────────────────────────────────────────────────────────────

    def _build_curve_section(self, lay: QVBoxLayout) -> None:
        anchor = _section_label("色調曲線")
        self._section_anchors["curve"] = anchor
        lay.addWidget(anchor)

        ctrl_row = QWidget()
        ctrl_lay = QHBoxLayout(ctrl_row)
        ctrl_lay.setContentsMargins(0, 0, 0, 0)
        ctrl_lay.setSpacing(6)

        self._curve_channel = QComboBox()
        self._curve_channel.addItems(list(self._CHANNEL_COLORS.keys()))
        self._curve_channel.setFixedHeight(28)
        self._curve_channel.currentTextChanged.connect(self._on_channel_changed)

        reset_btn = QPushButton("重置")
        reset_btn.setObjectName("SmallBtn")
        reset_btn.setFixedHeight(28)
        reset_btn.clicked.connect(self._on_curve_reset)

        ctrl_lay.addWidget(self._curve_channel, 1)
        ctrl_lay.addWidget(reset_btn)
        lay.addWidget(ctrl_row)

        self._curve_widget = CurveWidget()
        self._curve_widget.curve_changed.connect(self._on_curve_changed)
        lay.addWidget(self._curve_widget)

        hint = QLabel("拖曳控制點　雙擊刪除")
        hint.setStyleSheet(
            f"color: {T.TEXT_MUTED}; font-size: {T.FONT_XS}px; background: transparent;"
        )
        lay.addWidget(hint)

    def _on_channel_changed(self, text: str) -> None:
        col = self._CHANNEL_COLORS.get(text) or T.TEXT_PRIMARY
        self._curve_widget.set_channel_color(col)
        # 載入對應曲線
        ch = text.split("（")[0]
        curve_map = {
            "RGB": self._settings.curve_rgb,
            "R":   self._settings.curve_r,
            "G":   self._settings.curve_g,
            "B":   self._settings.curve_b,
        }
        self._curve_widget.set_curve(curve_map.get(ch, self._settings.curve_rgb))

    def _on_curve_changed(self, curve: CurvePoints) -> None:
        ch = self._curve_channel.currentText().split("（")[0]
        field_map = {"RGB": "curve_rgb", "R": "curve_r", "G": "curve_g", "B": "curve_b"}
        field = field_map.get(ch, "curve_rgb")
        self._settings = dataclasses.replace(self._settings, **{field: curve})
        self.grade_changed.emit(self._settings)

    def _on_curve_reset(self) -> None:
        ch = self._curve_channel.currentText().split("（")[0]
        field_map = {"RGB": "curve_rgb", "R": "curve_r", "G": "curve_g", "B": "curve_b"}
        field = field_map.get(ch, "curve_rgb")
        self._settings = dataclasses.replace(self._settings, **{field: CurvePoints()})
        self._curve_widget.reset()
        # curve_widget.reset() 會觸發 curve_changed，所以不用再 emit

    # ── 白平衡 ────────────────────────────────────────────────────────────────

    def _build_wb_section(self, lay: QVBoxLayout) -> None:
        anchor = _section_label("白平衡")
        self._section_anchors["wb"] = anchor
        lay.addWidget(anchor)

        preset_row = QWidget()
        pr_lay = QHBoxLayout(preset_row)
        pr_lay.setContentsMargins(0, 0, 0, 0)
        pr_lay.setSpacing(5)
        # 自動白平衡按鈕（分析圖片）
        auto_wb_btn = QPushButton("自動")
        auto_wb_btn.setObjectName("ChipBtn")
        auto_wb_btn.setFixedHeight(26)
        auto_wb_btn.clicked.connect(self._apply_auto_wb)
        pr_lay.addWidget(auto_wb_btn)

        wb_presets = [("日光", 5600), ("多雲", 6500), ("鎢絲燈", 3200)]
        for label, kelvin in wb_presets:
            btn = QPushButton(label)
            btn.setObjectName("ChipBtn")
            btn.setFixedHeight(26)
            btn.clicked.connect(lambda _, k=kelvin: self._set_wb_preset(k))
            pr_lay.addWidget(btn)
        pr_lay.addStretch()
        lay.addWidget(preset_row)

        self._wb_temp = _SliderRow("色溫", 2000, 10000, 5500)
        self._wb_tint = _SliderRow("色調", -100, 100, 0)
        self._wb_temp.value_changed.connect(
            lambda v: self._update("wb_temperature", v))
        self._wb_tint.value_changed.connect(
            lambda v: self._update("wb_tint", v))
        lay.addWidget(self._wb_temp)
        lay.addWidget(self._wb_tint)

    def _set_wb_preset(self, kelvin: int) -> None:
        self._wb_temp.set_value(kelvin)

    def _apply_auto_wb(self) -> None:
        """分析當前圖片，自動設定白平衡色溫和色調。"""
        img = getattr(self, "_current_image", None)
        if img is None:
            return
        suggested = compute_auto_wb(img)
        self._wb_temp.set_value(suggested["wb_temperature"])
        self._wb_tint.set_value(suggested["wb_tint"])
        self._settings = dataclasses.replace(
            self._settings,
            wb_temperature=suggested["wb_temperature"],
            wb_tint=suggested["wb_tint"],
        )
        self.grade_changed.emit(self._settings)

    # ── 曝光 ─────────────────────────────────────────────────────────────────

    def _build_exposure_section(self, lay: QVBoxLayout) -> None:
        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)
        anchor = _section_label("亮度")
        self._section_anchors["light"] = anchor
        header_row.addWidget(anchor, 1)
        self._auto_btn = QPushButton("自動")
        self._auto_btn.setFixedSize(46, 22)
        self._auto_btn.setToolTip("根據圖片自動設定亮度參數")
        self._auto_btn.setStyleSheet(
            f"QPushButton {{ background: {T.PRIMARY}; color: {T.TEXT_ON_PRIMARY}; border: none; "
            f"border-radius: 4px; font-size: {T.FONT_XS}px; font-weight: 600; "
            f"padding: 1px 4px; }}"
            f"QPushButton:hover {{ background: {T.PRIMARY_HOVER}; }}"
            f"QPushButton:pressed {{ background: {T.PRIMARY_PRESSED}; }}"
        )
        self._auto_btn.clicked.connect(self._apply_auto_grade)
        header_row.addWidget(self._auto_btn)
        lay.addLayout(header_row)
        rows = [
            ("曝光",  "exposure",   -300, 300, 0),
            ("對比度","contrast",   -100, 100, 0),
            ("亮部",  "highlights", -100, 100, 0),
            ("陰影",  "shadows",    -100, 100, 0),
            ("白點",  "whites",     -100, 100, 0),
            ("黑點",  "blacks",     -100, 100, 0),
        ]
        self._exposure_rows: dict[str, _SliderRow] = {}
        for label, field, mn, mx, default in rows:
            row = _SliderRow(label, mn, mx, default)
            row.value_changed.connect(lambda v, f=field: self._update(f, v))
            self._exposure_rows[field] = row
            lay.addWidget(row)

    # ── HSL ──────────────────────────────────────────────────────────────────

    def _build_hsl_section(self, lay: QVBoxLayout) -> None:
        anchor = _section_label("色相飽和度")
        self._section_anchors["hsl"] = anchor
        lay.addWidget(anchor)

        self._hsl_mode = QComboBox()
        self._hsl_mode.addItems(["色相", "飽和度", "明度"])
        self._hsl_mode.setFixedHeight(28)
        self._hsl_mode.currentIndexChanged.connect(self._on_hsl_mode_changed)
        lay.addWidget(self._hsl_mode)

        self._hsl_rows: list[_SliderRow] = []
        for color in self._HSL_COLORS:
            row = _SliderRow(color, -100, 100, 0)
            row.value_changed.connect(self._on_hsl_changed)
            self._hsl_rows.append(row)
            lay.addWidget(row)

    def _on_hsl_mode_changed(self, _: int) -> None:
        mode_idx = self._hsl_mode.currentIndex()
        fields = ["hsl_hue", "hsl_saturation", "hsl_luminance"]
        vals = getattr(self._settings, fields[mode_idx])
        for i, row in enumerate(self._hsl_rows):
            row.set_value(vals[i])

    def _on_hsl_changed(self) -> None:
        mode_idx = self._hsl_mode.currentIndex()
        fields = ["hsl_hue", "hsl_saturation", "hsl_luminance"]
        field = fields[mode_idx]
        vals = tuple(row.value() for row in self._hsl_rows)
        self._settings = dataclasses.replace(self._settings, **{field: vals})
        self.grade_changed.emit(self._settings)

    # ── 細節 ─────────────────────────────────────────────────────────────────

    def _build_detail_section(self, lay: QVBoxLayout) -> None:
        anchor = _section_label("細節")
        self._section_anchors["detail"] = anchor
        lay.addWidget(anchor)
        rows = [
            ("降噪", "noise_reduction", 0, 100, 0),
            ("銳化", "sharpening",      0, 100, 0),
            ("遮罩", "detail_mask",     0, 100, 20),
        ]
        for label, field, mn, mx, default in rows:
            row = _SliderRow(label, mn, mx, default)
            row.value_changed.connect(lambda v, f=field: self._update(f, v))
            lay.addWidget(row)

    # ── 通用更新 ──────────────────────────────────────────────────────────────

    def _update(self, field: str, value) -> None:
        self._settings = dataclasses.replace(self._settings, **{field: value})
        self.grade_changed.emit(self._settings)

    # ── 公開 API ──────────────────────────────────────────────────────────────

    def scroll_to_section(self, section_id: str) -> None:
        """捲動至指定 section（curve / wb / light / hsl / detail）。"""
        widget = self._section_anchors.get(section_id)
        if widget:
            self._scroll.ensureWidgetVisible(widget, 0, T.S3)

    def update_histogram(self, img) -> None:
        """傳入 PIL.Image 更新直方圖（img 為 None 時清空）。"""
        self._current_image = img
        self._histogram.update_image(img)

    def _apply_auto_grade(self) -> None:
        """分析當前圖片，自動套用建議的亮度參數。"""
        img = getattr(self, "_current_image", None)
        if img is None:
            return
        suggested = compute_auto_grade(img)
        for field, value in suggested.items():
            row = self._exposure_rows.get(field)
            if row:
                row.set_value(value)
            self._settings = dataclasses.replace(self._settings, **{field: value})
        self.grade_changed.emit(self._settings)

    def update_exif(self, exif) -> None:
        """傳入 ExifData 更新直方圖下方的相機參數顯示。"""
        if exif is None or not exif.has_any:
            self._exif_camera_lbl.setVisible(False)
            self._exif_params_lbl.setVisible(False)
            return
        camera_line = exif.camera_line
        params_line = exif.params_line
        if camera_line:
            self._exif_camera_lbl.setText(camera_line)
            self._exif_camera_lbl.setVisible(True)
        else:
            self._exif_camera_lbl.setVisible(False)
        if params_line:
            self._exif_params_lbl.setText(params_line)
            self._exif_params_lbl.setVisible(True)
        else:
            self._exif_params_lbl.setVisible(False)

    def current_settings(self) -> GradeSettings:
        return self._settings

    def restore_settings(self, s: GradeSettings) -> None:
        """從 GradeSettings 還原所有控件狀態（不觸發信號）。"""
        self._settings = s

        # LUT
        self._lut_combo.blockSignals(True)
        if s.lut_path is None:
            self._lut_combo.setCurrentIndex(0)
        else:
            idx = self._lut_combo.findData(s.lut_path)
            if idx >= 0:
                self._lut_combo.setCurrentIndex(idx)
        self._lut_combo.blockSignals(False)
        self._lut_opacity.set_value(s.lut_opacity)

        self._wb_temp.set_value(s.wb_temperature)
        self._wb_tint.set_value(s.wb_tint)

        for field, row in self._exposure_rows.items():
            row.set_value(getattr(s, field))

        mode_idx = self._hsl_mode.currentIndex()
        fields = ["hsl_hue", "hsl_saturation", "hsl_luminance"]
        vals = getattr(s, fields[mode_idx])
        for i, row in enumerate(self._hsl_rows):
            row.set_value(vals[i])

        # 更新曲線
        ch = self._curve_channel.currentText().split("（")[0]
        curve_map = {
            "RGB": s.curve_rgb, "R": s.curve_r, "G": s.curve_g, "B": s.curve_b,
        }
        self._curve_widget.set_curve(curve_map.get(ch, s.curve_rgb))

    # ── 樣式 ─────────────────────────────────────────────────────────────────

    def _apply_style(self) -> None:
        self.setStyleSheet(f"""
            QWidget#ColorGradePanel {{
                background: {T.SURFACE};
                border-left: 2px solid {T.BORDER};
            }}
            QWidget#HistWrap {{
                background: {T.SURFACE_2};
                border-bottom: 1px solid {T.BORDER};
            }}
            QScrollArea#GradeScroll {{
                background: {T.SURFACE};
                border: none;
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
                height: 5px; background: {T.SURFACE_3}; border-radius: 3px;
            }}
            QSlider::handle:horizontal {{
                width: 18px; height: 18px;
                background: {T.SURFACE};
                border: 2.5px solid {T.PRIMARY};
                border-radius: 9px;
                margin: -7px 0;
            }}
            QSlider::sub-page:horizontal {{
                background: {T.PRIMARY}; border-radius: 3px;
            }}
            QPushButton#ChipBtn {{
                background: {T.SURFACE_2};
                color: {T.TEXT_SECONDARY};
                border: 1.5px solid {T.BORDER_LIGHT};
                border-radius: {T.R_CHIP}px;
                font-size: {T.FONT_SM}px;
                padding: 2px 8px;
            }}
            QPushButton#ChipBtn:hover {{
                background: {T.SURFACE_3};
                color: {T.TEXT_PRIMARY};
                border-color: {T.BORDER};
            }}
            QPushButton#SmallBtn {{
                background: transparent;
                color: {T.TEXT_SECONDARY};
                border: 1.5px solid {T.BORDER_LIGHT};
                border-radius: {T.R_CHIP}px;
                font-size: {T.FONT_XS}px;
                padding: 2px 10px;
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
                padding: 4px 12px;
            }}
            QPushButton#ActionBtn:hover {{
                background: {T.PRIMARY_HOVER};
            }}
        """)
