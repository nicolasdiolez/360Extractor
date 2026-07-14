"""
Unit tests for the COLMAP priors export (I1-N2).
"""
import json
import os
import tempfile
import unittest

import numpy as np

from extractor360.core import colmap_export
from extractor360.core.geometry import GeometryProcessor


class TestQuaternionMath(unittest.TestCase):
    def test_identity(self):
        q = colmap_export.rotation_matrix_to_quat(np.eye(3))
        np.testing.assert_allclose(q, [1.0, 0.0, 0.0, 0.0], atol=1e-12)

    def test_roundtrip_all_cube_views(self):
        """matrix -> quat -> matrix must be lossless for every rig rotation."""
        views = GeometryProcessor.generate_views(6, layout_mode='cube')
        views += GeometryProcessor.generate_views(9, pitch_offset=-20, layout_mode='fibonacci')
        for name, yaw, pitch, roll in views:
            with self.subTest(view=name):
                R = GeometryProcessor.get_rotation_matrix(yaw, pitch, roll).T
                q = colmap_export.rotation_matrix_to_quat(R)
                self.assertAlmostEqual(sum(v * v for v in q), 1.0, places=12)
                self.assertGreaterEqual(q[0], 0.0)  # canonical form
                back = colmap_export.quat_to_rotation_matrix(q)
                np.testing.assert_allclose(back, R, atol=1e-9)


class TestExportedFiles(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.views = GeometryProcessor.generate_views(6, layout_mode='cube')
        self.names = {v[0] for v in self.views}

    def test_cameras_txt_exact_pinhole(self):
        txt = colmap_export.build_cameras_txt(90.0, 64)
        line = [line for line in txt.splitlines() if not line.startswith('#')][0]
        parts = line.split()
        self.assertEqual(parts[1], 'PINHOLE')
        self.assertEqual(parts[2:4], ['64', '64'])
        # FOV 90deg -> f = W/2 = 32; principal point at the center.
        self.assertAlmostEqual(float(parts[4]), 32.0, places=5)
        self.assertAlmostEqual(float(parts[5]), 32.0, places=5)
        self.assertAlmostEqual(float(parts[6]), 32.0, places=5)
        self.assertAlmostEqual(float(parts[7]), 32.0, places=5)

    def test_rig_rotations_respects_active_views(self):
        rig = colmap_export.build_rig_rotations(self.views, {'Front', 'Down'}, 90.0, 64)
        names = [v['name'] for v in rig['views']]
        self.assertEqual(sorted(names), ['Down', 'Front'])
        front = next(v for v in rig['views'] if v['name'] == 'Front')
        np.testing.assert_allclose(front['cam_from_rig_quat'], [1, 0, 0, 0], atol=1e-12)

    def test_write_colmap_export(self):
        ok = colmap_export.write_colmap_export(self.tmp, self.views, self.names, 90.0, 64)
        self.assertTrue(ok)
        target = os.path.join(self.tmp, 'colmap')
        files = set(os.listdir(target))
        self.assertEqual(files, {'cameras.txt', 'rig_rotations.json', 'reconstruct.sh', 'README.txt'})

        with open(os.path.join(target, 'rig_rotations.json'), encoding='utf-8') as fh:
            rig = json.load(fh)
        self.assertEqual(len(rig['views']), 6)
        self.assertAlmostEqual(rig['intrinsics']['fx'], 32.0, places=5)

        script = open(os.path.join(target, 'reconstruct.sh'), encoding='utf-8').read()
        self.assertIn('--ImageReader.camera_params "32.000000,32.000000,32.000000,32.000000"', script)
        self.assertIn('--Mapper.ba_refine_focal_length 0', script)
        self.assertTrue(os.access(os.path.join(target, 'reconstruct.sh'), os.X_OK))


if __name__ == '__main__':
    unittest.main(verbosity=2)
