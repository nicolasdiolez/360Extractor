"""Bounded COLMAP diagnostic of confirmed 360 exports, independent of Qt/AI.

This is a sample alignment, not a reconstruction-quality score. All views of
one physical frame stay together. Original images/masks are only read.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import signal
import subprocess
import time
from typing import Any, TypedDict

from extractor360.core.project import source_identity, source_problem
from extractor360.core.diagnostic import diagnostic_options, model_overview
from extractor360.core.reconstruction import _read_index, _read_rig
from extractor360.core.storage import require_free_space
from extractor360.core.validation import validate_settings

MAX_BYTES = 256 * 1024**2
MAX_SECONDS = 300


class _Component(TypedDict):
    models: list[str]
    frames: set[int]


class CommandFailed(RuntimeError):
    def __init__(self, name, returncode, log_path, hint=''):
        self.command, self.returncode, self.log_path = name, returncode, log_path
        super().__init__(f'{name} failed (exit {returncode}). See {log_path}. {hint}')


def no_model_outcome(error, sparse):
    if error.command != 'mapper' or error.returncode != 1 or any(sparse.iterdir()):
        return False
    with error.log_path.open('rb') as file:
        file.seek(max(0, error.log_path.stat().st_size - 65536))
        tail = file.read().decode('utf-8', errors='replace')
    return 'Failed to create any sparse model' in tail


def _json(path):
    if path.stat().st_size > 16 * 1024**2:
        raise ValueError(f'Diagnostic input exceeds 16 MiB: {path.name}')
    return json.loads(path.read_text(encoding='utf-8'))


def settings_key(settings):
    # A project intentionally forgets model trust when reopened. The diagnostic
    # reuses already exported pixels and never loads that model.
    value = copy.deepcopy(settings)
    value['trust_custom_model'] = True
    value = validate_settings(value)
    for key in ('custom_output_dir', 'trust_custom_model', 'excluded_frames'):
        value.pop(key, None)
    return value


def load_export(job):
    """Reject stale/partial exports before allocating a workspace."""
    problem = source_problem(job) if job.source_check_required or job.source_identity is not None else None
    if problem:
        raise ValueError(problem)
    folder = job.result.get('output_dir')
    if not folder:
        raise ValueError('Extract this source with COLMAP export enabled first.')
    dataset = Path(folder).resolve(strict=True)
    manifest = _json(dataset / 'manifest.json')
    if manifest.get('status') != 'completed' or manifest.get('run_id') != job.result.get('run_id'):
        raise ValueError('The last export is incomplete or belongs to a different run. Extract again.')
    identity = manifest.get('source_identity', {})
    if source_identity(job.file_path) != {k: identity.get(k) for k in ('size_bytes', 'mtime_ns')}:
        raise ValueError('The export describes a different source. Extract again.')
    if not manifest.get('settings', {}).get('is_360'):
        raise ValueError('This first diagnostic supports 360 exports with calibrated perspective rigs.')
    if settings_key(job.settings) != settings_key(manifest['settings']):
        raise ValueError('Settings changed since this export. Extract again before diagnosing alignment.')
    if (dataset / 'images.jsonl').stat().st_size > 16 * 1024**2:
        raise ValueError('Diagnostic index exceeds 16 MiB; use a smaller export.')
    entries = _read_index(dataset)
    rig_path = dataset / 'colmap' / 'rig_config.json'
    params, names = _read_rig(rig_path)
    if any(relative.parts[0] not in names for _, relative, _ in entries):
        raise ValueError('The confirmed index contains a camera outside its rig.')
    masks = manifest.get('mask_contract', {})
    if any(mask is not None for _, _, mask in entries) and masks.get('ignored_value') != 0:
        raise ValueError('COLMAP diagnostic requires masks with black = ignored.')
    records = [json.loads(line) for line in (dataset / 'images.jsonl').read_text(encoding='utf-8').splitlines()]
    frames: dict[int, dict[str, Any]] = {}
    for record, entry in zip(records, entries):
        frame = record['frame']
        item = frames.setdefault(frame, {'frame': frame, 'images': [],
                                        'timestamp_seconds': record.get('timestamp_seconds'),
                                        'timestamp_source': record.get('timestamp_source', 'unavailable')})
        item['images'].append(entry[1].as_posix())
    if len(frames) > 10000:
        raise ValueError('Diagnostic is limited to exports of 10000 physical captures.')
    return dataset, manifest, entries, params, _json(rig_path), frames


def fingerprint(job):
    return hashlib.sha256(json.dumps({'run': job.result.get('run_id'), 'source': job.source_identity,
                                     'settings': settings_key(job.settings),
                                     'excluded': sorted(job.settings.get('excluded_frames', []))},
                                    sort_keys=True, allow_nan=False).encode()).hexdigest()


def _export_signature(dataset, entries):
    """Detect changed export metadata/index and replaced selected pixel files."""
    digest = hashlib.sha256()
    for name in ('manifest.json', 'images.jsonl', 'colmap/rig_config.json'):
        digest.update((dataset / name).read_bytes())
    for source, _, mask in entries:
        for path in (source, mask):
            if path is not None:
                stat = path.stat()
                digest.update(f'{path}:{stat.st_size}:{stat.st_mtime_ns}'.encode())
    return digest.hexdigest()


def sample_frames(frames, excluded, maximum):
    if type(maximum) is not int or not 3 <= maximum <= 16:
        raise ValueError('Choose between 3 and 16 physical captures.')
    available = sorted(set(frames) - set(excluded))
    if len(available) < 3:
        raise ValueError('At least three included, exported physical captures are required.')
    count = min(maximum, len(available))
    return [available[round(i * (len(available) - 1) / (count - 1))] for i in range(count)]


def read_registered_images(path, allowed):
    """Read COLMAP text image records, retaining empty observation lines."""
    names = set()
    expect_image = True
    for line in path.read_text(encoding='utf-8').splitlines():
        if line.startswith('#'):
            continue
        if expect_image:
            fields = line.split(maxsplit=9)
            if len(fields) != 10 or fields[9] not in allowed or fields[9] in names:
                raise ValueError('COLMAP returned an invalid, duplicate or unexpected registered image.')
            int(fields[0])
            int(fields[8])
            if not all(math.isfinite(float(value)) for value in fields[1:8]):
                raise ValueError('COLMAP returned a nonfinite pose.')
            names.add(fields[9])
        expect_image = not expect_image
    if not expect_image:
        raise ValueError('Truncated COLMAP images.txt record.')
    return names


def summarize(frames, sampled, excluded, models):
    rows: list[dict[str, Any]] = []
    groups: list[dict[str, Any]] = []
    for model, names in models.items():
        group_frames = sorted(frame for frame in sampled if set(frames[frame]['images']) & names)
        groups.append({'model': model, 'frames': group_frames, 'registered_images': len(names)})
    for frame, item in sorted(frames.items()):
        memberships = {model: len(set(item['images']) & names) for model, names in models.items()
                       if set(item['images']) & names}
        state = ('excluded' if frame in excluded else 'not_sampled' if frame not in sampled
                 else 'registered' if memberships else 'unregistered')
        rows.append({**item, 'state': state, 'models': memberships})
    # Connected components of *model overlap*. Two models sharing captures are
    # alternative reconstructions, not evidence of disconnected scene groups.
    components: list[_Component] = []
    for group in groups:
        capture_set = set(group['frames'])
        touching = [component for component in components if component['frames'] & capture_set]
        merged: _Component = {'models': [group['model']], 'frames': capture_set}
        for component in touching:
            merged['models'] += component['models']
            merged['frames'] |= component['frames']
            components.remove(component)
        components.append(merged)
    report: dict[str, Any] = {'captures': rows, 'models': groups,
            'groups': [{'models': c['models'], 'frames': sorted(c['frames'])} for c in components],
            'sampled_frames': sampled,
            'registered_captures': sum(row['state'] == 'registered' for row in rows),
            'unregistered_captures': sum(row['state'] == 'unregistered' for row in rows)}
    report['overview'] = model_overview(report)
    return report


class AlignmentRunner:
    """Run one disposable CPU workspace with size, time and cancellation bounds."""
    def __init__(self, cancelled=lambda: False, progress=lambda message: None, budget=None):
        self.cancelled = cancelled
        self.progress = progress
        self.budget = budget

    def _check(self):
        if self.budget is not None:
            self.budget._check()
            return
        if self.cancelled():
            raise InterruptedError('Alignment cancelled')
        if time.monotonic() > self.deadline:
            raise TimeoutError(f'Alignment exceeded {MAX_SECONDS} seconds')
        size = 0
        for path in self.root.rglob('*'):
            try:
                if path.is_file():
                    size += path.stat().st_size
            except FileNotFoundError:
                # Native tools can remove their own temporary files mid-scan.
                continue
        if size > MAX_BYTES:
            raise OSError('Alignment reached its 256 MiB workspace limit')
        require_free_space(self.root, 8 * 1024**2)

    def _command(self, name, arguments, label=None):
        argv = [self.colmap, name, '--log_target', 'stderr', *map(str, arguments)]
        self._execute(argv, name, label or name, hint='Verify the COLMAP log and supported version (4.2).')

    def _execute(self, argv, name, label, env=None, hint=''):
        self._check()
        self.progress(label)
        started = time.monotonic()
        log_path = self.root / f'{len(self.commands):02d}-{name}.log'
        with log_path.open('xb') as output:
            process = subprocess.Popen(argv, stdout=output, stderr=subprocess.STDOUT,
                                       start_new_session=os.name != 'nt', env=env)
            try:
                while process.poll() is None:
                    self._check()
                    time.sleep(.1)
                self._check()
                if process.returncode:
                    raise CommandFailed(name, process.returncode, log_path, hint)
            finally:
                if process.poll() is None:
                    if os.name != 'nt':
                        try:
                            os.killpg(process.pid, signal.SIGKILL)
                        except ProcessLookupError:
                            pass
                    else:
                        # The sampling helper can own ffprobe/ExifTool children.
                        # taskkill /T closes that process tree on Windows.
                        try:
                            subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'],
                                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
                        except (OSError, subprocess.TimeoutExpired):
                            pass
                        if process.poll() is None:
                            process.kill()
                process.wait()
                self.commands.append({'command': argv, 'seconds': round(time.monotonic() - started, 3),
                                      'returncode': process.returncode})
                (self.root / 'commands.json').write_text(json.dumps(self.commands, indent=2), encoding='utf-8')

    def run_source(self, job, destination, maximum=8):
        from extractor360.core.preflight import run_source
        return run_source(self, job, destination, maximum)

    def run(self, job, destination, maximum=16):
        import cv2  # optional media dependency; no Qt or model imports

        dataset, manifest, entries, params, rig, frames = load_export(job)
        options = diagnostic_options(job.diagnostic_settings)
        options.update(mode='export', maximum=maximum)
        options = diagnostic_options(options)
        window = options['frame_range']
        if window and window[1] >= manifest.get('video', {}).get('total_frames', 0):
            raise ValueError('Diagnostic frame range exceeds the source length recorded in the export')
        excluded = set(job.settings.get('excluded_frames', []))
        available = [f for f in frames if window is None or window[0] <= f <= window[1]]
        sampled = sample_frames(available, excluded, maximum)
        selected_names = {name for frame in sampled for name in frames[frame]['images']}
        entries = [entry for entry in entries if entry[1].as_posix() in selected_names]
        if len(entries) > 128:
            raise ValueError('Diagnostic is limited to 128 views. Choose fewer captures or active cameras.')
        export_signature = _export_signature(dataset, entries)
        colmap = shutil.which('colmap')
        if colmap is None:
            raise FileNotFoundError('Install COLMAP 4.2 and make colmap available on PATH, then retry.')
        self.colmap = colmap
        self.root = Path(destination)
        require_free_space(self.root.parent, MAX_BYTES)
        self.root.mkdir(exist_ok=False)
        self.deadline = time.monotonic() + MAX_SECONDS
        self.commands = []
        try:
            self.progress(f'Preparing confirmed images (maximum {options["resolution"]} pixels per view)')
            resolution = manifest['settings']['resolution']
            scale = min(1, options['resolution'] / resolution)
            dimension = round(resolution * scale)
            for camera in rig[0]['cameras']:
                camera['camera_params'] = [value * scale for value in camera['camera_params']]
            # Some active cameras may have no confirmed pixels in this sample.
            present = {entry[1].parts[0] for entry in entries}
            if present != {camera['image_prefix'][:-1] for camera in rig[0]['cameras']}:
                raise ValueError('Some rig cameras have no confirmed views in this sample. Change the sample or extraction filters.')
            (self.root / 'rig_config.json').write_text(json.dumps(rig, indent=2), encoding='utf-8')
            masks_enabled = any(mask is not None for _, _, mask in entries)
            for original, relative, mask in entries:
                self._check()
                pixels = cv2.imread(str(original))
                if pixels is None or pixels.shape[:2] != (resolution, resolution):
                    raise ValueError(f'Unexpected exported image dimensions: {original.name}')
                target = self.root / 'images' / relative.with_suffix('.jpg')
                target.parent.mkdir(parents=True, exist_ok=True)
                if not cv2.imwrite(str(target), cv2.resize(pixels, (dimension, dimension), interpolation=cv2.INTER_AREA),
                                   [cv2.IMWRITE_JPEG_QUALITY, 95]):
                    raise OSError(f'Could not write diagnostic image: {target}')
                if masks_enabled:
                    import numpy as np
                    mask_pixels = cv2.imread(str(mask), cv2.IMREAD_GRAYSCALE) if mask else np.full((resolution, resolution), 255, np.uint8)
                    if mask_pixels is None or mask_pixels.shape != (resolution, resolution):
                        raise ValueError('Invalid diagnostic mask dimensions')
                    mask_target = self.root / 'masks' / (relative.with_suffix('.jpg').as_posix() + '.png')
                    mask_target.parent.mkdir(parents=True, exist_ok=True)
                    if not cv2.imwrite(str(mask_target), cv2.resize(mask_pixels, (dimension, dimension), interpolation=cv2.INTER_NEAREST)):
                        raise OSError('Could not write diagnostic mask')
            # Use standardized names in the report as well as COLMAP's image list.
            for item in frames.values():
                item['images'] = [Path(name).with_suffix('.jpg').as_posix() for name in item['images']]
            selected_names = {name for frame in sampled for name in frames[frame]['images']}
            (self.root / 'image_list.txt').write_text('\n'.join(sorted(selected_names)) + '\n', encoding='utf-8')
            db, images = self.root / 'database.db', self.root / 'images'
            self._command('feature_extractor', [
                '--database_path', db, '--image_path', images, '--image_list_path', self.root / 'image_list.txt',
                '--ImageReader.camera_model', 'PINHOLE', '--ImageReader.camera_params', ','.join(str(p * scale) for p in params),
                '--ImageReader.single_camera_per_folder', 1,
                '--FeatureExtraction.use_gpu', 0, '--FeatureExtraction.num_threads', 4,
                '--SiftExtraction.max_num_features', 4096,
                *(['--ImageReader.mask_path', self.root / 'masks'] if masks_enabled else [])])
            self._command('rig_configurator', ['--database_path', db, '--rig_config_path', self.root / 'rig_config.json'])
            self._command('sequential_matcher', ['--database_path', db, '--FeatureMatching.use_gpu', 0,
                '--FeatureMatching.num_threads', 4, '--SequentialMatching.overlap', 10,
                '--SequentialMatching.quadratic_overlap', 0])
            sparse = self.root / 'sparse'
            sparse.mkdir()
            mapper_status = 'completed'
            try:
                self._command('mapper', ['--database_path', db, '--image_path', images, '--output_path', sparse,
                    '--Mapper.num_threads', 4, '--Mapper.random_seed', 0, '--Mapper.min_model_size', 3,
                    '--Mapper.ba_refine_focal_length', 0, '--Mapper.ba_refine_principal_point', 0,
                    '--Mapper.ba_refine_extra_params', 0, '--Mapper.ba_refine_sensor_from_rig', 0])
            except CommandFailed as exc:
                if not no_model_outcome(exc, sparse):
                    raise
                mapper_status = 'no_model'
            models = {}
            for model in sorted(sparse.iterdir()):
                if not model.is_dir():
                    continue
                text = model / 'text'
                text.mkdir()
                self._command('model_converter', ['--input_path', model, '--output_path', text, '--output_type', 'TXT'])
                models[model.name] = read_registered_images(text / 'images.txt', selected_names)
            report = {**summarize(frames, sampled, excluded, models), 'schema_version': 1,
                      'fingerprint': fingerprint(job), 'run_id': manifest['run_id'], 'export_signature': export_signature,
                      'resolution': dimension, 'excluded_frames': sorted(excluded), 'mapper_status': mapper_status,
                      'diagnostic_settings': options,
                      'limits': 'Sample only; unregistered does not establish a cause. Overlapping models are alternatives. '
                                'No dense reconstruction, metric accuracy or Gaussian Splatting quality measured.',
                      'seconds': round(time.monotonic() - (self.deadline - MAX_SECONDS), 3)}
            # Recheck source/settings/export identity before accepting the result.
            load_export(job)
            if _export_signature(dataset, entries) != export_signature:
                raise ValueError('The export changed during alignment. Diagnostic discarded; run again.')
            (self.root / 'report.json').write_text(json.dumps(report, indent=2, allow_nan=False), encoding='utf-8')
            self._check()
            return report
        except Exception as exc:
            (self.root / 'failure.json').write_text(json.dumps({'error': str(exc)}), encoding='utf-8')
            raise
