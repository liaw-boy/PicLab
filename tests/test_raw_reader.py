"""Unit tests for src/core/raw_reader.py."""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Import helpers — rawpy may not be installed in CI; mock it so the module
# loads regardless.
# ---------------------------------------------------------------------------
import sys
import types

# Provide a minimal rawpy stub so the import of raw_reader succeeds even when
# the native library is absent.
if "rawpy" not in sys.modules:
    rawpy_stub = types.ModuleType("rawpy")
    rawpy_stub.ColorSpace = MagicMock()
    rawpy_stub.DemosaicAlgorithm = MagicMock()
    rawpy_stub.Params = MagicMock()
    rawpy_stub.ThumbFormat = MagicMock()
    rawpy_stub.imread = MagicMock()
    sys.modules["rawpy"] = rawpy_stub

from src.core.raw_reader import RAW_EXTS, decode, is_raw  # noqa: E402


# ---------------------------------------------------------------------------
# is_raw() — extension detection
# ---------------------------------------------------------------------------

class TestIsRaw:
    # NOTE: Path(".cr3").suffix == "" because Python treats a leading-dot name
    # as a dotfile stem with no extension.  is_raw() is documented to accept a
    # path; the canonical way to test a bare extension is to embed it in a
    # filename, e.g. "photo.cr3".

    def test_cr3_returns_true(self):
        assert is_raw("photo.cr3") is True

    def test_jpg_returns_false(self):
        assert is_raw("photo.jpg") is False

    def test_cr3_uppercase_returns_true(self):
        """is_raw must be case-insensitive."""
        assert is_raw("photo.CR3") is True

    def test_arw_returns_true(self):
        assert is_raw("photo.arw") is True

    def test_full_path_cr3(self):
        """Accepts a full file path, not just an extension."""
        assert is_raw("/photos/shot.CR3") is True

    def test_full_path_jpg(self):
        assert is_raw("/photos/shot.jpg") is False

    def test_empty_string(self):
        """Empty string has no extension → not raw."""
        assert is_raw("") is False

    def test_no_extension(self):
        assert is_raw("README") is False

    def test_png_returns_false(self):
        assert is_raw("photo.png") is False

    def test_dng_returns_true(self):
        assert is_raw("photo.dng") is True

    def test_mixed_case_nef(self):
        assert is_raw("photo.NEF") is True


# ---------------------------------------------------------------------------
# RAW_EXTS — set membership
# ---------------------------------------------------------------------------

class TestRawExts:
    def test_contains_cr3(self):
        assert ".cr3" in RAW_EXTS

    def test_contains_arw(self):
        assert ".arw" in RAW_EXTS

    def test_contains_nef(self):
        assert ".nef" in RAW_EXTS

    def test_is_frozenset(self):
        assert isinstance(RAW_EXTS, frozenset)

    def test_all_lowercase(self):
        """Every extension stored in lowercase."""
        for ext in RAW_EXTS:
            assert ext == ext.lower(), f"Extension {ext!r} is not lowercase"

    def test_jpg_not_in_raw_exts(self):
        assert ".jpg" not in RAW_EXTS

    def test_png_not_in_raw_exts(self):
        assert ".png" not in RAW_EXTS


# ---------------------------------------------------------------------------
# decode() — FileNotFoundError for missing file
# ---------------------------------------------------------------------------

class TestDecode:
    def test_raises_file_not_found_for_nonexistent_path(self, tmp_path):
        missing = tmp_path / "ghost.cr3"
        with pytest.raises(FileNotFoundError):
            decode(missing)

    def test_raises_file_not_found_for_string_path(self, tmp_path):
        missing = str(tmp_path / "ghost.arw")
        with pytest.raises(FileNotFoundError):
            decode(missing)

    def test_decode_calls_rawpy_imread_when_file_exists(self, tmp_path):
        """decode() opens the file with rawpy when it exists.

        rawpy is imported lazily inside decode(), so we patch it through
        sys.modules rather than as a module-level attribute.
        """
        raw_file = tmp_path / "sample.cr3"
        raw_file.write_bytes(b"\x00" * 16)  # minimal fake content

        import numpy as np
        import sys
        import types

        fake_rgb = np.zeros((10, 10, 3), dtype="uint8")

        mock_raw = MagicMock()
        mock_raw.__enter__ = MagicMock(return_value=mock_raw)
        mock_raw.__exit__ = MagicMock(return_value=False)
        mock_raw.postprocess.return_value = fake_rgb

        mock_rawpy = types.ModuleType("rawpy")
        mock_rawpy.imread = MagicMock(return_value=mock_raw)
        mock_rawpy.Params = MagicMock(return_value=MagicMock())
        mock_rawpy.ColorSpace = MagicMock()
        mock_rawpy.DemosaicAlgorithm = MagicMock()

        with patch.dict(sys.modules, {"rawpy": mock_rawpy}):
            from PIL import Image
            result = decode(raw_file)

        mock_rawpy.imread.assert_called_once_with(str(raw_file))
        assert isinstance(result, Image.Image)
