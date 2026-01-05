"""
360 Extractor Pro - Modern Main Window
Redesigned UI with sidebar navigation and modern components.
"""
import os
import copy
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QGroupBox, QLabel, QSpinBox,
    QComboBox, QFileDialog, QProgressBar, QMessageBox,
    QDoubleSpinBox, QListWidget, QListWidgetItem, QAbstractItemView,
    QCheckBox, QSplitter, QScrollArea, QMenu, QStackedWidget,
    QLineEdit, QFrame, QSizePolicy
)
from PySide6.QtGui import QAction, QDesktopServices
from PySide6.QtCore import Qt, QFile, QTextStream, QThread, QUrl, QEvent, QObject, Signal
import subprocess
import platform

from ui.widgets import DropZone
from ui.preview_widget import PreviewWidget
from ui.sidebar import Sidebar
from ui.video_card import VideoCard
from ui.toggle_switch import ToggleSwitch, ToggleSwitchWithDescription
from ui.collapsible_section import CollapsibleSection
from core.processor import ProcessingWorker
from core.analyzer import BlurAnalysisWorker
from core.job import Job
from core.settings_manager import SettingsManager
from core.version import APP_NAME, VERSION


class ScrollBlocker(QObject):
    """Event filter to block scroll events on widgets unless they have focus."""
    def eventFilter(self, obj, event):
        if event.type() == QEvent.Wheel:
            if not obj.hasFocus():
                event.ignore()
                return True
        return False


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} Pro")
        self.setMinimumSize(1100, 750)
        
        # Internal State
        self.jobs = []
        self.default_settings = {}
        self.custom_output_dir = ""
        self.is_processing = False
        self._video_cards = []
        self._selected_card = None

        # Scroll Blocker
        self.scroll_blocker = ScrollBlocker(self)
        
        # Load Stylesheet
        self.load_stylesheet("styles.qss")

        # Central Widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main horizontal layout: Sidebar | Content
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Sidebar Navigation
        self.sidebar = Sidebar()
        self.sidebar.page_changed.connect(self.on_page_changed)
        main_layout.addWidget(self.sidebar)
        
        # Content Area
        content_widget = QWidget()
        content_widget.setObjectName("contentArea")
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(24, 24, 24, 0)
        content_layout.setSpacing(16)
        
        # Stacked widget for pages
        self.pages = QStackedWidget()
        
        # Create pages
        self.videos_page = self.create_videos_page()
        self.settings_page = self.create_settings_page()
        self.export_page = self.create_export_page()
        self.advanced_page = self.create_advanced_page()
        
        self.pages.addWidget(self.videos_page)
        self.pages.addWidget(self.settings_page)
        self.pages.addWidget(self.export_page)
        self.pages.addWidget(self.advanced_page)
        
        content_layout.addWidget(self.pages)
        
        # Action Bar (always visible at bottom)
        self.action_bar = self.create_action_bar()
        content_layout.addWidget(self.action_bar)
        
        main_layout.addWidget(content_widget, 1)
        
        # Initialize Settings
        self.settings_manager = SettingsManager()
        self.set_ui_from_settings(self.settings_manager.get_all())
        self.update_default_settings_from_ui()

    def load_stylesheet(self, filename):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        path = os.path.join(base_dir, filename)
        
        file = QFile(path)
        if file.open(QFile.ReadOnly | QFile.Text):
            stream = QTextStream(file)
            self.setStyleSheet(stream.readAll())
            file.close()

    # =========================================================================
    # PAGE CREATION
    # =========================================================================

    def create_videos_page(self):
        """Create the main videos/queue page."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)
        
        # Header
        header = QLabel("Video Queue")
        header.setObjectName("headerLabel")
        layout.addWidget(header)
        
        # Main content splitter
        splitter = QSplitter(Qt.Horizontal)
        
        # Left side: Queue
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(12)
        
        # Drop Zone
        self.drop_zone = DropZone()
        self.drop_zone.files_dropped.connect(self.handle_files_dropped)
        self.drop_zone.clicked.connect(self.open_file_dialog)
        self.drop_zone.setMinimumHeight(120)
        left_layout.addWidget(self.drop_zone)
        
        # Queue container with scroll
        queue_scroll = QScrollArea()
        queue_scroll.setWidgetResizable(True)
        queue_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        queue_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        
        self.queue_container = QWidget()
        self.queue_container.setObjectName("queueContainer")
        self.queue_layout = QVBoxLayout(self.queue_container)
        self.queue_layout.setContentsMargins(0, 0, 8, 0)
        self.queue_layout.setSpacing(8)
        self.queue_layout.addStretch()
        
        queue_scroll.setWidget(self.queue_container)
        left_layout.addWidget(queue_scroll, 1)
        
        # Queue controls
        controls = QHBoxLayout()
        
        self.btn_remove = QPushButton("Remove Selected")
        self.btn_remove.setProperty("secondary", True)
        self.btn_remove.clicked.connect(self.remove_selected_jobs)
        
        self.btn_clear = QPushButton("Clear Queue")
        self.btn_clear.setProperty("secondary", True)
        self.btn_clear.clicked.connect(self.clear_queue)
        
        controls.addWidget(self.btn_remove)
        controls.addWidget(self.btn_clear)
        controls.addStretch()
        left_layout.addLayout(controls)
        
        splitter.addWidget(left_widget)
        
        # Right side: Preview
        right_widget = QWidget()
        right_widget.setObjectName("previewArea")
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(16, 16, 16, 16)
        
        preview_header = QLabel("Preview")
        preview_header.setStyleSheet("color: #FFFFFF; font-weight: 600; font-size: 14px;")
        right_layout.addWidget(preview_header)
        
        self.preview_widget = PreviewWidget()
        right_layout.addWidget(self.preview_widget, 1)
        
        splitter.addWidget(right_widget)
        
        # Set sizes
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        
        layout.addWidget(splitter, 1)
        
        return page

    def create_settings_page(self):
        """Create the camera/extraction settings page."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)
        
        # Header
        header = QLabel("Camera Settings")
        header.setObjectName("headerLabel")
        layout.addWidget(header)
        
        # Scroll area for settings
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 16, 16)
        content_layout.setSpacing(16)
        
        # Camera Settings Section
        camera_section = CollapsibleSection("Camera Configuration")
        
        # FOV
        fov_row = QHBoxLayout()
        fov_row.addWidget(QLabel("Field of View"))
        fov_row.addStretch()
        self.fov_spin = QSpinBox()
        self.fov_spin.setRange(60, 120)
        self.fov_spin.setValue(90)
        self.fov_spin.setSuffix("°")
        self.fov_spin.setFixedWidth(100)
        self.fov_spin.valueChanged.connect(self.on_setting_changed)
        self.fov_spin.installEventFilter(self.scroll_blocker)
        fov_row.addWidget(self.fov_spin)
        camera_section.addLayout(fov_row)
        
        # Camera Count
        count_row = QHBoxLayout()
        count_row.addWidget(QLabel("Virtual Cameras"))
        count_row.addStretch()
        self.cam_count_spin = QSpinBox()
        self.cam_count_spin.setRange(2, 36)
        self.cam_count_spin.setValue(6)
        self.cam_count_spin.setFixedWidth(100)
        self.cam_count_spin.valueChanged.connect(self.on_setting_changed)
        self.cam_count_spin.installEventFilter(self.scroll_blocker)
        count_row.addWidget(self.cam_count_spin)
        camera_section.addLayout(count_row)
        
        # Layout Mode
        layout_row = QHBoxLayout()
        layout_row.addWidget(QLabel("Layout Mode"))
        layout_row.addStretch()
        self.layout_combo = QComboBox()
        self.layout_combo.addItem("Ring", "ring")
        self.layout_combo.addItem("Cube Map", "cube")
        self.layout_combo.addItem("Fibonacci Sphere", "fibonacci")
        self.layout_combo.setFixedWidth(160)
        self.layout_combo.currentIndexChanged.connect(self.on_layout_changed)
        self.layout_combo.installEventFilter(self.scroll_blocker)
        layout_row.addWidget(self.layout_combo)
        camera_section.addLayout(layout_row)
        
        # Pitch/Inclination
        pitch_row = QHBoxLayout()
        pitch_row.addWidget(QLabel("Camera Inclination"))
        pitch_row.addStretch()
        self.pitch_combo = QComboBox()
        self.pitch_combo.addItem("Top Down (-90°)", -90)
        self.pitch_combo.addItem("High (-45°)", -45)
        self.pitch_combo.addItem("Perch (-20°)", -20)
        self.pitch_combo.addItem("Standard (0°)", 0)
        self.pitch_combo.addItem("Low (+20°)", 20)
        self.pitch_combo.addItem("Ground (+45°)", 45)
        self.pitch_combo.setFixedWidth(160)
        self.pitch_combo.currentIndexChanged.connect(self.on_setting_changed)
        self.pitch_combo.installEventFilter(self.scroll_blocker)
        pitch_row.addWidget(self.pitch_combo)
        camera_section.addLayout(pitch_row)
        
        content_layout.addWidget(camera_section)
        
        # Extraction Section
        extraction_section = CollapsibleSection("Extraction Settings")
        
        # Interval
        interval_row = QHBoxLayout()
        interval_row.addWidget(QLabel("Extraction Interval"))
        interval_row.addStretch()
        
        self.interval_spin = QDoubleSpinBox()
        self.interval_spin.setRange(0.1, 3600.0)
        self.interval_spin.setValue(1.0)
        self.interval_spin.setSingleStep(0.5)
        self.interval_spin.setFixedWidth(80)
        self.interval_spin.valueChanged.connect(self.on_setting_changed)
        self.interval_spin.installEventFilter(self.scroll_blocker)
        interval_row.addWidget(self.interval_spin)
        
        self.interval_unit = QComboBox()
        self.interval_unit.addItems(["Seconds", "Frames"])
        self.interval_unit.setFixedWidth(100)
        self.interval_unit.currentTextChanged.connect(self.on_setting_changed)
        self.interval_unit.installEventFilter(self.scroll_blocker)
        interval_row.addWidget(self.interval_unit)
        
        extraction_section.addLayout(interval_row)
        
        # Resolution
        res_row = QHBoxLayout()
        res_row.addWidget(QLabel("Output Resolution"))
        res_row.addStretch()
        self.res_spin = QSpinBox()
        self.res_spin.setRange(512, 8192)
        self.res_spin.setValue(2048)
        self.res_spin.setSingleStep(256)
        self.res_spin.setSuffix(" px")
        self.res_spin.setFixedWidth(120)
        self.res_spin.valueChanged.connect(self.on_setting_changed)
        self.res_spin.installEventFilter(self.scroll_blocker)
        res_row.addWidget(self.res_spin)
        extraction_section.addLayout(res_row)
        
        content_layout.addWidget(extraction_section)
        content_layout.addStretch()
        
        scroll.setWidget(content)
        layout.addWidget(scroll, 1)
        
        return page

    def create_export_page(self):
        """Create the export settings page."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)
        
        # Header
        header = QLabel("Export Settings")
        header.setObjectName("headerLabel")
        layout.addWidget(header)
        
        # Scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 16, 16)
        content_layout.setSpacing(16)
        
        # Output Section
        output_section = CollapsibleSection("Output Configuration")
        
        # Format
        format_row = QHBoxLayout()
        format_row.addWidget(QLabel("Image Format"))
        format_row.addStretch()
        self.format_combo = QComboBox()
        self.format_combo.addItems(["jpg", "png", "tiff"])
        self.format_combo.setFixedWidth(100)
        self.format_combo.currentTextChanged.connect(self.on_setting_changed)
        self.format_combo.installEventFilter(self.scroll_blocker)
        format_row.addWidget(self.format_combo)
        output_section.addLayout(format_row)
        
        # Output Directory
        dir_row = QHBoxLayout()
        dir_row.addWidget(QLabel("Output Folder"))
        dir_row.addStretch()
        
        self.output_dir_label = QLabel("Source Folder")
        self.output_dir_label.setStyleSheet("color: #52525B; font-style: italic;")
        dir_row.addWidget(self.output_dir_label)
        
        self.btn_select_output = QPushButton("Browse...")
        self.btn_select_output.setProperty("secondary", True)
        self.btn_select_output.setFixedWidth(100)
        self.btn_select_output.clicked.connect(self.select_output_directory)
        dir_row.addWidget(self.btn_select_output)
        output_section.addLayout(dir_row)
        
        content_layout.addWidget(output_section)
        
        # Naming Section
        naming_section = CollapsibleSection("File Naming")
        
        # Naming Mode
        naming_row = QHBoxLayout()
        naming_row.addWidget(QLabel("Naming Convention"))
        naming_row.addStretch()
        self.naming_mode_combo = QComboBox()
        self.naming_mode_combo.addItem("RealityScan (Standard)", "realityscan")
        self.naming_mode_combo.addItem("Simple Suffix", "simple")
        self.naming_mode_combo.addItem("Custom Pattern", "custom")
        self.naming_mode_combo.setFixedWidth(180)
        self.naming_mode_combo.currentIndexChanged.connect(self.on_naming_mode_changed)
        self.naming_mode_combo.installEventFilter(self.scroll_blocker)
        naming_row.addWidget(self.naming_mode_combo)
        naming_section.addLayout(naming_row)
        
        # Custom patterns (hidden by default)
        self.custom_naming_widget = QWidget()
        custom_layout = QVBoxLayout(self.custom_naming_widget)
        custom_layout.setContentsMargins(0, 8, 0, 0)
        custom_layout.setSpacing(8)
        
        img_pattern_row = QHBoxLayout()
        img_pattern_row.addWidget(QLabel("Image Pattern"))
        img_pattern_row.addStretch()
        self.image_pattern_input = QLineEdit()
        self.image_pattern_input.setPlaceholderText("{filename}_frame{frame}_{camera}")
        self.image_pattern_input.setFixedWidth(250)
        self.image_pattern_input.textChanged.connect(self.on_setting_changed)
        img_pattern_row.addWidget(self.image_pattern_input)
        custom_layout.addLayout(img_pattern_row)
        
        mask_pattern_row = QHBoxLayout()
        mask_pattern_row.addWidget(QLabel("Mask Pattern"))
        mask_pattern_row.addStretch()
        self.mask_pattern_input = QLineEdit()
        self.mask_pattern_input.setPlaceholderText("{filename}_frame{frame}_{camera}_mask")
        self.mask_pattern_input.setFixedWidth(250)
        self.mask_pattern_input.textChanged.connect(self.on_setting_changed)
        mask_pattern_row.addWidget(self.mask_pattern_input)
        custom_layout.addLayout(mask_pattern_row)
        
        self.custom_naming_widget.hide()
        naming_section.addWidget(self.custom_naming_widget)
        
        content_layout.addWidget(naming_section)
        content_layout.addStretch()
        
        scroll.setWidget(content)
        layout.addWidget(scroll, 1)
        
        return page

    def create_advanced_page(self):
        """Create the advanced/experimental settings page."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)
        
        # Header
        header = QLabel("Advanced Settings")
        header.setObjectName("headerLabel")
        layout.addWidget(header)
        
        # Scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 16, 16)
        content_layout.setSpacing(16)
        
        # AI Section
        ai_section = CollapsibleSection("AI Processing")
        
        # AI Mode
        ai_row = QHBoxLayout()
        ai_row.addWidget(QLabel("Operator Removal"))
        ai_row.addStretch()
        self.ai_combo = QComboBox()
        self.ai_combo.addItems(["None", "Skip Frame", "Generate Mask"])
        self.ai_combo.setFixedWidth(160)
        self.ai_combo.currentTextChanged.connect(self.on_setting_changed)
        self.ai_combo.installEventFilter(self.scroll_blocker)
        ai_row.addWidget(self.ai_combo)
        ai_section.addLayout(ai_row)
        
        content_layout.addWidget(ai_section)
        
        # Blur Section
        blur_section = CollapsibleSection("Blur Detection")
        
        # Enable Blur
        self.blur_toggle = ToggleSwitchWithDescription("Enable Blur Filter", "Skip blurry frames")
        self.blur_toggle.toggled.connect(self.on_blur_toggled)
        blur_section.addWidget(self.blur_toggle)
        
        # Smart Blur
        self.smart_blur_toggle = ToggleSwitchWithDescription("Smart Mode", "Adaptive threshold")
        self.smart_blur_toggle.toggled.connect(self.on_smart_blur_toggled)
        blur_section.addWidget(self.smart_blur_toggle)
        
        # Threshold
        threshold_row = QHBoxLayout()
        threshold_row.addWidget(QLabel("Threshold"))
        threshold_row.addStretch()
        self.blur_threshold_spin = QDoubleSpinBox()
        self.blur_threshold_spin.setRange(0.0, 1000.0)
        self.blur_threshold_spin.setValue(100.0)
        self.blur_threshold_spin.setSingleStep(10.0)
        self.blur_threshold_spin.setFixedWidth(100)
        self.blur_threshold_spin.valueChanged.connect(self.on_setting_changed)
        self.blur_threshold_spin.installEventFilter(self.scroll_blocker)
        threshold_row.addWidget(self.blur_threshold_spin)
        blur_section.addLayout(threshold_row)
        
        # Analyze button
        self.btn_analyze = QPushButton("Analyze Selected Video")
        self.btn_analyze.setProperty("secondary", True)
        self.btn_analyze.clicked.connect(self.analyze_blur)
        blur_section.addWidget(self.btn_analyze)
        
        content_layout.addWidget(blur_section)
        
        # Post-Processing Section
        post_section = CollapsibleSection("Post-Processing")
        
        # Sharpening
        self.sharpen_toggle = ToggleSwitchWithDescription("Enable Sharpening", "Enhance details")
        self.sharpen_toggle.toggled.connect(self.on_sharpen_toggled)
        post_section.addWidget(self.sharpen_toggle)
        
        # Sharpen Strength
        sharpen_row = QHBoxLayout()
        sharpen_row.addWidget(QLabel("Strength"))
        sharpen_row.addStretch()
        self.sharpen_slider = QDoubleSpinBox()
        self.sharpen_slider.setRange(0.0, 2.0)
        self.sharpen_slider.setSingleStep(0.1)
        self.sharpen_slider.setValue(0.5)
        self.sharpen_slider.setFixedWidth(100)
        self.sharpen_slider.valueChanged.connect(self.on_setting_changed)
        self.sharpen_slider.installEventFilter(self.scroll_blocker)
        sharpen_row.addWidget(self.sharpen_slider)
        post_section.addLayout(sharpen_row)
        
        content_layout.addWidget(post_section)
        
        # Experimental Section
        exp_section = CollapsibleSection("Experimental Features")
        
        # Adaptive Mode
        self.adaptive_toggle = ToggleSwitchWithDescription("Adaptive Interval", "Motion-based extraction")
        self.adaptive_toggle.toggled.connect(self.on_adaptive_toggled)
        exp_section.addWidget(self.adaptive_toggle)
        
        # Motion Threshold
        motion_row = QHBoxLayout()
        motion_row.addWidget(QLabel("Motion Threshold"))
        motion_row.addStretch()
        self.motion_threshold_spin = QDoubleSpinBox()
        self.motion_threshold_spin.setRange(0.0, 10.0)
        self.motion_threshold_spin.setValue(0.5)
        self.motion_threshold_spin.setSingleStep(0.1)
        self.motion_threshold_spin.setFixedWidth(100)
        self.motion_threshold_spin.setEnabled(False)
        self.motion_threshold_spin.valueChanged.connect(self.on_setting_changed)
        self.motion_threshold_spin.installEventFilter(self.scroll_blocker)
        motion_row.addWidget(self.motion_threshold_spin)
        exp_section.addLayout(motion_row)
        
        # Telemetry
        self.telemetry_toggle = ToggleSwitchWithDescription("Export GPS/IMU", "Embed metadata in images")
        self.telemetry_toggle.toggled.connect(self.on_setting_changed)
        exp_section.addWidget(self.telemetry_toggle)
        
        content_layout.addWidget(exp_section)
        content_layout.addStretch()
        
        scroll.setWidget(content)
        layout.addWidget(scroll, 1)
        
        return page

    def create_action_bar(self):
        """Create the bottom action bar."""
        bar = QWidget()
        bar.setObjectName("actionBar")
        bar.setFixedHeight(100)
        
        layout = QVBoxLayout(bar)
        layout.setContentsMargins(0, 16, 0, 16)
        layout.setSpacing(12)
        
        # Buttons row
        buttons = QHBoxLayout()
        
        self.process_btn = QPushButton("▶  Start Processing")
        self.process_btn.setFixedHeight(48)
        self.process_btn.clicked.connect(self.start_processing)
        self.process_btn.setEnabled(False)
        
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setObjectName("cancelButton")
        self.cancel_btn.setFixedHeight(48)
        self.cancel_btn.setFixedWidth(120)
        self.cancel_btn.clicked.connect(self.cancel_processing)
        self.cancel_btn.setEnabled(False)
        
        buttons.addWidget(self.process_btn, 1)
        buttons.addWidget(self.cancel_btn)
        layout.addLayout(buttons)
        
        # Progress row
        progress_layout = QHBoxLayout()
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(8)
        
        self.status_label = QLabel("Ready")
        self.status_label.setObjectName("statusLabel")
        self.status_label.setFixedWidth(200)
        self.status_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        
        progress_layout.addWidget(self.progress_bar, 1)
        progress_layout.addWidget(self.status_label)
        layout.addLayout(progress_layout)
        
        return bar

    # =========================================================================
    # PAGE NAVIGATION
    # =========================================================================

    def on_page_changed(self, page_id):
        page_map = {
            "videos": 0,
            "settings": 1,
            "export": 2,
            "advanced": 3,
        }
        self.pages.setCurrentIndex(page_map.get(page_id, 0))

    # =========================================================================
    # SETTINGS MANAGEMENT
    # =========================================================================

    def get_settings_from_ui(self):
        return {
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
            'ai_mode': self.ai_combo.currentText(),
            'adaptive_mode': self.adaptive_toggle.isChecked(),
            'adaptive_threshold': self.motion_threshold_spin.value(),
            'blur_filter_enabled': self.blur_toggle.isChecked(),
            'smart_blur_enabled': self.smart_blur_toggle.isChecked(),
            'blur_threshold': self.blur_threshold_spin.value(),
            'sharpening_enabled': self.sharpen_toggle.isChecked(),
            'sharpening_strength': self.sharpen_slider.value(),
            'naming_mode': self.naming_mode_combo.currentData(),
            'image_pattern': self.image_pattern_input.text(),
            'mask_pattern': self.mask_pattern_input.text()
        }

    def set_ui_from_settings(self, settings):
        # Block signals temporarily
        widgets = [
            self.format_combo, self.interval_spin, self.interval_unit,
            self.res_spin, self.fov_spin, self.cam_count_spin,
            self.layout_combo, self.pitch_combo, self.ai_combo,
            self.blur_threshold_spin, self.sharpen_slider,
            self.motion_threshold_spin, self.naming_mode_combo,
            self.image_pattern_input, self.mask_pattern_input
        ]
        for w in widgets:
            w.blockSignals(True)
        
        # Set values
        self.format_combo.setCurrentText(settings.get('output_format', 'jpg'))
        self.custom_output_dir = settings.get('custom_output_dir', "")
        if self.custom_output_dir:
            self.output_dir_label.setText(os.path.basename(self.custom_output_dir))
            self.output_dir_label.setStyleSheet("color: #FFFFFF;")
        
        self.interval_spin.setValue(settings.get('interval_value', 1.0))
        self.interval_unit.setCurrentText(settings.get('interval_unit', 'Seconds'))
        self.res_spin.setValue(settings.get('resolution', 2048))
        self.fov_spin.setValue(settings.get('fov', 90))
        self.cam_count_spin.setValue(settings.get('camera_count', 6))
        
        layout_val = settings.get('layout_mode', 'ring')
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
        
        self.blur_toggle.setChecked(settings.get('blur_filter_enabled', False))
        self.smart_blur_toggle.setChecked(settings.get('smart_blur_enabled', False))
        self.blur_threshold_spin.setValue(settings.get('blur_threshold', 100.0))
        
        self.sharpen_toggle.setChecked(settings.get('sharpening_enabled', False))
        self.sharpen_slider.setValue(settings.get('sharpening_strength', 0.5))
        
        self.adaptive_toggle.setChecked(settings.get('adaptive_mode', False))
        self.motion_threshold_spin.setValue(settings.get('adaptive_threshold', 0.5))
        self.motion_threshold_spin.setEnabled(self.adaptive_toggle.isChecked())
        
        self.telemetry_toggle.setChecked(settings.get('export_telemetry', False))
        
        naming_mode = settings.get('naming_mode', 'realityscan')
        idx = self.naming_mode_combo.findData(naming_mode)
        if idx >= 0:
            self.naming_mode_combo.setCurrentIndex(idx)
        self.image_pattern_input.setText(settings.get('image_pattern', ''))
        self.mask_pattern_input.setText(settings.get('mask_pattern', ''))
        self.update_naming_ui_state()
        
        # Unblock signals
        for w in widgets:
            w.blockSignals(False)

    def update_default_settings_from_ui(self):
        self.default_settings = self.get_settings_from_ui()

    def on_setting_changed(self):
        if self.is_processing:
            return
            
        current_settings = self.get_settings_from_ui()
        
        if self._selected_card:
            self._selected_card.job.settings = current_settings
            self._selected_card.refresh()
        else:
            self.default_settings = current_settings
            for key, value in current_settings.items():
                self.settings_manager.set(key, value)
        
        self.update_preview_display()

    # =========================================================================
    # UI STATE HANDLERS
    # =========================================================================

    def on_layout_changed(self, index):
        mode = self.layout_combo.currentData()
        if mode == 'cube':
            self.cam_count_spin.setValue(6)
            self.cam_count_spin.setEnabled(False)
        else:
            self.cam_count_spin.setEnabled(True)
        self.on_setting_changed()

    def on_blur_toggled(self, checked):
        self.blur_threshold_spin.setEnabled(checked)
        self.smart_blur_toggle.setChecked(False)
        self.on_setting_changed()

    def on_smart_blur_toggled(self, checked):
        self.on_setting_changed()

    def on_sharpen_toggled(self, checked):
        self.sharpen_slider.setEnabled(checked)
        self.on_setting_changed()

    def on_adaptive_toggled(self, checked):
        self.motion_threshold_spin.setEnabled(checked)
        self.on_setting_changed()

    def on_naming_mode_changed(self, index):
        self.update_naming_ui_state()
        self.on_setting_changed()

    def update_naming_ui_state(self):
        mode = self.naming_mode_combo.currentData()
        self.custom_naming_widget.setVisible(mode == 'custom')

    def select_output_directory(self):
        dir_path = QFileDialog.getExistingDirectory(self, "Select Output Directory")
        if dir_path:
            self.custom_output_dir = dir_path
            self.output_dir_label.setText(os.path.basename(dir_path))
            self.output_dir_label.setStyleSheet("color: #FFFFFF;")
            self.on_setting_changed()

    # =========================================================================
    # QUEUE MANAGEMENT
    # =========================================================================

    def handle_files_dropped(self, files):
        valid_extensions = ['.mp4', '.mov', '.mkv', '.avi']
        valid_files = [f for f in files if os.path.splitext(f)[1].lower() in valid_extensions]
        
        if valid_files:
            for f in valid_files:
                self.add_job(f)
            self.process_btn.setEnabled(True)
        else:
            QMessageBox.warning(self, "Invalid Files", "Please drop video files (.mp4, .mov, .mkv, .avi)")

    def open_file_dialog(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Select 360° Videos", "", "Video Files (*.mp4 *.mov *.mkv *.avi)"
        )
        if files:
            self.handle_files_dropped(files)

    def add_job(self, file_path):
        job = Job(file_path=file_path, settings=copy.deepcopy(self.default_settings))
        self.jobs.append(job)
        
        # Create video card
        card = VideoCard(job)
        card.clicked.connect(lambda c=card: self.on_card_clicked(c))
        card.remove_clicked.connect(lambda c=card: self.remove_job_by_card(c))
        
        # Insert before stretch
        self.queue_layout.insertWidget(self.queue_layout.count() - 1, card)
        self._video_cards.append(card)

    def on_card_clicked(self, card):
        # Deselect previous
        if self._selected_card:
            self._selected_card.setSelected(False)
        
        # Select new
        card.setSelected(True)
        self._selected_card = card
        
        # Update settings UI
        self.set_ui_from_settings(card.job.settings)
        self.update_preview_display()

    def remove_job_by_card(self, card):
        if card in self._video_cards:
            idx = self._video_cards.index(card)
            self._video_cards.remove(card)
            self.jobs.pop(idx)
            card.deleteLater()
            
            if card == self._selected_card:
                self._selected_card = None
                self.set_ui_from_settings(self.default_settings)
                self.update_preview_display()
            
            if not self.jobs:
                self.process_btn.setEnabled(False)

    def remove_selected_jobs(self):
        if self._selected_card:
            self.remove_job_by_card(self._selected_card)

    def clear_queue(self):
        for card in self._video_cards[:]:
            card.deleteLater()
        self._video_cards.clear()
        self.jobs.clear()
        self._selected_card = None
        self.process_btn.setEnabled(False)
        self.set_ui_from_settings(self.default_settings)
        self.update_preview_display()

    def update_preview_display(self):
        if self._selected_card:
            job = self._selected_card.job
            self.preview_widget.update_preview(job.file_path, self.get_settings_from_ui())
        else:
            self.preview_widget.update_preview(None, None)

    # =========================================================================
    # PROCESSING
    # =========================================================================

    def start_processing(self):
        if not self.jobs:
            return
            
        self.toggle_processing_state(True)
        self.progress_bar.setValue(0)
        self.status_label.setText("Initializing...")
        
        for card in self._video_cards:
            card.update_status("Pending")
        
        self.thread = QThread()
        self.worker = ProcessingWorker(self.jobs)
        self.worker.moveToThread(self.thread)
        
        self.thread.started.connect(self.worker.run)
        self.worker.job_started.connect(self.on_job_started)
        self.worker.job_finished.connect(self.on_job_finished)
        self.worker.progress_updated.connect(self.update_progress)
        self.worker.finished.connect(self.processing_finished)
        self.worker.error_occurred.connect(self.processing_error)
        
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        
        self.thread.start()

    def cancel_processing(self):
        if hasattr(self, 'worker'):
            self.status_label.setText("Cancelling...")
            self.worker.stop()
            self.cancel_btn.setEnabled(False)

    def toggle_processing_state(self, is_processing):
        self.is_processing = is_processing
        self.process_btn.setEnabled(not is_processing)
        self.cancel_btn.setEnabled(is_processing)
        self.drop_zone.setEnabled(not is_processing)
        self.btn_remove.setEnabled(not is_processing)
        self.btn_clear.setEnabled(not is_processing)
        self.sidebar.setEnabled(not is_processing)
        
        if is_processing:
            self.process_btn.setText("Processing...")
        else:
            self.process_btn.setText("▶  Start Processing")

    def on_job_started(self, index):
        if 0 <= index < len(self._video_cards):
            self._video_cards[index].update_status("Processing")

    def on_job_finished(self, index):
        if 0 <= index < len(self._video_cards):
            self._video_cards[index].update_status("Done")

    def update_progress(self, value, message):
        self.progress_bar.setValue(value)
        self.status_label.setText(message.split(" - ")[0] if " - " in message else message)
        
        # Update current job progress
        for i, card in enumerate(self._video_cards):
            if card.job.status == "Processing":
                card.set_progress(value)

    def processing_finished(self):
        self.toggle_processing_state(False)
        self.progress_bar.setValue(100)
        self.status_label.setText("Complete!")
        QMessageBox.information(self, "Success", "Batch processing completed successfully.")

    def processing_error(self, message):
        self.toggle_processing_state(False)
        self.status_label.setText("Error")
        QMessageBox.critical(self, "Error", message)
        if hasattr(self, 'worker'):
            self.worker.stop()

    # =========================================================================
    # ANALYSIS
    # =========================================================================

    def analyze_blur(self):
        if not self._selected_card:
            QMessageBox.warning(self, "Selection Required", "Please select a video to analyze.")
            return
        
        job = self._selected_card.job
        self.status_label.setText(f"Analyzing {job.filename}...")
        self.btn_analyze.setEnabled(False)
        self.btn_analyze.setText("Analyzing...")
        
        self.analysis_thread = QThread()
        self.analysis_worker = BlurAnalysisWorker(job.file_path, job.settings)
        self.analysis_worker.moveToThread(self.analysis_thread)
        
        self.analysis_thread.started.connect(self.analysis_worker.run)
        self.analysis_worker.finished.connect(self.on_analysis_finished)
        self.analysis_worker.error.connect(self.on_analysis_error)
        
        self.analysis_worker.finished.connect(self.analysis_thread.quit)
        self.analysis_worker.finished.connect(self.analysis_worker.deleteLater)
        self.analysis_thread.finished.connect(self.analysis_thread.deleteLater)
        self.analysis_worker.error.connect(self.analysis_thread.quit)
        self.analysis_worker.error.connect(self.analysis_worker.deleteLater)
        
        self.analysis_thread.start()

    def on_analysis_finished(self, result):
        self.btn_analyze.setEnabled(True)
        self.btn_analyze.setText("Analyze Selected Video")
        self.status_label.setText("Analysis complete")
        
        avg = result['average']
        recommendation = avg * 0.8
        
        QMessageBox.information(
            self, "Blur Analysis",
            f"Average Sharpness: {avg:.2f}\n"
            f"Min: {result['min']:.2f} / Max: {result['max']:.2f}\n\n"
            f"Recommended threshold: {recommendation:.2f}"
        )

    def on_analysis_error(self, error_msg):
        self.btn_analyze.setEnabled(True)
        self.btn_analyze.setText("Analyze Selected Video")
        self.status_label.setText("Analysis failed")
        QMessageBox.critical(self, "Error", f"Analysis failed: {error_msg}")

    # =========================================================================
    # LIFECYCLE
    # =========================================================================

    def closeEvent(self, event):
        self.settings_manager.save_settings()
        super().closeEvent(event)