"""
ColorGradePanel — 步驟 1 調色設定面板（右側，320px）

發出 grade_changed(GradeSettings) 信號，由主視窗驅動 GradeWorker。
Public API:
  Signals: grade_changed, go_next, reset_requested, undo_requested
  Methods: set_can_undo, scroll_to_section, update_histogram, update_exif,
           restore_settings
"""
from __future__ import annotations
import dataclasses

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QScrollArea, QSlider, QComboBox, QPushButton, QSizePolicy, QFileDialog,
)
from PyQt6.QtCore import Qt, pyqtSignal, QPropertyAnimation, QEasingCurve, QRectF
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QPainterPath

import src.gui.theme as T
from src.models.grade_settings import GradeSettings, CurvePoints, BUILTIN_LUTS, LUT_ASSETS_DIR
from src.gui.histogram_widget import HistogramWidget
from src.core.auto_grade import compute_auto_grade, compute_auto_wb


# ─────────────────────────────────────────────────────────────────────────────
# _Section — collapsible section widget
# ─────────────────────────────────────────────────────────────────────────────

class _Section(QWidget):
    """Collapsible section with animated body expansion/collapse."""

    def __init__(self, title: str, collapsed: bool = True, parent: QWidget | None = None):
        super().__init__(parent)
        self._collapsed = collapsed
        self._anim: QPropertyAnimation | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Header button
        self._header = QPushButton()
        self._header.setObjectName("SectionHeader")
        self._header.setFixedHeight(32)
        self._header.setCheckable(True)
        self._header.setChecked(not collapsed)
        self._header.setCursor(Qt.CursorShape.PointingHandCursor)
        self._header.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._header.setFlat(True)
        self._header.clicked.connect(self._toggle)

        header_inner = QHBoxLayout(self._header)
        header_inner.setContentsMargins(10, 0, 8, 0)
        header_inner.setSpacing(6)

        self._arrow_lbl = QLabel("▶" if collapsed else "▼")
        self._arrow_lbl.setFixedWidth(14)
        self._arrow_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._arrow_lbl.setStyleSheet("background: transparent; color: inherit;")

        self._title_lbl = QLabel(title)
        self._title_lbl.setStyleSheet(
            "font-size: 13px; font-weight: 700; background: transparent; color: inherit;"
        )

        header_inner.addWidget(self._arrow_lbl)
        header_inner.addWidget(self._title_lbl, 1)
        root.addWidget(self._header)

        # Body
        self._body = QWidget()
        self._body.setObjectName("SectionBody")
        self._body_lay = QVBoxLayout(self._body)
        self._body_lay.setContentsMargins(12, 6, 12, 8)
        self._body_lay.setSpacing(5)
        root.addWidget(self._body)

        if collapsed:
            self._body.setVisible(False)
            self._body.setMaximumHeight(0)

        self._refresh_header_style()

    # ── Public API ────────────────────────────────────────────────────────────

    def add_widget(self, w: QWidget) -> None:
        self._body_lay.addWidget(w)

    def add_layout(self, lay) -> None:
        self._body_lay.addLayout(lay)

    def add_spacing(self, n: int) -> None:
        self._body_lay.addSpacing(n)

    def is_collapsed(self) -> bool:
        return self._collapsed

    # ── Internal ──────────────────────────────────────────────────────────────

    def _toggle(self) -> None:
        self._collapsed = not self._collapsed
        self._arrow_lbl.setText("▶" if self._collapsed else "▼")
        self._header.setChecked(not self._collapsed)
        self._refresh_header_style()
        if self._collapsed:
            self._animate_collapse()
        else:
            self._body.setVisible(True)
            self._animate_expand()

    def _animate_expand(self) -> None:
        self._body.setMaximumHeight(0)
        target = self._body.sizeHint().height()
        anim = QPropertyAnimation(self._body, b"maximumHeight", self)
        anim.setDuration(180)
        anim.setStartValue(0)
        anim.setEndValue(max(target, 40))
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.start()
        self._anim = anim

    def _animate_collapse(self) -> None:
        anim = QPropertyAnimation(self._body, b"maximumHeight", self)
        anim.setDuration(160)
        anim.setStartValue(self._body.height())
        anim.setEndValue(0)
        anim.setEasingCurve(QEasingCurve.Type.InCubic)
        anim.finished.connect(lambda: self._body.setVisible(False))
        anim.start()
        self._anim = anim

    def _refresh_header_style(self) -> None:
        border_color = "#C5A46A" if not self._collapsed else "#3E3E3E"
        self._header.setStyleSheet(f"""
            QPushButton#SectionHeader {{
                background: #2C2C2C;
                color: #F2F0EA;
                border: none;
                border-left: 3px solid {border_color};
                border-radius: 0px;
                text-align: left;
                font-size: 13px;
                font-weight: 700;
                padding: 4px 8px;
            }}
            QPushButton#SectionHeader:hover {{
                background: #363636;
                color: #C5A46A;
                border-left-color: #C5A46A;
            }}
        """)


# ─────────────────────────────────────────────────────────────────────────────
# _SliderRow — label + slider + value display
# ─────────────────────────────────────────────────────────────────────────────

class _SliderRow(QWidget):
    """Horizontal slider row with label and value. Double-click value to reset."""

    value_changed = pyqtSignal(int)

    def __init__(
        self,
        label: str,
        mn: int,
        mx: int,
        default: int,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._default = default

        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)

        lbl = QLabel(label)
        lbl.setFixedWidth(80)
        lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        lbl.setStyleSheet("color: #F2F0EA; font-size: 12px; background: transparent;")

        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setRange(mn, mx)
        self._slider.setValue(default)
        self._slider.setFixedHeight(22)
        self._slider.setStyleSheet(self._slider_qss())

        self._val_lbl = QLabel(str(default))
        self._val_lbl.setFixedWidth(40)
        self._val_lbl.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self._val_lbl.setStyleSheet(
            "color: #BBBAC4; font-size: 11px; font-weight: 600; background: transparent;"
        )
        self._val_lbl.setToolTip("雙擊恢復預設值")
        self._val_lbl.mouseDoubleClickEvent = lambda _e: self._reset_and_emit()

        self._slider.valueChanged.connect(self._on_change)

        lay.addWidget(lbl)
        lay.addWidget(self._slider, 1)
        lay.addWidget(self._val_lbl)

    # ── Public API ────────────────────────────────────────────────────────────

    def value(self) -> int:
        return self._slider.value()

    def set_value(self, v: int) -> None:
        self._slider.blockSignals(True)
        self._slider.setValue(v)
        self._val_lbl.setText(str(v))
        self._slider.blockSignals(False)

    # ── Internal ──────────────────────────────────────────────────────────────

    def _on_change(self, v: int) -> None:
        self._val_lbl.setText(str(v))
        self.value_changed.emit(v)

    def _reset_and_emit(self) -> None:
        self._slider.blockSignals(False)
        self._slider.setValue(self._default)
        self._val_lbl.setText(str(self._default))
        self.value_changed.emit(self._default)

    @staticmethod
    def _slider_qss() -> str:
        return """
            QSlider::groove:horizontal {
                height: 4px;
                background: #363636;
                border-radius: 2px;
            }
            QSlider::sub-page:horizontal {
                background: #C5A46A;
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background: #C5A46A;
                border: 2px solid rgba(197,164,106,0.3);
                width: 14px;
                height: 14px;
                margin: -5px 0;
                border-radius: 7px;
            }
            QSlider::handle:horizontal:hover {
                background: #D4B87E;
                border-color: rgba(197,164,106,0.5);
            }
        """


# ─────────────────────────────────────────────────────────────────────────────
# CurveWidget — draggable tone curve
# ─────────────────────────────────────────────────────────────────────────────

class CurveWidget(QWidget):
    """Interactive tone curve with draggable control points."""

    curve_changed = pyqtSignal(object)  # CurvePoints

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setFixedHeight(160)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._pts: list[tuple[float, float]] = [(0.0, 0.0), (0.5, 0.5), (1.0, 1.0)]
        self._drag_idx = -1
        self._channel_color = "#F2F0EA"
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

    # ── Coordinate conversion ─────────────────────────────────────────────────

    def _to_w(self, px: float, py: float) -> tuple[int, int]:
        m = 14
        W, H = self.width() - m * 2, self.height() - m * 2
        return int(m + px * W), int(m + (1.0 - py) * H)

    def _from_w(self, wx: float, wy: float) -> tuple[float, float]:
        m = 14
        W, H = self.width() - m * 2, self.height() - m * 2
        return max(0.0, min(1.0, (wx - m) / W)), max(0.0, min(1.0, 1.0 - (wy - m) / H))

    # ── Mouse events ──────────────────────────────────────────────────────────

    def mousePressEvent(self, e) -> None:
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

    def mouseMoveEvent(self, e) -> None:
        if self._drag_idx < 0:
            return
        nx, ny = self._from_w(e.position().x(), e.position().y())
        if self._drag_idx in (0, len(self._pts) - 1):
            nx = self._pts[self._drag_idx][0]
        self._pts[self._drag_idx] = (nx, ny)
        self.update()
        self.curve_changed.emit(self.get_curve())

    def mouseReleaseEvent(self, e) -> None:
        self._drag_idx = -1

    def mouseDoubleClickEvent(self, e) -> None:
        wx, wy = e.position().x(), e.position().y()
        for i in range(1, len(self._pts) - 1):
            cx, cy = self._to_w(*self._pts[i])
            if abs(wx - cx) < 10 and abs(wy - cy) < 10:
                self._pts.pop(i)
                self.update()
                self.curve_changed.emit(self.get_curve())
                return

    # ── Paint ─────────────────────────────────────────────────────────────────

    def paintEvent(self, _) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()
        m = 14

        # Background
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(QColor("#2C2C2C")))
        p.drawRoundedRect(0, 0, W, H, 8, 8)

        # Grid lines
        grid_pen = QPen(QColor("#303030"), 1, Qt.PenStyle.DotLine)
        p.setPen(grid_pen)
        for i in range(1, 4):
            f = i / 4.0
            p.drawLine(*self._to_w(f, 0), *self._to_w(f, 1))
            p.drawLine(*self._to_w(0, f), *self._to_w(1, f))

        # Diagonal reference
        p.setPen(QPen(QColor("#3E3E3E"), 1, Qt.PenStyle.DashLine))
        p.drawLine(*self._to_w(0, 0), *self._to_w(1, 1))

        # Curve
        col = QColor(self._channel_color)
        pts_sorted = sorted(self._pts, key=lambda pt: pt[0])
        if len(pts_sorted) >= 2:
            pts_px = [self._to_w(px, py) for px, py in pts_sorted]
            path = QPainterPath()
            path.moveTo(*pts_px[0])
            if len(pts_px) == 2:
                path.lineTo(*pts_px[1])
            else:
                for i in range(len(pts_px) - 1):
                    p0 = pts_px[max(0, i - 1)]
                    p1 = pts_px[i]
                    p2 = pts_px[i + 1]
                    p3 = pts_px[min(len(pts_px) - 1, i + 2)]
                    cp1x = p1[0] + (p2[0] - p0[0]) / 6.0
                    cp1y = p1[1] + (p2[1] - p0[1]) / 6.0
                    cp2x = p2[0] - (p3[0] - p1[0]) / 6.0
                    cp2y = p2[1] - (p3[1] - p1[1]) / 6.0
                    path.cubicTo(cp1x, cp1y, cp2x, cp2y, p2[0], p2[1])
            curve_pen = QPen(col, 2.5, Qt.PenStyle.SolidLine,
                             Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
            p.strokePath(path, curve_pen)

        # Control points
        for px, py in self._pts:
            cx, cy = self._to_w(px, py)
            p.setPen(QPen(col, 2))
            p.setBrush(QBrush(QColor("#222222")))
            p.drawEllipse(QRectF(cx - 5, cy - 5, 10, 10))

        p.end()


# ─────────────────────────────────────────────────────────────────────────────
# ColorGradePanel — main panel
# ─────────────────────────────────────────────────────────────────────────────

class ColorGradePanel(QWidget):
    """Right-side color grading panel, 320px fixed width."""

    grade_changed   = pyqtSignal(object)  # GradeSettings
    go_next         = pyqtSignal()
    reset_requested = pyqtSignal()
    undo_requested  = pyqtSignal()

    _CHANNEL_COLORS = {
        "RGB（主通道）": None,
        "R（紅）": "#f87171",
        "G（綠）": "#4ade80",
        "B（藍）": "#60a5fa",
    }
    _HSL_LABELS = ["紅", "橙", "黃", "綠", "青", "藍", "紫", "洋紅"]

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("ColorGradePanel")
        self.setFixedWidth(320)

        self._settings: GradeSettings = GradeSettings()
        self._section_anchors: dict[str, _Section] = {}
        self._current_image = None
        self._custom_lut_path: str | None = None

        self._build_ui()
        self._apply_panel_style()

    # ─────────────────────────────────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────────────────────────────────

    def set_can_undo(self, can: bool) -> None:
        """Enable or disable the undo button."""
        self._undo_btn.setEnabled(can)

    def scroll_to_section(self, section_id: str) -> None:
        """Expand and scroll to the named section."""
        sec = self._section_anchors.get(section_id)
        if sec is None:
            return
        if sec.is_collapsed():
            sec._toggle()
        self._scroll.ensureWidgetVisible(sec, 0, T.S3)

    def update_histogram(self, img) -> None:
        """Update histogram from a PIL image (pass None to clear)."""
        self._current_image = img
        self._histogram.update_image(img)

    def update_exif(self, exif) -> None:
        """Show EXIF camera/params info below histogram."""
        if exif is None or not exif.has_any:
            self._exif_camera_lbl.setVisible(False)
            self._exif_params_lbl.setVisible(False)
            return
        camera = exif.camera_line
        params = exif.params_line
        self._exif_camera_lbl.setText(camera or "")
        self._exif_camera_lbl.setVisible(bool(camera))
        self._exif_params_lbl.setText(params or "")
        self._exif_params_lbl.setVisible(bool(params))

    def restore_settings(self, s: GradeSettings) -> None:
        """Restore all UI controls from a GradeSettings without emitting signals."""
        self._settings = s

        # White balance
        self._wb_temp.set_value(s.wb_temperature)
        self._wb_tint.set_value(s.wb_tint)

        # Exposure
        for field, row in self._exposure_rows.items():
            row.set_value(getattr(s, field))

        # Presence
        for field, row in self._presence_rows.items():
            row.set_value(getattr(s, field))

        # HSL — update current mode's values
        mode_idx = self._hsl_mode.currentIndex()
        hsl_fields = ["hsl_hue", "hsl_saturation", "hsl_luminance"]
        vals = getattr(s, hsl_fields[mode_idx])
        for i, row in enumerate(self._hsl_rows):
            row.set_value(vals[i])

        # Curve
        ch_text = self._curve_channel.currentText()
        ch_key = ch_text.split("（")[0]
        curve_map = {
            "RGB": s.curve_rgb, "R": s.curve_r, "G": s.curve_g, "B": s.curve_b,
        }
        self._curve_widget.set_curve(curve_map.get(ch_key, s.curve_rgb))

        # Detail
        self._detail_noise.set_value(s.noise_reduction)
        self._detail_sharp.set_value(s.sharpening)
        self._detail_mask.set_value(s.detail_mask)

        # B&W
        self._bw_toggle.blockSignals(True)
        self._bw_toggle.setChecked(s.treatment == "bw")
        self._bw_toggle.blockSignals(False)
        for i, row in enumerate(self._bw_rows):
            row.set_value(s.bw_mix[i])

        # Split tone
        self._split_hi_hue.set_value(s.split_highlights_hue)
        self._split_hi_sat.set_value(s.split_highlights_sat)
        self._split_sh_hue.set_value(s.split_shadows_hue)
        self._split_sh_sat.set_value(s.split_shadows_sat)
        self._split_balance.set_value(s.split_balance)

        # Effects
        self._vignette_amount.set_value(s.vignette_amount)
        self._vignette_midpoint.set_value(s.vignette_midpoint)
        self._vignette_feather.set_value(s.vignette_feather)
        self._grain_amount.set_value(s.grain_amount)
        self._grain_size.set_value(s.grain_size)
        self._grain_roughness.set_value(s.grain_roughness)

        # Transform
        self._rotation_row.set_value(round(s.rotation * 10))
        self._flip_h_btn.blockSignals(True)
        self._flip_v_btn.blockSignals(True)
        self._flip_h_btn.setChecked(s.flip_h)
        self._flip_v_btn.setChecked(s.flip_v)
        self._flip_h_btn.blockSignals(False)
        self._flip_v_btn.blockSignals(False)

        # Film / LUT
        self._lut_combo.blockSignals(True)
        if s.lut_path is None:
            self._lut_combo.setCurrentIndex(0)
        else:
            idx = self._lut_combo.findData(s.lut_path)
            self._lut_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self._lut_combo.blockSignals(False)
        self._lut_opacity.set_value(s.lut_opacity)

    def current_settings(self) -> GradeSettings:
        return self._settings

    # ─────────────────────────────────────────────────────────────────────────
    # Internal: settings update
    # ─────────────────────────────────────────────────────────────────────────

    def _update(self, field: str, value) -> None:
        self._settings = dataclasses.replace(self._settings, **{field: value})
        self.grade_changed.emit(self._settings)

    def _on_reset(self) -> None:
        fresh = GradeSettings()
        self.restore_settings(fresh)
        self._settings = fresh
        self.grade_changed.emit(fresh)
        self.reset_requested.emit()

    # ─────────────────────────────────────────────────────────────────────────
    # UI construction
    # ─────────────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_histogram_area())
        root.addWidget(self._build_scroll_area(), 1)
        root.addWidget(self._build_footer())

    def _build_histogram_area(self) -> QWidget:
        wrap = QWidget()
        wrap.setObjectName("HistWrap")
        wrap.setStyleSheet("QWidget#HistWrap { background: #2C2C2C; }")
        lay = QVBoxLayout(wrap)
        lay.setContentsMargins(12, 12, 12, 8)
        lay.setSpacing(0)

        self._histogram = HistogramWidget()
        lay.addWidget(self._histogram)

        self._exif_camera_lbl = QLabel("")
        self._exif_camera_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._exif_camera_lbl.setStyleSheet(
            "color: #F2F0EA; font-size: 11px; font-weight: 600; "
            "background: transparent; padding-top: 4px;"
        )
        self._exif_camera_lbl.setVisible(False)
        lay.addWidget(self._exif_camera_lbl)

        self._exif_params_lbl = QLabel("")
        self._exif_params_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._exif_params_lbl.setStyleSheet(
            "color: #7A7888; font-size: 10px; background: transparent; padding-bottom: 4px;"
        )
        self._exif_params_lbl.setVisible(False)
        lay.addWidget(self._exif_params_lbl)

        return wrap

    def _build_scroll_area(self) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setObjectName("GradeScroll")
        scroll.setStyleSheet(
            "QScrollArea#GradeScroll { background: #222222; border: none; }"
        )
        self._scroll = scroll

        content = QWidget()
        content.setStyleSheet("background: #222222;")
        lay = QVBoxLayout(content)
        lay.setContentsMargins(0, 4, 0, 16)
        lay.setSpacing(0)

        self._build_wb_section(lay)
        self._build_exposure_section(lay)
        self._build_presence_section(lay)
        self._build_hsl_section(lay)
        self._build_curve_section(lay)
        self._build_detail_section(lay)
        self._build_bw_section(lay)
        self._build_split_tone_section(lay)
        self._build_effects_section(lay)
        self._build_transform_section(lay)
        self._build_film_section(lay)
        lay.addStretch(1)

        scroll.setWidget(content)
        return scroll

    def _build_footer(self) -> QWidget:
        footer = QWidget()
        footer.setObjectName("GradeFooter")
        footer.setStyleSheet(
            "QWidget#GradeFooter { background: #222222; border-top: 1px solid #3E3E3E; }"
        )
        lay = QVBoxLayout(footer)
        lay.setContentsMargins(12, 10, 12, 12)
        lay.setSpacing(8)

        # Row 1: Undo | Reset
        btn_row = QWidget()
        btn_row.setStyleSheet("background: transparent;")
        btn_lay = QHBoxLayout(btn_row)
        btn_lay.setContentsMargins(0, 0, 0, 0)
        btn_lay.setSpacing(8)

        self._undo_btn = QPushButton("↩ 復原")
        self._undo_btn.setFixedHeight(34)
        self._undo_btn.setToolTip("復原上一步（Ctrl+Z）")
        self._undo_btn.setEnabled(False)
        self._undo_btn.clicked.connect(self.undo_requested)
        self._undo_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #BBBAC4;
                border: 1.5px solid #3E3E3E;
                border-radius: 6px;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton:hover { background: #2C2C2C; color: #F2F0EA; border-color: #555; }
            QPushButton:disabled { color: #484858; border-color: #2C2C2C; }
        """)

        self._reset_btn = QPushButton("重設全部")
        self._reset_btn.setFixedHeight(34)
        self._reset_btn.setToolTip("清除所有調色參數")
        self._reset_btn.clicked.connect(self._on_reset)
        self._reset_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #F87171;
                border: 1.5px solid #F87171;
                border-radius: 6px;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton:hover { background: rgba(248,113,113,0.12); }
            QPushButton:pressed { background: rgba(248,113,113,0.22); }
        """)

        btn_lay.addWidget(self._undo_btn, 1)
        btn_lay.addWidget(self._reset_btn, 1)
        lay.addWidget(btn_row)

        # Row 2: Continue button
        self._next_btn = QPushButton("繼續加框 →")
        self._next_btn.setFixedHeight(44)
        self._next_btn.clicked.connect(self.go_next)
        self._next_btn.setStyleSheet("""
            QPushButton {
                background: #C5A46A;
                color: #1A1A1A;
                border: none;
                border-radius: 8px;
                font-size: 14px;
                font-weight: 700;
            }
            QPushButton:hover { background: #D4B87E; }
            QPushButton:pressed { background: #A8894F; }
        """)
        lay.addWidget(self._next_btn)

        return footer

    # ─────────────────────────────────────────────────────────────────────────
    # Section builders
    # ─────────────────────────────────────────────────────────────────────────

    def _build_wb_section(self, lay: QVBoxLayout) -> None:
        sec = _Section("白平衡", collapsed=False)
        self._section_anchors["wb"] = sec
        lay.addWidget(sec)

        # WB preset chip buttons
        chip_row = QWidget()
        chip_row.setStyleSheet("background: transparent;")
        chip_lay = QHBoxLayout(chip_row)
        chip_lay.setContentsMargins(0, 0, 0, 0)
        chip_lay.setSpacing(4)

        auto_btn = self._make_chip("自動")
        auto_btn.clicked.connect(self._apply_auto_wb)
        chip_lay.addWidget(auto_btn)

        for label, kelvin in [("日光", 5600), ("多雲", 6500), ("鎢絲燈", 3200)]:
            btn = self._make_chip(label)
            btn.clicked.connect(lambda _, k=kelvin: self._set_wb_preset(k))
            chip_lay.addWidget(btn)
        chip_lay.addStretch(1)
        sec.add_widget(chip_row)

        self._wb_temp = _SliderRow("色溫", 2000, 12000, 5500)
        self._wb_tint = _SliderRow("色調", -150, 150, 0)
        self._wb_temp.value_changed.connect(lambda v: self._update("wb_temperature", v))
        self._wb_tint.value_changed.connect(lambda v: self._update("wb_tint", v))
        sec.add_widget(self._wb_temp)
        sec.add_widget(self._wb_tint)

    def _build_exposure_section(self, lay: QVBoxLayout) -> None:
        sec = _Section("亮度", collapsed=False)
        self._section_anchors["exposure"] = sec
        lay.addWidget(sec)

        # Auto button in header
        auto_btn = QPushButton("自動")
        auto_btn.setFixedSize(44, 22)
        auto_btn.setToolTip("根據圖片自動設定亮度參數")
        auto_btn.clicked.connect(self._apply_auto_grade)
        auto_btn.setStyleSheet("""
            QPushButton {
                background: #C5A46A; color: #1A1A1A;
                border: none; border-radius: 4px;
                font-size: 11px; font-weight: 600;
            }
            QPushButton:hover { background: #D4B87E; }
        """)
        sec._header.layout().addWidget(auto_btn)

        fields = [
            ("曝光",  "exposure",   -300, 300, 0),
            ("對比",  "contrast",   -100, 100, 0),
            ("亮部",  "highlights", -100, 100, 0),
            ("暗部",  "shadows",    -100, 100, 0),
            ("白色",  "whites",     -100, 100, 0),
            ("黑色",  "blacks",     -100, 100, 0),
        ]
        self._exposure_rows: dict[str, _SliderRow] = {}
        for label, field, mn, mx, default in fields:
            row = _SliderRow(label, mn, mx, default)
            row.value_changed.connect(lambda v, f=field: self._update(f, v))
            self._exposure_rows[field] = row
            sec.add_widget(row)

    def _build_presence_section(self, lay: QVBoxLayout) -> None:
        sec = _Section("臨場感", collapsed=True)
        self._section_anchors["presence"] = sec
        lay.addWidget(sec)

        fields = [
            ("紋理",       "texture",    -100, 100, 0),
            ("清晰度",     "clarity",    -100, 100, 0),
            ("去霧",       "dehaze",     -100, 100, 0),
            ("自然飽和度", "vibrance",   -100, 100, 0),
            ("飽和度",     "saturation", -100, 100, 0),
        ]
        self._presence_rows: dict[str, _SliderRow] = {}
        for label, field, mn, mx, default in fields:
            row = _SliderRow(label, mn, mx, default)
            row.value_changed.connect(lambda v, f=field: self._update(f, v))
            self._presence_rows[field] = row
            sec.add_widget(row)

    def _build_hsl_section(self, lay: QVBoxLayout) -> None:
        sec = _Section("色相飽和度", collapsed=True)
        self._section_anchors["hsl"] = sec
        lay.addWidget(sec)

        self._hsl_mode = QComboBox()
        self._hsl_mode.addItems(["色相", "飽和度", "亮度"])
        self._hsl_mode.setFixedHeight(28)
        self._hsl_mode.currentIndexChanged.connect(self._on_hsl_mode_changed)
        self._hsl_mode.setStyleSheet(self._combo_qss())
        sec.add_widget(self._hsl_mode)

        self._hsl_rows: list[_SliderRow] = []
        for label in self._HSL_LABELS:
            row = _SliderRow(label, -100, 100, 0)
            row.value_changed.connect(self._on_hsl_changed)
            self._hsl_rows.append(row)
            sec.add_widget(row)

    def _build_curve_section(self, lay: QVBoxLayout) -> None:
        sec = _Section("色調曲線", collapsed=True)
        self._section_anchors["curve"] = sec
        lay.addWidget(sec)

        ctrl_row = QWidget()
        ctrl_row.setStyleSheet("background: transparent;")
        ctrl_lay = QHBoxLayout(ctrl_row)
        ctrl_lay.setContentsMargins(0, 0, 0, 0)
        ctrl_lay.setSpacing(6)

        self._curve_channel = QComboBox()
        self._curve_channel.addItems(list(self._CHANNEL_COLORS.keys()))
        self._curve_channel.setFixedHeight(28)
        self._curve_channel.currentTextChanged.connect(self._on_curve_channel_changed)
        self._curve_channel.setStyleSheet(self._combo_qss())

        reset_curve_btn = self._make_chip("重置")
        reset_curve_btn.clicked.connect(self._on_curve_reset)

        ctrl_lay.addWidget(self._curve_channel, 1)
        ctrl_lay.addWidget(reset_curve_btn)
        sec.add_widget(ctrl_row)

        self._curve_widget = CurveWidget()
        self._curve_widget.curve_changed.connect(self._on_curve_changed)
        sec.add_widget(self._curve_widget)

        hint = QLabel("拖曳控制點　雙擊刪除")
        hint.setStyleSheet("color: #7A7888; font-size: 10px; background: transparent;")
        sec.add_widget(hint)

    def _build_detail_section(self, lay: QVBoxLayout) -> None:
        sec = _Section("細節", collapsed=True)
        self._section_anchors["detail"] = sec
        lay.addWidget(sec)

        self._detail_noise = _SliderRow("降噪", 0, 100, 0)
        self._detail_sharp = _SliderRow("銳化", 0, 100, 0)
        self._detail_mask  = _SliderRow("遮罩", 0, 100, 20)

        self._detail_noise.value_changed.connect(lambda v: self._update("noise_reduction", v))
        self._detail_sharp.value_changed.connect(lambda v: self._update("sharpening", v))
        self._detail_mask.value_changed.connect(lambda v: self._update("detail_mask", v))

        sec.add_widget(self._detail_noise)
        sec.add_widget(self._detail_sharp)
        sec.add_widget(self._detail_mask)

    def _build_bw_section(self, lay: QVBoxLayout) -> None:
        sec = _Section("黑白", collapsed=True)
        self._section_anchors["bw"] = sec
        lay.addWidget(sec)

        self._bw_toggle = QPushButton("彩色 / 黑白")
        self._bw_toggle.setCheckable(True)
        self._bw_toggle.setFixedHeight(28)
        self._bw_toggle.toggled.connect(self._on_bw_toggle)
        self._bw_toggle.setStyleSheet("""
            QPushButton {
                background: transparent; color: #BBBAC4;
                border: 1.5px solid #3E3E3E;
                border-radius: 6px; font-size: 12px;
            }
            QPushButton:checked {
                background: #C5A46A; color: #1A1A1A;
                border-color: #C5A46A; font-weight: 700;
            }
            QPushButton:hover { border-color: #C5A46A; color: #F2F0EA; }
        """)
        sec.add_widget(self._bw_toggle)

        self._bw_rows: list[_SliderRow] = []
        for label in self._HSL_LABELS:
            row = _SliderRow(label, -100, 100, 0)
            row.value_changed.connect(self._on_bw_mix_changed)
            self._bw_rows.append(row)
            sec.add_widget(row)

    def _build_split_tone_section(self, lay: QVBoxLayout) -> None:
        sec = _Section("分割色調", collapsed=True)
        self._section_anchors["split_tone"] = sec
        lay.addWidget(sec)

        hi_lbl = self._sub_label("亮部")
        sec.add_widget(hi_lbl)

        self._split_hi_hue = _SliderRow("色相", 0, 360, 0)
        self._split_hi_sat = _SliderRow("飽和度", 0, 100, 0)
        self._split_hi_hue.value_changed.connect(lambda v: self._update("split_highlights_hue", v))
        self._split_hi_sat.value_changed.connect(lambda v: self._update("split_highlights_sat", v))
        sec.add_widget(self._split_hi_hue)
        sec.add_widget(self._split_hi_sat)

        sh_lbl = self._sub_label("暗部")
        sec.add_widget(sh_lbl)

        self._split_sh_hue = _SliderRow("色相", 0, 360, 0)
        self._split_sh_sat = _SliderRow("飽和度", 0, 100, 0)
        self._split_sh_hue.value_changed.connect(lambda v: self._update("split_shadows_hue", v))
        self._split_sh_sat.value_changed.connect(lambda v: self._update("split_shadows_sat", v))
        sec.add_widget(self._split_sh_hue)
        sec.add_widget(self._split_sh_sat)

        self._split_balance = _SliderRow("平衡", -100, 100, 0)
        self._split_balance.value_changed.connect(lambda v: self._update("split_balance", v))
        sec.add_widget(self._split_balance)

    def _build_effects_section(self, lay: QVBoxLayout) -> None:
        sec = _Section("效果", collapsed=True)
        self._section_anchors["effects"] = sec
        lay.addWidget(sec)

        sec.add_widget(self._sub_label("暗角"))
        self._vignette_amount   = _SliderRow("數量",  -100, 100, 0)
        self._vignette_midpoint = _SliderRow("中點",     0, 100, 50)
        self._vignette_feather  = _SliderRow("羽化",     0, 100, 50)
        self._vignette_amount.value_changed.connect(lambda v: self._update("vignette_amount", v))
        self._vignette_midpoint.value_changed.connect(lambda v: self._update("vignette_midpoint", v))
        self._vignette_feather.value_changed.connect(lambda v: self._update("vignette_feather", v))
        sec.add_widget(self._vignette_amount)
        sec.add_widget(self._vignette_midpoint)
        sec.add_widget(self._vignette_feather)

        sec.add_widget(self._sub_label("顆粒"))
        self._grain_amount    = _SliderRow("數量",  0, 100,  0)
        self._grain_size      = _SliderRow("大小",  0, 100, 25)
        self._grain_roughness = _SliderRow("粗糙度", 0, 100, 50)
        self._grain_amount.value_changed.connect(lambda v: self._update("grain_amount", v))
        self._grain_size.value_changed.connect(lambda v: self._update("grain_size", v))
        self._grain_roughness.value_changed.connect(lambda v: self._update("grain_roughness", v))
        sec.add_widget(self._grain_amount)
        sec.add_widget(self._grain_size)
        sec.add_widget(self._grain_roughness)

    def _build_transform_section(self, lay: QVBoxLayout) -> None:
        sec = _Section("幾何", collapsed=True)
        self._section_anchors["transform"] = sec
        lay.addWidget(sec)

        self._rotation_row = _SliderRow("旋轉", -450, 450, 0)
        self._rotation_row.value_changed.connect(lambda v: self._update("rotation", v / 10.0))
        sec.add_widget(self._rotation_row)

        flip_row = QWidget()
        flip_row.setStyleSheet("background: transparent;")
        flip_lay = QHBoxLayout(flip_row)
        flip_lay.setContentsMargins(0, 0, 0, 0)
        flip_lay.setSpacing(8)

        self._flip_h_btn = QPushButton("水平翻轉")
        self._flip_h_btn.setCheckable(True)
        self._flip_h_btn.setFixedHeight(28)
        self._flip_h_btn.toggled.connect(lambda v: self._update("flip_h", v))
        self._flip_h_btn.setStyleSheet(self._toggle_chip_qss())

        self._flip_v_btn = QPushButton("垂直翻轉")
        self._flip_v_btn.setCheckable(True)
        self._flip_v_btn.setFixedHeight(28)
        self._flip_v_btn.toggled.connect(lambda v: self._update("flip_v", v))
        self._flip_v_btn.setStyleSheet(self._toggle_chip_qss())

        flip_lay.addWidget(self._flip_h_btn)
        flip_lay.addWidget(self._flip_v_btn)
        flip_lay.addStretch(1)
        sec.add_widget(flip_row)

    def _build_film_section(self, lay: QVBoxLayout) -> None:
        sec = _Section("底片模擬", collapsed=True)
        self._section_anchors["film"] = sec
        lay.addWidget(sec)

        self._lut_combo = QComboBox()
        self._lut_combo.addItem("── 無 ──", userData=None)
        for display_name, filename in BUILTIN_LUTS.items():
            lut_path = str(LUT_ASSETS_DIR / filename)
            self._lut_combo.addItem(display_name, userData=lut_path)
        self._lut_combo.addItem("載入自訂 LUT…", userData="__custom__")
        self._lut_combo.setFixedHeight(28)
        self._lut_combo.currentIndexChanged.connect(self._on_lut_changed)
        self._lut_combo.setStyleSheet(self._combo_qss())
        sec.add_widget(self._lut_combo)

        self._lut_opacity = _SliderRow("不透明度", 0, 100, 100)
        self._lut_opacity.value_changed.connect(lambda v: self._update("lut_opacity", v))
        sec.add_widget(self._lut_opacity)

    # ─────────────────────────────────────────────────────────────────────────
    # HSL handlers
    # ─────────────────────────────────────────────────────────────────────────

    def _on_hsl_mode_changed(self, _: int) -> None:
        mode_idx = self._hsl_mode.currentIndex()
        hsl_fields = ["hsl_hue", "hsl_saturation", "hsl_luminance"]
        vals = getattr(self._settings, hsl_fields[mode_idx])
        for i, row in enumerate(self._hsl_rows):
            row.set_value(vals[i])

    def _on_hsl_changed(self) -> None:
        mode_idx = self._hsl_mode.currentIndex()
        hsl_fields = ["hsl_hue", "hsl_saturation", "hsl_luminance"]
        field = hsl_fields[mode_idx]
        vals = tuple(row.value() for row in self._hsl_rows)
        self._settings = dataclasses.replace(self._settings, **{field: vals})
        self.grade_changed.emit(self._settings)

    # ─────────────────────────────────────────────────────────────────────────
    # Curve handlers
    # ─────────────────────────────────────────────────────────────────────────

    def _on_curve_channel_changed(self, text: str) -> None:
        col = self._CHANNEL_COLORS.get(text) or "#F2F0EA"
        self._curve_widget.set_channel_color(col)
        ch_key = text.split("（")[0]
        curve_map = {
            "RGB": self._settings.curve_rgb,
            "R":   self._settings.curve_r,
            "G":   self._settings.curve_g,
            "B":   self._settings.curve_b,
        }
        self._curve_widget.set_curve(curve_map.get(ch_key, self._settings.curve_rgb))

    def _on_curve_changed(self, curve: CurvePoints) -> None:
        ch_key = self._curve_channel.currentText().split("（")[0]
        field_map = {"RGB": "curve_rgb", "R": "curve_r", "G": "curve_g", "B": "curve_b"}
        field = field_map.get(ch_key, "curve_rgb")
        self._settings = dataclasses.replace(self._settings, **{field: curve})
        self.grade_changed.emit(self._settings)

    def _on_curve_reset(self) -> None:
        ch_key = self._curve_channel.currentText().split("（")[0]
        field_map = {"RGB": "curve_rgb", "R": "curve_r", "G": "curve_g", "B": "curve_b"}
        field = field_map.get(ch_key, "curve_rgb")
        self._settings = dataclasses.replace(self._settings, **{field: CurvePoints()})
        self._curve_widget.reset()

    # ─────────────────────────────────────────────────────────────────────────
    # B&W handlers
    # ─────────────────────────────────────────────────────────────────────────

    def _on_bw_toggle(self, checked: bool) -> None:
        self._update("treatment", "bw" if checked else "color")

    def _on_bw_mix_changed(self) -> None:
        vals = tuple(row.value() for row in self._bw_rows)
        self._settings = dataclasses.replace(self._settings, bw_mix=vals)
        self.grade_changed.emit(self._settings)

    # ─────────────────────────────────────────────────────────────────────────
    # WB + Auto grade helpers
    # ─────────────────────────────────────────────────────────────────────────

    def _set_wb_preset(self, kelvin: int) -> None:
        self._wb_temp.set_value(kelvin)

    def _apply_auto_wb(self) -> None:
        img = self._current_image
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

    def _apply_auto_grade(self) -> None:
        img = self._current_image
        if img is None:
            return
        suggested = compute_auto_grade(img)
        for field, value in suggested.items():
            row = self._exposure_rows.get(field)
            if row is not None:
                row.set_value(value)
            self._settings = dataclasses.replace(self._settings, **{field: value})
        self.grade_changed.emit(self._settings)

    # ─────────────────────────────────────────────────────────────────────────
    # LUT handler
    # ─────────────────────────────────────────────────────────────────────────

    def _on_lut_changed(self, _: int) -> None:
        data = self._lut_combo.currentData()
        if data == "__custom__":
            path, _ = QFileDialog.getOpenFileName(
                self, "選擇 LUT 檔案", "", "LUT 檔案 (*.cube);;所有檔案 (*)"
            )
            if path:
                self._custom_lut_path = path
                custom_idx = self._lut_combo.findData("__custom_loaded__")
                short = path.split("/")[-1]
                if custom_idx >= 0:
                    self._lut_combo.setItemText(custom_idx, f"自訂：{short}")
                    self._lut_combo.blockSignals(True)
                    self._lut_combo.setCurrentIndex(custom_idx)
                    self._lut_combo.blockSignals(False)
                else:
                    self._lut_combo.blockSignals(True)
                    insert_at = self._lut_combo.count() - 1
                    self._lut_combo.insertItem(insert_at, f"自訂：{short}", userData="__custom_loaded__")
                    self._lut_combo.setCurrentIndex(insert_at)
                    self._lut_combo.blockSignals(False)
                self._update("lut_path", path)
            else:
                # Cancelled — revert to previous
                self._lut_combo.blockSignals(True)
                cur = self._settings.lut_path
                idx = self._lut_combo.findData(cur) if cur else 0
                self._lut_combo.setCurrentIndex(max(0, idx))
                self._lut_combo.blockSignals(False)
        elif data == "__custom_loaded__":
            self._update("lut_path", self._custom_lut_path)
        else:
            self._update("lut_path", data)

    # ─────────────────────────────────────────────────────────────────────────
    # Style helpers
    # ─────────────────────────────────────────────────────────────────────────

    def _apply_panel_style(self) -> None:
        self.setStyleSheet("""
            QWidget#ColorGradePanel {
                background: #222222;
                border-left: 2px solid #3E3E3E;
            }
            QScrollBar:vertical {
                width: 4px; background: transparent; margin: 0; border: none;
            }
            QScrollBar::handle:vertical {
                background: #444444; border-radius: 2px; min-height: 24px;
            }
            QScrollBar::handle:vertical:hover { background: #7A7888; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }
        """)

    @staticmethod
    def _combo_qss() -> str:
        return """
            QComboBox {
                background: #2C2C2C; color: #F2F0EA;
                border: 1.5px solid #3E3E3E; border-radius: 6px;
                font-size: 12px; padding: 0 8px;
            }
            QComboBox:hover { border-color: #555555; }
            QComboBox::drop-down { border: none; width: 20px; }
            QComboBox QAbstractItemView {
                background: #2C2C2C; color: #F2F0EA;
                border: 1px solid #3E3E3E;
                selection-background-color: rgba(197,164,106,0.15);
                selection-color: #C5A46A;
            }
        """

    @staticmethod
    def _make_chip(text: str) -> QPushButton:
        btn = QPushButton(text)
        btn.setFixedHeight(24)
        btn.setStyleSheet("""
            QPushButton {
                background: transparent; color: #BBBAC4;
                border: 1px solid #3E3E3E; border-radius: 6px;
                font-size: 11px; padding: 0 8px;
            }
            QPushButton:hover { background: #2C2C2C; color: #F2F0EA; border-color: #555; }
            QPushButton:pressed { background: #363636; }
        """)
        return btn

    @staticmethod
    def _toggle_chip_qss() -> str:
        return """
            QPushButton {
                background: transparent; color: #BBBAC4;
                border: 1.5px solid #3E3E3E; border-radius: 6px; font-size: 12px;
            }
            QPushButton:checked {
                background: #C5A46A; color: #1A1A1A;
                border-color: #C5A46A; font-weight: 700;
            }
            QPushButton:hover { border-color: #C5A46A; color: #F2F0EA; }
        """

    @staticmethod
    def _sub_label(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(
            "color: #BBBAC4; font-size: 11px; font-weight: 700; background: transparent;"
        )
        return lbl
