"""Instagram publish dialog."""
from __future__ import annotations

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit,
    QPushButton, QProgressBar, QMessageBox, QFrame,
)

from src.core.ig_publisher import IGPublisher


class _PublishWorker(QThread):
    finished = pyqtSignal(bool, str)  # success, post_id or error

    def __init__(self, publisher: IGPublisher, image_path: str, caption: str) -> None:
        super().__init__()
        self._publisher = publisher
        self._image_path = image_path
        self._caption = caption

    def run(self) -> None:
        result = self._publisher.publish(self._image_path, self._caption)
        self.finished.emit(result.success, result.post_id if result.success else result.error)


class PublishDialog(QDialog):
    def __init__(self, image_path: str, preview_pixmap: QPixmap | None = None, parent=None) -> None:
        super().__init__(parent)
        self._image_path = image_path
        self._publisher = IGPublisher()
        self._worker: _PublishWorker | None = None
        self._build_ui(preview_pixmap)
        self.setWindowTitle("發布到 Instagram")
        self.setMinimumWidth(480)
        self.setModal(True)

    def _build_ui(self, pixmap: QPixmap | None) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        # 預覽縮圖
        if pixmap:
            thumb_label = QLabel()
            scaled = pixmap.scaled(200, 200, Qt.AspectRatioMode.KeepAspectRatio,
                                   Qt.TransformationMode.SmoothTransformation)
            thumb_label.setPixmap(scaled)
            thumb_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(thumb_label)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #3d3d3d;")
        layout.addWidget(sep)

        # Caption 輸入
        caption_label = QLabel("貼文說明（Caption）")
        caption_label.setStyleSheet("font-weight: 600; font-size: 13px;")
        layout.addWidget(caption_label)

        self._caption_edit = QTextEdit()
        self._caption_edit.setPlaceholderText("輸入貼文內容和 hashtag…")
        self._caption_edit.setFixedHeight(120)
        self._caption_edit.setStyleSheet("""
            QTextEdit {
                background: #2d2d2d;
                border: 1px solid #3d3d3d;
                border-radius: 6px;
                padding: 8px;
                font-size: 13px;
                color: #f5f5f7;
            }
        """)
        layout.addWidget(self._caption_edit)

        # 字數提示
        self._char_label = QLabel("0 / 2200")
        self._char_label.setStyleSheet("color: #86868b; font-size: 11px;")
        self._char_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addWidget(self._char_label)
        self._caption_edit.textChanged.connect(self._update_char_count)

        # 進度條（隱藏）
        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.setFixedHeight(4)
        self._progress.setStyleSheet("""
            QProgressBar { border: none; background: #3d3d3d; border-radius: 2px; }
            QProgressBar::chunk { background: #0066cc; border-radius: 2px; }
        """)
        self._progress.hide()
        layout.addWidget(self._progress)

        # 狀態訊息
        self._status_label = QLabel("")
        self._status_label.setStyleSheet("color: #86868b; font-size: 12px;")
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._status_label)

        # 按鈕列
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        cancel_btn = QPushButton("取消")
        cancel_btn.setFixedHeight(36)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background: #3d3d3d; color: #f5f5f7;
                border: none; border-radius: 6px; font-size: 13px;
            }
            QPushButton:hover { background: #4d4d4d; }
        """)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        self._publish_btn = QPushButton("發布到 IG")
        self._publish_btn.setFixedHeight(36)
        self._publish_btn.setStyleSheet("""
            QPushButton {
                background: #0066cc; color: white;
                border: none; border-radius: 6px;
                font-size: 13px; font-weight: 600;
            }
            QPushButton:hover { background: #0077ee; }
            QPushButton:disabled { background: #3d3d3d; color: #86868b; }
        """)
        self._publish_btn.clicked.connect(self._start_publish)
        btn_layout.addWidget(self._publish_btn)

        layout.addLayout(btn_layout)

        if not self._publisher.is_configured():
            self._publish_btn.setEnabled(False)
            self._status_label.setText("⚠️ 尚未設定 IG 帳號設定（.env 缺少設定）")

    def _update_char_count(self) -> None:
        n = len(self._caption_edit.toPlainText())
        self._char_label.setText(f"{n} / 2200")
        if n > 2200:
            self._char_label.setStyleSheet("color: #ff3b30; font-size: 11px;")
        else:
            self._char_label.setStyleSheet("color: #86868b; font-size: 11px;")

    def _start_publish(self) -> None:
        caption = self._caption_edit.toPlainText().strip()
        if len(caption) > 2200:
            QMessageBox.warning(self, "超過字數限制", "貼文說明不能超過 2200 字元")
            return

        self._publish_btn.setEnabled(False)
        self._progress.show()
        self._status_label.setText("上傳圖片中…")

        self._worker = _PublishWorker(self._publisher, self._image_path, caption)
        self._worker.finished.connect(self._on_finished)
        self._worker.start()

    def _on_finished(self, success: bool, value: str) -> None:
        self._progress.hide()
        self._publish_btn.setEnabled(True)

        if success:
            self._status_label.setText(f"✅ 發布成功！貼文 ID: {value}")
            QMessageBox.information(self, "發布成功", "已成功發布到 Instagram！")
            self.accept()
        else:
            self._status_label.setText(f"❌ 發布失敗：{value}")
            self._publish_btn.setEnabled(True)
