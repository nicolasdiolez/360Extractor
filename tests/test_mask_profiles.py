"""Check destination contracts against written pixels, names and manifests."""
import json
from pathlib import Path

import cv2
import numpy as np
import pytest

from extractor360.core.job import Job
from extractor360.core.processor import ProcessingWorker
from extractor360.core.validation import validate_settings


@pytest.mark.parametrize('format,extension', [('jpg', '.jpg'), ('png', '.png'), ('tiff', '.tif')])
@pytest.mark.parametrize('profile,ignored,mask_suffix', [
    ('realityscan', 0, '{ext}.mask.png'),
    ('colmap', 0, '{ext}.png'),
    ('postshot', 255, '.mask.png'),
])
def test_written_mask_contract(tmp_path, format, extension, profile, ignored, mask_suffix):
    source = tmp_path / 'panorama.jpg'
    cv2.imwrite(str(source), np.full((64, 128, 3), 127, np.uint8))
    original = source.read_bytes()
    job = Job(str(source), settings={
        'resolution': 64, 'layout_mode': 'cube', 'active_cameras': [5],
        'nadir_mask_enabled': True, 'mask_profile': profile,
        'exif_intrinsics': False, 'output_format': format,
    })
    worker = ProcessingWorker([job])
    worker.run()
    assert worker.error_count == 0
    out = Path(job.result['output_dir'])
    record = json.loads((out / 'images.jsonl').read_text())
    assert record['image'] == 'panorama_frame000000_Down' + extension
    assert record['mask'] == 'panorama_frame000000_Down' + mask_suffix.format(ext=extension)
    mask = cv2.imread(str(out / record['mask']), cv2.IMREAD_GRAYSCALE)
    assert mask.shape == (64, 64)
    assert mask[32, 32] == ignored
    assert mask[0, 0] == 255 - ignored
    manifest = json.loads((out / 'manifest.json').read_text())
    assert manifest['mask_contract']['ignored_value'] == ignored
    assert manifest['mask_contract']['profile'] == profile
    assert manifest['mask_contract']['meaning'] == 'ignore_observation'
    assert source.read_bytes() == original


def test_postshot_refuses_colmap_before_outputs_or_model(tmp_path, monkeypatch):
    source = tmp_path / 'pano.jpg'
    source.write_bytes(b'not read')
    target = tmp_path / 'must-not-exist'
    def forbidden(*args):
        pytest.fail('Invalid mask contract loaded a model')
    monkeypatch.setattr(ProcessingWorker, '_ensure_ai_service', forbidden)
    job = Job(str(source), settings={'mask_profile': 'postshot', 'export_colmap': True,
                                     'ai_mode': 'Generate Mask', 'custom_output_dir': str(target)})
    worker = ProcessingWorker([job])
    worker.run()
    assert worker.error_count == 1
    assert 'separate run' in job.result['error']
    assert not target.exists()


def test_custom_preserves_manual_conventions():
    settings = validate_settings({'naming_mode': 'custom', 'ai_invert_mask': False,
                                  'mask_pattern': '{image_name}.custom.png'})
    assert settings['mask_profile'] == 'custom'
    assert settings['ai_invert_mask'] is False
    assert settings['naming_mode'] == 'custom'
    assert settings['mask_pattern'] == '{image_name}.custom.png'


def test_cli_mask_profile_overrides_saved_profile(monkeypatch):
    from extractor360.main import parse_arguments
    from extractor360.core.settings_manager import build_settings
    monkeypatch.setattr('sys.argv', ['360extractor', '--mask-profile', 'postshot'])
    settings = validate_settings(build_settings(parse_arguments(), {'mask_profile': 'colmap'}))
    assert settings['mask_profile'] == settings['naming_mode'] == 'postshot'
    assert settings['ai_invert_mask'] is False
