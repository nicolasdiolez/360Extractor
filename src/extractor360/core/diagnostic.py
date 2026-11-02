"""Diagnostic choices and model interpretation, independent of Qt and media IO."""
from __future__ import annotations

import math
from collections import Counter
from pathlib import PurePosixPath
from typing import Any


def diagnostic_options(value=None) -> dict[str, Any]:
    if value is None:
        value = {}
    if not isinstance(value, dict):
        raise ValueError('Diagnostic settings must be an object')
    result = dict(mode='source', maximum=8, resolution=512, frame_range=None)
    if set(value) - set(result):
        raise ValueError('Unknown diagnostic setting')
    result.update(value)
    if result['mode'] not in ('source', 'export'):
        raise ValueError('Diagnostic mode must be source or export')
    if type(result['maximum']) is not int or not 3 <= result['maximum'] <= 16:
        raise ValueError('Choose between 3 and 16 physical captures')
    if type(result['resolution']) is not int or result['resolution'] not in (512, 1024):
        raise ValueError('Diagnostic resolution must be 512 or 1024 pixels')
    window = result['frame_range']
    if window is not None:
        if (not isinstance(window, list) or len(window) != 2
                or any(type(i) is not int or not 0 <= i <= 2147483647 for i in window)
                or window[1] - window[0] < 2):
            raise ValueError('Choose an inclusive source-frame range containing at least three frames')
        result['frame_range'] = list(window)
    return result


def model_overview(report) -> dict[str, Any]:
    """Describe individual reconstructions; never merge overlapping alternatives.

    A time span is not continuous coverage. Gaps count *tested* captures absent
    from that model; unsampled intervals remain unqualified.
    """
    captures = {row['frame']: row for row in report['captures']}
    sampled = report.get('requested_frames', report['sampled_frames'])
    if (not isinstance(sampled, list) or len(sampled) > 10000
            or any(type(f) is not int or f not in captures for f in sampled)
            or len(set(sampled)) != len(sampled)):
        raise ValueError('Invalid diagnostic sample')
    models = report['models']
    if not isinstance(models, list) or len(models) > 128:
        raise ValueError('Invalid diagnostic models')
    rows: list[dict[str, Any]] = []
    ids = set()
    for model in models:
        name, frames = model['model'], model['frames']
        if not isinstance(name, str) or name in ids:
            raise ValueError('Invalid or duplicate diagnostic model')
        ids.add(name)
        if (not isinstance(frames, list) or not frames or len(frames) > len(sampled)
                or any(type(f) is not int or f not in sampled for f in frames)
                or len(set(frames)) != len(frames)):
            raise ValueError('Invalid model capture membership')
        frames = sorted(frames)
        missing = [f for f in sorted(sampled) if frames[0] < f < frames[-1] and f not in frames]
        seconds = [captures[f].get('timestamp_seconds') for f in frames]
        sources = {captures[f].get('timestamp_source', 'unavailable') for f in frames}
        valid_time = (all(type(t) in (float, int) and math.isfinite(t) and t >= 0 for t in seconds)
                      and all(a < b for a, b in zip(seconds, seconds[1:])))
        timing = ('decoded' if sources == {'decoder_timestamp'} else
                  'FPS estimate' if sources <= {'decoder_timestamp', 'fps_estimate'} else 'unavailable')
        rows.append({'model': name, 'capture_count': len(frames), 'frames': frames,
                     **view_coverage(report, model),
                     'frame_span': [frames[0], frames[-1]], 'missing_tested_frames': missing,
                     'time_span': [seconds[0], seconds[-1]] if valid_time and timing != 'unavailable' else None,
                     'timing': timing if valid_time else 'unavailable', 'fragment': len(frames) <= 2})
    rows.sort(key=lambda row: (-row['capture_count'], row['model']))
    largest = rows[0] if rows else None
    return {'models': rows, 'largest': largest,
            'largest_ties': [row['model'] for row in rows if largest and row['capture_count'] == largest['capture_count']],
            'fragment_models': sum(row['fragment'] for row in rows),
            'only_fragments': bool(rows) and all(row['fragment'] for row in rows)}


def view_coverage(report, model):
    """Count confirmed tested views in one model; old reports remain unknown.

    Direction names describe virtual cameras, not measured solid-angle coverage.
    Rejected views are relative to this model, not necessarily to all models.
    """
    sampled = set(report['sampled_frames'])
    directions = {}
    for row in report['captures']:
        if row['frame'] not in sampled:
            continue
        for image in row['images']:
            if not isinstance(image, str) or image in directions:
                raise ValueError('Invalid or duplicate tested image')
            camera = row.get('image_cameras', {}).get(image)
            if camera is None:
                parts = PurePosixPath(image).parts
                camera = parts[0] if len(parts) == 2 else None
            if camera is not None and (not isinstance(camera, str) or not camera):
                raise ValueError('Invalid tested camera')
            directions[image] = camera
    names = model.get('image_names')
    if names is None:
        return {'view_coverage': None}
    if (not isinstance(names, list) or len(names) > len(directions)
            or any(not isinstance(n, str) or n not in directions for n in names)
            or len(set(names)) != len(names)):
        raise ValueError('Invalid registered image membership')
    registered = set(names)
    member_frames = sorted(row['frame'] for row in report['captures']
                           if row['frame'] in sampled and registered.intersection(row['images']))
    if member_frames != sorted(model['frames']):
        raise ValueError('Image and capture membership disagree')
    totals = Counter(d for d in directions.values() if d is not None)
    counts = Counter(directions[n] for n in registered if directions[n] is not None)
    return {'view_coverage': {
        'registered': len(registered), 'tested': len(directions),
        'directions': {d: {'registered': counts[d], 'tested': totals[d]} for d in sorted(totals)},
        'missing_directions': sorted(d for d in totals if not counts[d]),
        'unknown_direction_views': sum(d is None for d in directions.values()),
        'unregistered_images': sorted(set(directions) - registered),
    }}
