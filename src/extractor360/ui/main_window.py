"""
360 Extractor Studio — Pro Main Window.
Unified 3-column Studio architecture with:
- Top Navbar: Workflow Presets and Hardware status
- Left Column: Media Queue with metadata chips and dropzone
- Center Column: Interactive Viewport with 6-face switcher, live overlays, and timeline scrubber
- Right Column: Complete 4-Card Inspector with Progressive Disclosure
- Bottom HUD: Real-time dataset estimation and extraction controls
"""
from __future__ import annotations

import copy
import os
from pathlib import Path

import cv2
from PySide6.QtCore import (
    QEvent, QFile, QObject, Qt, QTextStream, QThread, QUrl
)
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog, QFrame,
    QGridLayout, QHBoxLayout, QLabel, QLineEdit, QMainWindow,
    QMessageBox, QProgressBar, QPushButton, QScrollArea, QSlider,
    QSpinBox, QSplitter, QVBoxLayout, QWidget
)

from extractor360.core.job import Job
from extractor360.core.processor import ProcessingWorker
from extractor360.core.settings_manager import SettingsManager
from extractor360.core.version import APP_NAME
from extractor360.ui.collapsible_section import CollapsibleDrawer
from extractor360.ui.icons import get_app_icon
from extractor360.ui.log_panel import LogPanel
from extractor360.ui.preview_widget import PreviewWidget
from extractor360.ui.video_card import VideoCard
from extractor360.ui.widgets import DropZone
from extractor360.ui.workers import BlurAnalysisWorker, ProcessingBridge


class ScrollBlocker(QObject):
    """Event filter to block scroll events on spinboxes/combos unless focused."""
    def eventFilter(self, obj, event):
        if event.type() == QEvent.Wheel and not obj.hasFocus():
            event.ignore()
            return True
        return False


class MainWindow(QMainWindow):
    """Studio Main Window."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} Studio")
        self.setWindowIcon(get_app_icon())
        self.setMinimumSize(1280, 820)
        self.resize(1520, 920)

        self.jobs: list[Job] = []
        self.default_settings = {}
        self.custom_output_dir = ""
        self.is_processing = False
        self._video_cards: list[VideoCard] = []
        self._selected_cards: list[VideoCard] = []

        self.scroll_blocker = ScrollBlocker(self)

        # Load stylesheet
        self.load_stylesheet("styles.qss")

        # Build Studio 3-Column Layout
        self._build_studio_layout()

        # Initialize Settings Manager
        self.settings_manager = SettingsManager()
        self.set_ui_from_settings(self.settings_manager.get_all())
        self.update_default_settings_from_ui()

        # Blur analysis worker thread
        self._blur_thread = None
        self._blur_worker = None

    def load_stylesheet(self, filename: str):
        qss_path = os.path.join(os.path.dirname(__file__), filename)
        file = QFile(qss_path)
        if file.open(QFile.ReadOnly | QFile.Text):
            stream = QTextStream(file)
            self.setStyleSheet(stream.readAll())
            file.close()

    # =========================================================================
    # UI CONSTRUCTION (Studio 3-Column Layout)
    # =========================================================================

    def _build_studio_layout(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        root_layout = QVBoxLayout(central_widget)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # 1. Top Navbar
        self.top_nav = self._create_top_nav()
        root_layout.addWidget(self.top_nav)

        # 2. Main 3-Column Splitter
        self.content_splitter = QSplitter(Qt.Horizontal)
        self.content_splitter.setHandleWidth(1)
        self.content_splitter.setStyleSheet("QSplitter::handle { background: #262630; }")

        # Left Column: Media Queue (260px)
        self.left_panel = self._create_queue_panel()
        self.content_splitter.addWidget(self.left_panel)

        # Center Column: Viewport & Preview (Flex)
        self.center_panel = self._create_viewport_panel()
        self.content_splitter.addWidget(self.center_panel)

        # Right Column: Inspector Settings (360px)
        self.right_panel = self._create_inspector_panel()
        self.content_splitter.addWidget(self.right_panel)

        self.content_splitter.setStretchFactor(0, 0)
        self.content_splitter.setStretchFactor(1, 1)
        self.content_splitter.setStretchFactor(2, 0)
        root_layout.addWidget(self.content_splitter, 1)

        # 3. Bottom HUD Action Bar
        self.hud_bar = self._create_hud_bar()
        root_layout.addWidget(self.hud_bar)

    def _create_top_nav(self) -> QWidget:
        nav = QFrame()
        nav.setObjectName("topNav")
        nav.setFixedHeight(48)
        layout = QHBoxLayout(nav)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(14)

        title_label = QLabel("360 Extractor")
        title_label.setStyleSheet("font-weight: 700; font-size: 13px; letter-spacing: -0.2px; color: #FFFFFF;")
        layout.addWidget(title_label)

        v_sep = QFrame()
        v_sep.setFrameShape(QFrame.VLine)
        v_sep.setFixedHeight(16)
        v_sep.setStyleSheet("color: #2E2E3C;")
        layout.addWidget(v_sep)

        wf_lbl = QLabel("Workflow Preset:")
        wf_lbl.setStyleSheet("color: #8E8E98; font-size: 11px;")
        layout.addWidget(wf_lbl)

        self.preset_combo = QComboBox()
        self.preset_combo.addItems([
            "Postshot (3D Gaussian Splatting)",
            "RealityScan / Metashape",
            "COLMAP Calibrated Rig",
            "Custom Workflow"
        ])
        self.preset_combo.setFixedWidth(230)
        self.preset_combo.currentIndexChanged.connect(self._on_preset_selected)
        layout.addWidget(self.preset_combo)

        layout.addStretch()

        # Hardware GPU Status Chip
        gpu_chip = QFrame()
        gpu_chip.setStyleSheet("background-color: #212129; border: 1px solid #30303D; border-radius: 4px; padding: 2px 8px;")
        gpu_lay = QHBoxLayout(gpu_chip)
        gpu_lay.setContentsMargins(4, 2, 4, 2)
        gpu_lay.setSpacing(5)
        dot = QLabel("●")
        dot.setStyleSheet("color: #F59E0B; font-size: 10px;")
        gpu_lay.addWidget(dot)
        gpu_txt = QLabel("Apple Metal (MPS) GPU Active")
        gpu_txt.setStyleSheet("color: #D4D4D8; font-size: 10px; font-weight: 500;")
        gpu_lay.addWidget(gpu_txt)
        layout.addWidget(gpu_chip)

        return nav

    def _create_queue_panel(self) -> QWidget:
        col = QFrame()
        col.setObjectName("leftSidebar")
        col.setFixedWidth(260)
        layout = QVBoxLayout(col)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # Header
        hdr_layout = QHBoxLayout()
        self.queue_title = QLabel("Queue")
        self.queue_title.setObjectName("sectionHeader")
        hdr_layout.addWidget(self.queue_title)

        self.queue_count_badge = QLabel("0 files")
        self.queue_count_badge.setStyleSheet("color: #71717A; font-size: 11px;")
        hdr_layout.addWidget(self.queue_count_badge)
        hdr_layout.addStretch()

        add_btn = QPushButton("+ Add Media")
        add_btn.setObjectName("toolBtn")
        add_btn.setCursor(Qt.PointingHandCursor)
        add_btn.clicked.connect(self.on_add_video_clicked)
        hdr_layout.addWidget(add_btn)
        layout.addLayout(hdr_layout)

        # Drop Zone
        self.drop_zone = DropZone()
        self.drop_zone.files_dropped.connect(self.add_videos_from_paths)
        layout.addWidget(self.drop_zone)

        # Scrollable Cards Area
        self.cards_scroll = QScrollArea()
        self.cards_scroll.setWidgetResizable(True)
        self.cards_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.cards_scroll.setStyleSheet("QScrollArea, QScrollArea > QWidget { border: none; background-color: transparent; }")

        self.cards_container = QWidget()
        self.cards_container.setObjectName("cardsContainer")
        self.cards_container.setStyleSheet("background-color: transparent;")
        self.cards_layout = QVBoxLayout(self.cards_container)
        self.cards_layout.setContentsMargins(0, 0, 0, 0)
        self.cards_layout.setSpacing(6)
        self.cards_layout.addStretch()

        self.cards_scroll.setWidget(self.cards_container)
        layout.addWidget(self.cards_scroll, 1)

        # Clear All Button
        self.clear_btn = QPushButton("Clear Completed")
        self.clear_btn.setObjectName("toolBtn")
        self.clear_btn.clicked.connect(self.clear_completed_jobs)
        layout.addWidget(self.clear_btn)

        return col

    def _create_viewport_panel(self) -> QWidget:
        col = QFrame()
        col.setObjectName("centerArea")
        layout = QVBoxLayout(col)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)

        # Studio Interactive Viewport
        self.preview_widget = PreviewWidget()
        self.preview_widget.face_changed.connect(lambda _: self.update_preview_display())
        layout.addWidget(self.preview_widget, 1)

        # Embedded Log Panel (collapsible at bottom)
        self.log_panel = LogPanel()
        self.log_panel.setFixedHeight(90)
        layout.addWidget(self.log_panel)

        return col

    def _create_inspector_panel(self) -> QWidget:
        col = QFrame()
        col.setObjectName("rightInspector")
        col.setFixedWidth(360)
        layout = QVBoxLayout(col)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        hdr = QLabel("Processing Settings")
        hdr.setObjectName("sectionHeader")
        layout.addWidget(hdr)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea, QScrollArea > QWidget { border: none; background-color: transparent; }")

        container = QWidget()
        container.setObjectName("inspectorContainer")
        container.setStyleSheet("background-color: transparent;")
        c_layout = QVBoxLayout(container)
        c_layout.setContentsMargins(0, 0, 4, 0)
        c_layout.setSpacing(8)

        # 4 Cards with Progressive Disclosure
        c_layout.addWidget(self._build_camera_card())
        c_layout.addWidget(self._build_quality_card())
        c_layout.addWidget(self._build_ai_card())
        c_layout.addWidget(self._build_export_card())

        c_layout.addStretch()
        scroll.setWidget(container)
        layout.addWidget(scroll, 1)

        return col

    # -------------------------------------------------------------------------
    # Card 1: Camera & Optics
    # -------------------------------------------------------------------------
    def _build_camera_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("inspectorCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)

        title = QLabel("1. Camera & Optics")
        title.setObjectName("cardTitle")
        layout.addWidget(title)

        grid = QGridLayout()
        grid.setSpacing(6)

        # Essentials
        grid.addWidget(QLabel("Layout:"), 0, 0)
        self.layout_combo = QComboBox()
        self.layout_combo.addItem("Cube Map (6 Views)", "cube")
        self.layout_combo.addItem("Ring (Horizon 360°)", "ring")
        self.layout_combo.addItem("Fibonacci Sphere", "fibonacci")
        self.layout_combo.currentIndexChanged.connect(self.on_layout_changed)
        grid.addWidget(self.layout_combo, 0, 1)

        grid.addWidget(QLabel("Resolution:"), 1, 0)
        self.res_spin = QSpinBox()
        self.res_spin.setRange(512, 8192)
        self.res_spin.setSingleStep(512)
        self.res_spin.setValue(2048)
        self.res_spin.valueChanged.connect(self.on_setting_changed)
        grid.addWidget(self.res_spin, 1, 1)

        grid.addWidget(QLabel("FOV:"), 2, 0)
        fov_layout = QHBoxLayout()
        self.fov_slider = QSlider(Qt.Horizontal)
        self.fov_slider.setRange(45, 140)
        self.fov_slider.setValue(90)
        self.fov_spin = QSpinBox()
        self.fov_spin.setRange(45, 140)
        self.fov_spin.setValue(90)
        self.fov_spin.setFixedWidth(50)
        self.fov_slider.valueChanged.connect(self.fov_spin.setValue)
        self.fov_spin.valueChanged.connect(self.fov_slider.setValue)
        self.fov_spin.valueChanged.connect(self.on_setting_changed)
        fov_layout.addWidget(self.fov_slider)
        fov_layout.addWidget(self.fov_spin)
        grid.addLayout(fov_layout, 2, 1)

        layout.addLayout(grid)

        # Advanced Camera Drawer
        self.adv_camera = CollapsibleDrawer("Advanced Camera Options")
        adv_grid = QGridLayout()
        adv_grid.setSpacing(5)

        adv_grid.addWidget(QLabel("Media Type:"), 0, 0)
        self.input_360_toggle = QCheckBox("360° Equirectangular Media")
        self.input_360_toggle.setChecked(True)
        self.input_360_toggle.toggled.connect(self.on_360_toggled)
        adv_grid.addWidget(self.input_360_toggle, 0, 1)

        adv_grid.addWidget(QLabel("Pitch Tilt:"), 1, 0)
        self.pitch_combo = QComboBox()
        self.pitch_combo.addItem("0° (Horizon Level)", 0)
        self.pitch_combo.addItem("-20° (High / Perch Mode)", -20)
        self.pitch_combo.addItem("+20° (Low / Ground Mode)", 20)
        self.pitch_combo.currentIndexChanged.connect(self.on_setting_changed)
        adv_grid.addWidget(self.pitch_combo, 1, 1)

        adv_grid.addWidget(QLabel("Cam Count:"), 2, 0)
        self.cam_count_spin = QSpinBox()
        self.cam_count_spin.setRange(1, 64)
        self.cam_count_spin.setValue(6)
        self.cam_count_spin.setEnabled(False)
        self.cam_count_spin.valueChanged.connect(self.on_setting_changed)
        adv_grid.addWidget(self.cam_count_spin, 2, 1)

        self.adv_camera.addLayout(adv_grid)

        self.lanczos_toggle = QCheckBox("Lanczos-4 High-Sharpness Interpolation")
        self.lanczos_toggle.toggled.connect(self.on_setting_changed)
        self.adv_camera.addWidget(self.lanczos_toggle)

        layout.addWidget(self.adv_camera)
        return card

    # -------------------------------------------------------------------------
    # Card 2: Quality & Motion Filters
    # -------------------------------------------------------------------------
    def _build_quality_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("inspectorCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)

        title = QLabel("2. Quality & Motion Filters")
        title.setObjectName("cardTitle")
        layout.addWidget(title)

        # Blur Rejection Row
        blur_row = QHBoxLayout()
        self.blur_toggle = QCheckBox("Reject Blurry Views")
        self.blur_toggle.setChecked(False)
        self.blur_toggle.toggled.connect(self.on_setting_changed)
        blur_row.addWidget(self.blur_toggle)

        blur_row.addWidget(QLabel("Min:"))
        self.blur_threshold_spin = QDoubleSpinBox()
        self.blur_threshold_spin.setRange(0.0, 1000.0)
        self.blur_threshold_spin.setValue(100.0)
        self.blur_threshold_spin.setFixedWidth(65)
        self.blur_threshold_spin.valueChanged.connect(self.on_setting_changed)
        blur_row.addWidget(self.blur_threshold_spin)

        self.btn_analyze = QPushButton("🔍 Analyze")
        self.btn_analyze.setObjectName("toolBtn")
        self.btn_analyze.clicked.connect(self.analyze_blur_for_selected)
        blur_row.addWidget(self.btn_analyze)
        layout.addLayout(blur_row)

        # Advanced Quality Drawer
        self.adv_quality = CollapsibleDrawer("Advanced Quality Controls")

        self.smart_blur_toggle = QCheckBox("Smart Adaptive Blur (Moving Average)")
        self.smart_blur_toggle.toggled.connect(self.on_setting_changed)
        self.adv_quality.addWidget(self.smart_blur_toggle)

        # Sharpening
        sharp_row = QHBoxLayout()
        self.sharpen_toggle = QCheckBox("Sharpening Recovery")
        self.sharpen_toggle.toggled.connect(self.on_setting_changed)
        sharp_row.addWidget(self.sharpen_toggle)

        self.sharpen_slider = QDoubleSpinBox()
        self.sharpen_slider.setRange(0.0, 2.0)
        self.sharpen_slider.setSingleStep(0.1)
        self.sharpen_slider.setValue(0.5)
        self.sharpen_slider.setFixedWidth(55)
        self.sharpen_slider.valueChanged.connect(self.on_setting_changed)
        sharp_row.addWidget(self.sharpen_slider)
        self.adv_quality.addLayout(sharp_row)

        # Adaptive Optical Flow Motion
        flow_row = QHBoxLayout()
        self.adaptive_toggle = QCheckBox("Optical Flow Motion Keyframing")
        self.adaptive_toggle.toggled.connect(self.on_setting_changed)
        flow_row.addWidget(self.adaptive_toggle)

        self.motion_threshold_spin = QDoubleSpinBox()
        self.motion_threshold_spin.setRange(0.1, 10.0)
        self.motion_threshold_spin.setSingleStep(0.1)
        self.motion_threshold_spin.setValue(0.5)
        self.motion_threshold_spin.setFixedWidth(55)
        self.motion_threshold_spin.valueChanged.connect(self.on_setting_changed)
        flow_row.addWidget(self.motion_threshold_spin)
        self.adv_quality.addLayout(flow_row)

        layout.addWidget(self.adv_quality)
        return card

    # -------------------------------------------------------------------------
    # Card 3: Operator & Nadir Masking
    # -------------------------------------------------------------------------
    def _build_ai_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("inspectorCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)

        title = QLabel("3. Operator & Nadir Masking")
        title.setObjectName("cardTitle")
        layout.addWidget(title)

        grid = QGridLayout()
        grid.setSpacing(5)

        # AI Mode
        grid.addWidget(QLabel("AI Mode:"), 0, 0)
        self.ai_combo = QComboBox()
        self.ai_combo.addItem("None", "None")
        self.ai_combo.addItem("Generate Mask", "Generate Mask")
        self.ai_combo.addItem("Skip Frame", "Skip Frame")
        self.ai_combo.currentIndexChanged.connect(self.on_setting_changed)
        grid.addWidget(self.ai_combo, 0, 1)

        # Nadir Disc
        grid.addWidget(QLabel("Nadir Disc:"), 1, 0)
        nadir_row = QHBoxLayout()
        self.nadir_toggle = QCheckBox("Enable")
        self.nadir_toggle.setChecked(False)
        self.nadir_toggle.toggled.connect(self.on_setting_changed)
        nadir_row.addWidget(self.nadir_toggle)

        self.nadir_radius_spin = QDoubleSpinBox()
        self.nadir_radius_spin.setRange(1.0, 100.0)
        self.nadir_radius_spin.setValue(40.0)
        self.nadir_radius_spin.setSuffix("%")
        self.nadir_radius_spin.setFixedWidth(65)
        self.nadir_radius_spin.valueChanged.connect(self.on_setting_changed)
        nadir_row.addWidget(self.nadir_radius_spin)
        grid.addLayout(nadir_row, 1, 1)

        layout.addLayout(grid)

        # Advanced AI Drawer
        self.adv_ai = CollapsibleDrawer("Advanced AI & Target Classes")
        adv_grid = QGridLayout()
        adv_grid.setSpacing(5)

        adv_grid.addWidget(QLabel("Model:"), 0, 0)
        self.ai_model_combo = QComboBox()
        self.ai_model_combo.addItem("YOLO26-N Seg (Fast Nano)", "yolo26n-seg.pt")
        self.ai_model_combo.addItem("YOLO26-S Seg (Balanced Small)", "yolo26s-seg.pt")
        self.ai_model_combo.addItem("YOLO26-M Seg (High Precision)", "yolo26m-seg.pt")
        self.ai_model_combo.currentIndexChanged.connect(self.on_setting_changed)
        adv_grid.addWidget(self.ai_model_combo, 0, 1)

        adv_grid.addWidget(QLabel("Confidence:"), 1, 0)
        self.ai_conf_spin = QDoubleSpinBox()
        self.ai_conf_spin.setRange(0.05, 1.0)
        self.ai_conf_spin.setSingleStep(0.05)
        self.ai_conf_spin.setValue(0.25)
        self.ai_conf_spin.valueChanged.connect(self.on_setting_changed)
        adv_grid.addWidget(self.ai_conf_spin, 1, 1)
        self.adv_ai.addLayout(adv_grid)

        # Target classes
        cls_row = QHBoxLayout()
        cls_row.addWidget(QLabel("Classes:"))
        self.chk_humans = QCheckBox("Humans")
        self.chk_humans.setChecked(True)
        self.chk_humans.toggled.connect(self.on_setting_changed)
        self.chk_vehicles = QCheckBox("Vehicles")
        self.chk_vehicles.toggled.connect(self.on_setting_changed)
        self.chk_plants = QCheckBox("Plants")
        self.chk_plants.toggled.connect(self.on_setting_changed)
        cls_row.addWidget(self.chk_humans)
        cls_row.addWidget(self.chk_vehicles)
        cls_row.addWidget(self.chk_plants)
        self.adv_ai.addLayout(cls_row)

        cust_row = QHBoxLayout()
        cust_row.addWidget(QLabel("Custom:"))
        self.txt_custom_classes = QLineEdit()
        self.txt_custom_classes.setPlaceholderText("e.g. dog, backpack")
        self.txt_custom_classes.textChanged.connect(self.on_setting_changed)
        cust_row.addWidget(self.txt_custom_classes)
        self.adv_ai.addLayout(cust_row)

        # Scoped Faces Checkboxes
        face_box = QFrame()
        face_lay = QHBoxLayout(face_box)
        face_lay.setContentsMargins(0, 0, 0, 0)
        face_lay.addWidget(QLabel("Faces:"))
        self.mask_face_checks = {}
        for face in ["Front", "Right", "Back", "Left", "Up", "Down"]:
            chk = QCheckBox(face)
            if face == "Down":
                chk.setChecked(True)
            chk.toggled.connect(self.on_setting_changed)
            self.mask_face_checks[face] = chk
            face_lay.addWidget(chk)
        self.adv_ai.addWidget(face_box)

        self.ai_feather_toggle = QCheckBox("Soft Alpha Mask (Native Softness for 3DGS)")
        self.ai_feather_toggle.toggled.connect(self.on_setting_changed)
        self.adv_ai.addWidget(self.ai_feather_toggle)

        self.ai_invert_toggle = QCheckBox("Invert Mask (Photogrammetry: Black=Subject)")
        self.ai_invert_toggle.setChecked(True)
        self.ai_invert_toggle.toggled.connect(self.on_setting_changed)
        self.adv_ai.addWidget(self.ai_invert_toggle)

        layout.addWidget(self.adv_ai)
        return card

    # -------------------------------------------------------------------------
    # Card 4: Output & Calibration
    # -------------------------------------------------------------------------
    def _build_export_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("inspectorCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)

        title = QLabel("4. Output & Calibration")
        title.setObjectName("cardTitle")
        layout.addWidget(title)

        grid = QGridLayout()
        grid.setSpacing(5)

        # Format
        grid.addWidget(QLabel("Format:"), 0, 0)
        self.format_combo = QComboBox()
        self.format_combo.addItem("jpg")
        self.format_combo.addItem("png")
        self.format_combo.addItem("tiff")
        self.format_combo.currentIndexChanged.connect(self.on_setting_changed)
        grid.addWidget(self.format_combo, 0, 1)

        # Interval
        grid.addWidget(QLabel("Interval:"), 1, 0)
        int_row = QHBoxLayout()
        self.interval_spin = QDoubleSpinBox()
        self.interval_spin.setRange(0.01, 1000.0)
        self.interval_spin.setValue(1.0)
        self.interval_spin.setFixedWidth(55)
        self.interval_spin.valueChanged.connect(self.on_setting_changed)
        self.interval_unit = QComboBox()
        self.interval_unit.addItem("Seconds")
        self.interval_unit.addItem("Frames")
        self.interval_unit.currentIndexChanged.connect(self.on_setting_changed)
        int_row.addWidget(self.interval_spin)
        int_row.addWidget(self.interval_unit)
        grid.addLayout(int_row, 1, 1)

        layout.addLayout(grid)

        # Essential Export Priors
        self.colmap_toggle = QCheckBox("Export COLMAP Priors (cameras.txt + rig_rotations)")
        self.colmap_toggle.toggled.connect(self.on_setting_changed)
        layout.addWidget(self.colmap_toggle)

        self.exif_intrinsics_toggle = QCheckBox("Embed Optical EXIF (Focal, Make/Model, Heading)")
        self.exif_intrinsics_toggle.setChecked(True)
        self.exif_intrinsics_toggle.toggled.connect(self.on_setting_changed)
        layout.addWidget(self.exif_intrinsics_toggle)

        # Advanced Export Drawer
        self.adv_export = CollapsibleDrawer("Advanced Naming & GPS Options")
        adv_grid = QGridLayout()
        adv_grid.setSpacing(5)

        adv_grid.addWidget(QLabel("Naming:"), 0, 0)
        self.naming_mode_combo = QComboBox()
        self.naming_mode_combo.addItem("RealityScan Standard", "realityscan")
        self.naming_mode_combo.addItem("Simple Sequential", "simple")
        self.naming_mode_combo.addItem("Custom Pattern", "custom")
        self.naming_mode_combo.currentIndexChanged.connect(self.on_setting_changed)
        adv_grid.addWidget(self.naming_mode_combo, 0, 1)

        adv_grid.addWidget(QLabel("Altitude:"), 1, 0)
        self.altitude_combo = QComboBox()
        self.altitude_combo.addItem("Absolute (ASL)", "absolute")
        self.altitude_combo.addItem("Relative (AGL)", "relative")
        self.altitude_combo.currentIndexChanged.connect(self.on_setting_changed)
        adv_grid.addWidget(self.altitude_combo, 1, 1)
        self.adv_export.addLayout(adv_grid)

        self.telemetry_toggle = QCheckBox("Export Telemetry (GPMF / CAMM / GPX / SRT)")
        self.telemetry_toggle.toggled.connect(self.on_setting_changed)
        self.adv_export.addWidget(self.telemetry_toggle)

        # Custom Patterns
        self.image_pattern_input = QLineEdit("{filename}_frame{frame}_{camera}")
        self.image_pattern_input.textChanged.connect(self.on_setting_changed)
        self.mask_pattern_input = QLineEdit("{filename}_frame{frame}_{camera}_mask")
        self.mask_pattern_input.textChanged.connect(self.on_setting_changed)

        # Output dir row
        dir_row = QHBoxLayout()
        self.output_dir_label = QLabel("Auto (Video subfolder)")
        self.output_dir_label.setStyleSheet("color: #71717A; font-size: 10px;")
        btn_dir = QPushButton("Browse...")
        btn_dir.setObjectName("toolBtn")
        btn_dir.clicked.connect(self.on_choose_output_dir)
        dir_row.addWidget(self.output_dir_label, 1)
        dir_row.addWidget(btn_dir)
        self.adv_export.addLayout(dir_row)

        layout.addWidget(self.adv_export)
        return card

    # -------------------------------------------------------------------------
    # Bottom HUD Action Bar
    # -------------------------------------------------------------------------
    def _create_hud_bar(self) -> QWidget:
        hud = QFrame()
        hud.setObjectName("hudBar")
        hud.setFixedHeight(54)
        layout = QHBoxLayout(hud)
        layout.setContentsMargins(18, 0, 18, 0)
        layout.setSpacing(14)

        self.estimation_label = QLabel("No media loaded.")
        self.estimation_label.setStyleSheet("font-weight: 500; font-size: 11px; color: #D4D4D8;")
        layout.addWidget(self.estimation_label)

        self.hud_progress = QProgressBar()
        self.hud_progress.setFixedWidth(180)
        self.hud_progress.setFixedHeight(6)
        self.hud_progress.setTextVisible(False)
        self.hud_progress.hide()
        layout.addWidget(self.hud_progress)

        layout.addStretch()

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setObjectName("secondaryActionBtn")
        self.cancel_btn.clicked.connect(self.cancel_processing)
        self.cancel_btn.setEnabled(False)
        layout.addWidget(self.cancel_btn)

        self.extract_btn = QPushButton("Extract Dataset")
        self.extract_btn.setObjectName("primaryActionBtn")
        self.extract_btn.setCursor(Qt.PointingHandCursor)
        self.extract_btn.clicked.connect(self.start_processing)
        layout.addWidget(self.extract_btn)

        return hud

    # =========================================================================
    # PRESETS MANAGEMENT
    # =========================================================================

    def apply_preset(self, preset_name: str):
        idx = self.preset_combo.findText(preset_name)
        if idx >= 0:
            self.preset_combo.blockSignals(True)
            self.preset_combo.setCurrentIndex(idx)
            self.preset_combo.blockSignals(False)

        if "Postshot" in preset_name:
            self.layout_combo.setCurrentIndex(self.layout_combo.findData("cube"))
            self.res_spin.setValue(2048)
            self.fov_spin.setValue(90)
            self.pitch_combo.setCurrentIndex(self.pitch_combo.findData(0))
            self.ai_combo.setCurrentText("Generate Mask")
            self.ai_feather_toggle.setChecked(True)
            self.ai_invert_toggle.setChecked(True)
            self.nadir_toggle.setChecked(True)
            self.nadir_radius_spin.setValue(35.0)
            self.format_combo.setCurrentText("jpg")
            self.colmap_toggle.setChecked(True)
            self.exif_intrinsics_toggle.setChecked(True)
            for face, chk in self.mask_face_checks.items():
                chk.setChecked(face == "Down")
        elif "RealityScan" in preset_name:
            self.layout_combo.setCurrentIndex(self.layout_combo.findData("cube"))
            self.res_spin.setValue(2048)
            self.fov_spin.setValue(90)
            self.ai_combo.setCurrentText("Generate Mask")
            self.ai_feather_toggle.setChecked(False)
            self.ai_invert_toggle.setChecked(True)
            self.nadir_toggle.setChecked(True)
            self.nadir_radius_spin.setValue(40.0)
            self.naming_mode_combo.setCurrentIndex(self.naming_mode_combo.findData("realityscan"))
            self.format_combo.setCurrentText("jpg")
            self.colmap_toggle.setChecked(True)
            self.exif_intrinsics_toggle.setChecked(True)
            for face, chk in self.mask_face_checks.items():
                chk.setChecked(face == "Down")
        elif "COLMAP" in preset_name:
            self.layout_combo.setCurrentIndex(self.layout_combo.findData("cube"))
            self.res_spin.setValue(3072)
            self.fov_spin.setValue(90)
            self.lanczos_toggle.setChecked(True)
            self.ai_combo.setCurrentText("Generate Mask")
            self.ai_feather_toggle.setChecked(False)
            self.colmap_toggle.setChecked(True)
            self.exif_intrinsics_toggle.setChecked(True)
            self.format_combo.setCurrentText("png")
            self.interval_spin.setValue(0.5)
            self.interval_unit.setCurrentText("Seconds")

        self.on_setting_changed()

    def _on_preset_selected(self, index: int):
        self.apply_preset(self.preset_combo.currentText())

    # =========================================================================
    # SETTINGS SYNC (SettingsManager <-> UI)
    # =========================================================================

    def get_settings_from_ui(self) -> dict:
        return {
            'is_360': self.input_360_toggle.isChecked(),
            'output_format': self.format_combo.currentText(),
            'custom_output_dir': self.custom_output_dir,
            'interval_value': self.interval_spin.value(),
            'interval_unit': self.interval_unit.currentText(),
            'resolution': self.res_spin.value(),
            'fov': self.fov_spin.value(),
            'camera_count': self.cam_count_spin.value(),
            'layout_mode': self.layout_combo.currentData(),
            'pitch_offset': self.pitch_combo.currentData(),
            'export_telemetry': self.telemetry_toggle.isChecked(),
            'altitude_mode': self.altitude_combo.currentData(),
            'exif_intrinsics': self.exif_intrinsics_toggle.isChecked(),
            'export_colmap': self.colmap_toggle.isChecked(),
            'interpolation_mode': 'lanczos' if self.lanczos_toggle.isChecked() else 'linear',
            'feather_mask': self.ai_feather_toggle.isChecked(),
            'ai_mode': self.ai_combo.currentText(),
            'ai_model': self.ai_model_combo.currentData(),
            'ai_invert_mask': self.ai_invert_toggle.isChecked(),
            'ai_confidence': self.ai_conf_spin.value(),
            'nadir_mask_enabled': self.nadir_toggle.isChecked(),
            'nadir_mask_radius': self.nadir_radius_spin.value(),
            'ai_detect_humans': self.chk_humans.isChecked(),
            'ai_detect_vehicles': self.chk_vehicles.isChecked(),
            'ai_detect_plants': self.chk_plants.isChecked(),
            'ai_custom_classes': self.txt_custom_classes.text(),
            'ai_mask_cameras': [name for name, chk in self.mask_face_checks.items() if chk.isChecked()],
            'adaptive_mode': self.adaptive_toggle.isChecked(),
            'adaptive_threshold': self.motion_threshold_spin.value(),
            'blur_filter_enabled': self.blur_toggle.isChecked(),
            'smart_blur_enabled': self.smart_blur_toggle.isChecked(),
            'blur_threshold': self.blur_threshold_spin.value(),
            'sharpening_enabled': self.sharpen_toggle.isChecked(),
            'sharpening_strength': self.sharpen_slider.value(),
            'naming_mode': self.naming_mode_combo.currentData(),
            'image_pattern': self.image_pattern_input.text(),
            'mask_pattern': self.mask_pattern_input.text(),
        }

    def set_ui_from_settings(self, settings: dict):
        widgets = [
            self.format_combo, self.interval_spin, self.interval_unit,
            self.res_spin, self.fov_spin, self.cam_count_spin,
            self.layout_combo, self.pitch_combo, self.ai_combo, self.ai_model_combo,
            self.ai_invert_toggle, self.ai_conf_spin, self.chk_humans,
            self.chk_vehicles, self.chk_plants, self.nadir_toggle,
            self.nadir_radius_spin, self.blur_threshold_spin, self.sharpen_slider,
            self.motion_threshold_spin, self.naming_mode_combo,
            self.lanczos_toggle, self.ai_feather_toggle, self.input_360_toggle,
            self.altitude_combo, self.exif_intrinsics_toggle, self.colmap_toggle
        ]
        widgets += list(self.mask_face_checks.values())
        for w in widgets:
            w.blockSignals(True)

        self.input_360_toggle.setChecked(settings.get('is_360', True))
        self.format_combo.setCurrentText(settings.get('output_format', 'jpg'))
        self.custom_output_dir = settings.get('custom_output_dir', "")
        if self.custom_output_dir:
            self.output_dir_label.setText(os.path.basename(self.custom_output_dir))
            self.output_dir_label.setStyleSheet("color: #E6E6EA;")

        self.interval_spin.setValue(settings.get('interval_value', 1.0))
        self.interval_unit.setCurrentText(settings.get('interval_unit', 'Seconds'))
        self.res_spin.setValue(settings.get('resolution', 2048))
        self.fov_spin.setValue(settings.get('fov', 90))
        self.cam_count_spin.setValue(settings.get('camera_count', 6))

        layout_val = settings.get('layout_mode', 'cube')
        if layout_val == 'adaptive':
            layout_val = 'ring'
        idx = self.layout_combo.findData(layout_val)
        if idx >= 0:
            self.layout_combo.setCurrentIndex(idx)

        pitch_val = settings.get('pitch_offset', 0)
        idx = self.pitch_combo.findData(pitch_val)
        if idx >= 0:
            self.pitch_combo.setCurrentIndex(idx)

        self.ai_combo.setCurrentText(settings.get('ai_mode', 'None'))
        model_idx = self.ai_model_combo.findData(settings.get('ai_model', 'yolo26n-seg.pt'))
        if model_idx >= 0:
            self.ai_model_combo.setCurrentIndex(model_idx)

        self.ai_invert_toggle.setChecked(settings.get('ai_invert_mask', True))
        self.ai_conf_spin.setValue(settings.get('ai_confidence', 0.25))
        self.nadir_toggle.setChecked(settings.get('nadir_mask_enabled', False))
        self.nadir_radius_spin.setValue(settings.get('nadir_mask_radius', 40.0))
        self.chk_humans.setChecked(settings.get('ai_detect_humans', True))
        self.chk_vehicles.setChecked(settings.get('ai_detect_vehicles', False))
        self.chk_plants.setChecked(settings.get('ai_detect_plants', False))
        self.txt_custom_classes.setText(settings.get('ai_custom_classes', ""))

        mask_faces = settings.get('ai_mask_cameras', []) or []
        if isinstance(mask_faces, str):
            mask_faces = [c.strip() for c in mask_faces.split(',') if c.strip()]
        mask_faces_lower = {str(f).strip().lower() for f in mask_faces}
        for name, chk in self.mask_face_checks.items():
            chk.setChecked(name.lower() in mask_faces_lower)

        self.blur_toggle.setChecked(settings.get('blur_filter_enabled', False))
        self.smart_blur_toggle.setChecked(settings.get('smart_blur_enabled', False))
        self.blur_threshold_spin.setValue(settings.get('blur_threshold', 100.0))
        self.sharpen_toggle.setChecked(settings.get('sharpening_enabled', False))
        self.sharpen_slider.setValue(settings.get('sharpening_strength', 0.5))

        self.adaptive_toggle.setChecked(settings.get('adaptive_mode', False))
        self.motion_threshold_spin.setValue(settings.get('adaptive_threshold', 0.5))

        self.telemetry_toggle.setChecked(settings.get('export_telemetry', False))
        self.exif_intrinsics_toggle.setChecked(settings.get('exif_intrinsics', True))
        self.colmap_toggle.setChecked(settings.get('export_colmap', False))

        alt_mode = settings.get('altitude_mode', 'absolute')
        idx = self.altitude_combo.findData(alt_mode)
        if idx >= 0:
            self.altitude_combo.setCurrentIndex(idx)

        self.lanczos_toggle.setChecked(settings.get('interpolation_mode', 'linear') == 'lanczos')
        self.ai_feather_toggle.setChecked(settings.get('feather_mask', False))

        naming_mode = settings.get('naming_mode', 'realityscan')
        idx = self.naming_mode_combo.findData(naming_mode)
        if idx >= 0:
            self.naming_mode_combo.setCurrentIndex(idx)
        self.image_pattern_input.setText(settings.get('image_pattern', ''))
        self.mask_pattern_input.setText(settings.get('mask_pattern', ''))

        for w in widgets:
            w.blockSignals(False)

        self._apply_360_state(self.input_360_toggle.isChecked())

    def update_default_settings_from_ui(self):
        self.default_settings = self.get_settings_from_ui()

    def on_setting_changed(self):
        if self.is_processing:
            return

        current_settings = self.get_settings_from_ui()
        if self._selected_cards:
            for card in self._selected_cards:
                card.job.settings = current_settings
                card.refresh()
        else:
            self.default_settings = current_settings
            for key, value in current_settings.items():
                self.settings_manager.set(key, value)

        self.update_preview_display()
        self.update_estimate()

    def on_layout_changed(self, index: int):
        mode = self.layout_combo.currentData()
        if mode == 'cube':
            self.cam_count_spin.setValue(6)
            self.cam_count_spin.setEnabled(False)
        else:
            self.cam_count_spin.setEnabled(True)
        self.on_setting_changed()

    def on_360_toggled(self, checked: bool):
        self._apply_360_state(checked)
        self.on_setting_changed()

    def _apply_360_state(self, is_360: bool):
        self.layout_combo.setEnabled(is_360)
        self.pitch_combo.setEnabled(is_360)
        self.fov_slider.setEnabled(is_360)
        self.fov_spin.setEnabled(is_360)

    # =========================================================================
    # QUEUE & MEDIA MANAGEMENT
    # =========================================================================

    def on_add_video_clicked(self):
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Select 360° Videos or Images",
            "",
            "Media Files (*.mp4 *.mov *.insv *.jpg *.jpeg *.png *.tiff *.tif);;All Files (*)"
        )
        if files:
            self.add_videos_from_paths(files)

    def add_videos_from_paths(self, paths: list[str]):
        valid_extensions = ('.mp4', '.mov', '.insv', '.jpg', '.jpeg', '.png', '.tiff', '.tif')
        new_jobs = []

        for p in paths:
            if os.path.isdir(p):
                for root, _, files in os.walk(p):
                    for file in files:
                        if file.lower().endswith(valid_extensions):
                            full_path = os.path.join(root, file)
                            new_jobs.append(self._create_job_for_path(full_path))
            elif os.path.isfile(p) and p.lower().endswith(valid_extensions):
                new_jobs.append(self._create_job_for_path(p))

        if not new_jobs:
            return

        for job in new_jobs:
            self.jobs.append(job)
            card = VideoCard(job)
            card.clicked.connect(lambda c=card: self.select_card(c))
            card.ctrl_clicked.connect(lambda c=card: self.toggle_card_selection(c))
            card.remove_clicked.connect(lambda c=card: self.remove_video(c))
            card.open_folder_clicked.connect(lambda j=job: self._open_job_output_folder(j))

            self._video_cards.append(card)
            self.cards_layout.insertWidget(self.cards_layout.count() - 1, card)

        self._update_queue_ui_state()

        if self._video_cards:
            self.select_card(self._video_cards[-1])

        self.update_estimate()

    def _create_job_for_path(self, path: str) -> Job:
        job = Job(path)
        job.settings = copy.deepcopy(self.default_settings)
        return job

    def remove_video(self, card: VideoCard):
        if card in self._video_cards:
            idx = self._video_cards.index(card)
            self.cards_layout.removeWidget(card)
            self._video_cards.remove(card)
            if card.job in self.jobs:
                self.jobs.remove(card.job)
            if card in self._selected_cards:
                self._selected_cards.remove(card)
            card.deleteLater()

            self._update_queue_ui_state()

            if self._video_cards:
                new_idx = min(idx, len(self._video_cards) - 1)
                self.select_card(self._video_cards[new_idx])
            else:
                self.clear_selection()

            self.update_estimate()

    def clear_completed_jobs(self):
        to_remove = [card for card in self._video_cards if card.job.status == "Done"]
        for card in to_remove:
            self.remove_video(card)

    def _update_queue_ui_state(self):
        count = len(self._video_cards)
        self.queue_count_badge.setText(f"{count} file{'s' if count != 1 else ''}")
        self.drop_zone.setVisible(count == 0)

    def select_card(self, card: VideoCard):
        for c in self._selected_cards:
            c.setSelected(False)
        self._selected_cards = [card]
        card.setSelected(True)

        self.set_ui_from_settings(card.job.settings)
        self.update_preview_display()
        self.update_estimate()

    def toggle_card_selection(self, card: VideoCard):
        if card in self._selected_cards:
            card.setSelected(False)
            self._selected_cards.remove(card)
        else:
            card.setSelected(True)
            self._selected_cards.append(card)

        if self._selected_cards:
            self.set_ui_from_settings(self._selected_cards[-1].job.settings)
        self.update_preview_display()
        self.update_estimate()

    def clear_selection(self):
        for c in self._selected_cards:
            c.setSelected(False)
        self._selected_cards = []
        self.preview_widget.update_preview(None, {})
        self.update_estimate()

    def update_preview_display(self):
        if self._selected_cards:
            active_card = self._selected_cards[-1]
            settings = active_card.job.settings or self.get_settings_from_ui()
            self.preview_widget.update_preview(active_card.job.file_path, settings)
        elif self._video_cards:
            active_card = self._video_cards[0]
            settings = active_card.job.settings or self.get_settings_from_ui()
            self.preview_widget.update_preview(active_card.job.file_path, settings)
        else:
            self.preview_widget.update_preview(None, {})

    def _open_job_output_folder(self, job: Job):
        out_dir = job.settings.get('custom_output_dir') or self.custom_output_dir
        if not out_dir:
            out_dir = os.path.join(os.path.dirname(job.file_path), Path(job.file_path).stem + "_extracted")
        if os.path.exists(out_dir):
            QDesktopServices.openUrl(QUrl.fromLocalFile(out_dir))

    def on_choose_output_dir(self):
        directory = QFileDialog.getExistingDirectory(self, "Select Output Directory", self.custom_output_dir or "")
        if directory:
            self.custom_output_dir = directory
            self.output_dir_label.setText(os.path.basename(directory))
            self.output_dir_label.setStyleSheet("color: #E6E6EA;")
            self.on_setting_changed()

    # =========================================================================
    # ESTIMATION
    # =========================================================================

    def update_estimate(self):
        if not self.jobs:
            self.estimation_label.setText("No media loaded.")
            self.extract_btn.setText("Extract Dataset")
            self.extract_btn.setEnabled(False)
            return

        total_images = 0
        total_size_mb = 0.0

        for job in self.jobs:
            s = job.settings or self.default_settings
            is_360 = s.get('is_360', True)
            cams = s.get('camera_count', 6) if is_360 else 1
            interval_val = s.get('interval_value', 1.0)
            interval_unit = s.get('interval_unit', 'Seconds')
            res = s.get('resolution', 2048)

            # Quick frame count estimate
            try:
                cap = cv2.VideoCapture(job.file_path)
                frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 1)
                fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
                cap.release()
            except Exception:
                frame_count = 300
                fps = 30.0

            if interval_unit == 'Frames':
                extracted_frames = max(1, int(frame_count / max(1.0, interval_val)))
            else:
                extracted_frames = max(1, int((frame_count / fps) / max(0.1, interval_val)))

            job_images = extracted_frames * cams
            total_images += job_images

            # Estimate image size (jpg ~1.2MB, png ~4MB)
            fmt = s.get('output_format', 'jpg')
            mb_per_img = 1.2 if fmt == 'jpg' else (4.5 if fmt == 'png' else 8.0)
            mb_per_img *= (res / 2048.0) ** 2
            total_size_mb += job_images * mb_per_img

        gb_size = total_size_mb / 1024.0
        est_sec = total_images * 0.05  # ~20 images/s with Metal GPU
        m, sec = divmod(int(est_sec), 60)

        self.estimation_label.setText(
            f"{total_images:,} pinhole images ({len(self.jobs)} videos) • ~{gb_size:.1f} GB • Est. time: ~{m}m {sec:02d}s"
        )
        self.extract_btn.setText(f"Extract Dataset ({len(self.jobs)} video{'s' if len(self.jobs) > 1 else ''})")
        self.extract_btn.setEnabled(not self.is_processing)

    # =========================================================================
    # BLUR ANALYSIS
    # =========================================================================

    def analyze_blur_for_selected(self):
        if not self._selected_cards:
            QMessageBox.information(self, "No Video Selected", "Please select a video from the queue to analyze.")
            return

        card = self._selected_cards[-1]
        self.btn_analyze.setText("Analyzing...")
        self.btn_analyze.setEnabled(False)

        self._blur_thread = QThread()
        self._blur_worker = BlurAnalysisWorker(card.job.file_path, card.job.settings or self.default_settings)
        self._blur_worker.moveToThread(self._blur_thread)

        self._blur_thread.started.connect(self._blur_worker.run)
        self._blur_worker.finished.connect(self._on_blur_analysis_finished)
        self._blur_worker.error.connect(self._on_blur_analysis_error)
        self._blur_worker.finished.connect(self._blur_thread.quit)
        self._blur_worker.finished.connect(self._blur_worker.deleteLater)
        self._blur_thread.finished.connect(self._blur_thread.deleteLater)
        self._blur_thread.start()

    def _on_blur_analysis_finished(self, optimal_threshold: float, mean_score: float):
        self.btn_analyze.setText("🔍 Analyze")
        self.btn_analyze.setEnabled(True)
        self.blur_threshold_spin.setValue(optimal_threshold)
        self.blur_toggle.setChecked(True)
        self.on_setting_changed()
        QMessageBox.information(
            self,
            "Blur Analysis Complete",
            f"Video Analysis Results:\n\n• Average Blur Score: {mean_score:.1f}\n• Recommended Threshold: {optimal_threshold:.1f}\n\nThreshold applied and enabled."
        )

    def _on_blur_analysis_error(self, error_msg: str):
        self.btn_analyze.setText("🔍 Analyze")
        self.btn_analyze.setEnabled(True)
        QMessageBox.warning(self, "Analysis Error", f"Could not analyze video:\n{error_msg}")

    # =========================================================================
    # PROCESSING WORKER EXECUTION
    # =========================================================================

    def start_processing(self):
        if not self.jobs:
            QMessageBox.information(self, "Queue Empty", "Please add at least one video to process.")
            return

        self.is_processing = True
        self.extract_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.hud_progress.show()
        self.hud_progress.setValue(0)

        # Build processing jobs
        jobs_to_process = [j for j in self.jobs if j.status in ("Pending", "Error")]
        if not jobs_to_process:
            jobs_to_process = self.jobs

        bridge = ProcessingBridge()
        bridge.log_message.connect(self.log_panel.append_log)
        bridge.progress_updated.connect(self._on_processing_progress)
        bridge.all_finished.connect(self._on_processing_finished)

        self.worker = ProcessingWorker(jobs_to_process, bridge=bridge)
        self.worker.start()

    def cancel_processing(self):
        if hasattr(self, 'worker') and self.worker:
            self.worker.cancel()
            self.cancel_btn.setEnabled(False)
            self.log_panel.append_log("Cancelling extraction process...")

    def _on_processing_progress(self, current: int, total: int):
        if total > 0:
            pct = int((current / total) * 100)
            self.hud_progress.setValue(pct)

    def _on_processing_finished(self):
        self.is_processing = False
        self.extract_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.hud_progress.hide()
        for card in self._video_cards:
            card.refresh()
        self.update_estimate()
        QMessageBox.information(self, "Extraction Complete", "All media jobs have finished processing.")