"""
PresetManager — 讀寫使用者自訂加框設定預設組。
儲存於 ~/.piclab/presets.json
"""
from __future__ import annotations
import json
from pathlib import Path

_DIR  = Path.home() / ".piclab"
_FILE = _DIR / "presets.json"


def _ensure() -> None:
    _DIR.mkdir(parents=True, exist_ok=True)


def load_all() -> dict[str, dict]:
    if not _FILE.exists():
        return {}
    try:
        return json.loads(_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save(name: str, settings) -> None:
    _ensure()
    presets = load_all()
    presets[name] = _to_dict(settings)
    _FILE.write_text(
        json.dumps(presets, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def delete(name: str) -> None:
    presets = load_all()
    if name in presets:
        del presets[name]
        _ensure()
        _FILE.write_text(
            json.dumps(presets, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


def _to_dict(s) -> dict:
    return {
        "template":           s.template.name,
        "aspect_ratio":       s.aspect_ratio.name,
        "border_preset":      s.border_preset.name,
        "custom_top":         s.custom_top,
        "custom_side":        s.custom_side,
        "custom_exif_strip":  s.custom_exif_strip,
        "show_logo":          s.show_logo,
        "show_exif":          s.show_exif,
        "logo_style":         s.logo_style.name,
        "logo_brand_override": s.logo_brand_override,
        "text_align":         s.text_align.name,
        "bg_color":           list(s.bg_color),
        "blur_background":    s.blur_background,
        "output_format":      s.output_format,
        "jpeg_quality":       s.jpeg_quality,
    }


def from_dict(d: dict):
    from src.models.settings import (
        BorderSettings, TemplateStyle, AspectRatioPreset,
        BorderPreset, LogoStyle, TextAlign,
    )
    try:
        return BorderSettings(
            template           = TemplateStyle[d.get("template", "CLASSIC")],
            aspect_ratio       = AspectRatioPreset[d.get("aspect_ratio", "SQUARE_1_1")],
            border_preset      = BorderPreset[d.get("border_preset", "CUSTOM")],
            custom_top         = d.get("custom_top", 40),
            custom_side        = d.get("custom_side", 40),
            custom_exif_strip  = d.get("custom_exif_strip", 80),
            show_logo          = d.get("show_logo", False),
            show_exif          = d.get("show_exif", False),
            logo_style         = LogoStyle[d.get("logo_style", "LOGO")],
            logo_brand_override= d.get("logo_brand_override"),
            text_align         = TextAlign[d.get("text_align", "CENTER")],
            bg_color           = tuple(d.get("bg_color", [255, 255, 255])),
            blur_background    = d.get("blur_background", False),
            output_format      = d.get("output_format", "JPEG"),
            jpeg_quality       = d.get("jpeg_quality", 95),
        )
    except (KeyError, TypeError):
        from src.models.settings import BorderSettings
        return BorderSettings()
