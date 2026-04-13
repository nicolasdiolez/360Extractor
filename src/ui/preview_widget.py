import cv2
import numpy as np
from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout, QSizePolicy, QFrame, QHBoxLayout
from PySide6.QtCore import Qt, QRunnable, QThreadPool, QObject, Signal, Slot, QSize
from PySide6.QtGui import QImage, QPixmap, QPainter, QColor, QLinearGradient

from core.geometry import GeometryProcessor
from utils.image_utils import ImageUtils
from ui.icons import get_pixmap

class WorkerSignals(QObject):
    """
    Defines the signals available from a running worker thread.
    """
    result = Signal(QImage)
    blur_score = Signal(float)
    error = Signal(str)

class PreviewWorker(QRunnable):
    """
    Worker thread for generating the preview image.
    """
    def __init__(self, video_path, settings):
        super().__init__()
        self.video_path = video_path
        self.settings = settings
        self.signals = WorkerSignals()

    @Slot()
    def run(self):
        try:
            is_image = self.video_path.lower().endswith(('.jpg', '.jpeg', '.png', '.tiff', '.tif'))
            
            if is_image:
                frame = cv2.imread(self.video_path)
                if frame is None:
                    self.signals.error.emit(f"Could not load image: {self.video_path}")
                    return
            else:
                cap = cv2.VideoCapture(self.video_path)
                if not cap.isOpened():
                    self.signals.error.emit(f"Could not open video: {self.video_path}")
                    return

                # Read first frame (or frame at timestamp 0)
                ret, frame = cap.read()
                cap.release()

                if not ret:
                    self.signals.error.emit("Could not read frame from video")
                    return

            # Source dimensions
            h, w = frame.shape[:2]
            
            # Preview Settings
            fov = self.settings.get('fov', 90)
            pitch_offset = self.settings.get('pitch_offset', 0)
            cam_count = self.settings.get('camera_count', 6)
            res_setting = self.settings.get('resolution', 2048) # Target width for final export
            
            sharpen_enabled = self.settings.get('sharpening_enabled', False)
            sharpen_strength = self.settings.get('sharpening_strength', 0.5)

            # Determine PREVIEW aspect ratio and resolution
            # We want the preview to match the aspect ratio of the final output.
            # Standard pinhole is usually 1:1 or 4:3 or 16:9. 
            # In our case, GeometryProcessor.create_rectilinear_map uses focal length based on dest_w.
            # We'll use a standard preview width (e.g. 1024) and calculate height based on width.
            # If nothing specified, assume square but allow rectangular.
            preview_w = 1024 
            # Height depends on what the user wants. For now, let's keep it 1:1 if for GS datasets, 
            # OR adaptive if we want more "cinematic" previews.
            # Actually, most 360 extraction for photogrammetry is square or 4:3.
            # Let's check if there's an aspect ratio setting (not yet). 
            # Default to square for now but prepare for dynamic.
            preview_h = 1024 

            # Normalize source frame if extremely large
            if w > 4096:
                scale = 4096 / w
                frame = cv2.resize(frame, (4096, int(h * scale)), interpolation=cv2.INTER_AREA)
                h, w = frame.shape[:2]

            # Get the first view configuration
            views = GeometryProcessor.generate_views(cam_count, pitch_offset)
            if not views:
                 self.signals.error.emit("No views generated")
                 return
            
            # Use the first view for preview
            name, yaw, pitch, roll = views[0]

            # Generate maps
            map_x, map_y = GeometryProcessor.create_rectilinear_map(
                src_h=h, src_w=w,
                dest_h=preview_h, dest_w=preview_w,
                fov_deg=fov,
                yaw_deg=yaw,
                pitch_deg=pitch,
                roll_deg=roll
            )

            # Remap
            remapped = cv2.remap(frame, map_x, map_y, cv2.INTER_LINEAR)

            # Apply Sharpening if enabled
            if sharpen_enabled:
                gaussian = cv2.GaussianBlur(remapped, (0, 0), 2.0)
                remapped = cv2.addWeighted(remapped, 1.0 + sharpen_strength, gaussian, -sharpen_strength, 0)

            # Calculate blur score
            blur_score = ImageUtils.calculate_blur_score(remapped)
            self.signals.blur_score.emit(blur_score)

            # Convert to QImage
            rgb_image = cv2.cvtColor(remapped, cv2.COLOR_BGR2RGB)
            rh, rw, ch = rgb_image.shape
            bytes_per_line = ch * rw
            qt_image = QImage(rgb_image.data, rw, rh, bytes_per_line, QImage.Format_RGB888)
            
            self.signals.result.emit(qt_image.copy())

        except Exception as e:
            self.signals.error.emit(str(e))

class EmptyStateWidget(QFrame):
    """A polished empty state widget for the preview area."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("emptyStateWidget")
        
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(20)
        
        self.icon_label = QLabel()
        self.icon_label.setPixmap(get_pixmap("monitor", color="#27272A", size=80))
        self.icon_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.icon_label)
        
        text_layout = QVBoxLayout()
        text_layout.setSpacing(8)
        
        self.title_label = QLabel("No Video Selected")
        self.title_label.setStyleSheet("""
            color: #E4E4E7;
            font-size: 18px;
            font-weight: 600;
        """)
        self.title_label.setAlignment(Qt.AlignCenter)
        text_layout.addWidget(self.title_label)
        
        self.desc_label = QLabel("Select a video from the queue to see a perspective preview.")
        self.desc_label.setStyleSheet("""
            color: #71717A;
            font-size: 13px;
        """)
        self.desc_label.setAlignment(Qt.AlignCenter)
        text_layout.addWidget(self.desc_label)
        
        layout.addLayout(text_layout)

class PreviewWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)
        
        # Container for the image
        self.container = QFrame()
        self.container.setObjectName("previewArea")
        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setContentsMargins(0, 0, 0, 0)
        
        self.label = QLabel()
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.label.setMinimumSize(200, 200)
        
        self.container_layout.addWidget(self.label)
        
        # Bottom info bar
        self.info_bar = QWidget()
        self.info_bar.setFixedHeight(40)
        self.info_bar.setStyleSheet("background-color: transparent;")
        info_layout = QHBoxLayout(self.info_bar)
        info_layout.setContentsMargins(16, 0, 16, 0)
        
        self.score_label = QLabel("Blur Score: —")
        self.score_label.setStyleSheet("""
            color: #A1A1AA;
            font-weight: 600;
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        """)
        info_layout.addWidget(self.score_label)
        info_layout.addStretch()
        
        # Resolution badge
        self.res_label = QLabel("")
        self.res_label.setStyleSheet("""
            color: #3B82F6;
            background-color: rgba(59, 130, 246, 0.1);
            border: 1px solid rgba(59, 130, 246, 0.2);
            border-radius: 4px;
            padding: 2px 8px;
            font-size: 10px;
            font-weight: 700;
        """)
        info_layout.addWidget(self.res_label)
        
        self.layout.addWidget(self.container, 1)
        self.layout.addWidget(self.info_bar)
        
        # Empty State
        self.empty_state = EmptyStateWidget(self)
        self.empty_state.setGeometry(0, 0, self.width(), self.height())
        self.empty_state.hide()
        
        self.threadpool = QThreadPool()
        self.cached_image = None
        
        # Initial State
        self.set_empty(True)
        
    def set_empty(self, is_empty):
        if is_empty:
            self.container.hide()
            self.info_bar.hide()
            self.empty_state.show()
            self.empty_state.raise_()
        else:
            self.empty_state.hide()
            self.container.show()
            self.info_bar.show()
            
    def update_preview(self, video_path, settings):
        """
        Starts a background worker to update the preview image.
        """
        if not video_path:
            self.set_empty(True)
            self.cached_image = None
            return
            
        self.set_empty(False)
        self.label.setText("Loading perspective preview...")
        self.label.setStyleSheet("color: #52525B; font-size: 12px;")
        
        worker = PreviewWorker(video_path, settings)
        worker.signals.result.connect(self.display_image)
        worker.signals.blur_score.connect(self.display_blur_score)
        worker.signals.error.connect(self.display_error)
        self.threadpool.start(worker)
        
    def display_blur_score(self, score):
        self.score_label.setText(f"Blur Score: {score:.1f}")

    def display_image(self, image):
        self.cached_image = image
        self.label.setText("")
        self._update_label_pixmap()
        
        # Update resolution badge
        self.res_label.setText(f"{image.width()}x{image.height()}")

    def _update_label_pixmap(self):
        if not self.cached_image:
            return
            
        pixmap = QPixmap.fromImage(self.cached_image)
        if not pixmap.isNull():
            # Fit in label while keeping aspect ratio
            scaled_pixmap = pixmap.scaled(
                self.label.size(), 
                Qt.KeepAspectRatio, 
                Qt.SmoothTransformation
            )
            self.label.setPixmap(scaled_pixmap)

    def display_error(self, error):
        self.label.setText(f"Preview Error:\n{error}")
        self.label.setStyleSheet("color: #EF4444; font-size: 11px;")
        self.label.setPixmap(QPixmap())
        self.cached_image = None
        self.res_label.setText("ERROR")
        
    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.empty_state.setGeometry(0, 0, self.width(), self.height())
        # Re-scale pixmap for better display on resize
        if self.cached_image:
            self._update_label_pixmap()