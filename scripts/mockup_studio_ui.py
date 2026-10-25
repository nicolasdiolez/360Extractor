#!/usr/bin/env python3
"""360 Extractor Studio - Refined Theme A (Graphite & Warm Amber) with Progressive Disclosure.

- Aesthetic: DaVinci Resolve / Blender Pro dark graphite with warm amber accents (#F59E0B / #D97706).
- Progressive Disclosure: Clean, essential settings visible by default, with collapsible "Advanced" drawers.
- Interactive camera face selector, real-time AI & Nadir overlay, timeline scrubber, and dynamic HUD.

Usage:
    # Run interactive GUI:
    python scripts/mockup_studio_ui.py --interactive

    # Render screenshot to file:
    python scripts/mockup_studio_ui.py -o docs/images/mockup-studio-gui.png
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
    QGridLayout, QHBoxLayout, QLabel, QLineEdit, QMainWindow,
    QPushButton, QScrollArea, QSlider,
    QSplitter, QVBoxLayout, QWidget
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

    # Nadir Tripod
    nadir_cx = width // 2
    nadir_cy = int(height * 0.9)
    cv2.circle(img, (nadir_cx, nadir_cy), 70, (25, 25, 30), -1)
    cv2.line(img, (nadir_cx, nadir_cy), (nadir_cx - 180, height), (40, 40, 45), 6)
    cv2.line(img, (nadir_cx, nadir_cy), (nadir_cx + 180, height), (40, 40, 45), 6)
    cv2.line(img, (nadir_cx, nadir_cy), (nadir_cx, height), (40, 40, 45), 6)
    cv2.circle(img, (nadir_cx, nadir_cy), 25, (15, 15, 20), -1)

    cv2.imwrite(str(path), img)
    return img


class CollapsibleSection(QFrame):
    """An elegant collapsible drawer for advanced settings."""
    def __init__(self, title="Advanced Options", parent=None):
        super().__init__(parent)
        self.setObjectName("advancedSection")
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 4, 0, 0)
        self.layout.setSpacing(4)

        # Header Toggle Button
        self.toggle_btn = QPushButton(f"▶  {title}")
        self.toggle_btn.setObjectName("disclosureBtn")
        self.toggle_btn.setCursor(Qt.PointingHandCursor)
        self.toggle_btn.setCheckable(True)
        self.toggle_btn.setChecked(False)
        self.toggle_btn.clicked.connect(self._on_toggled)
        self.layout.addWidget(self.toggle_btn)

        # Content container
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(8, 6, 4, 4)
        self.content_layout.setSpacing(6)
        self.content_widget.setVisible(False)
        self.layout.addWidget(self.content_widget)

    def _on_toggled(self, checked: bool):
        self.content_widget.setVisible(checked)
        title_text = self.toggle_btn.text().split("  ")[-1]
        arrow = "▼" if checked else "▶"
        self.toggle_btn.setText(f"{arrow}  {title_text}")

    def addWidget(self, widget: QWidget):
        self.content_layout.addWidget(widget)

    def addLayout(self, layout):
        self.content_layout.addLayout(layout)


class StudioMockupWindow(QMainWindow):
    def __init__(self, demo_image_path: Path):
        super().__init__()
        self.setWindowTitle("360 Extractor Studio — [Graphite & Amber Theme]")
        self.resize(1540, 950)
        self.demo_image_path = demo_image_path
        self.equirect_bgr = cv2.imread(str(demo_image_path))
        if self.equirect_bgr is None:
            self.equirect_bgr = make_demo_equirect(demo_image_path)

        self.current_face = "Down"
        self.fov = 90
        self.pitch_offset = 0
        self.nadir_radius = 35.0
        self.show_ai_mask = True
        self.show_nadir_disc = True

        self._setup_stylesheet()
        self._build_ui()
        self._update_viewport_render()

    def _setup_stylesheet(self):
        # Theme A: Graphite & Warm Amber (#F59E0B / #D97706)
        self.setStyleSheet("""
            QMainWindow {
                background-color: #141417;
                color: #E6E6EA;
            }
            QWidget {
                font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI", Roboto, sans-serif;
                font-size: 11px;
                color: #9898A4;
                background-color: transparent;
            }
            /* Scroll Areas and Viewports (Fix light gray bleed) */
            QScrollArea, QScrollArea > QWidget, QScrollArea > QWidget > QWidget {
                background-color: transparent;
                border: none;
            }
            QScrollArea::viewport {
                background-color: transparent;
            }
            QFrame#topNav {
                background-color: #19191E;
                border-bottom: 1px solid #282833;
                padding: 0px 14px;
            }
            QFrame#leftSidebar {
                background-color: #16161A;
                border-right: 1px solid #262630;
            }
            QFrame#centerArea {
                background-color: #0F0F12;
            }
            QFrame#rightInspector {
                background-color: #16161A;
                border-left: 1px solid #262630;
            }
            QFrame#viewportContainer {
                background-color: #000000;
                border: 1px solid #262632;
                border-radius: 6px;
            }
            QFrame#hudBar {
                background-color: #19191E;
                border-top: 1px solid #282833;
                padding: 8px 18px;
            }
            QFrame#inspectorCard {
                background-color: #1D1D24;
                border: 1px solid #292934;
                border-radius: 6px;
                padding: 10px 12px;
            }
            QLabel#sectionHeader {
                color: #E2E2E8;
                font-weight: 600;
                font-size: 11px;
                text-transform: uppercase;
                letter-spacing: 0.8px;
            }
            QLabel#cardTitle {
                color: #E8E8EE;
                font-weight: 600;
                font-size: 12px;
            }
            /* Segmented Buttons */
            QPushButton#segmentBtn {
                background-color: transparent;
                border: none;
                border-radius: 4px;
                color: #9898A4;
                padding: 5px 12px;
                font-weight: 500;
                font-size: 11px;
            }
            QPushButton#segmentBtn:hover {
                color: #E8E8EE;
                background-color: rgba(255, 255, 255, 0.05);
            }
            QPushButton#segmentBtn[active="true"] {
                background-color: rgba(245, 158, 11, 0.15);
                color: #FBBF24;
                font-weight: 600;
                border: 1px solid #F59E0B;
            }
            /* Disclosure Button (Advanced toggle) */
            QPushButton#disclosureBtn {
                background-color: transparent;
                border: none;
                color: #727280;
                font-weight: 600;
                font-size: 10px;
                text-align: left;
                padding: 4px 0px;
            }
            QPushButton#disclosureBtn:hover {
                color: #FBBF24;
            }
            QPushButton#disclosureBtn:checked {
                color: #F59E0B;
            }
            /* Buttons */
            QPushButton#primaryActionBtn {
                background-color: #D97706;
                color: #FAF9F6;
                font-weight: 600;
                font-size: 12px;
                border-radius: 5px;
                padding: 8px 20px;
                border: none;
            }
            QPushButton#primaryActionBtn:hover {
                background-color: #F59E0B;
            }
            QPushButton#secondaryActionBtn {
                background-color: transparent;
                border: 1px solid #323240;
                border-radius: 5px;
                color: #C8C8D0;
                padding: 7px 16px;
                font-size: 11px;
            }
            QPushButton#secondaryActionBtn:hover {
                background-color: #22222B;
                color: #E8E8EE;
            }
            QPushButton#toolBtn {
                background-color: #17171C;
                border: 1px solid #2D2D3A;
                border-radius: 4px;
                color: #C8C8D0;
                padding: 3px 8px;
                font-size: 11px;
            }
            QPushButton#toolBtn:hover {
                border-color: #F59E0B;
                color: #E8E8EE;
            }
            /* Inputs */
            QComboBox, QDoubleSpinBox, QLineEdit {
                background-color: #151519;
                border: 1px solid #2C2C38;
                border-radius: 4px;
                padding: 4px 6px;
                color: #E6E6EA;
                font-size: 11px;
            }
            QComboBox:focus, QSpinBox:focus, QLineEdit:focus {
                border-color: #F59E0B;
            }
            QSlider::groove:horizontal {
                height: 3px;
                background: #2E2E3C;
                border-radius: 1.5px;
            }
            QSlider::sub-page:horizontal {
                background: #F59E0B;
                border-radius: 1.5px;
            }
            QSlider::handle:horizontal {
                background: #D8D8E0;
                border: 1px solid #F59E0B;
                width: 10px;
                margin-top: -3.5px;
                margin-bottom: -3.5px;
                border-radius: 5px;
            }
            QCheckBox {
                color: #C8C8D0;
                spacing: 6px;
                font-size: 11px;
            }
            QCheckBox::indicator {
                width: 13px;
                height: 13px;
                border-radius: 3px;
                border: 1px solid #363646;
                background-color: #17171C;
            }
            QCheckBox::indicator:checked {
                background-color: #F59E0B;
                border-color: #F59E0B;
            }
            QScrollBar:vertical {
                border: none;
                background: transparent;
                width: 4px;
            }
            QScrollBar::handle:vertical {
                background: #2E2E3E;
                border-radius: 2px;
            }
        """)

    def _build_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        root_layout = QVBoxLayout(main_widget)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # 1. Top Navbar
        top_nav = self._create_top_nav()
        root_layout.addWidget(top_nav)

        # 2. Main 3-Column Splitter
        content_splitter = QSplitter(Qt.Horizontal)
        content_splitter.setHandleWidth(1)
        content_splitter.setStyleSheet("QSplitter::handle { background: #242430; }")

        # Left Column: Media Queue (260px)
        left_col = self._create_left_queue()
        content_splitter.addWidget(left_col)

        # Center Column: Viewport & Timeline (Flex)
        center_col = self._create_center_viewport()
        content_splitter.addWidget(center_col)

        # Right Column: Inspector with Progressive Disclosure (360px)
        right_col = self._create_right_inspector()
        content_splitter.addWidget(right_col)

        content_splitter.setStretchFactor(0, 0)
        content_splitter.setStretchFactor(1, 1)
        content_splitter.setStretchFactor(2, 0)
        root_layout.addWidget(content_splitter, 1)

        # 3. Bottom HUD Action Bar
        hud_bar = self._create_hud_bar()
        root_layout.addWidget(hud_bar)

    def _create_top_nav(self) -> QWidget:
        nav = QFrame()
        nav.setObjectName("topNav")
        nav.setFixedHeight(48)
        layout = QHBoxLayout(nav)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(14)

        # Brand Title
        title_label = QLabel("360 Extractor")
        title_label.setStyleSheet("font-weight: 700; font-size: 13px; letter-spacing: -0.2px; color: #FFFFFF;")
        layout.addWidget(title_label)

        v_sep = QFrame()
        v_sep.setFrameShape(QFrame.VLine)
        v_sep.setFixedHeight(16)
        v_sep.setStyleSheet("color: #2E2E3C;")
        layout.addWidget(v_sep)

        # Workflow Target Selector
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
        layout.addWidget(self.preset_combo)

        layout.addStretch()

        # GPU Hardware Badge
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

    def _create_left_queue(self) -> QWidget:
        col = QFrame()
        col.setObjectName("leftSidebar")
        col.setFixedWidth(260)
        layout = QVBoxLayout(col)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # Header
        hdr_layout = QHBoxLayout()
        hdr_title = QLabel("Queue")
        hdr_title.setObjectName("sectionHeader")
        hdr_layout.addWidget(hdr_title)

        count_badge = QLabel("3 videos")
        count_badge.setStyleSheet("color: #71717A; font-size: 11px;")
        hdr_layout.addWidget(count_badge)
        hdr_layout.addStretch()

        add_btn = QPushButton("+ Add Media")
        add_btn.setObjectName("toolBtn")
        hdr_layout.addWidget(add_btn)
        layout.addLayout(hdr_layout)

        # Drop Zone
        drop_card = QFrame()
        drop_card.setStyleSheet("""
            background-color: rgba(255, 255, 255, 0.02);
            border: 1px dashed #30303E;
            border-radius: 6px;
            padding: 10px 8px;
        """)
        drop_layout = QVBoxLayout(drop_card)
        drop_layout.setAlignment(Qt.AlignCenter)
        drop_layout.setSpacing(2)

        txt_lbl = QLabel("Drop 360° videos or folders")
        txt_lbl.setStyleSheet("color: #D4D4D8; font-size: 11px; font-weight: 500;")
        txt_lbl.setAlignment(Qt.AlignCenter)
        drop_layout.addWidget(txt_lbl)

        sub_lbl = QLabel("GoPro Max, Insta360, Kandao, DJI")
        sub_lbl.setStyleSheet("color: #63636E; font-size: 10px;")
        sub_lbl.setAlignment(Qt.AlignCenter)
        drop_layout.addWidget(sub_lbl)
        layout.addWidget(drop_card)

        # Scrollable items
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea, QScrollArea > QWidget { border: none; background-color: transparent; }")

        cards_container = QWidget()
        cards_container.setObjectName("cardsContainer")
        cards_container.setStyleSheet("background-color: transparent;")
        cards_layout = QVBoxLayout(cards_container)
        cards_layout.setContentsMargins(0, 0, 0, 0)
        cards_layout.setSpacing(6)

        items_data = [
            ("GS_PARK_WALK_8K.mp4", "8K 360 • 01:45 • GPS/IMU Level", True),
            ("GOPRO_MAX_INTERIOR.mp4", "5.6K 360 • 03:12 • GPMF Telemetry", False),
            ("DRONE_ROOF_SURVEY.mp4", "4K Flat • 00:58 • SRT Subtitles", False),
        ]

        for name, meta, selected in items_data:
            card = QFrame()
            card.setObjectName("inspectorCard")
            if selected:
                card.setStyleSheet("background-color: #262630; border: 1px solid #F59E0B;")
            c_lay = QVBoxLayout(card)
            c_lay.setContentsMargins(8, 8, 8, 8)
            c_lay.setSpacing(3)

            t_lbl = QLabel(name)
            t_lbl.setStyleSheet("font-weight: 600; font-size: 11px; color: #FFFFFF;")
            c_lay.addWidget(t_lbl)

            m_lbl = QLabel(meta)
            m_lbl.setStyleSheet("color: #888896; font-size: 10px;")
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
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)

        # Toolbar: Segmented Face Selector + Overlay Toggles
        tb_layout = QHBoxLayout()
        tb_layout.setContentsMargins(0, 0, 0, 0)
        tb_layout.setSpacing(10)

        seg_container = QFrame()
        seg_container.setStyleSheet("background-color: #1A1A22; border: 1px solid #2D2D3B; border-radius: 5px; padding: 2px;")
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
        tb_layout.addSpacing(8)

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
        tl_bar.setFixedHeight(40)
        tl_layout = QHBoxLayout(tl_bar)
        tl_layout.setContentsMargins(10, 2, 10, 2)
        tl_layout.setSpacing(10)

        play_btn = QPushButton("▶")
        play_btn.setFixedSize(24, 24)
        play_btn.setObjectName("toolBtn")
        tl_layout.addWidget(play_btn)

        timecode = QLabel("00:14.2 / 01:45.0")
        timecode.setStyleSheet("font-family: monospace; font-size: 10px; color: #A1A1AA;")
        tl_layout.addWidget(timecode)

        scrubber = QSlider(Qt.Horizontal)
        scrubber.setRange(0, 100)
        scrubber.setValue(14)
        tl_layout.addWidget(scrubber, 1)

        frame_lbl = QLabel("Frame 426")
        frame_lbl.setStyleSheet("font-family: monospace; font-size: 10px; color: #8E8E96;")
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

        # Subtle Amber Overlays on Down Face
        if self.current_face == "Down":
            overlay = rect_img.copy()
            center_x, center_y = dest_res // 2, dest_res // 2

            # Nadir Disc
            if self.show_nadir_disc:
                radius_px = int((self.nadir_radius / 100.0) * (dest_res / 2.0))
                cv2.circle(overlay, (center_x, center_y), radius_px, (15, 15, 18), -1)
                cv2.circle(overlay, (center_x, center_y), radius_px, (245, 158, 11), 1)

            # AI Operator Mask
            if self.show_ai_mask:
                op_x1, op_y1 = center_x - 110, center_y + 50
                op_x2, op_y2 = center_x + 110, dest_res - 30
                cv2.ellipse(overlay, ((op_x1 + op_x2) // 2, (op_y1 + op_y2) // 2), (120, 160), 0, 0, 360, (20, 70, 210), -1)

            cv2.addWeighted(overlay, 0.40, rect_img, 0.60, 0, rect_img)

        # Clean typographic overlay
        cv2.putText(rect_img, f"{self.current_face.upper()} VIEW", (24, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (240, 240, 245), 1, cv2.LINE_AA)
        cv2.putText(rect_img, f"FOV {self.fov} deg | PINHOLE CALIBRATED", (24, 55), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (160, 160, 170), 1, cv2.LINE_AA)

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
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # Header
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
        c_layout.addWidget(self._create_camera_optics_card())
        c_layout.addWidget(self._create_quality_filters_card())
        c_layout.addWidget(self._create_ai_masking_card())
        c_layout.addWidget(self._create_export_calibration_card())

        c_layout.addStretch()
        scroll.setWidget(container)
        layout.addWidget(scroll, 1)
        return col

    # -------------------------------------------------------------------------
    # Card 1: Camera & Optics (Clean essentials + Advanced drawer)
    # -------------------------------------------------------------------------
    def _create_camera_optics_card(self) -> QWidget:
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

        # Primary Essentials (Always visible)
        grid.addWidget(QLabel("Layout:"), 0, 0)
        layout_cb = QComboBox()
        layout_cb.addItems(["Cube Map (6 Views)", "Ring (Horizon)", "Fibonacci Sphere"])
        grid.addWidget(layout_cb, 0, 1)

        grid.addWidget(QLabel("Resolution:"), 1, 0)
        res_cb = QComboBox()
        res_cb.addItems(["2048 x 2048 (Recommended)", "3072 x 3072", "4096 x 4096"])
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

        # Advanced Drawer (Collapsed by default)
        adv = CollapsibleSection("Advanced Camera Options")
        adv_grid = QGridLayout()
        adv_grid.setSpacing(5)

        adv_grid.addWidget(QLabel("Media Type:"), 0, 0)
        media_type = QComboBox()
        media_type.addItems(["360° Equirectangular", "Flat Media (Passthrough)"])
        adv_grid.addWidget(media_type, 0, 1)

        adv_grid.addWidget(QLabel("Pitch Offset:"), 1, 0)
        pitch_cb = QComboBox()
        pitch_cb.addItems(["0° (Horizon)", "-20° (High Mode)", "+20° (Low Mode)"])
        adv_grid.addWidget(pitch_cb, 1, 1)
        adv.addLayout(adv_grid)

        adv.addWidget(QCheckBox("Auto-Horizon Leveling (IMU Gyro Fusion)"))
        adv.addWidget(QCheckBox("Lanczos-4 High-Sharpness Interpolation"))
        layout.addWidget(adv)

        return card

    # -------------------------------------------------------------------------
    # Card 2: Quality & Motion (Clean essentials + Advanced drawer)
    # -------------------------------------------------------------------------
    def _create_quality_filters_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("inspectorCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)

        title = QLabel("2. Quality & Motion Filters")
        title.setObjectName("cardTitle")
        layout.addWidget(title)

        # Essential: Blur rejection toggle + analyze button
        blur_row = QHBoxLayout()
        chk_blur = QCheckBox("Reject Blurry Views")
        chk_blur.setChecked(True)
        blur_row.addWidget(chk_blur)

        blur_row.addWidget(QLabel("Min:"))
        blur_spin = QDoubleSpinBox()
        blur_spin.setRange(0.0, 1000.0)
        blur_spin.setValue(100.0)
        blur_spin.setFixedWidth(65)
        blur_row.addWidget(blur_spin)

        btn_analyze = QPushButton("🔍 Analyze")
        btn_analyze.setObjectName("toolBtn")
        blur_row.addWidget(btn_analyze)
        layout.addLayout(blur_row)

        # Advanced Drawer
        adv = CollapsibleSection("Advanced Quality Controls")
        adv.addWidget(QCheckBox("Smart Adaptive Blur (Moving Average)"))

        # Sharpening
        sharp_row = QHBoxLayout()
        chk_sharp = QCheckBox("Sharpening Recovery")
        sharp_row.addWidget(chk_sharp)
        sharp_slider = QSlider(Qt.Horizontal)
        sharp_slider.setRange(0, 100)
        sharp_slider.setValue(50)
        sharp_row.addWidget(sharp_slider)
        sharp_row.addWidget(QLabel("0.5"))
        adv.addLayout(sharp_row)

        # Optical flow motion
        flow_row = QHBoxLayout()
        chk_flow = QCheckBox("Optical Flow Motion Keyframing")
        flow_row.addWidget(chk_flow)
        flow_spin = QDoubleSpinBox()
        flow_spin.setRange(0.1, 10.0)
        flow_spin.setValue(0.5)
        flow_spin.setFixedWidth(55)
        flow_row.addWidget(flow_spin)
        adv.addLayout(flow_row)

        layout.addWidget(adv)
        return card

    # -------------------------------------------------------------------------
    # Card 3: AI & Nadir Masking (Clean essentials + Advanced drawer)
    # -------------------------------------------------------------------------
    def _create_ai_masking_card(self) -> QWidget:
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

        # Essentials
        grid.addWidget(QLabel("AI Mode:"), 0, 0)
        ai_mode_cb = QComboBox()
        ai_mode_cb.addItems(["Generate Mask (Photogrammetry / 3DGS)", "Skip Frame on Person", "Disabled"])
        grid.addWidget(ai_mode_cb, 0, 1)

        grid.addWidget(QLabel("Scope:"), 1, 0)
        scope_cb = QComboBox()
        scope_cb.addItems(["Down Face Only (Preserve Scene)", "All Cameras"])
        grid.addWidget(scope_cb, 1, 1)

        grid.addWidget(QLabel("Nadir Disc:"), 2, 0)
        rad_row = QHBoxLayout()
        rad_slider = QSlider(Qt.Horizontal)
        rad_slider.setRange(0, 100)
        rad_slider.setValue(int(self.nadir_radius))
        rad_lbl = QLabel(f"{int(self.nadir_radius)}%")
        rad_slider.valueChanged.connect(lambda v: (rad_lbl.setText(f"{v}%"), setattr(self, 'nadir_radius', float(v)), self._update_viewport_render()))
        rad_row.addWidget(rad_slider)
        rad_row.addWidget(rad_lbl)
        grid.addLayout(rad_row, 2, 1)

        layout.addLayout(grid)

        # Advanced AI Drawer
        adv = CollapsibleSection("Advanced AI & Target Classes")
        adv_grid = QGridLayout()
        adv_grid.setSpacing(5)

        adv_grid.addWidget(QLabel("Model:"), 0, 0)
        model_cb = QComboBox()
        model_cb.addItems(["YOLO26-M Seg (Recommended)", "YOLO26-N Seg (Fast)", "Custom (.pt)"])
        adv_grid.addWidget(model_cb, 0, 1)

        adv_grid.addWidget(QLabel("Confidence:"), 1, 0)
        conf_row = QHBoxLayout()
        conf_slider = QSlider(Qt.Horizontal)
        conf_slider.setRange(5, 95)
        conf_slider.setValue(25)
        conf_lbl = QLabel("25%")
        conf_slider.valueChanged.connect(lambda v: conf_lbl.setText(f"{v}%"))
        conf_row.addWidget(conf_slider)
        conf_row.addWidget(conf_lbl)
        adv_grid.addLayout(conf_row, 1, 1)
        adv.addLayout(adv_grid)

        # Classes
        cls_row = QHBoxLayout()
        cls_row.addWidget(QLabel("Classes:"))
        chk_h = QCheckBox("Humans")
        chk_h.setChecked(True)
        chk_v = QCheckBox("Vehicles")
        chk_p = QCheckBox("Plants")
        cls_row.addWidget(chk_h)
        cls_row.addWidget(chk_v)
        cls_row.addWidget(chk_p)
        adv.addLayout(cls_row)

        cust_row = QHBoxLayout()
        cust_row.addWidget(QLabel("Custom:"))
        txt_cust = QLineEdit()
        txt_cust.setPlaceholderText("e.g. backpack, tripod")
        cust_row.addWidget(txt_cust)
        adv.addLayout(cust_row)

        adv.addWidget(QCheckBox("Soft Alpha Mask (Native Softness for 3DGS)"))
        adv.addWidget(QCheckBox("Invert Mask (Photogrammetry: Black=Subject)"))
        adv.addWidget(QCheckBox("Sky Mask (Outdoor Floater Reduction)"))

        layout.addWidget(adv)
        return card

    # -------------------------------------------------------------------------
    # Card 4: Output & Calibration (Clean essentials + Advanced drawer)
    # -------------------------------------------------------------------------
    def _create_export_calibration_card(self) -> QWidget:
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

        grid.addWidget(QLabel("Format:"), 0, 0)
        fmt_cb = QComboBox()
        fmt_cb.addItems(["JPG (Quality 95%)", "PNG (Lossless)", "TIFF (16-bit)"])
        grid.addWidget(fmt_cb, 0, 1)

        grid.addWidget(QLabel("Interval:"), 1, 0)
        int_row = QHBoxLayout()
        int_spin = QDoubleSpinBox()
        int_spin.setRange(0.1, 100.0)
        int_spin.setValue(1.0)
        int_spin.setFixedWidth(55)
        int_unit = QComboBox()
        int_unit.addItems(["Seconds", "Frames"])
        int_row.addWidget(int_spin)
        int_row.addWidget(int_unit)
        grid.addLayout(int_row, 1, 1)

        layout.addLayout(grid)

        # Essential Priors (Checkboxes)
        layout.addWidget(QCheckBox("Export COLMAP Priors (cameras.txt + rig_rotations)"))
        layout.addWidget(QCheckBox("Export transforms.json (Postshot / Nerfstudio)"))
        layout.addWidget(QCheckBox("Embed Optical EXIF (Focal, Make/Model, Heading)"))

        # Advanced Output Drawer
        adv = CollapsibleSection("Advanced Naming & GPS Options")
        adv_grid = QGridLayout()
        adv_grid.setSpacing(5)

        adv_grid.addWidget(QLabel("Naming:"), 0, 0)
        name_cb = QComboBox()
        name_cb.addItems(["RealityScan Standard", "Simple Sequential", "Custom Pattern"])
        adv_grid.addWidget(name_cb, 0, 1)

        adv_grid.addWidget(QLabel("Altitude:"), 1, 0)
        alt_cb = QComboBox()
        alt_cb.addItems(["Absolute (ASL)", "Relative (AGL)"])
        adv_grid.addWidget(alt_cb, 1, 1)
        adv.addLayout(adv_grid)

        layout.addWidget(adv)
        return card

    def _create_hud_bar(self) -> QWidget:
        hud = QFrame()
        hud.setObjectName("hudBar")
        hud.setFixedHeight(54)
        layout = QHBoxLayout(hud)
        layout.setContentsMargins(18, 0, 18, 0)
        layout.setSpacing(14)

        est_text = QLabel("1,440 pinhole images (240 frames × 6 views) • ~2.8 GB • Est. time: ~1m 15s")
        est_text.setStyleSheet("font-weight: 500; font-size: 11px; color: #D4D4D8;")
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
    parser.add_argument("-o", "--output", default=str(REPO_ROOT / "docs" / "images" / "mockup-studio-gui.png"))
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
            print("Interactive 360 Extractor Studio is open with Theme A (Graphite & Amber).")
            return app.exec()

        pump(app, 1500)

        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if not window.grab().save(str(output_path)):
            print(f"error: could not write {output_path}", file=sys.stderr)
            return 1

        print(f"Wrote Theme A mockup screenshot: {output_path} ({output_path.stat().st_size / 1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
