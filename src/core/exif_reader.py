from __future__ import annotations
from fractions import Fraction
from pathlib import Path

import exifread
import piexif

from src.models.photo import ExifData
from src.core.nikon_lens_map import LensMapDict

MAKE_NORMALIZATION: dict[str, str] = {
    "SONY": "Sony",
    "CANON": "Canon",
    "NIKON CORPORATION": "Nikon",
    "NIKON": "Nikon",
    "FUJIFILM": "Fujifilm",
    "OLYMPUS": "OM System",
    "OM DIGITAL SOLUTIONS": "OM System",
    "PANASONIC": "Panasonic",
    "LEICA": "Leica",
    "RICOH": "Ricoh",
    "PENTAX":    "Pentax",
}


def _get_nikon_lens_name(tags: dict) -> str | None:
    """Advanced Nikon Lens ID lookup using nikon_lens_map."""
    try:
        
        def to_hex(val) -> str:
            try:
                h = hex(int(val)).replace("0x", "").upper()
                return h if len(h) >= 2 else f"0{h}"
            except (ValueError, TypeError):
                return "00"

        # Construct the 8-part key used in the map
        # "LensID FStop MinFocal MaxFocal MaxApMin MaxApMax MCUVersion LensType"
        parts = []
        for tag_name in [
            "MakerNote Nikon3 LensID",
            "MakerNote Nikon3 FStop", 
            "MakerNote Nikon3 MinFocalLength",
            "MakerNote Nikon3 MaxFocalLength",
            "MakerNote Nikon3 MaxApertureAtMinFocal",
            "MakerNote Nikon3 MaxApertureAtMaxFocal",
            "MakerNote Nikon1 MCUVersion",
            "MakerNote Nikon3 LensType"
        ]:
            val = tags.get(tag_name)
            if val:
                # exifread tags can be many types, take the first value if it's a list
                v = val.values[0] if hasattr(val, 'values') and val.values else val
                parts.append(to_hex(v))
            else:
                parts.append("00")
        
        key = " ".join(parts)
        return LensMapDict.get(key)
    except Exception:
        return None


def _normalize_make(raw: str) -> str:
    key = raw.strip().upper()
    return MAKE_NORMALIZATION.get(key, raw.strip().title())


def _rational_to_float(value) -> float | None:
    try:
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, tuple) and len(value) == 2:
            num, den = value
            return float(num) / float(den) if den != 0 else None
        return None
    except Exception:
        return None


def _format_aperture(value) -> str:
    f = _rational_to_float(value)
    if f is None:
        return ""
    return f"f/{f:.1f}"


def _format_shutter(value) -> str:
    try:
        if isinstance(value, tuple) and len(value) == 2:
            num, den = value
            if den == 0:
                return ""
            frac = Fraction(int(num), int(den))
        elif isinstance(value, (int, float)):
            frac = Fraction(value).limit_denominator(100000)
        else:
            return ""
        f = float(frac)
        if f >= 1.0:
            return f"{f:.1f}s"
        # Use the exact Fraction, not float, to avoid precision loss
        frac2 = frac.limit_denominator(10000)
        if frac2.numerator == 1:
            return f"1/{frac2.denominator}s"
        return f"{frac2.numerator}/{frac2.denominator}s"
    except Exception:
        return ""


def _format_focal(value, value_35mm=None) -> str:
    if value_35mm is not None:
        f = _rational_to_float(value_35mm)
        if f is not None and f > 0:
            return f"{int(round(f))}mm"
    f = _rational_to_float(value)
    if f is None:
        return ""
    return f"{int(round(f))}mm"


def _read_with_piexif(path: Path) -> ExifData | None:
    try:
        data = piexif.load(str(path))
        exif = data.get("Exif", {})
        ifd0 = data.get("0th", {})

        make_raw = ifd0.get(piexif.ImageIFD.Make, b"")
        if isinstance(make_raw, bytes):
            make_raw = make_raw.decode("utf-8", errors="ignore").strip("\x00")
        make = _normalize_make(make_raw)

        model_raw = ifd0.get(piexif.ImageIFD.Model, b"")
        if isinstance(model_raw, bytes):
            model_raw = model_raw.decode("utf-8", errors="ignore").strip("\x00")
        model = model_raw.strip()
        # Remove make prefix from model if present
        make_upper = make_raw.upper() if isinstance(make_raw, str) else make_raw.decode("utf-8", errors="ignore").upper()
        if model.upper().startswith(make_upper):
            model = model[len(make_upper):].strip()

        lens_raw = exif.get(piexif.ExifIFD.LensModel, b"")
        if isinstance(lens_raw, bytes):
            lens_raw = lens_raw.decode("utf-8", errors="ignore").strip("\x00")
        lens = lens_raw.strip()

        focal = exif.get(piexif.ExifIFD.FocalLength)
        focal_35 = exif.get(piexif.ExifIFD.FocalLengthIn35mmFilm)
        focal_str = _format_focal(focal, focal_35)

        aperture_str = _format_aperture(exif.get(piexif.ExifIFD.FNumber))
        shutter_str = _format_shutter(exif.get(piexif.ExifIFD.ExposureTime))

        iso_val = exif.get(piexif.ExifIFD.ISOSpeedRatings, 0)
        if isinstance(iso_val, (list, tuple)):
            iso_val = iso_val[0] if iso_val else 0
        iso_str = f"ISO {iso_val}" if iso_val else ""

        dt_raw = exif.get(piexif.ExifIFD.DateTimeOriginal, b"")
        if isinstance(dt_raw, bytes):
            dt_raw = dt_raw.decode("utf-8", errors="ignore")
        date_str = ""
        if dt_raw:
            # 保留完整 "YYYY:MM:DD HH:MM:SS" → "YYYY-MM-DD HH:MM:SS"
            cleaned = dt_raw.strip("\x00").replace("\x00", "")
            parts = cleaned.split(" ")
            date_part = parts[0].replace(":", "-") if parts else ""
            time_part = parts[1] if len(parts) > 1 else ""
            date_str = f"{date_part} {time_part}".strip()

        return ExifData(
            camera_make=make,
            camera_model=model,
            lens_model=lens,
            focal_length=focal_str,
            aperture=aperture_str,
            shutter_speed=shutter_str,
            iso=iso_str,
            date_taken=date_str,
        )
    except Exception:
        return None


def _read_with_exifread(path: Path) -> ExifData | None:
    try:
        with open(path, "rb") as f:
            tags = exifread.process_file(f, stop_tag="UNDEF", details=False)

        def _get_tag(key: str, default="") -> str:
            v = tags.get(key)
            return str(v).strip() if v else default

        make_raw = _get_tag("Image Make")
        make = _normalize_make(make_raw)
        model = _get_tag("Image Model").strip()
        make_upper = make_raw.upper()
        if model.upper().startswith(make_upper):
            model = model[len(make_upper):].strip()

        lens = _get_tag("EXIF LensModel") or _get_tag("MakerNote LensType", "")
        if make == "Nikon":
            deep_lens = _get_nikon_lens_name(tags)
            if deep_lens:
                lens = deep_lens

        focal_35_raw = tags.get("EXIF FocalLengthIn35mmFilm")
        focal_raw = tags.get("EXIF FocalLength")
        if focal_35_raw:
            try:
                focal_str = f"{int(str(focal_35_raw))}mm"
            except Exception:
                focal_str = _get_tag("EXIF FocalLength")
        elif focal_raw:
            try:
                frac = Fraction(str(focal_raw))
                focal_str = f"{int(round(float(frac)))}mm"
            except Exception:
                focal_str = str(focal_raw)
        else:
            focal_str = ""

        aperture_raw = tags.get("EXIF FNumber")
        if aperture_raw:
            try:
                frac = Fraction(str(aperture_raw))
                aperture_str = f"f/{float(frac):.1f}"
            except Exception:
                aperture_str = f"f/{aperture_raw}"
        else:
            aperture_str = ""

        shutter_raw = tags.get("EXIF ExposureTime")
        if shutter_raw:
            try:
                frac = Fraction(str(shutter_raw))
                f = float(frac)
                if f >= 1.0:
                    shutter_str = f"{f:.1f}s"
                else:
                    frac2 = frac.limit_denominator(10000)
                    if frac2.numerator == 1:
                        shutter_str = f"1/{frac2.denominator}s"
                    else:
                        shutter_str = f"{frac2.numerator}/{frac2.denominator}s"
            except Exception:
                shutter_str = str(shutter_raw)
        else:
            shutter_str = ""

        iso_raw = tags.get("EXIF ISOSpeedRatings") or tags.get("EXIF RecommendedExposureIndex")
        iso_str = f"ISO {iso_raw}" if iso_raw else ""

        dt_raw = _get_tag("EXIF DateTimeOriginal") or _get_tag("Image DateTime")
        date_str = ""
        if dt_raw:
            parts = dt_raw.split(" ")
            date_part = parts[0].replace(":", "-") if parts else ""
            time_part = parts[1] if len(parts) > 1 else ""
            date_str = f"{date_part} {time_part}".strip()

        return ExifData(
            camera_make=make,
            camera_model=model,
            lens_model=lens,
            focal_length=focal_str,
            aperture=aperture_str,
            shutter_speed=shutter_str,
            iso=iso_str,
            date_taken=date_str,
        )
    except Exception:
        return None


def read_exif(path: Path) -> ExifData:
    """Read EXIF from image file. Returns empty ExifData on failure."""
    result = _read_with_piexif(path)
    if result is not None and result.has_any:
        return result
    result = _read_with_exifread(path)
    if result is not None:
        return result
    return ExifData()
