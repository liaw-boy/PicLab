"""
Design system tokens — supports Dark, Light, and Paper (手繪草稿) themes.

Usage:
    from src.gui import theme as T
    T.BG          # current background
    T.PRIMARY     # current primary colour

Switching themes:
    T.apply_dark()   # switch to dark
    T.apply_light()  # switch to light
    T.apply_paper()  # switch to paper wireframe style
"""

# ── Token dictionaries ────────────────────────────────────────────────────────

# Paper Wireframe — 手繪草稿設計語言
# 靈感：Paper Wireframe Kit (Figma Community)
# 特點：米紙底色、炭黑邊框、反色選取、無漸層無陰影
_PAPER = dict(
    PRIMARY         = "#1c1c1c",       # 炭黑：主色 = 邊框色（無彩色系）
    PRIMARY_HOVER   = "#3a3a3a",
    PRIMARY_PRESSED = "#000000",
    PRIMARY_ALPHA   = "rgba(28,28,28,0.10)",
    PRIMARY_LIGHT   = "rgba(28,28,28,0.08)",

    BG              = "#f5f0e8",       # 米紙：主背景
    SURFACE         = "#ede8df",       # 紙面：卡片/面板
    SURFACE_2       = "#e2dbd0",       # 稍深紙面
    SURFACE_3       = "#d4cdc2",       # 更深紙面（按下狀態）
    MENUBAR         = "#f0ece3",       # 工具列
    SIDEBAR         = "#f0ece3",       # 側邊欄
    IMG_LIST_BG     = "#e8e2d8",       # 縮圖列

    BORDER          = "#1c1c1c",       # 炭黑：主邊框（粗實線感）
    BORDER_LIGHT    = "#5a5a5a",       # 次邊框（灰色）
    BORDER_FOCUS    = "#1c1c1c",

    TEXT_PRIMARY    = "#1c1c1c",       # 主文字（近黑）
    TEXT_SECONDARY  = "#5a5a5a",       # 次文字（深灰）
    TEXT_MUTED      = "#8a8a8a",       # 弱化文字
    TEXT_DISABLED   = "#b4ada5",       # 停用文字
    TEXT_ON_PRIMARY = "#f5f0e8",       # 深底上的文字

    PREVIEW_BG      = "#cdc7bc",       # 預覽區：稍深的紙色

    DANGER          = "#c0392b",
    SUCCESS         = "#27ae60",
    WARNING         = "#e67e22",
)

_DARK = dict(
    PRIMARY         = "#4b96f7",
    PRIMARY_HOVER   = "#6baaf9",
    PRIMARY_PRESSED = "#2e74d5",
    PRIMARY_ALPHA   = "rgba(75,150,247,0.15)",
    PRIMARY_LIGHT   = "rgba(75,150,247,0.12)",

    BG              = "#0c0c0e",
    SURFACE         = "#18181b",
    SURFACE_2       = "#27272a",
    SURFACE_3       = "#3f3f46",
    MENUBAR         = "#111113",
    SIDEBAR         = "#111113",
    IMG_LIST_BG     = "#0c0c0e",

    BORDER          = "#27272a",
    BORDER_LIGHT    = "#3f3f46",
    BORDER_FOCUS    = "#4b96f7",

    TEXT_PRIMARY    = "#fafafa",
    TEXT_SECONDARY  = "#a1a1aa",
    TEXT_MUTED      = "#52525b",
    TEXT_DISABLED   = "#3f3f46",
    TEXT_ON_PRIMARY = "#ffffff",

    PREVIEW_BG      = "#111111",

    DANGER          = "#f87171",
    SUCCESS         = "#4ade80",
    WARNING         = "#fbbf24",
)

_LIGHT = dict(
    PRIMARY         = "#2563eb",
    PRIMARY_HOVER   = "#1d4ed8",
    PRIMARY_PRESSED = "#1e40af",
    PRIMARY_ALPHA   = "rgba(37,99,235,0.10)",
    PRIMARY_LIGHT   = "rgba(37,99,235,0.08)",

    BG              = "#fafafa",
    SURFACE         = "#ffffff",
    SURFACE_2       = "#f4f4f5",
    SURFACE_3       = "#e4e4e7",
    MENUBAR         = "#ffffff",
    SIDEBAR         = "#fafafa",
    IMG_LIST_BG     = "#f4f4f5",

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

# ── Module-level mutable tokens (default: paper) ─────────────────────────────

PRIMARY         = _PAPER["PRIMARY"]
PRIMARY_HOVER   = _PAPER["PRIMARY_HOVER"]
PRIMARY_PRESSED = _PAPER["PRIMARY_PRESSED"]
PRIMARY_ALPHA   = _PAPER["PRIMARY_ALPHA"]
PRIMARY_LIGHT   = _PAPER["PRIMARY_LIGHT"]

BG              = _PAPER["BG"]
SURFACE         = _PAPER["SURFACE"]
SURFACE_2       = _PAPER["SURFACE_2"]
SURFACE_3       = _PAPER["SURFACE_3"]
MENUBAR         = _PAPER["MENUBAR"]
SIDEBAR         = _PAPER["SIDEBAR"]
IMG_LIST_BG     = _PAPER["IMG_LIST_BG"]

BORDER          = _PAPER["BORDER"]
BORDER_LIGHT    = _PAPER["BORDER_LIGHT"]
BORDER_FOCUS    = _PAPER["BORDER_FOCUS"]

TEXT_PRIMARY    = _PAPER["TEXT_PRIMARY"]
TEXT_SECONDARY  = _PAPER["TEXT_SECONDARY"]
TEXT_MUTED      = _PAPER["TEXT_MUTED"]
TEXT_DISABLED   = _PAPER["TEXT_DISABLED"]
TEXT_ON_PRIMARY = _PAPER["TEXT_ON_PRIMARY"]

PREVIEW_BG      = _PAPER["PREVIEW_BG"]
DANGER          = _PAPER["DANGER"]
SUCCESS         = _PAPER["SUCCESS"]
WARNING         = _PAPER["WARNING"]

_theme = "paper"   # "dark" | "light" | "paper"


def apply_dark() -> None:
    global _theme; _theme = "dark"; _apply(_DARK)

def apply_light() -> None:
    global _theme; _theme = "light"; _apply(_LIGHT)

def apply_paper() -> None:
    global _theme; _theme = "paper"; _apply(_PAPER)

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


# ── Spacing — 4px grid ────────────────────────────────────────────────────────
S1, S2, S3, S4, S5, S6, S8 = 4, 8, 12, 16, 20, 24, 32

# ── Rounding ──────────────────────────────────────────────────────────────────
R_BUTTON, R_CARD, R_INPUT, R_CHIP, R_PILL = 10, 14, 8, 8, 20

# ── Animation (ms) ───────────────────────────────────────────────────────────
ANIM_FAST, ANIM_NORMAL, ANIM_SLOW = 130, 200, 300

# ── Typography ───────────────────────────────────────────────────────────────
FONT_XS, FONT_SM, FONT_BASE, FONT_MD = 13, 15, 16, 17
FONT_LG, FONT_XL, FONT_2XL = 19, 22, 27

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

# ── Shared scrollbar QSS (rebuilt on each theme change, not cached) ───────────

def scrollbar_qss() -> str:
    return f"""
    QScrollBar:vertical {{
        width: 5px; background: transparent; margin: 0;
    }}
    QScrollBar::handle:vertical {{
        background: {BORDER_LIGHT}; border-radius: 2px; min-height: 20px;
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}
    QScrollBar:horizontal {{
        height: 5px; background: transparent; margin: 0;
    }}
    QScrollBar::handle:horizontal {{
        background: {BORDER_LIGHT}; border-radius: 2px; min-width: 20px;
    }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
    QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{ background: none; }}
    """

# Legacy alias kept for any code still using the constant
SCROLLBAR_QSS = scrollbar_qss()
