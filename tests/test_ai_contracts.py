from unittest.mock import patch
import numpy as np
import pytest

torch=pytest.importorskip('torch')
pytest.importorskip('ultralytics')
from extractor360.core.ai_model import AIService


def test_mask_feather_is_float_edge_smoothing():
    image=np.zeros((100,100,3),np.uint8)
    tensor=torch.zeros((1,100,100),dtype=torch.uint8)
    tensor[:,30:70,30:70]=1
    binary=AIService._build_mask(tensor,image,True,False)
    soft=AIService._build_mask(tensor,image,True,True)
    assert set(np.unique(binary))=={0,255}
    assert ((soft>0)&(soft<255)).any()
    assert soft[50,50]==0 and soft[0,0]==255


def test_load_failure_is_not_a_passthrough(tmp_path,monkeypatch):
    monkeypatch.setenv('EXTRACTOR360_MODEL_DIR',str(tmp_path/'models'))
    with patch('extractor360.core.ai_model.YOLO',side_effect=OSError('Unavailable')),patch.object(AIService,'get_device_info',return_value={'device':'cpu','is_accelerated':False}):
        with pytest.raises(RuntimeError,match='Could not load'):
            AIService()


def test_incomplete_inference_batch_is_error():
    service=AIService.__new__(AIService)
    service.model=lambda *args,**kwargs: []
    service.target_classes=[0]
    service.device='cpu'
    with pytest.raises(RuntimeError,match='incomplete'):
        service.process_batch([np.zeros((10,10,3),np.uint8)],mode='generate_mask')
