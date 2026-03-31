from __future__ import annotations
from pathlib import Path
from PIL import Image, ImageDraw

from src.core.font_manager import get_font, text_size

# Absolute path to bundled brand logo assets — resolved relative to this file
_BRANDS_DIR = Path(__file__).parent.parent / "assets" / "brands"

# Map brand name → filename inside _BRANDS_DIR
LOGO_FILES: dict[str, str] = {
    "Sony":       "sony.png",
    "Canon":      "Canon_red.png",
    "Nikon":      "Nikon_yellow.png",
    "Fujifilm":   "fujifilm.png",
    "Olympus":    "olympus.png",
    "Leica":      "Leica_red.png",
    "Panasonic":  "lumix.png",
    "Ricoh":      "ricoh.png",
    "Pentax":     "pentax.png",
    "Hasselblad": "hasselblad.png",
    "DJI":        "dji.jpg",
    "Apple":      "apple.png",
    "XMAGE":      "xmage.png",
    "Sigma":      "sigma.png",
    "Zeiss":      "zeiss.png",
    "Tamron":     "tamron.png",
    "Tokina":     "tokina.png",
    "Samyang":    "samyang.png",
    "Voigtlander":"voigtlander.png",
    "GoPro":      "gopro.png",
    "Insta360":   "insta360.png",
    "Phase One":  "phase_one.png",
    "Kodak":      "kodak.png",
    "Polaroid":   "polaroid.png",
}

def _has_logo(brand: str) -> bool:
    fname = LOGO_FILES.get(brand)
    return bool(fname and (_BRANDS_DIR / fname).exists())

# Brand registry
BRANDS: dict[str, dict] = {
    "Sony":       {"text": "SONY",       "short": "Sony",      "weight": "bold",    "color": (10, 10, 10),      "styles": ["text", "badge", "wordmark", "logo"]},
    "Canon":      {"text": "Canon",      "short": "Canon",     "weight": "regular", "color": (190, 0, 0),        "styles": ["text", "badge", "wordmark", "logo"]},
    "Nikon":      {"text": "Nikon",      "short": "Nikon",     "weight": "bold",    "color": (18, 54, 103),      "styles": ["text", "badge", "wordmark", "logo"]},
    "Fujifilm":   {"text": "FUJIFILM",   "short": "Fuji",      "weight": "bold",    "color": (210, 16, 52),      "styles": ["text", "badge", "wordmark", "logo"]},
    "OM System":  {"text": "OM SYSTEM",  "short": "OM Sys",    "weight": "bold",    "color": (10, 10, 10),       "styles": ["text", "badge"]},
    "Olympus":    {"text": "OLYMPUS",    "short": "Olympus",   "weight": "bold",    "color": (10, 10, 10),       "styles": ["text", "badge", "logo"]},
    "Leica":      {"text": "Leica",      "short": "Leica",     "weight": "regular", "color": (190, 0, 0),        "styles": ["text", "badge", "wordmark", "logo"]},
    "Panasonic":  {"text": "Panasonic",  "short": "Pana",      "weight": "regular", "color": (0, 80, 160),       "styles": ["text", "badge", "logo"]},
    "Ricoh":      {"text": "RICOH",      "short": "Ricoh",     "weight": "bold",    "color": (0, 40, 110),       "styles": ["text", "badge", "logo"]},
    "Pentax":     {"text": "PENTAX",     "short": "Pentax",    "weight": "bold",    "color": (10, 10, 10),       "styles": ["text", "badge", "logo"]},
    "Hasselblad": {"text": "HASSELBLAD", "short": "Hassy",     "weight": "bold",    "color": (215, 160, 30),     "styles": ["text", "badge", "wordmark", "logo"]},
    "Sigma":      {"text": "SIGMA",      "short": "Sigma",     "weight": "bold",    "color": (10, 10, 10),       "styles": ["text", "badge", "logo"]},
    "Tamron":     {"text": "TAMRON",     "short": "Tamron",    "weight": "bold",    "color": (220, 50, 30),      "styles": ["text", "badge", "logo"]},
    "DJI":        {"text": "DJI",        "short": "DJI",       "weight": "bold",    "color": (44, 120, 175),     "styles": ["text", "badge", "wordmark", "logo"]},
    "GoPro":      {"text": "GoPro",      "short": "GoPro",     "weight": "bold",    "color": (0, 163, 108),      "styles": ["text", "badge", "logo"]},
    "Apple":      {"text": "iPhone",     "short": "iPhone",    "weight": "regular", "color": (10, 10, 10),       "styles": ["text", "badge", "logo"]},
    "Kodak":      {"text": "KODAK",      "short": "Kodak",     "weight": "bold",    "color": (180, 130, 0),      "styles": ["text", "badge", "logo"]},
    "Minolta":    {"text": "MINOLTA",    "short": "Minolta",   "weight": "bold",    "color": (10, 10, 10),       "styles": ["text", "badge"]},
    "Zeiss":      {"text": "ZEISS",      "short": "Zeiss",     "weight": "bold",    "color": (10, 10, 10),       "styles": ["text", "badge", "logo"]},
    "Phase One":  {"text": "Phase One",  "short": "P.One",     "weight": "regular", "color": (10, 10, 10),       "styles": ["text", "badge", "logo"]},
    "Samsung":    {"text": "SAMSUNG",    "short": "Samsung",   "weight": "bold",    "color": (0, 70, 127),       "styles": ["text", "badge"]},
    "Contax":     {"text": "CONTAX",     "short": "Contax",    "weight": "bold",    "color": (10, 10, 10),       "styles": ["text"]},
    "Tokina":     {"text": "TOKINA",     "short": "Tokina",    "weight": "bold",    "color": (10, 10, 10),       "styles": ["text", "badge", "logo"]},
    "Samyang":    {"text": "SAMYANG",    "short": "Samyang",   "weight": "bold",    "color": (10, 10, 10),       "styles": ["text", "badge", "logo"]},
    "Voigtlander":{"text": "VOIGTLÄNDER","short": "Voigt",     "weight": "regular", "color": (10, 10, 10),       "styles": ["text", "badge", "logo"]},
    "Insta360":   {"text": "Insta360",   "short": "Insta",     "weight": "bold",    "color": (10, 10, 10),       "styles": ["text", "badge", "logo"]},
    "Polaroid":   {"text": "POLAROID",   "short": "Pol",       "weight": "bold",    "color": (10, 10, 10),       "styles": ["text", "badge", "logo"]},
    "XMAGE":      {"text": "XMAGE",      "short": "XMAGE",     "weight": "bold",    "color": (10, 10, 10),       "styles": ["text", "badge", "logo"]},
}

# Legacy alias — keeps old code that references BRAND_STYLES working
BRAND_STYLES = {k: {"text": v["text"], "weight": v["weight"], "color": v["color"]} for k, v in BRANDS.items()}


def render_brand(
    make: str,
    slot_height: int,
    custom_logo_path: Path | None = None,
    style: str = "text",
) -> Image.Image:
    """
    Render a camera brand as a transparent RGBA image sized to slot_height.
    style: "text" | "badge" | "wordmark"
    Returns a 1×slot_height transparent image when make is empty.
    """
    if not make:
        return Image.new("RGBA", (1, slot_height), (0, 0, 0, 0))
    if custom_logo_path and custom_logo_path.exists():
        return _render_custom_logo(custom_logo_path, slot_height)

    if style == "badge":
        return _render_badge(make, slot_height)
    if style == "wordmark":
        return _render_wordmark(make, slot_height)
    if style == "logo":
        return _render_official_logo(make, slot_height)
    return _render_text(make, slot_height)


# ── Official brand logo (PNG) ────────────────────────────────────────────────

def _render_official_logo(make: str, slot_height: int) -> Image.Image:
    """Render the official brand logo from src/assets/brands/. Falls back to text."""
    fname = LOGO_FILES.get(make)
    if not fname:
        return _render_text(make, slot_height)
    asset_path = _BRANDS_DIR / fname
    if not asset_path.exists():
        return _render_text(make, slot_height)
    return _render_custom_logo(asset_path, slot_height)


# ── Custom logo ───────────────────────────────────────────────────────────────

def _render_custom_logo(path: Path, slot_height: int) -> Image.Image:
    """載入 logo，等比縮放至 slot_height，保留透明通道，不失真。"""
    with Image.open(path) as raw:
        # 統一轉 RGBA 保留透明度；JPG 無透明但仍可正確合成
        img = raw.convert("RGBA")
    if img.height == 0:
        return Image.new("RGBA", (1, slot_height), (0, 0, 0, 0))
    aspect = img.width / img.height
    new_w  = max(1, int(slot_height * aspect))
    # LANCZOS 高品質縮放，保持等高等比不失真
    return img.resize((new_w, slot_height), Image.LANCZOS)


# ── Text style ────────────────────────────────────────────────────────────────

def _render_text(make: str, slot_height: int) -> Image.Image:
    """Brand name as styled text on transparent background."""
    info = BRANDS.get(make, {"text": make.upper(), "weight": "bold", "color": (10, 10, 10)})
    font_size = max(8, int(slot_height * 0.55))
    font = get_font(font_size, info["weight"])
    text = info["text"]
    if not text:
        return Image.new("RGBA", (1, slot_height), (0, 0, 0, 0))

    tw, th = text_size(text, font)
    img = Image.new("RGBA", (max(1, tw + 4), slot_height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.text((2, (slot_height - th) // 2), text, font=font, fill=info["color"] + (255,))
    return img


# ── Badge style ───────────────────────────────────────────────────────────────

def _render_badge(make: str, slot_height: int) -> Image.Image:
    """Brand name inside a colored pill badge with white text."""
    info = BRANDS.get(make, {"text": make.upper(), "weight": "bold", "color": (10, 10, 10)})
    color = info["color"]

    font_size = max(6, int(slot_height * 0.40))
    font = get_font(font_size, "bold")
    text = info["text"]
    if not text:
        return Image.new("RGBA", (1, slot_height), (0, 0, 0, 0))

    tw, th = text_size(text, font)
    pad_h = max(8, int(slot_height * 0.22))
    pad_v = max(3, int(slot_height * 0.14))

    img_w = max(1, tw + 2 * pad_h)
    img_h = slot_height

    img = Image.new("RGBA", (img_w, img_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    inner_h = img_h - 2 * pad_v
    r = min(6, inner_h // 3)
    draw.rounded_rectangle(
        [(0, pad_v), (img_w - 1, img_h - pad_v - 1)],
        radius=r,
        fill=color + (255,),
    )

    tx = (img_w - tw) // 2
    ty = (img_h - th) // 2
    draw.text((tx, ty), text, font=font, fill=(255, 255, 255, 238))
    return img


# ── Wordmark style ────────────────────────────────────────────────────────────

def _render_wordmark(make: str, slot_height: int) -> Image.Image:
    """Large bold wordmark — refined editorial style."""
    info = BRANDS.get(make, {"text": make.upper(), "weight": "bold", "color": (10, 10, 10)})
    font_size = max(10, int(slot_height * 0.68))
    font = get_font(font_size, "bold")
    text = info["text"]
    if not text:
        return Image.new("RGBA", (1, slot_height), (0, 0, 0, 0))

    tw, th = text_size(text, font)
    img = Image.new("RGBA", (max(1, tw + 8), slot_height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.text((4, (slot_height - th) // 2), text, font=font, fill=info["color"] + (255,))
    return img
