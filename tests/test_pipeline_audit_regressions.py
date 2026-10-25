"""Synthetic regressions for cancellation, frame provenance and output preflight."""
import json
import weakref
from pathlib import Path
from threading import Event, Lock

import cv2
import numpy as np
import piexif
import pytest

from extractor360.core.frame_timing import FrameClock
from extractor360.core.job import Job
from extractor360.core.processor import ProcessingWorker
from extractor360.core.settings_manager import SettingsManager
from extractor360.utils.file_manager import FileManager


def make_job(tmp_path, **settings):
    source = tmp_path / 'source.png'
    assert cv2.imwrite(str(source), np.full((32, 64, 3), 120, np.uint8))
    options = dict(SettingsManager.DEFAULT_SETTINGS, custom_output_dir=str(tmp_path),
                   resolution=64, is_360=False, export_telemetry=False)
    options.update(settings)
    return Job(str(source), settings=options)


@pytest.mark.parametrize('writer_fails', [False, True])
def test_interrupt_wait_drains_counts_and_indexes_before_terminal_manifest(tmp_path, monkeypatch, writer_fails):
    job = make_job(tmp_path, is_360=True, layout_mode='cube')
    worker = ProcessingWorker([job])
    gate = Event()
    lock = Lock()
    state = {'active': 0, 'finished': 0, 'interrupted': False}
    original_write = FileManager.write_pair

    def writer(*args):
        with lock:
            state['active'] += 1
        try:
            assert gate.wait(5)
            if writer_fails and '_Front.' in args[0]:
                raise OSError('deliberate writer failure')
            return original_write(*args)
        finally:
            with lock:
                state['active'] -= 1
                state['finished'] += 1

    monkeypatch.setattr(FileManager, 'write_pair', writer)
    original_submit = worker.io_pool.submit

    def submit(*args):
        future = original_submit(*args)
        original_result = future.result

        def result(*args, **kwargs):
            if not state['interrupted']:
                state['interrupted'] = True
                gate.set()
                raise KeyboardInterrupt
            return original_result(*args, **kwargs)

        future.result = result
        return future

    monkeypatch.setattr(worker.io_pool, 'submit', submit)
    original_manifest = worker._write_manifest

    def manifest(output_dir, job, stats):
        if stats['status'] != 'running':
            assert state['active'] == 0
            assert state['finished'] == 6
            records = (Path(output_dir) / 'images.jsonl').read_text().splitlines()
            assert len(records) == stats['extraction']['images_written']
        original_manifest(output_dir, job, stats)

    monkeypatch.setattr(worker, '_write_manifest', manifest)
    cancelled = []
    worker.job_cancelled.connect(cancelled.append)
    with pytest.raises(KeyboardInterrupt):
        worker.run()
    assert cancelled == [0]
    assert job.status == 'Cancelled'
    saved = json.loads((Path(job.result['output_dir']) / 'manifest.json').read_text())
    assert saved['status'] == 'cancelled'
    assert saved['extraction']['images_written'] == (5 if writer_fails else 6)
    assert saved['extraction']['writes_failed'] == int(writer_fails)
    if writer_fails:
        assert 'deliberate writer failure' in saved['write_errors'][0]


def test_invalid_output_name_creates_no_directory(tmp_path):
    job = make_job(tmp_path, naming_mode='custom', image_pattern='../{filename}{ext}')
    worker = ProcessingWorker([job])
    worker.run()
    assert job.status == 'Error'
    assert list(tmp_path.iterdir()) == [Path(job.file_path)]
    assert 'output_dir' not in job.result


def test_worker_releases_service_after_writers_finish(tmp_path):
    class Service:
        pass

    worker = ProcessingWorker([make_job(tmp_path)])
    worker.ai_service = Service()
    service_ref = weakref.ref(worker.ai_service)
    worker.run()
    assert service_ref() is None
    assert worker.ai_service is None
    assert worker._ai_model_name is None


class Capture:
    def __init__(self, timestamps, count):
        self.timestamps = timestamps
        self.count = count
        self.index = -1

    def isOpened(self):
        return True

    def get(self, prop):
        return {cv2.CAP_PROP_FPS: 10, cv2.CAP_PROP_FRAME_COUNT: self.count,
                cv2.CAP_PROP_POS_MSEC: self.timestamps[max(0, self.index)] * 1000,
                cv2.CAP_PROP_FRAME_WIDTH: 64, cv2.CAP_PROP_FRAME_HEIGHT: 32}.get(prop, 0)

    def grab(self):
        self.index += 1
        return self.index < len(self.timestamps)

    def retrieve(self):
        return True, np.full((32, 64, 3), 120, np.uint8)

    def release(self):
        pass


def video_job(tmp_path, monkeypatch, timestamps, count, probe=None, **settings):
    job = make_job(tmp_path, interval_unit='Frames', interval_value=2, **settings)
    source = tmp_path / 'source.mp4'
    source.touch()
    job.file_path = str(source)
    monkeypatch.setattr('extractor360.core.processor.cv2.VideoCapture', lambda _: Capture(timestamps, count))
    if probe is None:
        monkeypatch.setattr('extractor360.core.telemetry.capture', lambda *args: b'{}')
    else:
        monkeypatch.setattr('extractor360.core.telemetry.capture', lambda *args: json.dumps(probe).encode())
    return job


def test_fps_fallback_on_unselected_frame_remains_in_manifest(tmp_path, monkeypatch):
    job = video_job(tmp_path, monkeypatch, [0, 0, .2], 3)
    ProcessingWorker([job]).run()
    assert job.status == 'Done'
    assert job.result['frame_time_source'] == 'mixed'
    assert 'FPS estimation used' in job.result['timestamp_fallback']
    assert job.result['extraction']['images_written'] == 2


def test_missing_last_expected_frame_is_failure(tmp_path, monkeypatch):
    job = video_job(tmp_path, monkeypatch, [0], 2)
    ProcessingWorker([job]).run()
    assert job.status == 'Error'
    assert job.result['status'] == 'failed'
    assert job.result['frame_count_check']['decoded'] == 1
    assert job.result['extraction']['images_written'] == 1


def test_estimated_container_count_mismatch_is_explicit(tmp_path, monkeypatch):
    job = video_job(tmp_path, monkeypatch, [0], 2, probe={'streams': [{'codec_type': 'video'}]})
    ProcessingWorker([job]).run()
    assert job.status == 'Done'
    assert 'estimated' in job.result['frame_count_warning']


def test_capture_date_without_gps_export(tmp_path, monkeypatch):
    job = make_job(tmp_path, export_telemetry=False)
    monkeypatch.setattr('extractor360.core.telemetry.capture', lambda *args: json.dumps({
        'format': {'tags': {'creation_time': '2026-10-23T08:12:34Z'}}}).encode())
    ProcessingWorker([job]).run()
    assert job.result['capture_time_source'] == 'container_creation_time'
    output = next(Path(job.result['output_dir']).glob('*.jpg'))
    assert piexif.load(str(output))['Exif'][piexif.ExifIFD.DateTimeOriginal] == b'2026:10:23 08:12:34'


def test_optional_ffprobe_absence_preserves_extraction(tmp_path, monkeypatch):
    job = make_job(tmp_path)

    def unavailable(*args):
        raise FileNotFoundError('ffprobe')

    monkeypatch.setattr('extractor360.core.telemetry.capture', unavailable)
    ProcessingWorker([job]).run()
    assert job.status == 'Done'
    assert job.result['capture_time_source'] == 'unknown'


def test_frame_clock_fallback_is_monotone_and_provenance_accumulates():
    clock = FrameClock(10)
    assert clock.resolve(0, 0) == (0, 'decoder_timestamp')
    assert clock.resolve(1, 0)[1] == 'fps_estimate'
    assert clock.resolve(2, float('nan'))[0] == pytest.approx(.2)
    assert clock.resolve(3, .1)[0] == pytest.approx(.3)
    assert clock.resolve(4, .4) == (.4, 'decoder_timestamp')
    assert clock.source == 'mixed'


@pytest.mark.parametrize('sidecar', ['relative_srt', 'missing_gpx', 'absolute_srt'])
def test_export_preserves_gps_without_fabricating_altitude(tmp_path, monkeypatch, sidecar):
    job = make_job(tmp_path, export_telemetry=True, altitude_mode='absolute', gps_altitude_reference='orthometric')
    monkeypatch.setattr('extractor360.core.telemetry.capture', lambda *args: b'{}')
    if sidecar == 'missing_gpx':
        Path(job.file_path).with_suffix('.gpx').write_text('<gpx><trk><trkseg><trkpt lat="48" lon="2"><time>2026-01-01T00:00:00Z</time></trkpt></trkseg></trk></gpx>')
    else:
        altitude = '[rel_alt: 12.5]' if sidecar == 'relative_srt' else '[abs_alt: 5000.125]'
        Path(job.file_path).with_suffix('.srt').write_text('1\n00:00:00,000 --> 00:00:01,000\n[latitude: 48] [longitude: 2] ' + altitude)
    ProcessingWorker([job]).run()
    assert job.status == 'Done'
    output = next(Path(job.result['output_dir']).glob('*.jpg'))
    gps = piexif.load(str(output))['GPS']
    assert piexif.GPSIFD.GPSLatitude in gps
    assert piexif.GPSIFD.GPSLongitude in gps
    assert (piexif.GPSIFD.GPSAltitude in gps) == (sidecar == 'absolute_srt')
    reference = {'relative_srt': 'relative', 'missing_gpx': 'unknown', 'absolute_srt': 'absolute'}[sidecar]
    assert job.result['telemetry']['altitude_references'] == [reference]


def test_submission_interrupt_preserves_interrupt_and_writer_failure(tmp_path, monkeypatch):
    job = make_job(tmp_path, is_360=True, layout_mode='cube')
    worker = ProcessingWorker([job])
    original_submit = worker.io_pool.submit
    submissions = []

    def failure():
        raise OSError('failure from already submitted writer')

    def submit(*args):
        if submissions:
            raise KeyboardInterrupt
        submissions.append(True)
        return original_submit(failure)

    monkeypatch.setattr(worker.io_pool, 'submit', submit)
    with pytest.raises(KeyboardInterrupt):
        worker.run()
    assert job.status == 'Cancelled'
    assert job.result['extraction']['writes_failed'] == 1
    assert job.result['write_errors'] == ['failure from already submitted writer']
    manifest = json.loads((Path(job.result['output_dir']) / 'manifest.json').read_text())
    assert manifest['status'] == 'cancelled'
    assert manifest['extraction']['images_written'] == 0


@pytest.mark.parametrize('signal_count', [1, 2])
def test_cli_real_sigint_during_index_write_is_cooperative(tmp_path, signal_count):
    import os
    import subprocess
    import sys

    if os.name != 'posix':
        pytest.skip('POSIX SIGINT delivery regression; Windows console signals differ')
    job = make_job(tmp_path)
    script = tmp_path / 'interrupt_during_index.py'
    marker = tmp_path / 'signal_state.json'
    script.write_text('''import builtins
import json
import os
from pathlib import Path
import signal
import extractor360.main as cli
from extractor360.core import telemetry

cli.TQDM_AVAILABLE = False
telemetry.capture = lambda *args: b'{}'
original_open = builtins.open
previous_handler = signal.getsignal(signal.SIGINT)
sent = 0

class InterruptedIndex:
    def __init__(self, handle):
        self.handle = handle
    def __enter__(self):
        self.handle.__enter__()
        return self
    def __exit__(self, *args):
        return self.handle.__exit__(*args)
    def write(self, text):
        global sent
        if not sent:
            # This is after the writer was confirmed and counted, but before
            # its index row is written: raising KeyboardInterrupt here loses it.
            for _ in range(int(os.environ['TEST_SIGNAL_COUNT'])):
                sent += 1
                os.kill(os.getpid(), signal.SIGINT)
        return self.handle.write(text)

def intercepted_open(file, mode='r', *args, **kwargs):
    handle = original_open(file, mode, *args, **kwargs)
    if str(file).endswith('images.jsonl') and mode == 'a':
        return InterruptedIndex(handle)
    return handle

builtins.open = intercepted_open
try:
    cli.main()
finally:
    Path(os.environ['TEST_SIGNAL_MARKER']).write_text(json.dumps({
        'signals_sent': sent,
        'handler_restored': signal.getsignal(signal.SIGINT) == previous_handler,
    }))
''', encoding='utf-8')
    env = dict(os.environ, TEST_SIGNAL_COUNT=str(signal_count), TEST_SIGNAL_MARKER=str(marker),
               PYTHONPATH=str(Path(__file__).resolve().parents[1] / 'src'))
    process = subprocess.run([
        sys.executable, str(script), '--input', job.file_path,
        '--output', str(tmp_path / 'outputs'), '--resolution', '64', '--layout', 'cube',
    ], env=env, capture_output=True, text=True, timeout=20)
    assert process.returncode == 130, process.stdout + process.stderr
    state = json.loads(marker.read_text())
    assert state == {'signals_sent': signal_count, 'handler_restored': True}
    output = next((tmp_path / 'outputs').glob('*_processed'))
    manifest = json.loads((output / 'manifest.json').read_text())
    records = [json.loads(line) for line in (output / 'images.jsonl').read_text().splitlines()]
    assert manifest['status'] == 'cancelled'
    assert manifest['extraction']['images_written'] == len(records) == len(list(output.glob('*.jpg'))) == 6
    assert {r['image'] for r in records} == {p.name for p in output.glob('*.jpg')}


def test_invalid_name_preflight_precedes_metadata_and_model_loading(tmp_path, monkeypatch):
    job = make_job(tmp_path, naming_mode='custom', image_pattern='../{filename}{ext}', ai_mode='Generate Mask')
    forbidden = []

    def unexpected(*args, **kwargs):
        forbidden.append(True)
        raise AssertionError('Preflight must run first')

    monkeypatch.setattr('extractor360.core.processor.TelemetryHandler.extract_metadata', unexpected)
    monkeypatch.setattr(ProcessingWorker, '_ensure_ai_service', unexpected)
    worker = ProcessingWorker([job])
    worker.run()
    assert job.status == 'Error'
    assert not forbidden
    assert 'output_dir' not in job.result
