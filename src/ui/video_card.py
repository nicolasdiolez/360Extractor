"""
Video Card Widget for the job queue.
Modern card-style widget for displaying video jobs with thumbnail.
"""
import os
import cv2
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, 
    QProgressBar, QSizePolicy, QPushButton
)
from PySide6.QtCore import Qt, Signal, QThread, QObject, QSize
from PySide6.QtGui import QPixmap, QImage, QColor, QPainter, QPainterPath


class ThumbnailWorker(QObject):
    """Worker to generate video thumbnails in background."""
    finished = Signal(QPixmap)
    
    def __init__(self, video_path, size=80):
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
            cap = cv2.VideoCapture(self.video_path)
            if not cap.isOpened():
                self.finished.emit(QPixmap())
                return
                
            ret, frame = cap.read()
            cap.release()
            
            if not ret or self._is_cancelled:
                self.finished.emit(QPixmap())
                return
                
            # Convert and resize
            h, w = frame.shape[:2]
            # Crop to square from center
            if w > h:
                x = (w - h) // 2
                frame = frame[:, x:x+h]
            else:
                y = (h - w) // 2
                frame = frame[y:y+w, :]
                
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
            print(f"Thumbnail error: {e}")
            self.finished.emit(QPixmap())


class VideoCard(QWidget):
    """
    A modern card widget representing a video job in the queue.
    """
    clicked = Signal()
    remove_clicked = Signal()
    
    STATUS_COLORS = {
        "Pending": "#52525B",
        "Processing": "#3B82F6", 
        "Done": "#22C55E",
        "Error": "#EF4444"
    }
    
    def __init__(self, job, parent=None):
        super().__init__(parent)
        self.job = job
        self._selected = False
        self._thread = None
        self._worker = None
        
        self.setObjectName("videoCard")
        self.setFixedHeight(90)
        self.setMinimumWidth(250)
        self.setCursor(Qt.PointingHandCursor)
        
        self._update_style()
        
        # Main layout
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(12)
        
        # Thumbnail
        self._thumbnail = QLabel()
        self._thumbnail.setFixedSize(70, 70)
        self._thumbnail.setStyleSheet("""
            background-color: #252529;
            border-radius: 8px;
        """)
        self._thumbnail.setAlignment(Qt.AlignCenter)
        self._thumbnail.setText("📹")
        layout.addWidget(self._thumbnail)
        
        # Info container
        info_layout = QVBoxLayout()
        info_layout.setSpacing(4)
        
        # Filename
        self._name_label = QLabel(job.filename)
        self._name_label.setStyleSheet("color: #FFFFFF; font-size: 13px; font-weight: 500;")
        self._name_label.setWordWrap(False)
        info_layout.addWidget(self._name_label)
        
        # Status badge
        status_layout = QHBoxLayout()
        status_layout.setSpacing(6)
        
        self._status_dot = QLabel("●")
        self._status_label = QLabel(job.status)
        self._status_label.setStyleSheet("color: #A1A1AA; font-size: 11px;")
        status_layout.addWidget(self._status_dot)
        status_layout.addWidget(self._status_label)
        status_layout.addStretch()
        
        info_layout.addLayout(status_layout)
        
        # Settings summary
        self._summary_label = QLabel(job.summary())
        self._summary_label.setStyleSheet("color: #52525B; font-size: 10px;")
        info_layout.addWidget(self._summary_label)
        
        # Progress bar (hidden by default)
        self._progress = QProgressBar()
        self._progress.setFixedHeight(4)
        self._progress.setTextVisible(False)
        self._progress.setStyleSheet("""
            QProgressBar {
                background-color: #27272A;
                border: none;
                border-radius: 2px;
            }
            QProgressBar::chunk {
                background-color: #3B82F6;
                border-radius: 2px;
            }
        """)
        self._progress.hide()
        info_layout.addWidget(self._progress)
        
        layout.addLayout(info_layout, 1)
        
        # Remove button
        self._remove_btn = QPushButton("✕")
        self._remove_btn.setFixedSize(24, 24)
        self._remove_btn.setCursor(Qt.PointingHandCursor)
        self._remove_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #52525B;
                border: none;
                font-size: 14px;
            }
            QPushButton:hover {
                color: #EF4444;
            }
        """)
        self._remove_btn.clicked.connect(self.remove_clicked.emit)
        layout.addWidget(self._remove_btn, alignment=Qt.AlignTop)
        
        # Load thumbnail async
        self._load_thumbnail()
        
        # Update status styling
        self.update_status(job.status)
        
    def _update_style(self):
        if self._selected:
            self.setStyleSheet("""
                QWidget#videoCard {
                    background-color: #1E1E22;
                    border: 2px solid #3B82F6;
                    border-radius: 12px;
                }
            """)
        else:
            self.setStyleSheet("""
                QWidget#videoCard {
                    background-color: #161618;
                    border: 1px solid #27272A;
                    border-radius: 12px;
                }
                QWidget#videoCard:hover {
                    background-color: #1A1A1D;
                    border-color: #3B82F6;
                }
            """)
    
    def _cleanup_thread(self):
        """Safely cleanup the thumbnail loading thread."""
        if self._worker:
            self._worker.cancel()
            self._worker = None
        if self._thread and self._thread.isRunning():
            self._thread.quit()
            self._thread.wait(1000)  # Wait max 1 second
            self._thread = None
            
    def _load_thumbnail(self):
        """Load video thumbnail in background thread."""
        # Cleanup any existing thread first
        self._cleanup_thread()
        
        self._thread = QThread()
        self._worker = ThumbnailWorker(self.job.file_path)
        self._worker.moveToThread(self._thread)
        
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._set_thumbnail)
        self._worker.finished.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.finished.connect(lambda: setattr(self, '_thread', None))
        
        self._thread.start()
        
    def _set_thumbnail(self, pixmap):
        if not pixmap.isNull():
            # Create rounded pixmap
            rounded = QPixmap(pixmap.size())
            rounded.fill(Qt.transparent)
            
            painter = QPainter(rounded)
            painter.setRenderHint(QPainter.Antialiasing)
            
            path = QPainterPath()
            path.addRoundedRect(0, 0, pixmap.width(), pixmap.height(), 8, 8)
            painter.setClipPath(path)
            painter.drawPixmap(0, 0, pixmap)
            painter.end()
            
            self._thumbnail.setPixmap(rounded)
            self._thumbnail.setText("")
            
    def setSelected(self, selected):
        self._selected = selected
        self._update_style()
        
    def isSelected(self):
        return self._selected
        
    def update_status(self, status):
        self.job.status = status
        self._status_label.setText(status)
        
        color = self.STATUS_COLORS.get(status, "#52525B")
        self._status_dot.setStyleSheet(f"color: {color}; font-size: 8px;")
        
        # Show/hide progress
        if status == "Processing":
            self._progress.show()
        else:
            self._progress.hide()
            
    def set_progress(self, value):
        self._progress.setValue(value)
        
    def refresh(self):
        """Refresh display from job data."""
        self._name_label.setText(self.job.filename)
        self._summary_label.setText(self.job.summary())
        self.update_status(self.job.status)
        
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)
        
    def __del__(self):
        """Destructor to ensure cleanup."""
        self._cleanup_thread()

