#!/usr/bin/env python3
"""Small, reproducible COLMAP pilot; not a dense or metrological benchmark.

Run from an installed source environment; see docs/BENCHMARK_PROTOCOL.md.
Sources are read in place. Each invocation requires a fresh output directory.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import platform
import re
import shutil
import subprocess
import time

import cv2

from extractor360.core.job import Job
from extractor360.core.processor import ProcessingWorker
from extractor360.core.reconstruction import prepare, _read_rig


def save(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')


def run_colmap(root, command, args):
    started = time.monotonic()
    argv = [shutil.which('colmap'), command, '--log_target', 'stderr', *map(str, args)]
    with (root / f'{command}.log').open('w') as log:
        result = subprocess.run(argv, stdout=log, stderr=subprocess.STDOUT, timeout=600)
    record = {'command': argv, 'seconds': time.monotonic() - started, 'returncode': result.returncode}
    with (root / 'commands.jsonl').open('a') as log:
        log.write(json.dumps(record) + '\n')
    if result.returncode:
        raise RuntimeError(f'{command} exited {result.returncode}; see {root}')
    return record['seconds']


def reconstruct(root, dataset=None):
    if dataset:
        params, _ = _read_rig(dataset / 'colmap' / 'rig_config.json')
        prepare(dataset, root)
        camera_args = ['--ImageReader.camera_model', 'PINHOLE',
                       '--ImageReader.camera_params', ','.join(map(str, params)),
                       '--ImageReader.single_camera_per_folder', 1]
    else:
        camera_args = ['--ImageReader.camera_model', 'EQUIRECTANGULAR', '--ImageReader.single_camera', 1]
    db, images = root / 'database.db', root / 'images'
    started = time.monotonic()
    run_colmap(root, 'feature_extractor', [
        '--database_path', db, '--image_path', images, *camera_args,
        '--FeatureExtraction.use_gpu', 0, '--FeatureExtraction.num_threads', 4,
        '--SiftExtraction.max_num_features', 8192])
    if dataset:
        run_colmap(root, 'rig_configurator', ['--database_path', db,
                   '--rig_config_path', dataset / 'colmap' / 'rig_config.json'])
    run_colmap(root, 'sequential_matcher', [
        '--database_path', db, '--FeatureMatching.use_gpu', 0, '--FeatureMatching.num_threads', 4,
        '--SequentialMatching.overlap', 10, '--SequentialMatching.quadratic_overlap', 0])
    (root / 'sparse').mkdir()
    run_colmap(root, 'mapper', [
        '--database_path', db, '--image_path', images, '--output_path', root / 'sparse',
        '--Mapper.num_threads', 4, '--Mapper.random_seed', 0, '--Mapper.min_model_size', 3,
        '--Mapper.ba_refine_focal_length', 0, '--Mapper.ba_refine_principal_point', 0,
        '--Mapper.ba_refine_extra_params', 0, '--Mapper.ba_refine_sensor_from_rig', 0])
    seconds = time.monotonic() - started
    models = []
    for model in sorted((root / 'sparse').iterdir()):
        if not model.is_dir():
            continue
        txt = model / 'text'
        txt.mkdir()
        run_colmap(model, 'model_converter', ['--input_path', model, '--output_path', txt, '--output_type', 'TXT'])
        lines = [line for line in (txt / 'images.txt').read_text().splitlines() if not line.startswith('#')]
        names = [line.split(maxsplit=9)[-1] for line in lines[::2] if line]
        frames = sorted({int(re.search(r'frame(\d+)', name)[1]) for name in names})
        points = [line.split() for line in (txt / 'points3D.txt').read_text().splitlines()
                  if line and not line.startswith('#')]
        models.append({'model': model.name, 'registered_images': len(names),
                       'registered_captures': len(frames), 'frame_indices': frames,
                       'points3D': len(points),
                       'mean_reprojection_error_pixels': sum(float(p[7]) for p in points) / len(points) if points else None})
    return {'reconstruction_seconds': seconds, 'models': models}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--captures', type=int, default=8)
    parser.add_argument('--resolution', type=int, default=512)
    args = parser.parse_args()
    if not 3 <= args.captures <= 32 or not 64 <= args.resolution <= 1024:
        parser.error('Pilot limits: 3..32 captures, 64..1024 pixel faces')
    if not shutil.which('colmap'):
        parser.error('COLMAP is required')
    source = args.input.resolve(strict=True)
    before = source.stat()
    cap = cv2.VideoCapture(str(source))
    try:
        width, height = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        frame_count, fps = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)), cap.get(cv2.CAP_PROP_FPS)
    finally:
        cap.release()
    if width != height * 2 or height <= 0 or frame_count < 3 or fps <= 0:
        parser.error('Requires a decoded 2:1 stitched panorama video with known frame count/FPS')
    args.output.mkdir(parents=True, exist_ok=False)
    with source.open('rb') as file:
        digest = hashlib.file_digest(file, 'sha256').hexdigest()
    summary = {'source': str(source), 'sha256': digest, 'source_bytes': before.st_size,
               'source_width': width, 'source_height': height, 'frame_count': frame_count, 'fps': fps,
               'platform': platform.platform(), 'python': platform.python_version(), 'opencv': cv2.__version__,
               'colmap': subprocess.run(['colmap', '-h'], capture_output=True, text=True).stdout.splitlines()[:2],
               'git_head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
               'working_tree_status': subprocess.check_output(['git', 'status', '--short'], text=True),
               'face_resolution': args.resolution, 'native_width': args.resolution * 4, 'cases': {}}
    save(args.output / 'summary.json', summary)
    regular_frames = []
    for name in ('regular', 'adaptive', 'native'):
        print(f'Starting {source.name}: {name}', flush=True)
        started = time.monotonic()
        try:
            dataset = None
            if name != 'native':
                job = Job(str(source), settings={
                    'custom_output_dir': str(args.output / name), 'layout_mode': 'cube',
                    'resolution': args.resolution, 'interval_unit': 'Frames',
                    'interval_value': math.ceil(frame_count / args.captures),
                    'export_colmap': True, 'mask_profile': 'colmap', 'exif_intrinsics': False,
                    'adaptive_mode': name == 'adaptive', 'adaptive_threshold': 0.5,
                })
                worker = ProcessingWorker([job])
                worker.run()
                if worker.error_count:
                    raise RuntimeError(job.result)
                dataset = Path(job.result['output_dir'])
                records = [json.loads(line) for line in (dataset / 'images.jsonl').read_text().splitlines()]
                frames = sorted({record['frame'] for record in records})
                if name == 'regular':
                    regular_frames = frames
                workspace = args.output / name / 'workspace'
                image_count = len(records)
            else:
                if not regular_frames:
                    raise RuntimeError('No regular capture list available')
                workspace = args.output / name / 'workspace'
                images = workspace / 'images'
                images.mkdir(parents=True)
                cap = cv2.VideoCapture(str(source))
                try:
                    for index in range(frame_count):
                        if not cap.grab():
                            raise RuntimeError(f'Decode ended at {index}')
                        if index not in regular_frames:
                            continue
                        ok, frame = cap.retrieve()
                        if not ok:
                            raise RuntimeError(f'Cannot decode {index}')
                        resized = cv2.resize(frame, (args.resolution * 4, args.resolution * 2), interpolation=cv2.INTER_AREA)
                        if not cv2.imwrite(str(images / f'frame{index:09d}.jpg'), resized, [cv2.IMWRITE_JPEG_QUALITY, 95]):
                            raise OSError('Native image write failed')
                finally:
                    cap.release()
                frames, image_count = regular_frames, len(regular_frames)
            record = {'preparation_seconds': time.monotonic() - started, 'input_captures': len(frames),
                      'input_images': image_count, 'frame_indices': frames}
            record.update(reconstruct(workspace, dataset))
            summary['cases'][name] = record
        except (RuntimeError, OSError, subprocess.SubprocessError) as exc:
            summary['cases'][name] = {'error': str(exc)}
        save(args.output / 'summary.json', summary)
        print(json.dumps(summary['cases'][name]), flush=True)
    after = source.stat()
    summary['source_size_mtime_unchanged'] = (before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns)
    # Count unique inodes because reconstruction staging uses hardlinks.
    files = { (p.stat().st_dev, p.stat().st_ino): p.stat() for p in args.output.rglob('*') if p.is_file() }
    summary['allocated_bytes_unique_inodes'] = sum(stat.st_blocks * 512 for stat in files.values())
    save(args.output / 'summary.json', summary)
    if not summary['source_size_mtime_unchanged'] or any('error' in case for case in summary['cases'].values()):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
