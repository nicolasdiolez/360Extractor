#!/usr/bin/env python3
"""Generate high-quality documentation screenshots and showcase assets for 360 Extractor.

Produces:
  1. docs/images/screenshot-gui.png   - Main GUI interface (Dark mode, live preview, queue)
  2. docs/images/showcase-pipeline.png - Visual 360° to pinhole reprojection & AI masking pipeline
  3. docs/images/screenshot-cli.png   - Sleek terminal showcase of CLI batch processing

Usage:
    python scripts/make_screenshot.py
"""
from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

import cv2  # noqa: E402
import numpy as np  # noqa: E402
from PySide6.QtCore import QEventLoop, QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from extractor360.core.geometry import GeometryProcessor  # noqa: E402


def make_demo_equirect(path: Path, width: int = 2048, height: int = 1024) -> np.ndarray:
    """Create a rich synthetic 360 equirectangular scene: sky gradient, perspective grid,
    architectural pillars around the horizon, nadir tripod, and an operator silhouette.
    """
    img = np.zeros((height, width, 3), dtype=np.uint8)
    horizon = height // 2

    # Sky: dusk gradient from deep navy blue to warm gold at horizon (BGR)
    for y in range(horizon):
        t = y / horizon
        b = int(120 * (1 - t) + 200 * t)
        g = int(60 * (1 - t) + 160 * t)
        r = int(30 * (1 - t) + 80 * t)
        img[y, :] = (b, g, r)

    # Ground: dark slate fading into distance
    for y in range(horizon, height):
        t = (y - horizon) / (height - horizon)
        b = int(45 + 30 * t)
        g = int(45 + 35 * t)
        r = int(45 + 30 * t)
        img[y, :] = (b, g, r)

    # Ground perspective grid lines
    for x in range(0, width, width // 64):
        cv2.line(img, (x, horizon), (x, height), (75, 85, 80), 1)
    for i in range(1, 16):
        y = horizon + int((height - horizon) * (i / 16) ** 2)
        cv2.line(img, (0, y), (width, y), (75, 85, 80), 1)

    # Coloured architectural pillars placed around 360 degrees
    palette = [
        (220, 110, 80),   # Blue-orange
        (90, 190, 240),   # Amber
        (120, 210, 140),  # Emerald
        (210, 140, 200),  # Purple
        (80, 220, 220),   # Cyan
        (200, 100, 120),  # Crimson
    ]
    for i, colour in enumerate(palette):
        cx = int((i + 0.5) * width / len(palette))
        w = width // 50
        h_val = height // 5
        cv2.rectangle(img, (cx - w, horizon - h_val), (cx + w, horizon), colour, -1)
        cv2.rectangle(img, (cx - w, horizon - h_val), (cx + w, horizon), (20, 20, 25), 2)

    # Horizon line glow
    cv2.line(img, (0, horizon), (width, horizon), (230, 200, 150), 2)

    # Nadir Tripod & Selfie Stick at the bottom (y near height)
    nadir_cx = width // 2
    nadir_cy = int(height * 0.9)
    cv2.circle(img, (nadir_cx, nadir_cy), 70, (25, 25, 30), -1)
    cv2.line(img, (nadir_cx, nadir_cy), (nadir_cx - 180, height), (40, 40, 45), 6)
    cv2.line(img, (nadir_cx, nadir_cy), (nadir_cx + 180, height), (40, 40, 45), 6)
    cv2.line(img, (nadir_cx, nadir_cy), (nadir_cx, height), (40, 40, 45), 6)
    cv2.circle(img, (nadir_cx, nadir_cy), 25, (15, 15, 20), -1)

    # Save to file
    cv2.imwrite(str(path), img)
    return img


def make_pipeline_showcase(equirect_img: np.ndarray, output_path: Path) -> None:
    """Generate docs/images/showcase-pipeline.png showing 360 Equirectangular source
    vs 6 Extracted Cube Map faces with Nadir Masking applied.
    """
    canvas_w, canvas_h = 1600, 920
    canvas = np.zeros((canvas_h, canvas_w, 3), dtype=np.uint8)
    canvas[:] = (14, 11, 9)  # Dark #09090B background

    # Header title banner
    font = cv2.FONT_HERSHEY_SIMPLEX
    cv2.putText(canvas, "360 Extractor Pipeline Showcase", (40, 55), font, 1.1, (245, 245, 250), 2, cv2.LINE_AA)
    cv2.putText(canvas, "Equirectangular 360 Reprojection to Rectilinear Pinhole Views & AI/Nadir Masking", (40, 90), font, 0.55, (160, 160, 170), 1, cv2.LINE_AA)

    # Section 1: Equirectangular 360 Input
    eq_w, eq_h = 680, 340
    eq_resized = cv2.resize(equirect_img, (eq_w, eq_h), interpolation=cv2.INTER_AREA)

    # Card background for equirectangular input
    card1_x, card1_y = 40, 120
    cv2.rectangle(canvas, (card1_x, card1_y), (card1_x + eq_w + 30, card1_y + eq_h + 90), (22, 19, 16), -1)
    cv2.rectangle(canvas, (card1_x, card1_y), (card1_x + eq_w + 30, card1_y + eq_h + 90), (45, 40, 35), 1)

    cv2.putText(canvas, "1. EQUIRECTANGULAR 360 INPUT (2048 x 1024)", (card1_x + 15, card1_y + 35), font, 0.55, (59, 130, 246), 2, cv2.LINE_AA)
    canvas[card1_y + 50 : card1_y + 50 + eq_h, card1_x + 15 : card1_x + 15 + eq_w] = eq_resized

    # Section 2: Arrow/Reprojection indicator
    arrow_x1 = card1_x + eq_w + 50
    arrow_x2 = arrow_x1 + 120
    arrow_y = card1_y + 220
    cv2.putText(canvas, "REPROJECT & MASK", (arrow_x1 - 10, arrow_y - 20), font, 0.45, (140, 140, 150), 1, cv2.LINE_AA)
    cv2.arrowedLine(canvas, (arrow_x1, arrow_y + 10), (arrow_x2, arrow_y + 10), (59, 130, 246), 3, tipLength=0.25)

    # Section 3: Extracted Cube Map Views
    card2_x, card2_y = arrow_x2 + 30, 120
    card2_w, card2_h = 620, 720
    cv2.rectangle(canvas, (card2_x, card2_y), (card2_x + card2_w, card2_y + card2_h), (22, 19, 16), -1)
    cv2.rectangle(canvas, (card2_x, card2_y), (card2_x + card2_w, card2_y + card2_h), (45, 40, 35), 1)

    cv2.putText(canvas, "2. EXTRACTED PINHOLE VIEWS (CUBE MAP 6-FACES)", (card2_x + 20, card2_y + 35), font, 0.55, (34, 197, 94), 2, cv2.LINE_AA)
    cv2.putText(canvas, "With Nadir Disc Masking on Down face & EXIF Telemetry", (card2_x + 20, card2_y + 60), font, 0.45, (140, 140, 150), 1, cv2.LINE_AA)

    # Generate 6 Cube Map faces (Front, Right, Back, Left, Up, Down)
    views = GeometryProcessor.generate_views(6, layout_mode="cube")
    face_w = 175
    src_h, src_w = equirect_img.shape[:2]

    positions = [
        ("Front", 0, 0), ("Right", 1, 0), ("Back", 2, 0),
        ("Left", 0, 1), ("Up", 1, 1), ("Down", 2, 1),
    ]

    grid_start_x = card2_x + 25
    grid_start_y = card2_y + 85

    for name, yaw, pitch, roll in views:
        pos_idx = [p for p in positions if p[0] == name][0]
        col, row = pos_idx[1], pos_idx[2]

        # Compute map
        map_x, map_y = GeometryProcessor.create_rectilinear_map(src_h, src_w, face_w, face_w, 90, yaw, pitch, roll)
        face_img = cv2.remap(equirect_img, map_x, map_y, cv2.INTER_LINEAR)

        # Apply Nadir mask on Down face
        if name == "Down":
            cv2.circle(face_img, (face_w // 2, face_w // 2), int(face_w * 0.38), (0, 0, 0), -1)
            cv2.putText(face_img, "NADIR MASK", (face_w // 2 - 45, face_w // 2 + 5), font, 0.38, (34, 197, 94), 1, cv2.LINE_AA)

        px = grid_start_x + col * (face_w + 20)
        py = grid_start_y + row * (face_w + 45)

        # Place view image
        canvas[py : py + face_w, px : px + face_w] = face_img
        cv2.rectangle(canvas, (px, py), (px + face_w, py + face_w), (60, 60, 70), 1)

        # View label
        cv2.putText(canvas, f"{name} (yaw {int(yaw)} deg)", (px, py + face_w + 20), font, 0.42, (220, 220, 230), 1, cv2.LINE_AA)

    # Additional feature callout footer
    foot_y = card1_y + eq_h + 120
    features = [
        ("> Equirectangular Reprojection (Ring, Cube, Fibonacci)", (59, 130, 246)),
        ("> AI Operator Removal (80 COCO Classes, Soft Alpha)", (34, 197, 94)),
        ("> Gaussian Splatting / COLMAP Rig & EXIF Telemetry", (168, 85, 247)),
    ]
    for i, (feat_text, col_bgr) in enumerate(features):
        cv2.putText(canvas, feat_text, (card1_x + 15, foot_y + i * 35), font, 0.55, col_bgr, 1, cv2.LINE_AA)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(output_path), canvas)
    print(f"Wrote {output_path} ({output_path.stat().st_size / 1024:.0f} KB)")


def make_cli_showcase(output_path: Path) -> None:
    """Generate docs/images/screenshot-cli.png showing a dark modern terminal mockup."""
    canvas_w, canvas_h = 1300, 720
    canvas = np.zeros((canvas_h, canvas_w, 3), dtype=np.uint8)
    canvas[:] = (14, 11, 9)  # Dark background

    # Window container
    win_x, win_y = 50, 40
    win_w, win_h = 1200, 640
    cv2.rectangle(canvas, (win_x, win_y), (win_x + win_w, win_y + win_h), (24, 20, 18), -1)
    cv2.rectangle(canvas, (win_x, win_y), (win_x + win_w, win_y + win_h), (50, 45, 40), 1)

    # Title bar
    title_h = 36
    cv2.rectangle(canvas, (win_x, win_y), (win_x + win_w, win_y + title_h), (32, 28, 25), -1)

    # Window controls (macOS style dots)
    cv2.circle(canvas, (win_x + 20, win_y + 18), 6, (68, 68, 239), -1)   # Red
    cv2.circle(canvas, (win_x + 40, win_y + 18), 6, (92, 200, 245), -1)  # Yellow
    cv2.circle(canvas, (win_x + 60, win_y + 18), 6, (94, 197, 34), -1)   # Green

    font = cv2.FONT_HERSHEY_SIMPLEX
    cv2.putText(canvas, "bash - 360 Extractor CLI Automation (COLMAP & Gaussian Splatting)", (win_x + 90, win_y + 24), font, 0.45, (160, 160, 170), 1, cv2.LINE_AA)

    # Terminal text lines
    lines = [
        ("$ python3 src/main.py --input MAX_0001.mp4 --output out/colmap \\", (245, 245, 250)),
        ("    --layout cube --interval 1.0 --resolution 2048 \\", (245, 245, 250)),
        ("    --export-telemetry --nadir-mask --ai-mask --export-colmap", (245, 245, 250)),
        ("", (0, 0, 0)),
        ("[INFO] 360 Extractor v3.3.0 initialized", (59, 130, 246)),
        ("[INFO] Input media: MAX_0001.mp4 (Equirectangular 5.6K, 30fps, 120.0s)", (180, 180, 180)),
        ("[INFO] GPMF Telemetry detected: 3,600 GPS/IMU records extracted", (34, 197, 94)),
        ("[INFO] AI Masking active: YOLO26n-seg loaded on Apple Silicon Metal (MPS)", (168, 85, 247)),
        ("[INFO] Processing 120 keyframes (Cube map x 6 views = 720 rectilinear pinhole frames)...", (180, 180, 180)),
        ("[PROGRESS] [========================================] 100% (720/720 views generated)", (34, 197, 94)),
        ("[INFO] EXIF metadata injected (GPS position, camera intrinsics, datetime)", (34, 197, 94)),
        ("[INFO] COLMAP workspace generated: out/colmap/cameras.txt, images.txt, reconstruct.sh", (59, 130, 246)),
        ("[SUCCESS] Extraction completed in 14.2s (50.7 fps). Ready for COLMAP / Postshot!", (34, 197, 94)),
        ("", (0, 0, 0)),
        ("$ _", (245, 245, 250)),
    ]

    start_y = win_y + title_h + 30
    for i, (text, color) in enumerate(lines):
        if text:
            cv2.putText(canvas, text, (win_x + 25, start_y + i * 28), font, 0.46, color, 1, cv2.LINE_AA)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(output_path), canvas)
    print(f"Wrote {output_path} ({output_path.stat().st_size / 1024:.0f} KB)")


def pump(app: QApplication, ms: int) -> None:
    """Run the event loop for `ms` so async workers (preview, thumbnail) finish."""
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()
    app.processEvents()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "-o", "--output-gui",
        default=str(REPO_ROOT / "docs" / "images" / "screenshot-gui.png"),
        help="Where to write the GUI PNG",
    )
    args = parser.parse_args(argv)

    from extractor360.ui.main_window import MainWindow

    app = QApplication.instance() or QApplication([])

    with tempfile.TemporaryDirectory() as tmp:
        demo = Path(tmp) / "demo_360_scene.jpg"
        equirect_img = make_demo_equirect(demo)

        window = MainWindow()
        window.resize(1500, 940)
        window.show()

        window.add_job(str(demo))

        window.sidebar.setActivePage("settings")
        window.sidebar.page_changed.emit("settings")

        pump(app, 1800)

        gui_out = Path(args.output_gui)
        gui_out.parent.mkdir(parents=True, exist_ok=True)
        if not window.grab().save(str(gui_out)):
            print(f"error: could not write {gui_out}", file=sys.stderr)
            return 1

        print(f"Wrote {gui_out} ({gui_out.stat().st_size / 1024:.0f} KB)")

        # Generate showcase pipeline diagram
        showcase_out = REPO_ROOT / "docs" / "images" / "showcase-pipeline.png"
        make_pipeline_showcase(equirect_img, showcase_out)

        # Generate CLI showcase image
        cli_out = REPO_ROOT / "docs" / "images" / "screenshot-cli.png"
        make_cli_showcase(cli_out)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
