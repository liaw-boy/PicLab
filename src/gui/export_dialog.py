"""
Export dialog — Dark Luxury Precision, Stitch Screen 3.
Gold hairline border, segmented format control, quality slider, EXIF toggle.
"""
from __future__ import annotations
from pathlib import Path
from typing import Optional

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar,
    QFileDialog, QLineEdit, QMessageBox, QFrame, QSlider,
    QWidget, QCheckBox, QSizePolicy,
)
from PyQt6.QtCore import QThread, pyqtSignal, Qt, QRectF
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QPainterPath

from PIL import Image

import src.gui.theme as T
from src.models.settings import BorderSettings


# ── Background worker ─────────────────────────────────────────────────────────

class ExportWorker(QThread):
    progress = pyqtSignal(int)
    finished = pyqtSignal(str)
    error    = pyqtSignal(str)

    def __init__(self, image: Image.Image, path: Path, fmt: str, quality: int,
                 settings: BorderSettings):
        super().__init__()
        self._image    = image.copy()
        self._path     = path
        self._fmt      = fmt
        self._quality  = quality
        self._settings = settings

    def run(self) -> None:
        try:
            from src.core.image_processor import finalize_export
            self.progress.emit(10)
            processed = finalize_export(self._image, self._settings)
            self.progress.emit(40)

            kwargs: dict = {}
            if self._fmt == "JPEG":
                kwargs = {"quality": self._quality, "subsampling": 0}
                img = processed.convert("RGB")
            else:
                img = processed

            self.progress.emit(70)
            img.save(str(self._path), format=self._fmt, **kwargs)
            self.progress.emit(100)
            self.finished.emit(str(self._path))
        except Exception as e:
            self.error.emit(str(e))
        finally:
            self._image.close()


# ── Toggle switch ─────────────────────────────────────────────────────────────

class _Toggle(QWidget):
    """macOS-style toggle switch, gold when ON."""
    toggled = pyqtSignal(bool)
    _W, _H = 38, 22

    def __init__(self, checked: bool = False, parent=None):
        super().__init__(parent)
        self._on = checked
        self.setFixedSize(self._W, self._H)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def is_checked(self) -> bool:
        return self._on

    def set_checked(self, v: bool) -> None:
        self._on = v
        self.update()

    def mousePressEvent(self, e) -> None:
        if e.button() == Qt.MouseButton.LeftButton:
            self._on = not self._on
            self.toggled.emit(self._on)
            self.update()

    def paintEvent(self, _) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self._W, self._H
        r = H / 2

        track = QColor("#C5A46A") if self._on else QColor("#444444")
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(track))
        path = QPainterPath()
        path.addRoundedRect(QRectF(0, 0, W, H), r, r)
        p.drawPath(path)

        knob_x = W - H + 3 if self._on else 3
        p.setBrush(QBrush(QColor("#F2F0EA")))
        p.drawEllipse(QRectF(knob_x, 3, H - 6, H - 6))
        p.end()


# ── Segmented control (format selector) ──────────────────────────────────────

class _FormatSeg(QWidget):
    """Pill-style segmented control — active segment gets full gold fill."""
    changed = pyqtSignal(str)
    _OPTS = ["JPEG", "PNG", "TIFF", "WebP"]
    _H = 32

    def __init__(self, parent=None):
        super().__init__(parent)
        self._sel = 0
        self._hovering = -1
        self.setFixedHeight(self._H)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMouseTracking(True)

    def current(self) -> str:
        return self._OPTS[self._sel]

    def set_current(self, fmt: str) -> None:
        if fmt in self._OPTS:
            self._sel = self._OPTS.index(fmt)
            self.update()

    def mouseMoveEvent(self, e) -> None:
        idx = int(e.position().x() / (self.width() / len(self._OPTS)))
        idx = max(0, min(len(self._OPTS) - 1, idx))
        if idx != self._hovering:
            self._hovering = idx
            self.update()

    def leaveEvent(self, e) -> None:
        self._hovering = -1
        self.update()

    def mousePressEvent(self, e) -> None:
        if e.button() == Qt.MouseButton.LeftButton:
            idx = int(e.position().x() / (self.width() / len(self._OPTS)))
            idx = max(0, min(len(self._OPTS) - 1, idx))
            if idx != self._sel:
                self._sel = idx
                self.changed.emit(self._OPTS[self._sel])
                self.update()

    def paintEvent(self, _) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()
        n = len(self._OPTS)
        sw = W / n

        # Container
        p.setPen(QPen(QColor("#3E3E3E"), 1))
        p.setBrush(QBrush(QColor("#2C2C2C")))
        path = QPainterPath()
        path.addRoundedRect(QRectF(0.5, 0.5, W - 1, H - 1), 7, 7)
        p.drawPath(path)

        for i, lbl in enumerate(self._OPTS):
            x = int(i * sw)
            w = int(sw)
            if i == self._sel:
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QBrush(QColor("#C5A46A")))
                sr = QPainterPath()
                r = 6 if i == 0 or i == n - 1 else 3
                rx_l = 6 if i == 0 else 3
                rx_r = 6 if i == n - 1 else 3
                sr.addRoundedRect(QRectF(x + 2, 2, w - 4, H - 4), r, r)
                p.drawPath(sr)
                txt = QColor("#1A1A1A")
                weight = "700"
            elif i == self._hovering:
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QBrush(QColor("#363636")))
                p.drawRoundedRect(QRectF(x + 2, 2, w - 4, H - 4), 4, 4)
                txt = QColor("#F2F0EA")
                weight = "500"
            else:
                txt = QColor("#9A9890")
                weight = "400"

            p.setPen(QPen(txt))
            f = T.ui_font(12)
            p.setFont(f)
            p.drawText(QRectF(x, 0, w, H), Qt.AlignmentFlag.AlignCenter, lbl)

        p.end()


# ── Quality slider row ────────────────────────────────────────────────────────

def _qual_label(v: int) -> str:
    if v >= 95: return f"{v}  (最高品質)"
    if v >= 85: return f"{v}  (極高品質)"
    if v >= 70: return f"{v}  (高品質)"
    return f"{v}  (標準)"


def _divider() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.Shape.HLine)
    f.setStyleSheet(f"color: #3E3E3E; background: #3E3E3E; max-height: 1px;")
    return f


def _sec_label(text: str) -> QLabel:
    l = QLabel(text)
    l.setStyleSheet("color: #9A9890; font-size: 11px; font-weight: 600;"
                    " letter-spacing: 1px; background: transparent;")
    return l


def _field_label(text: str) -> QLabel:
    l = QLabel(text)
    l.setFixedWidth(90)
    l.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    l.setStyleSheet("color: #BBBAC4; font-size: 12px; background: transparent;")
    return l


# ── Main dialog ───────────────────────────────────────────────────────────────

class ExportDialog(QDialog):
    def __init__(
        self,
        image: Image.Image,
        settings: BorderSettings,
        default_dir: Optional[Path] = None,
        parent=None,
    ):
        super().__init__(parent)
        self._image       = image
        self._settings    = settings
        self._default_dir = default_dir
        self._worker: Optional[ExportWorker] = None

        self.setWindowTitle("匯出設定")
        self.setFixedWidth(500)
        self.setModal(True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self._build()

    # ── Build ─────────────────────────────────────────────────────────────────

    def _build(self) -> None:
        self.setStyleSheet(f"""
            QDialog {{
                background: #222222;
                border: 1px solid #C5A46A;
                border-radius: 12px;
            }}
            QLabel {{ background: transparent; }}
            QLineEdit {{
                background: #2C2C2C;
                border: 1px solid #3E3E3E;
                border-radius: 6px;
                color: #F2F0EA;
                font-size: 12px;
                padding: 4px 8px;
            }}
            QLineEdit:focus {{ border-color: #C5A46A; }}
            QPushButton {{
                background: transparent;
                color: #BBBAC4;
                border: 1px solid #3E3E3E;
                border-radius: 6px;
                padding: 5px 14px;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background: #363636;
                color: #F2F0EA;
                border-color: #555555;
            }}
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Header ────────────────────────────────────────────────────────────
        hdr = QWidget()
        hdr.setStyleSheet("background: #1E1E1E; border-bottom: 1px solid #3E3E3E;"
                          " border-top-left-radius: 12px; border-top-right-radius: 12px;")
        hdr.setFixedHeight(56)
        hdr_lay = QHBoxLayout(hdr)
        hdr_lay.setContentsMargins(20, 0, 20, 0)

        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        t = QLabel("匯出設定")
        t.setStyleSheet("color: #F2F0EA; font-size: 15px; font-weight: 600;")
        w, h = self._image.size
        sub = QLabel(f"{w} × {h}  ·  1 張照片")
        sub.setStyleSheet("color: #9A9890; font-size: 11px;")
        title_col.addWidget(t)
        title_col.addWidget(sub)

        hdr_lay.addLayout(title_col)
        hdr_lay.addStretch()

        close_btn = _CloseBtn()
        close_btn.clicked.connect(self.reject)
        hdr_lay.addWidget(close_btn)
        root.addWidget(hdr)

        # ── Content ───────────────────────────────────────────────────────────
        content = QWidget()
        content.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(content)
        lay.setContentsMargins(20, 16, 20, 16)
        lay.setSpacing(14)

        # Format section
        lay.addWidget(_sec_label("檔案設定"))

        fmt_row = QHBoxLayout()
        fmt_row.setSpacing(12)
        fmt_row.addWidget(_field_label("格式"))
        self._fmt_seg = _FormatSeg()
        self._fmt_seg.set_current(getattr(self._settings, "output_format", "JPEG"))
        self._fmt_seg.changed.connect(self._on_fmt_changed)
        fmt_row.addWidget(self._fmt_seg)
        lay.addLayout(fmt_row)

        qual_row = QHBoxLayout()
        qual_row.setSpacing(12)
        qual_row.addWidget(_field_label("品質"))
        self._qual_slider = QSlider(Qt.Orientation.Horizontal)
        self._qual_slider.setRange(1, 100)
        q = getattr(self._settings, "jpeg_quality", 92)
        self._qual_slider.setValue(q)
        self._qual_slider.setFixedHeight(22)
        self._qual_slider.setStyleSheet("""
            QSlider::groove:horizontal { height: 4px; background: #363636; border-radius: 2px; }
            QSlider::sub-page:horizontal { background: #C5A46A; border-radius: 2px; }
            QSlider::handle:horizontal {
                background: #C5A46A; width: 14px; height: 14px;
                margin: -5px 0; border-radius: 7px;
                border: 2px solid rgba(197,164,106,0.3);
            }
            QSlider::handle:horizontal:hover { background: #D4B87E; }
        """)
        self._qual_lbl = QLabel(_qual_label(q))
        self._qual_lbl.setMinimumWidth(130)
        self._qual_lbl.setStyleSheet("color: #C5A46A; font-size: 11px; font-weight: 600;")
        self._qual_slider.valueChanged.connect(
            lambda v: self._qual_lbl.setText(_qual_label(v))
        )
        qual_row.addWidget(self._qual_slider)
        qual_row.addWidget(self._qual_lbl)
        lay.addLayout(qual_row)

        # EXIF toggle row
        exif_row = QHBoxLayout()
        exif_row.setSpacing(12)
        exif_row.addWidget(_field_label("嵌入 EXIF"))
        self._exif_toggle = _Toggle(checked=True)
        exif_row.addWidget(self._exif_toggle)
        exif_row.addStretch()
        lay.addLayout(exif_row)

        lay.addWidget(_divider())

        # Size section
        lay.addWidget(_sec_label("尺寸設定"))

        long_row = QHBoxLayout()
        long_row.setSpacing(12)
        long_row.addWidget(_field_label("限制長邊"))
        self._long_edge = QLineEdit()
        self._long_edge.setPlaceholderText("原始尺寸（留空不縮放）")
        le = getattr(self._settings, "export_long_edge", None)
        if le:
            self._long_edge.setText(str(le))
        long_row.addWidget(self._long_edge)
        lay.addLayout(long_row)

        sharpen_row = QHBoxLayout()
        sharpen_row.setSpacing(12)
        sharpen_row.addWidget(_field_label("輸出銳化"))
        self._sharpen_toggle = _Toggle(
            checked=getattr(self._settings, "output_sharpening", False)
        )
        sharpen_row.addWidget(self._sharpen_toggle)
        sharpen_row.addStretch()
        lay.addLayout(sharpen_row)

        lay.addWidget(_divider())

        # Storage section
        lay.addWidget(_sec_label("儲存位置"))

        path_row = QHBoxLayout()
        path_row.setSpacing(8)
        self._path = QLineEdit()
        self._path.setPlaceholderText("選擇資料夾…")
        if self._default_dir:
            self._path.setText(str(self._default_dir))
        browse = _SmallBtn("瀏覽…")
        browse.clicked.connect(self._browse)
        path_row.addWidget(self._path)
        path_row.addWidget(browse)
        lay.addLayout(path_row)

        name_row = QHBoxLayout()
        name_row.setSpacing(12)
        name_row.addWidget(_field_label("檔名"))
        self._name = QLineEdit("photo_export")
        name_row.addWidget(self._name)
        lay.addLayout(name_row)

        # Progress
        self._prog = QProgressBar()
        self._prog.setRange(0, 100)
        self._prog.setTextVisible(False)
        self._prog.setFixedHeight(3)
        self._prog.setStyleSheet("""
            QProgressBar { background: #3E3E3E; border-radius: 1px; border: none; }
            QProgressBar::chunk { background: #C5A46A; border-radius: 1px; }
        """)
        self._prog.hide()
        lay.addWidget(self._prog)

        root.addWidget(content)

        # ── Footer ────────────────────────────────────────────────────────────
        foot = QWidget()
        foot.setStyleSheet("background: #1A1A1A; border-top: 1px solid #3E3E3E;"
                           " border-bottom-left-radius: 12px; border-bottom-right-radius: 12px;")
        foot.setFixedHeight(64)
        foot_lay = QHBoxLayout(foot)
        foot_lay.setContentsMargins(20, 0, 20, 0)

        self._cancel_btn = _SmallBtn("取消")
        self._cancel_btn.clicked.connect(self.reject)

        self._export_btn = _PrimaryBtn("立即匯出")
        self._export_btn.clicked.connect(self._do)

        note = QLabel("匯出後不會刪除原始檔")
        note.setStyleSheet("color: #9A9890; font-size: 11px; font-style: italic;")

        foot_lay.addWidget(self._cancel_btn)
        foot_lay.addStretch()
        foot_lay.addWidget(note)
        foot_lay.addSpacing(16)
        foot_lay.addWidget(self._export_btn)
        root.addWidget(foot)

    # ── Handlers ──────────────────────────────────────────────────────────────

    def _on_fmt_changed(self, fmt: str) -> None:
        self._qual_slider.setEnabled(fmt == "JPEG")
        opacity = 1.0 if fmt == "JPEG" else 0.35
        self._qual_slider.setStyleSheet(self._qual_slider.styleSheet())

    def _browse(self) -> None:
        start = self._path.text().strip() or str(self._default_dir or "")
        f = QFileDialog.getExistingDirectory(self, "選擇資料夾", start)
        if f:
            self._path.setText(f)

    def _do(self) -> None:
        folder = self._path.text().strip()
        if not folder:
            QMessageBox.warning(self, "錯誤", "請選擇儲存路徑")
            return
        fp = Path(folder)
        if not fp.exists():
            QMessageBox.warning(self, "錯誤", f"資料夾不存在：\n{folder}")
            return

        fmt = self._fmt_seg.current()
        name = self._name.text().strip() or "photo_export"
        ext_map = {"JPEG": "jpg", "PNG": "png", "TIFF": "tif", "WebP": "webp"}
        out = fp / f"{name}.{ext_map.get(fmt, 'jpg')}"

        long_txt = self._long_edge.text().strip()
        long_edge = int(long_txt) if long_txt.isdigit() else None

        import dataclasses
        settings = dataclasses.replace(
            self._settings,
            output_format=fmt,
            jpeg_quality=self._qual_slider.value(),
            export_long_edge=long_edge,
            output_sharpening=self._sharpen_toggle.is_checked(),
        )

        self._export_btn.setEnabled(False)
        self._cancel_btn.setEnabled(False)
        self._prog.setValue(0)
        self._prog.show()

        self._worker = ExportWorker(self._image, out, fmt,
                                    self._qual_slider.value(), settings)
        self._worker.progress.connect(self._prog.setValue)
        self._worker.finished.connect(self._done)
        self._worker.error.connect(self._err)
        self._worker.start()

    def _done(self, path: str) -> None:
        if self._worker:
            self._worker.deleteLater()
            self._worker = None
        QMessageBox.information(self, "完成", f"已儲存至：\n{path}")
        self.accept()

    def _err(self, msg: str) -> None:
        if self._worker:
            self._worker.deleteLater()
            self._worker = None
        QMessageBox.critical(self, "失敗", f"錯誤：{msg}")
        self._export_btn.setEnabled(True)
        self._cancel_btn.setEnabled(True)
        self._prog.hide()


# ── Small button helpers ──────────────────────────────────────────────────────

class _SmallBtn(QWidget):
    clicked = pyqtSignal()

    def __init__(self, label: str, parent=None):
        from PyQt6.QtWidgets import QPushButton
        super().__init__(parent)
        btn = QPushButton(label, self)
        btn.setFixedHeight(30)
        btn.setStyleSheet("""
            QPushButton {
                background: transparent; color: #BBBAC4;
                border: 1px solid #3E3E3E; border-radius: 6px;
                padding: 0 14px; font-size: 12px;
            }
            QPushButton:hover { background: #363636; color: #F2F0EA; }
            QPushButton:disabled { color: #484858; }
        """)
        btn.clicked.connect(self.clicked)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(btn)

    def setEnabled(self, v: bool) -> None:
        super().setEnabled(v)
        for child in self.children():
            if hasattr(child, "setEnabled"):
                child.setEnabled(v)


class _PrimaryBtn(QWidget):
    clicked = pyqtSignal()

    def __init__(self, label: str, parent=None):
        from PyQt6.QtWidgets import QPushButton
        super().__init__(parent)
        self._btn = QPushButton(label, self)
        self._btn.setFixedHeight(34)
        self._btn.setMinimumWidth(110)
        self._btn.setStyleSheet("""
            QPushButton {
                background: #C5A46A; color: #1A1A1A;
                border: none; border-radius: 7px;
                padding: 0 20px; font-size: 13px; font-weight: 700;
            }
            QPushButton:hover { background: #D4B87E; }
            QPushButton:disabled { background: #444444; color: #7A7888; }
        """)
        self._btn.clicked.connect(self.clicked)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self._btn)

    def setEnabled(self, v: bool) -> None:
        super().setEnabled(v)
        self._btn.setEnabled(v)


class _CloseBtn(QWidget):
    clicked = pyqtSignal()

    def __init__(self, parent=None):
        from PyQt6.QtWidgets import QPushButton
        super().__init__(parent)
        btn = QPushButton("✕", self)
        btn.setFixedSize(24, 24)
        btn.setStyleSheet("""
            QPushButton {
                background: transparent; color: #7A7888;
                border: none; font-size: 13px; border-radius: 4px;
            }
            QPushButton:hover { background: #363636; color: #F2F0EA; }
        """)
        btn.clicked.connect(self.clicked)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(btn)
