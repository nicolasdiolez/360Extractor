import os
import copy
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QGroupBox, QLabel, QSpinBox,
    QComboBox, QFileDialog, QProgressBar, QMessageBox,
    QDoubleSpinBox, QListWidget, QListWidgetItem, QAbstractItemView,
    QCheckBox, QSplitter, QScrollArea, QMenu, QTabWidget
)
from PySide6.QtGui import QAction, QDesktopServices
from PySide6.QtCore import Qt, QFile, QTextStream, QThread, QUrl, QEvent, QObject
import subprocess
import platform

from ui.widgets import DropZone
from ui.preview_widget import PreviewWidget
from core.processor import ProcessingWorker
from core.analyzer import BlurAnalysisWorker
from core.job import Job
from core.settings_manager import SettingsManager
from PySide6.QtCore import Signal
from core.version import APP_NAME, VERSION

class ScrollBlocker(QObject):
    """
    Event filter to block scroll events on widgets unless they have focus.
    This prevents accidental value changes when scrolling the parent container.
    """
    def eventFilter(self, obj, event):
        if event.type() == QEvent.Wheel:
            if not obj.hasFocus():
                event.ignore()
                return True # Event handled (blocked)
        return False # Propagate standard event

class EmptyStateWidget(QLabel):
    files_dropped = Signal(list)
    
    def __init__(self):
        super().__init__()
        self.setText("Drag & Drop 360° Videos Here to Start")
        self.setAlignment(Qt.AlignCenter)
        self.setAcceptDrops(True)
        self.setObjectName("emptyStateWidget")

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
            self.setProperty("dragActive", True)
            self.style().polish(self)
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        self.setProperty("dragActive", False)
        self.style().polish(self)

    def dropEvent(self, event):
        # Reset style
        self.setProperty("dragActive", False)
        self.style().polish(self)
        
        files = []
        for url in event.mimeData().urls():
            files.append(url.toLocalFile())
        
        if files:
            self.files_dropped.emit(files)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} - 360° Video Preprocessor")
        self.setMinimumSize(900, 700) # Increased slightly for better default spacing
        
        # Internal State
        self.jobs = []
        self.default_settings = {}
        self.custom_output_dir = ""  # Stores the current custom output directory
        self.is_processing = False

        # Scroll Blocker for Inputs
        self.scroll_blocker = ScrollBlocker(self)
        
        # Load Stylesheet
        self.load_stylesheet("styles.qss")

        # Central Widget & Layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        self.main_layout = QVBoxLayout(central_widget)
        self.main_layout.setSpacing(20)
        self.main_layout.setContentsMargins(30, 30, 30, 30)

        # 0. Menu Bar
        self.create_menu_bar()

        # 0. Header
        header = QLabel("360 Extractor Processor")
        header.setObjectName("headerLabel")
        header.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.main_layout.addWidget(header)

        # Content Splitter (Queue Area | Settings)
        content_splitter = QSplitter(Qt.Horizontal)
        
        # 1. Queue Area (Left) - Vertical Splitter
        left_splitter = QSplitter(Qt.Vertical)
        
        # Top Part Container (Drop Zone + List + Controls)
        queue_top_widget = QWidget()
        queue_top_layout = QVBoxLayout(queue_top_widget)
        queue_top_layout.setContentsMargins(0, 0, 0, 0)
        queue_top_layout.setSpacing(10)
        # Ensure queue area doesn't shrink too much
        queue_top_widget.setMinimumHeight(200)
        
        # Drop Zone
        self.drop_zone = DropZone()
        self.drop_zone.files_dropped.connect(self.handle_files_dropped)
        self.drop_zone.clicked.connect(self.open_file_dialog)
        self.drop_zone.setMinimumHeight(100)
        queue_top_layout.addWidget(self.drop_zone)
        
        # Queue List
        self.job_list = QListWidget()
        self.job_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.job_list.setDragDropMode(QAbstractItemView.InternalMove)
        self.job_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.job_list.customContextMenuRequested.connect(self.show_context_menu)
        self.job_list.itemSelectionChanged.connect(self.on_selection_changed)
        # Handle drop event to reorder underlying list
        self.job_list.model().rowsMoved.connect(self.on_rows_moved)
        queue_top_layout.addWidget(self.job_list)

        # Empty State Label
        self.empty_state_label = EmptyStateWidget()
        self.empty_state_label.files_dropped.connect(self.handle_files_dropped)
        queue_top_layout.addWidget(self.empty_state_label)
        
        # Queue Controls
        queue_controls = QHBoxLayout()
        self.btn_remove = QPushButton("Remove Selected")
        self.btn_remove.clicked.connect(self.remove_selected_jobs)
        self.btn_clear = QPushButton("Clear Queue")
        self.btn_clear.clicked.connect(self.clear_queue)
        
        queue_controls.addWidget(self.btn_remove)
        queue_controls.addWidget(self.btn_clear)
        queue_top_layout.addLayout(queue_controls)
        
        left_splitter.addWidget(queue_top_widget)

        # Preview Widget (Bottom Part)
        self.preview_widget = PreviewWidget()
        self.preview_widget.setMinimumHeight(250) # Ensure preview is always visible
        left_splitter.addWidget(self.preview_widget)
        
        # Set stretch factors for vertical splitter (Top:Bottom -> 1:1 or as preferred)
        left_splitter.setStretchFactor(0, 4)
        left_splitter.setStretchFactor(1, 3)
        
        content_splitter.addWidget(left_splitter)

        # 2. Settings Panel (Right) wrapped in ScrollArea
        settings_scroll = QScrollArea()
        settings_scroll.setWidgetResizable(True)
        settings_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        settings_scroll.setMinimumWidth(320) # Prevent settings from being crushed
        
        self.settings_group = QGroupBox("Default Settings")
        self.settings_panel_layout = self.create_settings_layout()
        self.settings_group.setLayout(self.settings_panel_layout)
        
        settings_scroll.setWidget(self.settings_group)
        content_splitter.addWidget(settings_scroll)
        
        # Set stretch factors (2:1 ratio roughly)
        content_splitter.setStretchFactor(0, 5) # Queue/Preview
        content_splitter.setStretchFactor(1, 2) # Settings
        
        self.main_layout.addWidget(content_splitter)
        
        # 3. Action Buttons & Progress
        self.create_action_area()
        
        # Initialize Default Settings
        self.settings_manager = SettingsManager()
        self.set_ui_from_settings(self.settings_manager.get_all())
        self.update_default_settings_from_ui()
        
        # Initial Visibility Update
        self.update_queue_visibility()

    def update_queue_visibility(self):
        has_jobs = len(self.jobs) > 0
        self.job_list.setVisible(has_jobs)
        self.empty_state_label.setVisible(not has_jobs)

    def closeEvent(self, event):
        self.settings_manager.save_settings()
        super().closeEvent(event)

    def load_stylesheet(self, filename):
        # Resolve path relative to this file to ensure it works from any working directory
        base_dir = os.path.dirname(os.path.abspath(__file__))
        path = os.path.join(base_dir, filename)
        
        file = QFile(path)
        if file.open(QFile.ReadOnly | QFile.Text):
            stream = QTextStream(file)
            self.setStyleSheet(stream.readAll())
            file.close()
        else:
            print(f"Warning: Could not load stylesheet from {path}")

    def create_menu_bar(self):
        menu_bar = self.menuBar()
        
        # Help Menu
        help_menu = menu_bar.addMenu("Help")
        
        # Report Issue
        report_action = QAction("Report Issue", self)
        report_action.triggered.connect(self.report_issue)
        help_menu.addAction(report_action)
        
        # About
        about_action = QAction("About 360 Extractor", self)
        about_action.triggered.connect(self.show_about_dialog)
        help_menu.addAction(about_action)

    def add_setting_row(self, layout, label_text, widget, tooltip_text):
        """
        Helper to create a standardized settings row with a label, help button, and control widget.
        """
        row_layout = QHBoxLayout()
        
        label = QLabel(label_text)
        row_layout.addWidget(label)
        
        help_btn = QPushButton("?")
        help_btn.setFixedSize(16, 16)
        help_btn.setFlat(True)
        help_btn.setCursor(Qt.PointingHandCursor)
        help_btn.setToolTip(tooltip_text)
        help_btn.setObjectName("helpButton")
        row_layout.addWidget(help_btn)
        
        # Spacer to push widget to the right
        row_layout.addStretch()
        
        row_layout.addWidget(widget)
        layout.addLayout(row_layout)

    def report_issue(self):
        # Open a dummy URL or GitHub link
        QDesktopServices.openUrl(QUrl("https://github.com/example/360Extractor/issues"))

    def show_about_dialog(self):
        QMessageBox.about(
            self,
            f"About {APP_NAME}",
            f"{APP_NAME} - 360° Video Preprocessor\n\n"
            f"Version {VERSION}\n\n"
            "A tool for processing 360° videos into rectilinear frames for photogrammetry."
        )

    def create_settings_layout(self):
        # Vertical layout for side panel
        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(0, 0, 0, 0) # Tabs take full space

        self.settings_tabs = QTabWidget()
        layout.addWidget(self.settings_tabs)

        # --- Tab 1: Export ---
        tab_export = QWidget()
        export_layout = QVBoxLayout(tab_export)
        export_layout.setSpacing(15)
        
        # Output Format
        self.format_combo = QComboBox()
        self.format_combo.addItems(["jpg", "png", "tiff"])
        self.format_combo.currentTextChanged.connect(self.on_setting_changed)
        self.format_combo.installEventFilter(self.scroll_blocker)
        self.add_setting_row(export_layout, "Output Format:", self.format_combo, "Choose file format (JPG=Standard, PNG=Lossless).")

        # Output Directory
        dir_layout = QVBoxLayout()
        dir_layout.setSpacing(5)
        dir_layout.addWidget(QLabel("Output Folder:"))
        
        dir_controls = QHBoxLayout()
        self.btn_select_output = QPushButton("Select...")
        self.btn_select_output.clicked.connect(self.select_output_directory)
        self.btn_select_output.setFixedWidth(80)
        
        self.output_dir_label = QLabel("Default: Source Folder")
        self.output_dir_label.setObjectName("outputDirLabel")
        self.output_dir_label.setProperty("isDefault", True)
        self.output_dir_label.setWordWrap(True)
        
        dir_controls.addWidget(self.btn_select_output)
        dir_controls.addWidget(self.output_dir_label)
        
        dir_layout.addLayout(dir_controls)
        export_layout.addLayout(dir_layout)
        
        # Extraction Interval
        interval_layout = QVBoxLayout()
        interval_layout.setSpacing(5)
        interval_layout.addWidget(QLabel("Extraction Interval:"))
        
        interval_controls = QHBoxLayout()
        self.interval_spin = QDoubleSpinBox()
        self.interval_spin.setRange(0.1, 3600.0)
        self.interval_spin.setValue(1.0)
        self.interval_spin.setSingleStep(0.5)
        self.interval_spin.valueChanged.connect(self.on_setting_changed)
        self.interval_spin.installEventFilter(self.scroll_blocker)
        
        self.interval_unit = QComboBox()
        self.interval_unit.addItems(["Seconds", "Frames"])
        self.interval_unit.setCurrentText("Seconds")
        self.interval_unit.currentTextChanged.connect(self.on_setting_changed)
        self.interval_unit.installEventFilter(self.scroll_blocker)
        
        interval_controls.addWidget(self.interval_spin)
        interval_controls.addWidget(self.interval_unit)
        interval_layout.addLayout(interval_controls)
        
        export_layout.addLayout(interval_layout)

        # Output Resolution
        res_layout = QVBoxLayout()
        res_layout.setSpacing(5)
        res_layout.addWidget(QLabel("Output Resolution (px):"))
        self.res_spin = QSpinBox()
        self.res_spin.setRange(512, 4096)
        self.res_spin.setValue(1024)
        self.res_spin.setSingleStep(128)
        self.res_spin.valueChanged.connect(self.on_setting_changed)
        self.res_spin.installEventFilter(self.scroll_blocker)
        res_layout.addWidget(self.res_spin)
        export_layout.addLayout(res_layout)
        
        export_layout.addStretch()
        self.settings_tabs.addTab(tab_export, "Export")

        # --- Tab 2: Camera ---
        tab_camera = QWidget()
        camera_layout = QVBoxLayout(tab_camera)
        camera_layout.setSpacing(15)

        # FOV
        self.fov_spin = QSpinBox()
        self.fov_spin.setRange(60, 120)
        self.fov_spin.setValue(90)
        self.fov_spin.valueChanged.connect(self.on_setting_changed)
        self.fov_spin.installEventFilter(self.scroll_blocker)
        self.add_setting_row(camera_layout, "Field of View (°):", self.fov_spin, "Field of View for each virtual camera.")

        # Camera Count
        self.cam_count_spin = QSpinBox()
        self.cam_count_spin.setRange(2, 36)
        self.cam_count_spin.setValue(6)
        self.cam_count_spin.valueChanged.connect(self.on_setting_changed)
        self.cam_count_spin.installEventFilter(self.scroll_blocker)
        self.add_setting_row(camera_layout, "Camera Count:", self.cam_count_spin, "Number of virtual cameras to extract (2-36). Note: Locked to 6 for Cube Map layout.")

        # Camera Layout
        self.layout_combo = QComboBox()
        self.layout_combo.addItem("Ring", "ring")
        self.layout_combo.addItem("Cube Map", "cube")
        self.layout_combo.addItem("Fibonacci Sphere", "fibonacci")
        self.layout_combo.currentIndexChanged.connect(self.on_layout_changed)
        self.layout_combo.installEventFilter(self.scroll_blocker)
        self.add_setting_row(camera_layout, "Layout Mode:", self.layout_combo, "Choose camera arrangement.")

        # Camera Inclination (Pitch)
        self.pitch_combo = QComboBox()
        self.pitch_combo.addItem("Top Down / Nadir (-90°)", -90)
        self.pitch_combo.addItem("Very High (-60°)", -60)
        self.pitch_combo.addItem("High (-45°)", -45)
        self.pitch_combo.addItem("Medium High (-30°)", -30)
        self.pitch_combo.addItem("Perch (-20°)", -20)
        self.pitch_combo.addItem("Slightly High (-10°)", -10)
        self.pitch_combo.addItem("Standard (0°)", 0)
        self.pitch_combo.addItem("Slightly Low (+10°)", 10)
        self.pitch_combo.addItem("Ground (+20°)", 20)
        self.pitch_combo.addItem("Medium Low (+30°)", 30)
        self.pitch_combo.addItem("Low (+45°)", 45)
        self.pitch_combo.addItem("Very Low (+60°)", 60)
        self.pitch_combo.currentIndexChanged.connect(self.on_setting_changed)
        self.pitch_combo.installEventFilter(self.scroll_blocker)
        self.add_setting_row(camera_layout, "Camera Inclination:", self.pitch_combo, "Vertical angle adjustment (e.g., -20 for high-mounted cameras).")
        
        camera_layout.addStretch()
        self.settings_tabs.addTab(tab_camera, "Camera")

        # --- Tab 3: Processing ---
        tab_processing = QWidget()
        processing_layout = QVBoxLayout(tab_processing)
        processing_layout.setSpacing(15)

        # AI Mode
        self.ai_combo = QComboBox()
        self.ai_combo.addItems(["None", "Skip Frame", "Generate Mask"])
        self.ai_combo.currentTextChanged.connect(self.on_setting_changed)
        self.ai_combo.installEventFilter(self.scroll_blocker)
        self.add_setting_row(processing_layout, "AI Operator Removal:", self.ai_combo, "Skip frames or generate masks when a person is detected.")

        # Blur Filter Group
        blur_group = QGroupBox("Blur Filter")
        blur_layout = QVBoxLayout()
        blur_layout.setSpacing(10)
        
        # Checkbox for enabling filter
        self.blur_check = QCheckBox("Enable Blur Filter")
        self.blur_check.toggled.connect(self.on_blur_toggled)
        blur_layout.addWidget(self.blur_check)

        # Smart Blur (Adaptive)
        self.smart_blur_check = QCheckBox("Smart Blur (Adaptive)")
        self.smart_blur_check.setToolTip("EXPERIMENTAL: Uses adaptive thresholding to detect motion blur. May produce inconsistent results.")
        self.smart_blur_check.toggled.connect(self.on_smart_blur_toggled)
        self.smart_blur_check.setEnabled(False) # Default disabled until blur is checked
        blur_layout.addWidget(self.smart_blur_check)

        # Threshold Control
        threshold_layout = QHBoxLayout()
        self.threshold_label = QLabel("Threshold:")
        threshold_layout.addWidget(self.threshold_label)
        self.blur_threshold_spin = QDoubleSpinBox()
        self.blur_threshold_spin.setRange(0.0, 1000.0)
        self.blur_threshold_spin.setValue(100.0)
        self.blur_threshold_spin.setSingleStep(10.0)
        self.blur_threshold_spin.setEnabled(False) # Disabled by default
        self.blur_threshold_spin.setToolTip("Higher values are stricter (require sharper images). Lower values allow more blur. Use 'Analyze' to find a good baseline.")
        self.blur_threshold_spin.valueChanged.connect(self.on_setting_changed)
        self.blur_threshold_spin.installEventFilter(self.scroll_blocker)
        threshold_layout.addWidget(self.blur_threshold_spin)
        
        blur_layout.addLayout(threshold_layout)

        # Analyze Button
        self.btn_analyze = QPushButton("Analyze Selected Video")
        self.btn_analyze.clicked.connect(self.analyze_blur)
        blur_layout.addWidget(self.btn_analyze)
        
        blur_group.setLayout(blur_layout)
        processing_layout.addWidget(blur_group)
        
        # --- Post-Processing Settings ---
        post_group = QGroupBox("Post-Processing")
        post_layout = QVBoxLayout()
        post_layout.setSpacing(5)
        
        # Sharpening
        self.sharpen_check = QCheckBox("Enable Sharpening")
        self.sharpen_check.toggled.connect(self.on_sharpen_toggled)
        post_layout.addWidget(self.sharpen_check)
        
        # Strength Slider
        sharpen_ctrl_layout = QHBoxLayout()
        sharpen_ctrl_layout.addWidget(QLabel("Strength:"))
        
        self.sharpen_slider = QDoubleSpinBox()
        self.sharpen_slider.setRange(0.0, 2.0)
        self.sharpen_slider.setSingleStep(0.1)
        self.sharpen_slider.setValue(0.5)
        self.sharpen_slider.setEnabled(False)
        self.sharpen_slider.valueChanged.connect(self.on_setting_changed)
        self.sharpen_slider.installEventFilter(self.scroll_blocker)
        sharpen_ctrl_layout.addWidget(self.sharpen_slider)
        
        post_layout.addLayout(sharpen_ctrl_layout)
        post_group.setLayout(post_layout)
        processing_layout.addWidget(post_group)

        processing_layout.addStretch()
        self.settings_tabs.addTab(tab_processing, "Processing")

        # --- Tab 4: Experimental ---
        tab_experimental = QWidget()
        experimental_layout = QVBoxLayout(tab_experimental)
        experimental_layout.setSpacing(15)

        # Adaptive Interval Group
        adaptive_group = QGroupBox("Adaptive Extraction")
        adaptive_layout = QVBoxLayout()
        adaptive_layout.setSpacing(10)

        self.adaptive_check = QCheckBox("Adaptive Interval (Motion-Based)")
        self.adaptive_check.setToolTip("Analyzes optical flow to skip redundant frames when the camera is stationary. Useful for photogrammetry datasets.")
        self.adaptive_check.toggled.connect(self.on_adaptive_toggled)
        adaptive_layout.addWidget(self.adaptive_check)

        # Motion Threshold
        motion_layout = QHBoxLayout()
        self.motion_label = QLabel("Motion Threshold:")
        motion_layout.addWidget(self.motion_label)

        self.motion_threshold_spin = QDoubleSpinBox()
        self.motion_threshold_spin.setRange(0.0, 10.0)
        self.motion_threshold_spin.setValue(0.5)
        self.motion_threshold_spin.setSingleStep(0.1)
        self.motion_threshold_spin.setEnabled(False)
        self.motion_threshold_spin.valueChanged.connect(self.on_setting_changed)
        self.motion_threshold_spin.installEventFilter(self.scroll_blocker)
        motion_layout.addWidget(self.motion_threshold_spin)
        adaptive_layout.addLayout(motion_layout)
        
        adaptive_group.setLayout(adaptive_layout)
        experimental_layout.addWidget(adaptive_group)

        # Telemetry Group
        telemetry_group = QGroupBox("Metadata")
        telemetry_layout = QVBoxLayout()
        
        self.export_telemetry_check = QCheckBox("Export GPS/IMU Metadata")
        self.export_telemetry_check.setToolTip("Attempts to extract GPMF (GoPro) or CAMM metadata and embed GPS into extracted frames.")
        self.export_telemetry_check.toggled.connect(self.on_setting_changed)
        telemetry_layout.addWidget(self.export_telemetry_check)
        
        telemetry_group.setLayout(telemetry_layout)
        experimental_layout.addWidget(telemetry_group)

        experimental_layout.addStretch()
        self.settings_tabs.addTab(tab_experimental, "Experimental")
        
        return layout

    def create_action_area(self):
        # Container layout
        container_layout = QVBoxLayout()
        
        # Buttons layout
        buttons_layout = QHBoxLayout()
        
        self.process_btn = QPushButton("Process Queue")
        self.process_btn.setMinimumHeight(45)
        self.process_btn.clicked.connect(self.start_processing)
        self.process_btn.setEnabled(False) # Disabled until files are added
        
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setObjectName("cancelButton")
        self.cancel_btn.setMinimumHeight(45)
        self.cancel_btn.clicked.connect(self.cancel_processing)
        self.cancel_btn.setEnabled(False) # Disabled until processing starts
        
        buttons_layout.addWidget(self.process_btn)
        buttons_layout.addWidget(self.cancel_btn)
        
        # Progress Bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("%p% - Waiting...")
        self.progress_bar.setMinimumHeight(25)
        
        # Status Label (Log area)
        self.status_label = QLabel("Ready")
        self.status_label.setObjectName("statusLabel")
        self.status_label.setAlignment(Qt.AlignLeft)
        
        container_layout.addLayout(buttons_layout)
        container_layout.addWidget(self.progress_bar)
        container_layout.addWidget(self.status_label)
        
        self.main_layout.addLayout(container_layout)

    # --- Settings Management ---

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
            'export_telemetry': self.export_telemetry_check.isChecked(),
            'ai_mode': self.ai_combo.currentText(),
            'adaptive_mode': self.adaptive_check.isChecked(),
            'adaptive_threshold': self.motion_threshold_spin.value(),
            'blur_filter_enabled': self.blur_check.isChecked(),
            'smart_blur_enabled': self.smart_blur_check.isChecked(),
            'blur_threshold': self.blur_threshold_spin.value(),
            'sharpening_enabled': self.sharpen_check.isChecked(),
            'sharpening_strength': self.sharpen_slider.value()
        }

    def set_ui_from_settings(self, settings):
        # Block signals to prevent triggering on_setting_changed loops
        self.block_settings_signals(True)
        
        # Output Format
        self.format_combo.setCurrentText(settings.get('output_format', 'jpg'))
        
        # Output Directory
        self.custom_output_dir = settings.get('custom_output_dir', "")
        if self.custom_output_dir:
            self.output_dir_label.setText(self.custom_output_dir)
            self.output_dir_label.setProperty("isDefault", False)
            self.output_dir_label.style().polish(self.output_dir_label)
        else:
            self.output_dir_label.setText("Default: Source Folder")
            self.output_dir_label.setProperty("isDefault", True)
            self.output_dir_label.style().polish(self.output_dir_label)

        self.interval_spin.setValue(settings.get('interval_value', 1.0))
        self.interval_unit.setCurrentText(settings.get('interval_unit', 'Seconds'))
        
        self.adaptive_check.setChecked(settings.get('adaptive_mode', False))
        self.motion_threshold_spin.setValue(settings.get('adaptive_threshold', 0.5))
        self.motion_threshold_spin.setEnabled(self.adaptive_check.isChecked())

        self.res_spin.setValue(settings.get('resolution', 1024))
        self.export_telemetry_check.setChecked(settings.get('export_telemetry', False))
        self.fov_spin.setValue(settings.get('fov', 90))
        self.cam_count_spin.setValue(settings.get('camera_count', 6))
        
        layout_val = settings.get('layout_mode', 'ring')
        # Handle legacy 'adaptive' -> default to 'ring'
        if layout_val == 'adaptive':
             layout_val = 'ring'

        idx = self.layout_combo.findData(layout_val)
        if idx >= 0:
            self.layout_combo.setCurrentIndex(idx)
        else:
            self.layout_combo.setCurrentIndex(0)
            
        # Update UI state for layout
        if layout_val == 'cube':
            self.cam_count_spin.setEnabled(False)
            # Ensure count is 6 (though settings should have it, enforcement is good)
            self.cam_count_spin.setValue(6)
        else:
            self.cam_count_spin.setEnabled(True)

        pitch_val = settings.get('pitch_offset', 0)
        index = self.pitch_combo.findData(pitch_val)
        if index >= 0:
            self.pitch_combo.setCurrentIndex(index)
            
        self.ai_combo.setCurrentText(settings.get('ai_mode', 'None'))
        
        self.blur_check.setChecked(settings.get('blur_filter_enabled', False))
        self.smart_blur_check.setChecked(settings.get('smart_blur_enabled', False))
        
        # Update UI state based on loaded settings
        self.update_blur_ui_state()
        
        self.blur_threshold_spin.setValue(settings.get('blur_threshold', 100.0))
        
        self.sharpen_check.setChecked(settings.get('sharpening_enabled', False))
        self.sharpen_slider.setValue(settings.get('sharpening_strength', 0.5))
        self.sharpen_slider.setEnabled(self.sharpen_check.isChecked())

        self.block_settings_signals(False)

    def block_settings_signals(self, block):
        self.format_combo.blockSignals(block)
        self.interval_spin.blockSignals(block)
        self.interval_unit.blockSignals(block)
        self.adaptive_check.blockSignals(block)
        self.motion_threshold_spin.blockSignals(block)
        self.res_spin.blockSignals(block)
        self.export_telemetry_check.blockSignals(block)
        self.fov_spin.blockSignals(block)
        self.cam_count_spin.blockSignals(block)
        self.layout_combo.blockSignals(block)
        self.pitch_combo.blockSignals(block)
        self.ai_combo.blockSignals(block)
        self.blur_check.blockSignals(block)
        self.smart_blur_check.blockSignals(block)
        self.blur_threshold_spin.blockSignals(block)
        self.sharpen_check.blockSignals(block)
        self.sharpen_slider.blockSignals(block)

    def update_default_settings_from_ui(self):
        self.default_settings = self.get_settings_from_ui()

    def on_adaptive_toggled(self, checked):
        self.motion_threshold_spin.setEnabled(checked)
        self.on_setting_changed()

    def on_layout_changed(self, index):
        mode = self.layout_combo.currentData()
        if mode == 'cube':
            self.cam_count_spin.setValue(6)
            self.cam_count_spin.setEnabled(False)
        else:
            self.cam_count_spin.setEnabled(True)
        self.on_setting_changed()

    def select_output_directory(self):
        dir_path = QFileDialog.getExistingDirectory(self, "Select Output Directory")
        if dir_path:
            self.custom_output_dir = dir_path
            self.output_dir_label.setText(dir_path)
            self.output_dir_label.setProperty("isDefault", False)
            self.output_dir_label.style().polish(self.output_dir_label)
            self.on_setting_changed()

    def on_blur_toggled(self, checked):
        self.update_blur_ui_state()
        self.on_setting_changed()

    def on_smart_blur_toggled(self, checked):
        self.update_blur_ui_state()
        self.on_setting_changed()

    def update_blur_ui_state(self):
        blur_enabled = self.blur_check.isChecked()
        self.smart_blur_check.setEnabled(blur_enabled)
        self.blur_threshold_spin.setEnabled(blur_enabled)
        
        if blur_enabled and self.smart_blur_check.isChecked():
            self.threshold_label.setText("Min Floor:")
            self.blur_threshold_spin.setToolTip("Minimum acceptable sharpness score, even with adaptive logic.")
        else:
            self.threshold_label.setText("Threshold:")
            self.blur_threshold_spin.setToolTip("Higher values are stricter (require sharper images). Lower values allow more blur.")

    def on_sharpen_toggled(self, checked):
        self.sharpen_slider.setEnabled(checked)
        self.on_setting_changed()

    def on_setting_changed(self):
        if self.is_processing:
            return

        current_settings = self.get_settings_from_ui()
        selected_items = self.job_list.selectedItems()
        
        if len(selected_items) == 1:
            # Updating a specific job
            row = self.job_list.row(selected_items[0])
            job = self.jobs[row]
            job.settings = current_settings
            # Update list item text
            self.refresh_job_item(row)
        elif len(selected_items) == 0:
            # Updating defaults
            self.default_settings = current_settings
            for key, value in current_settings.items():
                self.settings_manager.set(key, value)
        # If multiple selected, we generally treat it as modifying defaults or nothing (simplified)
        # Requirement says: "If *no* video is selected (or multiple), the panel controls the 'Default Settings'"
        else:
             self.default_settings = current_settings
             for key, value in current_settings.items():
                self.settings_manager.set(key, value)
        
        self.update_preview_display()

    # --- Queue Management ---

    def handle_files_dropped(self, files):
        valid_extensions = ['.mp4', '.mov', '.mkv', '.avi']
        valid_files = [f for f in files if os.path.splitext(f)[1].lower() in valid_extensions]
        
        if valid_files:
            for f in valid_files:
                self.add_job(f)
            self.process_btn.setEnabled(True)
        else:
            QMessageBox.warning(self, "Invalid Files", "Please drop .mp4, .mov, .mkv, or .avi files.")

    def open_file_dialog(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, 
            "Select 360° Videos", 
            "", 
            "Video Files (*.mp4 *.mov *.mkv *.avi)"
        )
        if files:
            self.handle_files_dropped(files)

    def add_job(self, file_path):
        job = Job(file_path=file_path, settings=copy.deepcopy(self.default_settings))
        self.jobs.append(job)
        
        item = QListWidgetItem()
        item.setData(Qt.UserRole, job) # Bind job object to item for robust tracking
        self.job_list.addItem(item)
        self.refresh_job_item(len(self.jobs) - 1)
        
        self.update_queue_visibility()

    def refresh_job_item(self, index):
        if 0 <= index < len(self.jobs):
            job = self.jobs[index]
            item = self.job_list.item(index)
            item.setText(f"{job.filename} | {job.status} | {job.summary()}")

    def remove_selected_jobs(self):
        selected_items = self.job_list.selectedItems()
        if not selected_items:
            return
            
        # Remove from bottom to top to avoid index shifting issues
        rows = sorted([self.job_list.row(i) for i in selected_items], reverse=True)
        
        for row in rows:
            self.job_list.takeItem(row)
            self.jobs.pop(row)
            
        if not self.jobs:
            self.process_btn.setEnabled(False)
            
        self.update_queue_visibility()

    def clear_queue(self):
        self.job_list.clear()
        self.jobs = []
        self.process_btn.setEnabled(False)
        self.update_queue_visibility()

    def on_selection_changed(self):
        selected_items = self.job_list.selectedItems()
        
        if len(selected_items) == 1:
            row = self.job_list.row(selected_items[0])
            job = self.jobs[row]
            self.settings_group.setTitle(f"Settings (Video: {job.filename})")
            self.set_ui_from_settings(job.settings)
        else:
            self.settings_group.setTitle("Default Settings")
            self.set_ui_from_settings(self.default_settings)
        
        self.update_preview_display()

    def update_preview_display(self):
        selected_items = self.job_list.selectedItems()
        if len(selected_items) == 1:
            row = self.job_list.row(selected_items[0])
            job = self.jobs[row]
            # Use current UI settings to reflect immediate changes
            self.preview_widget.update_preview(job.file_path, self.get_settings_from_ui())
        else:
            self.preview_widget.update_preview(None, None)

    # --- Processing ---

    def start_processing(self):
        if not self.jobs:
            return

        self.toggle_processing_state(True)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("Initializing...")
        
        # Reset statuses
        for i, job in enumerate(self.jobs):
            job.status = "Pending"
            self.refresh_job_item(i)
        
        # Setup Thread and Worker
        self.thread = QThread()
        self.worker = ProcessingWorker(self.jobs) # Passes reference to jobs list
        self.worker.moveToThread(self.thread)
        
        # Connect Signals
        self.thread.started.connect(self.worker.run)
        self.worker.job_started.connect(self.on_job_started)
        self.worker.job_finished.connect(self.on_job_finished)
        self.worker.progress_updated.connect(self.update_progress)
        self.worker.finished.connect(self.processing_finished)
        self.worker.error_occurred.connect(self.processing_error)
        
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        
        # Start
        self.thread.start()

    def cancel_processing(self):
        if hasattr(self, 'worker'):
            self.progress_bar.setFormat("Cancelling...")
            self.worker.stop()
            self.cancel_btn.setEnabled(False)

    def toggle_processing_state(self, is_processing):
        self.is_processing = is_processing
        self.process_btn.setEnabled(not is_processing)
        self.cancel_btn.setEnabled(is_processing)
        self.drop_zone.setEnabled(not is_processing)
        self.btn_remove.setEnabled(not is_processing)
        self.btn_clear.setEnabled(not is_processing)
        
        # Disable settings during processing
        self.settings_group.setEnabled(not is_processing)
        
        if is_processing:
            self.process_btn.setText("Processing Queue...")
            self.job_list.setDragDropMode(QAbstractItemView.NoDragDrop)
        else:
            self.process_btn.setText("Process Queue")
            self.job_list.setDragDropMode(QAbstractItemView.InternalMove)

    def on_job_started(self, index):
        if 0 <= index < len(self.jobs):
            self.jobs[index].status = "Processing"
            self.refresh_job_item(index)
            # Ensure visible
            self.job_list.scrollToItem(self.job_list.item(index))

    def on_job_finished(self, index):
        if 0 <= index < len(self.jobs):
            self.jobs[index].status = "Done"
            
            # Update item text with visual indicator
            item = self.job_list.item(index)
            if item:
                job = self.jobs[index]
                item.setText(f"✅ {job.filename} | Done | {job.summary()}")
                # Optional: Ensure it keeps the data or just rely on index
    
    def update_progress(self, value, message):
        self.progress_bar.setValue(value)
        self.progress_bar.setFormat(f"{value}%")
        self.status_label.setText(message)

    def processing_finished(self):
        self.toggle_processing_state(False)
        self.progress_bar.setValue(100)
        self.progress_bar.setFormat("Queue Complete")
        self.status_label.setText("Batch processing completed!")
        QMessageBox.information(self, "Success", "Batch processing completed successfully.")

    def processing_error(self, message):
        self.toggle_processing_state(False)
        self.progress_bar.setFormat("Error Occurred")
        self.status_label.setText(f"Error: {message}")
        QMessageBox.critical(self, "Error", message)
        if hasattr(self, 'worker'):
            self.worker.stop()

    # --- Analysis ---

    def analyze_blur(self):
        selected_items = self.job_list.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Selection Required", "Please select a video from the queue to analyze.")
            return
            
        row = self.job_list.row(selected_items[0])
        job = self.jobs[row]
        
        self.status_label.setText(f"Analyzing {job.filename}...")
        self.btn_analyze.setEnabled(False)
        self.btn_analyze.setText("Analyzing...")
        
        # Threaded analysis
        self.analysis_thread = QThread()
        self.analysis_worker = BlurAnalysisWorker(job.file_path, job.settings)
        self.analysis_worker.moveToThread(self.analysis_thread)
        
        self.analysis_thread.started.connect(self.analysis_worker.run)
        self.analysis_worker.finished.connect(self.on_analysis_finished)
        self.analysis_worker.error.connect(self.on_analysis_error)
        
        # Cleanup
        self.analysis_worker.finished.connect(self.analysis_thread.quit)
        self.analysis_worker.finished.connect(self.analysis_worker.deleteLater)
        self.analysis_thread.finished.connect(self.analysis_thread.deleteLater)
        self.analysis_worker.error.connect(self.analysis_thread.quit)
        self.analysis_worker.error.connect(self.analysis_worker.deleteLater)
        
        self.analysis_thread.start()

    def on_analysis_finished(self, result):
        self.btn_analyze.setEnabled(True)
        self.btn_analyze.setText("Analyze Selected Video")
        self.status_label.setText("Analysis complete.")
        
        avg = result['average']
        recommendation = avg * 0.8
        
        msg = (
            f"Sample Frame Analysis:\n\n"
            f"Average Sharpness: {avg:.2f}\n"
            f"Min: {result['min']:.2f} / Max: {result['max']:.2f}\n\n"
            f"Recommendation: Set threshold slightly below the Average (e.g., {recommendation:.2f})."
        )
        
        QMessageBox.information(self, "Blur Analysis Result", msg)
        
        # Optional: Auto-set the threshold? The requirement doesn't say so, just recommendation.
        # But we could offer it. For now sticking to requirements.

    def on_analysis_error(self, error_msg):
        self.btn_analyze.setEnabled(True)
        self.btn_analyze.setText("Analyze Selected Video")
        self.status_label.setText("Analysis failed.")
        QMessageBox.critical(self, "Analysis Error", f"Failed to analyze video:\n{error_msg}")

    # --- Context Menu & List Management ---

    def on_rows_moved(self, parent, start, end, destination, row):
        """
        Called when rows are moved via Drag & Drop.
        Rebuilds the self.jobs list to match the new visual order.
        """
        new_jobs = []
        for i in range(self.job_list.count()):
            item = self.job_list.item(i)
            job = item.data(Qt.UserRole)
            if job:
                new_jobs.append(job)
            else:
                # Fallback if for some reason UserRole is missing (shouldn't happen with new add_job)
                # Try to map by matching filename? Or just keep existing?
                # This case is risky, but with add_job fixed it should be fine.
                print(f"Warning: Item at index {i} has no Job data.")
        
        if len(new_jobs) == len(self.jobs):
            self.jobs = new_jobs
    
    def show_context_menu(self, position):
        item = self.job_list.itemAt(position)
        if not item:
            return
            
        menu = QMenu()
        show_action = QAction("Show in Finder/Explorer", self)
        show_action.triggered.connect(lambda: self.show_in_folder(item))
        menu.addAction(show_action)
        
        menu.exec(self.job_list.viewport().mapToGlobal(position))

    def show_in_folder(self, item):
        job = item.data(Qt.UserRole)
        # Fallback if job not bound (legacy items before restart? shouldn't happen in fresh run)
        if not job:
            row = self.job_list.row(item)
            if 0 <= row < len(self.jobs):
                job = self.jobs[row]
        
        if not job:
            return

        # Determine output directory
        custom_dir = job.output_dir
        if custom_dir and os.path.isdir(custom_dir):
            base_output_dir = custom_dir
        else:
            base_output_dir = os.path.dirname(job.file_path)
            
        # Specific processed folder
        output_dir = os.path.join(base_output_dir, f"{os.path.splitext(job.filename)[0]}_processed")
        
        target_path = output_dir if os.path.exists(output_dir) else base_output_dir
        
        QDesktopServices.openUrl(QUrl.fromLocalFile(target_path))