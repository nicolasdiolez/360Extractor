import json
from pathlib import Path
from unittest.mock import patch

import cv2
import numpy as np
import pytest

from extractor360.core.job import Job
from extractor360.core.output_plan import discover_media
from extractor360.core.processor import ProcessingWorker
from extractor360.core.validation import validate_settings
from extractor360.utils.file_manager import FileManager


def source(tmp_path, name='pano.png'):
    path = tmp_path / name
    cv2.imwrite(str(path), np.full((32, 64, 3), 80, np.uint8))
    return path


def run(path, **settings):
    job = Job(str(path), settings=dict(resolution=32, layout_mode='cube', **settings))
    worker = ProcessingWorker([job])
    worker.run()
    return job, worker


@pytest.mark.parametrize('bad', [None, [], {'resolution': -1}, {'resolution': float('nan')}, {'fov': 0}, {'quality': True}, {'camera_count': 0}, {'active_cameras': []}, {'active_cameras': [99]}, {'ai_mode': 'typo'}, {'interval_value': '1'}, {'resolution': 8192, 'camera_count': 64}])
def test_invalid_settings_rejected(bad):
    with pytest.raises(ValueError):
        validate_settings(bad)


@pytest.mark.parametrize('writer', ['extractor360.core.exif_writer.save_image_with_exif', 'extractor360.utils.file_manager.FileManager.save_image'])
def test_false_write_is_failed_run(tmp_path, writer):
    path = source(tmp_path)
    with patch(writer, return_value=False):
        job, worker = run(path, exif_intrinsics='exif_writer' in writer)
    assert worker.error_count == 1
    assert job.status == 'Error'
    out = Path(job.result['output_dir'])
    assert list(out.glob('*.jpg')) == []
    manifest = json.loads((out/'manifest.json').read_text())
    assert manifest['status'] == 'failed'
    assert manifest['extraction']['images_written'] == 0
    assert not list(out.glob('.writing-*'))


def test_pair_mask_failure_rolls_back_image(tmp_path):
    img = np.zeros((8, 8, 3), np.uint8)
    with patch.object(FileManager, 'save_mask', side_effect=OSError('Disk full')):
        with pytest.raises(OSError):
            FileManager.write_pair(str(tmp_path/'view.png'), img, [], None, str(tmp_path/'mask.png'), img[:,:,0])
    assert list(tmp_path.iterdir()) == []


def test_failed_opencv_boolean_raises(tmp_path):
    with patch('cv2.imwrite', return_value=False), pytest.raises(OSError):
        FileManager.save_image(tmp_path/'test.jpg', np.zeros((2,2,3), np.uint8))


def test_partial_count_is_exact(tmp_path):
    path = source(tmp_path)
    original = FileManager.write_pair
    def fail_one(image_path, *args):
        if '_Back.' in image_path:
            raise OSError('Disk full')
        return original(image_path, *args)
    with patch.object(FileManager, 'write_pair', side_effect=fail_one):
        job, worker = run(path)
    out=Path(job.result['output_dir'])
    assert worker.error_count == 1
    assert len(list(out.glob('*.jpg'))) == job.result['extraction']['images_written'] == 5


@pytest.mark.parametrize('options', [dict(naming_mode='custom', image_pattern='same'), dict(naming_mode='custom', image_pattern='{camera}.png', mask_pattern='{camera}.png', ai_mode='Generate Mask')])
def test_collision_refused_before_image_or_model(tmp_path, options):
    path=source(tmp_path)
    with patch.object(ProcessingWorker, '_ensure_ai_service') as ai:
        job, worker=run(path, **options)
    assert worker.error_count == 1
    assert not list(Path(job.result['output_dir']).glob('*.jpg'))
    ai.assert_not_called()


def test_repeated_runs_and_recursive_discovery(tmp_path):
    path=source(tmp_path)
    first, _=run(path)
    second, _=run(path)
    assert first.result['output_dir'] != second.result['output_dir']
    assert len(list(Path(first.result['output_dir']).glob('*.jpg'))) == 6
    assert discover_media([str(tmp_path), str(path)]) == [str(path)]


def test_missing_destination_is_created_not_redirected(tmp_path):
    path=source(tmp_path)
    destination=tmp_path/'new'/'output'
    job, worker=run(path, custom_output_dir=str(destination))
    assert worker.error_count == 0
    assert Path(job.result['output_dir']).parent == destination
    assert not (tmp_path/'pano_processed').exists()


def test_cancel_during_maps_never_emits_success(tmp_path):
    job=Job(str(source(tmp_path)), settings={'resolution':32, 'layout_mode':'cube'})
    worker=ProcessingWorker([job])
    completed=[]
    cancelled=[]
    worker.job_finished.connect(completed.append)
    worker.job_cancelled.connect(cancelled.append)
    worker.progress_updated.connect(lambda value, message: worker.stop() if message.startswith('Generating maps') else None)
    worker.run()
    assert completed == [] and cancelled == [0]
    assert job.result['status'] == 'cancelled'
    assert worker.io_pool._shutdown


def test_uniform_smart_blur_does_not_force_sixth_view(tmp_path):
    job, worker=run(source(tmp_path), blur_filter_enabled=True, smart_blur_enabled=True)
    assert worker.error_count == 0
    assert job.result['extraction']['images_written'] == 0
    assert job.result['extraction']['views_skipped_blur'] == 6


def test_seconds_sampling_uses_decoded_timestamps(tmp_path):
    path=tmp_path/'vfr.mkv'
    path.write_bytes(b'fixture')
    class Capture:
        index=-1
        times=[0.,.6,.7,1.3]
        def isOpened(self): return True
        def get(self,key):
            if key==cv2.CAP_PROP_FPS: return 2.
            if key==cv2.CAP_PROP_FRAME_COUNT: return 4
            if key==cv2.CAP_PROP_POS_MSEC: return self.times[max(0,min(3,self.index))]*1000
            return 32
        def grab(self):
            self.index+=1
            return self.index<len(self.times)
        def retrieve(self): return True,np.full((32,32,3),100,np.uint8)
        def release(self): pass
    with patch('cv2.VideoCapture',return_value=Capture()):
        job,worker=run(path,is_360=False,interval_value=1.,interval_unit='Seconds')
    assert worker.error_count==0
    records=[json.loads(line) for line in (Path(job.result['output_dir'])/'images.jsonl').read_text().splitlines()]
    assert [r['frame'] for r in records]==[0,3]


def test_model_trust_and_invalid_classes():
    with pytest.raises(ValueError,match='trusted'):
        validate_settings({'ai_mode':'Generate Mask','ai_model':'custom.pt'})
    assert validate_settings({'ai_mode':'Generate Mask','ai_model':'custom.pt','trust_custom_model':True})['ai_model']=='custom.pt'
    with pytest.raises(ValueError,match='Unknown AI classes'):
        validate_settings({'ai_mode':'Generate Mask','ai_custom_classes':'unicorn'})


def test_colmap_rejects_inverted_mask_convention():
    with pytest.raises(ValueError,match='COLMAP masks'):
        validate_settings({'export_colmap':True,'ai_mode':'Generate Mask','ai_invert_mask':False})
