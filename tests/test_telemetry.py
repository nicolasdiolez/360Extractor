"""
Unit tests for TelemetryHandler GPS sample sanitization.
"""
import unittest

from core.telemetry import TelemetryHandler


def _sample(lat, lon, alt=0.0, ts=0.0):
    return {'lat': lat, 'lon': lon, 'alt': alt, 'timestamp': ts}


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


if __name__ == '__main__':
    unittest.main(verbosity=2)
