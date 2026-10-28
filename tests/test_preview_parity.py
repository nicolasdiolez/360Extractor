import json
import gc
import shutil
import subprocess
import sys
import threading
import types
import weakref
from pathlib import Path

import cv2
import numpy as np
import pytest

pytest.importorskip('PySide6')
from extractor360.core.job import Job
from extractor360.core.processor import ProcessingWorker
from PySide6.QtWidgets import QApplication

from extractor360.core.geometry import GeometryProcessor
from extractor360.ui.preview_widget import PreviewModelCache, PreviewWidget, PreviewWorker


@pytest.fixture
def preview_app():
    return QApplication.instance() or QApplication([])


@pytest.mark.parametrize('layout,face,is_360',[('cube','Down',True),('ring','View_1',True),('fibonacci','View_2',True),('cube','flat',False)])
def test_preview_pixels_match_export(tmp_path,layout,face,is_360):
    image=np.random.default_rng(3).integers(0,255,(48,96,3),dtype=np.uint8)
    source=tmp_path/'source.png'
    cv2.imwrite(str(source),image)
    settings=dict(resolution=64,layout_mode=layout,camera_count=3,is_360=is_360,output_format='png',interpolation_mode='lanczos',sharpening_enabled=True,sharpening_strength=.5)
    job=Job(str(source),settings=settings)
    worker=ProcessingWorker([job]);worker.run()
    assert worker.error_count==0
    records=[json.loads(s) for s in (Path(job.result['output_dir'])/'images.jsonl').read_text().splitlines()]
    record=next(r for r in records if r['camera']==face)
    expected=cv2.imread(str(Path(job.result['output_dir'])/record['image']))
    previews=[];errors=[]
    preview=PreviewWorker(str(source),settings,face,show_ai_mask=False,show_nadir_disc=False)
    preview.signals.result.connect(previews.append)
    preview.signals.error.connect(errors.append)
    preview.run()
    assert not errors and len(previews)==1
    qt=previews[0]
    pixels=np.frombuffer(qt.bits(),dtype=np.uint8).reshape(qt.height(),qt.bytesPerLine())[:,:qt.width()*3].reshape(qt.height(),qt.width(),3)
    np.testing.assert_array_equal(cv2.cvtColor(pixels,cv2.COLOR_RGB2BGR),expected)


@pytest.mark.parametrize('pts,fps,seconds,source', [
    (1750, 30, 1.75, 'decoder_timestamp'),
    (0, 30, 2 / 30, 'fps_estimate'),
    (float('nan'), 25, 2 / 25, 'fps_estimate'),
    (1750, 0, 1.75, 'decoder_timestamp'),
])
def test_preview_uses_decoded_time_and_actual_seek_position(monkeypatch, pts, fps, seconds, source):
    class Capture:
        released = False

        def isOpened(self):
            return True

        def set(self, prop, value):
            assert value == 9  # requested frame can differ from decoded frame

        def get(self, prop):
            return {
                cv2.CAP_PROP_FRAME_COUNT: 10,
                cv2.CAP_PROP_FPS: fps,
                cv2.CAP_PROP_POS_FRAMES: 3,
                cv2.CAP_PROP_POS_MSEC: pts,
            }[prop]

        def read(self):
            return True, np.zeros((16, 32, 3), np.uint8)

        def release(self):
            self.released = True

    capture = Capture()
    monkeypatch.setattr(cv2, 'VideoCapture', lambda path: capture)
    worker = PreviewWorker('vfr.mp4', {'is_360': False}, position_ratio=1)
    times, sources, errors = [], [], []
    worker.signals.duration_info.connect(lambda *values: times.append(values))
    worker.signals.timing_source.connect(sources.append)
    worker.signals.error.connect(errors.append)
    worker.run()
    assert errors == []
    assert capture.released
    assert times[0][:2] == (seconds, 2)
    assert sources == [source]
    if fps == 0:
        assert np.isnan(times[0][2])


def test_real_vfr_preview_time_and_pixels_match_decoded_export(tmp_path):
    ffmpeg = shutil.which('ffmpeg')
    if not ffmpeg:
        pytest.skip('FFmpeg is required to synthesize variable frame rate media')
    for index in range(3):
        assert cv2.imwrite(str(tmp_path / f'{index}.png'), np.full((16, 32, 3), (index + 1) * 60, np.uint8))
    playlist = tmp_path / 'frames.txt'
    playlist.write_text("file '0.png'\nduration 0.04\nfile '1.png'\nduration 0.36\nfile '2.png'\nduration 0.08\nfile '2.png'\n", encoding='utf-8')
    video = tmp_path / 'vfr.mkv'
    subprocess.run(
        [ffmpeg, '-v', 'error', '-f', 'concat', '-safe', '0', '-i', str(playlist), '-fps_mode', 'vfr', '-c:v', 'ffv1', str(video)],
        check=True, capture_output=True, timeout=15,
    )
    capture = cv2.VideoCapture(str(video))
    decoded, timestamps = [], []
    count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = capture.get(cv2.CAP_PROP_FPS)
    try:
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            decoded.append(frame)
            timestamps.append(capture.get(cv2.CAP_PROP_POS_MSEC) / 1000)
    finally:
        capture.release()
    assert len(decoded) == 4
    assert max(np.diff(timestamps)) - min(np.diff(timestamps)) > .2
    job = Job(str(video), settings={'is_360': False, 'interval_unit': 'Frames', 'interval_value': 1, 'output_format': 'png'})
    engine = ProcessingWorker([job])
    engine.run()
    assert engine.error_count == 0
    records = [json.loads(line) for line in (Path(job.result['output_dir']) / 'images.jsonl').read_text().splitlines()]
    previews, times, sources, errors = [], [], [], []
    preview = PreviewWorker(str(video), {'is_360': False}, position_ratio=2 / (count - 1))
    preview.signals.result.connect(previews.append)
    preview.signals.duration_info.connect(lambda *value: times.append(value))
    preview.signals.timing_source.connect(sources.append)
    preview.signals.error.connect(errors.append)
    preview.run()
    assert not errors and len(previews) == 1
    seconds, frame_index, _ = times[0]
    assert sources == ['decoder_timestamp']
    assert seconds == pytest.approx(timestamps[frame_index])
    assert abs(seconds - frame_index / fps) > .1
    record = next(record for record in records if record['frame'] == frame_index)
    exported = cv2.imread(str(Path(job.result['output_dir']) / record['image']))
    image = previews[0]
    pixels = np.frombuffer(image.bits(), np.uint8).reshape(image.height(), image.bytesPerLine())[:, :image.width() * 3].reshape(image.height(), image.width(), 3)
    np.testing.assert_array_equal(cv2.cvtColor(pixels, cv2.COLOR_RGB2BGR), exported)


def _fake_ai(monkeypatch, process=None):
    class Service:
        calls = []
        refs = []

        def __init__(self, model_name):
            self.refs.append(weakref.ref(self))

        def process_image(self, image, **kwargs):
            self.calls.append(kwargs['mode'])
            if process:
                return process(image, kwargs)
            return None, True

    monkeypatch.setitem(sys.modules, 'extractor360.core.ai_model', types.SimpleNamespace(AIService=Service))
    monkeypatch.setattr(cv2, 'imread', lambda path: np.zeros((16, 32, 3), np.uint8))
    return Service


def test_preview_skip_frame_has_explicit_rejection_and_uses_export_mode(monkeypatch, preview_app):
    service = _fake_ai(monkeypatch)
    settings = {'is_360': False, 'ai_mode': 'Skip Frame'}
    worker = PreviewWorker('flat.png', settings, show_ai_mask=False)
    status, images, errors = [], [], []
    worker.signals.view_status.connect(status.append)
    worker.signals.result.connect(images.append)
    worker.signals.error.connect(errors.append)
    worker.run()
    assert not errors
    assert service.calls == ['skip_frame']
    assert status == ['Rejected by AI · excluded from export']
    assert len(images) == 1
    widget = PreviewWidget()
    widget._display_view_status(status[0], widget._generation)
    assert 'excluded from export' in widget.view_status_label.text()


@pytest.mark.parametrize('action', ['disable', 'remove', 'hide_overlay', 'suspend', 'shutdown'])
def test_preview_reuses_model_and_releases_references_when_unused(monkeypatch, preview_app, action):
    service = _fake_ai(monkeypatch, lambda image, kwargs: (image, np.full(image.shape[:2], 255, np.uint8)))
    widget = PreviewWidget()
    settings = {'is_360': False, 'ai_mode': 'Generate Mask'}
    widget.update_preview('flat.png', settings)
    widget._debounce.stop()
    for _ in range(2):
        worker = PreviewWorker('flat.png', settings, ai_cache=widget._ai_cache)
        worker.run()
    assert len(service.refs) == 1
    assert service.refs[0]() is not None
    if action == 'disable':
        widget.update_preview('flat.png', dict(settings, ai_mode='None'))
    elif action == 'remove':
        widget.update_preview(None, {})
    elif action == 'hide_overlay':
        widget._toggle_ai_mask(0)
    elif action == 'suspend':
        widget.suspend()
    else:
        widget.shutdown()
    widget._debounce.stop()
    gc.collect()
    assert service.refs[0]() is None


def test_model_cache_invalidation_during_load_does_not_retain_model():
    cache = PreviewModelCache()
    entered, release = threading.Event(), threading.Event()
    refs, outcomes = [], []

    class Model:
        pass

    def load(name):
        model = Model()
        refs.append(weakref.ref(model))
        entered.set()
        assert release.wait(5)
        return model

    def run():
        try:
            cache.get_or_create('model', load, lambda: False)
        except InterruptedError:
            outcomes.append('invalidated')

    thread = threading.Thread(target=run)
    thread.start()
    assert entered.wait(5)
    cache.clear()
    release.set()
    thread.join(5)
    assert not thread.is_alive()
    assert outcomes == ['invalidated']
    gc.collect()
    assert refs[0]() is None


def test_superseded_projection_reuses_completed_load_while_ai_stays_enabled():
    cache = PreviewModelCache()
    cancelled = threading.Event()
    loads = []

    class Model:
        pass

    def load(name):
        loads.append(name)
        cancelled.set()  # a new face/settings request supersedes this preview
        return Model()

    with pytest.raises(InterruptedError, match='Preview cancelled'):
        cache.get_or_create('model', load, cancelled.is_set)
    model = cache.get_or_create('model', load, lambda: False)
    assert isinstance(model, Model)
    assert loads == ['model']


def test_shutdown_cooperatively_cancels_active_map(monkeypatch, preview_app):
    entered = threading.Event()
    monkeypatch.setattr(cv2, 'imread', lambda path: np.zeros((16, 32, 3), np.uint8))

    def maps(*args, cancelled=None):
        entered.set()
        assert cancelled is not None
        # A tile generator checks this callback between bounded tiles.
        while not cancelled():
            threading.Event().wait(.001)
        raise InterruptedError('Projection cancelled')

    monkeypatch.setattr(GeometryProcessor, 'create_rectilinear_map', maps)
    widget = PreviewWidget()
    widget.update_preview('source.png', {'resolution': 32, 'camera_count': 1})
    widget._debounce.stop()
    widget._run_pending()
    assert entered.wait(5)
    widget.shutdown()
    assert widget.threadpool.waitForDone(1000)
    preview_app.processEvents()
    assert widget.cached_image is None
    assert widget._active_worker is None


@pytest.mark.parametrize('action', ['suspend', 'shutdown'])
def test_pause_or_shutdown_waits_for_native_model_load_then_skips_inference(monkeypatch, preview_app, action):
    entered, release = threading.Event(), threading.Event()
    calls, refs = [], []

    class Service:
        def __init__(self, name):
            refs.append(weakref.ref(self))
            entered.set()
            assert release.wait(5)

        def process_image(self, *args, **kwargs):
            calls.append('inference')

    monkeypatch.setitem(sys.modules, 'extractor360.core.ai_model', types.SimpleNamespace(AIService=Service))
    monkeypatch.setattr(cv2, 'imread', lambda path: np.zeros((16, 32, 3), np.uint8))
    widget = PreviewWidget()
    widget.update_preview('source.png', {'is_360': False, 'ai_mode': 'Skip Frame'})
    widget._debounce.stop()
    widget._run_pending()
    assert entered.wait(5)
    getattr(widget, action)()
    assert ('waiting' if action == 'shutdown' else 'paused') in widget.view_status_label.text()
    assert not widget.threadpool.waitForDone(10)
    release.set()
    assert widget.threadpool.waitForDone(1000)
    preview_app.processEvents()
    gc.collect()
    assert calls == []
    assert widget.cached_image is None
    assert refs[0]() is None


def test_suspend_keeps_image_defers_latest_request_and_resume_refreshes(monkeypatch, preview_app):
    service = _fake_ai(monkeypatch, lambda image, kwargs: (image, np.full(image.shape[:2], 255, np.uint8)))
    monkeypatch.setattr(cv2, 'imread', lambda path: np.full((16, 32, 3), 30 if path == 'first.png' else 60, np.uint8))
    settings = {'is_360': False, 'ai_mode': 'Generate Mask'}
    widget = PreviewWidget()
    widget.update_preview('first.png', settings)
    widget._debounce.stop()
    widget._run_pending()
    assert widget.threadpool.waitForDone(1000)
    preview_app.processEvents()
    displayed = widget.cached_image
    assert displayed is not None and displayed.pixelColor(0, 0).red() == 30
    assert service.refs[0]() is not None
    assert len(service.calls) == 1

    widget.suspend()
    gc.collect()
    assert service.refs[0]() is None
    assert widget.cached_image is displayed
    assert not widget._pending and not widget._debounce.isActive()
    widget.update_preview('second.png', settings)
    widget.set_face('flat')
    widget._run_pending()  # even a queued timer callback must remain inert
    assert not widget._pending and not widget._debounce.isActive()
    assert widget.threadpool.activeThreadCount() == 0
    assert len(service.calls) == 1
    assert widget.cached_image is displayed

    widget.resume()
    assert widget._pending[0] == 'second.png'
    assert widget._debounce.isActive()
    widget._debounce.stop()
    widget._run_pending()
    assert widget.threadpool.waitForDone(1000)
    preview_app.processEvents()
    assert len(service.calls) == 2
    assert widget.cached_image.pixelColor(0, 0).red() == 60
    widget.shutdown()
    widget.resume()  # a late extraction-finished callback cannot reopen it
    widget._run_pending()
    assert widget._closed and widget._suspended
    assert not widget._pending and not widget._debounce.isActive()
    assert widget.threadpool.activeThreadCount() == 0


@pytest.mark.parametrize('actual', [2, 1])
def test_exact_source_navigation_confirms_requested_frame(monkeypatch, actual):
    class Capture:
        def isOpened(self): return True
        def set(self, prop, value): assert prop == cv2.CAP_PROP_POS_FRAMES and value == 2
        def get(self, prop):
            return {cv2.CAP_PROP_FRAME_COUNT: 100, cv2.CAP_PROP_FPS: 10,
                    cv2.CAP_PROP_POS_FRAMES: actual + 1, cv2.CAP_PROP_POS_MSEC: actual * 100}[prop]
        def read(self): return True, np.zeros((16, 32, 3), np.uint8)
        def release(self): pass
    monkeypatch.setattr(cv2, 'VideoCapture', lambda path: Capture())
    worker = PreviewWorker('source.mp4', {'is_360': False, 'excluded_frames': [2]}, exact_frame=2)
    errors, times, states, images = [], [], [], []
    worker.signals.error.connect(errors.append)
    worker.signals.duration_info.connect(lambda *values: times.append(values))
    worker.signals.view_status.connect(states.append)
    worker.signals.result.connect(images.append)
    worker.run()
    if actual == 2:
        assert not errors and times[0][1] == 2 and len(images) == 1
        assert states == ['Capture excluded in project']
    else:
        assert errors and 'could not confirm' in errors[0] and not images
