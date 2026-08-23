#!/usr/bin/env python3
"""360 Extractor - Refined Minimalist Pro UI/UX Mockup.

Professional, clean, subdued desktop aesthetic (inspired by macOS Pro tools, Lightroom, Linear).
- Calm neutral dark palette (#121214, #1A1A1E, #26262B) without neon/AI clichés.
- High typographic clarity, breathing room, no visual clutter or emojis.
- Clean segmented controls, elegant viewport, minimal timeline, refined inspector.

Usage:
    python scripts/mockup_studio_ui.py -o docs/images/mockup-studio-gui.png
    python scripts/mockup_studio_ui.py --interactive
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
        self.setWindowTitle("360 Extractor")
        self.resize(1480, 920)
        self.demo_image_path = demo_image_path
        self.equirect_bgr = cv2.imread(str(demo_image_path))
        if self.equirect_bgr is None:
            self.equirect_bgr = make_demo_equirect(demo_image_path)

        self.current_face = "Down"
        self.fov = 90
        self.nadir_radius = 35.0
        self.show_ai_mask = True
        self.show_nadir_disc = True
        self.current_preset = "Postshot (Gaussian Splatting)"

        self._setup_stylesheet()
        self._build_ui()
        self._update_viewport_render()

    def _setup_stylesheet(self):
        self.setStyleSheet("""
            QMainWindow {
                background-color: #111113;
                color: #EDEDED;
            }
            QWidget {
                font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI", Roboto, sans-serif;
                font-size: 12px;
                color: #8E8E93;
            }
            QFrame#topNav {
                background-color: #161619;
                border-bottom: 1px solid #232328;
                padding: 0px 16px;
            }
            QFrame#leftSidebar {
                background-color: #141417;
                border-right: 1px solid #222227;
            }
            QFrame#centerArea {
                background-color: #0E0E10;
            }
            QFrame#rightInspector {
                background-color: #141417;
                border-left: 1px solid #222227;
            }
            QFrame#viewportContainer {
                background-color: #000000;
                border: 1px solid #222228;
                border-radius: 8px;
            }
            QFrame#hudBar {
                background-color: #161619;
                border-top: 1px solid #232328;
                padding: 8px 20px;
            }
            QFrame#inspectorCard {
                background-color: #18181C;
                border: 1px solid #24242A;
                border-radius: 8px;
                padding: 12px;
            }
            QLabel#sectionHeader {
                color: #A1A1A6;
                font-weight: 600;
                font-size: 11px;
                text-transform: uppercase;
                letter-spacing: 0.8px;
            }
            QLabel#cardTitle {
                color: #FAFAFA;
                font-weight: 600;
                font-size: 12px;
            }
            /* Segmented Control Buttons */
            QPushButton#segmentBtn {
                background-color: transparent;
                border: none;
                border-radius: 5px;
                color: #8E8E93;
                padding: 5px 12px;
                font-weight: 500;
                font-size: 11px;
            }
            QPushButton#segmentBtn:hover {
                color: #FFFFFF;
                background-color: #222228;
            }
            QPushButton#segmentBtn[active="true"] {
                background-color: #2C2C34;
                color: #FFFFFF;
                font-weight: 600;
            }
            /* Primary Pro Action Button */
            QPushButton#primaryActionBtn {
                background-color: #0A84FF;
                color: #FFFFFF;
                font-weight: 600;
                font-size: 12px;
                border-radius: 6px;
                padding: 8px 18px;
                border: none;
            }
            QPushButton#primaryActionBtn:hover {
                background-color: #0071E3;
            }
            QPushButton#primaryActionBtn:pressed {
                background-color: #0058B0;
            }
            QPushButton#secondaryActionBtn {
                background-color: transparent;
                border: 1px solid #2C2C34;
                border-radius: 6px;
                color: #C7C7CC;
                padding: 7px 16px;
                font-weight: 500;
                font-size: 12px;
            }
            QPushButton#secondaryActionBtn:hover {
                background-color: #202026;
                color: #FFFFFF;
            }
            QComboBox, QSpinBox, QDoubleSpinBox, QLineEdit {
                background-color: #1B1B20;
                border: 1px solid #292932;
                border-radius: 5px;
                padding: 5px 8px;
                color: #FAFAFA;
                font-size: 11px;
            }
            QComboBox:focus, QSpinBox:focus, QLineEdit:focus {
                border-color: #0A84FF;
            }
            QSlider::groove:horizontal {
                height: 3px;
                background: #2A2A33;
                border-radius: 1.5px;
            }
            QSlider::sub-page:horizontal {
                background: #0A84FF;
                border-radius: 1.5px;
            }
            QSlider::handle:horizontal {
                background: #FFFFFF;
                border: 1px solid #0A84FF;
                width: 12px;
                margin-top: -4.5px;
                margin-bottom: -4.5px;
                border-radius: 6px;
            }
            QCheckBox {
                color: #D1D1D6;
                spacing: 6px;
                font-size: 11px;
            }
            QCheckBox::indicator {
                width: 14px;
                height: 14px;
                border-radius: 3px;
                border: 1px solid #3A3A46;
                background-color: #19191E;
            }
            QCheckBox::indicator:checked {
                background-color: #0A84FF;
                border-color: #0A84FF;
            }
            QScrollBar:vertical {
                border: none;
                background: transparent;
                width: 5px;
            }
            QScrollBar::handle:vertical {
                background: #2C2C35;
                border-radius: 2.5px;
            }
        """)

    def _build_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        root_layout = QVBoxLayout(main_widget)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # 1. Top Navbar (Clean Pro Branding & Workflow Selector)
        top_nav = self._create_top_nav()
        root_layout.addWidget(top_nav)

        # 2. Main 3-Column Splitter
        content_splitter = QSplitter(Qt.Horizontal)
        content_splitter.setHandleWidth(1)
        content_splitter.setStyleSheet("QSplitter::handle { background: #1C1C22; }")

        # Left Column: Media Queue (260px)
        left_col = self._create_left_queue()
        content_splitter.addWidget(left_col)

        # Center Column: Viewport & Scrubber (Flex)
        center_col = self._create_center_viewport()
        content_splitter.addWidget(center_col)

        # Right Column: Inspector (340px)
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
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(16)

        # Title
        title_label = QLabel("360 Extractor")
        title_label.setStyleSheet("color: #FFFFFF; font-weight: 600; font-size: 13px; letter-spacing: -0.2px;")
        layout.addWidget(title_label)

        v_sep = QFrame()
        v_sep.setFrameShape(QFrame.VLine)
        v_sep.setStyleSheet("color: #24242A;")
        v_sep.setFixedHeight(18)
        layout.addWidget(v_sep)

        # Workflow Target Selector
        wf_lbl = QLabel("Target Pipeline:")
        wf_lbl.setStyleSheet("color: #71717A; font-size: 11px;")
        layout.addWidget(wf_lbl)

        self.preset_combo = QComboBox()
        self.preset_combo.addItems([
            "Postshot (3D Gaussian Splatting)",
            "RealityScan / Metashape",
            "COLMAP Calibrated Rig",
            "Custom Workflow"
        ])
        self.preset_combo.setFixedWidth(240)
        layout.addWidget(self.preset_combo)

        layout.addStretch()

        # Discreet System Status
        sys_status = QLabel("Apple Metal (MPS) • GPU Active")
        sys_status.setStyleSheet("color: #71717A; font-size: 11px;")
        layout.addWidget(sys_status)

        return nav

    def _create_left_queue(self) -> QWidget:
        col = QFrame()
        col.setObjectName("leftSidebar")
        col.setFixedWidth(260)
        layout = QVBoxLayout(col)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # Queue Header
        hdr_layout = QHBoxLayout()
        hdr_title = QLabel("Queue")
        hdr_title.setObjectName("sectionHeader")
        hdr_layout.addWidget(hdr_title)

        count_badge = QLabel("3 files")
        count_badge.setStyleSheet("color: #636366; font-size: 11px;")
        hdr_layout.addWidget(count_badge)
        hdr_layout.addStretch()

        add_btn = QPushButton("+ Add Media")
        add_btn.setStyleSheet("""
            background-color: #1E1E24;
            border: 1px solid #2B2B33;
            border-radius: 4px;
            color: #D1D1D6;
            padding: 3px 8px;
            font-size: 11px;
        """)
        hdr_layout.addWidget(add_btn)
        layout.addLayout(hdr_layout)

        # Subtle Drop Zone
        drop_card = QFrame()
        drop_card.setStyleSheet("""
            background-color: transparent;
            border: 1px dashed #282830;
            border-radius: 6px;
            padding: 10px 8px;
        """)
        drop_layout = QVBoxLayout(drop_card)
        drop_layout.setAlignment(Qt.AlignCenter)
        drop_layout.setSpacing(2)

        txt_lbl = QLabel("Drop 360° videos or folders")
        txt_lbl.setStyleSheet("color: #8E8E93; font-size: 11px;")
        txt_lbl.setAlignment(Qt.AlignCenter)
        drop_layout.addWidget(txt_lbl)

        sub_lbl = QLabel("GoPro Max, Insta360, Kandao, DJI")
        sub_lbl.setStyleSheet("color: #55555C; font-size: 10px;")
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
        cards_layout.setSpacing(6)

        items_data = [
            ("GS_PARK_WALK_8K.mp4", "8K • 01:45 • GPS/IMU", True),
            ("GOPRO_MAX_INTERIOR.mp4", "5.6K • 03:12 • GPMF", False),
            ("DRONE_ROOF_SURVEY.mp4", "4K Flat • 00:58 • SRT", False),
        ]

        for name, meta, selected in items_data:
            card = self._create_queue_item(name, meta, selected)
            cards_layout.addWidget(card)

        cards_layout.addStretch()
        scroll.setWidget(cards_container)
        layout.addWidget(scroll, 1)

        return col

    def _create_queue_item(self, name: str, meta: str, selected: bool) -> QWidget:
        card = QFrame()
        card_border = "#0A84FF" if selected else "#222228"
        card_bg = "#1B1B22" if selected else "#151518"

        card.setStyleSheet(f"""
            QFrame {{
                background-color: {card_bg};
                border: 1px solid {card_border};
                border-radius: 6px;
                padding: 8px;
            }}
            QFrame:hover {{
                border-color: #3A3A48;
            }}
        """)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(3)

        title = QLabel(name)
        title.setStyleSheet("color: #FFFFFF; font-weight: 500; font-size: 11px;")
        layout.addWidget(title)

        meta_lbl = QLabel(meta)
        meta_lbl.setStyleSheet("color: #71717A; font-size: 10px;")
        layout.addWidget(meta_lbl)

        return card

    def _create_center_viewport(self) -> QWidget:
        col = QFrame()
        col.setObjectName("centerArea")
        layout = QVBoxLayout(col)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)

        # Viewport Header Toolbar
        tb_layout = QHBoxLayout()
        tb_layout.setContentsMargins(0, 0, 0, 0)
        tb_layout.setSpacing(10)

        # Segmented Face Control (Pill container)
        seg_container = QFrame()
        seg_container.setStyleSheet("""
            background-color: #17171B;
            border: 1px solid #24242C;
            border-radius: 6px;
            padding: 2px;
        """)
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
        tb_layout.addSpacing(12)

        # Discreet Overlays Toggles
        self.chk_ai_mask = QCheckBox("Operator Mask Overlay")
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

        # Minimal Timeline Scrubber
        tl_bar = QFrame()
        tl_bar.setStyleSheet("""
            background-color: #141418;
            border: 1px solid #202026;
            border-radius: 6px;
            padding: 4px 10px;
        """)
        tl_layout = QHBoxLayout(tl_bar)
        tl_layout.setContentsMargins(6, 2, 6, 2)
        tl_layout.setSpacing(10)

        play_btn = QPushButton("▶")
        play_btn.setFixedSize(24, 24)
        play_btn.setStyleSheet("""
            background-color: #202028;
            border: 1px solid #2D2D38;
            border-radius: 12px;
            color: #EDEDED;
            font-size: 10px;
        """)
        tl_layout.addWidget(play_btn)

        timecode = QLabel("00:14.2 / 01:45.0")
        timecode.setStyleSheet("color: #A1A1A6; font-family: monospace; font-size: 11px;")
        tl_layout.addWidget(timecode)

        scrubber = QSlider(Qt.Horizontal)
        scrubber.setRange(0, 100)
        scrubber.setValue(14)
        tl_layout.addWidget(scrubber, 1)

        frame_lbl = QLabel("Frame 426")
        frame_lbl.setStyleSheet("color: #71717A; font-family: monospace; font-size: 11px;")
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
            "Front": (0.0, 0.0, 0.0),
            "Right": (90.0, 0.0, 0.0),
            "Back": (180.0, 0.0, 0.0),
            "Left": (270.0, 0.0, 0.0),
            "Up": (0.0, 90.0, 0.0),
            "Down": (0.0, -90.0, 0.0),
        }
        yaw, pitch, roll = angles.get(self.current_face, (0.0, 0.0, 0.0))

        map_x, map_y = GeometryProcessor.create_rectilinear_map(
            src_h, src_w, dest_res, dest_res, self.fov, yaw, pitch, roll
        )
        rect_img = cv2.remap(self.equirect_bgr, map_x, map_y, cv2.INTER_LINEAR)

        # Subtle, professional overlays on Down face
        if self.current_face == "Down":
            overlay = rect_img.copy()
            center_x, center_y = dest_res // 2, dest_res // 2

            # Nadir Disc
            if self.show_nadir_disc:
                radius_px = int((self.nadir_radius / 100.0) * (dest_res / 2.0))
                cv2.circle(overlay, (center_x, center_y), radius_px, (15, 15, 18), -1)
                cv2.circle(overlay, (center_x, center_y), radius_px, (90, 90, 100), 1)

            # AI Operator Mask (Subdued subtle tint)
            if self.show_ai_mask:
                op_x1, op_y1 = center_x - 110, center_y + 50
                op_x2, op_y2 = center_x + 110, dest_res - 30
                cv2.ellipse(overlay, ((op_x1 + op_x2) // 2, (op_y1 + op_y2) // 2), (120, 160), 0, 0, 360, (20, 30, 180), -1)

            cv2.addWeighted(overlay, 0.40, rect_img, 0.60, 0, rect_img)

        # Clean typographic overlay
        cv2.putText(rect_img, f"{self.current_face.upper()} VIEW", (24, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (230, 230, 235), 1, cv2.LINE_AA)
        cv2.putText(rect_img, f"FOV {self.fov} deg  |  PINHOLE CALIBRATED", (24, 55), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (140, 140, 150), 1, cv2.LINE_AA)

        # Convert to QPixmap
        rgb = cv2.cvtColor(rect_img, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        qimg = QImage(rgb.data, w, h, ch * w, QImage.Format_RGB888)
        pix = QPixmap.fromImage(qimg).scaled(780, 620, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.preview_image_label.setPixmap(pix)

    def _create_right_inspector(self) -> QWidget:
        col = QFrame()
        col.setObjectName("rightInspector")
        col.setFixedWidth(340)
        layout = QVBoxLayout(col)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        # Header
        hdr = QLabel("Settings")
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

        # Section 1: Projection
        c_layout.addWidget(self._create_projection_card())

        # Section 2: Masking
        c_layout.addWidget(self._create_masking_card())

        # Section 3: Output & Priors
        c_layout.addWidget(self._create_output_card())

        c_layout.addStretch()
        scroll.setWidget(container)
        layout.addWidget(scroll, 1)
        return col

    def _create_projection_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("inspectorCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        title = QLabel("Camera & Projection")
        title.setObjectName("cardTitle")
        layout.addWidget(title)

        grid = QGridLayout()
        grid.setSpacing(6)

        grid.addWidget(QLabel("Layout:"), 0, 0)
        layout_cb = QComboBox()
        layout_cb.addItems(["Cube Map (6 Views)", "Ring (Horizon)", "Fibonacci Sphere"])
        grid.addWidget(layout_cb, 0, 1)

        grid.addWidget(QLabel("Resolution:"), 1, 0)
        res_cb = QComboBox()
        res_cb.addItems(["2048 x 2048", "3072 x 3072", "4096 x 4096"])
        grid.addWidget(res_cb, 1, 1)

        grid.addWidget(QLabel("FOV:"), 2, 0)
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

        imu_chk = QCheckBox("Auto-level horizon (IMU)")
        imu_chk.setChecked(True)
        layout.addWidget(imu_chk)

        return card

    def _create_masking_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("inspectorCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        title = QLabel("Operator & Nadir Masking")
        title.setObjectName("cardTitle")
        layout.addWidget(title)

        grid = QGridLayout()
        grid.setSpacing(6)

        grid.addWidget(QLabel("Model:"), 0, 0)
        model_cb = QComboBox()
        model_cb.addItems(["YOLO26-M Seg", "YOLO26-N Seg", "Custom Weights"])
        grid.addWidget(model_cb, 0, 1)

        grid.addWidget(QLabel("Scope:"), 1, 0)
        scope_cb = QComboBox()
        scope_cb.addItems(["Down face only", "All cameras"])
        grid.addWidget(scope_cb, 1, 1)

        grid.addWidget(QLabel("Nadir Size:"), 2, 0)
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

        chk_soft = QCheckBox("Soft mask (alpha blend for 3DGS)")
        chk_soft.setChecked(True)
        layout.addWidget(chk_soft)

        return card

    def _create_output_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("inspectorCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        title = QLabel("Output & Calibration")
        title.setObjectName("cardTitle")
        layout.addWidget(title)

        grid = QGridLayout()
        grid.setSpacing(6)

        grid.addWidget(QLabel("Format:"), 0, 0)
        fmt_cb = QComboBox()
        fmt_cb.addItems(["JPG (Quality 95%)", "PNG (Lossless)", "TIFF"])
        grid.addWidget(fmt_cb, 0, 1)

        grid.addWidget(QLabel("Interval:"), 1, 0)
        int_cb = QComboBox()
        int_cb.addItems(["Every 1.0 s", "Every 0.5 s", "Adaptive (Flow)"])
        grid.addWidget(int_cb, 1, 1)

        layout.addLayout(grid)

        chk_colmap = QCheckBox("Export COLMAP rig calibration")
        chk_colmap.setChecked(True)
        layout.addWidget(chk_colmap)

        chk_transforms = QCheckBox("Export transforms.json (Postshot)")
        chk_transforms.setChecked(True)
        layout.addWidget(chk_transforms)

        chk_exif = QCheckBox("Embed optical EXIF & GPS heading")
        chk_exif.setChecked(True)
        layout.addWidget(chk_exif)

        return card

    def _create_hud_bar(self) -> QWidget:
        hud = QFrame()
        hud.setObjectName("hudBar")
        hud.setFixedHeight(56)
        layout = QHBoxLayout(hud)
        layout.setContentsMargins(18, 0, 18, 0)
        layout.setSpacing(16)

        est_text = QLabel("1,440 images  •  ~2.8 GB  •  Estimated time: 1m 15s")
        est_text.setStyleSheet("color: #8E8E93; font-size: 11px;")
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
            print("Running interactive 360 Extractor Pro mockup...")
            return app.exec()

        pump(app, 1500)

        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if not window.grab().save(str(output_path)):
            print(f"error: could not write {output_path}", file=sys.stderr)
            return 1

        print(f"Wrote pro studio mockup screenshot: {output_path} ({output_path.stat().st_size / 1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
