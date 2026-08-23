#!/usr/bin/env python3
"""360 Extractor Studio - Interactive UI/UX Mockup & Screenshot Generator.

Demonstrates the redesigned 3-column studio layout:
1. Left: Media Queue with metadata chips (8K, GPS, IMU, badges)
2. Center: Interactive Viewport with Camera Face Selector (Front, Back, Left, Right, Up, Down),
          Live AI Mask & Nadir Overlay, and Timeline Scrubber.
3. Right: Inspector with 1-Click Workflow Presets (Postshot 3DGS, RealityScan, COLMAP) and
          grouped settings.
4. Bottom: Dynamic estimation HUD & glowing extraction CTA.

Usage:
    # Run interactively (GUI window):
    python scripts/mockup_studio_ui.py --interactive

    # Render screenshot to file (offscreen):
    python scripts/mockup_studio_ui.py -o docs/images/mockup-studio-gui.png
"""
from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import cv2  # noqa: E402
import numpy as np  # noqa: E402
from PySide6.QtCore import Qt, QTimer  # noqa: E402
from PySide6.QtGui import QImage, QPixmap  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QApplication, QCheckBox, QComboBox, QFrame,
    QGridLayout, QHBoxLayout, QLabel, QMainWindow,
    QPushButton, QScrollArea, QSlider,
    QSplitter, QVBoxLayout, QWidget
)

from extractor360.core.geometry import GeometryProcessor  # noqa: E402
from make_screenshot import make_demo_equirect  # noqa: E402


class StudioMockupWindow(QMainWindow):
    def __init__(self, demo_image_path: Path):
        super().__init__()
        self.setWindowTitle("360 Extractor Studio — [UI/UX Redesign Concept]")
        self.resize(1540, 960)
        self.demo_image_path = demo_image_path
        self.equirect_bgr = cv2.imread(str(demo_image_path))
        if self.equirect_bgr is None:
            self.equirect_bgr = make_demo_equirect(demo_image_path)

        self.current_face = "Down"  # Start on Down face to showcase Nadir + AI Masking
        self.fov = 90
        self.nadir_radius = 40.0
        self.show_ai_mask = True
        self.show_nadir_disc = True
        self.current_preset = "Postshot 3DGS"

        self._setup_stylesheet()
        self._build_ui()
        self._update_viewport_render()

    def _setup_stylesheet(self):
        self.setStyleSheet("""
            QMainWindow {
                background-color: #09090B;
                color: #FAFAFA;
            }
            QWidget {
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
                font-size: 12px;
                color: #A1A1AA;
            }
            QFrame#topNav {
                background-color: #0F0F12;
                border-bottom: 1px solid #1E1E24;
                padding: 4px 16px;
            }
            QFrame#leftSidebar {
                background-color: #0D0D10;
                border-right: 1px solid #1A1A20;
            }
            QFrame#centerArea {
                background-color: #070709;
            }
            QFrame#rightInspector {
                background-color: #0D0D10;
                border-left: 1px solid #1A1A20;
            }
            QFrame#viewportContainer {
                background-color: #000000;
                border: 1px solid #24242C;
                border-radius: 12px;
            }
            QFrame#hudBar {
                background-color: #121216;
                border-top: 1px solid #22222A;
                border-radius: 0px;
                padding: 8px 16px;
            }
            QFrame#inspectorCard {
                background-color: #131317;
                border: 1px solid #202028;
                border-radius: 10px;
                padding: 10px;
            }
            QLabel#sectionHeader {
                color: #F4F4F5;
                font-weight: 700;
                font-size: 12px;
                letter-spacing: 0.5px;
            }
            QLabel#cardTitle {
                color: #FAFAFA;
                font-weight: 600;
                font-size: 12px;
            }
            QPushButton#presetPill {
                background-color: #1A1A22;
                border: 1px solid #2D2D38;
                border-radius: 14px;
                color: #D4D4D8;
                padding: 5px 14px;
                font-weight: 600;
                font-size: 11px;
            }
            QPushButton#presetPill:hover {
                background-color: #262633;
                border-color: #3B82F6;
                color: #FFFFFF;
            }
            QPushButton#presetPill[active="true"] {
                background-color: rgba(59, 130, 246, 0.2);
                border: 1px solid #3B82F6;
                color: #60A5FA;
            }
            QPushButton#camFaceBtn {
                background-color: #16161C;
                border: 1px solid #272732;
                border-radius: 6px;
                color: #A1A1AA;
                padding: 6px 12px;
                font-weight: 600;
                font-size: 11px;
            }
            QPushButton#camFaceBtn:hover {
                background-color: #22222C;
                color: #FFFFFF;
            }
            QPushButton#camFaceBtn[active="true"] {
                background-color: #3B82F6;
                border-color: #60A5FA;
                color: #FFFFFF;
            }
            QPushButton#ctaBtn {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #3B82F6, stop:1 #2563EB);
                color: #FFFFFF;
                font-weight: 700;
                font-size: 13px;
                border-radius: 8px;
                padding: 10px 24px;
                border: 1px solid rgba(255, 255, 255, 0.2);
            }
            QPushButton#ctaBtn:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #60A5FA, stop:1 #3B82F6);
            }
            QComboBox, QSpinBox, QDoubleSpinBox, QLineEdit {
                background-color: #18181E;
                border: 1px solid #282834;
                border-radius: 6px;
                padding: 5px 8px;
                color: #FAFAFA;
                font-size: 11px;
            }
            QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus, QLineEdit:focus {
                border-color: #3B82F6;
            }
            QSlider::groove:horizontal {
                height: 4px;
                background: #272732;
                border-radius: 2px;
            }
            QSlider::sub-page:horizontal {
                background: #3B82F6;
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background: #FAFAFA;
                border: 2px solid #3B82F6;
                width: 14px;
                margin-top: -5px;
                margin-bottom: -5px;
                border-radius: 7px;
            }
            QCheckBox {
                color: #D4D4D8;
                spacing: 6px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border-radius: 4px;
                border: 1px solid #363645;
                background-color: #16161C;
            }
            QCheckBox::indicator:checked {
                background-color: #3B82F6;
                border-color: #60A5FA;
            }
            QScrollBar:vertical {
                border: none;
                background: transparent;
                width: 6px;
            }
            QScrollBar::handle:vertical {
                background: #272732;
                border-radius: 3px;
            }
        """)

    def _build_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        root_layout = QVBoxLayout(main_widget)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # 1. Top Navbar with Brand & Workflow Presets
        top_nav = self._create_top_nav()
        root_layout.addWidget(top_nav)

        # 2. Main 3-Column Splitter
        content_splitter = QSplitter(Qt.Horizontal)
        content_splitter.setHandleWidth(1)
        content_splitter.setStyleSheet("QSplitter::handle { background: #1C1C24; }")

        # Left Column: Media & Job Queue (280px)
        left_col = self._create_left_queue()
        content_splitter.addWidget(left_col)

        # Center Column: Viewport & Timeline (Flex)
        center_col = self._create_center_viewport()
        content_splitter.addWidget(center_col)

        # Right Column: Unified Inspector & Settings (360px)
        right_col = self._create_right_inspector()
        content_splitter.addWidget(right_col)

        content_splitter.setStretchFactor(0, 0)  # Left fixed
        content_splitter.setStretchFactor(1, 1)  # Center flexible
        content_splitter.setStretchFactor(2, 0)  # Right fixed
        root_layout.addWidget(content_splitter, 1)

        # 3. Bottom HUD Action Bar
        hud_bar = self._create_hud_bar()
        root_layout.addWidget(hud_bar)

    def _create_top_nav(self) -> QWidget:
        nav = QFrame()
        nav.setObjectName("topNav")
        nav.setFixedHeight(54)
        layout = QHBoxLayout(nav)
        layout.setContentsMargins(18, 0, 18, 0)
        layout.setSpacing(16)

        # Brand Logo & Title
        logo_layout = QHBoxLayout()
        logo_layout.setSpacing(8)
        brand_icon = QLabel("🌐")
        brand_icon.setStyleSheet("font-size: 20px;")
        logo_layout.addWidget(brand_icon)

        title_label = QLabel("360 Extractor Studio")
        title_label.setStyleSheet("color: #FFFFFF; font-weight: 700; font-size: 15px; letter-spacing: -0.3px;")
        logo_layout.addWidget(title_label)

        version_badge = QLabel("v4.0 Pro")
        version_badge.setStyleSheet("""
            background-color: rgba(59, 130, 246, 0.15);
            color: #60A5FA;
            border: 1px solid rgba(59, 130, 246, 0.4);
            border-radius: 4px;
            padding: 2px 6px;
            font-size: 10px;
            font-weight: 700;
        """)
        logo_layout.addWidget(version_badge)
        layout.addLayout(logo_layout)

        layout.addSpacing(24)

        # Workflow Presets Section
        preset_label = QLabel("WORKFLOW PRESET:")
        preset_label.setStyleSheet("color: #71717A; font-weight: 700; font-size: 10px; letter-spacing: 1px;")
        layout.addWidget(preset_label)

        self.preset_buttons = {}
        presets = ["Postshot 3DGS", "RealityScan", "COLMAP Precision", "Drone / Pan"]
        for p in presets:
            btn = QPushButton(p)
            btn.setObjectName("presetPill")
            btn.setCursor(Qt.PointingHandCursor)
            if p == self.current_preset:
                btn.setProperty("active", True)
            btn.clicked.connect(lambda _, name=p: self._select_preset(name))
            self.preset_buttons[p] = btn
            layout.addWidget(btn)

        layout.addStretch()

        # Hardware & Acceleration Status Badge
        accel_badge = QFrame()
        accel_badge.setStyleSheet("""
            background-color: #14141A;
            border: 1px solid #23232C;
            border-radius: 6px;
            padding: 4px 10px;
        """)
        accel_layout = QHBoxLayout(accel_badge)
        accel_layout.setContentsMargins(6, 2, 6, 2)
        accel_layout.setSpacing(6)

        dot = QLabel("●")
        dot.setStyleSheet("color: #10B981; font-size: 12px;")
        accel_layout.addWidget(dot)

        accel_txt = QLabel("Apple Silicon Metal (MPS) • Fast GPU")
        accel_txt.setStyleSheet("color: #E4E4E7; font-size: 11px; font-weight: 500;")
        accel_layout.addWidget(accel_txt)

        layout.addWidget(accel_badge)
        return nav

    def _select_preset(self, preset_name: str):
        self.current_preset = preset_name
        for name, btn in self.preset_buttons.items():
            btn.setProperty("active", (name == preset_name))
            btn.setStyle(btn.style())

    def _create_left_queue(self) -> QWidget:
        col = QFrame()
        col.setObjectName("leftSidebar")
        col.setFixedWidth(280)
        layout = QVBoxLayout(col)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)

        # Header with Add Button
        hdr_layout = QHBoxLayout()
        hdr_title = QLabel("MEDIA QUEUE")
        hdr_title.setObjectName("sectionHeader")
        hdr_layout.addWidget(hdr_title)

        count_badge = QLabel("3 items")
        count_badge.setStyleSheet("color: #71717A; font-size: 11px; font-weight: 600;")
        hdr_layout.addWidget(count_badge)
        hdr_layout.addStretch()

        add_btn = QPushButton("+ Add")
        add_btn.setStyleSheet("""
            background-color: #1E1E28;
            border: 1px solid #2E2E3C;
            border-radius: 6px;
            color: #FAFAFA;
            padding: 4px 10px;
            font-weight: 600;
            font-size: 11px;
        """)
        hdr_layout.addWidget(add_btn)
        layout.addLayout(hdr_layout)

        # Smart Drop Zone Card
        drop_card = QFrame()
        drop_card.setStyleSheet("""
            background-color: rgba(255, 255, 255, 0.02);
            border: 2px dashed #272733;
            border-radius: 10px;
            padding: 14px 10px;
        """)
        drop_layout = QVBoxLayout(drop_card)
        drop_layout.setAlignment(Qt.AlignCenter)
        drop_layout.setSpacing(4)

        icon_lbl = QLabel("📂")
        icon_lbl.setStyleSheet("font-size: 20px;")
        icon_lbl.setAlignment(Qt.AlignCenter)
        drop_layout.addWidget(icon_lbl)

        txt_lbl = QLabel("Drop 360° Videos or Folders")
        txt_lbl.setStyleSheet("color: #D4D4D8; font-weight: 600; font-size: 11px;")
        txt_lbl.setAlignment(Qt.AlignCenter)
        drop_layout.addWidget(txt_lbl)

        sub_lbl = QLabel("Supports GoPro, Insta360, Kandao, DJI")
        sub_lbl.setStyleSheet("color: #71717A; font-size: 10px;")
        sub_lbl.setAlignment(Qt.AlignCenter)
        drop_layout.addWidget(sub_lbl)
        layout.addWidget(drop_card)

        # Scrollable Queue Cards
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        cards_container = QWidget()
        cards_layout = QVBoxLayout(cards_container)
        cards_layout.setContentsMargins(0, 0, 0, 0)
        cards_layout.setSpacing(8)

        # Mock Queue Items
        items_data = [
            ("GS_PARK_WALK_8K.mp4", "Active", "01:45 • 8K Equirect", ["8K 360", "GPS 18Hz", "IMU Level"], True),
            ("GOPRO_MAX_INTERIOR.mp4", "Ready", "03:12 • 5.6K Equirect", ["5.6K 360", "GPMF Telemetry"], False),
            ("DRONE_ROOF_SURVEY.mp4", "Done", "00:58 • 4K Flat", ["4K Flat", "SRT Telemetry"], False),
        ]

        for name, status, details, tags, selected in items_data:
            card = self._create_queue_card(name, status, details, tags, selected)
            cards_layout.addWidget(card)

        cards_layout.addStretch()
        scroll.setWidget(cards_container)
        layout.addWidget(scroll, 1)

        return col

    def _create_queue_card(self, name: str, status: str, details: str, tags: list[str], selected: bool) -> QWidget:
        card = QFrame()
        card_border = "#3B82F6" if selected else "#22222C"
        card_bg = "rgba(59, 130, 246, 0.08)" if selected else "#121217"

        card.setStyleSheet(f"""
            QFrame {{
                background-color: {card_bg};
                border: 1px solid {card_border};
                border-radius: 8px;
                padding: 10px;
            }}
            QFrame:hover {{
                border-color: #3B82F6;
                background-color: rgba(59, 130, 246, 0.05);
            }}
        """)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # Title & Status
        hdr = QHBoxLayout()
        title = QLabel(name)
        title.setStyleSheet("color: #FFFFFF; font-weight: 600; font-size: 11px;")
        hdr.addWidget(title)
        hdr.addStretch()

        status_colors = {"Active": "#3B82F6", "Ready": "#10B981", "Done": "#6B7280"}
        st_lbl = QLabel(status)
        st_lbl.setStyleSheet(f"color: {status_colors.get(status, '#FFF')}; font-weight: 700; font-size: 10px;")
        hdr.addWidget(st_lbl)
        layout.addLayout(hdr)

        det = QLabel(details)
        det.setStyleSheet("color: #888894; font-size: 10px;")
        layout.addWidget(det)

        # Tag chips
        tags_layout = QHBoxLayout()
        tags_layout.setSpacing(4)
        for t in tags:
            tag_chip = QLabel(t)
            tag_chip.setStyleSheet("""
                background-color: #1A1A22;
                color: #A1A1AA;
                border-radius: 3px;
                padding: 1px 5px;
                font-size: 9px;
                font-weight: 600;
            """)
            tags_layout.addWidget(tag_chip)
        tags_layout.addStretch()
        layout.addLayout(tags_layout)

        return card

    def _create_center_viewport(self) -> QWidget:
        col = QFrame()
        col.setObjectName("centerArea")
        layout = QVBoxLayout(col)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        # 1. Viewport Toolbar (Face Selector & Overlay Toggles)
        toolbar = QFrame()
        toolbar.setStyleSheet("""
            background-color: #111116;
            border: 1px solid #1F1F28;
            border-radius: 8px;
            padding: 4px 10px;
        """)
        tb_layout = QHBoxLayout(toolbar)
        tb_layout.setContentsMargins(6, 4, 6, 4)
        tb_layout.setSpacing(8)

        view_label = QLabel("PINHOLE VIEW:")
        view_label.setStyleSheet("color: #71717A; font-weight: 700; font-size: 10px; letter-spacing: 0.8px;")
        tb_layout.addWidget(view_label)

        self.cam_buttons = {}
        faces = [("Front", "0°"), ("Right", "90°"), ("Back", "180°"), ("Left", "270°"), ("Up", "+90°"), ("Down", "-90° (Nadir)")]
        for face_name, angle in faces:
            btn = QPushButton(f"{face_name} {angle}")
            btn.setObjectName("camFaceBtn")
            btn.setCursor(Qt.PointingHandCursor)
            if face_name == self.current_face:
                btn.setProperty("active", True)
            btn.clicked.connect(lambda _, name=face_name: self._select_cam_face(name))
            self.cam_buttons[face_name] = btn
            tb_layout.addWidget(btn)

        tb_layout.addSpacing(16)

        # Overlay Controls
        self.chk_ai_mask = QCheckBox("AI Mask (Red Alpha)")
        self.chk_ai_mask.setChecked(self.show_ai_mask)
        self.chk_ai_mask.stateChanged.connect(self._toggle_ai_mask)
        tb_layout.addWidget(self.chk_ai_mask)

        self.chk_nadir = QCheckBox("Nadir Disc")
        self.chk_nadir.setChecked(self.show_nadir_disc)
        self.chk_nadir.stateChanged.connect(self._toggle_nadir)
        tb_layout.addWidget(self.chk_nadir)

        tb_layout.addStretch()

        # View Mode Toggle (Perspective vs Split vs Mosaic)
        mosaic_btn = QPushButton("⊞ 6-View Mosaic")
        mosaic_btn.setObjectName("camFaceBtn")
        mosaic_btn.setCursor(Qt.PointingHandCursor)
        tb_layout.addWidget(mosaic_btn)

        layout.addWidget(toolbar)

        # 2. Main High-Resolution Perspective Viewport
        self.viewport_frame = QFrame()
        self.viewport_frame.setObjectName("viewportContainer")
        viewport_layout = QVBoxLayout(self.viewport_frame)
        viewport_layout.setContentsMargins(0, 0, 0, 0)

        self.preview_image_label = QLabel()
        self.preview_image_label.setAlignment(Qt.AlignCenter)
        self.preview_image_label.setStyleSheet("background-color: transparent;")
        viewport_layout.addWidget(self.preview_image_label)

        layout.addWidget(self.viewport_frame, 1)

        # 3. Video Timeline Scrubber & Frame Bar
        timeline_bar = QFrame()
        timeline_bar.setStyleSheet("""
            background-color: #111116;
            border: 1px solid #1F1F28;
            border-radius: 8px;
            padding: 6px 12px;
        """)
        tl_layout = QHBoxLayout(timeline_bar)
        tl_layout.setContentsMargins(8, 4, 8, 4)
        tl_layout.setSpacing(12)

        play_btn = QPushButton("▶")
        play_btn.setFixedSize(28, 28)
        play_btn.setStyleSheet("""
            background-color: #242432;
            border: 1px solid #363648;
            border-radius: 14px;
            color: #FAFAFA;
            font-weight: bold;
        """)
        tl_layout.addWidget(play_btn)

        timecode = QLabel("00:14.20 / 01:45.00")
        timecode.setStyleSheet("color: #D4D4D8; font-family: monospace; font-size: 11px; font-weight: 600;")
        tl_layout.addWidget(timecode)

        frame_lbl = QLabel("[Frame #00426]")
        frame_lbl.setStyleSheet("color: #60A5FA; font-family: monospace; font-size: 11px;")
        tl_layout.addWidget(frame_lbl)

        # Slider
        scrubber = QSlider(Qt.Horizontal)
        scrubber.setRange(0, 100)
        scrubber.setValue(14)
        tl_layout.addWidget(scrubber, 1)

        sharp_badge = QLabel("✨ Sharpest Keyframe")
        sharp_badge.setStyleSheet("""
            background-color: rgba(16, 185, 129, 0.15);
            color: #10B981;
            border: 1px solid rgba(16, 185, 129, 0.4);
            border-radius: 4px;
            padding: 2px 6px;
            font-size: 10px;
            font-weight: 600;
        """)
        tl_layout.addWidget(sharp_badge)

        layout.addWidget(timeline_bar)
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
        """Render the perspective camera face with Nadir Disc and AI Mask overlays."""
        src_h, src_w = self.equirect_bgr.shape[:2]
        dest_res = 800

        # Angles for selected face
        angles = {
            "Front": (0.0, 0.0, 0.0),
            "Right": (90.0, 0.0, 0.0),
            "Back": (180.0, 0.0, 0.0),
            "Left": (270.0, 0.0, 0.0),
            "Up": (0.0, 90.0, 0.0),
            "Down": (0.0, -90.0, 0.0),
        }
        yaw, pitch, roll = angles.get(self.current_face, (0.0, 0.0, 0.0))

        # Reproject
        map_x, map_y = GeometryProcessor.create_rectilinear_map(
            src_h, src_w, dest_res, dest_res, self.fov, yaw, pitch, roll
        )
        rect_img = cv2.remap(self.equirect_bgr, map_x, map_y, cv2.INTER_LINEAR)

        # If on Down face, add Nadir Disc and Operator AI Mask Overlay
        if self.current_face == "Down":
            overlay = rect_img.copy()
            center_x, center_y = dest_res // 2, dest_res // 2

            # 1. Nadir Disc (Black circle for tripod / selfie stick)
            if self.show_nadir_disc:
                radius_px = int((self.nadir_radius / 100.0) * (dest_res / 2.0))
                cv2.circle(overlay, (center_x, center_y), radius_px, (15, 15, 20), -1)
                cv2.circle(overlay, (center_x, center_y), radius_px, (59, 130, 246), 2)

            # 2. AI Operator Mask (Red translucent overlay representing YOLO mask)
            if self.show_ai_mask:
                # Synthetic operator silhouette on Down face
                op_x1, op_y1 = center_x - 120, center_y + 40
                op_x2, op_y2 = center_x + 120, dest_res - 20
                cv2.ellipse(overlay, ((op_x1 + op_x2) // 2, (op_y1 + op_y2) // 2), (130, 180), 0, 0, 360, (0, 0, 220), -1)

            # Blend with 45% transparency
            cv2.addWeighted(overlay, 0.45, rect_img, 0.55, 0, rect_img)

            # On-screen HUD badges
            font = cv2.FONT_HERSHEY_SIMPLEX
            if self.show_nadir_disc:
                cv2.putText(rect_img, f"NADIR DISC: {int(self.nadir_radius)}%", (center_x - 65, center_y - 10), font, 0.45, (255, 255, 255), 1, cv2.LINE_AA)
            if self.show_ai_mask:
                cv2.putText(rect_img, "AI MASK: PERSON (98.4% CONF)", (center_x - 110, dest_res - 40), font, 0.5, (0, 180, 255), 2, cv2.LINE_AA)

        # Corner View Indicator
        cv2.putText(rect_img, f"CAMERA: {self.current_face.upper()} (FOV {self.fov}deg)", (20, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2, cv2.LINE_AA)
        cv2.putText(rect_img, "EXACT PINHOLE INTRINSICS CALIBRATED", (20, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (59, 130, 246), 1, cv2.LINE_AA)

        # Convert to QPixmap
        rgb = cv2.cvtColor(rect_img, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        qimg = QImage(rgb.data, w, h, ch * w, QImage.Format_RGB888)
        pix = QPixmap.fromImage(qimg).scaled(780, 620, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.preview_image_label.setPixmap(pix)

    def _create_right_inspector(self) -> QWidget:
        col = QFrame()
        col.setObjectName("rightInspector")
        col.setFixedWidth(360)
        layout = QVBoxLayout(col)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)

        # Header
        hdr = QLabel("INSPECTOR & SETTINGS")
        hdr.setObjectName("sectionHeader")
        layout.addWidget(hdr)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        container = QWidget()
        c_layout = QVBoxLayout(container)
        c_layout.setContentsMargins(0, 0, 4, 0)
        c_layout.setSpacing(10)

        # Card 1: Optics & Geometry
        c_layout.addWidget(self._create_optics_card())

        # Card 2: AI Operator Removal & Nadir Masking
        c_layout.addWidget(self._create_ai_card())

        # Card 3: Export & Calibration Formats
        c_layout.addWidget(self._create_export_card())

        c_layout.addStretch()
        scroll.setWidget(container)
        layout.addWidget(scroll, 1)
        return col

    def _create_optics_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("inspectorCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        title = QLabel("1. Optics & Geometry")
        title.setObjectName("cardTitle")
        layout.addWidget(title)

        grid = QGridLayout()
        grid.setSpacing(8)

        # Layout Mode
        grid.addWidget(QLabel("Layout Mode:"), 0, 0)
        layout_cb = QComboBox()
        layout_cb.addItems(["Cube Map (6 Views - Recommended)", "Ring (Horizon 360°)", "Fibonacci Sphere (Dense)"])
        grid.addWidget(layout_cb, 0, 1)

        # Resolution
        grid.addWidget(QLabel("Resolution:"), 1, 0)
        res_cb = QComboBox()
        res_cb.addItems(["2048 x 2048 (Optimized)", "3072 x 3072", "4096 x 4096 (Ultra 8K)"])
        grid.addWidget(res_cb, 1, 1)

        # FOV Slider
        grid.addWidget(QLabel("FOV (Degrees):"), 2, 0)
        fov_layout = QHBoxLayout()
        fov_slider = QSlider(Qt.Horizontal)
        fov_slider.setRange(60, 120)
        fov_slider.setValue(90)
        fov_lbl = QLabel("90°")
        fov_slider.valueChanged.connect(lambda v: (fov_lbl.setText(f"{v}°"), setattr(self, 'fov', v), self._update_viewport_render()))
        fov_layout.addWidget(fov_slider)
        fov_layout.addWidget(fov_lbl)
        grid.addLayout(fov_layout, 2, 1)

        layout.addLayout(grid)

        # Auto-Horizon Leveling IMU Toggle
        imu_chk = QCheckBox("Auto-Horizon Leveling (IMU Gyro Fusion)")
        imu_chk.setChecked(True)
        imu_chk.setStyleSheet("color: #60A5FA; font-weight: 600;")
        layout.addWidget(imu_chk)

        return card

    def _create_ai_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("inspectorCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        title = QLabel("2. AI Operator & Nadir Removal")
        title.setObjectName("cardTitle")
        layout.addWidget(title)

        grid = QGridLayout()
        grid.setSpacing(8)

        # AI Model
        grid.addWidget(QLabel("AI Model:"), 0, 0)
        model_cb = QComboBox()
        model_cb.addItems(["YOLO26-M Seg (High Precision)", "YOLO26-N Seg (Fast Nano)", "Custom Weights (.pt)"])
        grid.addWidget(model_cb, 0, 1)

        # Scope
        grid.addWidget(QLabel("Mask Scope:"), 1, 0)
        scope_cb = QComboBox()
        scope_cb.addItems(["Down Face Only (Preserve Scene)", "All Cameras", "Custom Faces"])
        grid.addWidget(scope_cb, 1, 1)

        # Nadir Radius Slider
        grid.addWidget(QLabel("Nadir Radius:"), 2, 0)
        rad_layout = QHBoxLayout()
        rad_slider = QSlider(Qt.Horizontal)
        rad_slider.setRange(0, 100)
        rad_slider.setValue(int(self.nadir_radius))
        rad_lbl = QLabel(f"{int(self.nadir_radius)}%")
        rad_slider.valueChanged.connect(lambda v: (rad_lbl.setText(f"{v}%"), setattr(self, 'nadir_radius', float(v)), self._update_viewport_render()))
        rad_layout.addWidget(rad_slider)
        rad_layout.addWidget(rad_lbl)
        grid.addLayout(rad_layout, 2, 1)

        layout.addLayout(grid)

        # Checkboxes
        chk_soft = QCheckBox("Native Soft Mask (Alpha Blending for 3DGS)")
        chk_soft.setChecked(True)
        layout.addWidget(chk_soft)

        chk_sky = QCheckBox("Sky Mask (Outdoor Floater Reduction)")
        layout.addWidget(chk_sky)

        return card

    def _create_export_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("inspectorCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        title = QLabel("3. Calibration & Export Formats")
        title.setObjectName("cardTitle")
        layout.addWidget(title)

        grid = QGridLayout()
        grid.setSpacing(8)

        grid.addWidget(QLabel("Image Format:"), 0, 0)
        fmt_cb = QComboBox()
        fmt_cb.addItems(["JPG (Quality 95%)", "PNG (Lossless)", "TIFF (16-bit float)"])
        grid.addWidget(fmt_cb, 0, 1)

        grid.addWidget(QLabel("Interval:"), 1, 0)
        int_cb = QComboBox()
        int_cb.addItems(["Every 1.0 Second", "Every 0.5 Second (Dense)", "Adaptive Keyframing (Flow)"])
        grid.addWidget(int_cb, 1, 1)

        layout.addLayout(grid)

        # Calibration Toggles
        chk_colmap = QCheckBox("Generate COLMAP Priors (cameras.txt + rig_rotations.json)")
        chk_colmap.setChecked(True)
        chk_colmap.setStyleSheet("color: #A78BFA; font-weight: 600;")
        layout.addWidget(chk_colmap)

        chk_transforms = QCheckBox("Generate Nerfstudio / Postshot (transforms.json)")
        chk_transforms.setChecked(True)
        chk_transforms.setStyleSheet("color: #34D399; font-weight: 600;")
        layout.addWidget(chk_transforms)

        chk_exif = QCheckBox("Embed Optical EXIF (Focal, Make/Model, GPS direction)")
        chk_exif.setChecked(True)
        layout.addWidget(chk_exif)

        return card

    def _create_hud_bar(self) -> QWidget:
        hud = QFrame()
        hud.setObjectName("hudBar")
        hud.setFixedHeight(68)
        layout = QHBoxLayout(hud)
        layout.setContentsMargins(20, 0, 20, 0)
        layout.setSpacing(16)

        # Stats Chip
        stat_chip = QFrame()
        stat_chip.setStyleSheet("""
            background-color: #1A1A24;
            border: 1px solid #2B2B3A;
            border-radius: 8px;
            padding: 6px 14px;
        """)
        chip_layout = QHBoxLayout(stat_chip)
        chip_layout.setContentsMargins(8, 4, 8, 4)
        chip_layout.setSpacing(12)

        est_icon = QLabel("📊")
        est_icon.setStyleSheet("font-size: 16px;")
        chip_layout.addWidget(est_icon)

        est_text = QLabel("ESTIMATED: 1,440 images (240 frames × 6 views) • ~2.8 GB • ETA: ~1m 15s")
        est_text.setStyleSheet("color: #FAFAFA; font-weight: 600; font-size: 12px;")
        chip_layout.addWidget(est_text)

        layout.addWidget(stat_chip)

        # Output Folder
        out_lbl = QLabel("Output: /Volumes/Workspace/360_Dataset_Out")
        out_lbl.setStyleSheet("color: #71717A; font-family: monospace; font-size: 11px;")
        layout.addWidget(out_lbl)

        layout.addStretch()

        # CTA Buttons
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet("""
            background-color: #1E1E28;
            border: 1px solid #323242;
            border-radius: 8px;
            color: #D4D4D8;
            padding: 10px 18px;
            font-weight: 600;
        """)
        layout.addWidget(cancel_btn)

        extract_btn = QPushButton("🚀 Start Dataset Extraction")
        extract_btn.setObjectName("ctaBtn")
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "-o", "--output",
        default=str(REPO_ROOT / "docs" / "images" / "mockup-studio-gui.png"),
        help="Where to write the mockup PNG",
    )
    parser.add_argument("--interactive", action="store_true", help="Launch interactive GUI window")
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
            print("Running interactive 360 Extractor Studio mockup...")
            return app.exec()

        pump(app, 1500)

        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if not window.grab().save(str(output_path)):
            print(f"error: could not write {output_path}", file=sys.stderr)
            return 1

        print(f"Wrote studio mockup screenshot: {output_path} ({output_path.stat().st_size / 1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
