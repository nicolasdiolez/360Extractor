"""
Video Card Widget for the 360 Extractor Studio queue.
Modern card-style widget for displaying video jobs with thumbnail and metadata chips.
"""
from __future__ import annotations

import cv2
from PySide6.QtCore import QObject, Qt, QThread, Signal
from PySide6.QtGui import QImage, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QProgressBar, QPushButton,
    QVBoxLayout, QWidget
)

from extractor360.ui.icons import get_icon, get_pixmap
from extractor360.utils.logger import logger


class ThumbnailWorker(QObject):
    """Worker to generate video thumbnails in background."""
    finished = Signal(QPixmap)

    def __init__(self, video_path: str, size: int = 64):
        super().__init__()
        self.video_path = video_path
        self.size = size
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        if self._is_cancelled:
            self.finished.emit(QPixmap())
            return

        try:
            is_image = self.video_path.lower().endswith(('.jpg', '.jpeg', '.png', '.tiff', '.tif'))
            if is_image:
                frame = cv2.imread(self.video_path)
                if frame is None or self._is_cancelled:
                    self.finished.emit(QPixmap())
                    return
            else:
                cap = cv2.VideoCapture(self.video_path)
                if not cap.isOpened():
                    self.finished.emit(QPixmap())
                    return

                ret, frame = cap.read()
                cap.release()

                if not ret or self._is_cancelled or frame is None:
                    self.finished.emit(QPixmap())
                    return

            # Crop to square from center and resize
            h, w = frame.shape[:2]
            if w > h:
                x = (w - h) // 2
                frame = frame[:, x:x + h]
            else:
                y = (h - w) // 2
                frame = frame[y:y + w, :]

            frame = cv2.resize(frame, (self.size, self.size))
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            h, w, ch = frame.shape
            img = QImage(frame.data, w, h, ch * w, QImage.Format_RGB888)
            pixmap = QPixmap.fromImage(img)

            if not self._is_cancelled:
                self.finished.emit(pixmap)
            else:
                self.finished.emit(QPixmap())

        except Exception as e:
            logger.error(f"Thumbnail error: {e}")
            self.finished.emit(QPixmap())


class VideoCard(QWidget):
    """Studio Video Card widget in Queue."""
    clicked = Signal()
    ctrl_clicked = Signal()
    remove_clicked = Signal()
    open_folder_clicked = Signal()

    STATUS_COLORS = {
        "Pending": "#71717A",
        "Processing": "#F59E0B",
        "Done": "#10B981",
        "Error": "#EF4444",
    }

    def __init__(self, job, parent=None):
        super().__init__(parent)
        self.job = job
        self._selected = False
        self._thread = None
        self._worker = None

        self.setObjectName("videoCard")
        self.setFixedHeight(76)
        self.setMinimumWidth(220)
        self.setCursor(Qt.PointingHandCursor)

        # Main layout
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(10)

        # Thumbnail
        self._thumbnail = QLabel()
        self._thumbnail.setFixedSize(54, 54)
        self._thumbnail.setStyleSheet("""
            background-color: #15151A;
            border: 1px solid #282833;
            border-radius: 5px;
        """)
        self._thumbnail.setAlignment(Qt.AlignCenter)
        self._thumbnail.setPixmap(get_pixmap("video", color="#4E4E5A", size=20))
        layout.addWidget(self._thumbnail)

        # Info container
        info_layout = QVBoxLayout()
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(2)

        # Filename
        self._name_label = QLabel(job.filename)
        self._name_label.setStyleSheet("color: #E6E6EA; font-size: 11px; font-weight: 600;")
        self._name_label.setWordWrap(False)
        info_layout.addWidget(self._name_label)

        # Status badge + meta summary
        status_layout = QHBoxLayout()
        status_layout.setSpacing(5)

        self._status_dot = QLabel("●")
        self._status_dot.setStyleSheet("color: #71717A; font-size: 8px;")
        self._status_label = QLabel(job.status)
        self._status_label.setStyleSheet("color: #8E8E98; font-size: 10px;")
        status_layout.addWidget(self._status_dot)
        status_layout.addWidget(self._status_label)

        self._summary_label = QLabel(f"• {job.summary()}")
        self._summary_label.setStyleSheet("color: #6E6E78; font-size: 10px;")
        status_layout.addWidget(self._summary_label)

        status_layout.addStretch()

        self._folder_btn = QPushButton("Open")
        self._folder_btn.setCursor(Qt.PointingHandCursor)
        self._folder_btn.setToolTip("Open output folder")
        self._folder_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #10B981;
                border: none;
                font-size: 10px;
                font-weight: 600;
            }
            QPushButton:hover { color: #34D399; }
        """)
        self._folder_btn.clicked.connect(self.open_folder_clicked.emit)
        self._folder_btn.hide()
        status_layout.addWidget(self._folder_btn)

        info_layout.addLayout(status_layout)

        # Progress bar
        self._progress = QProgressBar()
        self._progress.setFixedHeight(3)
        self._progress.setTextVisible(False)
        self._progress.setStyleSheet("""
            QProgressBar {
                background-color: #24242E;
                border: none;
                border-radius: 1.5px;
            }
            QProgressBar::chunk {
                background-color: #F59E0B;
                border-radius: 1.5px;
            }
        """)
        self._progress.hide()
        info_layout.addWidget(self._progress)

        layout.addLayout(info_layout, 1)

        # Remove button
        self._remove_btn = QPushButton("")
        self._remove_btn.setIcon(get_icon("x", color="#6E6E78", size=13))
        self._remove_btn.setFixedSize(20, 20)
        self._remove_btn.setCursor(Qt.PointingHandCursor)
        self._remove_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
            }
            QPushButton:hover {
                background-color: rgba(239, 68, 68, 0.15);
                border-radius: 3px;
            }
        """)
        self._remove_btn.clicked.connect(self.remove_clicked.emit)
        layout.addWidget(self._remove_btn, alignment=Qt.AlignTop)

        self._update_style()
        self._load_thumbnail()
        self.update_status(job.status)

    def _update_style(self):
        self.setProperty("selected", self._selected)
        self.style().polish(self)
        if self._selected:
            self._name_label.setStyleSheet("color: #FFFFFF; font-size: 11px; font-weight: 600;")
        else:
            self._name_label.setStyleSheet("color: #E6E6EA; font-size: 11px; font-weight: 600;")

    def _cleanup_thread(self):
        if self._worker:
            self._worker.cancel()
            self._worker = None
        if self._thread and self._thread.isRunning():
            self._thread.quit()
            self._thread.wait(500)
            self._thread = None

    def _load_thumbnail(self):
        self._cleanup_thread()
        self._thread = QThread()
        self._worker = ThumbnailWorker(self.job.file_path, size=54)
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._set_thumbnail)
        self._worker.finished.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.finished.connect(lambda: setattr(self, '_thread', None))
        self._thread.start()

    def _set_thumbnail(self, pixmap: QPixmap):
        if not pixmap.isNull():
            rounded = QPixmap(pixmap.size())
            rounded.fill(Qt.transparent)

            painter = QPainter(rounded)
            painter.setRenderHint(QPainter.Antialiasing)
            path = QPainterPath()
            path.addRoundedRect(0, 0, pixmap.width(), pixmap.height(), 4, 4)
            painter.setClipPath(path)
            painter.drawPixmap(0, 0, pixmap)
            painter.end()

            self._thumbnail.setPixmap(rounded)
            self._thumbnail.setText("")

    def setSelected(self, selected: bool):
        self._selected = selected
        self._update_style()

    def isSelected(self) -> bool:
        return self._selected

    def update_status(self, status: str):
        self.job.status = status
        self._status_label.setText(status)

        color = self.STATUS_COLORS.get(status, "#71717A")
        self._status_dot.setStyleSheet(f"color: {color}; font-size: 8px;")

        if status == "Processing":
            self._progress.show()
        else:
            self._progress.hide()

        self._folder_btn.setVisible(status == "Done")

    def set_progress(self, value: int):
        self._progress.setValue(value)

    def refresh(self):
        self._name_label.setText(self.job.filename)
        self._summary_label.setText(f"• {self.job.summary()}")
        self.update_status(self.job.status)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            if event.modifiers() & Qt.ControlModifier:
                self.ctrl_clicked.emit()
            else:
                self.clicked.emit()
        super().mousePressEvent(event)

    def __del__(self):
        self._cleanup_thread()
