"""Export dialog — dark theme."""
from __future__ import annotations
from pathlib import Path
from typing import Optional

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar,
    QFileDialog, QLineEdit, QMessageBox, QFrame,
)
from PyQt6.QtCore import QThread, pyqtSignal

from PIL import Image

import src.gui.theme as T
from src.gui.widgets import AnimatedButton, GhostButton
from src.models.settings import BorderSettings


class ExportWorker(QThread):
    progress = pyqtSignal(int)
    finished = pyqtSignal(str)
    error    = pyqtSignal(str)

    def __init__(self, image: Image.Image, path: Path, fmt: str, quality: int, settings: BorderSettings):
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
            
            # Apply final LR-style processing (resize/sharpen)
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


class ExportDialog(QDialog):
    def __init__(
        self,
        image: Image.Image,
        settings,
        default_dir: Optional[Path] = None,
        parent=None,
    ):
        super().__init__(parent)
        self._image       = image
        self._settings    = settings
        self._default_dir = default_dir
        self._worker: Optional[ExportWorker] = None

        self.setWindowTitle("匯出照片")
        self.setMinimumWidth(440)
        self.setModal(True)
        self.setStyleSheet(f"""
            QDialog {{ background: {T.SURFACE}; }}
            QLabel {{ color: {T.TEXT_PRIMARY}; }}
        """)
        self._build()

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(T.S6, T.S6, T.S6, T.S6)
        root.setSpacing(T.S3)

        # Header
        title = QLabel("匯出照片")
        title.setStyleSheet(f"font-size: {T.FONT_XL}px; font-weight: 800; color: {T.TEXT_PRIMARY};")
        w, h = self._image.size
        fmt  = self._settings.output_format
        qual = f" · 品質 {self._settings.jpeg_quality}" if fmt == "JPEG" else ""
        sub  = QLabel(f"{w} × {h} px  ·  {fmt}{qual}")
        sub.setStyleSheet(f"font-size: {T.FONT_BASE}px; color: {T.TEXT_SECONDARY};")
        root.addWidget(title)
        root.addWidget(sub)

        div = QFrame(); div.setFrameShape(QFrame.Shape.HLine)
        div.setStyleSheet(f"color: {T.BORDER};")
        root.addWidget(div)

        # Folder
        root.addWidget(self._lbl("儲存資料夾"))
        row = QHBoxLayout(); row.setSpacing(T.S2)
        self._path = QLineEdit()
        self._path.setPlaceholderText("選擇資料夾…")
        self._path.setStyleSheet(self._inp())
        if self._default_dir:
            self._path.setText(str(self._default_dir))
        row.addWidget(self._path)
        b = GhostButton("瀏覽", font_size=T.FONT_SM, padding="6px 14px", bold=False)
        b.clicked.connect(self._browse)
        row.addWidget(b)
        root.addLayout(row)

        root.addWidget(self._lbl("檔案名稱"))
        self._name = QLineEdit("photo_bordered")
        self._name.setStyleSheet(self._inp())
        root.addWidget(self._name)

        root.addSpacing(T.S2)
        
        # Advanced Export Options
        root.addWidget(self._lbl("進階匯出設定 (LR 級別)"))
        
        adv_panel = QFrame()
        adv_panel.setStyleSheet(f"""
            QFrame {{
                background: {T.SURFACE_2};
                border: 1px solid {T.BORDER};
                border-radius: {T.R_CARD}px;
            }}
        """)
        adv_lay = QVBoxLayout(adv_panel)
        adv_lay.setContentsMargins(T.S4, T.S4, T.S4, T.S4)
        adv_lay.setSpacing(T.S3)

        # Resizing
        resize_row = QHBoxLayout()
        resize_row.addWidget(QLabel("限定長邊像素 (px)"))
        self._resize_edge = QLineEdit(str(self._settings.export_long_edge or ""))
        self._resize_edge.setPlaceholderText("不縮放…")
        self._resize_edge.setFixedWidth(100)
        self._resize_edge.setStyleSheet(self._inp())
        resize_row.addStretch()
        resize_row.addWidget(self._resize_edge)
        adv_lay.addLayout(resize_row)

        # Sharpening
        from PyQt6.QtWidgets import QCheckBox
        self._sharpen = QCheckBox("套用輸出銳化 (適合網頁)")
        self._sharpen.setChecked(self._settings.output_sharpening)
        self._sharpen.setStyleSheet(f"""
            QCheckBox {{
                color: {T.TEXT_PRIMARY}; font-size: {T.FONT_MD}px; spacing: 8px;
            }}
            QCheckBox::indicator {{
                width: 16px; height: 16px;
                border: 1.5px solid {T.BORDER_LIGHT};
                border-radius: 4px;
                background: {T.SURFACE_3};
            }}
            QCheckBox::indicator:checked {{
                background: {T.PRIMARY};
                border-color: {T.PRIMARY};
            }}
        """)
        adv_lay.addWidget(self._sharpen)

        root.addWidget(adv_panel)

        self._prog = QProgressBar()
        self._prog.setRange(0, 100)
        self._prog.setTextVisible(False)
        self._prog.setFixedHeight(4)
        self._prog.setStyleSheet(f"""
            QProgressBar {{ background: {T.BORDER}; border-radius: 2px; }}
            QProgressBar::chunk {{ background: {T.PRIMARY}; border-radius: 2px; }}
        """)
        self._prog.hide()
        root.addWidget(self._prog)

        root.addStretch()

        btn_row = QHBoxLayout(); btn_row.setSpacing(T.S2)
        self._cancel_btn = GhostButton("取消", font_size=T.FONT_MD, padding="9px 20px", bold=False)
        self._cancel_btn.clicked.connect(self.reject)
        self._export_btn = AnimatedButton("匯出", font_size=T.FONT_MD, padding="9px 28px")
        self._export_btn.setDefault(True)
        self._export_btn.clicked.connect(self._do)
        btn_row.addWidget(self._cancel_btn)
        btn_row.addStretch()
        btn_row.addWidget(self._export_btn)
        root.addLayout(btn_row)

    def _lbl(self, t: str) -> QLabel:
        l = QLabel(t)
        l.setStyleSheet(f"font-size: {T.FONT_BASE}px; font-weight: 500; color: {T.TEXT_SECONDARY};")
        return l

    def _inp(self) -> str:
        return f"""
            QLineEdit {{
                background: {T.SURFACE_2};
                border: 1px solid {T.BORDER};
                border-radius: {T.R_INPUT}px;
                padding: 8px 12px;
                font-size: {T.FONT_MD}px;
                color: {T.TEXT_PRIMARY};
            }}
            QLineEdit:focus {{
                border-color: {T.PRIMARY};
                background: {T.SURFACE};
            }}
            QLineEdit::placeholder {{
                color: {T.TEXT_MUTED};
            }}
        """

    def _browse(self) -> None:
        start = self._path.text().strip() or str(self._default_dir or "")
        f = QFileDialog.getExistingDirectory(self, "選擇資料夾", start)
        if f:
            self._path.setText(f)

    def _do(self) -> None:
        folder = self._path.text().strip()
        if not folder:
            QMessageBox.warning(self, "錯誤", "請選擇儲存路徑"); return
        fp = Path(folder)
        if not fp.exists():
            QMessageBox.warning(self, "錯誤", f"資料夾不存在：\n{folder}"); return

        name = self._name.text().strip() or "photo_bordered"
        ext  = "jpg" if self._settings.output_format == "JPEG" else "png"
        out  = fp / f"{name}.{ext}"

        self._export_btn.setEnabled(False)
        self._cancel_btn.setEnabled(False)
        self._prog.setValue(0); self._prog.show()

        import dataclasses
        self._worker = ExportWorker(
            self._image, 
            out, 
            self._settings.output_format, 
            self._settings.jpeg_quality,
            # Pass updated settings from UI
            dataclasses.replace(
                self._settings,
                export_long_edge=int(self._resize_edge.text()) if self._resize_edge.text().isdigit() else None,
                output_sharpening=self._sharpen.isChecked()
            )
        )
        self._worker.progress.connect(self._prog.setValue)
        self._worker.finished.connect(self._done)
        self._worker.error.connect(self._err)
        self._worker.start()

    def _done(self, path: str) -> None:
        if self._worker: self._worker.deleteLater(); self._worker = None
        QMessageBox.information(self, "完成", f"已儲存至：\n{path}")
        self.accept()

    def _err(self, msg: str) -> None:
        if self._worker: self._worker.deleteLater(); self._worker = None
        QMessageBox.critical(self, "失敗", f"錯誤：{msg}")
        self._export_btn.setEnabled(True); self._cancel_btn.setEnabled(True)
        self._prog.hide()
