from unittest.mock import patch
import numpy as np
import pytest

torch=pytest.importorskip('torch')
pytest.importorskip('ultralytics')
from extractor360.core.ai_model import AIService


def test_cpu_selection_overrides_reported_gpu_availability(monkeypatch):
    monkeypatch.setenv('EXTRACTOR360_DEVICE', 'cpu')
    with patch.object(torch.backends.mps, 'is_available', return_value=True), patch.object(torch.cuda, 'is_available', return_value=True):
        info = AIService.get_device_info()
    assert info['device'] == 'cpu'
    assert info['is_accelerated'] is False


def test_unknown_device_selection_is_explicit_error(monkeypatch):
    monkeypatch.setenv('EXTRACTOR360_DEVICE', 'typo')
    with pytest.raises(ValueError, match='auto or cpu'):
        AIService.get_device_info()


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


def test_offline_diagnostic_never_calls_yolo_for_missing_model(tmp_path, monkeypatch):
    monkeypatch.setenv('EXTRACTOR360_OFFLINE_MODELS', '1')
    monkeypatch.setenv('EXTRACTOR360_MODEL_DIR', str(tmp_path / 'models'))
    with patch('extractor360.core.ai_model.YOLO') as load, patch.object(AIService, 'get_device_info', return_value={'device': 'cpu', 'is_accelerated': False}):
        with pytest.raises(RuntimeError, match='not available locally'):
            AIService('yolo26x-seg.pt')
        load.assert_not_called()


def test_incomplete_inference_batch_is_error():
    service=AIService.__new__(AIService)
    service.model=lambda *args,**kwargs: []
    service.target_classes=[0]
    service.device='cpu'
    with pytest.raises(RuntimeError,match='incomplete'):
        service.process_batch([np.zeros((10,10,3),np.uint8)],mode='generate_mask')


def _service_with_result(result, task=None):
    from types import SimpleNamespace
    class Model:
        def __call__(self, images, **kwargs):
            return [result for _ in images]
    model = Model()
    model.task = task
    service = AIService.__new__(AIService)
    service.model = model
    service.target_classes = [0]
    service.device = 'cpu'
    return service, SimpleNamespace


def test_detection_only_custom_model_cannot_generate_a_keep_everything_mask():
    from types import SimpleNamespace
    service, _ = _service_with_result(SimpleNamespace(boxes=[object()], masks=None), task='detect')
    image = np.zeros((10, 10, 3), np.uint8)
    with pytest.raises(RuntimeError, match='segmentation model'):
        service.process_batch([image], mode='generate_mask')
    assert service.process_batch([image], mode='skip_frame') == [(None, True)]


def test_missing_masks_with_detections_is_an_error_even_without_model_task():
    from types import SimpleNamespace
    service, _ = _service_with_result(SimpleNamespace(boxes=[object()], masks=None))
    with pytest.raises(RuntimeError, match='no segmentation masks'):
        service.process_batch([np.zeros((10, 10, 3), np.uint8)], mode='generate_mask')


def test_no_detections_still_returns_a_valid_empty_segmentation_mask():
    from types import SimpleNamespace
    service, _ = _service_with_result(SimpleNamespace(boxes=[], masks=None), task='segment')
    image = np.zeros((10, 10, 3), np.uint8)
    output, mask = service.process_batch([image], mode='generate_mask')[0]
    assert output is image
    assert np.all(mask == 255)
