"""
Unit tests for the COLMAP priors export (I1-N2).
"""
import json
import errno
import math
import os
import subprocess
import sys
import tempfile
import unittest

import numpy as np
import pytest

from extractor360.core import colmap_export, reconstruction
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
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.tmp = temporary.name
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
        self.assertEqual(files, {'cameras.txt', 'rig_rotations.json', 'reconstruct.sh', 'reconstruct.py', 'rig_config.json', 'README.txt'})

        with open(os.path.join(target, 'rig_rotations.json'), encoding='utf-8') as fh:
            rig = json.load(fh)
        self.assertEqual(len(rig['views']), 6)
        self.assertAlmostEqual(rig['intrinsics']['fx'], 32.0, places=5)

        script = open(os.path.join(target, 'reconstruct.sh'), encoding='utf-8').read()
        self.assertIn('reconstruct.py', script)
        with open(os.path.join(target, 'rig_config.json'), encoding='utf-8') as fh:
            config = json.load(fh)
        np.testing.assert_allclose(config[0]['cameras'][0]['camera_params'], [32, 32, 32, 32], atol=1e-8)
        self.assertTrue(os.access(os.path.join(target, 'reconstruct.sh'), os.X_OK))


if __name__ == '__main__':
    unittest.main(verbosity=2)


def test_reconstruction_stages_only_images_and_separate_masks(tmp_path):
    from extractor360.core.reconstruction import prepare
    (tmp_path/'photo.jpg').write_bytes(b'image')
    (tmp_path/'photo.jpg.mask.png').write_bytes(b'mask')
    (tmp_path/'images.jsonl').write_text(json.dumps({'image':'photo.jpg','mask':'photo.jpg.mask.png','camera':'Front','frame':7})+'\n')
    destination=prepare(tmp_path,tmp_path/'workspace')
    assert (destination/'images'/'Front'/'frame000000007.jpg').read_bytes()==b'image'
    assert (destination/'masks'/'Front'/'frame000000007.jpg.png').read_bytes()==b'mask'
    assert (destination/'images.txt').read_text()=='Front/frame000000007.jpg\n'


def write_index(dataset, entries):
    (dataset / 'images.jsonl').write_text(
        ''.join(json.dumps(entry) + '\n' for entry in entries), encoding='utf-8')


def record(**overrides):
    return dict(dict(image='photo.jpg', mask=None, camera='Front', frame=7), **overrides)


@pytest.mark.parametrize('bad', [
    [], None, {'image': 'photo.jpg'},
    dict(image='photo.jpg', camera='Front', frame=True),
    dict(image='photo.jpg', camera='Front', frame=1.9),
    dict(image='photo.jpg', camera='Front', frame=-1),
    dict(image='photo.jpg', camera='Front', frame='7'),
    dict(image='photo.jpg', camera='Front', frame=10**250),
    dict(image='photo.jpg', camera='../escape', frame=7),
    dict(image='photo.jpg', camera='nested/camera', frame=7),
    dict(image='photo.jpg', camera='nested\\camera', frame=7),
    dict(image='photo.jpg', camera='C:', frame=7),
    dict(image='photo.jpg', camera='NUL', frame=7),
    dict(image='photo.jpg', camera='Front\n', frame=7),
    dict(image='photo.jpg', camera='Front', frame=7, mask=[]),
    dict(image='missing.jpg', camera='Front', frame=7),
])
def test_index_schema_is_checked_completely_before_staging(tmp_path, bad):
    (tmp_path / 'photo.jpg').write_bytes(b'original')
    write_index(tmp_path, [record(), bad])
    destination = tmp_path / 'new' / 'workspace'
    with pytest.raises(ValueError):
        reconstruction.prepare(tmp_path, destination)
    assert not destination.parent.exists()
    assert (tmp_path / 'photo.jpg').read_bytes() == b'original'


@pytest.mark.parametrize('field', ['image', 'mask'])
@pytest.mark.parametrize('kind', ['absolute', 'parent', 'symlink', 'windows', 'backslash'])
def test_index_sources_cannot_leave_dataset(tmp_path, field, kind):
    dataset = tmp_path / 'dataset'
    dataset.mkdir()
    original = dataset / 'photo.jpg'
    original.write_bytes(b'dataset original')
    external = tmp_path / 'external.jpg'
    external.write_bytes(b'external sentinel')
    if kind == 'absolute':
        value = str(external)
    elif kind == 'parent':
        value = '../external.jpg'
    elif kind == 'windows':
        value = 'C:/external.jpg'
    elif kind == 'backslash':
        value = '..\\external.jpg'
    else:
        link = dataset / 'link.jpg'
        try:
            link.symlink_to(external)
        except OSError:
            pytest.skip('Symbolic links unavailable on this platform')
        value = 'link.jpg'
    bad = record()
    bad[field] = value
    write_index(dataset, [record(), bad])
    destination = dataset / 'new' / 'workspace'
    with pytest.raises(ValueError):
        reconstruction.prepare(dataset, destination)
    assert not destination.parent.exists()
    assert original.read_bytes() == b'dataset original'
    assert external.read_bytes() == b'external sentinel'


@pytest.mark.parametrize('second_camera,second_image', [('Front', 'second.jpg'), ('front', 'second.JPG')])
def test_duplicate_destination_never_changes_previously_linked_original(tmp_path, second_camera, second_image):
    original = tmp_path / 'photo.jpg'
    original.write_bytes(b'original sentinel')
    second = tmp_path / second_image
    second.write_bytes(b'different image')
    write_index(tmp_path, [record(), dict(image=second_image, camera=second_camera, frame=7)])
    destination = tmp_path / 'workspace'
    with pytest.raises(ValueError, match='Duplicate reconstruction destination'):
        reconstruction.prepare(tmp_path, destination)
    assert not destination.exists()
    assert original.read_bytes() == b'original sentinel'
    assert second.read_bytes() == b'different image'


def test_empty_index_does_not_allocate_workspace(tmp_path):
    write_index(tmp_path, [])
    with pytest.raises(ValueError, match='No exported images'):
        reconstruction.prepare(tmp_path, tmp_path / 'workspace')
    assert not (tmp_path / 'workspace').exists()


def test_internal_source_symlink_remains_confined_and_preserves_index_suffix(tmp_path):
    original = tmp_path / 'original.png'
    original.write_bytes(b'original')
    try:
        (tmp_path / 'photo.jpg').symlink_to(original)
    except OSError:
        pytest.skip('Symbolic links unavailable on this platform')
    write_index(tmp_path, [record()])
    destination = reconstruction.prepare(tmp_path, tmp_path / 'workspace')
    assert (destination / 'images' / 'Front' / 'frame000000007.jpg').read_bytes() == b'original'


def test_cross_device_hardlink_falls_back_to_exclusive_copy(tmp_path, monkeypatch):
    (tmp_path / 'photo.jpg').write_bytes(b'image')
    write_index(tmp_path, [record()])
    def cross_device(*args):
        raise OSError(errno.EXDEV, 'Cross-device link')
    monkeypatch.setattr(reconstruction.os, 'link', cross_device)
    destination = reconstruction.prepare(tmp_path, tmp_path / 'workspace')
    copied = destination / 'images' / 'Front' / 'frame000000007.jpg'
    assert copied.read_bytes() == b'image'
    assert not os.path.samefile(copied, tmp_path / 'photo.jpg')


def test_hardlink_collision_is_fatal_and_never_copies_over_original(tmp_path, monkeypatch):
    original = tmp_path / 'photo.jpg'
    original.write_bytes(b'original sentinel')
    (tmp_path / 'second.jpg').write_bytes(b'different image')
    write_index(tmp_path, [dict(image='second.jpg', camera='Front', frame=7)])
    link = os.link
    def existing_link(source, target):
        link(original, target)
        raise FileExistsError(errno.EEXIST, 'Already exists')
    monkeypatch.setattr(reconstruction.os, 'link', existing_link)
    with pytest.raises(FileExistsError):
        reconstruction.prepare(tmp_path, tmp_path / 'workspace')
    assert original.read_bytes() == b'original sentinel'


def test_copy_fallback_is_exclusive_even_if_target_appears(tmp_path, monkeypatch):
    original = tmp_path / 'photo.jpg'
    original.write_bytes(b'original sentinel')
    (tmp_path / 'second.jpg').write_bytes(b'different image')
    write_index(tmp_path, [dict(image='second.jpg', camera='Front', frame=7)])
    link = os.link
    def competing_target(source, target):
        link(original, target)
        raise OSError(errno.EXDEV, 'Cross-device link')
    monkeypatch.setattr(reconstruction.os, 'link', competing_target)
    with pytest.raises(FileExistsError):
        reconstruction.prepare(tmp_path, tmp_path / 'workspace')
    assert original.read_bytes() == b'original sentinel'


def test_invalid_final_mask_is_detected_before_any_staging(tmp_path):
    (tmp_path / 'photo.jpg').write_bytes(b'image')
    write_index(tmp_path, [record(), dict(image='photo.jpg', camera='Right', frame=7, mask='absent.png')])
    with pytest.raises(ValueError, match='record 2'):
        reconstruction.prepare(tmp_path, tmp_path / 'workspace')
    assert not (tmp_path / 'workspace').exists()


def test_rig_quaternions_match_independent_cube_axis_oracle(tmp_path):
    views = GeometryProcessor.generate_views(6, layout_mode='cube')
    expected = {
        'Right': [math.sqrt(.5), 0, -math.sqrt(.5), 0],
        'Left': [math.sqrt(.5), 0, math.sqrt(.5), 0],
        'Up': [math.sqrt(.5), -math.sqrt(.5), 0, 0],
        'Down': [math.sqrt(.5), math.sqrt(.5), 0, 0],
    }
    rotations = colmap_export.build_rig_rotations(views, set(expected), 90., 64)
    for view in rotations['views']:
        np.testing.assert_allclose(view['cam_from_rig_quat'], expected[view['name']], atol=1e-12)

    # A Right reference exercises the change of rig frame, which an identity
    # Front reference would hide. These are Hamilton products of the fixed
    # quarter-turn quaternions above, independent of the geometry helpers.
    colmap_export.write_colmap_export(str(tmp_path), views, {'Right', 'Up', 'Down'}, 90., 64)
    config = json.loads((tmp_path / 'colmap' / 'rig_config.json').read_text(encoding='utf-8'))
    cameras = config[0]['cameras']
    assert [c['image_prefix'] for c in cameras] == ['Right/', 'Up/', 'Down/']
    assert cameras[0]['ref_sensor'] is True
    np.testing.assert_allclose(cameras[1]['cam_from_rig_rotation'], [.5, -.5, .5, -.5], atol=1e-12)
    np.testing.assert_allclose(cameras[2]['cam_from_rig_rotation'], [.5, .5, .5, .5], atol=1e-12)
    assert all(camera['cam_from_rig_translation'] == [0, 0, 0] for camera in cameras[1:])


@pytest.fixture
def exported_runner(tmp_path, monkeypatch):
    views = GeometryProcessor.generate_views(6, layout_mode='cube')
    colmap_export.write_colmap_export(str(tmp_path), views, {'Right', 'Up'}, 90., 64)
    (tmp_path / 'photo.jpg').write_bytes(b'image')
    write_index(tmp_path, [dict(image='photo.jpg', camera='Right', frame=7)])
    monkeypatch.setattr(reconstruction, '__file__', str(tmp_path / 'colmap' / 'reconstruct.py'))
    destination = tmp_path / 'new' / 'workspace'
    monkeypatch.setattr(sys, 'argv', ['reconstruct.py', str(destination)])
    monkeypatch.setattr(reconstruction.shutil, 'which', lambda name: '/fake/colmap')
    return tmp_path, destination


@pytest.mark.parametrize('rig', [None, 'not JSON', '{}', '[]', '[{"cameras": []}]',
                                 '[{"cameras": [{"camera_params": [1, 1, 1, 1]}]}]'])
def test_invalid_rig_never_stages_images(exported_runner, rig):
    dataset, destination = exported_runner
    path = dataset / 'colmap' / 'rig_config.json'
    if rig is None:
        path.unlink()
    else:
        path.write_text(rig, encoding='utf-8')
    with pytest.raises((ValueError, OSError)):
        reconstruction.main()
    assert not destination.parent.exists()


def test_missing_colmap_never_stages_images(exported_runner, monkeypatch):
    _, destination = exported_runner
    monkeypatch.setattr(reconstruction.shutil, 'which', lambda name: None)
    with pytest.raises(FileNotFoundError, match='COLMAP'):
        reconstruction.main()
    assert not destination.parent.exists()


def test_index_camera_must_match_rig_before_staging(exported_runner):
    dataset, destination = exported_runner
    write_index(dataset, [record()])
    with pytest.raises(ValueError, match='missing from rig_config'):
        reconstruction.main()
    assert not destination.parent.exists()


def test_exported_standalone_runner_configures_rig_before_matching(exported_runner):
    dataset, destination = exported_runner
    script = dataset / 'colmap' / 'reconstruct.py'
    # Isolated Python cannot import the project or its site packages. Only the
    # external COLMAP calls are replaced; the exported runner stages real files.
    harness = '''import json, runpy, sys
namespace = runpy.run_path(sys.argv[1])
module = namespace['main'].__globals__
module['shutil'].which = lambda name: 'colmap'
module['subprocess'].run = lambda command, check: print(json.dumps(command))
sys.argv = sys.argv[1:]
namespace['main']()
'''
    result = subprocess.run([sys.executable, '-I', '-c', harness, str(script), str(destination)],
                            check=True, capture_output=True, text=True)
    commands = [json.loads(line) for line in result.stdout.splitlines()]
    assert [command[1] for command in commands] == [
        'feature_extractor', 'rig_configurator', 'sequential_matcher', 'mapper']
    feature = commands[0]
    np.testing.assert_allclose(
        [float(value) for value in feature[feature.index('--ImageReader.camera_params') + 1].split(',')], [32] * 4)
    assert feature[feature.index('--ImageReader.mask_path') + 1] == str(destination / 'masks')
    assert feature[feature.index('--ImageReader.single_camera_per_folder') + 1] == '1'
    assert commands[1][commands[1].index('--rig_config_path') + 1] == str(script.with_name('rig_config.json'))
    mapper = commands[-1]
    for option in ['focal_length', 'principal_point', 'extra_params', 'sensor_from_rig']:
        assert mapper[mapper.index('--Mapper.ba_refine_' + option) + 1] == '0'
    assert (destination / 'images.txt').read_text(encoding='utf-8') == 'Right/frame000000007.jpg\n'
    assert {path.name for path in (destination / 'images').iterdir()} == {'Right'}
