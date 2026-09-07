"""
Interactive 360 Studio Viewport Widget.
Features:
- Segmented face switcher (Front, Right, Back, Left, Up, Down).
- Live AI Mask and Nadir Crop overlays with real-time feedback.
- Interactive timeline scrubber with timecode and frame position preview.
- Asynchronous worker with debouncing and generation tracking.
"""
from __future__ import annotations

import cv2
import numpy as np
import copy
from PySide6.QtCore import Qt, QRunnable, QThreadPool, QObject, Signal, Slot, QTimer
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFrame, QHBoxLayout, QLabel, QPushButton,
    QSizePolicy, QSlider, QVBoxLayout, QWidget
)

from extractor360.core.geometry import GeometryProcessor
from extractor360.core.validation import validate_settings
from extractor360.core.processor import ProcessingWorker
from extractor360.core.ai_classes import PRESETS, parse_custom_classes
from extractor360.core.settings_manager import normalize_mask_faces
from extractor360.utils.image_utils import ImageUtils
from extractor360.ui.icons import get_pixmap


class WorkerSignals(QObject):
    """Signals emitted by the preview background worker."""
    result = Signal(QImage)
    blur_score = Signal(float)
    duration_info = Signal(float, int, float)  # current_sec, current_frame, total_sec
    error = Signal(str)
    finished = Signal()


class PreviewWorker(QRunnable):
    """Background worker generating perspective preview with overlays."""
    def __init__(self, media_path: str, settings: dict, face_name: str = "Front",
                 position_ratio: float = 0.0, show_ai_mask: bool = True, show_nadir_disc: bool = True, ai_cache=None):
        super().__init__()
        self.media_path = media_path
        self.settings = copy.deepcopy(settings)
        self.ai_cache = ai_cache if ai_cache is not None else {}
        self.face_name = face_name
        self.position_ratio = position_ratio
        self.show_ai_mask = show_ai_mask
        self.show_nadir_disc = show_nadir_disc
        self.signals = WorkerSignals()

    @Slot()
    def run(self):
        try:
            self.settings = validate_settings(self.settings)
            is_image = self.media_path.lower().endswith(('.jpg', '.jpeg', '.png', '.tiff', '.tif'))
            total_sec = 0.0
            current_sec = 0.0
            current_frame = 0

            if is_image:
                frame = cv2.imread(self.media_path)
                if frame is None:
                    self.signals.error.emit(f"Could not load image: {self.media_path}")
                    return
            else:
                cap = cv2.VideoCapture(self.media_path)
                if not cap.isOpened():
                    cap.release()
                    self.signals.error.emit(f"Could not open video: {self.media_path}")
                    return

                total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 1)
                fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
                total_sec = total_frames / fps

                target_frame = int(self.position_ratio * (total_frames - 1))
                target_frame = max(0, min(target_frame, total_frames - 1))
                cap.set(cv2.CAP_PROP_POS_FRAMES, target_frame)
                current_frame = target_frame
                current_sec = target_frame / fps

                ret, frame = cap.read()
                cap.release()

                if not ret or frame is None:
                    self.signals.error.emit("Could not read frame from video")
                    return

            self.signals.duration_info.emit(current_sec, current_frame, total_sec)

            settings = self.settings
            h, w = frame.shape[:2]
            if settings['is_360']:
                views = GeometryProcessor.generate_views(settings['camera_count'], settings['pitch_offset'], settings['layout_mode'])
                active = settings.get('active_cameras')
                views = [v for i, v in enumerate(views) if active is None or i in active]
                name, yaw, pitch, roll = next((v for v in views if v[0] == self.face_name), views[0])
                resolution = settings['resolution']
                maps = GeometryProcessor.create_rectilinear_map(h, w, resolution, resolution, settings['fov'], yaw, pitch, roll)
                maps = cv2.convertMaps(*maps, cv2.CV_16SC2)
                interpolation = cv2.INTER_LANCZOS4 if settings['interpolation_mode'] == 'lanczos' else cv2.INTER_LINEAR
                remapped = cv2.remap(frame, *maps, interpolation, borderMode=cv2.BORDER_WRAP)
            else:
                name = 'flat'
                remapped = frame.copy()
            self.signals.blur_score.emit(ImageUtils.calculate_blur_score(remapped))
            if settings['sharpening_enabled']:
                strength = settings['sharpening_strength']
                remapped = cv2.addWeighted(remapped, 1 + strength, cv2.GaussianBlur(remapped, (0, 0), 2.0), -strength, 0)
            mask = None
            selected_faces = normalize_mask_faces(settings.get('ai_mask_cameras'))
            eligible = not settings['is_360'] or selected_faces is None or name.lower() in selected_faces
            if self.show_ai_mask and settings['ai_mode'] != 'None' and eligible:
                from extractor360.core.ai_model import AIService
                model_name = settings['ai_model']
                if model_name not in self.ai_cache:
                    self.ai_cache.clear()
                    self.ai_cache[model_name] = AIService(model_name)
                classes = parse_custom_classes(settings['ai_custom_classes'])
                for key, preset in [('ai_detect_humans', 'Humans'), ('ai_detect_vehicles', 'Vehicles'), ('ai_detect_plants', 'Plants')]:
                    if settings[key]:
                        classes.extend(PRESETS[preset])
                _, mask = self.ai_cache[model_name].process_image(remapped, mode='generate_mask', classes=sorted(set(classes)), conf=settings['ai_confidence'], invert_mask=settings['ai_invert_mask'], feather_mask=settings['feather_mask'])
            if self.show_nadir_disc and settings['nadir_mask_enabled'] and name.lower() == 'down':
                disc = ProcessingWorker._build_nadir_mask(remapped.shape, settings['nadir_mask_radius'], settings['ai_invert_mask'])
                mask = disc if mask is None else (cv2.min(mask, disc) if settings['ai_invert_mask'] else cv2.max(mask, disc))
            if mask is not None:
                ignored = (255 - mask if settings['ai_invert_mask'] else mask).astype(np.float32) / 255
                alpha = ignored[..., None] * 0.4
                remapped = np.clip(remapped * (1 - alpha) + np.array([20, 70, 210]) * alpha, 0, 255).astype(np.uint8)
            # Downsample only after computing the exported projection and quality score.
            if max(remapped.shape[:2]) > 800:
                scale = 800 / max(remapped.shape[:2])
                remapped = cv2.resize(remapped, (round(remapped.shape[1] * scale), round(remapped.shape[0] * scale)), interpolation=cv2.INTER_AREA)

            # Convert to QImage
            rgb_image = cv2.cvtColor(remapped, cv2.COLOR_BGR2RGB)
            rh, rw, ch = rgb_image.shape
            qt_image = QImage(rgb_image.data, rw, rh, ch * rw, QImage.Format_RGB888)

            self.signals.result.emit(qt_image.copy())

        except Exception as e:
            self.signals.error.emit(str(e))
        finally:
            self.signals.finished.emit()


class PreviewDelivery(QObject):
    """Keep result receivers and signal ownership on the GUI thread."""

    def __init__(self, widget, generation):
        super().__init__(widget)
        self.widget = widget
        self.generation = generation

    @Slot(QImage)
    def image(self, value):
        self.widget._display_image(value, self.generation)

    @Slot(float)
    def blur(self, value):
        self.widget._display_blur_score(value, self.generation)

    @Slot(float, int, float)
    def duration(self, seconds, frame, total):
        self.widget._display_duration_info(seconds, frame, total, self.generation)

    @Slot(str)
    def error(self, value):
        self.widget._display_error(value, self.generation)


class EmptyStateWidget(QFrame):
    """Clean empty state when no media is selected."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("emptyStateWidget")

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(12)

        self.icon_label = QLabel()
        self.icon_label.setPixmap(get_pixmap("monitor", color="#3A3A48", size=56))
        self.icon_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.icon_label)

        self.title_label = QLabel("No Media Selected")
        self.title_label.setStyleSheet("color: #E2E2E8; font-size: 14px; font-weight: 600;")
        self.title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.title_label)

        self.desc_label = QLabel("Select a video from the queue to preview 360° perspective views and mask overlays.")
        self.desc_label.setStyleSheet("color: #71717A; font-size: 11px;")
        self.desc_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.desc_label)


class PreviewWidget(QWidget):
    """Main interactive 360 viewport for Studio."""

    face_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_face = "Front"
        self.show_ai_mask = True
        self.show_nadir_disc = True
        self.current_media_path = None
        self.current_settings = {}
        self._ai_cache = {}
        self.cached_image = None
        self._position_ratio = 0.0

        self.threadpool = QThreadPool(self)
        self.threadpool.setMaxThreadCount(1)
        self._closed = False
        self._generation = 0

        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(120)
        self._debounce.timeout.connect(self._run_pending)
        self._pending = None

        self._build_ui()
        self.set_empty(True)

    def _build_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(6)

        # 1. Top Toolbar (Face selector + Overlay toggles)
        self.top_toolbar = QWidget()
        tb_layout = QHBoxLayout(self.top_toolbar)
        tb_layout.setContentsMargins(4, 2, 4, 2)
        tb_layout.setSpacing(8)

        # Segmented container for faces
        seg_container = QFrame()
        seg_container.setStyleSheet("background-color: #1A1A22; border: 1px solid #2D2D3B; border-radius: 5px; padding: 2px;")
        seg_layout = QHBoxLayout(seg_container)
        seg_layout.setContentsMargins(2, 2, 2, 2)
        seg_layout.setSpacing(2)

        self.face_buttons = {}
        faces = ["Front", "Right", "Back", "Left", "Up", "Down"]
        for face_name in faces:
            btn = QPushButton(face_name)
            btn.setObjectName("segmentBtn")
            btn.setCursor(Qt.PointingHandCursor)
            if face_name == self.current_face:
                btn.setProperty("active", True)
            btn.clicked.connect(lambda _, name=face_name: self.set_face(name))
            self.face_buttons[face_name] = btn
            seg_layout.addWidget(btn)

        self.segment_container = seg_container
        tb_layout.addWidget(seg_container)
        self.view_combo = QComboBox()
        self.view_combo.currentTextChanged.connect(self.set_face)
        tb_layout.addWidget(self.view_combo)
        self.view_combo.hide()
        tb_layout.addSpacing(6)

        self.chk_ai_mask = QCheckBox("Mask Overlay")
        self.chk_ai_mask.setChecked(self.show_ai_mask)
        self.chk_ai_mask.stateChanged.connect(self._toggle_ai_mask)
        tb_layout.addWidget(self.chk_ai_mask)

        self.chk_nadir = QCheckBox("Nadir Crop")
        self.chk_nadir.setChecked(self.show_nadir_disc)
        self.chk_nadir.stateChanged.connect(self._toggle_nadir)
        tb_layout.addWidget(self.chk_nadir)

        tb_layout.addStretch()

        # Resolution & blur chips
        self.score_label = QLabel("Blur: —")
        self.score_label.setStyleSheet("color: #8E8E98; font-size: 10px;")
        tb_layout.addWidget(self.score_label)

        self.res_label = QLabel("2048x2048")
        self.res_label.setStyleSheet("color: #F59E0B; background: rgba(245, 158, 11, 0.12); border: 1px solid #F59E0B; border-radius: 3px; padding: 1px 6px; font-size: 10px; font-weight: 600;")
        tb_layout.addWidget(self.res_label)

        root_layout.addWidget(self.top_toolbar)

        # 2. Main Viewport Area
        self.viewport_frame = QFrame()
        self.viewport_frame.setObjectName("viewportContainer")
        vp_layout = QVBoxLayout(self.viewport_frame)
        vp_layout.setContentsMargins(0, 0, 0, 0)

        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.image_label.setMinimumSize(200, 200)
        vp_layout.addWidget(self.image_label)

        root_layout.addWidget(self.viewport_frame, 1)

        # 3. Timeline Scrubber Bar
        self.timeline_bar = QFrame()
        self.timeline_bar.setObjectName("inspectorCard")
        self.timeline_bar.setFixedHeight(38)
        tl_layout = QHBoxLayout(self.timeline_bar)
        tl_layout.setContentsMargins(8, 2, 8, 2)
        tl_layout.setSpacing(8)

        self.play_btn = QPushButton("▶")
        self.play_btn.setFixedSize(22, 22)
        self.play_btn.setObjectName("toolBtn")
        self.play_btn.hide()
        tl_layout.addWidget(self.play_btn)

        self.timecode_label = QLabel("00:00.0 / 00:00.0")
        self.timecode_label.setStyleSheet("font-family: monospace; font-size: 10px; color: #A1A1AA;")
        tl_layout.addWidget(self.timecode_label)

        self.scrubber = QSlider(Qt.Horizontal)
        self.scrubber.setRange(0, 1000)
        self.scrubber.setValue(0)
        self.scrubber.valueChanged.connect(self._on_scrubber_changed)
        tl_layout.addWidget(self.scrubber, 1)

        self.frame_label = QLabel("Frame 0")
        self.frame_label.setStyleSheet("font-family: monospace; font-size: 10px; color: #8E8E96;")
        tl_layout.addWidget(self.frame_label)

        root_layout.addWidget(self.timeline_bar)

        # Empty State Widget
        self.empty_state = EmptyStateWidget(self)
        self.empty_state.setGeometry(0, 0, self.width(), self.height())
        self.empty_state.hide()

    def set_face(self, face_name: str):
        self.current_face = face_name
        for name, btn in self.face_buttons.items():
            btn.setProperty("active", (name == face_name))
            btn.setStyle(btn.style())
        self.face_changed.emit(face_name)
        self._schedule_update()

    def _toggle_ai_mask(self, state: int):
        self.show_ai_mask = bool(state)
        self._schedule_update()

    def _toggle_nadir(self, state: int):
        self.show_nadir_disc = bool(state)
        self._schedule_update()

    def _on_scrubber_changed(self, value: int):
        self._position_ratio = value / 1000.0
        self._schedule_update()

    def set_empty(self, is_empty: bool):
        if is_empty:
            self.top_toolbar.hide()
            self.viewport_frame.hide()
            self.timeline_bar.hide()
            self.empty_state.show()
            self.empty_state.raise_()
        else:
            self.empty_state.hide()
            self.top_toolbar.show()
            self.viewport_frame.show()
            self.timeline_bar.show()

    def update_preview(self, media_path: str | None, settings: dict):
        if not media_path:
            self._debounce.stop()
            self._pending = None
            self._generation += 1
            self.current_media_path = None
            self.cached_image = None
            self.set_empty(True)
            return

        self.current_media_path = media_path
        self.current_settings = copy.deepcopy(settings)
        views = GeometryProcessor.generate_views(max(1, min(64, settings.get("camera_count", 6))), settings.get("pitch_offset", 0), settings.get("layout_mode", "ring")) if settings.get("is_360", True) else [("flat", 0, 0, 0)]
        active = settings.get("active_cameras")
        names = [v[0] for i, v in enumerate(views) if active is None or i in active]
        self.view_combo.blockSignals(True)
        self.view_combo.clear()
        self.view_combo.addItems(names)
        if self.current_face not in names and names:
            self.current_face = names[0]
        self.view_combo.setCurrentText(self.current_face)
        self.view_combo.blockSignals(False)
        self.view_combo.show()
        self.segment_container.hide()
        self.set_empty(False)
        self._schedule_update()

    def _schedule_update(self):
        if self._closed or not self.current_media_path:
            return
        self._generation += 1
        self._pending = (self.current_media_path, dict(self.current_settings))
        self.threadpool.clear()
        self._debounce.start()

    def _run_pending(self):
        if not self._pending:
            return
        if self.threadpool.activeThreadCount():
            # Retain only the latest request, without orphaning GUI receivers
            # for runnables removed from the pool before they can finish.
            self._debounce.start()
            return
        media_path, settings = self._pending
        self._pending = None

        self._generation += 1
        gen = self._generation

        worker = PreviewWorker(
            media_path=media_path,
            settings=settings,
            face_name=self.current_face,
            position_ratio=self._position_ratio,
            show_ai_mask=self.show_ai_mask,
            show_nadir_disc=self.show_nadir_disc,
            ai_cache=self._ai_cache,
        )
        delivery = PreviewDelivery(self, gen)
        worker.signals.setParent(delivery)
        worker.signals.result.connect(delivery.image, Qt.ConnectionType.QueuedConnection)
        worker.signals.blur_score.connect(delivery.blur, Qt.ConnectionType.QueuedConnection)
        worker.signals.duration_info.connect(delivery.duration, Qt.ConnectionType.QueuedConnection)
        worker.signals.error.connect(delivery.error, Qt.ConnectionType.QueuedConnection)
        worker.signals.finished.connect(delivery.deleteLater, Qt.ConnectionType.QueuedConnection)
        self.threadpool.start(worker)

    def _display_image(self, image: QImage, generation: int):
        if generation != self._generation:
            return
        self.cached_image = image
        self.image_label.setText("")
        self._update_label_pixmap()
        self.res_label.setText(f"Preview {image.width()}×{image.height()} · export {self.current_settings.get('resolution', 2048) if self.current_settings.get('is_360', True) else 'native'}")

    def _display_blur_score(self, score: float, generation: int):
        if generation != self._generation:
            return
        self.score_label.setText(f"Export blur: {score:.1f}")

    def _display_duration_info(self, current_sec: float, current_frame: int, total_sec: float, generation: int):
        if generation != self._generation:
            return
        c_min, c_s = divmod(int(current_sec), 60)
        c_ms = int((current_sec - int(current_sec)) * 10)
        t_min, t_s = divmod(int(total_sec), 60)
        self.timecode_label.setText(f"{c_min:02d}:{c_s:02d}.{c_ms:01d} / {t_min:02d}:{t_s:02d}.0")
        self.frame_label.setText(f"Frame {current_frame}")

    def _display_error(self, error: str, generation: int):
        if generation != self._generation:
            return
        self.image_label.setText(f"Preview Error:\n{error}")
        self.image_label.setStyleSheet("color: #EF4444; font-size: 11px;")
        self.image_label.setPixmap(QPixmap())
        self.cached_image = None
        self.res_label.setText("ERROR")

    def _update_label_pixmap(self):
        if not self.cached_image:
            return
        pixmap = QPixmap.fromImage(self.cached_image)
        if not pixmap.isNull():
            scaled = pixmap.scaled(
                self.image_label.size(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            self.image_label.setPixmap(scaled)

    def shutdown(self):
        self._closed = True
        self._debounce.stop()
        self._pending = None
        self._generation += 1
        self.threadpool.clear()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.empty_state.setGeometry(0, 0, self.width(), self.height())
        if self.cached_image:
            self._update_label_pixmap()
