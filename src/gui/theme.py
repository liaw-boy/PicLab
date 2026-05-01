"""
Design system tokens — supports Dark (dark luxury), Light, and Paper (手繪草稿) themes.

Dark theme uses a dark luxury palette with gold accents extracted from the HTML
design reference. It is the default theme.

Usage:
    from src.gui import theme as T
    T.BG          # current background
    T.PRIMARY     # current primary colour (gold accent in dark mode)
    T.GOLD        # gold accent (#C5A46A) — always available

Switching themes:
    T.apply_dark()   # switch to dark luxury (default)
    T.apply_light()  # switch to light
    T.apply_paper()  # switch to paper wireframe style
"""

# ── Token dictionaries ────────────────────────────────────────────────────────

# Dark Luxury — extracted from HTML design reference
# Palette: deep ink backgrounds, gold accent, minimal borders
_DARK = dict(
    # Primary / accent — gold
    PRIMARY         = "#C5A46A",
    PRIMARY_HOVER   = "#D4B87E",
    PRIMARY_PRESSED = "#A8894F",
    PRIMARY_ALPHA   = "rgba(197,164,106,0.15)",
    PRIMARY_LIGHT   = "rgba(197,164,106,0.07)",

    # Gold accent aliases (same as PRIMARY family, exposed for clarity)
    GOLD            = "#C5A46A",
    GOLD_DIM        = "rgba(197,164,106,0.15)",
    GOLD_GLOW       = "rgba(197,164,106,0.07)",

    # Backgrounds — ink scale (darkest → lightest)
    BG              = "#0B0B0E",   # ink  — app root
    SURFACE         = "#111116",   # ink2 — panels
    SURFACE_2       = "#18181F",   # ink3 — cards / dialogs
    SURFACE_3       = "#21212A",   # ink4 — elevated surfaces
    SURFACE_4       = "#2C2C38",   # ink5 — hover / selected bg

    # Named surface aliases used by layout widgets
    MENUBAR         = "#111116",   # title bar / menu bar
    SIDEBAR         = "#0B0B0E",   # icon sidebar
    IMG_LIST_BG     = "#0B0B0E",   # thumbnail strip

    # Glass overlays
    GLASS_1         = "rgba(255,255,255,0.04)",
    GLASS_2         = "rgba(255,255,255,0.07)",

    # Borders
    BORDER          = "rgba(255,255,255,0.05)",
    BORDER_LIGHT    = "rgba(255,255,255,0.04)",
    BORDER_FOCUS    = "#C5A46A",

    # Text
    TEXT_PRIMARY    = "#EAE8E0",
    TEXT_SECONDARY  = "#9896A0",
    TEXT_MUTED      = "#5C5A66",
    TEXT_DISABLED   = "#3A3840",
    TEXT_ON_PRIMARY = "#0B0B0E",   # dark text on gold button

    # Preview canvas
    PREVIEW_BG      = "#0B0B0E",

    # Semantic colours
    DANGER          = "#F87171",
    SUCCESS         = "#4ADE80",
    WARNING         = "#FBBF24",
)

# Paper Wireframe — 手繪草稿設計語言
# 靈感：Paper Wireframe Kit (Figma Community)
# 特點：米紙底色、炭黑邊框、反色選取、無漸層無陰影
_PAPER = dict(
    PRIMARY         = "#1c1c1c",
    PRIMARY_HOVER   = "#3a3a3a",
    PRIMARY_PRESSED = "#000000",
    PRIMARY_ALPHA   = "rgba(28,28,28,0.10)",
    PRIMARY_LIGHT   = "rgba(28,28,28,0.08)",

    # Gold aliases (neutral in paper mode — same as primary)
    GOLD            = "#1c1c1c",
    GOLD_DIM        = "rgba(28,28,28,0.10)",
    GOLD_GLOW       = "rgba(28,28,28,0.06)",

    BG              = "#f5f0e8",
    SURFACE         = "#ede8df",
    SURFACE_2       = "#e2dbd0",
    SURFACE_3       = "#d4cdc2",
    SURFACE_4       = "#c8c1b6",
    MENUBAR         = "#f0ece3",
    SIDEBAR         = "#f0ece3",
    IMG_LIST_BG     = "#e8e2d8",

    GLASS_1         = "rgba(0,0,0,0.04)",
    GLASS_2         = "rgba(0,0,0,0.07)",

    BORDER          = "#1c1c1c",
    BORDER_LIGHT    = "#5a5a5a",
    BORDER_FOCUS    = "#1c1c1c",

    TEXT_PRIMARY    = "#1c1c1c",
    TEXT_SECONDARY  = "#5a5a5a",
    TEXT_MUTED      = "#8a8a8a",
    TEXT_DISABLED   = "#b4ada5",
    TEXT_ON_PRIMARY = "#f5f0e8",

    PREVIEW_BG      = "#cdc7bc",

    DANGER          = "#c0392b",
    SUCCESS         = "#27ae60",
    WARNING         = "#e67e22",
)

_LIGHT = dict(
    PRIMARY         = "#2563eb",
    PRIMARY_HOVER   = "#1d4ed8",
    PRIMARY_PRESSED = "#1e40af",
    PRIMARY_ALPHA   = "rgba(37,99,235,0.10)",
    PRIMARY_LIGHT   = "rgba(37,99,235,0.08)",

    # Gold aliases (muted warm in light mode)
    GOLD            = "#A07828",
    GOLD_DIM        = "rgba(160,120,40,0.12)",
    GOLD_GLOW       = "rgba(160,120,40,0.06)",

    BG              = "#fafafa",
    SURFACE         = "#ffffff",
    SURFACE_2       = "#f4f4f5",
    SURFACE_3       = "#e4e4e7",
    SURFACE_4       = "#d4d4d8",
    MENUBAR         = "#ffffff",
    SIDEBAR         = "#fafafa",
    IMG_LIST_BG     = "#f4f4f5",

    GLASS_1         = "rgba(0,0,0,0.03)",
    GLASS_2         = "rgba(0,0,0,0.06)",

    BORDER          = "#e4e4e7",
    BORDER_LIGHT    = "#d4d4d8",
    BORDER_FOCUS    = "#2563eb",

    TEXT_PRIMARY    = "#09090b",
    TEXT_SECONDARY  = "#71717a",
    TEXT_MUTED      = "#a1a1aa",
    TEXT_DISABLED   = "#d4d4d8",
    TEXT_ON_PRIMARY = "#ffffff",

    PREVIEW_BG      = "#e4e4e7",

    DANGER          = "#dc2626",
    SUCCESS         = "#16a34a",
    WARNING         = "#d97706",
)

# ── Module-level mutable tokens (default: dark luxury) ───────────────────────

PRIMARY         = _DARK["PRIMARY"]
PRIMARY_HOVER   = _DARK["PRIMARY_HOVER"]
PRIMARY_PRESSED = _DARK["PRIMARY_PRESSED"]
PRIMARY_ALPHA   = _DARK["PRIMARY_ALPHA"]
PRIMARY_LIGHT   = _DARK["PRIMARY_LIGHT"]

# Gold accent system — always keep these in sync with PRIMARY family in dark mode
GOLD            = _DARK["GOLD"]
GOLD_DIM        = _DARK["GOLD_DIM"]
GOLD_GLOW       = _DARK["GOLD_GLOW"]

BG              = _DARK["BG"]
SURFACE         = _DARK["SURFACE"]
SURFACE_2       = _DARK["SURFACE_2"]
SURFACE_3       = _DARK["SURFACE_3"]
SURFACE_4       = _DARK["SURFACE_4"]
MENUBAR         = _DARK["MENUBAR"]
SIDEBAR         = _DARK["SIDEBAR"]
IMG_LIST_BG     = _DARK["IMG_LIST_BG"]

GLASS_1         = _DARK["GLASS_1"]
GLASS_2         = _DARK["GLASS_2"]

BORDER          = _DARK["BORDER"]
BORDER_LIGHT    = _DARK["BORDER_LIGHT"]
BORDER_FOCUS    = _DARK["BORDER_FOCUS"]

TEXT_PRIMARY    = _DARK["TEXT_PRIMARY"]
TEXT_SECONDARY  = _DARK["TEXT_SECONDARY"]
TEXT_MUTED      = _DARK["TEXT_MUTED"]
TEXT_DISABLED   = _DARK["TEXT_DISABLED"]
TEXT_ON_PRIMARY = _DARK["TEXT_ON_PRIMARY"]

PREVIEW_BG      = _DARK["PREVIEW_BG"]
DANGER          = _DARK["DANGER"]
SUCCESS         = _DARK["SUCCESS"]
WARNING         = _DARK["WARNING"]

_theme = "dark"   # "dark" | "light" | "paper"


def apply_dark() -> None:
    global _theme
    _theme = "dark"
    _apply(_DARK)


def apply_light() -> None:
    global _theme
    _theme = "light"
    _apply(_LIGHT)


def apply_paper() -> None:
    global _theme
    _theme = "paper"
    _apply(_PAPER)


def is_dark() -> bool:
    return _theme == "dark"


def is_paper() -> bool:
    return _theme == "paper"


def current_theme() -> str:
    return _theme


def _apply(d: dict) -> None:
    g = globals()
    for k, v in d.items():
        g[k] = v


# ── Layout measurements (from HTML design reference) ─────────────────────────
TITLEBAR_HEIGHT    = 42   # px
SIDEBAR_WIDTH      = 50   # px  (icon sidebar)
RIGHT_PANEL_WIDTH  = 270  # px
PRESETS_BAR_WIDTH  = 180  # px
SIDEBAR_BTN_SIZE   = 34   # px  (width = height)
SIDEBAR_BTN_RADIUS = 7    # px
TAB_HEIGHT         = 28   # px

# ── Spacing — 4px grid ────────────────────────────────────────────────────────
S1, S2, S3, S4, S5, S6, S8 = 4, 8, 12, 16, 20, 24, 32

# ── Rounding ──────────────────────────────────────────────────────────────────
R_BUTTON, R_CARD, R_INPUT, R_CHIP, R_PILL = 7, 10, 6, 6, 20

# ── Animation (ms) ───────────────────────────────────────────────────────────
ANIM_FAST, ANIM_NORMAL, ANIM_SLOW = 130, 200, 300

# ── Typography ───────────────────────────────────────────────────────────────
FONT_XS, FONT_SM, FONT_BASE, FONT_MD = 11, 12, 13, 14
FONT_LG, FONT_XL, FONT_2XL = 16, 18, 22

# ── UI Font family (best available CJK-compatible sans-serif) ─────────────────

def _detect_ui_font() -> str:
    from PyQt6.QtGui import QFontDatabase
    available = set(QFontDatabase.families())
    for family in [
        "Noto Sans CJK TC",     # Linux 繁中（最優先，渲染清晰）
        "PingFang TC",          # macOS 繁中
        "Microsoft JhengHei",   # Windows 繁中
        "Noto Sans TC",         # 備選繁中
        "Microsoft YaHei",      # Windows 簡中
        "Noto Sans CJK SC",     # Linux 簡中備選
        "Ubuntu Sans",          # Linux 通用
        "Segoe UI",             # Windows 通用
    ]:
        if family in available:
            return family
    return "sans-serif"


_UI_FONT_FAMILY: str = ""   # 延遲初始化，第一次呼叫時設定


def ui_font_family() -> str:
    """回傳最佳 UI 字型名稱（需在 QApplication 建立後呼叫）。"""
    global _UI_FONT_FAMILY
    if not _UI_FONT_FAMILY:
        _UI_FONT_FAMILY = _detect_ui_font()
    return _UI_FONT_FAMILY


def ui_font(pixel_size: int, weight=None) -> "QFont":
    """建立統一樣式的 QFont。預設使用 Light 字重。"""
    from PyQt6.QtGui import QFont
    f = QFont(ui_font_family())
    f.setPixelSize(pixel_size)
    if weight is not None:
        f.setWeight(weight)
    return f


# QSS 用字串（在 QSS stylesheet 中嵌入 font-family）
def font_family_css() -> str:
    return ui_font_family()


# ── Scrollbar QSS ─────────────────────────────────────────────────────────────

def scrollbar_qss() -> str:
    """Minimal dark scrollbar — thin track, subtle handle."""
    return f"""
    QScrollBar:vertical {{
        width: 4px;
        background: transparent;
        margin: 0;
        border: none;
    }}
    QScrollBar::handle:vertical {{
        background: {SURFACE_4};
        border-radius: 2px;
        min-height: 24px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: {TEXT_MUTED};
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}
    QScrollBar:horizontal {{
        height: 4px;
        background: transparent;
        margin: 0;
        border: none;
    }}
    QScrollBar::handle:horizontal {{
        background: {SURFACE_4};
        border-radius: 2px;
        min-width: 24px;
    }}
    QScrollBar::handle:horizontal:hover {{
        background: {TEXT_MUTED};
    }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
    QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{ background: none; }}
    """


# ── Sidebar button QSS ────────────────────────────────────────────────────────

def sidebar_button_qss() -> str:
    """Dark sidebar icon button with gold active state."""
    size = SIDEBAR_BTN_SIZE
    radius = SIDEBAR_BTN_RADIUS
    return f"""
    QPushButton {{
        background: transparent;
        border: none;
        border-radius: {radius}px;
        min-width: {size}px;
        max-width: {size}px;
        min-height: {size}px;
        max-height: {size}px;
        color: {TEXT_MUTED};
        padding: 0;
    }}
    QPushButton:hover {{
        background: {GLASS_2};
        color: {TEXT_SECONDARY};
    }}
    QPushButton:pressed {{
        background: {GOLD_DIM};
        color: {GOLD};
    }}
    QPushButton:checked {{
        background: {GOLD_DIM};
        color: {GOLD};
    }}
    """


# ── Tab bar QSS ───────────────────────────────────────────────────────────────

def tab_bar_qss() -> str:
    """Dark tab bar with gold underline on selected tab."""
    tab_h = TAB_HEIGHT
    return f"""
    QTabBar {{
        background: transparent;
        border: none;
    }}
    QTabBar::tab {{
        background: transparent;
        color: {TEXT_MUTED};
        border: none;
        border-bottom: 2px solid transparent;
        padding: 0 {S3}px;
        height: {tab_h}px;
        min-width: 48px;
        font-size: {FONT_SM}px;
    }}
    QTabBar::tab:hover {{
        color: {TEXT_SECONDARY};
        background: {GLASS_1};
    }}
    QTabBar::tab:selected {{
        color: {GOLD};
        border-bottom: 2px solid {GOLD};
        background: transparent;
    }}
    QTabWidget::pane {{
        border: none;
        background: {SURFACE};
    }}
    QTabWidget::tab-bar {{
        alignment: left;
    }}
    """


# ── Slider QSS ────────────────────────────────────────────────────────────────

def slider_qss() -> str:
    """Dark track, gold handle with glow ring."""
    return f"""
    QSlider::groove:horizontal {{
        height: 3px;
        background: {SURFACE_4};
        border-radius: 1px;
    }}
    QSlider::sub-page:horizontal {{
        height: 3px;
        background: {GOLD};
        border-radius: 1px;
    }}
    QSlider::handle:horizontal {{
        background: {GOLD};
        border: 2px solid {GOLD_GLOW};
        width: 12px;
        height: 12px;
        margin: -5px 0;
        border-radius: 6px;
    }}
    QSlider::handle:horizontal:hover {{
        background: {PRIMARY_HOVER};
        border: 2px solid {GOLD_DIM};
    }}
    QSlider::groove:vertical {{
        width: 3px;
        background: {SURFACE_4};
        border-radius: 1px;
    }}
    QSlider::sub-page:vertical {{
        width: 3px;
        background: {GOLD};
        border-radius: 1px;
    }}
    QSlider::handle:vertical {{
        background: {GOLD};
        border: 2px solid {GOLD_GLOW};
        width: 12px;
        height: 12px;
        margin: 0 -5px;
        border-radius: 6px;
    }}
    """


# ── Button QSS ────────────────────────────────────────────────────────────────

def button_qss() -> str:
    """Glass-effect default button + gold primary button."""
    return f"""
    QPushButton {{
        background: {GLASS_1};
        color: {TEXT_SECONDARY};
        border: 1px solid {BORDER};
        border-radius: {R_BUTTON}px;
        padding: {S2}px {S3}px;
        font-size: {FONT_SM}px;
    }}
    QPushButton:hover {{
        background: {GLASS_2};
        color: {TEXT_PRIMARY};
        border-color: {BORDER_LIGHT};
    }}
    QPushButton:pressed {{
        background: {SURFACE_3};
        color: {TEXT_PRIMARY};
    }}
    QPushButton:disabled {{
        color: {TEXT_DISABLED};
        border-color: {BORDER};
        background: transparent;
    }}
    QPushButton[role="primary"] {{
        background: {GOLD};
        color: {TEXT_ON_PRIMARY};
        border: none;
        font-size: {FONT_SM}px;
    }}
    QPushButton[role="primary"]:hover {{
        background: {PRIMARY_HOVER};
    }}
    QPushButton[role="primary"]:pressed {{
        background: {PRIMARY_PRESSED};
    }}
    QPushButton[role="danger"] {{
        background: transparent;
        color: {DANGER};
        border: 1px solid {DANGER};
    }}
    QPushButton[role="danger"]:hover {{
        background: rgba(248,113,113,0.10);
    }}
    """


# ── Full application QSS ──────────────────────────────────────────────────────

def app_qss() -> str:
    """
    Complete application stylesheet using the current theme tokens.
    Call after applying a theme to refresh the QApplication stylesheet.
    """
    font = font_family_css()
    return f"""
    /* ── Global reset ── */
    * {{
        font-family: "{font}", sans-serif;
        font-size: {FONT_SM}px;
        outline: none;
    }}

    QWidget {{
        background: {BG};
        color: {TEXT_PRIMARY};
        border: none;
        selection-background-color: {GOLD_DIM};
        selection-color: {GOLD};
    }}

    /* ── Main window / frames ── */
    QMainWindow, QDialog {{
        background: {BG};
    }}

    QFrame {{
        background: transparent;
    }}

    /* ── Menu bar ── */
    QMenuBar {{
        background: {MENUBAR};
        color: {TEXT_SECONDARY};
        border-bottom: 1px solid {BORDER};
        spacing: 0;
        padding: 0 {S2}px;
    }}
    QMenuBar::item {{
        background: transparent;
        padding: {S2}px {S3}px;
        border-radius: {R_BUTTON}px;
        color: {TEXT_SECONDARY};
    }}
    QMenuBar::item:selected {{
        background: {GLASS_2};
        color: {TEXT_PRIMARY};
    }}
    QMenu {{
        background: {SURFACE_2};
        border: 1px solid {BORDER};
        border-radius: {R_CARD}px;
        padding: {S1}px;
        color: {TEXT_PRIMARY};
    }}
    QMenu::item {{
        padding: {S2}px {S4}px;
        border-radius: {R_BUTTON}px;
    }}
    QMenu::item:selected {{
        background: {GOLD_DIM};
        color: {GOLD};
    }}
    QMenu::separator {{
        height: 1px;
        background: {BORDER};
        margin: {S1}px {S2}px;
    }}

    /* ── Labels ── */
    QLabel {{
        background: transparent;
        color: {TEXT_SECONDARY};
    }}
    QLabel[role="heading"] {{
        color: {TEXT_PRIMARY};
        font-size: {FONT_BASE}px;
    }}
    QLabel[role="muted"] {{
        color: {TEXT_MUTED};
        font-size: {FONT_XS}px;
    }}
    QLabel[role="gold"] {{
        color: {GOLD};
    }}

    /* ── Line edit / spin box ── */
    QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
        background: {SURFACE_2};
        color: {TEXT_PRIMARY};
        border: 1px solid {BORDER};
        border-radius: {R_INPUT}px;
        padding: {S1}px {S2}px;
        selection-background-color: {GOLD_DIM};
        selection-color: {GOLD};
    }}
    QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{
        border-color: {BORDER_FOCUS};
    }}
    QLineEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled {{
        color: {TEXT_DISABLED};
        background: {SURFACE};
    }}

    QComboBox::drop-down {{
        border: none;
        width: {S5}px;
    }}
    QComboBox QAbstractItemView {{
        background: {SURFACE_2};
        border: 1px solid {BORDER};
        border-radius: {R_CARD}px;
        color: {TEXT_PRIMARY};
        selection-background-color: {GOLD_DIM};
        selection-color: {GOLD};
    }}

    /* ── Check box / radio ── */
    QCheckBox, QRadioButton {{
        color: {TEXT_SECONDARY};
        background: transparent;
        spacing: {S2}px;
    }}
    QCheckBox::indicator, QRadioButton::indicator {{
        width: 14px;
        height: 14px;
        border: 1px solid {BORDER_LIGHT};
        border-radius: 3px;
        background: {SURFACE_2};
    }}
    QCheckBox::indicator:checked, QRadioButton::indicator:checked {{
        background: {GOLD};
        border-color: {GOLD};
    }}
    QRadioButton::indicator {{
        border-radius: 7px;
    }}

    /* ── Group box ── */
    QGroupBox {{
        border: 1px solid {BORDER};
        border-radius: {R_CARD}px;
        margin-top: {S4}px;
        padding: {S3}px;
        color: {TEXT_MUTED};
        font-size: {FONT_XS}px;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        subcontrol-position: top left;
        left: {S3}px;
        padding: 0 {S1}px;
        color: {TEXT_MUTED};
    }}

    /* ── Tool tip ── */
    QToolTip {{
        background: {SURFACE_3};
        color: {TEXT_PRIMARY};
        border: 1px solid {BORDER};
        border-radius: {R_BUTTON}px;
        padding: {S1}px {S2}px;
        font-size: {FONT_XS}px;
    }}

    /* ── Status bar ── */
    QStatusBar {{
        background: {MENUBAR};
        color: {TEXT_MUTED};
        border-top: 1px solid {BORDER};
        font-size: {FONT_XS}px;
    }}

    /* ── Splitter ── */
    QSplitter::handle {{
        background: {BORDER};
    }}
    QSplitter::handle:horizontal {{
        width: 1px;
    }}
    QSplitter::handle:vertical {{
        height: 1px;
    }}

    /* ── Scrollbars ── */
    {scrollbar_qss()}

    /* ── Sliders ── */
    {slider_qss()}

    /* ── Tab bar / widget ── */
    {tab_bar_qss()}
    """


# Legacy alias — kept for any code still importing the constant
SCROLLBAR_QSS = scrollbar_qss()
