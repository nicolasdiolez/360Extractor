"""Supervised source sampling for an alignment diagnostic before full export."""
from __future__ import annotations

import copy
import json
import math
import os
from pathlib import Path
import shutil
import sys
import time

from extractor360.core.ai_classes import AI_MODEL_VARIANTS
from extractor360.core.alignment import AlignmentRunner, MAX_BYTES, MAX_SECONDS, _json, fingerprint, summarize
from extractor360.core.geometry import GeometryProcessor
from extractor360.core.job import Job
from extractor360.core.project import source_identity, source_problem
from extractor360.core.storage import require_free_space
from extractor360.core.validation import validate_settings
from extractor360.core.diagnostic import diagnostic_options, model_overview


def source_plan(job, maximum):
    diagnostic_options({**diagnostic_options(job.diagnostic_settings), 'maximum': maximum})
    if type(maximum) is not int or not 3 <= maximum <= 16:
        raise ValueError('Choose between 3 and 16 physical captures.')
    settings = validate_settings(job.settings)
    if not settings['is_360'] or Path(job.file_path).suffix.lower() in {'.jpg', '.jpeg', '.png', '.tif', '.tiff'}:
        raise ValueError('Source preflight requires a stitched 360 video.')
    problem = source_problem(job) if job.source_check_required or job.source_identity is not None else None
    if problem:
        raise ValueError(problem)
    identity = source_identity(job.file_path)
    views = GeometryProcessor.generate_views(settings['camera_count'], settings['pitch_offset'], settings['layout_mode'])
    count = len(views) if settings.get('active_cameras') is None else len(settings['active_cameras'])
    if maximum * count > 128:
        raise ValueError('Choose fewer captures or cameras: preflight is limited to 128 views.')
    model_directory = None
    if settings['ai_mode'] != 'None':
        name = settings['ai_model']
        if name in AI_MODEL_VARIANTS.values():
            candidates = [Path(os.environ.get('EXTRACTOR360_MODEL_DIR', str(Path.home() / '.cache/360-extractor/models'))) / name,
                          Path(__file__).resolve().parents[3] / name]
            local = next((path for path in candidates if path.is_file()), None)
            if local is None:
                raise ValueError('Preflight does not download AI models. Provision the selected model first.')
            model_directory = str(local.parent)
        elif not Path(name).is_file():
            raise ValueError('The trusted custom model is missing. Locate it before preflight.')
    return settings, identity, model_directory


def uniform_frames(total, excluded, maximum, frame_range=None):
    """Select ranks without allocating a set/list for the full source video."""
    if type(total) is not int or total < 3 or not 3 <= maximum <= 16:
        raise ValueError('Preflight needs a known source length and at least three frames.')
    window = diagnostic_options({'maximum': maximum, 'frame_range': frame_range})['frame_range']
    start, end = window if window is not None else (0, total - 1)
    if end >= total:
        raise ValueError('Diagnostic frame range exceeds the source length')
    excluded = sorted({frame for frame in excluded if start <= frame <= end})
    available = end - start + 1 - len(excluded)
    if available < 3:
        raise ValueError('At least three source frames must remain included.')
    count = min(maximum, available)
    frames = []
    for i in range(count):
        frame = start + round(i * (available - 1) / (count - 1))
        for excluded_frame in excluded:
            if excluded_frame > frame:
                break
            frame += 1
        frames.append(frame)
    return frames


def sampling_settings(settings, output, resolution=512):
    diagnostic_options({'resolution': resolution})
    result = copy.deepcopy(settings)
    # Thresholds calibrated at export resolution/motion cadence cannot be
    # silently reused on this coarse sample. Retain geometry and AI decisions.
    result.update(resolution=resolution, output_format='jpg', quality=95,
                  mask_profile='colmap', export_colmap=True, custom_output_dir=str(output),
                  interval_unit='Frames', interval_value=1, adaptive_mode=False,
                  blur_filter_enabled=False, smart_blur_enabled=False,
                  export_telemetry=False, exif_intrinsics=False)
    return validate_settings(result)


def sample_source(request_path):
    """Child entry: native decoding/inference stays inside a killable process."""
    import cv2
    from extractor360.core.processor import ProcessingWorker

    request_path = Path(request_path).resolve(strict=True)
    root = request_path.parent
    request = _json(request_path)
    options = diagnostic_options(request.get('diagnostic_settings', {}))
    job = Job(request['source'], settings=request['settings'], source_identity=request['source_identity'], source_check_required=True,
              diagnostic_settings=options)
    settings, _, _ = source_plan(job, request['maximum'])
    cap = cv2.VideoCapture(job.file_path)
    try:
        if not cap.isOpened():
            raise ValueError('Could not open the source video')
        raw_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        width, height = cap.get(cv2.CAP_PROP_FRAME_WIDTH), cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
        if not math.isfinite(raw_count) or raw_count < 3:
            raise ValueError('The decoder cannot establish a source frame count for preflight')
        if not (width > 0 and height > 0 and width == 2 * height):
            raise ValueError('Preflight expects a stitched 2:1 equirectangular video')
        frames = uniform_frames(int(raw_count), settings['excluded_frames'], request['maximum'], options['frame_range'])
    finally:
        cap.release()
    original = copy.deepcopy(settings)
    job.settings = sampling_settings(settings, root / 'sample', options['resolution'])
    worker = ProcessingWorker([job], diagnostic_frames=frames)
    worker.run()
    if worker.error_count or job.result.get('status') != 'completed':
        raise RuntimeError(job.result.get('error', 'Sampling did not complete'))
    if source_problem(job):
        raise ValueError('Source changed while sampling; diagnostic discarded')
    overrides = {key: {'project': original.get(key), 'sample': value} for key, value in job.settings.items()
                 if value != original.get(key) and key != 'custom_output_dir'}
    result = {'settings': job.settings, 'result': job.result, 'requested_frames': frames,
              'source_frame_count': int(raw_count), 'overrides': overrides}
    with (root / 'sample-result.json').open('x', encoding='utf-8') as file:
        json.dump(result, file, indent=2, allow_nan=False)


def run_source(runner, job, destination, maximum):
    settings, identity, model_directory = source_plan(job, maximum)
    options = diagnostic_options({**diagnostic_options(job.diagnostic_settings), 'mode': 'source', 'maximum': maximum})
    # Validate the sampling projection before creating a workspace.
    sampling_settings(settings, destination, options['resolution'])
    if not shutil.which('colmap'):
        raise FileNotFoundError('Install COLMAP 4.2 and make colmap available on PATH, then retry.')
    if runner.cancelled():
        raise InterruptedError('Preflight cancelled')
    runner.root = Path(destination)
    require_free_space(runner.root.parent, MAX_BYTES)
    runner.root.mkdir(exist_ok=False)
    runner.deadline = time.monotonic() + MAX_SECONDS
    runner.commands = []
    try:
        request = runner.root / 'sample-request.json'
        request.write_text(json.dumps({'source': job.file_path, 'settings': settings, 'source_identity': identity,
                                       'maximum': maximum, 'diagnostic_settings': options}, allow_nan=False), encoding='utf-8')
        temporary = runner.root / 'temporary'
        temporary.mkdir()
        env = dict(os.environ, EXTRACTOR360_OFFLINE_MODELS='1', EXTRACTOR360_DEVICE='cpu',
                   EXTRACTOR360_MODEL_DIR=model_directory or str(runner.root / 'models'),
                   YOLO_CONFIG_DIR=str(runner.root / 'ultralytics'), PYTHONDONTWRITEBYTECODE='1',
                   TMPDIR=str(temporary), TEMP=str(temporary), TMP=str(temporary))
        if getattr(sys, 'frozen', False):
            argv = [sys.executable, '--diagnostic-sample', str(request)]
        else:
            # Preserve the current source/wheel package in the child, without
            # depending on the terminal's cwd or a globally installed version.
            env['PYTHONPATH'] = str(Path(__file__).resolve().parents[2])
            argv = [sys.executable, '-m', 'extractor360.core.preflight', str(request)]
        try:
            runner._execute(argv, 'source-sampling', f'Sampling up to {maximum} source captures at reduced resolution', env=env)
        except RuntimeError as exc:
            error_path = runner.root / 'sample-error.json'
            if error_path.is_file():
                raise RuntimeError(_json(error_path)['error']) from exc
            raise
        sample = _json(runner.root / 'sample-result.json')
        sampled_job = Job(job.file_path, settings=sample['settings'], result=sample['result'],
                          source_identity=identity, source_check_required=True, diagnostic_settings=options)
        requested = sample['requested_frames']
        index = Path(sampled_job.result['output_dir']) / 'images.jsonl'
        records = [json.loads(line) for line in index.read_text(encoding='utf-8').splitlines()] if index.is_file() else []
        confirmed = sorted({entry['frame'] for entry in records})
        if len(confirmed) >= 3:
            report = AlignmentRunner(runner.cancelled, runner.progress, budget=runner).run(
                sampled_job, runner.root / 'alignment', maximum)
        else:
            # Insufficient confirmed captures is an extraction/filter outcome,
            # never evidence that COLMAP failed to register them.
            frames = {frame: {'frame': frame, 'images': [r['image'] for r in records if r['frame'] == frame]}
                      for frame in confirmed}
            report = {**summarize(frames, [], set(), {}), 'schema_version': 1,
                      'resolution': sampled_job.settings['resolution'], 'alignment_not_run': 'Fewer than three confirmed captures'}
        for frame in requested:
            if frame not in confirmed:
                report['captures'].append({'frame': frame, 'images': [], 'models': {}, 'state': 'filtered',
                                           'timestamp_source': 'unavailable'})
        report['captures'].sort(key=lambda item: item['frame'])
        report.update(mode='source_preflight', fingerprint=fingerprint(job),
                      diagnostic_settings=options,
                      source_identity=identity, requested_frames=requested, filtered_captures=len(requested) - len(confirmed),
                      source_frame_count=sample['source_frame_count'], sampling='uniform source frame ranks, independent of export interval',
                      overrides=sample['overrides'], sample_run_id=sampled_job.result['run_id'],
                      elapsed_total_seconds=round(time.monotonic() - (runner.deadline - MAX_SECONDS), 3))
        report['overview'] = model_overview(report)
        if source_identity(job.file_path) != identity:
            raise ValueError('Source changed during preflight; diagnostic discarded')
        runner._check()
        (runner.root / 'report.json').write_text(json.dumps(report, indent=2, allow_nan=False), encoding='utf-8')
        return report
    except Exception as exc:
        (runner.root / 'failure.json').write_text(json.dumps({'error': str(exc)}), encoding='utf-8')
        raise


def sample_main(path):
    try:
        sample_source(path)
    except Exception as exc:
        (Path(path).parent / 'sample-error.json').write_text(json.dumps({'error': str(exc)}), encoding='utf-8')
        raise


if __name__ == '__main__':
    sample_main(sys.argv[1])
