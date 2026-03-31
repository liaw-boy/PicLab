from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from PIL import Image


@dataclass(frozen=True)
class ExifData:
    camera_make: str = ""
    camera_model: str = ""
    lens_model: str = ""
    focal_length: str = ""
    aperture: str = ""
    shutter_speed: str = ""
    iso: str = ""
    date_taken: str = ""

    @property
    def has_any(self) -> bool:
        return any([
            self.camera_make, self.camera_model, self.lens_model,
            self.focal_length, self.aperture, self.shutter_speed,
            self.iso, self.date_taken,
        ])

    @property
    def camera_line(self) -> str:
        parts = [p for p in [self.camera_model, self.lens_model] if p]
        return "  ".join(parts)

    @property
    def params_line(self) -> str:
        parts = [p for p in [self.focal_length, self.aperture, self.shutter_speed, self.iso] if p]
        return "  |  ".join(parts)


@dataclass(frozen=True)
class Photo:
    file_path: Path
    image: object  # PIL.Image.Image (not typed to avoid import issues)
    exif: ExifData

    @property
    def size(self) -> tuple[int, int]:
        return self.image.size  # (width, height)
