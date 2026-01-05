"""
Unit tests for 360 Extractor Pro
Tests for core functionality: geometry, parsers, and utilities.
"""
import unittest
import numpy as np
import os
import sys

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from core.geometry import GeometryProcessor
from utils.image_utils import ImageUtils
from utils.gpx_parser import parse_gpx_data


class TestGeometryProcessor(unittest.TestCase):
    """Tests for the GeometryProcessor class."""
    
    def test_generate_views_ring_6(self):
        """Test ring layout with 6 cameras."""
        views = GeometryProcessor.generate_views(6, pitch_offset=0, layout_mode='ring')
        
        self.assertEqual(len(views), 6)
        
        # Check yaw angles are evenly distributed
        yaws = [v[1] for v in views]
        expected_yaws = [0.0, 60.0, 120.0, 180.0, 240.0, 300.0]
        for yaw, expected in zip(yaws, expected_yaws):
            self.assertAlmostEqual(yaw, expected, places=1)
    
    def test_generate_views_cube(self):
        """Test cube layout always returns 6 views."""
        views = GeometryProcessor.generate_views(12, layout_mode='cube')
        
        self.assertEqual(len(views), 6)
        
        # Check names
        names = [v[0] for v in views]
        self.assertIn("Front", names)
        self.assertIn("Back", names)
        self.assertIn("Up", names)
        self.assertIn("Down", names)
    
    def test_generate_views_fibonacci(self):
        """Test fibonacci layout generates correct number of views."""
        for n in [4, 8, 16]:
            views = GeometryProcessor.generate_views(n, layout_mode='fibonacci')
            self.assertEqual(len(views), n)
    
    def test_generate_views_with_pitch_offset(self):
        """Test pitch offset is applied correctly."""
        views = GeometryProcessor.generate_views(4, pitch_offset=-20, layout_mode='ring')
        
        for name, yaw, pitch, roll in views:
            self.assertEqual(pitch, -20)
    
    def test_rotation_matrix_identity(self):
        """Test rotation matrix with zero angles is identity-like."""
        R = GeometryProcessor.get_rotation_matrix(0, 0, 0)
        
        self.assertEqual(R.shape, (3, 3))
        # Should be close to identity
        np.testing.assert_array_almost_equal(R, np.eye(3), decimal=5)
    
    def test_create_rectilinear_map_shape(self):
        """Test that rectilinear maps have correct shape."""
        map_x, map_y = GeometryProcessor.create_rectilinear_map(
            src_h=1080, src_w=2160,
            dest_h=512, dest_w=512,
            fov_deg=90, yaw_deg=0, pitch_deg=0, roll_deg=0
        )
        
        self.assertEqual(map_x.shape, (512, 512))
        self.assertEqual(map_y.shape, (512, 512))
        self.assertEqual(map_x.dtype, np.float32)
        self.assertEqual(map_y.dtype, np.float32)


class TestImageUtils(unittest.TestCase):
    """Tests for ImageUtils class."""
    
    def test_blur_score_sharp_image(self):
        """Test blur score on a sharp gradient image."""
        # Create a sharp edge image
        img = np.zeros((100, 100), dtype=np.uint8)
        img[:, 50:] = 255
        
        score = ImageUtils.calculate_blur_score(img)
        
        # Sharp edges should have high score
        self.assertGreater(score, 1000)
    
    def test_blur_score_blurry_image(self):
        """Test blur score on a uniform (very blurry) image."""
        # Uniform gray image has no edges
        img = np.ones((100, 100), dtype=np.uint8) * 128
        
        score = ImageUtils.calculate_blur_score(img)
        
        # No edges = score near 0
        self.assertLess(score, 1)
    
    def test_blur_score_none_image(self):
        """Test blur score returns 0 for None input."""
        score = ImageUtils.calculate_blur_score(None)
        self.assertEqual(score, 0.0)
    
    def test_blur_score_color_image(self):
        """Test blur score works on color images."""
        img = np.random.randint(0, 256, (100, 100, 3), dtype=np.uint8)
        
        score = ImageUtils.calculate_blur_score(img)
        
        self.assertIsInstance(score, float)
        self.assertGreaterEqual(score, 0)


class TestGPXParser(unittest.TestCase):
    """Tests for GPX parser."""
    
    def test_parse_valid_gpx(self):
        """Test parsing valid GPX data."""
        gpx_content = '''<?xml version="1.0" encoding="UTF-8"?>
        <gpx version="1.1" xmlns="http://www.topografix.com/GPX/1/1">
            <trk>
                <trkseg>
                    <trkpt lat="48.8566" lon="2.3522">
                        <ele>35.0</ele>
                        <time>2024-01-01T12:00:00Z</time>
                    </trkpt>
                    <trkpt lat="48.8570" lon="2.3530">
                        <ele>36.5</ele>
                        <time>2024-01-01T12:00:01Z</time>
                    </trkpt>
                </trkseg>
            </trk>
        </gpx>'''
        
        samples = parse_gpx_data(gpx_content)
        
        self.assertEqual(len(samples), 2)
        self.assertAlmostEqual(samples[0]['lat'], 48.8566, places=4)
        self.assertAlmostEqual(samples[0]['lon'], 2.3522, places=4)
        self.assertAlmostEqual(samples[0]['alt'], 35.0, places=1)
        self.assertEqual(samples[0]['timestamp'], 0.0)  # First point
        self.assertEqual(samples[1]['timestamp'], 1.0)  # 1 second later
    
    def test_parse_empty_gpx(self):
        """Test parsing GPX with no track points."""
        gpx_content = '''<?xml version="1.0" encoding="UTF-8"?>
        <gpx version="1.1" xmlns="http://www.topografix.com/GPX/1/1">
            <trk><trkseg></trkseg></trk>
        </gpx>'''
        
        samples = parse_gpx_data(gpx_content)
        
        self.assertEqual(len(samples), 0)
    
    def test_parse_invalid_xml(self):
        """Test parsing invalid XML returns empty list."""
        samples = parse_gpx_data("not valid xml")
        
        self.assertEqual(len(samples), 0)
    
    def test_parse_gpx_without_namespace(self):
        """Test parsing GPX 1.0 without namespace."""
        gpx_content = '''<?xml version="1.0" encoding="UTF-8"?>
        <gpx version="1.0">
            <trk>
                <trkseg>
                    <trkpt lat="40.7128" lon="-74.0060">
                        <ele>10.0</ele>
                        <time>2024-01-01T00:00:00Z</time>
                    </trkpt>
                </trkseg>
            </trk>
        </gpx>'''
        
        samples = parse_gpx_data(gpx_content)
        
        self.assertEqual(len(samples), 1)


class TestJobModel(unittest.TestCase):
    """Tests for Job dataclass."""
    
    def test_job_creation(self):
        """Test creating a job with default settings."""
        from core.job import Job
        
        job = Job(file_path="/path/to/video.mp4")
        
        self.assertEqual(job.file_path, "/path/to/video.mp4")
        self.assertEqual(job.status, "Pending")
        self.assertEqual(job.filename, "video.mp4")
    
    def test_job_settings_properties(self):
        """Test job property accessors."""
        from core.job import Job
        
        job = Job(
            file_path="/path/to/video.mp4",
            settings={
                'resolution': 4096,
                'adaptive_mode': True,
                'export_telemetry': True
            }
        )
        
        self.assertEqual(job.resolution, 4096)
        self.assertTrue(job.adaptive_mode)
        self.assertTrue(job.export_telemetry)
    
    def test_job_summary(self):
        """Test job summary generation."""
        from core.job import Job
        
        job = Job(
            file_path="/test.mp4",
            settings={'pitch_offset': -20, 'camera_count': 8}
        )
        
        summary = job.summary()
        
        self.assertIn("High", summary)
        self.assertIn("8", summary)


class TestSettingsManager(unittest.TestCase):
    """Tests for SettingsManager singleton."""
    
    def test_singleton_pattern(self):
        """Test that SettingsManager is a singleton."""
        from core.settings_manager import SettingsManager
        
        sm1 = SettingsManager()
        sm2 = SettingsManager()
        
        self.assertIs(sm1, sm2)
    
    def test_default_settings(self):
        """Test default settings structure is correct."""
        from core.settings_manager import SettingsManager
        
        # Check DEFAULT_SETTINGS directly (not loaded user settings)
        defaults = SettingsManager.DEFAULT_SETTINGS
        
        self.assertEqual(defaults['resolution'], 2048)
        self.assertEqual(defaults['fov'], 90)
        self.assertEqual(defaults['layout_mode'], 'ring')
        self.assertIn('naming_mode', defaults)
        self.assertIn('export_telemetry', defaults)
    
    def test_get_set(self):
        """Test get and set methods."""
        from core.settings_manager import SettingsManager
        
        sm = SettingsManager()
        
        sm.set('test_key', 'test_value')
        self.assertEqual(sm.get('test_key'), 'test_value')
        
        # Clean up
        del sm.settings['test_key']


if __name__ == '__main__':
    unittest.main(verbosity=2)
