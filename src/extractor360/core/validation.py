"""Shared validation before opening media, models, or output directories."""
import copy
import math
from typing import Any

from extractor360.core.geometry import GeometryProcessor
from extractor360.core.settings_manager import SettingsManager, normalize_mask_faces


def validate_settings(settings: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(settings, dict):
        raise ValueError('Settings must be a JSON object')
    result: dict[str, Any] = copy.deepcopy(SettingsManager.DEFAULT_SETTINGS)
    result.update(copy.deepcopy(settings))
    if result['layout_mode'] == 'adaptive':
        result['layout_mode'] = 'ring'
    bounds = {
        'resolution': (16, 8192), 'camera_count': (1, 64), 'quality': (1, 100),
        'fov': (1, 179), 'pitch_offset': (-90, 90), 'interval_value': (0.001, 86400),
        'ai_confidence': (0, 1), 'nadir_mask_radius': (0, 100),
        'blur_threshold': (0, 1e9), 'adaptive_threshold': (0, 1e6),
        'sharpening_strength': (0, 5), 'memory_budget_mb': (128, 65536),
    }
    for key, (low, high) in bounds.items():
        value = result.get(key, 1536 if key == 'memory_budget_mb' else None)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError(f'{key} must be a finite number')
        if not low <= value <= high:
            raise ValueError(f'{key} must be between {low} and {high}')
        if key in ('resolution', 'camera_count', 'quality') and not isinstance(value, int):
            raise ValueError(f'{key} must be an integer')
        result[key] = value
    for key, default in SettingsManager.DEFAULT_SETTINGS.items():
        if isinstance(default, bool) and not isinstance(result[key], bool):
            raise ValueError(f'{key} must be true or false')
        if isinstance(default, str) and not isinstance(result[key], str):
            raise ValueError(f'{key} must be a string')
    enums = {
        'layout_mode': ('ring', 'cube', 'fibonacci'), 'output_format': ('jpg', 'png', 'tiff'),
        'interval_unit': ('Seconds', 'Frames'), 'ai_mode': ('None', 'Generate Mask', 'Skip Frame'),
        'altitude_mode': ('absolute', 'relative'), 'interpolation_mode': ('linear', 'lanczos'),
        'naming_mode': ('realityscan', 'simple', 'custom'),
    }
    for key, values in enums.items():
        if result[key] not in values:
            raise ValueError(f'{key} must be one of {", ".join(values)}')
    if result['export_colmap'] and (result['ai_mode'] == 'Generate Mask' or result['nadir_mask_enabled']) and not result['ai_invert_mask']:
        raise ValueError('COLMAP masks require black = ignored subject (ai_invert_mask=true)')
    if result['ai_mode'] != 'None':
        from extractor360.core.ai_classes import COCO_STR_TO_ID, resolve_ai_model_name
        custom = [s.strip().lower() for s in result['ai_custom_classes'].split(',') if s.strip()]
        unknown = set(custom) - set(COCO_STR_TO_ID)
        if unknown:
            raise ValueError(f'Unknown AI classes: {sorted(unknown)}')
        if not custom and not any(result[k] for k in ('ai_detect_humans', 'ai_detect_vehicles', 'ai_detect_plants')):
            raise ValueError('Select at least one AI target class')
        result['ai_model'] = resolve_ai_model_name(result['ai_model'])
        from extractor360.core.ai_classes import AI_MODEL_VARIANTS
        if result['ai_model'] not in AI_MODEL_VARIANTS.values() and result.get('trust_custom_model') is not True:
            raise ValueError('Custom .pt models can execute code; set trust_custom_model=true only for a trusted model')
    views = GeometryProcessor.generate_views(result['camera_count'], result['pitch_offset'], result['layout_mode']) if result['is_360'] else [('flat', 0, 0, 0)]
    active = result.get('active_cameras')
    if active is not None:
        if not isinstance(active, list) or not active or any(type(i) is not int or i < 0 or i >= len(views) for i in active):
            raise ValueError(f'active_cameras must contain indices between 0 and {len(views)-1}')
        result['active_cameras'] = sorted(set(active))
        views = [v for i, v in enumerate(views) if i in active]
    faces = result.get('ai_mask_cameras')
    if not isinstance(faces, (list, str, type(None))):
        raise ValueError('ai_mask_cameras must be a list or comma-separated string')
    selected = normalize_mask_faces(faces)
    if result['ai_mode'] != 'None' and result['is_360'] and selected:
        available = {v[0].lower() for v in views}
        if not selected <= available:
            raise ValueError(f'AI mask faces are not active in this layout: {sorted(selected - available)}')
    if result['is_360']:
        # Fixed maps + queued RGB views + conservative floating-point map workspace.
        predicted = (result['resolution'] ** 2 * (len(views) * 10 + 8) + min(256, result['resolution']) * result['resolution'] * 145) / 1024**2
        if predicted > result['memory_budget_mb']:
            raise ValueError(f'Projection needs approximately {predicted:.0f} MiB; lower resolution/camera count or increase memory_budget_mb')
    return result
