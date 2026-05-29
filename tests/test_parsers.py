"""
Unit tests for the pure-Python telemetry parsers (SRT and CAMM).

These intentionally avoid heavy dependencies (numpy/cv2/torch) so they can run
in a lightweight CI lint+test job.
"""
import unittest
import os
import struct
import sys

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from utils.srt_parser import parse_srt_data
from utils.camm_parser import parse_camm_data


class TestSRTParser(unittest.TestCase):
    """Tests for the DJI-style SRT subtitle GPS parser."""

    def test_bracket_format(self):
        raw = (
            b"1\n"
            b"00:00:00,000 --> 00:00:00,033\n"
            b"[latitude: 48.8566] [longitude: 2.3522] [altitude: 35.0]\n"
            b"\n"
            b"2\n"
            b"00:00:01,000 --> 00:00:01,033\n"
            b"[latitude: 48.8570] [longitude: 2.3530] [altitude: 36.5]\n"
        )
        samples = parse_srt_data(raw)
        self.assertEqual(len(samples), 2)
        self.assertAlmostEqual(samples[0]['lat'], 48.8566, places=4)
        self.assertAlmostEqual(samples[0]['lon'], 2.3522, places=4)
        self.assertAlmostEqual(samples[0]['alt'], 35.0, places=1)
        self.assertAlmostEqual(samples[0]['timestamp'], 0.0, places=3)
        self.assertAlmostEqual(samples[1]['timestamp'], 1.0, places=3)

    def test_gps_tuple_fallback(self):
        raw = (
            b"1\n"
            b"00:00:02,500 --> 00:00:02,533\n"
            b"GPS(40.7128, -74.0060, 10.0)\n"
        )
        samples = parse_srt_data(raw)
        self.assertEqual(len(samples), 1)
        self.assertAlmostEqual(samples[0]['lat'], 40.7128, places=4)
        self.assertAlmostEqual(samples[0]['lon'], -74.0060, places=4)
        self.assertAlmostEqual(samples[0]['timestamp'], 2.5, places=3)

    def test_garbage_returns_empty(self):
        self.assertEqual(parse_srt_data(b"not a valid srt"), [])

    def test_block_without_coords_skipped(self):
        raw = (
            b"1\n"
            b"00:00:00,000 --> 00:00:00,033\n"
            b"no coordinates here\n"
        )
        self.assertEqual(parse_srt_data(raw), [])


class TestCAMMParser(unittest.TestCase):
    """Tests for the Insta360-style binary CAMM GPS parser."""

    @staticmethod
    def _gps_packet(lat, lon, alt):
        # Header: reserved (H)=0, type (H)=6 (GPS). Payload: lat,lon (double), alt (float)
        return struct.pack('<HH', 0, 6) + struct.pack('<ddf', lat, lon, alt)

    def test_parse_two_gps_packets_with_duration(self):
        raw = self._gps_packet(48.8566, 2.3522, 35.0) + self._gps_packet(48.8570, 2.3530, 36.0)
        samples = parse_camm_data(raw, duration=2.0)
        self.assertEqual(len(samples), 2)
        self.assertAlmostEqual(samples[0]['lat'], 48.8566, places=4)
        self.assertAlmostEqual(samples[0]['lon'], 2.3522, places=4)
        self.assertAlmostEqual(samples[0]['timestamp'], 0.0, places=3)
        self.assertAlmostEqual(samples[1]['timestamp'], 1.0, places=3)  # (1/2) * 2.0

    def test_parse_without_duration_assumes_5hz(self):
        raw = self._gps_packet(10.0, 20.0, 0.0) + self._gps_packet(10.1, 20.1, 1.0)
        samples = parse_camm_data(raw)
        self.assertEqual(len(samples), 2)
        self.assertAlmostEqual(samples[0]['timestamp'], 0.0, places=3)
        self.assertAlmostEqual(samples[1]['timestamp'], 0.2, places=3)

    def test_null_island_is_filtered(self):
        # (0, 0) coordinates should be dropped by the parser's basic validation.
        raw = self._gps_packet(0.0, 0.0, 0.0) + self._gps_packet(48.85, 2.35, 30.0)
        samples = parse_camm_data(raw, duration=1.0)
        self.assertEqual(len(samples), 1)
        self.assertAlmostEqual(samples[0]['lat'], 48.85, places=2)

    def test_empty_input(self):
        self.assertEqual(parse_camm_data(b"", duration=1.0), [])


if __name__ == '__main__':
    unittest.main(verbosity=2)
