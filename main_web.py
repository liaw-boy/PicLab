"""
PicLab Cinema — Web-based UI prototype entry point.

底層邏輯：QWebEngineView 載入 src/gui/web/index.html（Stitch design），
PyBridge 透過 QWebChannel 暴露給 JS。所有影像處理仍走 src.core 既有管線。

執行：
    python3 main_web.py
"""
from __future__ import annotations

import sys
from pathlib import Path

from PyQt6.QtCore import QUrl, Qt
from PyQt6.QtGui import QFont, QFontDatabase, QIcon
from PyQt6.QtWebChannel import QWebChannel
from PyQt6.QtWebEngineCore import QWebEngineSettings
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget

from src.gui.web_bridge import PyBridge


WEB_ROOT = Path(__file__).parent / "src" / "gui" / "web"


class WebMainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("PicLab Cinema")
        self.resize(1440, 900)
        self.setMinimumSize(1120, 720)

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.view = QWebEngineView()
        self.bridge = PyBridge(self)
        self.channel = QWebChannel(self)
        self.channel.registerObject("bridge", self.bridge)
        self.view.page().setWebChannel(self.channel)

        # Allow the page to access remote fonts/Tailwind CDN.
        settings = self.view.settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)

        index_path = WEB_ROOT / "index.html"
        if not index_path.is_file():
            raise FileNotFoundError(f"Missing web UI: {index_path}")
        self.view.load(QUrl.fromLocalFile(str(index_path)))

        layout.addWidget(self.view)
        self.setCentralWidget(central)


def main() -> None:
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setApplicationName("PicLab Cinema")
    app.setOrganizationName("PicLab")

    # Optional: load embedded fonts so QFileDialog/native widgets match.
    assets = Path(__file__).parent / "src" / "assets" / "fonts"
    for fname in ("NotoSansTC.ttf", "SourceCodePro-Regular.ttf"):
        fp = assets / fname
        if fp.exists():
            QFontDatabase.addApplicationFont(str(fp))

    base_font = QFont("Noto Sans TC, Inter, sans-serif")
    base_font.setPixelSize(13)
    app.setFont(base_font)

    window = WebMainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
