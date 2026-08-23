#!/usr/bin/env python3
"""360 Extractor Studio - Complete Settings Mockup with 3 Color Themes.

Features:
- 100% of all settings from the original application cleanly organized in 4 collapsible cards.
- Real-time Theme Switcher with 3 distinct professional palettes:
    1. Theme A: "Graphite & Warm Amber" (Cinema / DaVinci Resolve / Blender)
    2. Theme B: "Titanium & Monochrome" (Photography / Capture One / Leica)
    3. Theme C: "Ardoise & Sauge" (Geospatial / Photogrammetry / RealityCapture)
- Interactive camera face selector (Front, Right, Back, Left, Up, Down), real-time mask overlay.
- Timeline scrubber with timecode and frame counter.

Usage:
    # Interactive mode (with real-time theme buttons):
    python scripts/mockup_studio_ui.py --interactive

    # Render all 3 theme screenshots:
    python scripts/mockup_studio_ui.py --all-themes
"""
from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path

# Ensure offscreen is NOT set before importing Qt if interactive
if "--interactive" in sys.argv:
    os.environ.pop("QT_QPA_PLATFORM", None)

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

import cv2  # noqa: E402
import numpy as np  # noqa: E402
from PySide6.QtCore import Qt, QTimer  # noqa: E402
from PySide6.QtGui import QImage, QPixmap  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QApplication, QCheckBox, QComboBox, QDoubleSpinBox, QFrame,
    QGridLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QMainWindow,
    QPushButton, QScrollArea, QSlider, QSpinBox,
    QSplitter, QTabWidget, QVBoxLayout, QWidget
)

from extractor360.core.geometry import GeometryProcessor  # noqa: E402


def make_demo_equirect(path: Path, width: int = 2048, height: int = 1024) -> np.ndarray:
    """Create rich synthetic 360 equirectangular scene."""
    img = np.zeros((height, width, 3), dtype=np.uint8)
    horizon = height // 2

    # Sky dusk gradient
    for y in range(horizon):
        t = y / horizon
        b = int(120 * (1 - t) + 200 * t)
        g = int(60 * (1 - t) + 160 * t)
        r = int(30 * (1 - t) + 80 * t)
        img[y, :] = (b, g, r)

    # Ground slate
    for y in range(horizon, height):
        t = (y - horizon) / (height - horizon)
        b = int(45 + 30 * t)
        g = int(45 + 35 * t)
        r = int(45 + 30 * t)
        img[y, :] = (b, g, r)

    # Perspective grid lines
    for x in range(0, width, width // 64):
        cv2.line(img, (x, horizon), (x, height), (75, 85, 80), 1)
    for i in range(1, 16):
        y = horizon + int((height - horizon) * (i / 16) ** 2)
        cv2.line(img, (0, y), (width, y), (75, 85, 80), 1)

    # Architectural pillars
    palette = [
        (220, 110, 80), (90, 190, 240), (120, 210, 140),
        (210, 140, 200), (80, 220, 220), (200, 100, 120),
    ]
    for i, colour in enumerate(palette):
        cx = int((i + 0.5) * width / len(palette))
        w = width // 50
        h_val = height // 5
        cv2.rectangle(img, (cx - w, horizon - h_val), (cx + w, horizon), colour, -1)
        cv2.rectangle(img, (cx - w, horizon - h_val), (cx + w, horizon), (20, 20, 25), 2)

    cv2.line(img, (0, horizon), (width, horizon), (230, 200, 150), 2)

    # Nadir Tripod at bottom
    nadir_cx = width // 2
    nadir_cy = int(height * 0.9)
    cv2.circle(img, (nadir_cx, nadir_cy), 70, (25, 25, 30), -1)
    cv2.line(img, (nadir_cx, nadir_cy), (nadir_cx - 180, height), (40, 40, 45), 6)
    cv2.line(img, (nadir_cx, nadir_cy), (nadir_cx + 180, height), (40, 40, 45), 6)
    cv2.line(img, (nadir_cx, nadir_cy), (nadir_cx, height), (40, 40, 45), 6)
    cv2.circle(img, (nadir_cx, nadir_cy), 25, (15, 15, 20), -1)

    cv2.imwrite(str(path), img)
    return img


THEMES = {
    "amber": {
        "name": "Graphite & Warm Amber (Resolve/Blender)",
        "bg_win": "#16161A",
        "bg_nav": "#1B1B20",
        "bg_side": "#18181D",
        "bg_center": "#101014",
        "bg_card": "#212127",
        "border": "#2E2E38",
        "border_subtle": "#252530",
        "text_main": "#F4F4F6",
        "text_muted": "#94949E",
        "accent": "#F59E0B",           # Warm Amber
        "accent_hover": "#D97706",
        "accent_bg": "rgba(245, 158, 11, 0.15)",
        "accent_text": "#FBBF24",
        "btn_primary_bg": "#D97706",
        "btn_primary_text": "#FFFFFF",
        "overlay_tint": (20, 80, 200),  # Warm amber-reddish mask
        "overlay_hud": (245, 158, 11),
    },
    "titanium": {
        "name": "Titanium & Monochrome (Capture One/Leica)",
        "bg_win": "#18181B",
        "bg_nav": "#1F1F23",
        "bg_side": "#1B1B1E",
        "bg_center": "#121214",
        "bg_card": "#242429",
        "border": "#363640",
        "border_subtle": "#2A2A33",
        "text_main": "#FFFFFF",
        "text_muted": "#A1A1AA",
        "accent": "#E4E4E7",           # Titanium White / Chrome
        "accent_hover": "#FFFFFF",
        "accent_bg": "rgba(255, 255, 255, 0.12)",
        "accent_text": "#FFFFFF",
        "btn_primary_bg": "#E4E4E7",
        "btn_primary_text": "#121214",
        "overlay_tint": (40, 40, 180),  # Classic brick red mask
        "overlay_hud": (228, 228, 231),
    },
    "sage": {
        "name": "Ardoise & Sauge (Geospatial/RealityCapture)",
        "bg_win": "#131716",
        "bg_nav": "#181D1B",
        "bg_side": "#151A18",
        "bg_center": "#0D1110",
        "bg_card": "#1E2421",
        "border": "#2B3530",
        "border_subtle": "#222B27",
        "text_main": "#ECFDF5",
        "text_muted": "#8FA399",
        "accent": "#10B981",           # Emerald / Sage
        "accent_hover": "#059669",
        "accent_bg": "rgba(16, 185, 129, 0.15)",
        "accent_text": "#34D399",
        "btn_primary_bg": "#059669",
        "btn_primary_text": "#FFFFFF",
        "overlay_tint": (30, 40, 190),  # Soft red mask
        "overlay_hud": (52, 211, 153),
    }
}


class StudioMockupWindow(QMainWindow):
    def __init__(self, demo_image_path: Path, current_theme_key: str = "amber"):
        super().__init__()
        self.setWindowTitle("360 Extractor Studio — Complete Settings & Multi-Theme Preview")
        self.resize(1560, 960)
        self.demo_image_path = demo_image_path
        self.equirect_bgr = cv2.imread(str(demo_image_path))
        if self.equirect_bgr is None:
            self.equirect_bgr = make_demo_equirect(demo_image_path)

        self.current_theme_key = current_theme_key
        self.current_face = "Down"
        self.fov = 90
        self.pitch_offset = 0
        self.nadir_radius = 35.0
        self.show_ai_mask = True
        self.show_nadir_disc = True

        self._build_ui()
        self._apply_theme(self.current_theme_key)
        self._update_viewport_render()

    def _apply_theme(self, theme_key: str):
        self.current_theme_key = theme_key
        t = THEMES[theme_key]

        # Update Theme switcher buttons state
        if hasattr(self, "theme_buttons"):
            for k, btn in self.theme_buttons.items():
                btn.setProperty("active", (k == theme_key))
                btn.setStyle(btn.style())

        self.setStyleSheet(f"""
            QMainWindow {{
                background-color: {t['bg_win']};
                color: {t['text_main']};
            }}
            QWidget {{
                font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI", Roboto, sans-serif;
                font-size: 11px;
                color: {t['text_muted']};
            }}
            QFrame#topNav {{
                background-color: {t['bg_nav']};
                border-bottom: 1px solid {t['border']};
                padding: 0px 14px;
            }}
            QFrame#leftSidebar {{
                background-color: {t['bg_side']};
                border-right: 1px solid {t['border']};
            }}
            QFrame#centerArea {{
                background-color: {t['bg_center']};
            }}
            QFrame#rightInspector {{
                background-color: {t['bg_side']};
                border-left: 1px solid {t['border']};
            }}
            QFrame#viewportContainer {{
                background-color: #000000;
                border: 1px solid {t['border']};
                border-radius: 6px;
            }}
            QFrame#hudBar {{
                background-color: {t['bg_nav']};
                border-top: 1px solid {t['border']};
                padding: 6px 16px;
            }}
            QFrame#inspectorCard {{
                background-color: {t['bg_card']};
                border: 1px solid {t['border_subtle']};
                border-radius: 6px;
                padding: 10px;
            }}
            QLabel#sectionHeader {{
                color: {t['text_main']};
                font-weight: 600;
                font-size: 11px;
                text-transform: uppercase;
                letter-spacing: 0.6px;
            }}
            QLabel#cardTitle {{
                color: {t['text_main']};
                font-weight: 600;
                font-size: 11px;
            }}
            /* Segmented & Theme Buttons */
            QPushButton#themeBtn {{
                background-color: {t['bg_card']};
                border: 1px solid {t['border_subtle']};
                border-radius: 4px;
                color: {t['text_muted']};
                padding: 4px 10px;
                font-weight: 500;
                font-size: 11px;
            }}
            QPushButton#themeBtn:hover {{
                color: {t['text_main']};
                border-color: {t['border']};
            }}
            QPushButton#themeBtn[active="true"] {{
                background-color: {t['accent_bg']};
                border: 1px solid {t['accent']};
                color: {t['accent_text']};
                font-weight: 600;
            }}
            QPushButton#segmentBtn {{
                background-color: transparent;
                border: none;
                border-radius: 4px;
                color: {t['text_muted']};
                padding: 4px 10px;
                font-weight: 500;
                font-size: 11px;
            }}
            QPushButton#segmentBtn:hover {{
                color: {t['text_main']};
                background-color: rgba(255, 255, 255, 0.05);
            }}
            QPushButton#segmentBtn[active="true"] {{
                background-color: {t['accent_bg']};
                color: {t['accent_text']};
                font-weight: 600;
                border: 1px solid {t['accent']};
            }}
            /* Primary & Secondary Buttons */
            QPushButton#primaryActionBtn {{
                background-color: {t['btn_primary_bg']};
                color: {t['btn_primary_text']};
                font-weight: 600;
                font-size: 12px;
                border-radius: 5px;
                padding: 7px 18px;
                border: none;
            }}
            QPushButton#primaryActionBtn:hover {{
                opacity: 0.9;
            }}
            QPushButton#secondaryActionBtn {{
                background-color: transparent;
                border: 1px solid {t['border']};
                border-radius: 5px;
                color: {t['text_main']};
                padding: 6px 14px;
                font-size: 11px;
            }}
            QPushButton#secondaryActionBtn:hover {{
                background-color: {t['bg_card']};
            }}
            QPushButton#toolBtn {{
                background-color: {t['bg_win']};
                border: 1px solid {t['border']};
                border-radius: 4px;
                color: {t['text_main']};
                padding: 3px 8px;
                font-size: 10px;
            }}
            QPushButton#toolBtn:hover {{
                border-color: {t['accent']};
            }}
            /* Inputs */
            QComboBox, QSpinBox, QDoubleSpinBox, QLineEdit {{
                background-color: {t['bg_win']};
                border: 1px solid {t['border']};
                border-radius: 4px;
                padding: 4px 6px;
                color: {t['text_main']};
                font-size: 11px;
            }}
            QComboBox:focus, QSpinBox:focus, QLineEdit:focus {{
                border-color: {t['accent']};
            }}
            QSlider::groove:horizontal {{
                height: 3px;
                background: {t['border']};
                border-radius: 1.5px;
            }}
            QSlider::sub-page:horizontal {{
                background: {t['accent']};
                border-radius: 1.5px;
            }}
            QSlider::handle:horizontal {{
                background: {t['text_main']};
                border: 1px solid {t['accent']};
                width: 10px;
                margin-top: -3.5px;
                margin-bottom: -3.5px;
                border-radius: 5px;
            }}
            QCheckBox {{
                color: {t['text_main']};
                spacing: 5px;
                font-size: 11px;
            }}
            QCheckBox::indicator {{
                width: 13px;
                height: 13px;
                border-radius: 3px;
                border: 1px solid {t['border']};
                background-color: {t['bg_win']};
            }}
            QCheckBox::indicator:checked {{
                background-color: {t['accent']};
                border-color: {t['accent']};
            }}
            QScrollBar:vertical {{
                border: none;
                background: transparent;
                width: 4px;
            }}
            QScrollBar::handle:vertical {{
                background: {t['border']};
                border-radius: 2px;
            }}
        """)
        self._update_viewport_render()

    def _build_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        root_layout = QVBoxLayout(main_widget)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # 1. Top Navbar: Title + Theme Selector + Preset Target
        top_nav = self._create_top_nav()
        root_layout.addWidget(top_nav)

        # 2. Main 3-Column Splitter
        content_splitter = QSplitter(Qt.Horizontal)
        content_splitter.setHandleWidth(1)

        # Left Column: Media Queue (250px)
        left_col = self._create_left_queue()
        content_splitter.addWidget(left_col)

        # Center Column: Viewport & Timeline (Flex)
        center_col = self._create_center_viewport()
        content_splitter.addWidget(center_col)

        # Right Column: Full Complete Inspector (380px)
        right_col = self._create_right_inspector()
        content_splitter.addWidget(right_col)

        content_splitter.setStretchFactor(0, 0)
        content_splitter.setStretchFactor(1, 1)
        content_splitter.setStretchFactor(2, 0)
        root_layout.addWidget(content_splitter, 1)

        # 3. Bottom HUD Status & Action Bar
        hud_bar = self._create_hud_bar()
        root_layout.addWidget(hud_bar)

    def _create_top_nav(self) -> QWidget:
        nav = QFrame()
        nav.setObjectName("topNav")
        nav.setFixedHeight(46)
        layout = QHBoxLayout(nav)
        layout.setContentsMargins(14, 0, 14, 0)
        layout.setSpacing(12)

        # App Title
        title_label = QLabel("360 Extractor")
        title_label.setStyleSheet("font-weight: 700; font-size: 13px; letter-spacing: -0.2px;")
        layout.addWidget(title_label)

        v_sep = QFrame()
        v_sep.setFrameShape(QFrame.VLine)
        v_sep.setFixedHeight(16)
        layout.addWidget(v_sep)

        # Workflow Presets
        wf_lbl = QLabel("Preset:")
        wf_lbl.setStyleSheet("font-size: 11px;")
        layout.addWidget(wf_lbl)

        self.preset_combo = QComboBox()
        self.preset_combo.addItems([
            "Postshot (3D Gaussian Splatting)",
            "RealityScan / Metashape",
            "COLMAP Calibrated Rig",
            "Custom Workflow"
        ])
        self.preset_combo.setFixedWidth(210)
        layout.addWidget(self.preset_combo)

        layout.addSpacing(16)

        # Live Theme Switcher
        theme_lbl = QLabel("Color Theme:")
        theme_lbl.setStyleSheet("font-size: 11px; font-weight: 600;")
        layout.addWidget(theme_lbl)

        self.theme_buttons = {}
        theme_options = [
            ("amber", "A. Graphite & Ambre"),
            ("titanium", "B. Titanium Monochrome"),
            ("sage", "C. Ardoise & Sauge"),
        ]
        for key, label in theme_options:
            btn = QPushButton(label)
            btn.setObjectName("themeBtn")
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda _, k=key: self._apply_theme(k))
            self.theme_buttons[key] = btn
            layout.addWidget(btn)

        layout.addStretch()

        sys_status = QLabel("Apple Metal (MPS) GPU Active")
        sys_status.setStyleSheet("font-size: 11px;")
        layout.addWidget(sys_status)

        return nav

    def _create_left_queue(self) -> QWidget:
        col = QFrame()
        col.setObjectName("leftSidebar")
        col.setFixedWidth(250)
        layout = QVBoxLayout(col)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # Queue Header
        hdr_layout = QHBoxLayout()
        hdr_title = QLabel("Queue (3 files)")
        hdr_title.setObjectName("sectionHeader")
        hdr_layout.addWidget(hdr_title)
        hdr_layout.addStretch()

        add_btn = QPushButton("+ Add Media")
        add_btn.setObjectName("toolBtn")
        hdr_layout.addWidget(add_btn)
        layout.addLayout(hdr_layout)

        # Subtle Drop Zone
        drop_card = QFrame()
        drop_card.setStyleSheet("""
            background-color: transparent;
            border: 1px dashed rgba(255, 255, 255, 0.15);
            border-radius: 5px;
            padding: 8px;
        """)
        drop_layout = QVBoxLayout(drop_card)
        drop_layout.setAlignment(Qt.AlignCenter)
        drop_layout.setSpacing(2)

        txt_lbl = QLabel("Drop 360° videos or folders")
        txt_lbl.setStyleSheet("font-size: 11px; font-weight: 500;")
        txt_lbl.setAlignment(Qt.AlignCenter)
        drop_layout.addWidget(txt_lbl)

        sub_lbl = QLabel("GoPro Max, Insta360, Kandao, DJI")
        sub_lbl.setStyleSheet("font-size: 10px;")
        sub_lbl.setAlignment(Qt.AlignCenter)
        drop_layout.addWidget(sub_lbl)
        layout.addWidget(drop_card)

        # Scrollable list of files
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        cards_container = QWidget()
        cards_layout = QVBoxLayout(cards_container)
        cards_layout.setContentsMargins(0, 0, 0, 0)
        cards_layout.setSpacing(5)

        items_data = [
            ("GS_PARK_WALK_8K.mp4", "8K 360 • 01:45 • GPS 18Hz/IMU", True),
            ("GOPRO_MAX_INTERIOR.mp4", "5.6K 360 • 03:12 • GPMF Telemetry", False),
            ("DRONE_ROOF_SURVEY.mp4", "4K Flat • 00:58 • SRT Subtitles", False),
        ]

        for name, meta, selected in items_data:
            card = QFrame()
            card.setObjectName("inspectorCard")
            if selected:
                card.setStyleSheet("border: 1px solid rgba(255, 255, 255, 0.4);")
            c_lay = QVBoxLayout(card)
            c_lay.setContentsMargins(6, 6, 6, 6)
            c_lay.setSpacing(2)

            t_lbl = QLabel(name)
            t_lbl.setStyleSheet("font-weight: 600; font-size: 11px;")
            c_lay.addWidget(t_lbl)

            m_lbl = QLabel(meta)
            m_lbl.setStyleSheet("font-size: 10px;")
            c_lay.addWidget(m_lbl)
            cards_layout.addWidget(card)

        cards_layout.addStretch()
        scroll.setWidget(cards_container)
        layout.addWidget(scroll, 1)

        return col

    def _create_center_viewport(self) -> QWidget:
        col = QFrame()
        col.setObjectName("centerArea")
        layout = QVBoxLayout(col)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        # Toolbar with Segmented Face Selector & Overlay Checks
        tb_layout = QHBoxLayout()
        tb_layout.setContentsMargins(0, 0, 0, 0)
        tb_layout.setSpacing(8)

        seg_container = QFrame()
        seg_container.setStyleSheet("background-color: rgba(255, 255, 255, 0.04); border-radius: 5px; padding: 2px;")
        seg_layout = QHBoxLayout(seg_container)
        seg_layout.setContentsMargins(2, 2, 2, 2)
        seg_layout.setSpacing(2)

        self.cam_buttons = {}
        faces = ["Front", "Right", "Back", "Left", "Up", "Down"]
        for face_name in faces:
            btn = QPushButton(face_name)
            btn.setObjectName("segmentBtn")
            btn.setCursor(Qt.PointingHandCursor)
            if face_name == self.current_face:
                btn.setProperty("active", True)
            btn.clicked.connect(lambda _, name=face_name: self._select_cam_face(name))
            self.cam_buttons[face_name] = btn
            seg_layout.addWidget(btn)

        tb_layout.addWidget(seg_container)
        tb_layout.addSpacing(10)

        self.chk_ai_mask = QCheckBox("Mask Overlay")
        self.chk_ai_mask.setChecked(self.show_ai_mask)
        self.chk_ai_mask.stateChanged.connect(self._toggle_ai_mask)
        tb_layout.addWidget(self.chk_ai_mask)

        self.chk_nadir = QCheckBox("Nadir Crop")
        self.chk_nadir.setChecked(self.show_nadir_disc)
        self.chk_nadir.stateChanged.connect(self._toggle_nadir)
        tb_layout.addWidget(self.chk_nadir)

        tb_layout.addStretch()
        layout.addLayout(tb_layout)

        # Viewport Area
        self.viewport_frame = QFrame()
        self.viewport_frame.setObjectName("viewportContainer")
        viewport_layout = QVBoxLayout(self.viewport_frame)
        viewport_layout.setContentsMargins(0, 0, 0, 0)

        self.preview_image_label = QLabel()
        self.preview_image_label.setAlignment(Qt.AlignCenter)
        self.preview_image_label.setStyleSheet("background-color: transparent;")
        viewport_layout.addWidget(self.preview_image_label)

        layout.addWidget(self.viewport_frame, 1)

        # Timeline Scrubber
        tl_bar = QFrame()
        tl_bar.setObjectName("inspectorCard")
        tl_bar.setFixedHeight(38)
        tl_layout = QHBoxLayout(tl_bar)
        tl_layout.setContentsMargins(8, 2, 8, 2)
        tl_layout.setSpacing(8)

        play_btn = QPushButton("▶")
        play_btn.setFixedSize(22, 22)
        play_btn.setObjectName("toolBtn")
        tl_layout.addWidget(play_btn)

        timecode = QLabel("00:14.2 / 01:45.0")
        timecode.setStyleSheet("font-family: monospace; font-size: 10px;")
        tl_layout.addWidget(timecode)

        scrubber = QSlider(Qt.Horizontal)
        scrubber.setRange(0, 100)
        scrubber.setValue(14)
        tl_layout.addWidget(scrubber, 1)

        frame_lbl = QLabel("Frame 426")
        frame_lbl.setStyleSheet("font-family: monospace; font-size: 10px;")
        tl_layout.addWidget(frame_lbl)

        layout.addWidget(tl_bar)
        return col

    def _select_cam_face(self, face_name: str):
        self.current_face = face_name
        for name, btn in self.cam_buttons.items():
            btn.setProperty("active", (name == face_name))
            btn.setStyle(btn.style())
        self._update_viewport_render()

    def _toggle_ai_mask(self, state: int):
        self.show_ai_mask = bool(state)
        self._update_viewport_render()

    def _toggle_nadir(self, state: int):
        self.show_nadir_disc = bool(state)
        self._update_viewport_render()

    def _update_viewport_render(self):
        src_h, src_w = self.equirect_bgr.shape[:2]
        dest_res = 800

        angles = {
            "Front": (0.0, float(self.pitch_offset), 0.0),
            "Right": (90.0, float(self.pitch_offset), 0.0),
            "Back": (180.0, float(self.pitch_offset), 0.0),
            "Left": (270.0, float(self.pitch_offset), 0.0),
            "Up": (0.0, 90.0, 0.0),
            "Down": (0.0, -90.0, 0.0),
        }
        yaw, pitch, roll = angles.get(self.current_face, (0.0, 0.0, 0.0))

        map_x, map_y = GeometryProcessor.create_rectilinear_map(
            src_h, src_w, dest_res, dest_res, self.fov, yaw, pitch, roll
        )
        rect_img = cv2.remap(self.equirect_bgr, map_x, map_y, cv2.INTER_LINEAR)

        t = THEMES[self.current_theme_key]

        # Subtle overlays on Down face
        if self.current_face == "Down":
            overlay = rect_img.copy()
            center_x, center_y = dest_res // 2, dest_res // 2

            # Nadir Disc
            if self.show_nadir_disc:
                radius_px = int((self.nadir_radius / 100.0) * (dest_res / 2.0))
                cv2.circle(overlay, (center_x, center_y), radius_px, (15, 15, 18), -1)
                cv2.circle(overlay, (center_x, center_y), radius_px, t["overlay_hud"], 1)

            # AI Operator Mask
            if self.show_ai_mask:
                op_x1, op_y1 = center_x - 110, center_y + 50
                op_x2, op_y2 = center_x + 110, dest_res - 30
                cv2.ellipse(overlay, ((op_x1 + op_x2) // 2, (op_y1 + op_y2) // 2), (120, 160), 0, 0, 360, t["overlay_tint"], -1)

            cv2.addWeighted(overlay, 0.40, rect_img, 0.60, 0, rect_img)

        # Typographic overlay
        cv2.putText(rect_img, f"{self.current_face.upper()} VIEW", (24, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (230, 230, 235), 1, cv2.LINE_AA)
        cv2.putText(rect_img, f"FOV {self.fov} deg | PINHOLE CALIBRATED", (24, 55), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (150, 150, 160), 1, cv2.LINE_AA)

        # Convert to QPixmap
        rgb = cv2.cvtColor(rect_img, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        qimg = QImage(rgb.data, w, h, ch * w, QImage.Format_RGB888)
        pix = QPixmap.fromImage(qimg).scaled(780, 620, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.preview_image_label.setPixmap(pix)

    def _create_right_inspector(self) -> QWidget:
        col = QFrame()
        col.setObjectName("rightInspector")
        col.setFixedWidth(380)
        layout = QVBoxLayout(col)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        hdr = QLabel("All Processing Settings")
        hdr.setObjectName("sectionHeader")
        layout.addWidget(hdr)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        container = QWidget()
        c_layout = QVBoxLayout(container)
        c_layout.setContentsMargins(0, 0, 4, 0)
        c_layout.setSpacing(8)

        # Section 1: Camera & Optics (Complete)
        c_layout.addWidget(self._create_camera_optics_card())

        # Section 2: Quality & Motion Filters (Complete)
        c_layout.addWidget(self._create_quality_filters_card())

        # Section 3: AI Masking & Nadir (Complete)
        c_layout.addWidget(self._create_ai_masking_card())

        # Section 4: Export & Formats (Complete)
        c_layout.addWidget(self._create_export_calibration_card())

        c_layout.addStretch()
        scroll.setWidget(container)
        layout.addWidget(scroll, 1)
        return col

    def _create_camera_optics_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("inspectorCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        title = QLabel("1. Camera & Projection Geometry")
        title.setObjectName("cardTitle")
        layout.addWidget(title)

        grid = QGridLayout()
        grid.setSpacing(5)

        # 360 Input toggle
        grid.addWidget(QLabel("Media Type:"), 0, 0)
        media_type = QComboBox()
        media_type.addItems(["360° Equirectangular", "Standard Flat Media (Passthrough)"])
        grid.addWidget(media_type, 0, 1)

        # Layout Mode
        grid.addWidget(QLabel("Layout Mode:"), 1, 0)
        layout_cb = QComboBox()
        layout_cb.addItems(["Cube Map (6 Views - Recommended)", "Ring (Horizon 360°)", "Fibonacci Sphere (Dense)"])
        grid.addWidget(layout_cb, 1, 1)

        # Resolution
        grid.addWidget(QLabel("Resolution:"), 2, 0)
        res_cb = QComboBox()
        res_cb.addItems(["2048 x 2048 (Optimized)", "3072 x 3072", "4096 x 4096 (8K)"])
        grid.addWidget(res_cb, 2, 1)

        # FOV Slider
        grid.addWidget(QLabel("FOV (Field of View):"), 3, 0)
        fov_layout = QHBoxLayout()
        fov_slider = QSlider(Qt.Horizontal)
        fov_slider.setRange(60, 120)
        fov_slider.setValue(90)
        fov_lbl = QLabel("90°")
        fov_slider.valueChanged.connect(lambda v: (fov_lbl.setText(f"{v}°"), setattr(self, 'fov', v), self._update_viewport_render()))
        fov_layout.addWidget(fov_slider)
        fov_layout.addWidget(fov_lbl)
        grid.addLayout(fov_layout, 3, 1)

        # Pitch Offset
        grid.addWidget(QLabel("Pitch Tilt Offset:"), 4, 0)
        pitch_cb = QComboBox()
        pitch_cb.addItems(["0° (Horizon Level)", "-20° (High / Perch Mode)", "+20° (Low Mode)"])
        grid.addWidget(pitch_cb, 4, 1)

        layout.addLayout(grid)

        # Checkboxes
        imu_chk = QCheckBox("Auto-Horizon Leveling (IMU Gyro Fusion)")
        imu_chk.setChecked(True)
        layout.addWidget(imu_chk)

        lanczos_chk = QCheckBox("Lanczos-4 High-Sharpness Interpolation")
        layout.addWidget(lanczos_chk)

        return card

    def _create_quality_filters_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("inspectorCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        title = QLabel("2. Quality & Motion Filters")
        title.setObjectName("cardTitle")
        layout.addWidget(title)

        # Blur Filter Row with Analyze Button
        blur_row = QHBoxLayout()
        chk_blur = QCheckBox("Blur Rejection")
        chk_blur.setChecked(True)
        blur_row.addWidget(chk_blur)

        blur_row.addWidget(QLabel("Min:"))
        blur_spin = QDoubleSpinBox()
        blur_spin.setRange(0.0, 1000.0)
        blur_spin.setValue(100.0)
        blur_spin.setFixedWidth(70)
        blur_row.addWidget(blur_spin)

        btn_analyze = QPushButton("🔍 Analyze")
        btn_analyze.setObjectName("toolBtn")
        blur_row.addWidget(btn_analyze)
        layout.addLayout(blur_row)

        chk_smart_blur = QCheckBox("Smart Adaptive Blur (Auto Threshold)")
        chk_smart_blur.setChecked(True)
        layout.addWidget(chk_smart_blur)

        # Sharpening
        sharp_row = QHBoxLayout()
        chk_sharp = QCheckBox("Sharpening Recovery")
        sharp_row.addWidget(chk_sharp)
        sharp_slider = QSlider(Qt.Horizontal)
        sharp_slider.setRange(0, 100)
        sharp_slider.setValue(50)
        sharp_row.addWidget(sharp_slider)
        sharp_row.addWidget(QLabel("0.5"))
        layout.addLayout(sharp_row)

        # Adaptive Keyframing (Optical Flow)
        flow_row = QHBoxLayout()
        chk_flow = QCheckBox("Adaptive Motion (Optical Flow)")
        flow_row.addWidget(chk_flow)
        flow_spin = QDoubleSpinBox()
        flow_spin.setRange(0.1, 10.0)
        flow_spin.setValue(0.5)
        flow_spin.setFixedWidth(60)
        flow_row.addWidget(flow_spin)
        layout.addLayout(flow_row)

        return card

    def _create_ai_masking_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("inspectorCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        title = QLabel("3. AI Operator & Nadir Removal")
        title.setObjectName("cardTitle")
        layout.addWidget(title)

        grid = QGridLayout()
        grid.setSpacing(5)

        # AI Mode
        grid.addWidget(QLabel("Mode:"), 0, 0)
        ai_mode_cb = QComboBox()
        ai_mode_cb.addItems(["Generate Binary / Soft Mask", "Skip Entire Frame", "None (Disabled)"])
        grid.addWidget(ai_mode_cb, 0, 1)

        # Model
        grid.addWidget(QLabel("Model:"), 1, 0)
        model_cb = QComboBox()
        model_cb.addItems(["YOLO26-M Seg (High Precision)", "YOLO26-N Seg (Fast Nano)", "Custom Weights (.pt)"])
        grid.addWidget(model_cb, 1, 1)

        # Scope
        grid.addWidget(QLabel("Scope:"), 2, 0)
        scope_cb = QComboBox()
        scope_cb.addItems(["Down Face Only (Preserve Scene)", "All Cameras", "Custom Face Selection"])
        grid.addWidget(scope_cb, 2, 1)

        # Confidence
        grid.addWidget(QLabel("Confidence:"), 3, 0)
        conf_row = QHBoxLayout()
        conf_slider = QSlider(Qt.Horizontal)
        conf_slider.setRange(5, 95)
        conf_slider.setValue(25)
        conf_lbl = QLabel("25%")
        conf_slider.valueChanged.connect(lambda v: conf_lbl.setText(f"{v}%"))
        conf_row.addWidget(conf_slider)
        conf_row.addWidget(conf_lbl)
        grid.addLayout(conf_row, 3, 1)

        # Nadir Radius
        grid.addWidget(QLabel("Nadir Disc:"), 4, 0)
        rad_row = QHBoxLayout()
        rad_slider = QSlider(Qt.Horizontal)
        rad_slider.setRange(0, 100)
        rad_slider.setValue(int(self.nadir_radius))
        rad_lbl = QLabel(f"{int(self.nadir_radius)}%")
        rad_slider.valueChanged.connect(lambda v: (rad_lbl.setText(f"{v}%"), setattr(self, 'nadir_radius', float(v)), self._update_viewport_render()))
        rad_row.addWidget(rad_slider)
        rad_row.addWidget(rad_lbl)
        grid.addLayout(rad_row, 4, 1)

        layout.addLayout(grid)

        # Target classes
        class_row = QHBoxLayout()
        class_row.addWidget(QLabel("Targets:"))
        chk_human = QCheckBox("Humans")
        chk_human.setChecked(True)
        chk_veh = QCheckBox("Vehicles")
        chk_plant = QCheckBox("Plants")
        class_row.addWidget(chk_human)
        class_row.addWidget(chk_veh)
        class_row.addWidget(chk_plant)
        class_row.addStretch()
        layout.addLayout(class_row)

        # Custom class text
        cust_row = QHBoxLayout()
        cust_row.addWidget(QLabel("Custom:"))
        txt_cust = QLineEdit()
        txt_cust.setPlaceholderText("e.g. backpack, tripod, dog")
        cust_row.addWidget(txt_cust)
        layout.addLayout(cust_row)

        # Mask refinement toggles
        chk_soft = QCheckBox("Soft Alpha Mask (Native Softness for 3DGS)")
        chk_soft.setChecked(True)
        layout.addWidget(chk_soft)

        chk_inv = QCheckBox("Invert Mask (Photogrammetry: Black=Subject, White=BG)")
        chk_inv.setChecked(True)
        layout.addWidget(chk_inv)

        chk_sky = QCheckBox("Sky Mask (Outdoor Gaussian Floater Reduction)")
        layout.addWidget(chk_sky)

        return card

    def _create_export_calibration_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("inspectorCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        title = QLabel("4. Output, Calibration & Metadata")
        title.setObjectName("cardTitle")
        layout.addWidget(title)

        grid = QGridLayout()
        grid.setSpacing(5)

        # Format
        grid.addWidget(QLabel("Image Format:"), 0, 0)
        fmt_cb = QComboBox()
        fmt_cb.addItems(["JPG (Quality 95%)", "PNG (Lossless 8-bit)", "TIFF (16-bit)"])
        grid.addWidget(fmt_cb, 0, 1)

        # Interval
        grid.addWidget(QLabel("Interval:"), 1, 0)
        int_row = QHBoxLayout()
        int_spin = QDoubleSpinBox()
        int_spin.setRange(0.1, 100.0)
        int_spin.setValue(1.0)
        int_spin.setFixedWidth(60)
        int_unit = QComboBox()
        int_unit.addItems(["Seconds", "Frames"])
        int_row.addWidget(int_spin)
        int_row.addWidget(int_unit)
        grid.addLayout(int_row, 1, 1)

        # Naming Pattern
        grid.addWidget(QLabel("Naming Mode:"), 2, 0)
        name_cb = QComboBox()
        name_cb.addItems(["RealityScan Standard (.mask.png)", "Simple Sequential", "Custom Pattern"])
        grid.addWidget(name_cb, 2, 1)

        # Altitude Mode
        grid.addWidget(QLabel("GPS Altitude:"), 3, 0)
        alt_cb = QComboBox()
        alt_cb.addItems(["Absolute (ASL - Above Sea Level)", "Relative (AGL - Above Ground)"])
        grid.addWidget(alt_cb, 3, 1)

        layout.addLayout(grid)

        # Export Toggles
        chk_colmap = QCheckBox("Export COLMAP Rig (cameras.txt + rig_rotations.json)")
        chk_colmap.setChecked(True)
        layout.addWidget(chk_colmap)

        chk_transforms = QCheckBox("Export transforms.json (Postshot / Nerfstudio)")
        chk_transforms.setChecked(True)
        layout.addWidget(chk_transforms)

        chk_exif = QCheckBox("Embed Optical EXIF (FocalLength, Make/Model, GPS heading)")
        chk_exif.setChecked(True)
        layout.addWidget(chk_exif)

        return card

    def _create_hud_bar(self) -> QWidget:
        hud = QFrame()
        hud.setObjectName("hudBar")
        hud.setFixedHeight(54)
        layout = QHBoxLayout(hud)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(14)

        est_text = QLabel("1,440 pinhole images (240 frames × 6 views) • ~2.8 GB • Est. time: ~1m 15s")
        est_text.setStyleSheet("font-weight: 500; font-size: 11px;")
        layout.addWidget(est_text)

        layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("secondaryActionBtn")
        layout.addWidget(cancel_btn)

        extract_btn = QPushButton("Extract Dataset")
        extract_btn.setObjectName("primaryActionBtn")
        extract_btn.setCursor(Qt.PointingHandCursor)
        layout.addWidget(extract_btn)

        return hud


def pump(app: QApplication, ms: int) -> None:
    loop = QApplication.instance()
    timer = QTimer()
    timer.setSingleShot(True)
    timer.timeout.connect(loop.quit)
    timer.start(ms)
    loop.exec()


def render_and_save(window: StudioMockupWindow, app: QApplication, theme_key: str, out_path: Path):
    window._apply_theme(theme_key)
    pump(app, 400)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    window.grab().save(str(out_path))
    print(f"Saved: {out_path} ({out_path.stat().st_size / 1024:.0f} KB)")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("-o", "--output", default=str(REPO_ROOT / "docs" / "images" / "mockup-studio-gui.png"))
    parser.add_argument("--interactive", action="store_true", help="Launch interactive GUI window")
    parser.add_argument("--all-themes", action="store_true", help="Render screenshots for all 3 themes")
    args = parser.parse_args(argv)

    if not args.interactive:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    app = QApplication.instance() or QApplication(sys.argv)

    with tempfile.TemporaryDirectory() as tmp:
        demo = Path(tmp) / "demo_360_scene.jpg"
        make_demo_equirect(demo)

        window = StudioMockupWindow(demo)
        window.show()

        if args.interactive:
            print("Interactive 360 Extractor Studio is open with real-time Theme & Settings switcher.")
            return app.exec()

        if args.all_themes:
            render_and_save(window, app, "amber", REPO_ROOT / "docs" / "images" / "mockup-theme-a-amber.png")
            render_and_save(window, app, "titanium", REPO_ROOT / "docs" / "images" / "mockup-theme-b-titanium.png")
            render_and_save(window, app, "sage", REPO_ROOT / "docs" / "images" / "mockup-theme-c-sage.png")
            # Also write default output
            render_and_save(window, app, "amber", Path(args.output))
        else:
            render_and_save(window, app, "amber", Path(args.output))

    return 0


if __name__ == "__main__":
    sys.exit(main())
