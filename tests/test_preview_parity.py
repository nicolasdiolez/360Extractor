import json
from pathlib import Path

import cv2
import numpy as np
import pytest

pytest.importorskip('PySide6')
from extractor360.core.job import Job
from extractor360.core.processor import ProcessingWorker
from extractor360.ui.preview_widget import PreviewWorker


@pytest.mark.parametrize('layout,face,is_360',[('cube','Down',True),('ring','View_1',True),('fibonacci','View_2',True),('cube','flat',False)])
def test_preview_pixels_match_export(tmp_path,layout,face,is_360):
    image=np.random.default_rng(3).integers(0,255,(48,96,3),dtype=np.uint8)
    source=tmp_path/'source.png'
    cv2.imwrite(str(source),image)
    settings=dict(resolution=64,layout_mode=layout,camera_count=3,is_360=is_360,output_format='png',interpolation_mode='lanczos',sharpening_enabled=True,sharpening_strength=.5)
    job=Job(str(source),settings=settings)
    worker=ProcessingWorker([job]);worker.run()
    assert worker.error_count==0
    records=[json.loads(s) for s in (Path(job.result['output_dir'])/'images.jsonl').read_text().splitlines()]
    record=next(r for r in records if r['camera']==face)
    expected=cv2.imread(str(Path(job.result['output_dir'])/record['image']))
    previews=[];errors=[]
    preview=PreviewWorker(str(source),settings,face,show_ai_mask=False,show_nadir_disc=False)
    preview.signals.result.connect(previews.append)
    preview.signals.error.connect(errors.append)
    preview.run()
    assert not errors and len(previews)==1
    qt=previews[0]
    pixels=np.frombuffer(qt.bits(),dtype=np.uint8).reshape(qt.height(),qt.bytesPerLine())[:,:qt.width()*3].reshape(qt.height(),qt.width(),3)
    np.testing.assert_array_equal(cv2.cvtColor(pixels,cv2.COLOR_RGB2BGR),expected)
