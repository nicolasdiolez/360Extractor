#!/usr/bin/env python3
"""Render the README screenshot of the GUI, headlessly.

No display needed: Qt runs on the "offscreen" platform and the window is
grabbed straight into a PNG. A synthetic equirectangular demo image is put in
the queue so the preview panel shows a real reprojected view rather than the
empty state.

    python scripts/make_screenshot.py [-o docs/images/screenshot-gui.png]
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


def make_demo_equirect(path: Path, width: int = 2048, height: int = 1024) -> None:
    """A synthetic 360 scene: sky, ground, horizon and coloured pillars.

    Synthetic on purpose — the screenshot must not pass off someone else's
    footage as a sample. It still exercises the real reprojection path.
    """
    img = np.zeros((height, width, 3), dtype=np.uint8)
    horizon = height // 2

    # Sky: deep blue at the zenith fading to pale at the horizon (BGR).
    for y in range(horizon):
        t = y / horizon
        img[y, :] = (int(180 - 60 * (1 - t)), int(130 - 40 * (1 - t)), int(70 - 30 * (1 - t)))

    # Ground: darker, fading with depth.
    for y in range(horizon, height):
        t = (y - horizon) / (height - horizon)
        img[y, :] = (int(60 + 30 * t), int(75 + 35 * t), int(70 + 30 * t))

    # Ground grid, denser near the horizon (reads as perspective once reprojected).
    for x in range(0, width, width // 48):
        cv2.line(img, (x, horizon), (x, height), (110, 125, 115), 1)
    for i in range(1, 14):
        y = horizon + int((height - horizon) * (i / 14) ** 2)
        cv2.line(img, (0, y), (width, y), (110, 125, 115), 1)

    # Coloured pillars around the horizon so every view has structure.
    palette = [(80, 90, 220), (90, 180, 240), (120, 200, 120), (210, 160, 90), (200, 120, 200), (90, 210, 230)]
    for i, colour in enumerate(palette):
        cx = int((i + 0.5) * width / len(palette))
        w = width // 60
        cv2.rectangle(img, (cx - w, horizon - height // 6), (cx + w, horizon), colour, -1)
        cv2.rectangle(img, (cx - w, horizon - height // 6), (cx + w, horizon), (30, 30, 30), 2)

    cv2.line(img, (0, horizon), (width, horizon), (200, 200, 200), 2)
    cv2.imwrite(str(path), img)


def pump(app: QApplication, ms: int) -> None:
    """Run the event loop for `ms` so async workers (preview, thumbnail) finish."""
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()
    app.processEvents()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "-o", "--output",
        default=str(REPO_ROOT / "docs" / "images" / "screenshot-gui.png"),
        help="Where to write the PNG",
    )
    parser.add_argument("--width", type=int, default=1500)
    parser.add_argument("--height", type=int, default=940)
    args = parser.parse_args(argv)

    from extractor360.ui.main_window import MainWindow

    app = QApplication.instance() or QApplication([])

    with tempfile.TemporaryDirectory() as tmp:
        demo = Path(tmp) / "demo_360_scene.jpg"
        make_demo_equirect(demo)

        window = MainWindow()
        window.resize(args.width, args.height)
        window.show()

        window.add_job(str(demo))

        # Show the Settings page: the default "Videos" page hides the settings
        # panel, and the settings are what the tool is actually about.
        window.sidebar.setActivePage("settings")
        window.sidebar.page_changed.emit("settings")

        # Let the thumbnail + the (debounced) preview render before grabbing.
        pump(app, 1800)

        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        if not window.grab().save(str(output)):
            print(f"error: could not write {output}", file=sys.stderr)
            return 1

    print(f"Wrote {output} ({output.stat().st_size / 1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
