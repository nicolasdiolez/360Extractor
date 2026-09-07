"""Portable COLMAP runner copied into each exported dataset.

Run with Python 3.10+ and a COLMAP installation supporting rig_configurator.
This file uses only the standard library so the exported copy is standalone.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


def prepare(dataset, destination):
    """Build a clean per-camera image tree and a separate COLMAP mask tree."""
    destination.mkdir(parents=True, exist_ok=False)
    names = []
    for line in (dataset / 'images.jsonl').open(encoding='utf-8'):
        entry = json.loads(line)
        source = dataset / entry['image']
        relative = Path(entry['camera']) / f"frame{entry['frame']:09d}{source.suffix}"
        target = destination / 'images' / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            os.link(source, target)
        except OSError:
            shutil.copy2(source, target)
        names.append(relative.as_posix())
        if entry.get('mask'):
            mask = destination / 'masks' / (relative.as_posix() + '.png')
            mask.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(dataset / entry['mask'], mask)
    (destination / 'images.txt').write_text('\n'.join(names) + '\n', encoding='utf-8')
    (destination / 'masks').mkdir(exist_ok=True)
    if not names:
        raise ValueError('No exported images available for reconstruction')
    return destination


def main():
    calibration = Path(__file__).resolve().parent
    dataset = calibration.parent
    destination = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else calibration / 'workspace'
    prepare(dataset, destination)
    database = str(destination / 'database.db')
    images = str(destination / 'images')
    rig = json.loads((calibration / 'rig_config.json').read_text(encoding='utf-8'))
    params = rig[0]['cameras'][0]['camera_params']
    subprocess.run(['colmap', 'feature_extractor', '--database_path', database,
                    '--image_path', images, '--image_list_path', str(destination / 'images.txt'),
                    '--ImageReader.mask_path', str(destination / 'masks'),
                    '--ImageReader.camera_model', 'PINHOLE',
                    '--ImageReader.camera_params', ','.join(str(p) for p in params),
                    '--ImageReader.single_camera_per_folder', '1'], check=True)
    subprocess.run(['colmap', 'rig_configurator', '--database_path', database,
                    '--rig_config_path', str(calibration / 'rig_config.json')], check=True)
    subprocess.run(['colmap', 'sequential_matcher', '--database_path', database], check=True)
    (destination / 'sparse').mkdir()
    subprocess.run(['colmap', 'mapper', '--database_path', database, '--image_path', images,
                    '--output_path', str(destination / 'sparse'),
                    '--Mapper.ba_refine_focal_length', '0', '--Mapper.ba_refine_principal_point', '0',
                    '--Mapper.ba_refine_extra_params', '0', '--Mapper.ba_refine_sensor_from_rig', '0'], check=True)


if __name__ == '__main__':
    main()
