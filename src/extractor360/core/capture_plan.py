"""Frozen 16-capture references and deterministic 31-capture densification.

This is an extraction schedule, not a larger COLMAP diagnostic. Frame indices
are source-specific; decoded timestamps remain the export's time authority.
"""
import hashlib
import json

from extractor360.core.selection import FrameSelection


def baseline_frames(value):
    if (not isinstance(value, list) or len(value) != 16
            or any(type(f) is not int or not 0 <= f <= 2147483647 for f in value)
            or sorted(set(value)) != value):
        raise ValueError('Capture plan requires exactly 16 unique, increasing source-frame indices')
    return list(value)


def baseline_from_window(start, end):
    if (any(type(f) is not int or not 0 <= f <= 2147483647 for f in (start, end))
            or end - start < 15):
        raise ValueError('The reference window must contain at least 16 source frames')
    # Nearest integer, including both endpoints. Integer arithmetic avoids
    # platform/large-frame floating point differences (15 has no half ties).
    return [start + (i * (end - start) + 7) // 15 for i in range(16)]


def densify_frames(baseline):
    baseline = baseline_frames(baseline)
    if any(b - a < 2 for a, b in zip(baseline, baseline[1:])):
        raise ValueError('Cannot reach 31 captures: every reference gap needs an interior source frame')
    return sorted(baseline + [(a + b) // 2 for a, b in zip(baseline, baseline[1:])])


def normalize_capture_plan(value):
    if value is None:
        return None
    if (not isinstance(value, dict) or set(value) != {'mode', 'baseline_frames'}
            or value['mode'] not in ('baseline', 'densified')):
        raise ValueError('capture_plan requires mode baseline/densified and baseline_frames')
    baseline = baseline_frames(value['baseline_frames'])
    if value['mode'] == 'densified':
        densify_frames(baseline)
    return {'mode': value['mode'], 'baseline_frames': baseline}


def planned_frames(plan):
    plan = normalize_capture_plan(plan)
    if plan is None:
        return None
    return plan['baseline_frames'] if plan['mode'] == 'baseline' else densify_frames(plan['baseline_frames'])


def validate_plan_selection(settings, total=None, is_image=False):
    frames = planned_frames(settings.get('capture_plan'))
    if frames is None:
        return None
    if is_image or (total is not None and (total <= 0 or frames[-1] >= total)):
        raise ValueError('Capture plan requires a video with all planned frames inside its known length')
    selection = FrameSelection(settings.get('included_frame_ranges', []))
    excluded = set(settings.get('excluded_frames', []))
    conflicts = [f for f in frames if not selection.contains(f) or f in excluded]
    if conflicts:
        raise ValueError(f'Capture plan conflicts with extraction ranges/exclusions at frames {conflicts}; '
                         'restore those frames or turn off the capture plan')
    if settings.get('blur_filter_enabled') or settings.get('adaptive_mode') or settings.get('ai_mode') == 'Skip Frame':
        raise ValueError('Capture plan requires blur, motion and AI Skip Frame rejection to be disabled; '
                         'mask generation is allowed')
    return frames


def sampling_record(settings, source_identity):
    plan = normalize_capture_plan(settings['capture_plan'])
    frames = planned_frames(plan)
    # Mode and output destination may differ between the pair. All other
    # settings and the source's size/mtime identity must match this signature.
    common = {k: v for k, v in settings.items() if k not in ('capture_plan', 'custom_output_dir', 'input', 'output')}
    payload = {'source_identity': source_identity, 'settings': common, 'baseline_frames': plan['baseline_frames']}
    signature = hashlib.sha256(json.dumps(payload, sort_keys=True, allow_nan=False).encode()).hexdigest()
    return {'method': 'floor-midpoints-v1', **plan, 'requested_frames': frames,
            'added_frames': [f for f in frames if f not in plan['baseline_frames']],
            'confirmed_frames': [], 'comparison_signature': signature,
            'source_hash_verified': False}
