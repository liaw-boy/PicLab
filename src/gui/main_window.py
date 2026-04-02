"""
Main window — 全新版面佈局。

Layout:
  TopBar (48px)  — 模板切換 + 主題 + 快速匯出
  ─────────────────────────────────────────
  LeftNavBar (56px) │ PreviewPanel │ SettingsPanel (360px)
  ─────────────────────────────────────────
  StatusBar (28px, built-in)
"""
from __future__ import annotations
from pathlib import Path
from typing import Optional

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QFileDialog, QMessageBox, QProgressBar, QLabel,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QCoreApplication
from PyQt6.QtGui import QAction, QDragEnterEvent, QDropEvent

from PIL import Image, ImageOps

import src.gui.theme as T
from src.gui.theme_manager import ThemeManager
from src.gui.top_bar import TopBar
from src.gui.left_nav import LeftNavBar
from src.gui.preview_panel import PreviewPanel
from src.gui.settings_panel import SettingsPanel
from src.gui.export_dialog import ExportDialog
import dataclasses

from src.models.photo import Photo
from src.models.settings import BorderSettings, TemplateStyle
from src.core.exif_reader import read_exif
from src.core import image_processor

_EXTS = (".jpg", ".jpeg", ".png", ".tiff", ".tif", ".webp", ".bmp")


# ── Background processor ──────────────────────────────────────────────────────

class ProcessWorker(QThread):
    result_ready = pyqtSignal(int, object)   # (photo_idx, PIL.Image)
    error        = pyqtSignal(int, str)      # (photo_idx, msg)

    def __init__(self, photo_idx: int, photo: Photo, settings: BorderSettings):
        super().__init__()
        self._photo_idx = photo_idx
        self._photo    = photo
        self._settings = settings
        self._cancel   = False

    def cancel(self) -> None:
        self._cancel = True

    def run(self) -> None:
        if self._cancel:
            return
        try:
            result = image_processor.process(self._photo, self._settings)
            if not self._cancel:
                self.result_ready.emit(self._photo_idx, result)
        except Exception as e:
            if not self._cancel:
                self.error.emit(self._photo_idx, str(e))


# ── Main window ───────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PicLab")
        self.setMinimumSize(1100, 700)
        self.resize(1440, 860)

        self._tm      = ThemeManager.instance()
        self._photos: list[Photo]                      = []
        self._cur_idx                                  = -1
        self._processed_cache: dict[int, Image.Image]  = {}
        self._workers: dict[int, ProcessWorker]        = {}
        self._synced_indices: set[int]                 = set()
        self._photo_settings: dict[int, BorderSettings] = {}   # 每張照片的獨立設定
        self._sync_all = False   # 同步所有圖片設定開關

        self.setAcceptDrops(True)
        self._build_ui()
        self._build_menu()
        self._build_status()
        self._apply_window_style()
        self._tm.theme_changed.connect(self._on_theme_change)

    # ── Style ─────────────────────────────────────────────────────────────────

    def _apply_window_style(self) -> None:
        self.setStyleSheet(f"QMainWindow {{ background: {T.BG}; }}")

    def _on_theme_change(self, dark: bool) -> None:
        self._apply_window_style()
        self._apply_menubar_style()
        self._apply_status_style()

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)

        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── TopBar ──
        self._top_bar = TopBar()
        self._top_bar.template_changed.connect(self._on_template_changed)
        self._top_bar.export_requested.connect(self._on_export)
        self._top_bar.sync_all_toggled.connect(self._on_sync_all_toggled)
        root.addWidget(self._top_bar)

        # ── Body ──
        body = QWidget()
        body_lay = QHBoxLayout(body)
        body_lay.setContentsMargins(0, 0, 0, 0)
        body_lay.setSpacing(0)

        # Left nav
        self._left_nav = LeftNavBar()
        self._left_nav.section_requested.connect(self._on_nav_section)
        body_lay.addWidget(self._left_nav)

        # Preview panel
        self._preview = PreviewPanel()
        self._preview.open_file_requested.connect(self._open_file)
        self._preview.photo_switched.connect(self._switch_photo)
        self._preview.sync_changed.connect(self._on_sync_changed)
        self._preview.delete_requested.connect(self._delete_photo)
        self._preview.split_crop_changed.connect(self._on_split_crop_changed)
        self._preview.split_zoom_changed.connect(self._on_split_zoom_changed)
        body_lay.addWidget(self._preview, 1)

        # Settings panel
        self._settings = SettingsPanel()
        self._settings.settings_changed.connect(self._on_settings_changed)
        self._settings.export_button.clicked.connect(self._on_export)
        body_lay.addWidget(self._settings)

        root.addWidget(body, 1)

    def _build_menu(self) -> None:
        mb = self.menuBar()
        self._mb = mb
        self._apply_menubar_style()

        fm = mb.addMenu("檔案")
        self._act(fm, "開啟照片…",  "Ctrl+O",       self._open_file)
        self._act(fm, "開啟資料夾…","Ctrl+Shift+O", self._open_folder)
        fm.addSeparator()
        self._act(fm, "匯出…",      "Ctrl+S",       self._on_export)
        fm.addSeparator()
        self._act(fm, "結束",       "Ctrl+Q",       self.close)

    def _apply_menubar_style(self) -> None:
        self._mb.setStyleSheet(f"""
            QMenuBar {{
                background: {T.MENUBAR};
                color: {T.TEXT_PRIMARY};
                font-size: {T.FONT_BASE}px;
                border-bottom: none;
                padding: 0;
                max-height: 0px;
            }}
            QMenuBar::item {{ padding: 5px 10px; border-radius: 4px; }}
            QMenuBar::item:selected {{ background: {T.SURFACE_2}; }}
            QMenu {{
                background: {T.SURFACE};
                border: 1px solid {T.BORDER};
                border-radius: {T.R_CARD}px;
                padding: 4px;
                color: {T.TEXT_PRIMARY};
            }}
            QMenu::item {{ padding: 7px 20px; border-radius: 5px; }}
            QMenu::item:selected {{ background: {T.SURFACE_2}; }}
            QMenu::separator {{ height: 1px; background: {T.BORDER}; margin: 4px 10px; }}
        """)

    def _act(self, menu, label: str, shortcut: str, slot,
             checkable: bool = False, checked: bool = False) -> QAction:
        a = QAction(label, self)
        if shortcut:
            a.setShortcut(shortcut)
        a.setCheckable(checkable)
        a.setChecked(checked)
        a.triggered.connect(slot)
        menu.addAction(a)
        return a

    def _build_status(self) -> None:
        self._sb = self.statusBar()
        self._apply_status_style()
        self._sb.showMessage("拖放照片或使用「開啟照片」載入")

        # 匯入進度條（平時隱藏）
        self._import_lbl = QLabel()
        self._import_lbl.setStyleSheet(
            f"color: {T.TEXT_SECONDARY}; font-size: {T.FONT_SM}px; "
            f"background: transparent; padding: 0 8px;"
        )
        self._import_bar = QProgressBar()
        self._import_bar.setFixedSize(160, 10)
        self._import_bar.setTextVisible(False)
        self._import_bar.setStyleSheet(f"""
            QProgressBar {{
                background: {T.SURFACE_3};
                border: none;
                border-radius: 5px;
            }}
            QProgressBar::chunk {{
                background: {T.PRIMARY};
                border-radius: 5px;
            }}
        """)
        self._sb.addPermanentWidget(self._import_lbl)
        self._sb.addPermanentWidget(self._import_bar)
        self._import_lbl.hide()
        self._import_bar.hide()

    def _apply_status_style(self) -> None:
        self._sb.setStyleSheet(f"""
            QStatusBar {{
                background: {T.MENUBAR};
                color: {T.TEXT_SECONDARY};
                font-size: {T.FONT_SM}px;
                border-top: 1px solid {T.BORDER};
                padding: 0 {T.S4}px;
            }}
        """)

    # ── Navigation ────────────────────────────────────────────────────────────

    def _on_nav_section(self, section: str) -> None:
        if section == "__open__files":
            self._open_file()
        elif section == "__open__folder":
            self._open_folder()
        elif section == "__open__":   # 舊路徑相容
            self._open_file()
        else:
            self._settings.scroll_to_section(section)
            self._left_nav.set_active_section(section)

    def _on_template_changed(self, style: TemplateStyle) -> None:
        self._settings.set_template(style)
        self._preview.set_template(style)
        if style == TemplateStyle.SPLIT and self._cur_idx >= 0:
            self._preview.set_split_photo(self._photos[self._cur_idx].image)
        self._trigger_processing()

    # ── File loading ──────────────────────────────────────────────────────────

    def _open_file(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self, "開啟照片", "",
            "圖片 (*.jpg *.jpeg *.png *.tiff *.tif *.webp *.bmp)",
        )
        if paths:
            self._load_photos([Path(p) for p in paths])

    def _open_multiple(self) -> None:
        self._open_file()

    def _open_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "選擇資料夾")
        if not folder:
            return
        paths = sorted(
            p for p in Path(folder).iterdir()
            if p.suffix.lower() in _EXTS
        )
        if not paths:
            QMessageBox.information(self, "無照片", "該資料夾內找不到支援的圖片檔案。")
            return
        self._load_photos(paths)

    def _load_photos(self, paths: list[Path]) -> None:
        """批次載入照片，顯示進度條。"""
        total = len(paths)
        if total == 0:
            return

        self._import_bar.setRange(0, total)
        self._import_bar.setValue(0)
        self._import_lbl.setText(f"匯入 0 / {total}")
        self._import_bar.show()
        self._import_lbl.show()

        failed = 0
        for i, p in enumerate(paths, 1):
            self._import_lbl.setText(f"匯入 {i} / {total}")
            self._import_bar.setValue(i)
            QCoreApplication.processEvents()
            try:
                self._load_photo(p)
            except Exception:
                failed += 1

        self._import_bar.hide()
        self._import_lbl.hide()

        if failed:
            self._sb.showMessage(f"完成，{total - failed} 張載入成功，{failed} 張失敗")
        else:
            self._sb.showMessage(f"已載入 {total} 張照片")

    def _load_photo(self, path: Path) -> None:
        try:
            img  = ImageOps.exif_transpose(Image.open(path))
            img.load()
            exif = read_exif(path)
            photo = Photo(file_path=path, image=img, exif=exif)
            new_idx = len(self._photos)
            self._photos.append(photo)
            # 新照片繼承當前面板設定作為初始值
            self._photo_settings[new_idx] = self._settings.current_settings()
            self._preview.add_to_strip(img)
            self._top_bar.enable_export(True)
            self._settings.enable_export(True)
            self._switch_photo(new_idx)
        except Exception as e:
            QMessageBox.critical(self, "載入失敗", f"無法開啟照片：\n{e}")

    def _switch_photo(self, idx: int) -> None:
        if idx < 0 or idx >= len(self._photos):
            return
        # 離開前儲存當前照片的設定
        if self._cur_idx >= 0 and self._cur_idx != idx:
            self._photo_settings[self._cur_idx] = self._settings.current_settings()

        self._cur_idx = idx
        self._preview.set_strip_current(idx)
        p = self._photos[idx]

        # 還原該照片的設定到面板
        if idx in self._photo_settings:
            s = self._photo_settings[idx]
            self._settings.restore_settings(s)
            self._top_bar.set_template(s.template)
            self._preview.set_aspect_ratio(s.aspect_ratio)
            self._preview.set_template(s.template)
            self._preview.set_split_crop(s.split_crop_x, s.split_crop_y)
            self._preview.set_split_zoom(s.split_zoom)
            if s.template == TemplateStyle.SPLIT:
                self._preview.set_split_photo(p.image)
        # 有快取就直接顯示，不重新處理
        if idx in self._processed_cache:
            self._preview.show_image(self._processed_cache[idx])
            w, h = self._processed_cache[idx].size
            self._sb.showMessage(f"{p.file_path.name}  ·  輸出 {w} × {h} px  ·  就緒")
        else:
            self._sb.showMessage(
                f"{p.file_path.name}  ·  {p.image.width} × {p.image.height} px"
            )
            self._trigger_processing()

    # ── Drag & Drop ───────────────────────────────────────────────────────────

    def dragEnterEvent(self, e: QDragEnterEvent) -> None:
        if e.mimeData().hasUrls():
            if any(u.toLocalFile().lower().endswith(_EXTS) for u in e.mimeData().urls()):
                self._preview.set_drag_highlight(True)
                e.acceptProposedAction()

    def dragLeaveEvent(self, e) -> None:
        self._preview.set_drag_highlight(False)

    def dropEvent(self, e: QDropEvent) -> None:
        self._preview.set_drag_highlight(False)
        paths = [
            Path(u.toLocalFile()) for u in e.mimeData().urls()
            if u.toLocalFile().lower().endswith(_EXTS)
        ]
        if paths:
            self._load_photos(paths)

    # ── Processing ────────────────────────────────────────────────────────────

    def _on_split_crop_changed(self, cx: float, cy: float) -> None:
        """SPLIT 版型拖曳裁切位置更新。"""
        if self._cur_idx < 0:
            return
        old = self._photo_settings.get(self._cur_idx, self._settings.current_settings())
        new_s = dataclasses.replace(old, split_crop_x=cx, split_crop_y=cy)
        self._photo_settings[self._cur_idx] = new_s
        # 同步模式下推給所有照片
        if self._sync_all:
            for idx in range(len(self._photos)):
                self._photo_settings[idx] = dataclasses.replace(
                    self._photo_settings.get(idx, new_s), split_crop_x=cx, split_crop_y=cy
                )
                self._processed_cache.pop(idx, None)
        else:
            self._processed_cache.pop(self._cur_idx, None)
        self._trigger_processing()

    def _on_split_zoom_changed(self, zoom: float) -> None:
        """SPLIT 版型滾輪縮放更新。"""
        if self._cur_idx < 0:
            return
        old = self._photo_settings.get(self._cur_idx, self._settings.current_settings())
        new_s = dataclasses.replace(old, split_zoom=zoom)
        self._photo_settings[self._cur_idx] = new_s
        if self._sync_all:
            for idx in range(len(self._photos)):
                self._photo_settings[idx] = dataclasses.replace(
                    self._photo_settings.get(idx, new_s), split_zoom=zoom
                )
                self._processed_cache.pop(idx, None)
        else:
            self._processed_cache.pop(self._cur_idx, None)
        self._trigger_processing()

    def _on_settings_changed(self, settings: BorderSettings) -> None:
        if self._cur_idx < 0:
            return
        if self._sync_all:
            # 同步模式：所有照片套用相同設定，清除所有快取強制重新處理
            for idx in range(len(self._photos)):
                self._photo_settings[idx] = settings
                self._processed_cache.pop(idx, None)
        else:
            self._photo_settings[self._cur_idx] = settings
        self._preview.set_aspect_ratio(settings.aspect_ratio)
        self._trigger_processing()

    def _on_sync_all_toggled(self, on: bool) -> None:
        self._sync_all = on
        if on and self._cur_idx >= 0:
            # 開啟時立即把當前設定推給所有照片
            settings = self._settings.current_settings()
            for idx in range(len(self._photos)):
                self._photo_settings[idx] = settings
                self._processed_cache.pop(idx, None)
            self._sb.showMessage("同步設定已開啟 — 所有照片將使用相同設定")

    def _trigger_processing(self) -> None:
        """只處理當前照片，不影響其他照片。"""
        idx = self._cur_idx
        if idx < 0 or idx >= len(self._photos):
            return
        if idx in self._workers and self._workers[idx].isRunning():
            self._workers[idx].cancel()
            self._workers[idx].wait(200)

        # 優先使用 _photo_settings（含 split_crop 等面板外更新）
        settings = self._photo_settings.get(idx, self._settings.current_settings())
        w = ProcessWorker(idx, self._photos[idx], settings)
        w.result_ready.connect(self._on_photo_result)
        w.error.connect(self._on_photo_error)
        self._workers[idx] = w
        w.start()
        self._preview.start_spinner()
        self._sb.showMessage("處理中…")

    def _on_photo_result(self, idx: int, img: Image.Image) -> None:
        self._processed_cache[idx] = img
        if idx == self._cur_idx:
            self._preview.stop_spinner()
            self._preview.show_image(img)
            w, h  = img.size
            fname = self._photos[idx].file_path.name
            n_sync = len(self._synced_indices)
            sync_info = f"  ·  同步 {n_sync} 張" if n_sync else ""
            self._sb.showMessage(f"{fname}  ·  輸出 {w} × {h} px  ·  就緒{sync_info}")

    def _on_photo_error(self, idx: int, msg: str) -> None:
        if idx == self._cur_idx:
            self._preview.stop_spinner()
            self._sb.showMessage(f"失敗：{msg}")
            QMessageBox.warning(self, "處理錯誤", msg)

    def _on_sync_changed(self, synced: object) -> None:
        """更新同步群組清單，不觸發任何處理（同步僅在匯出時生效）。"""
        self._synced_indices = set(synced)
        n = len(self._synced_indices)
        if n:
            self._sb.showMessage(f"同步群組：{n} 張  ·  匯出時將一併套用相同設定")
    def _delete_photo(self, idx: int) -> None:
        if idx < 0 or idx >= len(self._photos):
            return
        # 取消 worker
        if idx in self._workers:
            self._workers[idx].cancel()
            del self._workers[idx]
        # 重新編號 workers、cache、photo_settings（idx 之後的 key 全部 -1）
        self._processed_cache = {
            (k if k < idx else k - 1): v
            for k, v in self._processed_cache.items() if k != idx
        }
        self._photo_settings = {
            (k if k < idx else k - 1): v
            for k, v in self._photo_settings.items() if k != idx
        }
        self._workers = {
            (k if k < idx else k - 1): v
            for k, v in self._workers.items()
        }
        # 更新同步集合
        self._synced_indices.discard(idx)
        self._synced_indices = {i if i < idx else i - 1 for i in self._synced_indices}
        # 關閉 PIL 圖片並移除
        try:
            self._photos[idx].image.close()
        except Exception:
            pass
        self._photos.pop(idx)
        self._preview.remove_from_strip(idx)

        if not self._photos:
            self._cur_idx = -1
            self._top_bar.enable_export(False)
            self._settings.enable_export(False)
            self._preview.show_drop_zone()
            self._sb.showMessage("就緒")
        else:
            new_idx = min(idx, len(self._photos) - 1)
            if self._cur_idx == idx:
                self._cur_idx = new_idx
                self._switch_photo(self._cur_idx)
            elif self._cur_idx > idx:
                self._cur_idx -= 1
                # 切換後用快取避免重複處理
                if self._cur_idx in self._processed_cache:
                    self._preview.set_strip_current(self._cur_idx)
                    self._preview.show_image(self._processed_cache[self._cur_idx])
                else:
                    self._switch_photo(self._cur_idx)
            else:
                self._preview.set_strip_current(self._cur_idx)

    # ── Export ────────────────────────────────────────────────────────────────

    def _on_export(self) -> None:
        if self._cur_idx not in self._processed_cache:
            QMessageBox.information(self, "提示", "請先載入照片")
            return
        d = self._photos[self._cur_idx].file_path.parent if self._photos else None
        ExportDialog(self._processed_cache[self._cur_idx],
                     self._settings.current_settings(),
                     default_dir=d, parent=self).exec()
