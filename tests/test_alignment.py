"""Selection semantics, honest model grouping and bounded subprocess lifecycle."""
import copy
import json
import os
from pathlib import Path
import sys
import threading
import time

import cv2
import numpy as np
import pytest

from extractor360.core import alignment
from extractor360.core.job import Job
from extractor360.core.processor import ProcessingWorker
from extractor360.core.project import Project, read_project, source_identity, write_project, relink_source
from extractor360.core.validation import validate_settings


@pytest.fixture
def exported(tmp_path):
    source = tmp_path / 'source.avi'
    writer = cv2.VideoWriter(str(source), cv2.VideoWriter_fourcc(*'MJPG'), 10, (64, 32))
    assert writer.isOpened()
    for value in range(8):
        writer.write(np.full((32, 64, 3), value * 25, np.uint8))
    writer.release()
    job = Job(str(source), settings={'resolution': 32, 'layout_mode': 'cube', 'interval_unit': 'Frames',
                                    'interval_value': 2, 'export_colmap': True, 'mask_profile': 'colmap',
                                    'exif_intrinsics': False}, source_identity=source_identity(str(source)), source_check_required=True)
    worker = ProcessingWorker([job])
    worker.run()
    assert worker.error_count == 0
    return job


@pytest.mark.parametrize('unit,interval', [('Frames', 2), ('Seconds', .2)])
def test_exclusions_preserve_sampling_cadence_and_all_views(exported, unit, interval):
    exported.settings.update(excluded_frames=[2], interval_unit=unit, interval_value=interval)
    worker = ProcessingWorker([exported])
    worker.run()
    assert worker.error_count == 0
    records = [json.loads(line) for line in Path(exported.result['output_dir'], 'images.jsonl').read_text().splitlines()]
    assert {r['frame'] for r in records} == {0, 4, 6}
    assert len(records) == 18
    assert all(abs(r['timestamp_seconds'] - r['frame'] / 10) < .01 for r in records)
    assert exported.result['extraction']['frames_excluded'] == 1


@pytest.mark.parametrize('value', [None, [True], [-1], [1.5], '1,2'])
def test_invalid_selection_is_rejected(value):
    with pytest.raises(ValueError, match='excluded_frames'):
        validate_settings({'excluded_frames': value})


def test_selection_survives_project_but_not_replacement_source(exported, tmp_path):
    exported.settings['excluded_frames'] = [2, 4]
    exported.diagnostic_settings = {'mode': 'source', 'resolution': 1024, 'maximum': 3, 'frame_range': [0, 6]}
    target = tmp_path / 'decision.360proj'
    write_project(target, Project(jobs=[exported]))
    reopened, _ = read_project(target)
    assert reopened.jobs[0].settings['excluded_frames'] == [2, 4]
    assert reopened.jobs[0].diagnostic_settings == exported.diagnostic_settings
    replacement = tmp_path / 'other.png'
    cv2.imwrite(str(replacement), np.zeros((32, 64, 3), np.uint8))
    relink_source(reopened.jobs[0], str(replacement))
    assert not reopened.jobs[0].settings.get('excluded_frames')
    assert reopened.jobs[0].diagnostic_settings['frame_range'] is None
    assert reopened.jobs[0].diagnostic_settings['resolution'] == 1024


def test_preflight_refuses_stale_and_partial_export(exported, tmp_path):
    assert len(alignment.load_export(exported)[-1]) == 4
    exported.settings['excluded_frames'] = [2]
    alignment.load_export(exported)  # Selection may be changed without rewriting pixels.
    exported.settings['fov'] = 89
    with pytest.raises(ValueError, match='Settings changed'):
        alignment.load_export(exported)
    exported.settings['fov'] = 90
    manifest = Path(exported.result['output_dir'], 'manifest.json')
    data = json.loads(manifest.read_text())
    data['status'] = 'cancelled'
    manifest.write_text(json.dumps(data))
    with pytest.raises(ValueError, match='incomplete'):
        alignment.AlignmentRunner().run(exported, tmp_path / 'refused')
    assert not (tmp_path / 'refused').exists()


def test_sampling_and_overlapping_models_do_not_invent_separate_groups():
    frames = {n: {'frame': n, 'images': [f'Front/frame{n}.jpg', f'Back/frame{n}.jpg']} for n in range(7)}
    sampled = alignment.sample_frames(frames, [3], 5)
    assert sampled == [0, 1, 2, 5, 6]
    models = {'0': {'Front/frame0.jpg', 'Back/frame0.jpg', 'Front/frame1.jpg'},
              '1': {'Back/frame1.jpg', 'Front/frame2.jpg'}, '2': {'Front/frame5.jpg'}}
    report = alignment.summarize(frames, sampled, {3}, models)
    assert report['registered_captures'] == 4 and report['unregistered_captures'] == 1
    assert report['groups'] == [{'models': ['1', '0'], 'frames': [0, 1, 2]}, {'models': ['2'], 'frames': [5]}]
    assert report['captures'][3]['state'] == 'excluded'
    assert report['captures'][4]['state'] == 'not_sampled'
    assert report['captures'][6]['state'] == 'unregistered'
    with pytest.raises(ValueError, match='three'):
        alignment.sample_frames([0, 1, 2], [1], 8)


def test_model_parser_preserves_empty_observations_and_rejects_unknown_images(tmp_path):
    path = tmp_path / 'images.txt'
    record = '1 1 0 0 0 0 0 0 1 Front/frame0.jpg\n\n'
    path.write_text('# comment\n' + record)
    assert alignment.read_registered_images(path, {'Front/frame0.jpg'}) == {'Front/frame0.jpg'}
    with pytest.raises(ValueError, match='unexpected'):
        alignment.read_registered_images(path, {'Front/frame1.jpg'})
    path.write_text(record + record)
    with pytest.raises(ValueError, match='duplicate'):
        alignment.read_registered_images(path, {'Front/frame0.jpg'})
    path.write_text(record.rstrip() + '\n')
    with pytest.raises(ValueError, match='Truncated'):
        alignment.read_registered_images(path, {'Front/frame0.jpg'})


def test_runner_uses_fresh_workspace_and_stages_only_selected_views(exported, tmp_path, monkeypatch):
    monkeypatch.setattr(alignment.shutil, 'which', lambda _: '/fake/colmap')
    commands = []
    def command(self, name, args, label=None):
        commands.append(name)
    monkeypatch.setattr(alignment.AlignmentRunner, '_command', command)
    exported.settings['excluded_frames'] = [2]
    root = tmp_path / 'diagnostic'
    before = copy.deepcopy(exported.result)
    report = alignment.AlignmentRunner().run(exported, root, 3)
    assert commands == ['feature_extractor', 'rig_configurator', 'sequential_matcher', 'mapper']
    assert report['sampled_frames'] == [0, 4, 6]
    assert report['registered_captures'] == 0 and report['unregistered_captures'] == 3
    assert exported.result == before
    assert len(list((root / 'images').rglob('*.jpg'))) == 18
    with pytest.raises(FileExistsError):
        alignment.AlignmentRunner().run(exported, root, 3)


def test_export_window_samples_only_confirmed_captures_without_upscaling(exported, tmp_path, monkeypatch):
    monkeypatch.setattr(alignment.shutil, 'which', lambda _: '/fake/colmap')
    monkeypatch.setattr(alignment.AlignmentRunner, '_command', lambda *a: None)
    exported.diagnostic_settings = {'resolution': 1024, 'frame_range': [1, 6]}
    report = alignment.AlignmentRunner().run(exported, tmp_path / 'window', 3)
    assert report['sampled_frames'] == [2, 4, 6] and report['resolution'] == 32
    assert report['captures'][0]['state'] == 'not_sampled'
    exported.diagnostic_settings['frame_range'] = [0, 10]
    with pytest.raises(ValueError, match='source length'):
        alignment.AlignmentRunner().run(exported, tmp_path / 'outside', 3)
    assert not (tmp_path / 'outside').exists()


def test_diagnostic_preserves_mixed_mask_polarity_and_inputs(exported, tmp_path, monkeypatch):
    exported.settings.update(nadir_mask_enabled=True, nadir_mask_radius=30)
    worker = ProcessingWorker([exported])
    worker.run()
    assert worker.error_count == 0
    entries = alignment.load_export(exported)[2]
    before = {str(p): p.read_bytes() for image, _, mask in entries for p in (image, mask) if p is not None}
    monkeypatch.setattr(alignment.shutil, 'which', lambda _: '/fake/colmap')
    monkeypatch.setattr(alignment.AlignmentRunner, '_command', lambda *args: None)
    root = tmp_path / 'mixed'
    alignment.AlignmentRunner().run(exported, root, 3)
    masks = list((root / 'masks').rglob('*.png'))
    assert len(masks) == 18
    for path in masks:
        pixels = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
        if path.parent.name == 'Down':
            assert pixels[16, 16] == 0 and pixels[0, 0] == 255
        else:
            assert np.all(pixels == 255)
    assert all(Path(path).read_bytes() == data for path, data in before.items())


@pytest.mark.parametrize('mode', ['cancel', 'timeout', 'size'])
def test_subprocess_is_reaped_on_cancel_timeout_and_size_limit(tmp_path, monkeypatch, mode):
    monkeypatch.chdir(tmp_path)
    script = tmp_path / 'block.py'
    script.write_text('import time,os\nfrom pathlib import Path\n'
                      f'Path({str(tmp_path / "pid")!r}).write_text(str(os.getpid()))\n'
                      + (f'Path({str(tmp_path / "large")!r}).write_bytes(b"x"*4096)\n' if mode == 'size' else '')
                      + 'time.sleep(30)\n')
    cancelled = threading.Event()
    runner = alignment.AlignmentRunner(cancelled.is_set)
    runner.root, runner.colmap, runner.commands = tmp_path, sys.executable, []
    runner.deadline = time.monotonic() + (.5 if mode == 'timeout' else 30)
    if mode == 'size':
        monkeypatch.setattr(alignment, 'MAX_BYTES', 2048)
    timer = threading.Timer(.5, cancelled.set) if mode == 'cancel' else None
    if timer:
        timer.start()
    try:
        with pytest.raises({'cancel': InterruptedError, 'timeout': TimeoutError, 'size': OSError}[mode]):
            runner._command(script.name, [])
    finally:
        if timer:
            timer.cancel()
    assert runner.commands[-1]['returncode'] != 0
    if os.name != 'nt':
        with pytest.raises(ProcessLookupError):
            os.kill(int((tmp_path / 'pid').read_text()), 0)
