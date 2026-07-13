"""
End-to-end test of the (Qt-free) processing core on a synthetic 360 video.

Runs the real ProcessingWorker on a tiny generated equirectangular clip and
checks the produced images, nadir mask and manifest. This is the CI guard for
the extraction pipeline itself, which previously could not even be imported in
CI because the core depended on PySide6 (and, transitively, torch).
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

import cv2
import numpy as np

from extractor360.core.job import Job
from extractor360.core.processor import ProcessingWorker
from extractor360.core.settings_manager import SettingsManager

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _write_video(path, frames=30, w=256, h=128, fps=10):
    """Small synthetic equirect-shaped (2:1) video; returns True on success."""
    vw = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*'mp4v'), fps, (w, h))
    if not vw.isOpened():
        return False
    rng = np.random.default_rng(3)
    base = rng.integers(0, 255, (h, w, 3), dtype=np.uint8)
    for i in range(frames):
        vw.write(np.roll(base, i * 4, axis=1))
    vw.release()
    return os.path.getsize(path) > 0


class TestCoreIsHeadless(unittest.TestCase):
    """The processing core must import without Qt and without the AI stack."""

    def test_core_imports_without_qt_or_torch(self):
        code = (
            "import sys\n"
            "import extractor360.core.processor\n"
            "import extractor360.core.analyzer\n"
            "import extractor360.main\n"
            "banned = [m for m in ('PySide6', 'torch', 'ultralytics') if m in sys.modules]\n"
            "sys.exit(1 if banned else 0)\n"
        )
        env = dict(os.environ, PYTHONPATH=os.path.join(REPO_ROOT, 'src'))
        result = subprocess.run([sys.executable, '-c', code], env=env, cwd=REPO_ROOT)
        self.assertEqual(
            result.returncode, 0,
            "importing the core/CLI pulled in PySide6 or torch — it must stay headless"
        )


class TestProcessorEndToEnd(unittest.TestCase):
    def test_cube_extraction_with_nadir_and_manifest(self):
        tmp = tempfile.mkdtemp()
        video = os.path.join(tmp, 'pano.mp4')
        if not _write_video(video):
            self.skipTest("OpenCV build cannot encode mp4v on this platform")

        settings = SettingsManager.DEFAULT_SETTINGS.copy()
        settings.update({
            'layout_mode': 'cube',
            'resolution': 64,
            'interval_value': 1.0,
            'interval_unit': 'Seconds',
            'nadir_mask_enabled': True,
            'nadir_mask_radius': 30.0,
            'custom_output_dir': tmp,
            'active_cameras': None,
        })
        job = Job(file_path=video, settings=settings)

        events = []
        worker = ProcessingWorker([job])
        worker.job_started.connect(lambda i: events.append(('started', i)))
        worker.job_finished.connect(lambda i: events.append(('finished', i)))
        worker.finished.connect(lambda: events.append(('all', None)))
        worker.run()

        self.assertEqual(worker.error_count, 0)
        self.assertIn(('started', 0), events)
        self.assertIn(('finished', 0), events)
        self.assertIn(('all', None), events)

        out = os.path.join(tmp, 'pano_processed')
        files = sorted(os.listdir(out))
        jpgs = [f for f in files if f.endswith('.jpg')]
        masks = [f for f in files if f.endswith('.mask.png')]

        # 3 extraction points (frames 0/10/20 at 10 fps, 1 s interval)
        # x 6 cube faces, plus one nadir mask per Down view.
        self.assertEqual(len(jpgs), 18)
        self.assertEqual(len(masks), 3)
        self.assertIn('manifest.json', files)

        with open(os.path.join(out, 'manifest.json'), encoding='utf-8') as fh:
            manifest = json.load(fh)
        self.assertEqual(manifest['extraction']['frames_processed'], 3)
        self.assertEqual(manifest['extraction']['images_written'], 18)
        self.assertEqual(manifest['extraction']['interval_frames'], 10)

        # The nadir disc: ignore (0) at the centre, keep (255) in the corner.
        mask = cv2.imread(os.path.join(out, masks[0]), cv2.IMREAD_GRAYSCALE)
        self.assertEqual(mask[mask.shape[0] // 2, mask.shape[1] // 2], 0)
        self.assertEqual(mask[2, 2], 255)

    def test_flat_image_passthrough(self):
        """A flat (non-360) image goes through the full pipeline untouched."""
        tmp = tempfile.mkdtemp()
        src = os.path.join(tmp, 'photo.jpg')
        img = np.random.default_rng(1).integers(0, 255, (40, 60, 3), dtype=np.uint8)
        cv2.imwrite(src, img)

        settings = SettingsManager.DEFAULT_SETTINGS.copy()
        settings.update({
            'is_360': False,
            'custom_output_dir': tmp,
            'active_cameras': None,
        })
        worker = ProcessingWorker([Job(file_path=src, settings=settings)])
        worker.run()

        self.assertEqual(worker.error_count, 0)
        out_files = os.listdir(os.path.join(tmp, 'photo_processed'))
        self.assertIn('photo_frame000000_flat.jpg', out_files)


if __name__ == '__main__':
    unittest.main(verbosity=2)
