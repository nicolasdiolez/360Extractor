"""
Unit tests for CLI settings assembly (``core.settings_manager.build_settings``).

These guard against config keys being silently dropped or renamed between the
config file, the CLI, and what the processor actually reads — the class of bug
where, e.g., ``blur_threshold`` from the JSON never reached the processor and a
hard-coded default of 100.0 was used instead.
"""
import argparse
import builtins
import json
import os
import re
import sys
import unittest
from unittest.mock import MagicMock

import pytest

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from extractor360.core.settings_manager import SettingsManager, build_settings, normalize_mask_faces

SRC_DIR = os.path.join(os.path.dirname(__file__), '..', 'src')


def make_args(**overrides):
    """An argparse.Namespace with every CLI destination defaulted.

    Store-true flags default to False; everything else defaults to None, matching
    how argparse hands values to ``run_cli``.
    """
    defaults = dict(
        config=None, input=None, output=None,
        interval=None, format=None,
        ai=False, ai_mask=False, ai_skip=False,
        camera_count=None, quality=None, active_cameras=None,
        resolution=None, layout=None, flat=False,
        adaptive=False, motion_threshold=None,
        export_telemetry=False, altitude_mode=None,
        targets=None, custom_classes=None, ai_mask_cameras=None,
        ai_model=None, nadir_mask=False, nadir_radius=None,
        naming_mode=None, image_pattern=None, mask_pattern=None,
    )
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


def processor_setting_keys():
    """Every key read via ``settings.get('...')`` in the processor / job modules."""
    keys = set()
    pattern = re.compile(r"settings\.get\(\s*['\"]([a-zA-Z_0-9]+)['\"]")
    for rel in ('extractor360/core/processor.py', 'extractor360/core/job.py'):
        with open(os.path.join(SRC_DIR, rel), encoding='utf-8') as fh:
            keys.update(pattern.findall(fh.read()))
    return keys


class TestBuildSettings(unittest.TestCase):
    """Tests for the defaults < config < CLI precedence and key coverage."""

    def test_every_processor_key_is_provided(self):
        """The settings dict must contain every key the processor reads.

        Regression guard for the dropped-key bug: a key the processor reads
        (e.g. 'blur_threshold' or 'interpolation_mode') must never be absent and
        silently fall back to a hard-coded default inside the processor.
        """
        settings = build_settings(make_args(), config={})
        missing = processor_setting_keys() - set(settings)
        self.assertEqual(
            missing, set(),
            f"settings is missing keys the processor reads: {sorted(missing)}"
        )

    def test_config_overrides_defaults(self):
        """Values present in the config file must reach the settings dict."""
        config = {
            'blur_threshold': 27.0,
            'interpolation_mode': 'lanczos',
            'interval_value': 8,
            'interval_unit': 'Frames',
            'camera_count': 10,
        }
        settings = build_settings(make_args(), config=config)
        self.assertEqual(settings['blur_threshold'], 27.0)
        self.assertEqual(settings['interpolation_mode'], 'lanczos')
        self.assertEqual(settings['interval_value'], 8)
        self.assertEqual(settings['interval_unit'], 'Frames')
        self.assertEqual(settings['camera_count'], 10)

    def test_omitted_key_uses_documented_default(self):
        """An omitted key falls back to the DEFAULT_SETTINGS value, not a surprise."""
        settings = build_settings(make_args(), config={})
        self.assertEqual(
            settings['blur_threshold'],
            SettingsManager.DEFAULT_SETTINGS['blur_threshold'],
        )

    def test_cli_overrides_config(self):
        """Explicit CLI arguments win over the config file."""
        config = {'resolution': 2048, 'camera_count': 10}
        settings = build_settings(make_args(resolution=4096, camera_count=6), config=config)
        self.assertEqual(settings['resolution'], 4096)
        self.assertEqual(settings['camera_count'], 6)

    def test_cli_interval_overrides_in_seconds(self):
        """--interval is in seconds and overrides the config cadence."""
        config = {'interval_value': 8, 'interval_unit': 'Frames'}
        settings = build_settings(make_args(interval=2.0), config=config)
        self.assertEqual(settings['interval_value'], 2.0)
        self.assertEqual(settings['interval_unit'], 'Seconds')

    def test_legacy_interval_and_format_aliases(self):
        """Older config files used 'interval' and 'format' rather than the
        'interval_value' / 'output_format' keys."""
        config = {'interval': 2.0, 'format': 'png'}
        settings = build_settings(make_args(), config=config)
        self.assertEqual(settings['interval_value'], 2.0)
        self.assertEqual(settings['output_format'], 'png')

    def test_active_cameras_and_output_passthrough(self):
        settings = build_settings(
            make_args(), config={}, active_cameras=[0, 1, 2], output_path='/tmp/out'
        )
        self.assertEqual(settings['active_cameras'], [0, 1, 2])
        self.assertEqual(settings['custom_output_dir'], '/tmp/out')

    def test_targets_flag_sets_detection(self):
        settings = build_settings(make_args(targets='humans,vehicles'), config={})
        self.assertTrue(settings['ai_detect_humans'])
        self.assertTrue(settings['ai_detect_vehicles'])
        self.assertFalse(settings['ai_detect_plants'])

    def test_ai_mode_flags_and_legacy_boolean(self):
        self.assertEqual(build_settings(make_args(ai_skip=True), {})['ai_mode'], 'Skip Frame')
        self.assertEqual(build_settings(make_args(ai_mask=True), {})['ai_mode'], 'Generate Mask')
        # Legacy boolean 'ai' key in an older config still enables masking.
        self.assertEqual(build_settings(make_args(), {'ai': True})['ai_mode'], 'Generate Mask')

    def test_ai_mask_cameras_default_is_empty(self):
        """No selection => empty list, i.e. mask every face (current behavior)."""
        self.assertEqual(build_settings(make_args(), config={})['ai_mask_cameras'], [])

    def test_ai_mask_cameras_cli_parsing(self):
        """The CLI accepts a comma-separated face list, trimmed into a clean list."""
        settings = build_settings(make_args(ai_mask_cameras=' Down , Back '), config={})
        self.assertEqual(settings['ai_mask_cameras'], ['Down', 'Back'])

    def test_ai_mask_cameras_cli_overrides_config(self):
        settings = build_settings(
            make_args(ai_mask_cameras='Down'), config={'ai_mask_cameras': ['Front', 'Back']}
        )
        self.assertEqual(settings['ai_mask_cameras'], ['Down'])

    def test_ai_mask_cameras_config_string_normalized_to_list(self):
        """A config value stored as a string is normalized to a list."""
        settings = build_settings(make_args(), config={'ai_mask_cameras': 'Up, Down'})
        self.assertEqual(settings['ai_mask_cameras'], ['Up', 'Down'])

    def test_ai_mask_cameras_config_list_passthrough(self):
        settings = build_settings(make_args(), config={'ai_mask_cameras': ['Back']})
        self.assertEqual(settings['ai_mask_cameras'], ['Back'])

    def test_ai_model_default_and_cli_override(self):
        """The segmentation model defaults to nano and is overridable via CLI."""
        self.assertEqual(
            build_settings(make_args(), config={})['ai_model'],
            SettingsManager.DEFAULT_SETTINGS['ai_model'],
        )
        self.assertEqual(build_settings(make_args(ai_model='l'), config={})['ai_model'], 'l')
        # CLI wins over the config file.
        settings = build_settings(make_args(ai_model='x'), config={'ai_model': 'n'})
        self.assertEqual(settings['ai_model'], 'x')

    def test_nadir_mask_flag_and_radius(self):
        """--nadir-mask enables the disc; --nadir-radius sets its size."""
        self.assertFalse(build_settings(make_args(), config={})['nadir_mask_enabled'])
        settings = build_settings(make_args(nadir_mask=True, nadir_radius=55.0), config={})
        self.assertTrue(settings['nadir_mask_enabled'])
        self.assertEqual(settings['nadir_mask_radius'], 55.0)

    def test_nadir_radius_config_default(self):
        """Config value is used when the CLI omits --nadir-radius."""
        settings = build_settings(make_args(), config={'nadir_mask_radius': 25.0})
        self.assertEqual(settings['nadir_mask_radius'], 25.0)


class TestNormalizeMaskFaces(unittest.TestCase):
    """Tests for the per-face masking scope helper used by the processor."""

    def test_empty_means_all_faces(self):
        # None/empty => None sentinel => the processor masks every face.
        self.assertIsNone(normalize_mask_faces(None))
        self.assertIsNone(normalize_mask_faces([]))
        self.assertIsNone(normalize_mask_faces(""))
        self.assertIsNone(normalize_mask_faces(["", "  "]))

    def test_list_lowercased_set(self):
        self.assertEqual(normalize_mask_faces(["Down", "Back"]), {"down", "back"})

    def test_string_parsed_and_trimmed(self):
        self.assertEqual(normalize_mask_faces(" Down , Back "), {"down", "back"})

    def test_membership_is_case_insensitive(self):
        faces = normalize_mask_faces(["Down"])
        self.assertIn("down", faces)
        # The processor compares name.lower() in faces, so casing never matters.
        self.assertIn("Down".lower(), faces)


if __name__ == '__main__':
    unittest.main()


def test_load_config_reads_real_utf8_under_non_utf8_default(tmp_path, monkeypatch):
    from extractor360 import main as cli

    value = {'input': str(tmp_path / 'Vidéos' / 'été.mp4')}
    config = tmp_path / 'réglages.json'
    config.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')
    encodings = []

    def legacy_locale_open(path, mode='r', *args, encoding=None, **kwargs):
        encodings.append(encoding)
        return builtins.open(path, mode, *args, encoding=encoding or 'cp1252', **kwargs)

    monkeypatch.setattr(cli, 'open', legacy_locale_open, raising=False)
    assert cli.load_config(config) == value
    assert encodings == ['utf-8']


@pytest.mark.parametrize('active', [[True], [1.9], {}, 1, True, [], '0,1'])
def test_run_cli_rejects_invalid_json_camera_types_before_work(tmp_path, monkeypatch, active):
    from extractor360 import main as cli

    source = tmp_path / 'source.png'
    source.write_bytes(b'not decoded during validation')
    destination = tmp_path / 'new' / 'output'
    config = tmp_path / 'settings.json'
    config.write_text(json.dumps({'input': str(source), 'output': str(destination),
                                 'active_cameras': active}), encoding='utf-8')
    worker = MagicMock()
    monkeypatch.setattr(cli, 'ProcessingWorker', worker)
    with pytest.raises(SystemExit) as rejected:
        cli.run_cli(make_args(config=str(config)))
    assert rejected.value.code == 2
    worker.assert_not_called()
    assert not destination.parent.exists()


@pytest.mark.parametrize('active', ['true', '1.9', '', '0,'])
def test_run_cli_rejects_invalid_camera_option_without_output(tmp_path, monkeypatch, active):
    from extractor360 import main as cli

    source = tmp_path / 'source.png'
    source.write_bytes(b'fixture')
    destination = tmp_path / 'new' / 'output'
    worker = MagicMock()
    monkeypatch.setattr(cli, 'ProcessingWorker', worker)
    with pytest.raises(SystemExit) as rejected:
        cli.run_cli(make_args(input=str(source), output=str(destination), active_cameras=active))
    assert rejected.value.code == 2
    worker.assert_not_called()
    assert not destination.parent.exists()


def test_run_cli_camera_option_overrides_json_without_coercing_it(tmp_path, monkeypatch):
    from extractor360 import main as cli

    source = tmp_path / 'source.png'
    source.write_bytes(b'fixture')
    config = tmp_path / 'settings.json'
    config.write_text(json.dumps({'input': str(source), 'active_cameras': [True]}), encoding='utf-8')
    worker = MagicMock()
    worker.return_value.error_count = 0
    monkeypatch.setattr(cli, 'ProcessingWorker', worker)
    monkeypatch.setattr(cli, 'TQDM_AVAILABLE', False)
    cli.run_cli(make_args(config=str(config), output=str(tmp_path / 'output'), active_cameras=' 0, 2 '))
    jobs = worker.call_args.args[0]
    assert jobs[0].settings['active_cameras'] == [0, 2]
    worker.return_value.run.assert_called_once_with()
