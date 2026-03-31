import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon, QFont

from src.gui.main_window import MainWindow


def main() -> None:
    # Enable high-DPI scaling
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setApplicationName("Photo Border Tool")
    app.setOrganizationName("PhotoBorder")
    app.setStyle("Fusion")

    # 載入內嵌字型
    from PyQt6.QtGui import QFontDatabase
    from pathlib import Path
    _assets = Path(__file__).parent / "src/assets/fonts"
    for _f in ["NotoSansTC.ttf", "SourceCodePro-Regular.ttf"]:
        _p = _assets / _f
        if _p.exists():
            QFontDatabase.addApplicationFont(str(_p))

    # 設定全域字型（QApplication 建立後才能偵測字型資料庫）
    import src.gui.theme as T
    base_font = QFont(T.ui_font_family())
    base_font.setPixelSize(14)
    app.setFont(base_font)
    # QSS 全域字型 fallback（確保任何 setStyleSheet 也能繼承字型）
    app.setStyleSheet(f"* {{ font-family: '{T.ui_font_family()}'; }}")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
