"""SCUNet AI Denoise runner — wraps ONNX inference with auto pad+crop.

底層邏輯：保持模型 stateless，外面包 padding + clipping，讓任意尺寸輸入都能跑。
GPU 優先，無 GPU 時 CPU fallback（同樣 quality，只是慢）。
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import numpy as np
from PIL import Image

log = logging.getLogger(__name__)

MODEL_PATH = Path(__file__).parent.parent.parent / "assets" / "models" / "scunet_color_real_psnr.onnx"
PAD_MULTIPLE = 64  # SCUNet U-Net 4-stage requires 64-multiple input

_session = None
_provider = None


def _get_session():
    """Lazy-init ONNX session, prefer GPU."""
    global _session, _provider
    if _session is not None:
        return _session, _provider

    import onnxruntime as ort
    if not MODEL_PATH.exists():
        raise FileNotFoundError(f"SCUNet model missing: {MODEL_PATH}")

    available = ort.get_available_providers()
    providers = []
    if "CUDAExecutionProvider" in available:
        providers.append("CUDAExecutionProvider")
    providers.append("CPUExecutionProvider")

    sess = ort.InferenceSession(str(MODEL_PATH), providers=providers)
    used = sess.get_providers()[0]
    _session = sess
    _provider = used
    log.info("SCUNet loaded with provider: %s", used)
    return sess, used


def get_provider() -> str:
    """Report which provider is active without forcing init."""
    if _session is None:
        try:
            _get_session()
        except Exception:
            return "unavailable"
    return _provider or "unavailable"


def _pad_to_multiple(arr: np.ndarray, multiple: int = PAD_MULTIPLE):
    n, c, h, w = arr.shape
    new_h = ((h + multiple - 1) // multiple) * multiple
    new_w = ((w + multiple - 1) // multiple) * multiple
    if new_h == h and new_w == w:
        return arr, h, w
    pad_h, pad_w = new_h - h, new_w - w
    return np.pad(arr, ((0,0),(0,0),(0,pad_h),(0,pad_w)), mode="reflect"), h, w


def denoise(img: Image.Image, tile_size: int = 256, overlap: int = 32) -> Image.Image:
    """Apply SCUNet via tiled inference — keeps VRAM usage bounded.

    Splits image into tile_size×tile_size tiles with `overlap` pixels overlap
    on each side, runs SCUNet on each, then linearly blends overlap regions.
    Works for arbitrary input sizes regardless of VRAM.
    """
    sess, _ = _get_session()
    rgb = img.convert("RGB")
    arr = np.asarray(rgb, dtype=np.float32) / 255.0  # H×W×3
    H, W = arr.shape[:2]

    # Pad inputs so tiles align cleanly
    pad_h = (tile_size - H % tile_size) % tile_size
    pad_w = (tile_size - W % tile_size) % tile_size
    arr_p = np.pad(arr, ((0, pad_h), (0, pad_w), (0, 0)), mode="reflect")
    Hp, Wp = arr_p.shape[:2]

    out = np.zeros_like(arr_p)
    weight = np.zeros((Hp, Wp, 1), dtype=np.float32)

    # Linear feathering window for blend
    def make_window(size, pad):
        ramp = np.ones(size, dtype=np.float32)
        if pad > 0:
            r = np.linspace(0, 1, pad, dtype=np.float32)
            ramp[:pad] = r
            ramp[-pad:] = r[::-1]
        return ramp

    win_h = make_window(tile_size + 2 * overlap, overlap)
    win_w = make_window(tile_size + 2 * overlap, overlap)
    win_2d = (win_h[:, None] * win_w[None, :])[:, :, None]

    for ty in range(0, Hp, tile_size):
        for tx in range(0, Wp, tile_size):
            # Extended tile with overlap, padded if at boundary
            y0 = ty - overlap
            x0 = tx - overlap
            y1 = ty + tile_size + overlap
            x1 = tx + tile_size + overlap
            ext_y0 = max(0, y0)
            ext_x0 = max(0, x0)
            ext_y1 = min(Hp, y1)
            ext_x1 = min(Wp, x1)
            tile = arr_p[ext_y0:ext_y1, ext_x0:ext_x1]
            # Pad to consistent size
            pre_pad_y = ext_y0 - y0
            post_pad_y = y1 - ext_y1
            pre_pad_x = ext_x0 - x0
            post_pad_x = x1 - ext_x1
            tile_padded = np.pad(tile, ((pre_pad_y, post_pad_y),
                                         (pre_pad_x, post_pad_x), (0,0)), mode="reflect")
            inp = tile_padded.transpose(2, 0, 1)[None, ...].astype(np.float32)
            denoised = sess.run(None, {"input": inp})[0]
            denoised = denoised[0].transpose(1, 2, 0)  # H'×W'×3

            out[ext_y0:ext_y1, ext_x0:ext_x1] += (
                denoised[pre_pad_y:tile_padded.shape[0]-post_pad_y,
                         pre_pad_x:tile_padded.shape[1]-post_pad_x]
                * win_2d[pre_pad_y:tile_padded.shape[0]-post_pad_y,
                         pre_pad_x:tile_padded.shape[1]-post_pad_x]
            )
            weight[ext_y0:ext_y1, ext_x0:ext_x1] += win_2d[
                pre_pad_y:tile_padded.shape[0]-post_pad_y,
                pre_pad_x:tile_padded.shape[1]-post_pad_x
            ]

    out = out / np.maximum(weight, 1e-8)
    out = out[:H, :W]  # crop padding
    out = np.clip(out, 0, 1) * 255
    return Image.fromarray(out.astype(np.uint8), "RGB")


def is_available() -> bool:
    return MODEL_PATH.exists()
