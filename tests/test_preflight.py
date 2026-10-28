"""Source sampling is bounded, inspectable, offline and separate from export."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import cv2
import numpy as np
import pytest

from extractor360.core import alignment, preflight
from extractor360.core.job import Job
from extractor360.core.processor import ProcessingWorker
from extractor360.core.project import source_identity


@pytest.fixture
def video(tmp_path):
    source = tmp_path / 'source.avi'
    writer = cv2.VideoWriter(str(source), cv2.VideoWriter_fourcc(*'MJPG'), 10, (64, 32))
    assert writer.isOpened()
    for value in range(12):
        writer.write(np.full((32, 64, 3), value * 18, np.uint8))
    writer.release()
    return Job(str(source), settings={'layout_mode': 'cube', 'resolution': 32, 'exif_intrinsics': False},
               source_identity=source_identity(str(source)), source_check_required=True)


def test_uniform_sampling_skips_exclusions_without_allocating_full_video():
    assert preflight.uniform_frames(12, [0, 2, 11], 4) == [1, 5, 7, 10]
    large = preflight.uniform_frames(10**9, [0, 10**9 - 1], 16)
    assert len(set(large)) == 16 and large[0] == 1 and large[-1] == 10**9 - 2
    with pytest.raises(ValueError, match='three'):
        preflight.uniform_frames(3, [1], 8)
    assert preflight.uniform_frames(12, [0, 4, 9, 11], 4, [3, 10]) == [3, 6, 7, 10]
    with pytest.raises(ValueError, match='source length'):
        preflight.uniform_frames(12, [], 4, [3, 12])


def test_sampling_adaptations_are_explicit_and_do_not_edit_project(video, tmp_path):
    video.settings.update(resolution=2048, interval_unit='Seconds', interval_value=2,
                          mask_profile='postshot', adaptive_mode=True, blur_filter_enabled=True, smart_blur_enabled=True)
    before = copy.deepcopy(video.settings)
    settings, _, _ = preflight.source_plan(video, 8)
    sample = preflight.sampling_settings(settings, tmp_path)
    assert sample['resolution'] == 512 and sample['ai_invert_mask'] is True
    assert sample['export_colmap'] and sample['layout_mode'] == 'cube'
    assert not sample['adaptive_mode'] and not sample['blur_filter_enabled'] and not sample['smart_blur_enabled']
    assert video.settings == before


def test_source_plan_rejects_missing_untrusted_models_before_writing(video, tmp_path, monkeypatch):
    video.settings.update(ai_mode='Generate Mask', ai_model=str(tmp_path / 'unknown.pt'))
    with pytest.raises(ValueError, match='Custom .pt'):
        preflight.source_plan(video, 8)
    video.settings['trust_custom_model'] = True
    with pytest.raises(ValueError, match='missing'):
        preflight.source_plan(video, 8)
    video.settings.update(ai_model='yolo26x-seg.pt', trust_custom_model=False)
    monkeypatch.setenv('EXTRACTOR360_MODEL_DIR', str(tmp_path / 'absent'))
    with pytest.raises(ValueError, match='does not download'):
        preflight.source_plan(video, 8)


def test_diagnostic_worker_seeks_only_requested_frames_and_preserves_timestamps(video):
    video.settings.update(interval_unit='Frames', interval_value=10, excluded_frames=[5])
    worker = ProcessingWorker([video], diagnostic_frames=[0, 5, 11])
    worker.run()
    assert worker.error_count == 0
    records = [json.loads(line) for line in Path(video.result['output_dir'], 'images.jsonl').read_text().splitlines()]
    assert {row['frame'] for row in records} == {0, 11}
    assert len(records) == 12 and 'frame_count_check' not in video.result
    assert video.result['diagnostic_sampling'] == {'requested_frames': [0, 5, 11], 'decoded_frames': [0, 5, 11]}
    assert all(abs(row['timestamp_seconds'] - row['frame'] / 10) < .01 for row in records)


@pytest.mark.parametrize('frames', [[], [True], [2, 1], [1, 1], list(range(17))])
def test_invalid_diagnostic_selection_fails_before_outputs(video, frames):
    with pytest.raises(ValueError):
        ProcessingWorker([video], diagnostic_frames=frames)


def test_diagnostic_rejects_seek_to_different_frame(video, monkeypatch):
    original = cv2.VideoCapture
    class WrongPosition:
        def __init__(self, path): self.cap = original(path)
        def __getattr__(self, name): return getattr(self.cap, name)
        def get(self, prop):
            value = self.cap.get(prop)
            return value + 1 if prop == cv2.CAP_PROP_POS_FRAMES else value
    monkeypatch.setattr(cv2, 'VideoCapture', WrongPosition)
    worker = ProcessingWorker([video], diagnostic_frames=[0, 5, 11])
    worker.run()
    assert worker.error_count == 1 and 'cannot confirm' in video.result['error']
    assert not Path(video.result['output_dir'], 'images.jsonl').exists()


def test_real_sampling_subprocess_preserves_last_export_and_uses_global_budget(video, tmp_path, monkeypatch):
    monkeypatch.setattr(preflight.shutil, 'which', lambda _: sys.executable)
    commands = []
    def command(runner, name, arguments, label=None):
        assert runner.budget is not None
        runner._check()
        commands.append(name)
    monkeypatch.setattr(alignment.AlignmentRunner, '_command', command)
    video.settings.update(excluded_frames=[0, 11], nadir_mask_enabled=True)
    video.result = {'run_id': 'previous-export', 'output_dir': '/unchanged/export'}
    before = copy.deepcopy(video)
    root = tmp_path / 'preflight'
    report = alignment.AlignmentRunner().run_source(video, root, 4)
    assert report['mode'] == 'source_preflight' and report['requested_frames'] == [1, 4, 7, 10]
    assert report['sampled_frames'] == [1, 4, 7, 10] and report['unregistered_captures'] == 4
    assert report['fingerprint'] == alignment.fingerprint(video)
    assert video == before and report['filtered_captures'] == 0
    assert commands == ['feature_extractor', 'rig_configurator', 'sequential_matcher', 'mapper']
    manifests = list((root / 'sample').rglob('manifest.json'))
    manifest = json.loads(manifests[0].read_text())
    assert manifest['extraction']['images_written'] == 24
    assert manifest['diagnostic_sampling']['decoded_frames'] == report['requested_frames']
    with pytest.raises(FileExistsError):
        alignment.AlignmentRunner().run_source(video, root, 4)


def test_source_window_and_1024_resolution_reach_real_helper_and_colmap(video, tmp_path, monkeypatch):
    monkeypatch.setattr(preflight.shutil, 'which', lambda _: sys.executable)
    monkeypatch.setattr(alignment.AlignmentRunner, '_command', lambda *a: None)
    video.settings['excluded_frames'] = [5]
    video.diagnostic_settings = {'mode': 'source', 'resolution': 1024, 'maximum': 4, 'frame_range': [2, 10]}
    before = copy.deepcopy(video)
    root = tmp_path / 'window'
    report = alignment.AlignmentRunner().run_source(video, root, 4)
    assert video == before
    assert report['requested_frames'] == [2, 4, 8, 10]
    assert report['diagnostic_settings'] == video.diagnostic_settings and report['resolution'] == 1024
    assert report['captures'][0]['timestamp_seconds'] == pytest.approx(.2)
    images = list((root / 'alignment/images').rglob('*.jpg'))
    assert len(images) == 24 and cv2.imread(str(images[0])).shape[:2] == (1024, 1024)
    video.diagnostic_settings['frame_range'] = [9, 15]
    with pytest.raises(RuntimeError, match='source length'):
        alignment.AlignmentRunner().run_source(video, tmp_path / 'outside', 4)
    assert not (tmp_path / 'outside/sample').exists()


def test_filtered_candidates_are_not_called_unregistered(video, tmp_path, monkeypatch):
    monkeypatch.setattr(preflight.shutil, 'which', lambda _: sys.executable)
    def sample(runner, *args, **kwargs):
        out = runner.root / 'empty-export'
        out.mkdir()
        (runner.root / 'sample-result.json').write_text(json.dumps({
            'settings': preflight.sampling_settings(preflight.source_plan(video, 3)[0], out),
            'result': {'output_dir': str(out), 'run_id': 'filtered'},
            'requested_frames': [0, 5, 11], 'source_frame_count': 12, 'overrides': {}}))
    monkeypatch.setattr(alignment.AlignmentRunner, '_execute', sample)
    report = alignment.AlignmentRunner().run_source(video, tmp_path / 'preflight', 3)
    assert report['filtered_captures'] == 3 and report['unregistered_captures'] == 0
    assert report['sampled_frames'] == [] and all(row['state'] == 'filtered' for row in report['captures'])
    assert report['alignment_not_run'] == 'Fewer than three confirmed captures'


def test_source_sampling_cancelled_before_creation(video, tmp_path, monkeypatch):
    monkeypatch.setattr(preflight.shutil, 'which', lambda _: sys.executable)
    with pytest.raises(InterruptedError):
        alignment.AlignmentRunner(lambda: True).run_source(video, tmp_path / 'cancelled', 3)
    assert not (tmp_path / 'cancelled').exists()


def test_no_model_is_recognized_only_with_expected_mapper_evidence(tmp_path):
    sparse = tmp_path / 'sparse'
    sparse.mkdir()
    log = tmp_path / 'mapper.log'
    log.write_text('Failed to create any sparse model\n')
    assert alignment.no_model_outcome(alignment.CommandFailed('mapper', 1, log), sparse)
    assert not alignment.no_model_outcome(alignment.CommandFailed('mapper', -9, log), sparse)
    assert not alignment.no_model_outcome(alignment.CommandFailed('feature_extractor', 1, log), sparse)
    log.write_text('Invalid database\n')
    assert not alignment.no_model_outcome(alignment.CommandFailed('mapper', 1, log), sparse)


def test_cancellation_stops_sampling_process_and_its_child(tmp_path):
    marker = tmp_path / 'child.pid'
    script = tmp_path / 'parent.py'
    child_code = f'import os,time;from pathlib import Path;Path({str(marker)!r}).write_text(str(os.getpid()));time.sleep(30)'
    script.write_text(f'import subprocess,sys,time\nsubprocess.Popen([sys.executable,"-c",{child_code!r}])\ntime.sleep(30)\n')
    runner = alignment.AlignmentRunner(cancelled=marker.is_file)
    runner.root, runner.deadline, runner.commands = tmp_path, time.monotonic() + 10, []
    with pytest.raises(InterruptedError):
        runner._execute([sys.executable, str(script)], 'sampling', 'sampling')
    assert runner.commands[0]['returncode'] != 0
    pid = int(marker.read_text())
    def child_running():
        if os.name == 'nt':
            import ctypes
            from ctypes import wintypes
            kernel = ctypes.WinDLL('kernel32', use_last_error=True)
            kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
            kernel.OpenProcess.restype = wintypes.HANDLE
            kernel.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
            kernel.CloseHandle.argtypes = [wintypes.HANDLE]
            handle = kernel.OpenProcess(0x1000, False, pid)
            if not handle:
                return False
            try:
                code = wintypes.DWORD()
                assert kernel.GetExitCodeProcess(handle, ctypes.byref(code))
                return code.value == 259
            finally:
                kernel.CloseHandle(handle)
        status = subprocess.run(['ps', '-o', 'stat=', '-p', str(pid)], capture_output=True, text=True, timeout=5).stdout.strip()
        return bool(status) and not status.startswith('Z')
    deadline = time.monotonic() + 3
    while child_running():
        assert time.monotonic() < deadline, 'Sampling child remained alive after cancellation'
        time.sleep(.01)
