"""
raw_reader.py — RAW 檔案解碼器

支援各廠牌 RAW 格式（透過 libraw / rawpy）：
  Sony   : .ARW .SRF .SR2
  Canon  : .CR2 .CR3 .CRW
  Nikon  : .NEF .NRW
  Fujifilm: .RAF
  Panasonic: .RW2
  Olympus/OM System: .ORF
  Leica  : .RWL .DNG
  Ricoh/Pentax: .PEF .DNG
  DJI / 通用 : .DNG
  Adobe  : .DNG

提供：
  is_raw(path) → bool
  decode(path) → PIL.Image.Image  (16-bit → 8-bit sRGB)
  decode_thumb(path) → PIL.Image.Image | None  (快速縮圖預覽)
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from PIL import Image

# RAW 副檔名集合（小寫）
RAW_EXTS: frozenset[str] = frozenset({
    ".arw", ".srf", ".sr2",          # Sony
    ".cr2", ".cr3", ".crw",          # Canon
    ".nef", ".nrw",                  # Nikon
    ".raf",                          # Fujifilm
    ".rw2",                          # Panasonic
    ".orf",                          # Olympus / OM System
    ".rwl",                          # Leica
    ".pef",                          # Pentax / Ricoh
    ".dng",                          # Adobe DNG（通用）
    ".3fr",                          # Hasselblad
    ".mef",                          # Mamiya
    ".mrw",                          # Minolta
    ".x3f",                          # Sigma
    ".bay",                          # Casio
    ".kdc", ".dcr",                  # Kodak
    ".erf",                          # Epson
    ".mos",                          # Leaf
    ".iiq",                          # Phase One
})


def is_raw(path: Path | str) -> bool:
    """判斷檔案是否為 RAW 格式。"""
    return Path(path).suffix.lower() in RAW_EXTS


def decode(path: Path | str, use_camera_wb: bool = True,
           half_size: bool = False) -> Image.Image:
    """
    解碼 RAW 檔為 8-bit sRGB PIL.Image。

    參數：
      use_camera_wb: True = 使用相機內建白平衡（推薦），False = 自動白平衡
      half_size:     True = 半尺寸解碼（速度快 4x，用於快速預覽）

    回傳 RGB PIL.Image（已套用基礎色調映射，適合進一步調色）。
    """
    try:
        import rawpy
    except ImportError:
        raise RuntimeError(
            "rawpy 未安裝，請執行：pip install rawpy\n"
            "或：pip install rawpy --break-system-packages"
        )

    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"找不到檔案：{path}")

    with rawpy.imread(str(path)) as raw:
        params = rawpy.Params(
            use_camera_wb   = use_camera_wb,
            use_auto_wb     = not use_camera_wb,
            output_color    = rawpy.ColorSpace.sRGB,
            output_bps      = 8,
            no_auto_bright  = False,
            auto_bright_thr = 0.01,
            half_size       = half_size,
            # 保留高光細節
            highlight       = 1,   # 0=夾緊, 1=忽略, 2=混合, 3-9=重建
            # 去馬賽克：AHD（速度與品質平衡）
            demosaic_algorithm = rawpy.DemosaicAlgorithm.AHD,
        )
        rgb_array = raw.postprocess(params)

    return Image.fromarray(rgb_array, mode="RGB")


def decode_thumb(path: Path | str) -> Optional[Image.Image]:
    """
    快速提取 RAW 內嵌縮圖（JPEG preview）。
    速度極快，不需完整解碼。若無縮圖則回傳 None。
    """
    try:
        import rawpy
    except ImportError:
        return None

    try:
        with rawpy.imread(str(path)) as raw:
            thumb = raw.extract_thumb()
        if thumb.format == rawpy.ThumbFormat.JPEG:
            import io
            return Image.open(io.BytesIO(thumb.data))
        elif thumb.format == rawpy.ThumbFormat.BITMAP:
            return Image.fromarray(thumb.data, mode="RGB")
    except Exception:
        pass
    return None


def decode_preview(path: Path | str) -> Image.Image:
    """
    為 UI 預覽快速解碼：優先使用內嵌縮圖，無縮圖則半尺寸解碼。
    """
    thumb = decode_thumb(path)
    if thumb is not None:
        return thumb
    return decode(path, half_size=True)
