"""Output isolation and name validation shared by GUI and CLI processing."""
import os
import re
import string
from pathlib import Path

MEDIA_EXTENSIONS = {'.mp4', '.avi', '.mov', '.mkv', '.insv', '.jpg', '.jpeg', '.png', '.tiff', '.tif'}
IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.tiff', '.tif'}


def discover_media(paths, exclude=()):
    excluded = {Path(p).resolve() for p in exclude if p}
    found = set()
    def generated(folder):
        return (folder / 'manifest.json').is_file() or bool(re.search(r'_processed(?:_\d+)?$', folder.name))
    for raw in paths:
        path = Path(raw).resolve()
        if path.is_dir():
            for directory, dirs, files in os.walk(path, followlinks=False):
                folder = Path(directory)
                if folder in excluded or generated(folder):
                    dirs[:] = []
                    continue
                dirs[:] = sorted(d for d in dirs if not (folder/d).is_symlink() and (folder/d).resolve() not in excluded and not generated(folder/d))
                for name in files:
                    candidate = folder / name
                    if candidate.suffix.lower() in MEDIA_EXTENSIONS and not candidate.is_symlink():
                        found.add(str(candidate.resolve()))
        elif path.is_file() and path.suffix.lower() in MEDIA_EXTENSIONS:
            found.add(str(path))
    return sorted(found, key=lambda p: (p.casefold(), p))


def validate_name(name):
    if not name or name in ('.', '..') or '/' in name or '\\' in name or name.endswith((' ', '.')):
        raise ValueError(f'Unsafe output filename: {name!r}')
    if any(ord(c) < 32 or c in '<>:"|?*' for c in name):
        raise ValueError(f'Invalid output filename: {name!r}')
    stem = name.split('.')[0].upper()
    if stem in {'CON', 'PRN', 'AUX', 'NUL'} or re.fullmatch(r'(COM|LPT)[1-9]', stem):
        raise ValueError(f'Reserved output filename: {name!r}')
    if len(name.encode('utf-8')) > 240:
        raise ValueError('Output filename exceeds 240 bytes')
    return name


def output_names(settings, stem, frame, camera):
    extension = '.tif' if settings['output_format'] == 'tiff' else '.' + settings['output_format']
    image = f'{stem}_frame{frame:06d}_{camera}{extension}'
    if settings['naming_mode'] == 'realityscan':
        mask = image + '.mask.png'
    elif settings['naming_mode'] == 'simple':
        mask = f'{stem}_frame{frame:06d}_{camera}_mask.png'
    else:
        context = dict(filename=stem, frame=f'{frame:06d}', camera=camera, ext=extension)
        pattern = settings['image_pattern']
        image = pattern.format(**context)
        if not Path(image).suffix:
            image += extension
        if Path(image).suffix.lower() != extension:
            raise ValueError('Image pattern extension must match the output format')
        context['image_name'] = image
        pattern = settings['mask_pattern']
        mask = pattern.format(**context)
        if not mask.lower().endswith('.png'):
            mask += '.png'
    return validate_name(image), validate_name(mask)


def preflight_names(settings, stem, views, is_image):
    if settings['naming_mode'] == 'custom':
        for key in ('image_pattern', 'mask_pattern'):
            fields = {field for _, field, _, _ in string.Formatter().parse(settings[key]) if field}
            if not fields <= {'filename', 'frame', 'camera', 'ext', 'image_name'}:
                raise ValueError(f'Unknown placeholder in {key}')
        pattern = settings['image_pattern']
        if (not is_image and '{frame}' not in pattern) or (len(views) > 1 and '{camera}' not in pattern):
            raise ValueError('Custom image names must include {frame} for video and {camera} for multiple views')
        mask_pattern = settings['mask_pattern']
        if settings['ai_mode'] == 'Generate Mask' or settings['nadir_mask_enabled']:
            if '{image_name}' not in mask_pattern and ((not is_image and '{frame}' not in mask_pattern) or (len(views) > 1 and '{camera}' not in mask_pattern)):
                raise ValueError('Custom mask names must identify each frame and camera, or use {image_name}')
    used = set()
    for frame in ([0] if is_image else [0, 1]):
        for name, *_ in views:
            pair = output_names(settings, stem, frame, name)
            for value in pair if settings['ai_mode'] == 'Generate Mask' or settings['nadir_mask_enabled'] else pair[:1]:
                if value.casefold() in used:
                    raise ValueError(f'Output filename collision: {value}')
                used.add(value.casefold())


def create_output_directory(source, destination):
    base = Path(destination).expanduser() if destination else Path(source).resolve().parent
    # Do not follow pre-existing symlinks in a user-selected destination.
    if any(p.is_symlink() for p in (base, *base.parents) if str(p) not in ("/var", "/tmp")):
        raise ValueError(f'Output destination contains a symbolic link: {base}')
    base.mkdir(parents=True, exist_ok=True)
    stem = Path(source).stem + '_processed'
    for index in range(100000):
        folder = base / (stem if index == 0 else f'{stem}_{index:03d}')
        try:
            folder.mkdir()
            return str(folder.resolve())
        except FileExistsError:
            continue
    raise OSError('Could not allocate a new output directory')
