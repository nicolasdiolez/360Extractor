import cv2
import numpy as np
from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout, QSizePolicy
from PySide6.QtCore import Qt, QRunnable, QThreadPool, QObject, Signal, Slot
from PySide6.QtGui import QImage, QPixmap

from core.geometry import GeometryProcessor
from utils.image_utils import ImageUtils

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

            # Downscale source frame for performance if it's very large
            # We only need enough resolution for a ~512px preview
            h, w = frame.shape[:2]
            if w > 2048:
                new_w = 2048
                new_h = int(h * (new_w / w))
                frame = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_AREA)
                h, w = new_h, new_w

            # Preview settings
            # We generate a fixed size preview map
            dest_w = 512
            dest_h = 512
            fov = self.settings.get('fov', 90)
            pitch_offset = self.settings.get('pitch_offset', 0)
            cam_count = self.settings.get('camera_count', 6)
            
            sharpen_enabled = self.settings.get('sharpening_enabled', False)
            sharpen_strength = self.settings.get('sharpening_strength', 0.5)

            # Get the first view configuration
            views = GeometryProcessor.generate_views(cam_count, pitch_offset)
            if not views:
                 self.signals.error.emit("No views generated")
                 return
            
            # Use the first view for preview to show perspective/pitch changes
            # view format: (name, yaw, pitch, roll)
            name, yaw, pitch, roll = views[0]

            # Generate maps
            map_x, map_y = GeometryProcessor.create_rectilinear_map(
                src_h=h, src_w=w,
                dest_h=dest_h, dest_w=dest_w,
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
            # cv2 is BGR, QImage needs RGB
            rgb_image = cv2.cvtColor(remapped, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb_image.shape
            bytes_per_line = ch * w
            qt_image = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format_RGB888)
            
            # Explicit copy to ensure data persists after worker finishes
            self.signals.result.emit(qt_image.copy())

        except Exception as e:
            self.signals.error.emit(str(e))

class PreviewWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        self.label = QLabel("No Video Selected")
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setStyleSheet("""
            background-color: #1E1E22;
            color: #52525B;
            border: 1px solid #27272A;
            border-radius: 8px;
            font-size: 14px;
        """)
        self.label.setMinimumSize(100, 100)
        self.label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        
        self.layout.addWidget(self.label)
        
        self.score_label = QLabel("Blur Score: —")
        self.score_label.setAlignment(Qt.AlignCenter)
        self.score_label.setStyleSheet("""
            color: #A1A1AA;
            font-weight: 600;
            font-size: 12px;
            padding: 8px;
        """)
        self.layout.addWidget(self.score_label)
        
        self.threadpool = QThreadPool()
        
    def update_preview(self, video_path, settings):
        """
        Starts a background worker to update the preview image.
        """
        if not video_path:
            self.label.setText("No Video Selected")
            self.label.setPixmap(QPixmap())
            return
            
        self.label.setText("Loading preview...")
        
        # In a real scenario, we might want to cancel pending workers 
        # if the user slides rapidly, but for now we rely on the thread pool.
        worker = PreviewWorker(video_path, settings)
        worker.signals.result.connect(self.display_image)
        worker.signals.blur_score.connect(self.display_blur_score)
        worker.signals.error.connect(self.display_error)
        self.threadpool.start(worker)
        
    def display_blur_score(self, score):
        self.score_label.setText(f"Blur Score: {score:.1f}")

    def display_image(self, image):
        # Scale pixmap to fit label while keeping aspect ratio
        pixmap = QPixmap.fromImage(image)
        # We scale to the label's current size
        if not pixmap.isNull():
            scaled_pixmap = pixmap.scaled(self.label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.label.setPixmap(scaled_pixmap)
        else:
             self.label.setPixmap(QPixmap())
        self.label.setText("")

    def display_error(self, error):
        self.label.setText(f"Preview Error:\n{error}")
        self.label.setPixmap(QPixmap())
        
    def resizeEvent(self, event):
        # If the label has a pixmap, we should re-scale it to fit the new size
        if self.label.pixmap() and not self.label.pixmap().isNull():
             # Note: This is a simplification. For best results, we should store the original high-res QImage
             # and re-scale that. But here we rely on the worker to send a new image or just let it scale.
             # Ideally, we would trigger a re-display of the cached original image if we had it.
             # For now, just ensuring layout updates.
             pass
        super().resizeEvent(event)