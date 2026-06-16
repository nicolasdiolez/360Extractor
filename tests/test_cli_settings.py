"""
Unit tests for CLI settings assembly (``core.settings_manager.build_settings``).

These guard against config keys being silently dropped or renamed between the
config file, the CLI, and what the processor actually reads — the class of bug
where, e.g., ``blur_threshold`` from the JSON never reached the processor and a
hard-coded default of 100.0 was used instead.
"""
import argparse
import os
import re
import sys
import unittest

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from core.settings_manager import SettingsManager, build_settings

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
        targets=None, custom_classes=None,
        naming_mode=None, image_pattern=None, mask_pattern=None,
    )
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


def processor_setting_keys():
    """Every key read via ``settings.get('...')`` in the processor / job modules."""
    keys = set()
    pattern = re.compile(r"settings\.get\(\s*['\"]([a-zA-Z_0-9]+)['\"]")
    for rel in ('core/processor.py', 'core/job.py'):
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


if __name__ == '__main__':
    unittest.main()
