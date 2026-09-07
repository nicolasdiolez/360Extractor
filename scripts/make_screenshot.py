#!/usr/bin/env python3
"""Capture the actual Studio window with a synthetic panorama or supplied media.

No demo log, fake benchmark or synthetic UI is injected. Without --input the
source panorama itself is synthetic. Preferences are isolated and all Qt workers
are drained before shutdown. Run from a GUI-capable development environment.
"""
from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

import cv2  # noqa: E402
import numpy as np  # noqa: E402
from PySide6.QtCore import QEventLoop, QThreadPool, QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402


def make_demo_equirect(path: Path, width: int = 2048, height: int = 1024) -> np.ndarray:
    """Create a rich synthetic 360 equirectangular scene: sky gradient, perspective grid,
    architectural pillars around the horizon, nadir tripod, and a nadir tripod.
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



def pump(app, milliseconds):
    loop = QEventLoop()
    QTimer.singleShot(milliseconds, loop.quit)
    loop.exec()
    app.processEvents()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, help="Optional already stitched panorama/video")
    parser.add_argument("-o", "--output-gui", type=Path, default=REPO_ROOT / "docs/images/screenshot-gui.png")
    args = parser.parse_args(argv)
    with tempfile.TemporaryDirectory(prefix="360-studio-capture-") as temporary:
        temp = Path(temporary)
        previous = os.environ.get("EXTRACTOR360_CONFIG_DIR")
        os.environ["EXTRACTOR360_CONFIG_DIR"] = str(temp / "preferences")
        from extractor360.core.settings_manager import SettingsManager
        from extractor360.ui.main_window import MainWindow
        SettingsManager._instance = None
        settings = SettingsManager()
        settings.settings.update(layout_mode="cube", resolution=2048, output_format="png")
        source = args.input.resolve() if args.input else temp / "Studio_Demo_360.jpg"
        if args.input is None:
            make_demo_equirect(source)
        if not source.is_file():
            parser.error(f"Input does not exist: {source}")
        app = QApplication.instance() or QApplication([])
        window = MainWindow()
        try:
            window.resize(1540, 1020)
            window.show()
            window.add_videos_from_paths([str(source)])
            window.select_card(window._video_cards[0])
            window.preview_widget.set_face("Front")
            pump(app, 1800)
            window.preview_widget.threadpool.waitForDone(15000)
            QThreadPool.globalInstance().waitForDone(15000)
            pump(app, 100)
            if window.preview_widget.cached_image is None:
                raise RuntimeError("Preview did not produce an image")
            args.output_gui.parent.mkdir(parents=True, exist_ok=True)
            if not window.grab().save(str(args.output_gui)):
                raise OSError(f"Could not save screenshot: {args.output_gui}")
            print(f"Captured actual Studio: {args.output_gui}")
        finally:
            window.close()
            window.preview_widget.threadpool.waitForDone(15000)
            QThreadPool.globalInstance().waitForDone(15000)
            pump(app, 100)
            SettingsManager._instance = None
            if previous is None:
                os.environ.pop("EXTRACTOR360_CONFIG_DIR", None)
            else:
                os.environ["EXTRACTOR360_CONFIG_DIR"] = previous
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
