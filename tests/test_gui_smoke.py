"""
Smoke tests for PicLab GUI components.
Run with: xvfb-run -a python3 -m pytest tests/test_gui_smoke.py -v
"""
from __future__ import annotations
import sys
import os
import pathlib
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def qapp():
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)
    yield app


def _make_dummy_image():
    from PIL import Image
    return Image.new("RGB", (100, 100), color=(128, 64, 32))


def _make_border_settings():
    from src.models.settings import BorderSettings
    return BorderSettings()


# ── Import sanity ─────────────────────────────────────────────────────────────

def test_import_theme():
    import src.gui.theme as T
    assert hasattr(T, "GOLD")
    assert hasattr(T, "TEXT_SECONDARY")
    assert hasattr(T, "TEXT_PRIMARY")
    assert T.GOLD == "#C5A46A", f"unexpected GOLD: {T.GOLD}"


def test_import_widgets(qapp):
    from src.gui.widgets import SegmentedControl, SectionHeader
    assert SegmentedControl
    assert SectionHeader


def test_import_export_dialog(qapp):
    from src.gui.export_dialog import ExportDialog
    from src.models.settings import BorderSettings
    assert ExportDialog
    assert BorderSettings


def test_import_left_nav(qapp):
    from src.gui.left_nav import LeftNavBar
    assert LeftNavBar


def test_import_top_bar(qapp):
    from src.gui.top_bar import TopBar
    assert TopBar


def test_import_main_window(qapp):
    from src.gui.main_window import MainWindow
    assert MainWindow


# ── Theme token contrast check ────────────────────────────────────────────────

def _luminance(hex_color: str) -> float:
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i+2], 16) / 255 for i in (0, 2, 4))
    def chan(c):
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * chan(r) + 0.7152 * chan(g) + 0.0722 * chan(b)


def _contrast_ratio(fg: str, bg: str) -> float:
    l1 = _luminance(fg)
    l2 = _luminance(bg)
    lighter, darker = max(l1, l2), min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def test_text_primary_contrast_on_surface():
    import src.gui.theme as T
    ratio = _contrast_ratio(T.TEXT_PRIMARY, T.SURFACE)
    assert ratio >= 4.5, f"TEXT_PRIMARY on SURFACE contrast {ratio:.2f} < 4.5"


def test_text_secondary_contrast_on_surface():
    import src.gui.theme as T
    ratio = _contrast_ratio(T.TEXT_SECONDARY, T.SURFACE)
    assert ratio >= 3.0, f"TEXT_SECONDARY on SURFACE contrast {ratio:.2f} < 3.0"


def test_gold_readable_on_dark_bg():
    import src.gui.theme as T
    ratio = _contrast_ratio(T.GOLD, T.BG)
    assert ratio >= 3.0, f"GOLD on BG contrast {ratio:.2f} < 3.0"


def test_text_secondary_more_readable_than_muted():
    import src.gui.theme as T
    sec = _contrast_ratio(T.TEXT_SECONDARY, T.SURFACE)
    mut = _contrast_ratio(T.TEXT_MUTED, T.SURFACE)
    assert sec > mut, "TEXT_SECONDARY should have higher contrast than TEXT_MUTED on SURFACE"


# ── Widget instantiation ──────────────────────────────────────────────────────

def test_segmented_control_instantiation(qapp):
    from src.gui.widgets import SegmentedControl
    w = SegmentedControl([("a", "A"), ("b", "B"), ("c", "C")])
    assert w.current_value() == "a"
    w.set_value("b")
    assert w.current_value() == "b"


def test_export_dialog_instantiation(qapp):
    from src.gui.export_dialog import ExportDialog
    img = _make_dummy_image()
    settings = _make_border_settings()
    dlg = ExportDialog(image=img, settings=settings)
    assert dlg is not None


def test_left_nav_instantiation(qapp):
    from src.gui.left_nav import LeftNavBar
    nav = LeftNavBar()
    assert nav is not None
    nav.show()
    nav.hide()


def test_top_bar_instantiation(qapp):
    from src.gui.top_bar import TopBar
    bar = TopBar()
    assert bar is not None


def test_main_window_instantiation(qapp):
    from src.gui.main_window import MainWindow
    w = MainWindow()
    assert w is not None
    w.show()
    w.hide()


# ── Rounded frame paint event regression ──────────────────────────────────────

def test_rounded_frame_paint_no_crash(qapp):
    """_RoundedFrame.paintEvent must not throw TypeError (QRectF fix)."""
    from PyQt6.QtWidgets import QApplication
    from src.gui.main_window import MainWindow
    import gc

    w = MainWindow()
    w.resize(1200, 800)
    w.show()
    QApplication.processEvents()
    QApplication.processEvents()
    w.hide()
    w.deleteLater()
    QApplication.processEvents()
    gc.collect()


# ── Left nav inactive contrast (source-code audit) ───────────────────────────

def test_left_nav_inactive_icon_uses_secondary(qapp):
    """Inactive nav icons must use TEXT_SECONDARY, not TEXT_MUTED."""
    src_text = pathlib.Path(
        "/home/lbw/project/project_PicLab/src/gui/left_nav.py"
    ).read_text()

    # Confirm the fix: icon_col should reference TEXT_SECONDARY in inactive branch
    assert "icon_col = QColor(T.TEXT_SECONDARY)" in src_text, \
        "Inactive nav state icon_col must use T.TEXT_SECONDARY for readable contrast"
    # Confirm old bad pattern is gone
    assert "icon_col = QColor(T.TEXT_MUTED)" not in src_text, \
        "icon_col must not use TEXT_MUTED (unreadable on dark background)"


# ── main_window QRectF import check ──────────────────────────────────────────

def test_main_window_imports_qrectf():
    """QRectF must be imported in main_window.py for the rounded rect fix."""
    src_text = pathlib.Path(
        "/home/lbw/project/project_PicLab/src/gui/main_window.py"
    ).read_text()
    assert "QRectF" in src_text, "QRectF must be imported in main_window.py"
    assert "QRectF(0.6, 0.6" in src_text, "drawRoundedRect must use QRectF wrapper"


# ── BorderSettings dataclass ──────────────────────────────────────────────────

def test_border_settings_fields():
    from src.models.settings import BorderSettings
    s = _make_border_settings()
    assert hasattr(s, "aspect_ratio")
    assert hasattr(s, "border_preset")
    assert hasattr(s, "output_format")
    assert hasattr(s, "jpeg_quality")
    assert hasattr(s, "bg_color")


# ── Floating overlay widgets (radical redesign) ──────────────────────────────

def test_floating_widgets_import(qapp):
    from src.gui.floating_widgets import (
        DrawerToggle, FloatingDock, FloatingHistogram,
    )
    assert DrawerToggle and FloatingDock and FloatingHistogram


def test_drawer_toggle_state(qapp):
    from src.gui.floating_widgets import DrawerToggle
    t = DrawerToggle()
    assert t.is_expanded() is True
    t.set_expanded(False)
    assert t.is_expanded() is False
    t.set_expanded(True)
    assert t.is_expanded() is True


def test_floating_dock_emits_tool_id(qapp):
    from src.gui.floating_widgets import FloatingDock
    received: list[str] = []
    dock = FloatingDock()
    dock.tool_clicked.connect(received.append)
    # Fire one button programmatically
    btn = dock._buttons["wb"]
    btn.click()
    assert received == ["wb"]


def test_floating_histogram_paint(qapp):
    from src.gui.floating_widgets import FloatingHistogram
    h = FloatingHistogram()
    h.set_data([10.0] * 64, [5.0] * 64, [3.0] * 64)
    h.show()
    qapp.processEvents()
    h.hide()


def test_main_window_no_longer_uses_left_nav(qapp):
    """Radical redesign: LeftNavBar must NOT be instantiated in screen layouts."""
    src_text = pathlib.Path(
        "/home/lbw/project/project_PicLab/src/gui/main_window.py"
    ).read_text()
    # The two old instantiations should be gone from _build_ui
    assert "left_nav1 = LeftNavBar(mode=\"develop\")" not in src_text, \
        "Screen 1 must not instantiate LeftNavBar"
    assert "left_nav2 = LeftNavBar()" not in src_text, \
        "Screen 2 must not instantiate LeftNavBar"


def test_main_window_uses_floating_widgets(qapp):
    src_text = pathlib.Path(
        "/home/lbw/project/project_PicLab/src/gui/main_window.py"
    ).read_text()
    assert "DrawerToggle" in src_text
    assert "FloatingDock" in src_text
    assert "FloatingHistogram" in src_text


def test_main_window_drawer_toggle_collapses_panel(qapp):
    """Clicking drawer toggle animates grade_panel max width to 0."""
    from src.gui.main_window import MainWindow
    w = MainWindow()
    w.resize(1280, 800)
    w.show()
    qapp.processEvents()
    assert w._grade_panel_expanded is True
    initial_max = w._grade_panel.maximumWidth()
    assert initial_max == 320

    w._toggle_drawer(1)
    qapp.processEvents()
    # After toggle, expanded flag flips and animation target is 0
    assert w._grade_panel_expanded is False
    assert w._grade_drawer_anim.endValue() == 0

    w._toggle_drawer(1)
    qapp.processEvents()
    assert w._grade_panel_expanded is True
    assert w._grade_drawer_anim.endValue() == 320
    w.hide()
