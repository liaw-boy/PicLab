"""
Image compositing pipeline.

Three templates:
  CLASSIC — White border + EXIF strip at bottom (landscape-friendly)
  ROUNDED — Equal white border + rounded photo corners + EXIF text below photo
  SPLIT   — Left info panel (35%) + right photo (65%) — PS-boot style

EXIF strip format (reference: OneLine / Cameramark style):

  LEFT (42%)                CENTER (18%)    │    RIGHT (40%)
  ISO800  ƒ/2.8  1/200s     [Brand Logo]   │    Canon EOS R7
  Jan 13, 2025 at 2:22 PM                  │    EF-S 17-55mm f/2.8 IS USM
"""
from __future__ import annotations
import datetime
from PIL import Image, ImageDraw, ImageFilter

from src.models.photo import Photo
from src.models.settings import BorderSettings, TemplateStyle, TextAlign, ASPECT_RATIO_SIZES
from src.core.aspect_ratio import compute_geometry
from src.core.brand_renderer import render_brand
from src.core.font_manager import get_font, get_cjk_font, text_size

# Output image always uses white background regardless of app theme
COLOR_BG           = (255, 255, 255)
COLOR_PHOTO_BORDER = (230, 230, 230)   # Subtle border around rounded/split photos
COLOR_DIVIDER      = (210, 210, 210)
COLOR_TEXT_DARK    = (15,  15,  15)    # Near-black — primary text
COLOR_TEXT_MID     = (55,  55,  55)    # Dark gray — camera/lens name
COLOR_TEXT_LIGHT   = (110, 110, 110)   # Medium gray — secondary labels
COLOR_SEP          = (160, 160, 160)   # Separator dots between EXIF params
COLOR_LEFT_BG      = (248, 248, 248)   # Split template left panel


def _format_datetime_display(date_taken: str) -> str:
    """
    Convert "2025-01-13 14:22:50" → "Jan 13, 2025 at 2:22:50 PM"
    Falls back gracefully on parse error. Windows-compatible (no %-I).
    """
    if not date_taken:
        return ""
    try:
        dt = datetime.datetime.strptime(date_taken.strip(), "%Y-%m-%d %H:%M:%S")
        month  = dt.strftime("%b")
        day    = dt.day
        year   = dt.year
        hour   = dt.hour % 12 or 12
        minute = f"{dt.minute:02d}"
        second = f"{dt.second:02d}"
        ampm   = "AM" if dt.hour < 12 else "PM"
        return f"{month} {day}, {year} at {hour}:{minute}:{second} {ampm}"
    except ValueError:
        pass
    try:
        dt = datetime.datetime.strptime(date_taken.strip()[:10], "%Y-%m-%d")
        return f"{dt.strftime('%b')} {dt.day}, {dt.year}"
    except ValueError:
        return date_taken


def _format_datetime_strip(date_taken: str) -> str:
    """Convert "2025-01-13 14:22:50" → "2025.01.13  14:22:50" for EXIF strip."""
    if not date_taken:
        return ""
    try:
        dt = datetime.datetime.strptime(date_taken.strip(), "%Y-%m-%d %H:%M:%S")
        return f"{dt.year}.{dt.month:02d}.{dt.day:02d}  {dt.hour:02d}:{dt.minute:02d}:{dt.second:02d}"
    except ValueError:
        pass
    try:
        dt = datetime.datetime.strptime(date_taken.strip()[:10], "%Y-%m-%d")
        return f"{dt.year}.{dt.month:02d}.{dt.day:02d}"
    except ValueError:
        return date_taken


# ── Layout helpers ────────────────────────────────────────────────────────────

def _text_colors(bg: tuple[int, int, int]) -> tuple:
    """Return (dark, mid, sep) text colors suited to the background brightness."""
    lum = (bg[0] * 299 + bg[1] * 587 + bg[2] * 114) // 1000
    if lum < 128:                           # dark background → light text
        return (235, 235, 235), (170, 170, 170), (110, 110, 110)
    else:                                   # light background → dark text
        return (15, 15, 15),   (55, 55, 55),    (160, 160, 160)


def _align_x(align: TextAlign, content_w: int, canvas_w: int, pad: int) -> int:
    """Return left x so that content_w is placed per alignment."""
    if align == TextAlign.CENTER:
        return max(pad, (canvas_w - content_w) // 2)
    if align == TextAlign.RIGHT:
        return max(pad, canvas_w - pad - content_w)
    return pad  # LEFT


def _fit_text(text: str, font, max_w: int) -> str:
    """Truncate text with '…' if it exceeds max_w pixels."""
    if not text or text_size(text, font)[0] <= max_w:
        return text
    while len(text) > 1 and text_size(text.rstrip() + "…", font)[0] > max_w:
        text = text[:-1]
    return text.rstrip() + "…"


# ── 模糊背景生成 ──────────────────────────────────────────────────────────────

def _make_blur_canvas(photo_img: Image.Image,
                      canvas_w: int, canvas_h: int) -> Image.Image:
    """
    用照片本身生成模糊背景畫布：
    1. 等比縮放至恰好覆蓋整個畫布（cover 模式）
    2. 高斯模糊（半徑 = 畫布短邊 3%，確保足夠柔化）
    3. 略為暗化，讓主照片更突出
    """
    rgb = photo_img.convert("RGB")
    img_r = rgb.width / rgb.height
    cvs_r = canvas_w / canvas_h

    # Cover 模式縮放
    if img_r > cvs_r:
        new_h = canvas_h
        new_w = int(new_h * img_r)
    else:
        new_w = canvas_w
        new_h = int(new_w / img_r)

    # 放大 10% 避免高斯模糊邊緣產生黑邊
    new_w = int(new_w * 1.1)
    new_h = int(new_h * 1.1)

    scaled  = rgb.resize((new_w, new_h), Image.LANCZOS)
    ox = (new_w - canvas_w) // 2
    oy = (new_h - canvas_h) // 2
    cropped = scaled.crop((ox, oy, ox + canvas_w, oy + canvas_h))

    # 模糊半徑 = 短邊 3%，最小 20px
    radius = max(20, int(min(canvas_w, canvas_h) * 0.03))
    blurred = cropped.filter(ImageFilter.GaussianBlur(radius=radius))

    # 略微暗化（乘以 0.80）讓主照片更突出
    r, g, b = blurred.split()
    factor = 0.80
    r = r.point(lambda x: int(x * factor))
    g = g.point(lambda x: int(x * factor))
    b = b.point(lambda x: int(x * factor))
    return Image.merge("RGB", (r, g, b))


# ── Public entry point ────────────────────────────────────────────────────────

def process(photo: Photo, settings: BorderSettings) -> Image.Image:
    """Return a new composited PIL Image. Pure function."""
    if settings.template == TemplateStyle.ROUNDED:
        return _process_rounded(photo, settings)
    elif settings.template == TemplateStyle.SPLIT:
        return _process_split(photo, settings)
    else:
        return _process_classic(photo, settings)


# ── Template 1: CLASSIC ───────────────────────────────────────────────────────

def _process_classic(photo: Photo, settings: BorderSettings) -> Image.Image:
    geo = compute_geometry(photo.size, settings)
    if settings.blur_background:
        canvas = _make_blur_canvas(photo.image, geo.canvas_w, geo.canvas_h)
    else:
        canvas = Image.new("RGB", (geo.canvas_w, geo.canvas_h), settings.bg_color)

    rgb = photo.image.convert("RGB")
    scaled = rgb.resize((geo.img_w, geo.img_h), Image.LANCZOS)
    rgb.close()
    canvas.paste(scaled, (geo.img_x, geo.img_y))
    scaled.close()

    _draw_classic_exif(canvas, photo, settings, geo)
    return canvas


def _draw_classic_exif(canvas, photo, settings, geo) -> None:
    """
    Cameramark 風格 EXIF 條：

      LEFT (~40%)                    CENTER (~22%)    │  RIGHT (~36%)
      35mm  f/2.8  1/250s  ISO800    [ Logo ]         │  ILCE-7RM2
      2025.01.13  14:22:50                            │  FE 35mm F2.8 ZA
    """
    if not settings.show_logo and not settings.show_exif:
        return

    draw = ImageDraw.Draw(canvas)
    exif = photo.exif
    sw = geo.canvas_w
    sh = geo.exif_strip_h
    sy = geo.img_y + geo.img_h

    C_DARK, C_MID, C_SEP = _text_colors(settings.bg_color)
    lum = (settings.bg_color[0] * 299 + settings.bg_color[1] * 587
           + settings.bg_color[2] * 114) // 1000
    div_color = (185, 185, 185) if lum > 128 else (75, 75, 75)

    pad_x   = max(28, int(sw * 0.028))
    v_pad   = max(6,  int(sh * 0.14))
    row_gap = max(3,  int(sh * 0.08))
    gap     = max(10, int(sw * 0.012))

    # ── 字型 ──────────────────────────────────────────────────────────────
    line1_sz   = max(13, int(sh * 0.34))
    line2_sz   = max(11, int(sh * 0.27))
    font_line1 = get_font(line1_sz, "bold")
    font_line2 = get_font(line2_sz, "regular")

    # ── 區帶劃分 ──────────────────────────────────────────────────────────
    logo_zone_x = int(sw * 0.42)          # logo 區起點
    logo_zone_w = int(sw * 0.22)          # logo 區寬度
    div_x       = logo_zone_x + logo_zone_w
    right_x     = div_x + gap
    right_avail = sw - right_x - pad_x
    left_avail  = logo_zone_x - pad_x

    # ── 準備 Logo ──────────────────────────────────────────────────────────
    # 參考圖片：logo 高度佔 strip 約 55–65%，視覺上與兩行文字等高
    v_margin = max(4, int(sh * 0.18))
    brand_h  = max(14, sh - 2 * v_margin)
    brand_img = None
    if settings.show_logo and (settings.logo_brand_override or exif.camera_make):
        brand_img = render_brand(
            settings.logo_brand_override or exif.camera_make,
            brand_h, settings.custom_logo_path, settings.logo_style.value,
        )

    # ── 準備左側文字 ───────────────────────────────────────────────────────
    # 第一行：拍攝參數（焦距 光圈 快門 ISO）
    left1 = ""
    if settings.show_exif:
        parts = [v for v in [
            exif.focal_length, exif.aperture,
            exif.shutter_speed, exif.iso,
        ] if v]
        left1 = "  ".join(parts)

    # 第二行：日期時間
    left2 = ""
    if settings.show_exif and exif.date_taken:
        left2 = _format_datetime_strip(exif.date_taken)

    # ── 準備右側文字 ───────────────────────────────────────────────────────
    right1 = ""
    right2 = ""
    if settings.show_exif:
        right1 = exif.camera_model or ""
        right2 = exif.lens_model   or ""

    # ── 垂直置中輔助 ──────────────────────────────────────────────────────
    def _vc_y(line_a: str, font_a, line_b: str, font_b) -> tuple[int, int, int, int]:
        """回傳 (y_line_a, h_a, y_line_b, h_b)，整體在 strip 內垂直置中。"""
        _, ha = text_size(line_a or "A", font_a)
        _, hb = text_size(line_b or "A", font_b)
        has_b  = bool(line_b)
        blk_h  = ha + (row_gap + hb if has_b else 0)
        y0     = sy + (sh - blk_h) // 2
        return y0, ha, y0 + ha + row_gap, hb

    ly0, lh1, ly2, _ = _vc_y(left1,  font_line1, left2,  font_line2)
    ry0, rh1, ry2, _ = _vc_y(right1, font_line1, right2, font_line2)

    # ── 繪製左側 ──────────────────────────────────────────────────────────
    if left1:
        draw.text((pad_x, ly0),
                  _fit_text(left1, font_line1, left_avail),
                  font=font_line1, fill=C_DARK)
    if left2:
        draw.text((pad_x, ly2),
                  _fit_text(left2, font_line2, left_avail),
                  font=font_line2, fill=C_SEP)

    # ── 繪製 Logo（置中於 logo 區）──────────────────────────────────────
    if brand_img:
        lx = logo_zone_x + (logo_zone_w - brand_img.width) // 2
        ly = sy + (sh - brand_img.height) // 2
        if brand_img.mode == "RGBA":
            canvas.paste(brand_img, (lx, ly), brand_img)
        else:
            canvas.paste(brand_img, (lx, ly))

    # ── 繪製分隔線 ────────────────────────────────────────────────────────
    has_right = bool(right1 or right2)
    show_divider = (brand_img or settings.show_logo) and has_right
    if show_divider:
        draw.line(
            [(div_x, sy + v_pad), (div_x, sy + sh - v_pad)],
            fill=div_color, width=1,
        )

    # ── 繪製右側 ──────────────────────────────────────────────────────────
    if right1:
        draw.text((right_x, ry0),
                  _fit_text(right1, font_line1, right_avail),
                  font=font_line1, fill=C_DARK)
    if right2:
        draw.text((right_x, ry2),
                  _fit_text(right2, font_line2, right_avail),
                  font=font_line2, fill=C_MID)


# ── Template 2: ROUNDED ───────────────────────────────────────────────────────

def _process_rounded(photo: Photo, settings: BorderSettings) -> Image.Image:
    preset = ASPECT_RATIO_SIZES[settings.aspect_ratio]
    if preset:
        cw, ch = preset
    else:
        cw, ch = photo.size

    if settings.blur_background:
        canvas = _make_blur_canvas(photo.image, cw, ch)
    else:
        canvas = Image.new("RGB", (cw, ch), settings.bg_color)
    border = settings.border_dims(cw)
    pad    = border["side"]
    strip  = border["exif_strip"]

    # Available area for photo (top & sides equally padded, bottom = pad+strip)
    avail_w = max(1, cw - 2 * pad)
    avail_h = max(1, ch - 2 * pad - strip)

    # Scale photo into available area
    pw, ph = photo.size
    scale  = min(avail_w / max(1, pw), avail_h / max(1, ph))
    scale  = max(scale, 1e-6)
    sw_    = max(1, int(pw * scale))
    sh_    = max(1, int(ph * scale))

    # Rounded corners radius = 2.5% of shorter side
    radius = max(8, int(min(sw_, sh_) * 0.025))

    rgb    = photo.image.convert("RGB")
    scaled = rgb.resize((sw_, sh_), Image.LANCZOS)
    rgb.close()
    rounded = _apply_rounded(scaled, radius)
    scaled.close()

    # Center horizontally; top-pad vertically
    ix = pad + (avail_w - sw_) // 2
    iy = pad + (avail_h - sh_) // 2
    canvas.paste(rounded, (ix, iy), rounded)

    # EXIF strip below photo
    _draw_rounded_exif(canvas, photo, settings, cw, ch, pad, strip)
    return canvas


def _apply_rounded(img: Image.Image, radius: int) -> Image.Image:
    """Return RGBA PIL Image with rounded corners."""
    out  = Image.new("RGBA", img.size, (0, 0, 0, 0))
    mask = Image.new("L",    img.size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle([0, 0, img.size[0] - 1, img.size[1] - 1],
                           radius=radius, fill=255)
    out.paste(img, mask=mask)
    return out


def _draw_rounded_exif(canvas, photo, settings, cw, ch, pad, strip) -> None:
    """同 CLASSIC 雙欄 EXIF 條，應用於 ROUNDED 模板。"""
    # Reuse the same two-column layout logic
    from src.core.aspect_ratio import CanvasGeometry
    geo_stub = type('G', (), {
        'canvas_w': cw, 'exif_strip_h': strip, 'exif_strip_y': ch - strip,
        'img_y': ch - strip, 'img_h': 0,
    })()
    _draw_classic_exif(canvas, photo, settings, geo_stub)


# ── Template 3: SPLIT ─────────────────────────────────────────────────────────

def _process_split(photo: Photo, settings: BorderSettings) -> Image.Image:
    """
    Left panel (35%): soft gray background, brand large + EXIF list vertically
    Right panel (65%): photo fills the space (crop-to-fill)
    Thin divider between panels.
    """
    preset = ASPECT_RATIO_SIZES[settings.aspect_ratio]
    cw, ch = preset if preset else (1080, 1080)

    if settings.blur_background:
        canvas = _make_blur_canvas(photo.image, cw, ch)
    else:
        canvas = Image.new("RGB", (cw, ch), settings.bg_color)

    left_w  = int(cw * 0.35)
    right_w = cw - left_w
    div_w   = 1

    # Left panel
    if settings.blur_background:
        # 模糊背景：左側貼半透明暗色遮罩，讓模糊底圖透出來且文字可讀
        overlay = Image.new("RGB", (left_w, ch), (0, 0, 0))
        mask    = Image.new("L", (left_w, ch), 110)   # ~43% 不透明
        canvas.paste(overlay, (0, 0), mask)
    else:
        br, bg_, bb = settings.bg_color
        brightness  = (br + bg_ + bb) // 3
        adj         = -10 if brightness > 128 else 10
        left_color  = (max(0, min(255, br + adj)),
                       max(0, min(255, bg_ + adj)),
                       max(0, min(255, bb + adj)))
        canvas.paste(Image.new("RGB", (left_w, ch), left_color), (0, 0))

    # Divider
    draw = ImageDraw.Draw(canvas)
    draw.line([(left_w, 0), (left_w, ch)], fill=COLOR_DIVIDER, width=div_w)

    # Right panel: crop photo to fill (user-adjustable position + zoom)
    photo_x = left_w + div_w
    photo_area_w = right_w - div_w
    rgb = photo.image.convert("RGB")
    crop = _crop_to_fill(rgb, photo_area_w, ch,
                         cx_frac=settings.split_crop_x,
                         cy_frac=settings.split_crop_y,
                         zoom=settings.split_zoom)
    rgb.close()
    canvas.paste(crop, (photo_x, 0))
    crop.close()

    # Left panel content
    _draw_split_left(canvas, photo, settings, left_w, ch)
    return canvas


def _crop_to_fill(
    img: Image.Image, target_w: int, target_h: int,
    cx_frac: float = 0.5, cy_frac: float = 0.5,
    zoom: float = 1.0,
) -> Image.Image:
    """Scale then offset-crop to exactly target_w × target_h.

    cx_frac / cy_frac: 0.0 = top-left, 0.5 = centre, 1.0 = bottom-right.
    zoom: additional scale multiplier (>1 = magnify photo).
    """
    tw, th = img.size
    scale  = max(target_w / max(1, tw), target_h / max(1, th)) * max(0.5, zoom)
    sw_    = max(1, int(tw * scale))
    sh_    = max(1, int(th * scale))
    scaled = img.resize((sw_, sh_), Image.LANCZOS)
    avail_x = sw_ - target_w
    avail_y = sh_ - target_h
    cx = int(avail_x * max(0.0, min(1.0, cx_frac)))
    cy = int(avail_y * max(0.0, min(1.0, cy_frac)))
    cropped = scaled.crop((cx, cy, cx + target_w, cy + target_h))
    scaled.close()
    return cropped


def _draw_split_left(canvas, photo, settings, left_w: int, canvas_h: int) -> None:
    draw  = ImageDraw.Draw(canvas)
    exif  = photo.exif
    align = settings.text_align
    pad   = max(24, int(left_w * 0.08))
    # 模糊背景時左側已暗化，使用亮色文字；否則依背景色決定
    if settings.blur_background:
        C_DARK, C_MID, C_SEP = (235, 235, 235), (180, 180, 180), (120, 120, 120)
    else:
        C_DARK, C_MID, C_SEP = _text_colors(settings.bg_color)

    def ax(content_w: int) -> int:
        return _align_x(align, content_w, left_w, pad)

    # ── Brand logo ──────────────────────────────────────────────────────────
    brand_h = max(36, int(canvas_h * 0.055))
    cur_y   = int(canvas_h * 0.11)

    if settings.show_logo and (settings.logo_brand_override or exif.camera_make):
        brand_img = render_brand(
            settings.logo_brand_override or exif.camera_make,
            brand_h,
            settings.custom_logo_path,
            settings.logo_style.value,
        )
        bx = ax(brand_img.width)
        if brand_img.mode == "RGBA":
            canvas.paste(brand_img, (bx, cur_y), brand_img)
        else:
            canvas.paste(brand_img, (bx, cur_y))
        cur_y += brand_img.height + int(canvas_h * 0.025)

    # ── Camera model + lens + EXIF params (only when show_exif) ────────────
    if settings.show_exif:
        model_size = max(20, int(canvas_h * 0.028))
        font_model = get_font(model_size, "bold")
        if exif.camera_model:
            mw, _ = text_size(exif.camera_model, font_model)
            draw.text((ax(mw), cur_y), exif.camera_model,
                      font=font_model, fill=C_DARK)
            cur_y += model_size + int(canvas_h * 0.012)

        if exif.lens_model:
            lens_size = max(16, int(model_size * 0.80))
            lens_font = get_font(lens_size, "light")
            lw, _ = text_size(exif.lens_model, lens_font)
            draw.text((ax(lw), cur_y), exif.lens_model,
                      font=lens_font, fill=C_MID)
            cur_y += lens_size + int(canvas_h * 0.04)

        draw.line([(pad, cur_y), (left_w - pad, cur_y)],
                  fill=COLOR_DIVIDER, width=1)
        cur_y += int(canvas_h * 0.03)

        param_size = max(16, int(canvas_h * 0.023))
        font_label = get_cjk_font(param_size)
        font_value = get_font(param_size, "bold")
        row_gap    = int(param_size * 2.1)

        exif_rows = [
            ("焦距", exif.focal_length),
            ("光圈", exif.aperture),
            ("快門", exif.shutter_speed),
            ("ISO",  exif.iso),
            ("日期", exif.date_taken),
        ]
        label_w = max(text_size(lbl, font_label)[0] for lbl, _ in exif_rows) + 10

        for label, value in exif_rows:
            if not value:
                continue
            row_w  = label_w + text_size(value, font_value)[0]
            row_x  = ax(row_w)
            draw.text((row_x,            cur_y), label,
                      font=font_label, fill=C_MID)
            draw.text((row_x + label_w,  cur_y), value,
                      font=font_value,  fill=C_DARK)
            cur_y += row_gap


# ── Final Export Processing ───────────────────────────────────────────────────

def finalize_export(img: Image.Image, settings: BorderSettings) -> Image.Image:
    """
    Apply final Lightroom-style processing:
    1. Resize according to export_long_edge.
    2. Apply output sharpening if enabled.
    """
    out = img.copy()

    # 1. Resize
    if settings.export_long_edge:
        w, h = out.size
        if w > h:
            nw, nh = settings.export_long_edge, int(h * settings.export_long_edge / w)
        else:
            nw, nh = int(w * settings.export_long_edge / h), settings.export_long_edge
        
        # Only scale if different
        if (nw, nh) != (w, h):
            out = out.resize((nw, nh), Image.LANCZOS)

    # 2. Sharpening
    if settings.output_sharpening:
        from PIL import ImageFilter
        # Subtle unsharp mask to counteract scaling blur
        # Radius=1, Percent=50 is a common soft sharpening for web
        out = out.filter(ImageFilter.UnsharpMask(radius=1, percent=50, threshold=3))

    return out
