import json
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np

from extractor360.core.job import Job
from extractor360.core.processor import ProcessingWorker
from extractor360.core import storage
from extractor360.core.validation import validate_settings


def test_flat_native_dimensions_and_scoped_masks():
    settings = validate_settings({'is_360': False, 'resolution': 64, 'ai_mode': 'Generate Mask',
                                  'ai_mask_cameras': ['Down']})
    estimate = storage.estimate_output(settings, 1920, 1080, 101, 10, False, ['flat'])
    assert estimate['images_estimated'] == estimate['masks_estimated'] == 11
    assert (estimate['output_width'], estimate['output_height']) == (1920, 1080)
    cube = validate_settings({'layout_mode': 'cube', 'ai_mode': 'Generate Mask', 'ai_mask_cameras': ['Down']})
    estimate = storage.estimate_output(cube, 64, 64, 1, 0, True, ['Front', 'Down'])
    assert estimate['images_estimated'] == 2 and estimate['masks_estimated'] == 1


def test_unknown_duration_does_not_invent_fps():
    estimate = storage.estimate_output(validate_settings({}), 64, 64, 100, 0, False, ['Front'])
    assert estimate['images_estimated'] is None and estimate['bytes_high'] is None
    assert estimate['capture_budget_bytes'] > 0


def test_low_disk_refuses_before_destination_and_model(tmp_path, monkeypatch):
    source = tmp_path / 'pano.png'
    cv2.imwrite(str(source), np.zeros((32, 64, 3), np.uint8))
    original = source.read_bytes()
    target = tmp_path / 'new-parent' / 'out'
    monkeypatch.setattr(storage.shutil, 'disk_usage', lambda path: SimpleNamespace(free=1))
    calls = []
    monkeypatch.setattr(ProcessingWorker, '_ensure_ai_service', lambda *args: calls.append(args))
    job = Job(str(source), settings={'resolution': 32, 'ai_mode': 'Generate Mask', 'custom_output_dir': str(target)})
    worker = ProcessingWorker([job])
    worker.run()
    assert worker.error_count == 1 and job.result['status'] == 'failed'
    assert 'Insufficient disk space' in job.result['error']
    assert not target.parent.exists() and not calls
    assert source.read_bytes() == original


def test_disk_drop_preserves_confirmed_capture_and_failed_manifest(tmp_path, monkeypatch):
    source = tmp_path / 'sequence.mp4'
    source.write_bytes(b'fixture')
    class Capture:
        index = -1
        def isOpened(self): return True
        def get(self, key):
            return {cv2.CAP_PROP_FPS: 1, cv2.CAP_PROP_FRAME_COUNT: 3,
                    cv2.CAP_PROP_FRAME_WIDTH: 32, cv2.CAP_PROP_FRAME_HEIGHT: 32,
                    cv2.CAP_PROP_POS_MSEC: max(0, self.index) * 1000}.get(key, 0)
        def grab(self):
            self.index += 1
            return self.index < 3
        def retrieve(self): return True, np.full((32, 32, 3), 120, np.uint8)
        def release(self): pass
    monkeypatch.setattr(cv2, 'VideoCapture', lambda path: Capture())
    free = iter([10**10, 10**10, 1])
    monkeypatch.setattr(storage.shutil, 'disk_usage', lambda path: SimpleNamespace(free=next(free)))
    job = Job(str(source), settings={'is_360': False, 'exif_intrinsics': False})
    worker = ProcessingWorker([job])
    worker.run()
    out = Path(job.result['output_dir'])
    manifest = json.loads((out / 'manifest.json').read_text())
    records = [json.loads(line) for line in (out / 'images.jsonl').read_text().splitlines()]
    assert worker.error_count == 1 and manifest['status'] == 'failed'
    assert len(records) == manifest['extraction']['images_written'] == 1
    assert (out / records[0]['image']).is_file()
    assert len(list(out.glob('*.jpg'))) == 1
