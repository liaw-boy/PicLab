from __future__ import annotations
from dataclasses import dataclass

from src.models.settings import AspectRatioPreset, ASPECT_RATIO_SIZES, BorderSettings


@dataclass(frozen=True)
class CanvasGeometry:
    canvas_w: int
    canvas_h: int
    photo_x: int
    photo_y: int
    photo_w: int
    photo_h: int
    exif_strip_y: int
    exif_strip_h: int
    img_x: int
    img_y: int
    img_w: int
    img_h: int


def compute_geometry(
    photo_size: tuple[int, int],
    settings: BorderSettings,
) -> CanvasGeometry:
    photo_w_orig, photo_h_orig = photo_size
    preset_canvas = ASPECT_RATIO_SIZES[settings.aspect_ratio]

    if preset_canvas is not None:
        canvas_w, canvas_h = preset_canvas
    else:
        # FREE mode: temporarily use photo dimensions to compute border scale
        canvas_w = photo_w_orig
        canvas_h = photo_h_orig

    border = settings.border_dims(canvas_w)
    top  = border["top"]
    side = border["side"]

    has_exif = settings.show_logo or settings.show_exif

    if not has_exif:
        # 無 EXIF：底部 = 頂部，照片完全置中
        exif_strip_h = top
        avail_top    = top
    else:
        # 有 EXIF：底部加入 strip，頂部也同步加到 strip_h
        # → 照片仍置中，不因 strip 往上偏移
        exif_strip_h = border["exif_strip"]
        avail_top    = exif_strip_h   # 頂部 = 底部 strip_h，保持置中

    if preset_canvas is None:
        # FREE mode：canvas 依照片 + 等量上下邊距計算
        canvas_w = photo_w_orig + 2 * side
        canvas_h = photo_h_orig + avail_top + exif_strip_h

    # Available photo area（頂部用 avail_top，確保垂直置中）
    avail_x = side
    avail_y = avail_top
    avail_w = max(1, canvas_w - 2 * side)
    avail_h = max(1, canvas_h - avail_top - exif_strip_h)

    # Scale photo to fit available area (letterbox), guard against zero
    scale = min(avail_w / max(1, photo_w_orig), avail_h / max(1, photo_h_orig))
    scale = max(scale, 1e-6)
    img_w = max(1, int(photo_w_orig * scale))
    img_h = max(1, int(photo_h_orig * scale))

    # Center within available area
    img_x = avail_x + (avail_w - img_w) // 2
    img_y = avail_y + (avail_h - img_h) // 2

    return CanvasGeometry(
        canvas_w=canvas_w,
        canvas_h=canvas_h,
        photo_x=avail_x,
        photo_y=avail_y,
        photo_w=avail_w,
        photo_h=avail_h,
        exif_strip_y=canvas_h - exif_strip_h,
        exif_strip_h=exif_strip_h,
        img_x=img_x,
        img_y=img_y,
        img_w=img_w,
        img_h=img_h,
    )
