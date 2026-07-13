"""
Unit tests for TelemetryHandler GPS sample sanitization and EXIF writing.
"""
import os
import tempfile
import unittest

import numpy as np
from PIL import Image
from PIL.ExifTags import IFD

from core.telemetry import TelemetryHandler


def _sample(lat, lon, alt=0.0, ts=0.0):
    return {'lat': lat, 'lon': lon, 'alt': alt, 'timestamp': ts}


def _read_gps(path):
    """Read (lat, lon, alt) back from an image's EXIF via Pillow (signed)."""
    exif = Image.open(path).getexif()
    gps = exif.get_ifd(IFD.GPSInfo)

    def to_deg(dms, ref):
        deg = float(dms[0]) + float(dms[1]) / 60 + float(dms[2]) / 3600
        return -deg if ref in ('S', 'W', b'S', b'W') else deg

    lat = to_deg(gps[2], gps[1])
    lon = to_deg(gps[4], gps[3])
    alt = float(gps[6])
    if gps.get(5) in (1, b'\x01'):
        alt = -alt
    return lat, lon, alt


class TestSanitizeGPSSamples(unittest.TestCase):
    """Tests for TelemetryHandler._sanitize_gps_samples."""

    def test_keeps_valid_samples_sorted_by_timestamp(self):
        samples = [
            _sample(48.8570, 2.3530, 36.5, 2.0),
            _sample(48.8566, 2.3522, 35.0, 1.0),
        ]
        out = TelemetryHandler._sanitize_gps_samples(samples)

        self.assertEqual(len(out), 2)
        self.assertEqual([s['timestamp'] for s in out], [1.0, 2.0])

    def test_drops_null_island_no_fix_placeholder(self):
        """(0,0) samples (device without GPS fix) must be rejected."""
        samples = [
            _sample(0.0, 0.0, 0.0, 0.0),
            _sample(48.8566, 2.3522, 35.0, 1.0),
        ]
        out = TelemetryHandler._sanitize_gps_samples(samples)

        self.assertEqual(len(out), 1)
        self.assertAlmostEqual(out[0]['lat'], 48.8566, places=4)

    def test_keeps_equator_and_prime_meridian_crossings(self):
        """Only the exact (0,0) placeholder is dropped, not lat=0 or lon=0 alone."""
        samples = [
            _sample(0.0, 6.6, 0.0, 0.0),    # Gulf of Guinea, on the equator
            _sample(51.4779, 0.0, 45.0, 1.0),  # Greenwich, on the prime meridian
        ]
        out = TelemetryHandler._sanitize_gps_samples(samples)

        self.assertEqual(len(out), 2)

    def test_drops_out_of_range_and_non_finite(self):
        samples = [
            _sample(91.0, 0.0),
            _sample(0.0, -190.0),
            _sample(float('nan'), 2.0),
            _sample(10.0, float('inf')),
        ]
        out = TelemetryHandler._sanitize_gps_samples(samples)

        self.assertEqual(out, [])

    def test_drops_missing_or_invalid_keys(self):
        self.assertEqual(TelemetryHandler._sanitize_gps_samples([{'lat': 1.0}]), [])
        self.assertEqual(TelemetryHandler._sanitize_gps_samples([{'lat': 'x', 'lon': 'y'}]), [])
        self.assertEqual(TelemetryHandler._sanitize_gps_samples(None), [])
        self.assertEqual(TelemetryHandler._sanitize_gps_samples([]), [])


class TestSaveImageWithGps(unittest.TestCase):
    """Round-trip tests for the single-write in-memory EXIF path (B22).

    Would have caught the negative-altitude bug of 3.1.0 before users, and now
    guards the in-memory JPEG insert + the array->Pillow PNG/TIFF path.
    """

    def setUp(self):
        self.handler = TelemetryHandler()
        self.tmp = tempfile.mkdtemp()
        # Distinct per channel so a BGR<->RGB swap would be caught.
        self.img = np.zeros((32, 48, 3), dtype=np.uint8)
        self.img[..., 0] = 200  # B
        self.img[..., 1] = 120  # G
        self.img[..., 2] = 40   # R

    def _params(self, ext):
        import cv2
        if ext == '.jpg':
            return [cv2.IMWRITE_JPEG_QUALITY, 95]
        if ext == '.png':
            return [cv2.IMWRITE_PNG_COMPRESSION, 3]
        return [cv2.IMWRITE_TIFF_COMPRESSION, 1]

    def test_gps_roundtrip_all_formats(self):
        for ext in ('.jpg', '.png', '.tif'):
            with self.subTest(ext=ext):
                path = os.path.join(self.tmp, f'img{ext}')
                ok = self.handler.save_image_with_gps(
                    path, self.img, self._params(ext), 48.8566, 2.3522, 35.0
                )
                self.assertTrue(ok, f"save failed for {ext}")
                lat, lon, alt = _read_gps(path)
                self.assertAlmostEqual(lat, 48.8566, places=3)
                self.assertAlmostEqual(lon, 2.3522, places=3)
                self.assertAlmostEqual(alt, 35.0, places=1)

    def test_negative_altitude_and_south_west(self):
        """Below-sea-level altitude + southern/western hemisphere round-trip."""
        path = os.path.join(self.tmp, 'neg.jpg')
        self.handler.save_image_with_gps(path, self.img, self._params('.jpg'), -33.8688, -151.2093, -12.5)
        lat, lon, alt = _read_gps(path)
        self.assertAlmostEqual(lat, -33.8688, places=3)
        self.assertAlmostEqual(lon, -151.2093, places=3)
        self.assertAlmostEqual(alt, -12.5, places=1)

    def test_lossless_formats_preserve_pixels(self):
        """PNG/TIFF are lossless: the written pixels must equal the input (BGR)."""
        import cv2
        for ext in ('.png', '.tif'):
            with self.subTest(ext=ext):
                path = os.path.join(self.tmp, f'lossless{ext}')
                self.handler.save_image_with_gps(path, self.img, self._params(ext), 1.0, 2.0, 3.0)
                back = cv2.cvtColor(np.array(Image.open(path).convert('RGB')), cv2.COLOR_RGB2BGR)
                self.assertTrue(np.array_equal(back, self.img))


if __name__ == '__main__':
    unittest.main(verbosity=2)
