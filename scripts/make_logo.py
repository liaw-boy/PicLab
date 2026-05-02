"""PicLab Atelier Logo Generator.

Concept: Atelier Lightbox — cream paper + aubergine frame + a single gold light leak.
Reads as: a darkroom viewing window with a sliver of light coming through.

Outputs:
    src/assets/icons/piclab.png        — 512x512 master
    src/assets/icons/piclab_256.png    — desktop icon
    src/assets/icons/piclab_128.png    — small menu
    src/assets/icons/piclab_64.png     — task bar
    src/assets/icons/piclab.ico        — Windows
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "src" / "assets" / "icons"
OUT.mkdir(parents=True, exist_ok=True)
FONT = ROOT / "src" / "assets" / "fonts" / "Inter-Medium.ttf"

# Atelier Lightbox palette
CREAM = (244, 239, 230)
AUBERGINE = (74, 31, 56)
AUBERGINE_DARK = (54, 22, 41)
GOLD = (168, 129, 78)
INK = (31, 26, 20)


def render(size: int) -> Image.Image:
    """Render a square logo at the given pixel size."""
    img = Image.new("RGBA", (size, size), CREAM + (255,))
    d = ImageDraw.Draw(img, "RGBA")

    # ── Subtle paper grain (very light, only at large sizes)
    if size >= 128:
        grain = Image.new("L", (size, size), 0)
        gd = ImageDraw.Draw(grain)
        import random
        random.seed(42)
        for _ in range(size * 4):
            x, y = random.randint(0, size - 1), random.randint(0, size - 1)
            gd.point((x, y), fill=random.randint(0, 14))
        grain_rgba = Image.new("RGBA", (size, size), INK + (0,))
        grain_rgba.putalpha(grain)
        img.alpha_composite(grain_rgba)

    # ── Aubergine viewing frame — generously inset, soft corners
    pad = int(size * 0.18)
    rect = (pad, pad, size - pad, size - pad)
    radius = int(size * 0.08)

    # frame fill (slightly lighter inside than edge — fakes inner depth)
    d.rounded_rectangle(rect, radius=radius, fill=AUBERGINE_DARK + (255,))

    # inner inset — the "viewing aperture"
    inset = int(size * 0.04)
    inner = (rect[0] + inset, rect[1] + inset, rect[2] - inset, rect[3] - inset)
    d.rounded_rectangle(inner, radius=max(2, radius - inset), fill=AUBERGINE + (255,))

    # ── Gold light leak — vertical slice cutting through the aperture
    leak_w = max(2, int(size * 0.014))
    leak_x = int(rect[0] + (rect[2] - rect[0]) * 0.62)  # off-center, editorial
    leak_top = rect[1] - int(size * 0.04)
    leak_bot = rect[3] + int(size * 0.04)
    leak = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ld = ImageDraw.Draw(leak)
    ld.rectangle((leak_x, leak_top, leak_x + leak_w, leak_bot), fill=GOLD + (255,))
    # bloom — soft halo around the leak
    if size >= 64:
        leak_blur = leak.filter(ImageFilter.GaussianBlur(radius=size * 0.012))
        # halo color, lower alpha
        halo = Image.new("RGBA", (size, size), GOLD + (0,))
        halo.putalpha(leak_blur.split()[3].point(lambda v: int(v * 0.55)))
        img.alpha_composite(halo)
    img.alpha_composite(leak)

    # ── Frame corner ticks (registration marks — editorial detail)
    if size >= 128:
        tick_len = int(size * 0.05)
        tick_w = max(1, int(size * 0.008))
        for cx, cy, dx, dy in [
            (rect[0], rect[1], +1, +1),
            (rect[2], rect[1], -1, +1),
            (rect[0], rect[3], +1, -1),
            (rect[2], rect[3], -1, -1),
        ]:
            offset = int(size * 0.025)
            x, y = cx - dx * offset, cy - dy * offset
            d.line(
                [(x, y), (x + dx * tick_len, y)],
                fill=GOLD + (220,),
                width=tick_w,
            )
            d.line(
                [(x, y), (x, y + dy * tick_len)],
                fill=GOLD + (220,),
                width=tick_w,
            )

    # ── Wordmark "PL" inside the aperture (only at sizes that can hold it)
    if size >= 128:
        font_size = int(size * 0.30)
        try:
            font = ImageFont.truetype(str(FONT), font_size)
        except OSError:
            font = ImageFont.load_default()
        text = "PL"
        # measure
        bbox = d.textbbox((0, 0), text, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        tx = (size - tw) // 2 - bbox[0]
        ty = (size - th) // 2 - bbox[1] - int(size * 0.02)
        d.text((tx, ty), text, font=font, fill=CREAM + (235,))

    return img


def export() -> None:
    master = render(512)
    master.save(OUT / "piclab.png")
    print(f"✅ {OUT / 'piclab.png'}")
    for s in (256, 128, 64, 32):
        img = render(s)
        path = OUT / f"piclab_{s}.png"
        img.save(path)
        print(f"✅ {path}")
    # ICO bundle for Windows
    master.save(
        OUT / "piclab.ico",
        sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
    print(f"✅ {OUT / 'piclab.ico'}")


if __name__ == "__main__":
    export()
