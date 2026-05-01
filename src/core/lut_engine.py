"""
lut_engine.py — 3D LUT 解析與套用引擎

支援標準 Adobe .cube 格式（LUT_3D_SIZE N）。
使用 numpy 向量化三線性插值，效能足夠後製用途。

公開 API：
  load(path)              → LutData（解析並快取）
  apply(img, lut, opacity)→ PIL.Image
  clear_cache()           → 清除快取
"""
from __future__ import annotations

from pathlib import Path
from typing import NamedTuple

import numpy as np
from PIL import Image


class LutData(NamedTuple):
    size: int
    table: np.ndarray   # shape (size, size, size, 3), dtype float32, 0.0-1.0


# ── 快取 ─────────────────────────────────────────────────────────────────────

_cache: dict[str, LutData] = {}


def clear_cache() -> None:
    _cache.clear()


# ── 解析 ─────────────────────────────────────────────────────────────────────

def load(path: Path | str) -> LutData:
    """解析 .cube 檔，回傳 LutData（結果被快取）。"""
    key = str(Path(path).resolve())
    if key in _cache:
        return _cache[key]

    lut = _parse_cube(Path(path))
    _cache[key] = lut
    return lut


def _parse_cube(path: Path) -> LutData:
    size = 0
    data_rows: list[tuple[float, float, float]] = []

    with path.open("r", encoding="utf-8", errors="replace") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if line.upper().startswith("LUT_3D_SIZE"):
                size = int(line.split()[-1])
                continue
            # 跳過其他關鍵字行（TITLE, DOMAIN_MIN/MAX…）
            try:
                parts = line.split()
                if len(parts) == 3:
                    data_rows.append((float(parts[0]), float(parts[1]), float(parts[2])))
            except ValueError:
                continue

    if size == 0 or len(data_rows) != size ** 3:
        raise ValueError(
            f"無效 .cube 檔：size={size}, rows={len(data_rows)}，"
            f"預期 {size**3 if size else '?'} 行"
        )

    # .cube 儲存順序：R 最快變化，B 最慢變化
    arr = np.array(data_rows, dtype=np.float32)   # (N³, 3)
    table = arr.reshape(size, size, size, 3)       # (B, G, R, 3) — 依 .cube 慣例
    return LutData(size=size, table=table)


# ── 套用 ─────────────────────────────────────────────────────────────────────

def apply(img: Image.Image, lut: LutData, opacity: float = 1.0) -> Image.Image:
    """
    對 PIL.Image 套用 3D LUT，opacity 0.0-1.0。
    回傳新的 RGB PIL.Image，原圖不受影響。
    """
    if opacity <= 0.0:
        return img.copy()

    rgb = np.asarray(img.convert("RGB"), dtype=np.float32) / 255.0
    H, W, _ = rgb.shape
    pixels = rgb.reshape(-1, 3)   # (N, 3)  — R, G, B

    size = lut.size
    # table shape is (B, G, R, 3) — .cube stores R fastest, B slowest,
    # so after reshape axis-0=B, axis-1=G, axis-2=R. Access as table[b, g, r].
    table = lut.table

    # 座標 0.0-1.0 → 索引 0.0-(size-1)
    s1 = size - 1
    coords = pixels * s1           # (N, 3)  — columns: R, G, B

    r0 = np.floor(coords[:, 0]).astype(np.int32).clip(0, s1 - 1)
    g0 = np.floor(coords[:, 1]).astype(np.int32).clip(0, s1 - 1)
    b0 = np.floor(coords[:, 2]).astype(np.int32).clip(0, s1 - 1)
    r1, g1, b1 = (r0 + 1).clip(0, s1), (g0 + 1).clip(0, s1), (b0 + 1).clip(0, s1)

    # 小數部分（用於插值權重）
    dr = (coords[:, 0] - r0).reshape(-1, 1)
    dg = (coords[:, 1] - g0).reshape(-1, 1)
    db = (coords[:, 2] - b0).reshape(-1, 1)

    # 三線性插值：8 個角點（索引順序 table[b, g, r]）
    c000 = table[b0, g0, r0]
    c100 = table[b0, g0, r1]
    c010 = table[b0, g1, r0]
    c110 = table[b0, g1, r1]
    c001 = table[b1, g0, r0]
    c101 = table[b1, g0, r1]
    c011 = table[b1, g1, r0]
    c111 = table[b1, g1, r1]

    out = (
        c000 * (1 - dr) * (1 - dg) * (1 - db)
        + c100 * dr       * (1 - dg) * (1 - db)
        + c010 * (1 - dr) * dg       * (1 - db)
        + c110 * dr       * dg       * (1 - db)
        + c001 * (1 - dr) * (1 - dg) * db
        + c101 * dr       * (1 - dg) * db
        + c011 * (1 - dr) * dg       * db
        + c111 * dr       * dg       * db
    )   # (N, 3)

    out = out.reshape(H, W, 3).clip(0.0, 1.0)

    if opacity < 1.0:
        out = rgb * (1.0 - opacity) + out * opacity

    result = (out * 255.0 + 0.5).astype(np.uint8)
    return Image.fromarray(result, mode="RGB")
