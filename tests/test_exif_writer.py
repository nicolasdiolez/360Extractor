"""
Unit tests for the calibration EXIF writer (I1-N1) and GPS heading.
"""
import os
import tempfile
import unittest
from datetime import datetime

import numpy as np
import piexif

from extractor360.core import exif_writer
from extractor360.core.telemetry import TelemetryHandler


class TestFocalMath(unittest.TestCase):
    def test_focal_35mm_from_fov(self):
        # FOV 90deg on a 36mm-wide reference frame -> 18mm.
        self.assertAlmostEqual(exif_writer.focal_35mm_from_fov(90.0), 18.0, places=6)
        # Narrower FOV -> longer focal.
        self.assertGreater(exif_writer.focal_35mm_from_fov(60.0), 18.0)

    def test_focal_px_from_fov(self):
        # FOV 90deg -> f = W/2.
        self.assertAlmostEqual(exif_writer.focal_px_from_fov(90.0, 2048), 1024.0, places=6)


class TestBuildAndSave(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.img = np.full((24, 32, 3), 128, dtype=np.uint8)

    def test_full_exif_roundtrip_jpg(self):
        path = os.path.join(self.tmp, 'x.jpg')
        dt = datetime(2026, 7, 13, 10, 0, 5, 250000)
        exif = exif_writer.build_exif_bytes(
            fov_deg=90, capture_dt=dt, gps=(48.85, 2.35, 35.0),
            heading_deg=123.4, camera_model="Virtual Pinhole 90deg",
        )
        self.assertTrue(exif_writer.save_image_with_exif(path, self.img, None, exif))

        loaded = piexif.load(path)
        self.assertEqual(loaded['0th'][piexif.ImageIFD.Make], b'360Extractor')
        self.assertEqual(loaded['0th'][piexif.ImageIFD.Model], b'Virtual Pinhole 90deg')
        self.assertIn(b'360 Extractor', loaded['0th'][piexif.ImageIFD.Software])

        self.assertEqual(loaded['Exif'][piexif.ExifIFD.FocalLengthIn35mmFilm], 18)
        num, den = loaded['Exif'][piexif.ExifIFD.FocalLength]
        self.assertAlmostEqual(num / den, 18.0, places=3)
        self.assertEqual(loaded['Exif'][piexif.ExifIFD.DateTimeOriginal], b'2026:07:13 10:00:05')
        self.assertEqual(loaded['Exif'][piexif.ExifIFD.SubSecTimeOriginal], b'250')

        num, den = loaded['GPS'][piexif.GPSIFD.GPSImgDirection]
        self.assertAlmostEqual(num / den, 123.4, places=1)
        self.assertEqual(loaded['GPS'][piexif.GPSIFD.GPSImgDirectionRef], b'T')

    def test_partial_blocks_are_optional(self):
        """Intrinsics without GPS, and GPS without intrinsics, both valid."""
        only_focal = exif_writer.build_exif_bytes(fov_deg=90, camera_model="Virtual Pinhole 90deg")
        only_gps = exif_writer.build_exif_bytes(gps=(1.0, 2.0, 3.0))
        for blob in (only_focal, only_gps):
            path = os.path.join(self.tmp, f'p{len(blob)}.jpg')
            self.assertTrue(exif_writer.save_image_with_exif(path, self.img, None, blob))

        loaded = piexif.load(os.path.join(self.tmp, f'p{len(only_gps)}.jpg'))
        self.assertNotIn(piexif.ExifIFD.FocalLengthIn35mmFilm, loaded['Exif'])
        self.assertIn(piexif.GPSIFD.GPSLatitude, loaded['GPS'])

    def test_heading_wraps_modulo_360(self):
        exif = exif_writer.build_exif_bytes(gps=(1.0, 2.0, 0.0), heading_deg=450.0)
        path = os.path.join(self.tmp, 'wrap.jpg')
        exif_writer.save_image_with_exif(path, self.img, None, exif)
        num, den = piexif.load(path)['GPS'][piexif.GPSIFD.GPSImgDirection]
        self.assertAlmostEqual(num / den, 90.0, places=2)

    def test_heading_just_below_360_stays_in_range(self):
        """359.9999 must store as 0.0, never round up to 360 (EXIF range [0,360))."""
        exif = exif_writer.build_exif_bytes(gps=(1.0, 2.0, 0.0), heading_deg=359.9999)
        path = os.path.join(self.tmp, 'edge.jpg')
        exif_writer.save_image_with_exif(path, self.img, None, exif)
        num, den = piexif.load(path)['GPS'][piexif.GPSIFD.GPSImgDirection]
        self.assertLess(num / den, 360.0)
        self.assertAlmostEqual(num / den, 0.0, places=2)


class TestHeadingFromTrack(unittest.TestCase):
    def _handler(self, samples):
        h = TelemetryHandler()
        h.gps_samples = TelemetryHandler._sanitize_gps_samples(samples)
        h.has_gps = bool(h.gps_samples)
        return h

    def test_heading_east(self):
        h = self._handler([
            {'lat': 48.0, 'lon': 2.0000, 'alt': 0.0, 'timestamp': 0.0},
            {'lat': 48.0, 'lon': 2.0010, 'alt': 0.0, 'timestamp': 10.0},
        ])
        heading = h.get_heading_at_time(5.0)
        self.assertIsNotNone(heading)
        self.assertAlmostEqual(heading, 90.0, delta=1.0)

    def test_heading_north(self):
        self.assertAlmostEqual(
            TelemetryHandler._bearing_deg(48.0, 2.0, 48.001, 2.0), 0.0, places=3
        )

    def test_stationary_returns_none(self):
        h = self._handler([
            {'lat': 48.0, 'lon': 2.0, 'alt': 0.0, 'timestamp': 0.0},
            {'lat': 48.0, 'lon': 2.0, 'alt': 0.0, 'timestamp': 10.0},
        ])
        self.assertIsNone(h.get_heading_at_time(5.0))

    def test_no_gps_returns_none(self):
        self.assertIsNone(TelemetryHandler().get_heading_at_time(1.0))


if __name__ == '__main__':
    unittest.main(verbosity=2)
