"""Independent pole/seam oracle and bounded, cancellable blur sampling."""
import cv2
import numpy as np
import pytest

from extractor360.core.analyzer import BlurAnalyzer
from extractor360.core.geometry import GeometryProcessor


@pytest.mark.parametrize('interpolation', [cv2.INTER_LINEAR, cv2.INTER_LANCZOS4])
def test_projection_poles_and_seam_match_independent_extended_image(interpolation):
    # Opposite poles have disjoint channels: wrapping latitude is visible even
    # when linear and Lanczos agree with each other at an integer coordinate.
    frame = np.zeros((12, 24, 3), np.uint8)
    frame[:4, :, 2] = 240
    frame[-4:, :, 0] = 220
    frame[:, :, 1] = np.arange(24, dtype=np.uint8) * 8
    h, w = frame.shape[:2]
    mx, my = np.meshgrid(
        np.array([-.25, .25, w - .25, w + .25], np.float32),
        np.array([0, .25, h - .25, h], np.float32),
    )
    # Oracle uses explicitly indexed source pixels on BOTH axes and a constant
    # border which no interpolation tap reaches. It does not use production
    # padding, production maps, or BORDER_WRAP.
    margin = 16
    oracle_source = frame[
        np.clip(np.arange(-margin, h + margin), 0, h - 1)[:, None],
        np.arange(-margin, w + margin)[None, :] % w,
    ]
    expected = cv2.remap(oracle_source, mx + margin, my + margin, interpolation, borderMode=cv2.BORDER_CONSTANT)
    actual = GeometryProcessor.remap_equirectangular(
        frame, *GeometryProcessor.prepare_equirectangular_maps(mx, my), interpolation
    )
    np.testing.assert_array_equal(actual, expected)
    assert actual[0, 0, 0] == 0  # north never receives south's blue
    assert actual[-1, 0, 2] == 0  # south never receives north's red


@pytest.mark.parametrize('interpolation', [cv2.INTER_LINEAR, cv2.INTER_LANCZOS4])
def test_down_view_center_samples_south_pole(interpolation):
    frame = np.zeros((20, 40, 3), np.uint8)
    frame[0] = (0, 0, 255)
    frame[-1] = (255, 0, 0)
    maps = GeometryProcessor.create_rectilinear_map(20, 40, 32, 32, 90, 0, -90, 0)
    assert maps[1][16, 16] == 20
    projected = GeometryProcessor.remap_equirectangular(
        frame, *GeometryProcessor.prepare_equirectangular_maps(*maps), interpolation
    )
    np.testing.assert_array_equal(projected[16, 16], (255, 0, 0))


def test_projection_cancels_between_tiles():
    calls = []

    def cancelled():
        calls.append(True)
        return len(calls) == 2

    with pytest.raises(InterruptedError, match='Projection cancelled'):
        GeometryProcessor.create_rectilinear_map(20, 40, 768, 16, 90, 0, 0, 0, cancelled=cancelled)
    assert len(calls) == 2


@pytest.mark.parametrize('settings', [
    {'resolution': float('nan')},
    {'active_cameras': [True]},
    {'interpolation_mode': 'unsupported'},
    {'resolution': 8192, 'camera_count': 64, 'memory_budget_mb': 128},
])
def test_analyzer_validates_before_opening_media(monkeypatch, settings):
    def must_not_open(path):
        pytest.fail('Invalid settings must fail before media is opened')

    monkeypatch.setattr(cv2, 'VideoCapture', must_not_open)
    with pytest.raises(ValueError):
        BlurAnalyzer.analyze_sample('video.mp4', settings)


class SampleCapture:
    def __init__(self):
        self.released = False

    def isOpened(self):
        return True

    def get(self, prop):
        return 1

    def set(self, *args):
        return True

    def read(self):
        return True, np.zeros((20, 40, 3), np.uint8)

    def release(self):
        self.released = True


def test_analyzer_uses_validated_snapshot_and_cancellable_maps(monkeypatch):
    capture = SampleCapture()
    monkeypatch.setattr(cv2, 'VideoCapture', lambda path: capture)
    settings = {'resolution': 32, 'camera_count': 1}
    received = []
    original = GeometryProcessor.create_rectilinear_map

    def maps(*args, cancelled=None):
        received.append(args[2:4])
        assert callable(cancelled)
        return original(*args, cancelled=cancelled)

    def cancel_callback():
        settings['resolution'] = 8192
        return False

    monkeypatch.setattr(GeometryProcessor, 'create_rectilinear_map', maps)
    result = BlurAnalyzer.analyze_sample('video.mp4', settings, cancelled=cancel_callback)
    assert received == [(32, 32)]
    assert result['details'] == [('View_0', 0)]
    assert capture.released


def test_analyzer_cancellation_reaches_map_tiles(monkeypatch):
    capture = SampleCapture()
    monkeypatch.setattr(cv2, 'VideoCapture', lambda path: capture)
    original = GeometryProcessor.create_rectilinear_map
    in_map = False
    checks = 0

    def maps(*args, **kwargs):
        nonlocal in_map
        in_map = True
        return original(*args, **kwargs)

    def cancelled():
        nonlocal checks
        if in_map:
            checks += 1
        return checks == 2

    monkeypatch.setattr(GeometryProcessor, 'create_rectilinear_map', maps)
    with pytest.raises(InterruptedError, match='Projection cancelled'):
        BlurAnalyzer.analyze_sample('video.mp4', {'resolution': 768, 'camera_count': 1}, cancelled)
    assert checks == 2
    assert capture.released
