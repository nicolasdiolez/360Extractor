"""A dense export must retain the frozen reference, its pixels and its masks."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys

import cv2
import numpy as np
import pytest

from extractor360.core.capture_plan import baseline_from_window, densify_frames, normalize_capture_plan
from extractor360.core.job import Job
from extractor360.core.processor import ProcessingWorker
from extractor360.core.project import Project, read_project, relink_source, source_identity, write_project
from extractor360.core.storage import estimate_output
from extractor360.core.validation import validate_settings


BASELINE = [0, 5, 11, 16, 22, 27, 33, 38, 44, 49, 55, 60, 66, 71, 77, 82]
ADDED = [2, 8, 13, 19, 24, 30, 35, 41, 46, 52, 57, 63, 68, 74, 79]


@pytest.fixture
def video(tmp_path):
    path = tmp_path / 'staircase-window.avi'
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*'MJPG'), 25, (64, 32))
    assert writer.isOpened()
    for frame in range(83):
        pixels = np.full((32, 64, 3), frame * 3, np.uint8)
        pixels[:, 20:40, 1] = 80
        writer.write(pixels)
    writer.release()
    return path


def settings(mode='baseline', **changes):
    return validate_settings({'resolution': 32, 'layout_mode': 'cube', 'exif_intrinsics': False,
                              'nadir_mask_enabled': True, 'interval_unit': 'Frames', 'interval_value': 97,
                              'capture_plan': {'mode': mode, 'baseline_frames': BASELINE}, **changes})


def records(job):
    root = Path(job.result['output_dir'])
    return root, [json.loads(line) for line in (root / 'images.jsonl').read_text().splitlines()]


def test_plan_reproduces_historical_staircase_pair():
    measurements = json.loads((Path(__file__).parents[1] / 'docs/implementation-2026-11-01/sampling-results.json').read_text())
    assert baseline_from_window(0, 82) == BASELINE == measurements['sampling']['control16']['frames']
    assert densify_frames(BASELINE) == sorted(BASELINE + ADDED) == measurements['sampling']['trial31']['frames']
    config = json.loads((Path(__file__).parents[1] / 'docs/implementation-2026-11-01/staircase-capture-plan.json').read_text())
    assert validate_settings(config)['capture_plan'] == {'mode': 'baseline', 'baseline_frames': BASELINE}
    assert baseline_from_window(2147483565, 2147483647) == [2147483565 + f for f in BASELINE]
    assert BASELINE == [0, 5, 11, 16, 22, 27, 33, 38, 44, 49, 55, 60, 66, 71, 77, 82]


@pytest.mark.parametrize('profile', ['realityscan', 'postshot'])
@pytest.mark.parametrize('unit', ['Frames', 'Seconds'])
def test_paired_exports_preserve_reference_bytes_and_record_confirmed_frames(video, profile, unit):
    original = video.read_bytes()
    jobs = []
    for mode, count in [('baseline', 16), ('densified', 31)]:
        job = Job(str(video), settings=settings(mode, mask_profile=profile, interval_unit=unit))
        estimate = estimate_output(job.settings, 32, 32, 83, 25, False, ['Front', 'Right', 'Back', 'Left', 'Up', 'Down'])
        assert estimate['captures_estimated'] == count and estimate['masks_estimated'] == count
        worker = ProcessingWorker([job])
        worker.run()
        assert worker.error_count == 0 and job.result['status'] == 'completed'
        root, index = records(job)
        expected = BASELINE if count == 16 else sorted(BASELINE + ADDED)
        assert len(index) == count * 6 and len(list(root.glob('*.png'))) == count
        assert sorted({r['frame'] for r in index}) == expected
        assert all(r['timestamp_seconds'] == pytest.approx(r['frame'] / 25) for r in index)
        assert all(r['sampling_role'] == ('baseline' if r['frame'] in BASELINE else 'inserted') for r in index)
        manifest = json.loads((root / 'manifest.json').read_text())
        assert manifest['capture_sampling']['requested_frames'] == manifest['capture_sampling']['confirmed_frames'] == expected
        assert manifest['capture_sampling']['added_frames'] == ([] if count == 16 else ADDED)
        jobs.append(job)
    control_root, control = records(jobs[0])
    dense_root, dense = records(jobs[1])
    dense_lookup = {(r['frame'], r['camera']): r for r in dense}
    for row in control:
        other = dense_lookup[row['frame'], row['camera']]
        for field in ('image', 'mask'):
            if row[field]:
                assert (control_root / row[field]).read_bytes() == (dense_root / other[field]).read_bytes()
    assert jobs[0].result['capture_sampling']['comparison_signature'] == jobs[1].result['capture_sampling']['comparison_signature']
    assert video.read_bytes() == original


@pytest.mark.parametrize('baseline', [[], BASELINE[:-1], BASELINE + [83], [True] + BASELINE[1:],
                                      [0.0] + BASELINE[1:], [0, 0] + BASELINE[2:], BASELINE[::-1]])
def test_invalid_reference_is_rejected(baseline):
    with pytest.raises(ValueError, match='16 unique'):
        normalize_capture_plan({'mode': 'baseline', 'baseline_frames': baseline})


def test_no_available_midpoint_never_drops_or_moves_reference():
    baseline = list(range(16))
    assert normalize_capture_plan({'mode': 'baseline', 'baseline_frames': baseline})['baseline_frames'] == baseline
    with pytest.raises(ValueError, match='every reference gap'):
        densify_frames(baseline)
    with pytest.raises(ValueError, match='at least 16'):
        baseline_from_window(0, 14)


@pytest.mark.parametrize('changes', [{'excluded_frames': [2]}, {'included_frame_ranges': [[3, 82]]},
                                    {'blur_filter_enabled': True}, {'adaptive_mode': True}, {'ai_mode': 'Skip Frame'}])
def test_conflicts_fail_before_writing(video, tmp_path, changes):
    target = tmp_path / 'absent'
    job = Job(str(video), settings={**settings('densified'), **changes, 'custom_output_dir': str(target)})
    worker = ProcessingWorker([job])
    worker.run()
    assert worker.error_count == 1 and 'Capture plan' in job.result['error']
    assert not target.exists()


def test_out_of_bounds_and_images_fail_before_writing(video, tmp_path):
    image = tmp_path / 'still.png'
    assert cv2.imwrite(str(image), np.zeros((32, 64, 3), np.uint8))
    for source in (video, image):
        target = tmp_path / source.stem
        plan = {'mode': 'densified', 'baseline_frames': [f + 1 for f in BASELINE]}
        job = Job(str(source), settings=settings(capture_plan=plan, custom_output_dir=str(target)))
        worker = ProcessingWorker([job])
        worker.run()
        assert worker.error_count == 1 and 'known length' in job.result['error']
        assert not target.exists()


def test_project_roundtrip_relocation_and_replacement(video, tmp_path):
    job = Job(str(video), settings=settings('densified'), source_identity=source_identity(str(video)))
    project = tmp_path / 'pair.360proj'
    write_project(project, Project(jobs=[job]))
    restored = read_project(project)[0].jobs[0]
    assert restored.settings['capture_plan'] == job.settings['capture_plan']
    relocated = tmp_path / 'moved.avi'
    video.rename(relocated)
    relink_source(restored, str(relocated))
    assert restored.settings['capture_plan'] == job.settings['capture_plan']
    relocated.write_bytes(b'replaced source')
    relink_source(restored, str(relocated))
    assert restored.settings['capture_plan'] is None


def test_cancellation_keeps_partial_plan_honest(video, monkeypatch):
    job = Job(str(video), settings=settings('densified'))
    worker = ProcessingWorker([job])
    drain = worker._drain_writes
    def stop_after_write(*args):
        accepted = drain(*args)
        worker.stop()
        return accepted
    monkeypatch.setattr(worker, '_drain_writes', stop_after_write)
    worker.run()
    assert worker.error_count == 0 and job.result['status'] == 'cancelled'
    assert job.result['capture_sampling']['confirmed_frames'] == [0]
    assert len(job.result['capture_sampling']['requested_frames']) == 31


def test_early_decoder_failure_does_not_claim_complete_plan(video, monkeypatch):
    real_capture = cv2.VideoCapture
    class Truncated:
        def __init__(self, path): self.cap = real_capture(path)
        def __getattr__(self, name): return getattr(self.cap, name)
        def grab(self): return self.cap.get(cv2.CAP_PROP_POS_FRAMES) < 40 and self.cap.grab()
    monkeypatch.setattr(cv2, 'VideoCapture', Truncated)
    job = Job(str(video), settings=settings('densified'))
    worker = ProcessingWorker([job])
    worker.run()
    assert worker.error_count == 1 and job.result['status'] == 'failed'
    assert job.result['capture_sampling']['confirmed_frames'] == [f for f in sorted(BASELINE + ADDED) if f < 40]


def test_partial_view_write_never_confirms_a_whole_capture(video, monkeypatch):
    from extractor360.utils.file_manager import FileManager
    write_pair = FileManager.write_pair
    def fail_down(path, *args):
        if 'Down' in str(path):
            raise OSError('Simulated Down write failure')
        return write_pair(path, *args)
    monkeypatch.setattr(FileManager, 'write_pair', fail_down)
    job = Job(str(video), settings=settings('densified'))
    worker = ProcessingWorker([job])
    worker.run()
    assert worker.error_count == 1 and job.result['status'] == 'failed'
    assert job.result['capture_sampling']['confirmed_frames'] == []
    assert job.result['extraction']['images_written'] == 5


def test_cli_creates_pair_from_one_config_and_frozen_reference(video, tmp_path):
    config = tmp_path / 'settings.json'
    common = settings(mask_profile='postshot')
    config.write_text(json.dumps(common))
    signatures = []
    for mode, count in [('baseline', 16), ('densified', 31)]:
        output = tmp_path / mode
        result = subprocess.run([sys.executable, '-m', 'extractor360', '--config', str(config), '--input', str(video),
                                 '--output', str(output), '--capture-mode', mode], capture_output=True, text=True,
                                env={**os.environ, 'PYTHONPATH': str(Path(__file__).parents[1] / 'src')})
        assert result.returncode == 0, result.stderr
        manifest = json.loads(next(output.rglob('manifest.json')).read_text())
        assert manifest['extraction']['images_written'] == count * 6
        signatures.append(manifest['capture_sampling']['comparison_signature'])
    assert signatures[0] == signatures[1]
    assert json.loads(config.read_text()) == common


def test_cli_window_and_explicit_reference_freeze_same_plan(monkeypatch):
    from extractor360.main import parse_arguments
    from extractor360.core.settings_manager import build_settings
    for args in [['--capture-window', '0', '82'], ['--capture-baseline', *map(str, BASELINE)]]:
        monkeypatch.setattr(sys, 'argv', ['360extractor', '--capture-mode', 'densified', *args])
        config = settings()
        before = copy.deepcopy(config)
        result = build_settings(parse_arguments(), config)
        assert result['capture_plan'] == {'mode': 'densified', 'baseline_frames': BASELINE}
        assert config == before


def test_source_and_export_diagnostics_keep_their_bound_with_a_dense_plan(video, tmp_path, monkeypatch):
    from extractor360.core import alignment, preflight
    monkeypatch.setattr(preflight.shutil, 'which', lambda _: sys.executable)
    monkeypatch.setattr(alignment.AlignmentRunner, '_command', lambda *args: None)
    job = Job(str(video), settings=settings('densified', mask_profile='colmap', export_colmap=True),
              source_identity=source_identity(str(video)), source_check_required=True)
    before = copy.deepcopy(job.settings)
    report = alignment.AlignmentRunner().run_source(job, tmp_path / 'source-diagnostic', 16)
    assert report['requested_frames'] == BASELINE and len(report['sampled_frames']) == 16
    assert report['fingerprint'] == alignment.fingerprint(job) and job.settings == before
    worker = ProcessingWorker([job])
    worker.run()
    assert worker.error_count == 0
    report = alignment.AlignmentRunner().run(job, tmp_path / 'export-diagnostic', 16)
    assert report['sampled_frames'] == BASELINE
    with pytest.raises(ValueError, match='16'):
        alignment.AlignmentRunner().run_source(job, tmp_path / 'too-many', 31)
