"""Source ranges must survive projects and select real decoded export frames."""
import json
from pathlib import Path

import cv2
import numpy as np
import pytest

from extractor360.core.job import Job
from extractor360.core.processor import ProcessingWorker
from extractor360.core.project import Project, read_project, relink_source, source_identity, write_project
from extractor360.core.preflight import uniform_frames
from extractor360.core.selection import FrameSelection
from extractor360.core.settings_manager import build_settings
from extractor360.core.storage import estimate_output
from extractor360.core.validation import validate_settings


@pytest.fixture
def video(tmp_path):
    path = tmp_path / 'source.avi'
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*'MJPG'), 10, (64, 32))
    assert writer.isOpened()
    for i in range(10):
        writer.write(np.full((32, 64, 3), i * 20, np.uint8))
    writer.release()
    return path


@pytest.mark.parametrize('unit,interval', [('Frames', 2), ('Seconds', .2)])
def test_export_preserves_source_cadence_timestamps_and_all_faces(video, tmp_path, unit, interval):
    job = Job(str(video), settings={'resolution': 32, 'layout_mode': 'cube', 'exif_intrinsics': False,
                                   'interval_unit': unit, 'interval_value': interval,
                                   'included_frame_ranges': [[1, 2], [4, 7]], 'excluded_frames': [4]})
    worker = ProcessingWorker([job])
    worker.run()
    assert worker.error_count == 0
    records = [json.loads(line) for line in Path(job.result['output_dir'], 'images.jsonl').read_text().splitlines()]
    assert {r['frame'] for r in records} == {2, 6}
    assert len(records) == 12
    assert all(abs(r['timestamp_seconds'] - r['frame'] / 10) < .01 for r in records)
    assert job.result['extraction']['frames_excluded'] == 1
    assert job.result['extraction']['frames_outside_ranges'] == 1
    assert job.result['frame_count_check']['decoded'] == 8
    assert job.result['frame_count_check']['scope'] == 'selected end'
    assert json.loads(Path(job.result['output_dir'], 'manifest.json').read_text())['settings']['included_frame_ranges'] == [[1, 2], [4, 7]]


@pytest.mark.parametrize('ranges', [None, '0-8', [[True, 5]], [[-1, 3]], [[5, 3]], [[1.5, 4]], [[0, 2**31]], [[0]]])
def test_invalid_ranges_fail_settings_validation(ranges):
    with pytest.raises(ValueError, match='included_frame_ranges'):
        validate_settings({'included_frame_ranges': ranges})


def test_ranges_merge_and_keep_individual_exclusions():
    settings = validate_settings({'included_frame_ranges': [[7, 9], [1, 3], [3, 6]], 'excluded_frames': [4]})
    assert settings['included_frame_ranges'] == [[1, 9]]
    assert FrameSelection(settings['included_frame_ranges']).sampled_count(10, 2, [4]) == 3


def test_outside_source_and_still_image_fail_before_output(video, tmp_path):
    image = tmp_path / 'still.png'
    assert cv2.imwrite(str(image), np.zeros((32, 64, 3), np.uint8))
    for source, ranges in [(video, [[0, 10]]), (image, [[0, 0]])]:
        output = tmp_path / ('absent-' + source.stem)
        job = Job(str(source), settings={'included_frame_ranges': ranges, 'custom_output_dir': str(output)})
        worker = ProcessingWorker([job])
        worker.run()
        assert worker.error_count == 1 and 'Extraction ranges' in job.result['error']
        assert not output.exists()


def test_range_end_does_not_hide_an_early_decoder_failure(video, monkeypatch):
    real_capture = cv2.VideoCapture
    class TruncatedCapture:
        def __init__(self, *args):
            self.cap = real_capture(*args)
        def __getattr__(self, name):
            return getattr(self.cap, name)
        def grab(self):
            return self.cap.get(cv2.CAP_PROP_POS_FRAMES) < 3 and self.cap.grab()
    monkeypatch.setattr(cv2, 'VideoCapture', TruncatedCapture)
    job = Job(str(video), settings={'resolution': 32, 'included_frame_ranges': [[1, 7]], 'exif_intrinsics': False})
    worker = ProcessingWorker([job])
    worker.run()
    assert worker.error_count == 1 and 'Decoder stopped at frame 3, expected 8' in job.result['error']


def test_roundtrip_relocation_replacement_and_estimate(video, tmp_path):
    job = Job(str(video), settings=validate_settings({'included_frame_ranges': [[1, 7]], 'excluded_frames': [4],
              'interval_unit': 'Frames', 'interval_value': 2}), source_identity=source_identity(str(video)))
    document = tmp_path / 'selection.360proj'
    write_project(document, Project(jobs=[job]))
    restored = read_project(document)[0].jobs[0]
    assert restored.settings['included_frame_ranges'] == [[1, 7]]
    estimate = estimate_output(restored.settings, 32, 32, 10, 10, False, ['Left', 'Right'])
    assert estimate['captures_estimated'] == 2 and estimate['images_estimated'] == 4
    moved = tmp_path / 'moved.avi'
    video.rename(moved)
    relink_source(restored, str(moved))
    assert restored.settings['included_frame_ranges'] == [[1, 7]]
    moved.write_bytes(b'replacement')
    relink_source(restored, str(moved))
    assert restored.settings['included_frame_ranges'] == [] and restored.settings['excluded_frames'] == []


def test_preflight_intersects_ranges_window_and_exclusions_without_expanding_video():
    assert uniform_frames(100, [2], 3, [0, 9], [[1, 3], [7, 12]]) == [1, 7, 9]
    assert uniform_frames(2_000_000_000, [], 3, included_ranges=[[1, 3], [1_999_999_997, 1_999_999_999]]) == [1, 3, 1_999_999_999]
    with pytest.raises(ValueError, match='three'):
        uniform_frames(100, [], 3, [0, 9], [[20, 30]])


def test_cli_ranges_override_config(monkeypatch):
    from extractor360.main import parse_arguments
    monkeypatch.setattr('sys.argv', ['360-extractor', '--input', 'source.mp4', '--frame-range', '0', '82', '--frame-range', '100', '150'])
    args = parse_arguments()
    settings = build_settings(args, {'included_frame_ranges': [[2, 3]]})
    assert settings['included_frame_ranges'] == [[0, 82], [100, 150]]
