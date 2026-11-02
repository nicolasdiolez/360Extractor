"""Portable COLMAP runner copied into each exported dataset.

Run with Python 3.10+ and a COLMAP installation supporting rig_configurator.
This file uses only the standard library so the exported copy is standalone.
"""
import errno
import json
import math
import os
from pathlib import Path, PureWindowsPath
import re
import shutil
import struct
import subprocess
import sys
from typing import TypeGuard
import unicodedata
import zlib


def _camera_name(value):
    """Accept one portable directory component, never an index-supplied path."""
    if (not isinstance(value, str) or not value or value in ('.', '..')
            or value.endswith((' ', '.'))
            or any(ord(c) < 32 or c in '/\\<>:"|?*' for c in value)
            or len(value.encode('utf-8')) > 240):
        raise ValueError(f'Invalid camera name: {value!r}')
    stem = value.split('.')[0].upper()
    if stem in {'CON', 'PRN', 'AUX', 'NUL'} or re.fullmatch(r'(COM|LPT)[1-9]', stem):
        raise ValueError(f'Reserved camera name: {value!r}')
    return value


def _source_path(dataset, value):
    """Resolve an existing index source without leaving the exported dataset."""
    if (not isinstance(value, str) or not value or '\\' in value
            or any(ord(c) < 32 for c in value)
            or Path(value).is_absolute() or PureWindowsPath(value).drive
            or any(part in ('', '.', '..') for part in value.split('/'))):
        raise ValueError(f'Index source must be a relative dataset path: {value!r}')
    source = (dataset / value).resolve(strict=True)
    if not source.is_relative_to(dataset) or not source.is_file():
        raise ValueError(f'Index source is not a file inside the dataset: {value!r}')
    return source


def _read_index(dataset):
    """Validate the entire index before creating any reconstruction files."""
    dataset = Path(dataset).resolve(strict=True)
    entries = []
    used = set()
    with (dataset / 'images.jsonl').open(encoding='utf-8') as index:
        for number, line in enumerate(index, 1):
            try:
                entry = json.loads(line)
                if not isinstance(entry, dict):
                    raise ValueError('Each image record must be a JSON object')
                camera = _camera_name(entry.get('camera'))
                frame = entry.get('frame')
                if type(frame) is not int or frame < 0:
                    raise ValueError('frame must be a nonnegative integer')
                source = _source_path(dataset, entry.get('image'))
                suffix = Path(entry['image']).suffix
                if suffix.lower() not in {'.jpg', '.jpeg', '.png', '.tiff', '.tif'}:
                    raise ValueError('Unsupported image extension in index')
                relative = Path(camera) / f'frame{frame:09d}{suffix}'
                if len(relative.name.encode('utf-8')) > 240:
                    raise ValueError('Reconstruction filename exceeds 240 bytes')
                # Case and Unicode normalization can alias filenames on the
                # receiving filesystem, even if they differ on the exporter.
                key = unicodedata.normalize('NFC', relative.as_posix()).casefold()
                if key in used:
                    raise ValueError(f'Duplicate reconstruction destination: {relative}')
                used.add(key)
                mask = entry.get('mask')
                mask_source = _source_path(dataset, mask) if mask is not None else None
                entries.append((source, relative, mask_source))
            except (ValueError, OSError) as exc:
                raise ValueError(f'Invalid images.jsonl record {number}: {exc}') from exc
    if not entries:
        raise ValueError('No exported images available for reconstruction')
    return entries


def _copy_exclusive(source, target):
    # copy2 opens an existing target with truncation. A target can already be
    # a hardlink to an original image, so fallback copying must be exclusive.
    with source.open('rb') as original, target.open('xb') as copy:
        shutil.copyfileobj(original, copy)
    shutil.copystat(source, target)


def _white_mask_for_mixed_export(entries):
    """Fill unmasked views only when COLMAP must load per-image PNG masks.

    A 360 export uses the same resolution for every view. Read that size from
    its existing masks, rather than adding Pillow to this standalone runner.
    Validate all headers before staging any files; do not guess dimensions.
    """
    masks = [mask for _, _, mask in entries if mask is not None]
    if not masks or len(masks) == len(entries):
        return None
    sizes = set()
    for mask in masks:
        with mask.open('rb') as file:
            header = file.read(24)
        if len(header) != 24 or header[:16] != b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR':
            raise ValueError('Mixed exports require PNG masks with valid dimensions')
        size = struct.unpack('>II', header[16:24])
        if not all(16 <= dimension <= 8192 for dimension in size):
            raise ValueError('Mask dimensions exceed supported export resolution (16..8192)')
        sizes.add(size)
    if len(sizes) != 1:
        raise ValueError('Mixed export masks must share the same dimensions')
    width, height = sizes.pop()

    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data))

    # Compress one row at a time instead of allocating an entire 8K image.
    compressor = zlib.compressobj()
    row = b'\x00' + b'\xff' * width
    pixels = b''.join(compressor.compress(row) for _ in range(height)) + compressor.flush()
    return (b'\x89PNG\r\n\x1a\n'
            + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 0, 0, 0, 0))
            + chunk(b'IDAT', pixels) + chunk(b'IEND', b''))


def _stage(entries, destination):
    white_mask = _white_mask_for_mixed_export(entries)
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=False)
    names = []
    for source, relative, mask_source in entries:
        target = destination / 'images' / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            os.link(source, target)
        except OSError as exc:
            if exc.errno == errno.EEXIST:
                raise
            _copy_exclusive(source, target)
        names.append(relative.as_posix())
        if mask_source is not None or white_mask is not None:
            mask = destination / 'masks' / (relative.as_posix() + '.png')
            mask.parent.mkdir(parents=True, exist_ok=True)
            if mask_source is not None:
                _copy_exclusive(mask_source, mask)
            else:
                with mask.open('xb') as file:
                    file.write(white_mask)
    (destination / 'images.txt').write_text('\n'.join(names) + '\n', encoding='utf-8')
    (destination / 'masks').mkdir(exist_ok=True)
    return destination


def prepare(dataset, destination):
    """Validate and stage confirmed images and masks without overwriting files."""
    return _stage(_read_index(dataset), destination)


def _numeric_vector(value: object, size: int) -> TypeGuard[list[int | float]]:
    return (isinstance(value, list) and len(value) == size
            and all(type(v) in (int, float) and math.isfinite(v) for v in value))


def _read_rig(path):
    """Check the generated PINHOLE rig before staging or invoking COLMAP."""
    rig = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(rig, list) or len(rig) != 1 or not isinstance(rig[0], dict):
        raise ValueError('rig_config.json must describe one camera rig')
    cameras = rig[0].get('cameras')
    if not isinstance(cameras, list) or not cameras:
        raise ValueError('rig_config.json must contain cameras')
    prefixes = set()
    names = set()
    reference_count = 0
    params = None
    for camera in cameras:
        if not isinstance(camera, dict):
            raise ValueError('Invalid rig camera')
        prefix = camera.get('image_prefix')
        if not isinstance(prefix, str) or not prefix.endswith('/'):
            raise ValueError('Rig camera prefix must end with /')
        name = _camera_name(prefix[:-1])
        key = unicodedata.normalize('NFC', name).casefold()
        if key in prefixes:
            raise ValueError('Duplicate rig camera prefix')
        prefixes.add(key)
        names.add(name)
        current = camera.get('camera_params')
        if (camera.get('camera_model_name') != 'PINHOLE'
                or not _numeric_vector(current, 4) or min(current) < 0 or min(current[:2]) <= 0):
            raise ValueError('Rig cameras must have finite PINHOLE intrinsics')
        if params is not None and current != params:
            raise ValueError('Rig cameras must share the same intrinsics')
        params = current
        if 'ref_sensor' in camera and type(camera['ref_sensor']) is not bool:
            raise ValueError('ref_sensor must be true or false')
        if camera.get('ref_sensor') is True:
            reference_count += 1
        else:
            rotation = camera.get('cam_from_rig_rotation')
            if (not _numeric_vector(rotation, 4)
                    or not math.isclose(sum(v * v for v in rotation), 1.0, abs_tol=1e-6)
                    or not _numeric_vector(camera.get('cam_from_rig_translation'), 3)):
                raise ValueError('Rig camera must have a unit quaternion and finite translation')
    if reference_count != 1:
        raise ValueError('Rig must have exactly one reference sensor')
    return params, names


def main():
    calibration = Path(__file__).resolve().parent
    dataset = calibration.parent
    destination = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else calibration / 'workspace'
    params, prefixes = _read_rig(calibration / 'rig_config.json')
    colmap = shutil.which('colmap')
    if colmap is None:
        raise FileNotFoundError('COLMAP executable not found on PATH')
    entries = _read_index(dataset)
    if any(relative.parts[0] not in prefixes for _, relative, _ in entries):
        raise ValueError('An indexed camera is missing from rig_config.json')
    _stage(entries, destination)
    database = str(destination / 'database.db')
    images = str(destination / 'images')
    feature_command = [colmap, 'feature_extractor', '--database_path', database,
                    '--image_path', images, '--image_list_path', str(destination / 'images.txt'),
                    '--ImageReader.camera_model', 'PINHOLE',
                    '--ImageReader.camera_params', ','.join(str(p) for p in params),
                    '--ImageReader.single_camera_per_folder', '1']
    if any(mask is not None for _, _, mask in entries):
        feature_command += ['--ImageReader.mask_path', str(destination / 'masks')]
    subprocess.run(feature_command, check=True)
    subprocess.run([colmap, 'rig_configurator', '--database_path', database,
                    '--rig_config_path', str(calibration / 'rig_config.json')], check=True)
    subprocess.run([colmap, 'sequential_matcher', '--database_path', database], check=True)
    (destination / 'sparse').mkdir()
    subprocess.run([colmap, 'mapper', '--database_path', database, '--image_path', images,
                    '--output_path', str(destination / 'sparse'),
                    '--Mapper.ba_refine_focal_length', '0', '--Mapper.ba_refine_principal_point', '0',
                    '--Mapper.ba_refine_extra_params', '0', '--Mapper.ba_refine_sensor_from_rig', '0'], check=True)


if __name__ == '__main__':
    main()
