"""Disk estimates and a rolling free-space guard shared by Studio and CLI.

Compression and timestamp-based sampling make totals estimates. The guard only
requires room for the next capture plus a reserve; it does not promise that a
whole run or an external reconstruction will fit.
"""
import math
from pathlib import Path
import shutil

from extractor360.core.frame_timing import frame_step
from extractor360.core.settings_manager import normalize_mask_faces


RESERVE_BYTES = 256 * 1024 * 1024


def existing_destination(source, destination):
    path = Path(destination).expanduser() if destination else Path(source).resolve().parent
    while not path.exists() and path.parent != path:
        path = path.parent
    if not path.is_dir():
        raise ValueError(f'Output destination is not a directory: {path}')
    return path.resolve()


def capture_write_budget(width, height, views, masked_views):
    # Allow raw RGB/gray pixels, encoder overhead and metadata for every view
    # submitted together. Staging publishes by rename, without a second copy.
    return math.ceil(width * height * (3 * views + masked_views) * 1.1) + 65536 * (views + masked_views)


def estimate_output(settings, width, height, frame_count, fps, is_image, view_names):
    if width <= 0 or height <= 0:
        raise ValueError('Cannot estimate storage without valid output dimensions')
    scope = normalize_mask_faces(settings.get('ai_mask_cameras'))
    masked_views = sum(
        (settings.get('ai_mode') == 'Generate Mask'
         and (not settings.get('is_360', True) or scope is None or name.lower() in scope))
        or (settings.get('nadir_mask_enabled', False) and name.lower() == 'down')
        for name in view_names
    )
    if is_image:
        captures = 1
    elif frame_count <= 0:
        captures = None
    elif settings['interval_unit'] == 'Frames':
        captures = math.ceil(frame_count / frame_step(settings['interval_value']))
    elif fps > 0 and math.isfinite(fps):
        captures = min(frame_count, max(1, math.ceil(frame_count / fps / settings['interval_value'])))
    else:
        captures = None
    views = len(view_names)
    pixels = width * height
    # An explicit planning range, not a guarantee or a filter prediction.
    image_range = {'jpg': (0.15, 1.5), 'png': (0.5, 3.1), 'tiff': (3.0, 3.1)}[settings['output_format']]
    lower = math.ceil(pixels * (views * image_range[0] + masked_views * 0.01))
    upper = math.ceil(pixels * (views * image_range[1] + masked_views * 1.1)) + 65536 * (views + masked_views)
    return {
        'captures_estimated': captures,
        'images_estimated': captures * views if captures is not None else None,
        'masks_estimated': captures * masked_views if captures is not None else None,
        'output_width': width, 'output_height': height,
        'bytes_low': captures * lower if captures is not None else None,
        'bytes_high': captures * upper if captures is not None else None,
        'capture_budget_bytes': capture_write_budget(width, height, views, masked_views),
        'reserve_bytes': RESERVE_BYTES,
        'assumptions': 'Before filters; seconds use nominal FPS for planning only. '
                       'Includes images and masks; excludes models and reconstruction workspaces.',
    }


def require_free_space(destination, capture_budget):
    free = shutil.disk_usage(destination).free
    required = capture_budget + RESERVE_BYTES
    if free < required:
        raise OSError(
            f'Insufficient disk space on {destination}: {free / 1024**2:.1f} MiB free; '
            f'{required / 1024**2:.1f} MiB needed for the next capture including '
            f'{RESERVE_BYTES / 1024**2:.0f} MiB reserve. Choose another output volume or free space.'
        )
    return free
