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
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QCoreApplication, QTimer
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

_RASTER_EXTS = (".jpg", ".jpeg", ".png", ".tiff", ".tif", ".webp", ".bmp")

from src.core.raw_reader import RAW_EXTS, is_raw, decode as raw_decode, decode_preview as raw_preview
_RAW_EXTS = tuple(RAW_EXTS)
_EXTS     = _RASTER_EXTS + _RAW_EXTS

from src.models.grade_settings import GradeSettings
from src.core import color_grader
from src.gui.color_grade_panel import ColorGradePanel

from PyQt6.QtCore import QPoint, QPropertyAnimation, QEasingCurve, QParallelAnimationGroup


# ── Background workers ────────────────────────────────────────────────────────

class _RawDecodeWorker(QThread):
    """背景完整解碼 RAW 檔。"""
    result_ready = pyqtSignal(int, object)   # (idx, PIL.Image)
    error        = pyqtSignal(int, str)

    def __init__(self, idx: int, path):
        super().__init__()
        self._idx  = idx
        self._path = path

    def run(self) -> None:
        try:
            from src.core.raw_reader import decode as raw_decode
            img = raw_decode(self._path)
            self.result_ready.emit(self._idx, img)
        except Exception as e:
            self.error.emit(self._idx, str(e))


class GradeWorker(QThread):
    """步驟 1：套用調色，產出 graded PIL.Image。"""
    result_ready = pyqtSignal(int, object)   # (photo_idx, PIL.Image)
    error        = pyqtSignal(int, str)

    def __init__(self, photo_idx: int, photo: Photo, grade: GradeSettings):
        super().__init__()
        self._photo_idx = photo_idx
        self._photo     = photo
        self._grade     = grade
        self._cancel    = False

    def cancel(self) -> None:
        self._cancel = True

    def run(self) -> None:
        if self._cancel:
            return
        try:
            result = color_grader.apply(self._photo.image, self._grade)
            if not self._cancel:
                self.result_ready.emit(self._photo_idx, result)
        except Exception as e:
            if not self._cancel:
                self.error.emit(self._photo_idx, str(e))


class ProcessWorker(QThread):
    result_ready = pyqtSignal(int, object)   # (photo_idx, PIL.Image)
    error        = pyqtSignal(int, str)      # (photo_idx, msg)

    def __init__(self, photo_idx: int, photo: Photo,
                 settings: BorderSettings, graded_image=None):
        super().__init__()
        self._photo_idx    = photo_idx
        self._photo        = photo
        self._settings     = settings
        self._graded_image = graded_image   # 已調色的 PIL.Image（可為 None）
        self._cancel       = False

    def cancel(self) -> None:
        self._cancel = True

    def run(self) -> None:
        if self._cancel:
            return
        try:
            # 若有調色結果，用暫時 Photo 包裝後再加框
            if self._graded_image is not None:
                import dataclasses as _dc
                photo = _dc.replace(self._photo, image=self._graded_image)
            else:
                photo = self._photo
            result = image_processor.process(photo, self._settings)
            if not self._cancel:
                self.result_ready.emit(self._photo_idx, result)
        except Exception as e:
            if not self._cancel:
                self.error.emit(self._photo_idx, str(e))


# ── Sliding body ──────────────────────────────────────────────────────────────

class SlidingBody(QWidget):
    """兩個畫面水平滑動切換的容器，320ms InOutCubic。"""

    def __init__(self, screen1: QWidget, screen2: QWidget, parent=None):
        super().__init__(parent)
        self._s1 = screen1
        self._s2 = screen2
        self._current = 0
        self._animating = False
        screen1.setParent(self)
        screen2.setParent(self)

    def resizeEvent(self, e):
        W, H = self.width(), self.height()
        self._s1.setGeometry(0, 0, W, H)
        if self._current == 0:
            self._s2.setGeometry(W, 0, W, H)
        else:
            self._s2.setGeometry(0, 0, W, H)
            self._s1.setGeometry(-W, 0, W, H)

    def slide_to(self, idx: int) -> None:
        if idx == self._current or self._animating:
            return
        self._animating = True
        W = self.width()
        going_right = idx == 1

        if going_right:
            self._s2.setGeometry(W, 0, W, self.height())
        else:
            self._s1.setGeometry(-W, 0, W, self.height())
        self._s1.show()
        self._s2.show()

        out_widget = self._s1 if going_right else self._s2
        in_widget  = self._s2 if going_right else self._s1

        anim_out = QPropertyAnimation(out_widget, b"pos")
        anim_out.setDuration(320)
        anim_out.setEasingCurve(QEasingCurve.Type.InOutCubic)
        anim_out.setStartValue(QPoint(0, 0))
        anim_out.setEndValue(QPoint(-W if going_right else W, 0))

        anim_in = QPropertyAnimation(in_widget, b"pos")
        anim_in.setDuration(320)
        anim_in.setEasingCurve(QEasingCurve.Type.InOutCubic)
        anim_in.setStartValue(QPoint(W if going_right else -W, 0))
        anim_in.setEndValue(QPoint(0, 0))

        self._anim_group = QParallelAnimationGroup()
        self._anim_group.addAnimation(anim_out)
        self._anim_group.addAnimation(anim_in)

        def _done():
            self._current = idx
            self._animating = False
            self._s1.setVisible(idx == 0)
            self._s2.setVisible(idx == 1)

        self._anim_group.finished.connect(_done)
        self._anim_group.start()


# ── Main window ───────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PicLab")
        self.setMinimumSize(1100, 700)
        self.resize(1440, 860)

        self._tm      = ThemeManager.instance()
        self._photos: list[Photo]                       = []
        self._cur_idx                                   = -1
        self._processed_cache: dict[int, Image.Image]   = {}
        self._graded_cache:    dict[int, Image.Image]   = {}   # 調色後快取
        self._workers:         dict[int, ProcessWorker] = {}
        self._grade_workers:   dict[int, GradeWorker]   = {}
        # 防抖計時器：滑桿拖動時延遲 80ms 才觸發處理
        self._grade_debounce = QTimer()
        self._grade_debounce.setSingleShot(True)
        self._grade_debounce.setInterval(80)
        self._grade_debounce.timeout.connect(self._trigger_grade_processing)
        self._synced_indices:  set[int]                 = set()
        self._photo_settings:  dict[int, BorderSettings] = {}
        self._grade_settings:  dict[int, GradeSettings]  = {}  # 每張照片調色設定
        self._grade_history:   dict[int, list[GradeSettings]] = {}  # undo 堆疊（每張照片）
        self._grade_future:    dict[int, list[GradeSettings]] = {}  # redo 堆疊（每張照片）
        self._sync_all = False
        self._current_step = 1   # 1=調色, 2=加框
        self._before_mode  = False   # Before/After 切換

        self.setAcceptDrops(True)
        self._build_ui()
        self._build_menu()
        self._build_status()
        self._apply_window_style()
        self._tm.theme_changed.connect(self._on_theme_change)

    # ── Style ─────────────────────────────────────────────────────────────────

    def _apply_window_style(self) -> None:
        self.setStyleSheet(T.app_qss())

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
        self._top_bar.batch_export_requested.connect(self._on_batch_export)
        self._top_bar.sync_all_toggled.connect(self._on_sync_all_toggled)
        self._top_bar.step_changed.connect(self._on_step_changed)
        root.addWidget(self._top_bar)

        # ── 畫面 1：調色（左導覽 + 預覽 + 調色面板）──
        screen1 = QWidget()
        s1_lay = QHBoxLayout(screen1)
        s1_lay.setContentsMargins(0, 0, 0, 0)
        s1_lay.setSpacing(0)

        left_nav1 = LeftNavBar(mode="develop")
        left_nav1.section_requested.connect(self._on_develop_nav_section)
        s1_lay.addWidget(left_nav1)

        self._preview = PreviewPanel()
        self._preview.open_file_requested.connect(self._open_file)
        self._preview.photo_switched.connect(self._switch_photo)
        self._preview.sync_changed.connect(self._on_sync_changed)
        self._preview.delete_requested.connect(self._delete_photo)
        self._preview.split_crop_changed.connect(self._on_split_crop_changed)
        self._preview.split_zoom_changed.connect(self._on_split_zoom_changed)
        s1_lay.addWidget(self._preview, 1)

        self._preview.disable_safezone()   # 調色步驟不顯示安全區

        self._grade_panel = ColorGradePanel()
        self._grade_panel.grade_changed.connect(self._on_grade_changed)
        self._grade_panel.go_next.connect(lambda: self._on_step_changed(2))
        s1_lay.addWidget(self._grade_panel)

        # ── 畫面 2：加框（左導覽 + 預覽（共用） + 設定面板）──
        screen2 = QWidget()
        s2_lay = QHBoxLayout(screen2)
        s2_lay.setContentsMargins(0, 0, 0, 0)
        s2_lay.setSpacing(0)

        left_nav2 = LeftNavBar()
        left_nav2.section_requested.connect(self._on_nav_section)
        s2_lay.addWidget(left_nav2)

        self._preview2 = PreviewPanel()
        self._preview2.open_file_requested.connect(self._open_file)
        self._preview2.photo_switched.connect(self._switch_photo)
        self._preview2.sync_changed.connect(self._on_sync_changed)
        self._preview2.delete_requested.connect(self._delete_photo)
        self._preview2.split_crop_changed.connect(self._on_split_crop_changed)
        self._preview2.split_zoom_changed.connect(self._on_split_zoom_changed)
        s2_lay.addWidget(self._preview2, 1)

        self._settings = SettingsPanel()
        self._settings.settings_changed.connect(self._on_settings_changed)
        self._settings.export_button.clicked.connect(self._on_export)
        s2_lay.addWidget(self._settings)

        # ── 加入「返回調色」按鈕到加框面板 ──
        self._settings.add_back_button(lambda: self._on_step_changed(1))

        # ── SlidingBody ──
        self._slider = SlidingBody(screen1, screen2)
        root.addWidget(self._slider, 1)

    def _build_menu(self) -> None:
        mb = self.menuBar()
        self._mb = mb
        self._apply_menubar_style()

        fm = mb.addMenu("檔案")
        self._act(fm, "開啟照片…",  "Ctrl+O",       self._open_file)
        self._act(fm, "開啟資料夾…","Ctrl+Shift+O", self._open_folder)
        fm.addSeparator()
        self._act(fm, "匯出…",      "Ctrl+S",       self._on_export)
        self._act(fm, "發布到 Instagram…", "Ctrl+Shift+P", self._on_publish_ig)
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

    # ── Step switching ────────────────────────────────────────────────────────

    def _on_step_changed(self, step: int) -> None:
        self._reset_before_after()
        self._current_step = step
        self._top_bar.set_step(step)
        self._slider.slide_to(step - 1)
        if step == 1:
            self._sb.showMessage("步驟 1：調色 — 完成後按「下一步：加框」")
        else:
            self._sb.showMessage("步驟 2：加框 — 設定完成後按「匯出照片」")

    # ── Navigation ────────────────────────────────────────────────────────────

    def _on_develop_nav_section(self, section: str) -> None:
        """Develop 畫面的左側導覽：捲動到調色面板對應區段。"""
        if section.startswith("__open__"):
            self._on_nav_section(section)
        else:
            self._grade_panel.scroll_to_section(section)

    def _on_nav_section(self, section: str) -> None:
        if section == "__open__files":
            self._open_file()
        elif section == "__open__folder":
            self._open_folder()
        elif section == "__open__":   # 舊路徑相容
            self._open_file()
        else:
            self._settings.scroll_to_section(section)


    def _on_template_changed(self, style: TemplateStyle) -> None:
        self._settings.set_template(style)
        self._preview.set_template(style)
        if style == TemplateStyle.SPLIT and self._cur_idx >= 0:
            self._preview.set_split_photo(self._photos[self._cur_idx].image)
        self._trigger_processing()

    # ── File loading ──────────────────────────────────────────────────────────

    def _open_file(self) -> None:
        # 同時包含大小寫副檔名，確保 Linux 上能篩選到 .CR3 / .cr3
        raw_glob = " ".join(f"*{e} *{e.upper()}" for e in sorted(RAW_EXTS))
        raster_glob = "*.jpg *.JPG *.jpeg *.JPEG *.png *.PNG *.tiff *.TIFF *.tif *.TIF *.webp *.WEBP *.bmp *.BMP"
        paths, _ = QFileDialog.getOpenFileNames(
            self, "開啟照片", "",
            f"所有支援格式 ({raster_glob} {raw_glob});;"
            f"RAW 檔案 ({raw_glob});;"
            f"一般圖片 ({raster_glob})",
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
            if is_raw(path):
                # RAW：快速取縮圖作為 UI 預覽；完整解碼交給背景 worker
                img = raw_preview(path)
                # 標記這張照片需要完整 RAW 解碼
                _needs_full_decode = True
            else:
                img = ImageOps.exif_transpose(Image.open(path))
                img.load()
                _needs_full_decode = False

            exif    = read_exif(path)
            photo   = Photo(file_path=path, image=img, exif=exif)
            new_idx = len(self._photos)
            self._photos.append(photo)
            self._photo_settings[new_idx] = self._settings.current_settings()
            self._grade_settings[new_idx] = GradeSettings()
            self._preview.add_to_strip(img)
            self._preview2.add_to_strip(img)
            self._top_bar.enable_export(True)
            self._settings.enable_export(True)

            if _needs_full_decode:
                # 啟動背景完整解碼 worker
                self._start_raw_decode(new_idx, path)
            else:
                self._switch_photo(new_idx)

        except Exception as e:
            QMessageBox.critical(self, "載入失敗", f"無法開啟照片：\n{e}")

    def _start_raw_decode(self, idx: int, path: Path) -> None:
        """背景完整解碼 RAW 檔，完成後替換縮圖並切換到該照片。"""
        w = _RawDecodeWorker(idx, path)
        w.result_ready.connect(self._on_raw_decoded)
        w.error.connect(lambda i, msg: self._sb.showMessage(f"RAW 解碼失敗：{msg}"))
        # 借用 grade_workers 槽位管理
        self._grade_workers[idx] = w  # type: ignore[assignment]
        w.start()
        self._sb.showMessage(f"RAW 解碼中：{path.name}…")
        # 先切換到此照片（顯示縮圖），等完整解碼後替換
        self._switch_photo(idx)

    def _on_raw_decoded(self, idx: int, full_img) -> None:
        """RAW 完整解碼完成：替換照片圖片並重新處理。"""
        import dataclasses as _dc
        if idx >= len(self._photos):
            return
        old_photo = self._photos[idx]
        self._photos[idx] = _dc.replace(old_photo, image=full_img)
        # 清除舊快取
        self._graded_cache.pop(idx, None)
        self._processed_cache.pop(idx, None)
        # 更新縮圖列
        self._preview.update_strip_thumb(idx, full_img)
        self._preview2.update_strip_thumb(idx, full_img)
        if idx == self._cur_idx:
            self._preview.show_image(full_img)
            self._sb.showMessage(
                f"{old_photo.file_path.name}  ·  RAW 解碼完成  ·  "
                f"{full_img.width} × {full_img.height} px"
            )
            self._trigger_grade_processing()

    def _switch_photo(self, idx: int) -> None:
        if idx < 0 or idx >= len(self._photos):
            return
        self._reset_before_after()
        if self._cur_idx >= 0 and self._cur_idx != idx:
            self._photo_settings[self._cur_idx] = self._settings.current_settings()
            self._grade_settings[self._cur_idx] = self._grade_panel.current_settings()

        self._cur_idx = idx
        self._preview.set_strip_current(idx)
        self._preview2.set_strip_current(idx)
        p = self._photos[idx]

        # 還原加框設定
        if idx in self._photo_settings:
            s = self._photo_settings[idx]
            self._settings.restore_settings(s)
            self._top_bar.set_template(s.template)
            for pv in (self._preview, self._preview2):
                pv.set_aspect_ratio(s.aspect_ratio)
                pv.set_template(s.template)
                pv.set_split_crop(s.split_crop_x, s.split_crop_y)
                pv.set_split_zoom(s.split_zoom)
                if s.template == TemplateStyle.SPLIT:
                    pv.set_split_photo(p.image)

        # 還原調色設定
        if idx in self._grade_settings:
            self._grade_panel.restore_settings(self._grade_settings[idx])

        # 設定 Before/After 比較的原始圖（未調色）
        from src.gui.preview_panel import _pil_to_pixmap as _p2px
        self._preview.set_before(_p2px(p.image))

        # Step 1 預覽（顯示調色結果 or 原圖）
        if idx in self._graded_cache:
            self._preview.show_image(self._graded_cache[idx])
            self._grade_panel.update_histogram(self._graded_cache[idx])
        else:
            self._preview.show_image(p.image)
            self._grade_panel.update_histogram(p.image)
            self._trigger_grade_processing()
        self._grade_panel.update_exif(p.exif)

        # Step 2 預覽（加框結果）
        if idx in self._processed_cache:
            self._preview2.show_image(self._processed_cache[idx])
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

    def _on_grade_changed(self, grade: GradeSettings) -> None:
        """調色設定變更：保持舊預覽，用 debounce 延遲觸發處理。"""
        if self._cur_idx < 0:
            return
        idx = self._cur_idx
        # 推入 undo 歷史（限 50 項），清空 redo
        prev = self._grade_settings.get(idx, GradeSettings())
        history = self._grade_history.setdefault(idx, [])
        history.append(prev)
        if len(history) > 50:
            history.pop(0)
        self._grade_future[idx] = []
        self._grade_settings[idx] = grade
        self._graded_cache.pop(idx, None)
        self._processed_cache.pop(idx, None)
        # 用 debounce 延遲觸發，拖動時不會每幀都重算
        self._grade_debounce.start()

    def _trigger_grade_processing(self) -> None:
        """啟動調色 worker（步驟 1），完成後自動觸發加框。"""
        idx = self._cur_idx
        if idx < 0 or idx >= len(self._photos):
            return
        if idx in self._grade_workers and self._grade_workers[idx].isRunning():
            self._grade_workers[idx].cancel()
            self._grade_workers[idx].wait(200)

        grade = self._grade_settings.get(idx, GradeSettings())
        w = GradeWorker(idx, self._photos[idx], grade)
        w.result_ready.connect(self._on_grade_result)
        w.error.connect(self._on_photo_error)
        self._grade_workers[idx] = w
        w.start()

    def _on_grade_result(self, idx: int, graded: Image.Image) -> None:
        self._graded_cache[idx] = graded
        if idx == self._cur_idx:
            self._preview.stop_spinner()
            self._preview.show_image(graded)
            self._grade_panel.update_histogram(graded)
        # 調色完成後，清除加框快取並觸發加框
        self._processed_cache.pop(idx, None)
        if idx == self._cur_idx:
            self._trigger_processing()

    def _on_settings_changed(self, settings: BorderSettings) -> None:
        if self._cur_idx < 0:
            return
        if self._sync_all:
            for idx in range(len(self._photos)):
                self._photo_settings[idx] = settings
                self._processed_cache.pop(idx, None)
        else:
            self._photo_settings[self._cur_idx] = settings
        for pv in (self._preview, self._preview2):
            pv.set_aspect_ratio(settings.aspect_ratio)
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
        """步驟 2：加框處理（使用調色後的影像）。"""
        idx = self._cur_idx
        if idx < 0 or idx >= len(self._photos):
            return
        if idx in self._workers and self._workers[idx].isRunning():
            self._workers[idx].cancel()
            self._workers[idx].wait(200)

        settings    = self._photo_settings.get(idx, self._settings.current_settings())
        graded_img  = self._graded_cache.get(idx)   # 可能為 None（尚未調色）
        w = ProcessWorker(idx, self._photos[idx], settings, graded_image=graded_img)
        w.result_ready.connect(self._on_photo_result)
        w.error.connect(self._on_photo_error)
        self._workers[idx] = w
        w.start()
        self._preview2.start_spinner()
        self._sb.showMessage("加框處理中…")

    def _on_photo_result(self, idx: int, img: Image.Image) -> None:
        self._processed_cache[idx] = img
        if idx == self._cur_idx:
            self._preview2.stop_spinner()
            self._preview2.show_image(img)
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
        for w_dict in (self._workers, self._grade_workers):
            if idx in w_dict:
                w_dict[idx].cancel()
                del w_dict[idx]

        def _rekey(d: dict) -> dict:
            return {(k if k < idx else k - 1): v
                    for k, v in d.items() if k != idx}

        self._processed_cache = _rekey(self._processed_cache)
        self._graded_cache    = _rekey(self._graded_cache)
        self._photo_settings  = _rekey(self._photo_settings)
        self._grade_settings  = _rekey(self._grade_settings)
        self._workers         = _rekey(self._workers)
        self._grade_workers   = _rekey(self._grade_workers)

        self._synced_indices.discard(idx)
        self._synced_indices = {i if i < idx else i - 1 for i in self._synced_indices}

        try:
            self._photos[idx].image.close()
        except Exception:
            pass
        self._photos.pop(idx)
        self._preview.remove_from_strip(idx)
        self._preview2.remove_from_strip(idx)

        if not self._photos:
            self._cur_idx = -1
            self._top_bar.enable_export(False)
            self._settings.enable_export(False)
            self._preview.show_drop_zone()
            self._preview2.show_drop_zone()
            self._sb.showMessage("就緒")
        else:
            new_idx = min(idx, len(self._photos) - 1)
            if self._cur_idx == idx:
                self._cur_idx = new_idx
                self._switch_photo(self._cur_idx)
            elif self._cur_idx > idx:
                self._cur_idx -= 1
                if self._cur_idx in self._processed_cache:
                    self._preview.set_strip_current(self._cur_idx)
                    self._preview2.set_strip_current(self._cur_idx)
                    self._preview2.show_image(self._processed_cache[self._cur_idx])
                    if self._cur_idx in self._graded_cache:
                        self._preview.show_image(self._graded_cache[self._cur_idx])
                else:
                    self._switch_photo(self._cur_idx)
            else:
                self._preview.set_strip_current(self._cur_idx)
                self._preview2.set_strip_current(self._cur_idx)

    # ── Grade Undo / Redo ─────────────────────────────────────────────────────

    def _undo_grade(self) -> None:
        """復原上一個調色操作。"""
        if self._cur_idx < 0:
            return
        idx = self._cur_idx
        history = self._grade_history.get(idx, [])
        if not history:
            return
        # 把當前狀態推入 redo
        current = self._grade_settings.get(idx, GradeSettings())
        self._grade_future.setdefault(idx, []).append(current)
        # 從 history 取出上一個狀態
        grade = history.pop()
        self._grade_settings[idx] = grade
        self._graded_cache.pop(idx, None)
        self._processed_cache.pop(idx, None)
        self._grade_panel.restore_settings(grade)
        self.grade_changed_from_undo(grade)

    def _redo_grade(self) -> None:
        """重做已復原的調色操作。"""
        if self._cur_idx < 0:
            return
        idx = self._cur_idx
        future = self._grade_future.get(idx, [])
        if not future:
            return
        # 把當前狀態推回 history
        current = self._grade_settings.get(idx, GradeSettings())
        self._grade_history.setdefault(idx, []).append(current)
        # 取出 redo 狀態
        grade = future.pop()
        self._grade_settings[idx] = grade
        self._graded_cache.pop(idx, None)
        self._processed_cache.pop(idx, None)
        self._grade_panel.restore_settings(grade)
        self.grade_changed_from_undo(grade)

    def grade_changed_from_undo(self, grade: GradeSettings) -> None:
        """Undo/Redo 後觸發重新渲染（不再推入歷史）。"""
        self._grade_debounce.start()

    # ── Keyboard shortcuts ────────────────────────────────────────────────────

    def keyPressEvent(self, e) -> None:
        key  = e.key()
        mods = e.modifiers()

        # ← → 切換照片
        if key == Qt.Key.Key_Left and not mods:
            if self._cur_idx > 0:
                self._switch_photo(self._cur_idx - 1)
            return
        if key == Qt.Key.Key_Right and not mods:
            if self._cur_idx < len(self._photos) - 1:
                self._switch_photo(self._cur_idx + 1)
            return

        # B — Before/After 切換
        if key == Qt.Key.Key_B and not mods:
            self._toggle_before_after()
            return

        # Delete — 刪除當前照片
        if key == Qt.Key.Key_Delete and not mods:
            if self._cur_idx >= 0:
                self._delete_photo(self._cur_idx)
            return

        # Ctrl+Z — 復原調色
        if key == Qt.Key.Key_Z and (mods & Qt.KeyboardModifier.ControlModifier) \
                and not (mods & Qt.KeyboardModifier.ShiftModifier):
            self._undo_grade()
            return

        # Ctrl+Shift+Z / Ctrl+Y — 重做調色
        if (key == Qt.Key.Key_Z and (mods & Qt.KeyboardModifier.ControlModifier)
                and (mods & Qt.KeyboardModifier.ShiftModifier)):
            self._redo_grade()
            return
        if key == Qt.Key.Key_Y and (mods & Qt.KeyboardModifier.ControlModifier):
            self._redo_grade()
            return

        # Ctrl+\ — 切換 Before/After 比較模式
        if key == Qt.Key.Key_Backslash and (mods & Qt.KeyboardModifier.ControlModifier):
            self._preview.toggle_compare()
            return

        # Ctrl+E — 匯出
        if key == Qt.Key.Key_E and mods & Qt.KeyboardModifier.ControlModifier:
            self._on_export()
            return

        # Ctrl+Shift+E — 批次匯出
        if key == Qt.Key.Key_E and (mods & Qt.KeyboardModifier.ControlModifier) \
                and (mods & Qt.KeyboardModifier.ShiftModifier):
            self._on_batch_export()
            return

        super().keyPressEvent(e)

    # ── Before / After ────────────────────────────────────────────────────────

    def _toggle_before_after(self) -> None:
        if self._cur_idx < 0:
            return
        self._before_mode = not self._before_mode
        idx = self._cur_idx

        if self._current_step == 1:
            panel = self._preview
            if self._before_mode:
                panel.show_image(self._photos[idx].image)
                panel.show_before_after("BEFORE")
            else:
                img = self._graded_cache.get(idx, self._photos[idx].image)
                panel.show_image(img)
                panel.show_before_after("AFTER")
        else:
            panel = self._preview2
            if self._before_mode:
                img = self._graded_cache.get(idx, self._photos[idx].image)
                panel.show_image(img)
                panel.show_before_after("BEFORE")
            else:
                if idx in self._processed_cache:
                    panel.show_image(self._processed_cache[idx])
                panel.show_before_after("AFTER")

        mode_str = "按 B 返回 After" if self._before_mode else ""
        if mode_str:
            self._sb.showMessage(f"▶ Before 模式  ·  {mode_str}")

    def _reset_before_after(self) -> None:
        """切換照片或步驟時重置 before 模式。"""
        if self._before_mode:
            self._before_mode = False
            self._preview.show_before_after(None)
            self._preview2.show_before_after(None)

    # ── Batch Export ──────────────────────────────────────────────────────────

    def _on_batch_export(self) -> None:
        if not self._processed_cache:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.information(self, "提示", "請先載入並處理照片")
            return
        from src.gui.batch_export_dialog import BatchExportDialog
        d = self._photos[self._cur_idx].file_path.parent if self._photos else None
        BatchExportDialog(
            self._processed_cache,
            self._photos,
            self._photo_settings,
            self._settings.current_settings(),
            parent=self,
        ).exec()

    # ── Export ────────────────────────────────────────────────────────────────

    def _on_export(self) -> None:
        if self._cur_idx not in self._processed_cache:
            QMessageBox.information(self, "提示", "請先載入照片")
            return
        d = self._photos[self._cur_idx].file_path.parent if self._photos else None
        ExportDialog(self._processed_cache[self._cur_idx],
                     self._settings.current_settings(),
                     default_dir=d, parent=self).exec()

    def _on_publish_ig(self) -> None:
        if self._cur_idx not in self._processed_cache:
            QMessageBox.information(self, "提示", "請先載入照片並等待預覽完成")
            return
        import tempfile, os
        from src.gui.publish_dialog import PublishDialog
        pil_img = self._processed_cache[self._cur_idx]
        tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
        tmp.close()
        pil_img.save(tmp.name, "JPEG", quality=95)
        preview = self._preview.current_pixmap()
        try:
            PublishDialog(tmp.name, preview, parent=self).exec()
        finally:
            os.unlink(tmp.name)
