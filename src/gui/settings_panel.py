"""
SettingsPanel — 全新版面設定面板（無模板選擇，已移至 TopBar）。

區段順序（由上到下）：
  1. 輸出比例   (anchor: ratio)
  2. 邊框設定   (anchor: border)  — 大小 + 顏色合併
  3. 品牌 & EXIF (anchor: brand)
  4. 匯出設定   (anchor: export)  — 格式、品質 + 匯出按鈕
"""
from __future__ import annotations
from pathlib import Path
from typing import Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QCheckBox, QSlider, QFileDialog,
    QScrollArea, QSizePolicy, QFrame, QPushButton,
    QComboBox, QLineEdit, QInputDialog, QColorDialog,
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QColor

import src.gui.theme as T


def _tm():
    from src.gui.theme_manager import ThemeManager
    return ThemeManager.instance()


from src.gui.widgets import (
    AnimatedButton, GhostButton, SegmentedControl,
    RatioCard, BrandButton, ColorSwatch,
)
from src.models.settings import (
    TemplateStyle, AspectRatioPreset, BorderPreset,
    BorderSettings, LogoStyle, TextAlign,
)
from src.core.brand_renderer import BRANDS


# ── Helpers ───────────────────────────────────────────────────────────────────

class _SectionHeader(QLabel):
    """區段標題 — Paper 風格：大寫粗字、底部橫線。"""
    def __init__(self, text: str, parent=None):
        super().__init__(text.upper(), parent)
        self._apply()
        _tm().theme_changed.connect(lambda _: self._apply())

    def _apply(self) -> None:
        self.setStyleSheet(f"""
            QLabel {{
                color: {T.TEXT_MUTED};
                font-family: "{T.ui_font_family()}";
                font-size: {T.FONT_XS}px;
                font-weight: 600;
                letter-spacing: 1.5px;
                padding: 0 0 4px 0;
                background: transparent;
                border: none;
                border-bottom: 1px solid {T.BORDER};
            }}
        """)


class _Card(QWidget):
    """Paper 風格卡片：方框外框 2px 實線，無圓角，白紙底色。"""
    _counter = 0

    def __init__(self, parent=None):
        super().__init__(parent)
        _Card._counter += 1
        self.setObjectName(f"card_{_Card._counter}")
        self._lay = QVBoxLayout(self)
        self._lay.setContentsMargins(T.S3, T.S4, T.S3, T.S4)
        self._lay.setSpacing(T.S3)
        self._apply()
        _tm().theme_changed.connect(lambda _: self._apply())

    def _apply(self) -> None:
        self.setStyleSheet(f"""
            QWidget#{self.objectName()} {{
                background: {T.SURFACE_2};
                border: 1px solid {T.BORDER};
                border-radius: {T.R_CARD}px;
            }}
        """)

    def add(self, w: QWidget) -> None:
        self._lay.addWidget(w)

    def add_layout(self, l) -> None:
        self._lay.addLayout(l)


class _Divider(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.HLine)
        self.setStyleSheet(f"color: {T.BORDER};")
        self.setFixedHeight(1)


class _AnchorWidget(QWidget):
    """為設定面板各區段提供捲動定位錨點。"""
    def __init__(self, section_id: str, parent=None):
        super().__init__(parent)
        self._id = section_id
        self.setFixedHeight(0)

    @property
    def section_id(self) -> str:
        return self._id


class _LabelledSlider(QWidget):
    value_changed = pyqtSignal(int)

    def __init__(self, lo: int, hi: int, default: int, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: transparent;")
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(T.S2)

        self._s = QSlider(Qt.Orientation.Horizontal)
        self._s.setRange(lo, hi)
        self._s.setValue(default)
        self._apply_slider_style()
        self._lbl = QLabel(str(default))
        self._lbl.setFixedWidth(32)
        self._lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._lbl.setStyleSheet(
            f"color: {T.TEXT_PRIMARY}; font-size: {T.FONT_SM}px; font-weight: 600;"
        )
        self._s.valueChanged.connect(lambda v: self._lbl.setText(str(v)))
        self._s.valueChanged.connect(self.value_changed)
        self._s.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._s.wheelEvent = self._wheel
        row.addWidget(self._s)
        row.addWidget(self._lbl)
        _tm().theme_changed.connect(lambda _: self._apply_slider_style())

    def _apply_slider_style(self) -> None:
        self._s.setStyleSheet(f"""
            QSlider::groove:horizontal {{
                height: 4px; background: {T.SURFACE_3}; border-radius: 2px;
            }}
            QSlider::handle:horizontal {{
                width: 16px; height: 16px;
                background: {T.PRIMARY};
                border-radius: 8px;
                margin: -6px 0;
                border: 2px solid {T.SURFACE};
            }}
            QSlider::handle:horizontal:hover {{ background: {T.PRIMARY_HOVER}; }}
            QSlider::sub-page:horizontal {{ background: {T.PRIMARY}; border-radius: 2px; }}
        """)

    def _wheel(self, e) -> None:
        delta = e.angleDelta().y()
        step  = max(1, (self._s.maximum() - self._s.minimum()) // 50)
        self._s.setValue(self._s.value() + (step if delta > 0 else -step))
        e.accept()

    def value(self) -> int:
        return self._s.value()

    def set_value(self, v: int) -> None:
        self._s.setValue(v)


# ── Main panel ────────────────────────────────────────────────────────────────

class SettingsPanel(QScrollArea):
    settings_changed = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        # 固定寬度：讓使用者無法左右調整 ─ 三個值都設同一個數字
        _W = 360
        self.setFixedWidth(_W)
        self.setMinimumWidth(_W)
        self.setMaximumWidth(_W)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)

        body = QWidget()
        self._body = body
        root = QVBoxLayout(body)
        root.setContentsMargins(T.S3, T.S3, T.S3, T.S4)
        root.setSpacing(T.S2)

        # ── 區段建立 ──
        self._anchors: dict[str, _AnchorWidget] = {}

        self._add_anchor(root, "presets")
        root.addWidget(self._build_presets_section())

        self._add_anchor(root, "ratio")
        root.addWidget(self._build_ratio_section())

        self._add_anchor(root, "border")
        root.addWidget(self._build_border_section())    # 邊框大小 + 顏色合併

        self._add_anchor(root, "color")                # color anchor → 指向同一個 card 底部

        self._add_anchor(root, "brand")
        root.addWidget(self._build_brand_section())

        self._add_anchor(root, "export")
        root.addWidget(self._build_export_section())

        root.addStretch()
        self.setWidget(body)

        self._custom_logo: Optional[Path] = None
        self._logo_brand: Optional[str]   = None
        self._selected_template = TemplateStyle.CLASSIC
        self._selected_ratio    = AspectRatioPreset.SQUARE_1_1
        self._split_crop_x: float = 0.5
        self._split_crop_y: float = 0.5
        self._split_zoom:   float = 1.0

        # Logo 選項預設隱藏（與 checkbox 初始狀態同步）
        self._logo_opts.setVisible(False)

        self._apply_panel_style()
        _tm().theme_changed.connect(lambda _: self._apply_panel_style())

    def _add_anchor(self, layout: QVBoxLayout, section_id: str) -> None:
        anchor = _AnchorWidget(section_id)
        self._anchors[section_id] = anchor
        layout.addWidget(anchor)

    def _apply_panel_style(self) -> None:
        self.setStyleSheet(f"""
            QScrollArea {{
                background: {T.SURFACE};
                border: none;
                border-left: 1px solid {T.BORDER};
            }}
            {T.scrollbar_qss()}
        """)
        self._body.setStyleSheet(f"background: {T.SURFACE};")

    # ── 區段：設定預設組 ──────────────────────────────────────────────────────

    def _build_presets_section(self) -> QWidget:
        from src.gui import preset_manager as PM
        card = _Card()
        hdr_row = QHBoxLayout()
        hdr_row.addWidget(_SectionHeader("設定預設組"))
        hdr_row.addStretch()
        card.add_layout(hdr_row)

        combo_row = QHBoxLayout()
        combo_row.setSpacing(6)
        self._preset_combo = QComboBox()
        self._preset_combo.setPlaceholderText("選擇預設…")
        self._preset_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._preset_combo.setFixedHeight(32)
        self._preset_combo.setStyleSheet(self._combo_qss())
        _tm().theme_changed.connect(lambda _: self._preset_combo.setStyleSheet(self._combo_qss()))
        combo_row.addWidget(self._preset_combo)

        apply_btn = GhostButton("套用", font_size=T.FONT_SM, padding="5px 10px", bold=False)
        apply_btn.setFixedHeight(32)
        apply_btn.clicked.connect(self._apply_preset)
        combo_row.addWidget(apply_btn)
        card.add_layout(combo_row)

        action_row = QHBoxLayout()
        action_row.setSpacing(6)
        save_btn = GhostButton("儲存目前設定…", font_size=T.FONT_SM, padding="5px 10px", bold=False)
        save_btn.clicked.connect(self._save_preset)
        del_btn  = GhostButton("刪除", font_size=T.FONT_SM, padding="5px 8px", bold=False)
        del_btn.clicked.connect(self._delete_preset)
        action_row.addWidget(save_btn)
        action_row.addWidget(del_btn)
        action_row.addStretch()
        card.add_layout(action_row)

        self._reload_presets()
        return card

    def _combo_qss(self) -> str:
        return f"""
            QComboBox {{
                background: {T.SURFACE_2};
                border: 1px solid {T.BORDER};
                border-radius: {T.R_INPUT}px;
                padding: 4px 8px;
                font-size: {T.FONT_SM}px;
                color: {T.TEXT_PRIMARY};
            }}
            QComboBox::drop-down {{ border: none; width: 20px; }}
            QComboBox QAbstractItemView {{
                background: {T.SURFACE};
                border: 1px solid {T.BORDER};
                selection-background-color: {T.PRIMARY_ALPHA};
                color: {T.TEXT_PRIMARY};
                font-size: {T.FONT_SM}px;
            }}
        """

    def _reload_presets(self) -> None:
        from src.gui import preset_manager as PM
        self._preset_combo.clear()
        for name in PM.load_all():
            self._preset_combo.addItem(name)

    def _apply_preset(self) -> None:
        from src.gui import preset_manager as PM
        name = self._preset_combo.currentText()
        if not name:
            return
        presets = PM.load_all()
        if name in presets:
            s = PM.from_dict(presets[name])
            self.restore_settings(s)
            self._emit()

    def _save_preset(self) -> None:
        from src.gui import preset_manager as PM
        name, ok = QInputDialog.getText(
            self, "儲存預設組", "輸入預設名稱："
        )
        if ok and name.strip():
            PM.save(name.strip(), self.current_settings())
            self._reload_presets()
            idx = self._preset_combo.findText(name.strip())
            if idx >= 0:
                self._preset_combo.setCurrentIndex(idx)

    def _delete_preset(self) -> None:
        from src.gui import preset_manager as PM
        name = self._preset_combo.currentText()
        if name:
            PM.delete(name)
            self._reload_presets()

    # ── 區段：輸出比例 ────────────────────────────────────────────────────────

    def _build_ratio_section(self) -> QWidget:
        card = _Card()

        hdr = QHBoxLayout()
        hdr.addWidget(_SectionHeader("輸出比例"))
        hdr.addStretch()
        sub = QLabel("Instagram 最佳化")
        sub.setStyleSheet(f"color: {T.TEXT_MUTED}; font-size: {T.FONT_XS}px; background: transparent;")
        hdr.addWidget(sub)
        card.add_layout(hdr)

        grid = QGridLayout()
        grid.setSpacing(T.S1 + 2)
        grid.setContentsMargins(0, T.S1, 0, 0)
        for c in range(3):
            grid.setColumnStretch(c, 1)

        presets = [
            (AspectRatioPreset.SQUARE_1_1,      "1:1"),
            (AspectRatioPreset.PORTRAIT_4_5,    "4:5"),
            (AspectRatioPreset.PORTRAIT_3_4,    "3:4"),
            (AspectRatioPreset.PORTRAIT_2_3,    "2:3"),
            (AspectRatioPreset.STORIES_9_16,    "9:16"),
            (AspectRatioPreset.LANDSCAPE_191_1, "1.91:1"),
            (AspectRatioPreset.LANDSCAPE_16_9,  "16:9"),
            (AspectRatioPreset.LANDSCAPE_5_4,   "5:4"),
            (AspectRatioPreset.FREE,            "自由"),
        ]
        self._ratio_cards: list[RatioCard] = []
        for i, (preset, lbl) in enumerate(presets):
            rc = RatioCard(preset, lbl)
            rc.clicked.connect(self._on_ratio_clicked)
            self._ratio_cards.append(rc)
            grid.addWidget(rc, i // 3, i % 3)

        self._ratio_cards[0].set_selected(True)
        card.add_layout(grid)
        return card

    def _on_ratio_clicked(self, preset: AspectRatioPreset) -> None:
        self._selected_ratio = preset
        for rc in self._ratio_cards:
            rc.set_selected(rc._preset == preset)
        self._emit()

    # ── 區段：邊框設定（大小 + 顏色合併）────────────────────────────────────

    _BORDER_PRESETS = [("細", 10), ("中", 40), ("粗", 80)]
    _COLOR_PRESETS: list[tuple[int, int, int]] = [
        (255, 255, 255), (240, 240, 240), (200, 200, 200),
        (140, 140, 140), (70,  70,  70),  (20,  20,  20),
        (245, 235, 220), (230, 215, 195), (200, 185, 165),
    ]
    _COLOR_NAMES = ["純白", "淺灰", "中灰", "深灰", "暗灰", "近黑", "奶油", "暖米", "大地棕"]

    def _build_border_section(self) -> QWidget:
        card = _Card()

        # ── 大小 ──
        hdr_row = QHBoxLayout()
        hdr_row.addWidget(_SectionHeader("邊框設定"))
        hdr_row.addStretch()
        card.add_layout(hdr_row)

        # 預設 Chips（獨立按鈕，間距 8px）
        chips_row = QHBoxLayout()
        chips_row.setSpacing(8)           # ← 各按鈕間距 8px
        chips_row.setContentsMargins(0, 0, 0, 0)

        self._border_chips: list[tuple] = []
        for label, px in self._BORDER_PRESETS:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setFixedSize(64, 32)      # 固定尺寸
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _, v=px: self._on_border_preset(v))
            self._border_chips.append((btn, px))
            chips_row.addWidget(btn)
        chips_row.addStretch()
        card.add_layout(chips_row)

        # 連續滑桿
        self._border_slider = _LabelledSlider(0, 200, 40)
        self._border_slider.value_changed.connect(self._on_border_slider)
        card.add(self._border_slider)

        self._border_val = 40
        self._highlight_border_chip(40)
        self._apply_chip_styles()
        _tm().theme_changed.connect(lambda _: self._apply_chip_styles())

        # ── 分隔 ──
        card.add(_Divider())

        # ── 模糊背景開關 ──
        self._blur_bg_cb = QCheckBox("模糊背景（用照片填充邊框）")
        self._blur_bg_cb.setChecked(False)
        self._blur_bg_cb.setStyleSheet(f"""
            QCheckBox {{
                color: {T.TEXT_PRIMARY}; font-size: {T.FONT_MD}px; spacing: 8px;
                background: transparent;
            }}
        """)
        self._blur_bg_cb.stateChanged.connect(self._on_blur_bg_toggle)
        card.add(self._blur_bg_cb)

        card.add(_Divider())

        # ── 顏色（包在容器裡，模糊背景開啟時整體隱藏）──
        self._color_section = QWidget()
        self._color_section.setStyleSheet("background: transparent;")
        color_lay = QVBoxLayout(self._color_section)
        color_lay.setContentsMargins(0, 0, 0, 0)
        color_lay.setSpacing(T.S2)

        color_hdr = QHBoxLayout()
        color_hdr.addWidget(_SectionHeader("外框顏色"))
        color_lay.addLayout(color_hdr)

        self._color_swatches: list[ColorSwatch] = []
        self._bg_color: tuple[int, int, int]    = (255, 255, 255)

        COLS = 3
        outer = QVBoxLayout()
        outer.setSpacing(T.S2)
        outer.setContentsMargins(0, T.S1, 0, 0)

        for row_i in range(0, len(self._COLOR_PRESETS), COLS):
            row_w = QHBoxLayout()
            row_w.setSpacing(T.S3)
            for col_i in range(COLS):
                idx = row_i + col_i
                if idx >= len(self._COLOR_PRESETS):
                    row_w.addStretch()
                    continue
                color = self._COLOR_PRESETS[idx]
                name  = self._COLOR_NAMES[idx]

                cell = QVBoxLayout()
                cell.setSpacing(2)
                cell.setAlignment(Qt.AlignmentFlag.AlignCenter)

                sw = ColorSwatch(color)
                sw.clicked.connect(self._on_color_click)
                self._color_swatches.append(sw)

                name_lbl = QLabel(name)
                name_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                name_lbl.setStyleSheet(
                    f"color: {T.TEXT_MUTED}; font-size: {T.FONT_XS}px; background: transparent;"
                )
                cell.addWidget(sw, 0, Qt.AlignmentFlag.AlignCenter)
                cell.addWidget(name_lbl)
                row_w.addLayout(cell)
            outer.addLayout(row_w)

        self._color_swatches[0].set_selected(True)
        color_lay.addLayout(outer)

        # ── 自訂顏色列（Hex 輸入 + 選色器）──
        custom_row = QHBoxLayout()
        custom_row.setSpacing(6)
        custom_row.setContentsMargins(0, T.S1, 0, 0)

        self._hex_input = QLineEdit()
        self._hex_input.setPlaceholderText("#ffffff")
        self._hex_input.setFixedWidth(76)
        self._hex_input.setFixedHeight(28)
        self._hex_input.setMaxLength(7)
        self._hex_input.setStyleSheet(f"""
            QLineEdit {{
                background: {T.SURFACE_2};
                border: 1px solid {T.BORDER};
                border-radius: {T.R_INPUT}px;
                padding: 3px 7px;
                font-size: {T.FONT_SM}px;
                color: {T.TEXT_PRIMARY};
                font-family: monospace;
            }}
            QLineEdit:focus {{ border-color: {T.PRIMARY}; }}
        """)
        self._hex_input.editingFinished.connect(self._on_hex_edit)
        _tm().theme_changed.connect(lambda _: self._hex_input.setStyleSheet(f"""
            QLineEdit {{
                background: {T.SURFACE_2};
                border: 1px solid {T.BORDER};
                border-radius: {T.R_INPUT}px;
                padding: 3px 7px;
                font-size: {T.FONT_SM}px;
                color: {T.TEXT_PRIMARY};
                font-family: monospace;
            }}
            QLineEdit:focus {{ border-color: {T.PRIMARY}; }}
        """))

        # 顏色預覽小方塊
        self._hex_preview = QLabel()
        self._hex_preview.setFixedSize(28, 28)
        self._hex_preview.setStyleSheet(
            f"background: #ffffff; border: 1.5px solid {T.BORDER}; border-radius: 4px;"
        )

        pick_btn = GhostButton("選色…", font_size=T.FONT_SM, padding="4px 10px", bold=False)
        pick_btn.setFixedHeight(28)
        pick_btn.clicked.connect(self._open_color_dialog)

        custom_row.addWidget(self._hex_input)
        custom_row.addWidget(self._hex_preview)
        custom_row.addWidget(pick_btn)
        custom_row.addStretch()
        color_lay.addLayout(custom_row)

        card.add(self._color_section)
        return card

    def _apply_chip_styles(self) -> None:
        """Dark luxury chip: gold-dim selected, subtle glass hover."""
        for btn, _ in self._border_chips:
            sel = btn.isChecked()
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: {T.GOLD_DIM if sel else "transparent"};
                    color: {T.GOLD if sel else T.TEXT_SECONDARY};
                    border: 1px solid {T.GOLD if sel else T.BORDER};
                    border-radius: {T.R_CHIP}px;
                    font-size: {T.FONT_SM}px;
                    font-weight: {"600" if sel else "500"};
                    padding: 2px 16px;
                }}
                QPushButton:hover:!checked {{
                    background: {T.GLASS_2};
                    color: {T.TEXT_PRIMARY};
                }}
            """)

    def _highlight_border_chip(self, val: int) -> None:
        for btn, px in self._border_chips:
            btn.setChecked(px == val)
        self._apply_chip_styles()

    def _on_border_preset(self, val: int) -> None:
        self._border_slider.set_value(val)

    def _on_border_slider(self, val: int) -> None:
        self._border_val = val
        self._highlight_border_chip(val)
        self._emit()

    def _on_blur_bg_toggle(self, _) -> None:
        self._color_section.setVisible(not self._blur_bg_cb.isChecked())
        self._emit()

    def _on_hex_edit(self) -> None:
        raw = self._hex_input.text().strip()
        if not raw.startswith("#"):
            raw = "#" + raw
        qc = QColor(raw)
        if qc.isValid():
            rgb = (qc.red(), qc.green(), qc.blue())
            self._set_custom_color(rgb)

    def _open_color_dialog(self) -> None:
        init = QColor(*self._bg_color)
        chosen = QColorDialog.getColor(
            init, self, "選擇外框顏色",
            QColorDialog.ColorDialogOption.DontUseNativeDialog,
        )
        if chosen.isValid():
            rgb = (chosen.red(), chosen.green(), chosen.blue())
            self._set_custom_color(rgb)

    def _set_custom_color(self, rgb: tuple) -> None:
        self._bg_color = rgb
        for sw in self._color_swatches:
            sw.set_selected(sw._color == rgb)
        hex_str = "#{:02x}{:02x}{:02x}".format(*rgb)
        self._hex_input.setText(hex_str)
        self._hex_preview.setStyleSheet(
            f"background: {hex_str}; border: 1.5px solid {T.BORDER}; border-radius: 4px;"
        )
        self._emit()

    def _on_color_click(self, color: tuple[int, int, int]) -> None:
        self._set_custom_color(color)

    # ── 區段：品牌 & EXIF ─────────────────────────────────────────────────────

    def _build_brand_section(self) -> QWidget:
        card = _Card()
        card.add(_SectionHeader("品牌 & EXIF"))

        cb_qss = f"""
            QCheckBox {{
                color: {T.TEXT_PRIMARY}; font-size: {T.FONT_MD}px; spacing: 8px;
                background: transparent;
            }}
            QCheckBox::indicator {{
                width: 17px; height: 17px;
                border: 1.5px solid {T.BORDER_LIGHT};
                border-radius: 5px;
                background: {T.SURFACE_3};
            }}
            QCheckBox::indicator:checked {{
                background: {T.PRIMARY};
                border-color: {T.PRIMARY};
            }}
            QCheckBox::indicator:hover {{ border-color: {T.PRIMARY}; }}
        """

        toggles_row = QHBoxLayout()
        toggles_row.setSpacing(T.S4)
        self._show_logo_cb = QCheckBox("品牌 Logo")
        self._show_logo_cb.setChecked(False)
        self._show_logo_cb.setStyleSheet(cb_qss)
        self._show_logo_cb.stateChanged.connect(self._on_logo_toggle)

        self._show_exif_cb = QCheckBox("拍攝參數")
        self._show_exif_cb.setChecked(False)
        self._show_exif_cb.setStyleSheet(cb_qss)
        self._show_exif_cb.stateChanged.connect(lambda _: self._emit())
        toggles_row.addWidget(self._show_logo_cb)
        toggles_row.addWidget(self._show_exif_cb)
        toggles_row.addStretch()
        card.add_layout(toggles_row)

        # ── 文字對齊 ──
        align_row = QHBoxLayout()
        align_lbl = QLabel("對齊")
        align_lbl.setStyleSheet(
            f"color: {T.TEXT_SECONDARY}; font-size: {T.FONT_BASE}px; background: transparent;"
        )
        self._align_seg = SegmentedControl([
            (TextAlign.LEFT,   "靠左"),
            (TextAlign.CENTER, "置中"),
            (TextAlign.RIGHT,  "靠右"),
        ])
        self._align_seg.set_value(TextAlign.CENTER)
        self._align_seg.value_changed.connect(lambda _: self._emit())
        align_row.addWidget(align_lbl)
        align_row.addStretch()
        align_row.addWidget(self._align_seg)
        card.add_layout(align_row)

        card.add(_Divider())

        # ── 品牌選擇 ──
        self._logo_opts = QWidget()
        self._logo_opts.setStyleSheet("background: transparent;")
        opts = QVBoxLayout(self._logo_opts)
        opts.setContentsMargins(0, 0, 0, 0)
        opts.setSpacing(T.S2)

        brand_lbl = QLabel("相機品牌")
        brand_lbl.setStyleSheet(
            f"color: {T.TEXT_SECONDARY}; font-size: {T.FONT_XS}px; background: transparent;"
        )
        opts.addWidget(brand_lbl)

        brand_w = QWidget()
        brand_w.setStyleSheet("background: transparent;")
        brand_grid = QGridLayout(brand_w)
        brand_grid.setSpacing(T.S1)
        brand_grid.setContentsMargins(0, 0, 0, 0)
        COLS = 5
        for col in range(COLS):
            brand_grid.setColumnStretch(col, 1)

        self._brand_btns: dict[str, BrandButton] = {}
        self._logo_brand: Optional[str] = None

        auto_btn = BrandButton("自動", (120, 120, 120))
        auto_btn.setChecked(True)
        auto_btn.clicked.connect(lambda: self._on_brand_click(None))
        brand_grid.addWidget(auto_btn, 0, 0)
        self._brand_btns["__auto__"] = auto_btn

        for idx, (brand, info) in enumerate(BRANDS.items(), 1):
            btn = BrandButton(info["short"], info["color"])
            btn.clicked.connect(lambda _checked, b=brand: self._on_brand_click(b))
            row, col = divmod(idx, COLS)
            brand_grid.addWidget(btn, row, col)
            self._brand_btns[brand] = btn

        opts.addWidget(brand_w)

        logo_row = QHBoxLayout()
        logo_row.setSpacing(T.S2)
        self._logo_btn = GhostButton("自訂 Logo…", font_size=T.FONT_SM, padding="5px 10px", bold=False)
        self._logo_btn.clicked.connect(self._pick_logo)
        self._logo_reset = GhostButton("重置", font_size=T.FONT_SM, padding="5px 8px", bold=False)
        self._logo_reset.setEnabled(False)
        self._logo_reset.clicked.connect(self._reset_logo)
        logo_row.addWidget(self._logo_btn)
        logo_row.addWidget(self._logo_reset)
        logo_row.addStretch()
        opts.addLayout(logo_row)

        self._logo_hint = QLabel("自動偵測品牌文字")
        self._logo_hint.setStyleSheet(
            f"color: {T.TEXT_MUTED}; font-size: {T.FONT_SM}px; background: transparent;"
        )
        opts.addWidget(self._logo_hint)
        card.add(self._logo_opts)
        return card

    def _on_logo_toggle(self, _) -> None:
        self._logo_opts.setVisible(self._show_logo_cb.isChecked())
        self._emit()

    def _on_brand_click(self, brand: Optional[str]) -> None:
        self._logo_brand = brand
        for key, btn in self._brand_btns.items():
            btn.setChecked(key == ("__auto__" if brand is None else brand))
        self._emit()

    def _pick_logo(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "選擇 Logo", "", "PNG (*.png)")
        if path:
            self._custom_logo = Path(path)
            self._logo_hint.setText(Path(path).name)
            self._logo_reset.setEnabled(True)
            self._emit()

    def _reset_logo(self) -> None:
        self._custom_logo = None
        self._logo_hint.setText("自動偵測品牌文字")
        self._logo_reset.setEnabled(False)
        self._emit()

    # ── 區段：匯出設定 ────────────────────────────────────────────────────────

    def _build_export_section(self) -> QWidget:
        card = _Card()
        card.add(_SectionHeader("匯出設定"))

        # 格式
        fmt_row = QHBoxLayout()
        fmt_lbl = QLabel("格式")
        fmt_lbl.setStyleSheet(
            f"color: {T.TEXT_SECONDARY}; font-size: {T.FONT_BASE}px; background: transparent;"
        )
        self._fmt_seg = SegmentedControl([("JPEG", "JPEG"), ("PNG", "PNG")])
        self._fmt_seg.value_changed.connect(self._on_fmt_change)
        fmt_row.addWidget(fmt_lbl)
        fmt_row.addStretch()
        fmt_row.addWidget(self._fmt_seg)
        card.add_layout(fmt_row)

        # 品質（僅 JPEG）
        self._q_widget = QWidget()
        self._q_widget.setStyleSheet("background: transparent;")
        ql = QHBoxLayout(self._q_widget)
        ql.setContentsMargins(0, 0, 0, 0)
        ql.setSpacing(T.S2)
        q_lbl = QLabel("品質")
        q_lbl.setFixedWidth(28)
        q_lbl.setStyleSheet(
            f"color: {T.TEXT_SECONDARY}; font-size: {T.FONT_BASE}px; background: transparent;"
        )
        self._q_slider = _LabelledSlider(60, 100, 95)
        self._q_slider.value_changed.connect(lambda _: self._emit())
        ql.addWidget(q_lbl)
        ql.addWidget(self._q_slider)
        card.add(self._q_widget)

        card.add(_Divider())

        # 匯出按鈕
        self._export_btn = AnimatedButton("匯出", font_size=T.FONT_LG, padding="13px 0")
        self._export_btn.setEnabled(False)
        self._export_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._export_btn.setMinimumHeight(48)
        card.add(self._export_btn)
        return card

    def _on_fmt_change(self, fmt: str) -> None:
        self._q_widget.setVisible(fmt == "JPEG")
        self._emit()

    # ── 導覽捲動 ──────────────────────────────────────────────────────────────

    def scroll_to_section(self, section_id: str) -> None:
        anchor = self._anchors.get(section_id)
        if anchor is None:
            return
        QTimer.singleShot(0, lambda: self._do_scroll(anchor))

    def _do_scroll(self, anchor: _AnchorWidget) -> None:
        y = anchor.mapTo(self.widget(), anchor.rect().topLeft()).y()
        self.verticalScrollBar().setValue(max(0, y - 8))

    # ── 公開 API ─────────────────────────────────────────────────────────────

    def set_template(self, style: TemplateStyle) -> None:
        self._selected_template = style
        self._emit()

    def _emit(self, *_) -> None:
        if getattr(self, "_restoring", False):
            return
        self.settings_changed.emit(self.current_settings())

    def restore_settings(self, s: "BorderSettings") -> None:
        """還原照片的獨立設定到面板，不觸發 settings_changed。"""
        self._restoring = True
        try:
            # 比例
            self._selected_ratio = s.aspect_ratio
            for rc in self._ratio_cards:
                rc.set_selected(rc._preset == s.aspect_ratio)
            # 邊框
            val = s.custom_top
            self._border_val = val
            self._border_slider.set_value(val)
            self._highlight_border_chip(val)
            # 外框顏色
            self._bg_color = s.bg_color
            for sw in self._color_swatches:
                sw.set_selected(sw._color == s.bg_color)
            hex_str = "#{:02x}{:02x}{:02x}".format(*s.bg_color)
            self._hex_input.setText(hex_str)
            self._hex_preview.setStyleSheet(
                f"background: {hex_str}; border: 1.5px solid {T.BORDER}; border-radius: 4px;"
            )
            # EXIF / Logo 開關
            self._show_logo_cb.setChecked(s.show_logo)
            self._show_exif_cb.setChecked(s.show_exif)
            self._logo_opts.setVisible(s.show_logo)
            # 品牌
            self._logo_brand = s.logo_brand_override
            for key, btn in self._brand_btns.items():
                btn.setChecked(
                    key == ("__auto__" if s.logo_brand_override is None
                            else s.logo_brand_override)
                )
            # 文字對齊
            self._align_seg.set_value(s.text_align)
            # 模糊背景
            self._blur_bg_cb.setChecked(s.blur_background)
            self._color_section.setVisible(not s.blur_background)
            # 匯出格式 / 品質
            self._fmt_seg.set_value(s.output_format)
            self._q_slider.set_value(s.jpeg_quality)
            # 版型（僅更新內部狀態，不觸發 emit）
            self._selected_template = s.template
            # SPLIT 裁切偏移 + 縮放
            self._split_crop_x = s.split_crop_x
            self._split_crop_y = s.split_crop_y
            self._split_zoom   = s.split_zoom
        finally:
            self._restoring = False

    def current_settings(self) -> BorderSettings:
        return BorderSettings(
            template         = self._selected_template,
            aspect_ratio     = self._selected_ratio,
            border_preset    = BorderPreset.CUSTOM,
            custom_top       = self._border_val,
            custom_side      = self._border_val,
            custom_exif_strip= max(48, self._border_val + 40),
            show_logo        = self._show_logo_cb.isChecked(),
            show_exif        = self._show_exif_cb.isChecked(),
            logo_style       = LogoStyle.LOGO,
            logo_brand_override = self._logo_brand,
            text_align       = self._align_seg.current_value() or TextAlign.CENTER,
            bg_color         = self._bg_color,
            blur_background  = self._blur_bg_cb.isChecked(),
            custom_logo_path = self._custom_logo,
            output_format    = self._fmt_seg.current_value() or "JPEG",
            jpeg_quality     = self._q_slider.value(),
            split_crop_x     = self._split_crop_x,
            split_crop_y     = self._split_crop_y,
            split_zoom       = self._split_zoom,
        )

    def enable_export(self, enabled: bool) -> None:
        self._export_btn.setEnabled(enabled)

    def add_back_button(self, callback) -> None:
        """在面板頂部加入「← 返回調色」按鈕。"""
        from PyQt6.QtWidgets import QPushButton
        btn = QPushButton("← 返回調色")
        btn.setFixedHeight(32)
        btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {T.TEXT_SECONDARY};
                border: 1.5px solid {T.BORDER_LIGHT};
                border-radius: {T.R_CHIP}px;
                font-size: {T.FONT_SM}px;
                padding: 2px 12px;
            }}
            QPushButton:hover {{
                background: {T.SURFACE_2};
                color: {T.TEXT_PRIMARY};
                border-color: {T.BORDER};
            }}
        """)
        btn.clicked.connect(callback)
        # 插入到最頂層 layout 第一個位置
        self.widget().layout().insertWidget(0, btn)

    @property
    def export_button(self) -> AnimatedButton:
        return self._export_btn
