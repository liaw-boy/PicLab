"""
PyBridge — JS↔Python bridge exposed via QWebChannel.

底層邏輯：JS 端的每個 slider/按鈕只調用一個入口，Python 端統一收斂處理。
顆粒度：所有 setter 都是「設定欄位 → 觸發重新渲染 → 透過 signal 把 base64 preview 推回 JS」。

API surface (callable from JavaScript):
    setGradeParam(name: str, value)        # int|float|bool
    loadImage(path: str) -> str            # absolute path; returns "ok" or error
    requestPreview() -> None               # async; preview emitted via previewReady signal
    listLuts() -> list[dict]
    listFilmRecipes() -> list[dict]
    exportImage(path: str, format: str, quality: int) -> str
    resetGrade() -> None

Signals (received by JavaScript):
    previewReady(str)   # data URL "data:image/jpeg;base64,..."
    histogramReady(str) # JSON of {r:[...], g:[...], b:[...]}
    statusChanged(str)  # human-readable status for footer
"""
from __future__ import annotations

import base64
import dataclasses
import io
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any


def _expand_filename_template(template: str, *, idx: int, stem: str, ext: str) -> str:
    """LR-style filename token expansion. {name} {seq} {date} {datetime} {ext} {fmt}."""
    from datetime import datetime
    now = datetime.now()
    out = (template or "{name}_graded")
    out = (out
           .replace("{name}", stem)
           .replace("{seq}", f"{idx:03d}")
           .replace("{date}", now.strftime("%Y-%m-%d"))
           .replace("{datetime}", now.strftime("%Y%m%d-%H%M%S"))
           .replace("{fmt}", ext.lower()))
    if "{ext}" in out:
        out = out.replace("{ext}", ext)
    else:
        out = f"{out}.{ext}"
    return out


def _resolve_collision(target: "Path", policy: str) -> "Path | None":
    """policy: 'overwrite' | 'skip' | 'increment'. Returns target path or None to skip."""
    if not target.exists() or policy == "overwrite":
        return target
    if policy == "skip":
        return None
    # increment
    n = 1
    while True:
        cand = target.with_name(f"{target.stem}-{n}{target.suffix}")
        if not cand.exists():
            return cand
        n += 1
        if n > 9999:
            return target  # give up, overwrite


def _batch_worker(args: tuple) -> tuple[bool, str]:
    """Module-level worker for multiprocessing.Pool — must be picklable.

    Each worker process imports the pipeline once and applies it to one image.
    Optionally runs Auto Tone per image before applying the master settings.
    Honors filename template + collision policy.
    """
    (path, settings, fmt, quality, ext, out_dir,
     filename_template, collision, auto_tone_per_image, idx) = args
    try:
        from PIL import Image as _Image
        from src.core import color_grader as _cg, raw_reader as _rr
        p = Path(path)
        if _rr.is_raw(p):
            img = _rr.decode(p).convert("RGB")
        else:
            img = _Image.open(p).convert("RGB")

        # Optional per-image auto tone — overwrites tonal fields with histogram-based deltas
        if auto_tone_per_image:
            from src.core import auto_tone as _at
            settings = _at.apply(settings, img)

        graded = _cg.apply(img, settings)

        target_dir = Path(out_dir) if out_dir else p.parent
        target_dir.mkdir(parents=True, exist_ok=True)
        target_name = _expand_filename_template(
            filename_template, idx=idx, stem=p.stem, ext=ext,
        )
        target = target_dir / target_name
        resolved = _resolve_collision(target, collision)
        if resolved is None:
            return (True, f"SKIP: {target}")  # treated as success, skipped
        kw: dict = {}
        if fmt == "JPEG":
            kw.update(quality=quality, optimize=True, progressive=True)
            graded = graded.convert("RGB")
        elif fmt == "WEBP":
            kw.update(quality=quality, method=6)
        elif fmt == "TIFF":
            kw.update(compression="tiff_lzw")
        graded.save(resolved, format=fmt, **kw)
        return (True, str(resolved))
    except Exception as exc:
        return (False, f"{path}: {exc}")

from PIL import Image
from PyQt6.QtCore import QObject, QTimer, pyqtSignal, pyqtSlot

from src.core import color_grader, raw_reader, exif_reader, image_processor
from src.models.grade_settings import GradeSettings, BUILTIN_LUTS, CurvePoints
from src.models.photo import Photo
from src.models.settings import (
    BorderSettings, TemplateStyle, AspectRatioPreset, BorderPreset, LogoStyle, TextAlign,
)

log = logging.getLogger(__name__)

# Preview render size. Larger = better fidelity but slower; 1280 keeps interactive.
PREVIEW_LONG_EDGE = 1280

# Debounce slider changes to avoid re-rendering on every pixel of drag.
DEBOUNCE_MS = 80

# File dialog name filters — single source of truth for both pickImage and pickFiles.
# RAW coverage: Canon (CR2/CR3), Nikon (NEF/NRW), Sony (ARW/SRF/SR2),
# Fuji (RAF), Panasonic (RW2), Olympus (ORF), Pentax (PEF), Samsung (SRW),
# Sigma (X3F), Phase One (IIQ), Hasselblad (3FR), Adobe (DNG).
#
# IMPORTANT: Linux QFileDialog name filters are case-sensitive. Cameras almost
# always write uppercase extensions (IMG_0430.CR3, DSC_1234.NEF), so every
# extension must be listed in BOTH cases or the files will be hidden.
def _both_cases(exts_lower: str) -> str:
    parts = exts_lower.split()
    out = []
    for p in parts:
        out.append(p)
        upper = p.upper()
        if upper != p:
            out.append(upper)
    return " ".join(out)

_RAW_LOWER = "*.cr2 *.cr3 *.crw *.nef *.nrw *.arw *.srf *.sr2 *.raf *.rw2 *.orf *.pef *.srw *.x3f *.iiq *.3fr *.dng *.raw"
_STANDARD_LOWER = "*.jpg *.jpeg *.png *.tif *.tiff *.webp *.heic *.heif"
RAW_EXTS = _both_cases(_RAW_LOWER)
STANDARD_EXTS = _both_cases(_STANDARD_LOWER)
ALL_EXTS = f"{STANDARD_EXTS} {RAW_EXTS}"
DIALOG_FILTERS = ";;".join([
    f"所有支援格式 ({ALL_EXTS})",
    f"標準圖片 ({STANDARD_EXTS})",
    f"RAW 檔 ({RAW_EXTS})",
    "所有檔案 (*)",
])


class PyBridge(QObject):
    """The single Python object exposed to JS via QWebChannel."""

    previewReady = pyqtSignal(str)
    histogramReady = pyqtSignal(str)
    statusChanged = pyqtSignal(str)
    exifReady = pyqtSignal(str)        # JSON string of EXIF for the loaded image
    settingsApplied = pyqtSignal(str)  # JSON of fields to push back to UI sliders
    batchProgress = pyqtSignal(str)    # JSON {done, total, current, ok, fail}
    batchFinished = pyqtSignal(str)    # JSON {ok, fail, out_dir, errors, cancelled}

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._source_image: Image.Image | None = None
        self._preview_source: Image.Image | None = None  # downscaled for fast preview
        self._raw_path: Path | None = None  # set when loaded file is RAW (lazy full-decode)
        self._loaded_path: Path | None = None
        self._exif: object | None = None  # ExifData when an image is loaded
        self._settings: GradeSettings = GradeSettings()
        self._border: BorderSettings = BorderSettings()
        self._border_enabled: bool = False
        self._render_timer = QTimer(self)
        self._render_timer.setSingleShot(True)
        self._render_timer.setInterval(DEBOUNCE_MS)
        self._render_timer.timeout.connect(self._render_preview)
        # Batch state — written from worker thread, read by Qt thread; flag is atomic.
        self._batch_cancel: bool = False
        self._batch_thread = None  # threading.Thread instance during a batch

    # ── Image loading ─────────────────────────────────────────────────────────
    @pyqtSlot(str, str, int, result=str)
    def pickAndExport(self, default_name: str, fmt: str, quality: int) -> str:
        """Open a save dialog and immediately export the graded image."""
        from PyQt6.QtWidgets import QFileDialog
        ext_map = {"JPEG": "jpg", "PNG": "png", "TIFF": "tif", "WEBP": "webp"}
        ext = ext_map.get(fmt.upper(), "jpg")
        suggested = str(Path.home() / f"{default_name}.{ext}")
        path, _ = QFileDialog.getSaveFileName(
            None, "輸出相片", suggested,
            f"{fmt} (*.{ext})",
        )
        if not path:
            return ""
        result = self.exportImage(path, fmt, quality)
        return path if result == "ok" else f"error: {result}"

    @pyqtSlot(result=str)
    def pickImage(self) -> str:
        """Open native file dialog; returns chosen path or empty string."""
        from PyQt6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(
            None,
            "選擇相片",
            str(Path.home()),
            DIALOG_FILTERS,
        )
        if not path:
            return ""
        result = self.loadImage(path)
        return path if result == "ok" else ""

    @pyqtSlot(str, result=str)
    def loadImage(self, path: str) -> str:
        """Load any supported image, including RAW (CR2/NEF/ARW/DNG/RAF/RW2 etc.).

        For RAW: decode_preview returns the embedded JPEG thumbnail (fast) or
        falls back to a half-size demosaic. Full-resolution RAW decoding only
        happens at export time, keeping the UI responsive.
        """
        try:
            p = Path(path).expanduser().resolve()
            if not p.is_file():
                return f"error: file not found: {p}"

            if raw_reader.is_raw(p):
                self.statusChanged.emit(f"解碼 RAW: {p.name} …")
                self._preview_source = raw_reader.decode_preview(p).convert("RGB")
                self._source_image = None
                self._raw_path = p
                w, h = self._preview_source.size
                self.statusChanged.emit(f"已載入 RAW {p.name} (預覽 {w}×{h}, 匯出時全解碼)")
            else:
                img = Image.open(p).convert("RGB")
                self._source_image = img
                self._preview_source = self._downscale(img, PREVIEW_LONG_EDGE)
                self._raw_path = None
                self.statusChanged.emit(f"已載入 {p.name} ({img.width}×{img.height})")

            self._loaded_path = p
            self._read_and_emit_exif(p)
            self._schedule_render()
            return "ok"
        except Exception as exc:
            log.exception("loadImage failed")
            return f"error: {exc}"

    @staticmethod
    def _downscale(img: Image.Image, long_edge: int) -> Image.Image:
        w, h = img.size
        if max(w, h) <= long_edge:
            return img.copy()
        scale = long_edge / max(w, h)
        new_w, new_h = int(w * scale), int(h * scale)
        return img.resize((new_w, new_h), Image.Resampling.LANCZOS)

    # ── Grade parameter setters ───────────────────────────────────────────────
    @pyqtSlot(str, "QVariant")
    def setGradeParam(self, name: str, value: Any) -> None:
        """Update a single GradeSettings field by name."""
        if not hasattr(self._settings, name):
            log.warning("setGradeParam: unknown field %s", name)
            return
        try:
            coerced = self._coerce(name, value)
            self._settings = dataclasses.replace(self._settings, **{name: coerced})
            self._schedule_render()
        except Exception:
            log.exception("setGradeParam failed for %s=%r", name, value)

    def _coerce(self, name: str, value: Any) -> Any:
        """Coerce JS-passed value to the expected dataclass field type."""
        current = getattr(self._settings, name)
        if isinstance(current, bool):
            return bool(value)
        if isinstance(current, int):
            return int(round(float(value)))
        if isinstance(current, float):
            return float(value)
        if isinstance(current, str):
            return str(value)
        return value

    @pyqtSlot()
    def resetGrade(self) -> None:
        self._settings = GradeSettings()
        self.statusChanged.emit("已重置調色")
        self._schedule_render()

    @pyqtSlot(str)
    def applyLut(self, filename: str) -> None:
        """Apply a built-in film simulation LUT by filename, '' to clear."""
        from src.models.grade_settings import LUT_ASSETS_DIR
        if not filename:
            self._settings = dataclasses.replace(self._settings, lut_path=None)
            self.statusChanged.emit("LUT 已清除")
        else:
            full = LUT_ASSETS_DIR / filename
            self._settings = dataclasses.replace(self._settings, lut_path=str(full))
            self.statusChanged.emit(f"套用 LUT: {filename}")
        self._schedule_render()

    @pyqtSlot(str, int, "QVariant")
    def setHslComponent(self, channel: str, idx: int, value: Any) -> None:
        """Update one HSL slot (hue/saturation/luminance × hue index 0-7)."""
        if channel not in ("hue", "saturation", "luminance") or not (0 <= idx < 8):
            return
        field = f"hsl_{channel}"
        current = list(getattr(self._settings, field))
        current[idx] = int(round(float(value)))
        self._settings = dataclasses.replace(self._settings, **{field: tuple(current)})
        self._schedule_render()

    @pyqtSlot(str)
    def setTreatment(self, treatment: str) -> None:
        if treatment not in ("color", "bw"):
            return
        self._settings = dataclasses.replace(self._settings, treatment=treatment)
        self._schedule_render()

    @pyqtSlot(bool)
    def setFlipH(self, flag: bool) -> None:
        self._settings = dataclasses.replace(self._settings, flip_h=bool(flag))
        self._schedule_render()

    @pyqtSlot(bool)
    def setFlipV(self, flag: bool) -> None:
        self._settings = dataclasses.replace(self._settings, flip_v=bool(flag))
        self._schedule_render()

    # ── AI Denoise (SCUNet) ───────────────────────────────────────────────────
    @pyqtSlot(result=str)
    def applyAIDenoise(self) -> str:
        """Run SCUNet on the current preview source. Replaces _preview_source in-place
        so subsequent slider tweaks operate on the cleaned image."""
        if self._preview_source is None:
            return json.dumps({"ok": False, "error": "尚未載入相片"})
        try:
            from src.core.ai import scunet_runner
            if not scunet_runner.is_available():
                return json.dumps({"ok": False, "error": "SCUNet model 不在"})
            self.statusChanged.emit("AI 神經網路去噪處理中… (SCUNet)")
            denoised = scunet_runner.denoise(self._preview_source)
            self._preview_source = denoised
            # Also clear noise_reduction sliders since AI replaces them
            self._settings = dataclasses.replace(
                self._settings, noise_reduction=0, noise_color=0,
            )
            provider = scunet_runner.get_provider()
            self.statusChanged.emit(f"AI 去噪完成（{provider}）")
            self._schedule_render()
            return json.dumps({"ok": True, "provider": provider})
        except Exception as exc:
            log.exception("applyAIDenoise failed")
            self.statusChanged.emit(f"AI 去噪失敗：{exc}")
            return json.dumps({"ok": False, "error": str(exc)})

    @pyqtSlot(result=str)
    def aiProvider(self) -> str:
        """Report whether GPU or CPU will be used for AI Denoise."""
        try:
            from src.core.ai import scunet_runner
            return scunet_runner.get_provider()
        except Exception:
            return "unavailable"

    # ── Auto Tone (LR-style) ──────────────────────────────────────────────────
    @pyqtSlot(result=str)
    def applyAutoTone(self) -> str:
        """Analyze current preview, propose tonal/WB/vibrance settings, push to UI.

        Frontend listens to `settingsApplied` to sync slider positions, and the
        normal render pipeline picks up the new settings via _schedule_render.
        """
        if self._preview_source is None:
            return json.dumps({"ok": False, "error": "尚未載入相片"})
        try:
            from src.core import auto_tone
            deltas = auto_tone.analyze(self._preview_source)
            self._settings = dataclasses.replace(self._settings, **deltas)
            self.settingsApplied.emit(json.dumps(deltas))
            self.statusChanged.emit("自動色調已套用 — 可再微調滑桿")
            self._schedule_render()
            return json.dumps({"ok": True, "deltas": deltas})
        except Exception as exc:
            log.exception("applyAutoTone failed")
            self.statusChanged.emit(f"自動色調失敗：{exc}")
            return json.dumps({"ok": False, "error": str(exc)})

    # ── EXIF ──────────────────────────────────────────────────────────────────
    def _read_and_emit_exif(self, path: Path) -> None:
        try:
            data = exif_reader.read_exif(path)
            self._exif = data
            self.exifReady.emit(json.dumps({
                "make": getattr(data, "make", "") or "",
                "model": getattr(data, "model", "") or "",
                "lens": getattr(data, "lens", "") or "",
                "iso": getattr(data, "iso", "") or "",
                "aperture": getattr(data, "aperture", "") or "",
                "shutter": getattr(data, "shutter", "") or "",
                "focal": getattr(data, "focal", "") or "",
                "date": getattr(data, "date_taken", "") or "",
            }, ensure_ascii=False))
        except Exception:
            log.exception("EXIF read failed")
            self.exifReady.emit("{}")

    @pyqtSlot(result=str)
    def getExif(self) -> str:
        if self._exif is None:
            return "{}"
        d = self._exif
        return json.dumps({
            "make": getattr(d, "make", "") or "",
            "model": getattr(d, "model", "") or "",
            "lens": getattr(d, "lens", "") or "",
            "iso": getattr(d, "iso", "") or "",
            "aperture": getattr(d, "aperture", "") or "",
            "shutter": getattr(d, "shutter", "") or "",
            "focal": getattr(d, "focal", "") or "",
            "date": getattr(d, "date_taken", "") or "",
        }, ensure_ascii=False)

    # ── Tone Curves ───────────────────────────────────────────────────────────
    @pyqtSlot(str, str)
    def setCurve(self, channel: str, points_json: str) -> None:
        """Set a tone curve. channel: 'rgb'|'r'|'g'|'b'.
        points_json: JSON list of [input, output] pairs each in 0.0-1.0."""
        if channel not in ("rgb", "r", "g", "b"):
            return
        try:
            pts = json.loads(points_json)
            tup = tuple(tuple(map(float, p)) for p in pts if len(p) == 2)
            if len(tup) < 2:
                return
            field = f"curve_{channel}"
            self._settings = dataclasses.replace(self._settings, **{field: CurvePoints(points=tup)})
            self._schedule_render()
        except Exception:
            log.exception("setCurve failed")

    # ── Split Toning ──────────────────────────────────────────────────────────
    # (uses regular setGradeParam for split_highlights_hue/sat, split_shadows_hue/sat, split_balance)

    # ── Frame / Border ────────────────────────────────────────────────────────
    @pyqtSlot(bool)
    def setBorderEnabled(self, flag: bool) -> None:
        self._border_enabled = bool(flag)
        self._schedule_render()

    @pyqtSlot(str, "QVariant")
    def setBorderParam(self, name: str, value: Any) -> None:
        """Update a single BorderSettings field by name. Enum fields accept string names."""
        try:
            current = getattr(self._border, name, None)
        except Exception:
            return
        # Map enum-typed fields
        enum_map = {
            "template": TemplateStyle,
            "aspect_ratio": AspectRatioPreset,
            "border_preset": BorderPreset,
            "logo_style": LogoStyle,
            "text_align": TextAlign,
        }
        try:
            if name in enum_map:
                cls = enum_map[name]
                # Try by name (e.g. "MEDIUM") then by value (e.g. "中")
                try:
                    enum_val = cls[value] if isinstance(value, str) else cls(value)
                except KeyError:
                    enum_val = cls(value)
                self._border = dataclasses.replace(self._border, **{name: enum_val})
            elif name == "bg_color":
                # Accept "#RRGGBB" or [r,g,b] list
                if isinstance(value, str) and value.startswith("#"):
                    h = value.lstrip("#")
                    rgb = (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
                else:
                    rgb = tuple(int(c) for c in value)[:3]
                self._border = dataclasses.replace(self._border, bg_color=rgb)
            elif isinstance(current, bool):
                self._border = dataclasses.replace(self._border, **{name: bool(value)})
            elif isinstance(current, int):
                self._border = dataclasses.replace(self._border, **{name: int(round(float(value)))})
            elif isinstance(current, float):
                self._border = dataclasses.replace(self._border, **{name: float(value)})
            else:
                self._border = dataclasses.replace(self._border, **{name: value})
            if self._border_enabled:
                self._schedule_render()
        except Exception:
            log.exception("setBorderParam failed")

    # ── Export with options ───────────────────────────────────────────────────
    @pyqtSlot(str, int, "QVariant", result=str)
    def pickAndExportWithOptions(self, fmt: str, quality: int, long_edge: Any) -> str:
        """Open save dialog, then export with format/quality/long-edge resize."""
        from PyQt6.QtWidgets import QFileDialog
        ext_map = {"JPEG": "jpg", "PNG": "png", "TIFF": "tif", "WEBP": "webp"}
        ext = ext_map.get(fmt.upper(), "jpg")
        stem = (self._loaded_path.stem if self._loaded_path else "untitled") + "_graded"
        suggested = str(Path.home() / f"{stem}.{ext}")
        path, _ = QFileDialog.getSaveFileName(None, "輸出相片", suggested, f"{fmt} (*.{ext})")
        if not path:
            return ""
        long_edge_int = int(long_edge) if long_edge else 0
        return self.exportImage(path, fmt, quality) if long_edge_int <= 0 \
            else self._export_resized(path, fmt, quality, long_edge_int)

    def _export_resized(self, path: str, fmt: str, quality: int, long_edge: int) -> str:
        if self._source_image is None and self._raw_path is None:
            return "error: no image loaded"
        try:
            if self._source_image is None:
                self._source_image = raw_reader.decode(self._raw_path).convert("RGB")
            graded = color_grader.apply(self._source_image, self._settings)
            w, h = graded.size
            if max(w, h) > long_edge:
                scale = long_edge / max(w, h)
                graded = graded.resize((int(w*scale), int(h*scale)), Image.Resampling.LANCZOS)
            out = Path(path).expanduser().resolve()
            out.parent.mkdir(parents=True, exist_ok=True)
            kw: dict[str, Any] = {}
            f = fmt.upper()
            if f == "JPEG":
                kw.update(quality=int(quality), optimize=True, progressive=True)
                graded = graded.convert("RGB")
            elif f == "WEBP":
                kw.update(quality=int(quality), method=6)
            elif f == "TIFF":
                kw.update(compression="tiff_lzw")
            graded.save(out, format=f, **kw)
            self.statusChanged.emit(f"已輸出 {out.name} ({graded.width}×{graded.height})")
            return path
        except Exception as exc:
            log.exception("_export_resized failed")
            return f"error: {exc}"

    # ── Batch Export ──────────────────────────────────────────────────────────
    @pyqtSlot(result=str)
    def pickFiles(self) -> str:
        """Open multi-file picker. Returns JSON list of paths."""
        from PyQt6.QtWidgets import QFileDialog
        paths, _ = QFileDialog.getOpenFileNames(
            None, "選擇多張相片", str(Path.home()),
            DIALOG_FILTERS,
        )
        return json.dumps(paths)

    # ── Crop ──────────────────────────────────────────────────────────────────
    @pyqtSlot(float, float, float, float)
    def setCrop(self, left: float, top: float, right: float, bottom: float) -> None:
        """Set crop insets (each 0..1, relative). All-zero = no crop."""
        clamp = lambda v: max(0.0, min(0.95, float(v)))  # noqa: E731
        self._settings = dataclasses.replace(
            self._settings,
            crop_left=clamp(left),
            crop_top=clamp(top),
            crop_right=clamp(right),
            crop_bottom=clamp(bottom),
        )
        self._schedule_render()

    @pyqtSlot()
    def resetCrop(self) -> None:
        """Clear any active crop."""
        self._settings = dataclasses.replace(
            self._settings,
            crop_left=0.0, crop_top=0.0, crop_right=0.0, crop_bottom=0.0,
        )
        self.statusChanged.emit("已清除裁切")
        self._schedule_render()

    @pyqtSlot(result=str)
    def pickOutputDir(self) -> str:
        """Open a folder picker; returns the chosen directory path or ''."""
        from PyQt6.QtWidgets import QFileDialog
        d = QFileDialog.getExistingDirectory(
            None, "選擇批次輸出資料夾", str(Path.home()),
        )
        return d or ""

    # ── Batch export (LR-grade, async, with progress) ─────────────────────────
    # Field groups exposed to the UI for selective sync. Keys = group ids used
    # by JS checkboxes; values = GradeSettings field names included in the group.
    BATCH_FIELD_GROUPS: dict[str, tuple[str, ...]] = {
        "light": ("exposure", "contrast", "highlights", "shadows", "whites",
                  "blacks", "clarity", "dehaze"),
        "color": ("wb_temperature", "wb_tint", "vibrance", "saturation",
                  "treatment", "bw_mix"),
        "detail": ("texture", "sharpening", "detail_mask", "noise_reduction",
                   "noise_color", "noise_lum_detail", "noise_color_detail"),
        "effects": ("vignette_amount", "vignette_midpoint", "grain_amount", "grain_size"),
        "splittone": ("split_highlights_hue", "split_highlights_sat",
                      "split_shadows_hue", "split_shadows_sat", "split_balance"),
        "hsl": ("hsl_hue", "hsl_saturation", "hsl_luminance"),
        "curves": ("curve_rgb", "curve_r", "curve_g", "curve_b"),
        "lut": ("lut_path", "lut_opacity"),
        "geometry": ("rotation", "flip_h", "flip_v"),
        "crop": ("crop_left", "crop_top", "crop_right", "crop_bottom"),
    }

    def _filter_settings(self, master: GradeSettings, groups: list[str]) -> GradeSettings:
        """Return a fresh GradeSettings containing only the chosen field groups
        from `master`; everything else is left at default."""
        out = GradeSettings()
        for group in groups:
            for field in self.BATCH_FIELD_GROUPS.get(group, ()):
                if hasattr(master, field):
                    out = dataclasses.replace(out, **{field: getattr(master, field)})
        return out

    @pyqtSlot(str)
    def batchExport(self, options_json: str) -> None:
        """Async batch — returns immediately, emits batchProgress/batchFinished.

        options_json fields:
          paths: list[str]
          out_dir: str
          fmt: str ("JPEG"|"PNG"|"TIFF"|"WEBP")
          quality: int
          filename_template: str   (tokens: {name} {seq} {date} {datetime} {ext})
          collision: str           ("overwrite" | "skip" | "increment")
          apply_groups: list[str]  (ids from BATCH_FIELD_GROUPS)
          auto_tone_per_image: bool
        """
        try:
            opts = json.loads(options_json)
        except Exception:
            self.batchFinished.emit(json.dumps({"ok": 0, "fail": 0, "errors": ["JSON 格式錯誤"]}))
            return
        paths = opts.get("paths") or []
        if not paths:
            self.batchFinished.emit(json.dumps({"ok": 0, "fail": 0, "errors": ["未選檔案"]}))
            return

        ext_map = {"JPEG": "jpg", "PNG": "png", "TIFF": "tif", "WEBP": "webp"}
        fmt = (opts.get("fmt") or "JPEG").upper()
        ext = ext_map.get(fmt, "jpg")
        quality = int(opts.get("quality") or 92)
        out_dir_raw = opts.get("out_dir") or ""
        out_dir_resolved = str(Path(out_dir_raw).expanduser().resolve()) if out_dir_raw else ""
        template = opts.get("filename_template") or "{name}_graded"
        collision = opts.get("collision") or "increment"
        groups = opts.get("apply_groups") or list(self.BATCH_FIELD_GROUPS.keys())
        auto_tone = bool(opts.get("auto_tone_per_image"))

        filtered_settings = self._filter_settings(self._settings, groups)
        worker_args = [
            (
                p, filtered_settings, fmt, quality, ext, out_dir_resolved,
                template, collision, auto_tone, idx,
            )
            for idx, p in enumerate(paths, start=1)
        ]
        loc_label = out_dir_resolved or "原檔同目錄"
        n_workers = max(1, min(len(paths), (os.cpu_count() or 4) - 1))
        self.statusChanged.emit(f"批次：{len(paths)} 張 → {n_workers} workers → {loc_label}")

        # Reset cancel flag and spawn worker thread (so progress signals are dispatched live)
        self._batch_cancel = False
        import threading
        self._batch_thread = threading.Thread(
            target=self._run_batch_thread,
            args=(worker_args, n_workers, out_dir_resolved),
            daemon=True,
            name="piclab-batch",
        )
        self._batch_thread.start()

    def _run_batch_thread(self, worker_args: list, n_workers: int, out_dir: str) -> None:
        total = len(worker_args)
        ok = 0
        fail = 0
        errors: list[str] = []
        cancelled = False
        try:
            import multiprocessing as mp
            ctx = mp.get_context("spawn")
            with ctx.Pool(n_workers) as pool:
                # imap_unordered yields results as workers finish — perfect for live progress.
                it = pool.imap_unordered(_batch_worker, worker_args)
                for done, (success, msg) in enumerate(it, start=1):
                    if self._batch_cancel:
                        cancelled = True
                        try:
                            pool.terminate()
                        except Exception:
                            pass
                        break
                    if success:
                        ok += 1
                    else:
                        fail += 1
                        if len(errors) < 5:
                            errors.append(msg)
                    self.batchProgress.emit(json.dumps({
                        "done": done, "total": total,
                        "ok": ok, "fail": fail,
                        "current": Path(msg).name if success else msg.split(":")[0],
                    }, ensure_ascii=False))
        except Exception as exc:
            log.exception("batch thread failed")
            errors.append(f"thread error: {exc}")

        self.statusChanged.emit(
            f"批次{'已中止' if cancelled else '完成'}：{ok} 成功 / {fail} 失敗 → "
            f"{out_dir or '原檔同目錄'}"
        )
        self.batchFinished.emit(json.dumps({
            "ok": ok, "fail": fail,
            "out_dir": out_dir or "（原檔同目錄）",
            "errors": errors,
            "cancelled": cancelled,
        }, ensure_ascii=False))

    @pyqtSlot()
    def cancelBatch(self) -> None:
        """Set the cancel flag — the worker thread checks it between yields."""
        self._batch_cancel = True
        self.statusChanged.emit("批次已要求中止…")

    @pyqtSlot(str)
    def openInFileManager(self, path: str) -> None:
        """Open a directory in the system's file manager (xdg-open / Finder)."""
        try:
            import subprocess
            p = str(Path(path).expanduser().resolve())
            if sys.platform == "darwin":
                subprocess.Popen(["open", p])
            elif os.name == "nt":
                os.startfile(p)  # type: ignore[attr-defined]
            else:
                subprocess.Popen(["xdg-open", p])
        except Exception:
            log.exception("openInFileManager failed")

    # ── IG Publish ────────────────────────────────────────────────────────────
    @pyqtSlot(str, result=str)
    def publishToIg(self, caption: str) -> str:
        """Export current preview to JPEG then publish via IGPublisher (uses .env credentials)."""
        try:
            from src.core.ig_publisher import IGPublisher
            if self._source_image is None and self._raw_path is None:
                return "error: 尚未載入相片"
            if self._source_image is None:
                self._source_image = raw_reader.decode(self._raw_path).convert("RGB")
            graded = color_grader.apply(self._source_image, self._settings).convert("RGB")
            tmp = Path("/tmp") / f"piclab_ig_{int(__import__('time').time())}.jpg"
            graded.save(tmp, format="JPEG", quality=92, optimize=True)
            self.statusChanged.emit("發佈到 Instagram …")
            pub = IGPublisher()
            res = pub.publish(image_path=tmp, caption=caption or "")
            self.statusChanged.emit(f"IG 發佈：{'成功' if getattr(res,'success',False) else '失敗'}")
            return json.dumps({"success": getattr(res, "success", False),
                               "message": getattr(res, "message", "") or ""})
        except Exception as exc:
            log.exception("publishToIg failed")
            self.statusChanged.emit(f"IG 發佈失敗：{exc}")
            return json.dumps({"success": False, "message": str(exc)})

    # ── Preview rendering ─────────────────────────────────────────────────────
    @pyqtSlot()
    def requestPreview(self) -> None:
        self._schedule_render()

    def _schedule_render(self) -> None:
        if self._preview_source is None:
            return
        self._render_timer.start()

    def _render_preview(self) -> None:
        if self._preview_source is None:
            return
        try:
            graded = color_grader.apply(self._preview_source, self._settings)
            if self._border_enabled and self._loaded_path is not None and self._exif is not None:
                photo = Photo(file_path=self._loaded_path, image=graded, exif=self._exif)
                graded = image_processor.process(photo, self._border)
            buf = io.BytesIO()
            graded.convert("RGB").save(buf, format="JPEG", quality=85, optimize=True)
            data_url = "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode("ascii")
            self.previewReady.emit(data_url)
            # Histogram off the graded image (post-pipeline reflects what the user sees)
            self._emit_histogram(graded)
        except Exception as exc:
            log.exception("render_preview failed")
            self.statusChanged.emit(f"渲染失敗: {exc}")

    def _emit_histogram(self, img: Image.Image) -> None:
        """Compute 256-bin RGB histogram + luma stats and push to JS."""
        try:
            import numpy as np
            arr = np.asarray(img.convert("RGB"), dtype=np.uint8)
            r_hist = np.bincount(arr[..., 0].ravel(), minlength=256).tolist()
            g_hist = np.bincount(arr[..., 1].ravel(), minlength=256).tolist()
            b_hist = np.bincount(arr[..., 2].ravel(), minlength=256).tolist()
            luma = (0.2126 * arr[..., 0] + 0.7152 * arr[..., 1] + 0.0722 * arr[..., 2])
            stats = {
                "mean": float(luma.mean()),
                "median": float(np.median(luma)),
                "clip_low": float((luma < 4).mean() * 100),
                "clip_high": float((luma > 250).mean() * 100),
            }
            payload = json.dumps({"r": r_hist, "g": g_hist, "b": b_hist, "stats": stats})
            self.histogramReady.emit(payload)
        except Exception:
            log.exception("emit_histogram failed")

    # ── Catalogs (for JS dropdowns) ───────────────────────────────────────────
    @pyqtSlot(result=str)
    def listLuts(self) -> str:
        items = [{"name": name, "file": fname} for name, fname in BUILTIN_LUTS.items()]
        return json.dumps(items, ensure_ascii=False)

    # ── Export ────────────────────────────────────────────────────────────────
    @pyqtSlot(str, str, int, result=str)
    def exportImage(self, path: str, fmt: str, quality: int) -> str:
        # Resolve full-resolution source: PIL-loaded standard image, or lazy RAW decode.
        if self._source_image is None and self._raw_path is None:
            return "error: no image loaded"
        try:
            if self._source_image is None and self._raw_path is not None:
                self.statusChanged.emit(f"全解碼 RAW: {self._raw_path.name} …")
                self._source_image = raw_reader.decode(self._raw_path).convert("RGB")
            graded = color_grader.apply(self._source_image, self._settings)
            out = Path(path).expanduser().resolve()
            out.parent.mkdir(parents=True, exist_ok=True)
            fmt = fmt.upper()
            save_kwargs: dict[str, Any] = {}
            if fmt == "JPEG":
                save_kwargs.update(quality=int(quality), optimize=True, progressive=True)
                graded = graded.convert("RGB")
            elif fmt == "WEBP":
                save_kwargs.update(quality=int(quality), method=6)
            elif fmt == "PNG":
                graded = graded.convert("RGBA" if graded.mode == "RGBA" else "RGB")
            elif fmt == "TIFF":
                save_kwargs.update(compression="tiff_lzw")
            graded.save(out, format=fmt, **save_kwargs)
            self.statusChanged.emit(f"已輸出 {out}")
            return "ok"
        except Exception as exc:
            log.exception("exportImage failed")
            return f"error: {exc}"
