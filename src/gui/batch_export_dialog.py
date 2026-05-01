"""
BatchExportDialog — 批次匯出所有已處理照片。
"""
from __future__ import annotations
from pathlib import Path
from typing import Optional

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QProgressBar, QFileDialog, QFrame,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal

import src.gui.theme as T
from src.gui.widgets import AnimatedButton, GhostButton


def _tm():
    from src.gui.theme_manager import ThemeManager
    return ThemeManager.instance()


class _BatchWorker(QThread):
    progress = pyqtSignal(int, str)   # (current, filename)
    done     = pyqtSignal(int, int)   # (success, fail)

    def __init__(self, tasks: list, out_dir: Path, fmt: str,
                 quality: int, settings):
        super().__init__()
        self._tasks   = tasks   # list of (PIL.Image, stem_name, BorderSettings)
        self._out_dir = out_dir
        self._fmt     = fmt
        self._quality = quality
        self._settings = settings
        self._cancel  = False

    def cancel(self) -> None:
        self._cancel = True

    def run(self) -> None:
        from src.core.image_processor import finalize_export
        import dataclasses
        success = fail = 0
        ext = ".jpg" if self._fmt == "JPEG" else ".png"
        for i, (img, name, per_settings) in enumerate(self._tasks):
            if self._cancel:
                break
            self.progress.emit(i + 1, name)
            try:
                s = dataclasses.replace(
                    per_settings,
                    output_format  = self._fmt,
                    jpeg_quality   = self._quality,
                )
                processed = finalize_export(img, s)
                out_path  = self._out_dir / (name + ext)
                n = 1
                while out_path.exists():
                    out_path = self._out_dir / (f"{name}_{n}" + ext)
                    n += 1
                kw = {"quality": self._quality, "optimize": True,
                      "subsampling": 0} if self._fmt == "JPEG" else {}
                final = processed.convert("RGB") if self._fmt == "JPEG" else processed
                final.save(str(out_path), format=self._fmt, **kw)
                success += 1
            except Exception:
                fail += 1
        self.done.emit(success, fail)


class BatchExportDialog(QDialog):
    def __init__(self, processed_cache: dict, photos: list,
                 photo_settings: dict, current_settings,
                 parent=None):
        super().__init__(parent)
        self._cache          = processed_cache   # {idx: PIL.Image}
        self._photos         = photos
        self._photo_settings = photo_settings    # {idx: BorderSettings}
        self._settings       = current_settings
        self._out_dir: Optional[Path] = None
        self._worker: Optional[_BatchWorker] = None

        self.setWindowTitle("批次匯出")
        self.setMinimumWidth(460)
        self.setModal(True)
        self._build()
        self._apply_style()
        _tm().theme_changed.connect(lambda _: self._apply_style())

    def _build(self) -> None:
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 22, 24, 22)
        lay.setSpacing(14)

        n = len(self._cache)
        title = QLabel(f"批次匯出  ·  共 {n} 張照片")
        title.setStyleSheet(
            f"font-size: {T.FONT_LG}px; font-weight: 800; "
            f"color: {T.TEXT_PRIMARY}; background: transparent;"
        )
        lay.addWidget(title)

        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {T.BORDER};")
        lay.addWidget(sep)

        # 格式提示
        fmt   = self._settings.output_format
        qual  = f"  ·  品質 {self._settings.jpeg_quality}" if fmt == "JPEG" else ""
        info  = QLabel(f"格式：{fmt}{qual}  ·  依各張照片獨立設定匯出")
        info.setStyleSheet(
            f"color: {T.TEXT_SECONDARY}; font-size: {T.FONT_SM}px; background: transparent;"
        )
        lay.addWidget(info)

        # 輸出資料夾
        dir_row = QHBoxLayout()
        dir_row.setSpacing(8)
        self._dir_lbl = QLabel("尚未選擇輸出資料夾")
        self._dir_lbl.setStyleSheet(
            f"color: {T.TEXT_MUTED}; font-size: {T.FONT_SM}px; background: transparent;"
        )
        self._dir_lbl.setWordWrap(True)
        dir_btn = GhostButton("選擇資料夾…", font_size=T.FONT_SM,
                              padding="6px 12px", bold=False)
        dir_btn.clicked.connect(self._pick_dir)
        dir_row.addWidget(self._dir_lbl, 1)
        dir_row.addWidget(dir_btn, 0)
        lay.addLayout(dir_row)

        # 進度條
        self._prog = QProgressBar()
        self._prog.setRange(0, max(1, n))
        self._prog.setValue(0)
        self._prog.setTextVisible(False)
        self._prog.setFixedHeight(8)
        self._prog.hide()
        lay.addWidget(self._prog)

        self._status = QLabel("")
        self._status.setStyleSheet(
            f"color: {T.TEXT_MUTED}; font-size: {T.FONT_SM}px; background: transparent;"
        )
        self._status.hide()
        lay.addWidget(self._status)

        lay.addStretch()

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        btn_row.addStretch()
        self._close_btn = GhostButton("取消", font_size=T.FONT_MD,
                                      padding="9px 20px", bold=False)
        self._close_btn.clicked.connect(self._on_close)
        self._export_btn = AnimatedButton("開始匯出",
                                          font_size=T.FONT_MD, padding="9px 28px")
        self._export_btn.setEnabled(False)
        self._export_btn.clicked.connect(self._on_export)
        btn_row.addWidget(self._close_btn)
        btn_row.addWidget(self._export_btn)
        lay.addLayout(btn_row)

    def _apply_style(self) -> None:
        self.setStyleSheet(f"""
            QDialog {{ background: {T.SURFACE}; }}
            QProgressBar {{
                background: {T.SURFACE_3}; border: none; border-radius: 4px;
            }}
            QProgressBar::chunk {{
                background: {T.PRIMARY}; border-radius: 4px;
            }}
        """)

    def _pick_dir(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "選擇輸出資料夾")
        if d:
            self._out_dir = Path(d)
            short = str(self._out_dir)
            self._dir_lbl.setText(short)
            self._dir_lbl.setStyleSheet(
                f"color: {T.TEXT_PRIMARY}; font-size: {T.FONT_SM}px; background: transparent;"
            )
            self._export_btn.setEnabled(True)

    def _on_export(self) -> None:
        if not self._out_dir:
            return
        tasks = [
            (
                self._cache[idx],
                self._photos[idx].file_path.stem,
                self._photo_settings.get(idx, self._settings),
            )
            for idx in sorted(self._cache.keys())
            if idx < len(self._photos)
        ]
        self._worker = _BatchWorker(
            tasks, self._out_dir,
            self._settings.output_format,
            self._settings.jpeg_quality,
            self._settings,
        )
        self._worker.progress.connect(self._on_progress)
        self._worker.done.connect(self._on_done)
        self._export_btn.setEnabled(False)
        total = len(tasks)
        self._prog.setRange(0, max(1, total))
        self._prog.setValue(0)
        self._prog.show()
        self._status.show()
        self._worker.start()

    def _on_progress(self, n: int, name: str) -> None:
        self._prog.setValue(n)
        self._status.setText(
            f"正在匯出：{name}  ({n} / {self._prog.maximum()})"
        )

    def _on_done(self, success: int, fail: int) -> None:
        self._prog.setValue(self._prog.maximum())
        if fail:
            self._status.setText(f"完成：{success} 張成功，{fail} 張失敗")
        else:
            self._status.setText(f"全部完成！共 {success} 張  ✓")
        self._close_btn.setText("關閉")
        self._export_btn.setEnabled(False)

    def _on_close(self) -> None:
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            self._worker.wait(500)
        self.reject()

    def closeEvent(self, e) -> None:
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            self._worker.wait(500)
        super().closeEvent(e)
