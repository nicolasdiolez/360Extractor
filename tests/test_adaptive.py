"""Adaptive extraction: optical flow, real video, and confirmed references."""
import json
from pathlib import Path

import cv2
import numpy as np
import pytest

from extractor360.core.job import Job
from extractor360.core.motion_detector import MotionDetector
from extractor360.core.processor import ProcessingWorker
from extractor360.core.telemetry import TelemetryHandler


def _texture():
    # Dense, deterministic features survive a small MJPG encode. A full-frame
    # translation avoids a score depending on one tiny rectangle's area.
    noise = np.random.default_rng(41).integers(0, 256, (64, 128, 3), dtype=np.uint8)
    return cv2.GaussianBlur(noise, (3, 3), 0)


def _index(job):
    output = Path(job.result['output_dir'])
    records = [json.loads(line) for line in (output / 'images.jsonl').read_text(encoding='utf-8').splitlines()]
    assert len(records) == len({record['image'] for record in records})
    for record in records:
        assert (output / record['image']).is_file()
        assert cv2.imread(str(output / record['image'])) is not None
    manifest = json.loads((output / 'manifest.json').read_text(encoding='utf-8'))
    assert manifest['extraction'] == job.result['extraction']
    return records


def test_motion_detector_static_and_translated_texture():
    detector = MotionDetector()
    still = _texture()
    moved = np.roll(still, 3, axis=1)
    static_score = detector.calculate_motion_score(still, still.copy())
    moved_score = detector.calculate_motion_score(still, moved)
    assert static_score < .01
    assert moved_score > 1
    assert moved_score > static_score + 1


def test_adaptive_video_skips_static_frames_then_exports_movement(tmp_path):
    video = tmp_path / 'static_then_motion.avi'
    writer = cv2.VideoWriter(str(video), cv2.VideoWriter_fourcc(*'MJPG'), 10, (128, 64))
    if not writer.isOpened():
        pytest.skip('OpenCV cannot encode the tiny MJPG fixture on this platform')
    still = _texture()
    try:
        for shift in (0, 0, 0, 3, 6, 9):
            writer.write(np.roll(still, shift, axis=1))
    finally:
        writer.release()
    settings = {
        'is_360': False, 'adaptive_mode': True, 'adaptive_threshold': .5,
        'interval_unit': 'Frames', 'interval_value': 1, 'output_format': 'png',
        'exif_intrinsics': False,
    }
    job = Job(str(video), settings=settings)
    worker = ProcessingWorker([job])
    worker.run()
    assert worker.error_count == 0
    assert job.status == 'Done'
    assert job.result['status'] == 'completed'
    records = _index(job)
    assert [record['frame'] for record in records] == [0, 3, 4, 5]
    assert {record['camera'] for record in records} == {'flat'}
    counts = job.result['extraction']
    assert counts['frames_processed'] == 4
    assert counts['frames_skipped_motion'] == 2
    assert counts['images_written'] == len(records) == 4
    assert counts['views_skipped_ai'] == counts['views_skipped_blur'] == counts['writes_failed'] == 0


class _Capture:
    def __init__(self, values):
        self.frames = [np.full((16, 32, 3), value, np.uint8) for value in values]
        self.position = -1
        self.released = False

    def isOpened(self):
        return True

    def get(self, prop):
        return {
            cv2.CAP_PROP_FPS: 10,
            cv2.CAP_PROP_FRAME_COUNT: len(self.frames),
            cv2.CAP_PROP_FRAME_WIDTH: 32,
            cv2.CAP_PROP_FRAME_HEIGHT: 16,
            cv2.CAP_PROP_POS_MSEC: max(0, self.position) * 100,
        }[prop]

    def grab(self):
        self.position += 1
        return self.position < len(self.frames)

    def retrieve(self):
        return True, self.frames[self.position].copy()

    def release(self):
        self.released = True


@pytest.mark.parametrize('values,rejected_value,partial,expected_pairs,expected_frames,skipped_motion,skipped_ai', [
    ([10, 11, 30], 10, False, [(11, 30)], [1, 1, 2, 2], 0, 2),
    ([0, 20, 21], 20, False, [(0, 20), (0, 21)], [0, 0, 2, 2], 0, 2),
    ([0, 20, 21], 20, True, [(0, 20), (20, 21)], [0, 0, 1], 1, 1),
], ids=['first-frame-all-rejected', 'later-frame-all-rejected', 'one-confirmed-view-is-enough'])
def test_motion_reference_advances_only_after_confirmed_view(
    tmp_path, monkeypatch, values, rejected_value, partial,
    expected_pairs, expected_frames, skipped_motion, skipped_ai,
):
    # Controlled decoded values and motion scores isolate the reference policy
    # from codecs, optical flow and model inference; real writes remain active.
    source = tmp_path / 'controlled.mp4'
    source.touch()
    capture = _Capture(values)
    monkeypatch.setattr(cv2, 'VideoCapture', lambda path: capture)

    def metadata(self, path, include_gps=True):
        self.metadata = {'status': 'disabled', 'frame_count': len(values), 'frame_count_source': 'container_nb_frames'}
        self.has_gps = False

    monkeypatch.setattr(TelemetryHandler, 'extract_metadata', metadata)
    job = Job(str(source), settings={
        'resolution': 16, 'camera_count': 2, 'layout_mode': 'ring',
        'adaptive_mode': True, 'adaptive_threshold': 5,
        'interval_unit': 'Frames', 'interval_value': 1,
        'ai_mode': 'Skip Frame', 'output_format': 'png', 'exif_intrinsics': False,
    })
    worker = ProcessingWorker([job])
    pairs = []

    def score(previous, current):
        previous_value, current_value = int(previous[0, 0, 0]), int(current[0, 0, 0])
        pairs.append((previous_value, current_value))
        # The previous reference must already have at least one indexed image.
        index_file = Path(job.result['output_dir']) / 'images.jsonl'
        confirmed = [json.loads(line) for line in index_file.read_text(encoding='utf-8').splitlines()]
        assert any(values[record['frame']] == previous_value for record in confirmed)
        return abs(current_value - previous_value)

    monkeypatch.setattr(worker.motion_detector, 'calculate_motion_score', score)

    class AI:
        def process_batch(self, images, **kwargs):
            assert kwargs['mode'] == 'skip_frame'
            return [
                (None, True) if int(image[0, 0, 0]) == rejected_value and (not partial or index == 0)
                else (image, False)
                for index, image in enumerate(images)
            ]

    def ensure_model(name):
        worker.ai_service = AI()
        return worker.ai_service

    monkeypatch.setattr(worker, '_ensure_ai_service', ensure_model)
    worker.run()
    assert worker.error_count == 0
    assert job.status == 'Done'
    assert capture.released
    assert pairs == expected_pairs
    records = _index(job)
    assert [record['frame'] for record in records] == expected_frames
    counts = job.result['extraction']
    assert counts['images_written'] == len(records)
    assert counts['frames_skipped_motion'] == skipped_motion
    assert counts['frames_processed'] == len(values) - skipped_motion
    assert counts['views_skipped_ai'] == skipped_ai
    assert counts['views_skipped_blur'] == counts['writes_failed'] == 0
