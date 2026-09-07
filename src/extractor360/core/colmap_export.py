"""
COLMAP calibration/rig priors export (I1-N2).

The virtual rig is fully known: every view shares the exact same PINHOLE
intrinsics (focal derived from the FOV), and the rotation of each view
relative to the rig is exactly the yaw/pitch/roll used for reprojection.
A structure-from-motion pipeline normally spends its riskiest phase
estimating precisely this — so we hand it over:

- ``cameras.txt``     exact shared PINHOLE intrinsics (COLMAP text format)
- ``rig_rotations.json``  exact cam-from-rig quaternion per view
- ``reconstruct.sh``  turnkey COLMAP run with the intrinsics FIXED during
                      bundle adjustment (they are exact; refining them against
                      noise can only hurt)
- ``README.txt``      what each file is and how to use it (COLMAP/GLOMAP)

Everything here is pure except :func:`write_colmap_export`.
"""
import json
import math
import os
import stat
from pathlib import Path
import shutil

import numpy as np

from extractor360.core.exif_writer import focal_px_from_fov
from extractor360.core.geometry import GeometryProcessor
from extractor360.core.version import APP_NAME, VERSION
from extractor360.utils.logger import logger


def rotation_matrix_to_quat(R) -> list:
    """Convert a 3x3 rotation matrix to a unit quaternion [qw, qx, qy, qz].

    Shepperd's method (numerically stable for all traces). The returned
    quaternion is canonicalized to qw >= 0.
    """
    m00, m01, m02 = R[0]
    m10, m11, m12 = R[1]
    m20, m21, m22 = R[2]
    trace = m00 + m11 + m22

    if trace > 0.0:
        s = 0.5 / math.sqrt(trace + 1.0)
        w = 0.25 / s
        x = (m21 - m12) * s
        y = (m02 - m20) * s
        z = (m10 - m01) * s
    elif m00 > m11 and m00 > m22:
        s = 2.0 * math.sqrt(1.0 + m00 - m11 - m22)
        w = (m21 - m12) / s
        x = 0.25 * s
        y = (m01 + m10) / s
        z = (m02 + m20) / s
    elif m11 > m22:
        s = 2.0 * math.sqrt(1.0 + m11 - m00 - m22)
        w = (m02 - m20) / s
        x = (m01 + m10) / s
        y = 0.25 * s
        z = (m12 + m21) / s
    else:
        s = 2.0 * math.sqrt(1.0 + m22 - m00 - m11)
        w = (m10 - m01) / s
        x = (m02 + m20) / s
        y = (m12 + m21) / s
        z = 0.25 * s

    q = np.array([w, x, y, z], dtype=float)
    q /= np.linalg.norm(q)
    if q[0] < 0:
        q = -q
    return [float(v) for v in q]


def quat_to_rotation_matrix(q) -> np.ndarray:
    """Inverse of :func:`rotation_matrix_to_quat` (unit quaternion assumed)."""
    w, x, y, z = q
    return np.array([
        [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
        [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
        [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
    ], dtype=float)


def build_cameras_txt(fov_deg: float, resolution: int) -> str:
    """COLMAP cameras.txt with the one exact PINHOLE camera all views share."""
    f = focal_px_from_fov(fov_deg, resolution)
    c = resolution / 2.0
    return (
        "# Camera list with one line of data per camera:\n"
        "#   CAMERA_ID, MODEL, WIDTH, HEIGHT, PARAMS[]\n"
        f"# Exact virtual pinhole from {APP_NAME} (focal derived from FOV {fov_deg}deg)\n"
        f"1 PINHOLE {resolution} {resolution} {f:.6f} {f:.6f} {c:.6f} {c:.6f}\n"
    )


def build_rig_rotations(views, active_view_names, fov_deg: float, resolution: int) -> dict:
    """Exact cam-from-rig rotation for every exported view.

    Convention: camera axes x right, y down, z forward (the reprojection
    convention of :mod:`extractor360.core.geometry`). ``cam_from_rig_quat``
    rotates rig-frame vectors into this view's camera frame — i.e. the
    transpose of the yaw/pitch/roll matrix used to cast the view's rays.
    """
    entries = []
    for name, yaw, pitch, roll in views:
        if name not in active_view_names:
            continue
        rig_from_cam = GeometryProcessor.get_rotation_matrix(yaw, pitch, roll)
        cam_from_rig = rig_from_cam.T
        entries.append({
            "name": name,
            "yaw_deg": float(yaw),
            "pitch_deg": float(pitch),
            "roll_deg": float(roll),
            "cam_from_rig_quat": rotation_matrix_to_quat(cam_from_rig),
        })
    f = focal_px_from_fov(fov_deg, resolution)
    return {
        "generated_by": f"{APP_NAME} {VERSION}",
        "convention": (
            "Camera axes: x right, y down, z forward. cam_from_rig_quat is "
            "[qw,qx,qy,qz], rotating rig-frame vectors into the camera frame. "
            "All views share the rig center (baseline = 0) and the PINHOLE "
            "intrinsics below."
        ),
        "intrinsics": {
            "model": "PINHOLE",
            "width": resolution,
            "height": resolution,
            "fx": f, "fy": f,
            "cx": resolution / 2.0, "cy": resolution / 2.0,
            "fov_deg": float(fov_deg),
        },
        "views": entries,
    }


def build_reconstruct_sh(fov_deg: float, resolution: int) -> str:
    """Shell convenience wrapper around the portable runner."""
    return '#!/usr/bin/env bash\nset -euo pipefail\nSCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"\nexec python3 "$SCRIPT_DIR/reconstruct.py" "$@"\n'


_README = """COLMAP export — {app} {version}

Run: python reconstruct.py [new_workspace_directory]
Requires Python 3.10+ and COLMAP with native rig_configurator support.
The workspace must not already exist. images.jsonl selects only confirmed image
outputs; masks are copied to a separate tree with COLMAP's <image-name>.png rule.
One folder per view and identical per-frame basenames preserve capture groups.
rig_config.json is applied before sequential matching. Intrinsics and relative
sensor rotations are held fixed during mapping. rig_rotations.json additionally
records the rotations relative to the original panorama coordinate frame.

This pipeline follows https://colmap.github.io/rigs.html . It still requires
qualification on real camera datasets and the target COLMAP build. Stitching
artifacts and non-central panoramas can violate the ideal virtual pinhole model.
The generated calibration is not evidence of successful reconstruction.
"""


def write_colmap_export(output_dir: str, views, active_view_names, fov_deg: float,
                        resolution: int) -> bool:
    """Write the colmap/ priors folder into a job's output directory."""
    target = os.path.join(output_dir, "colmap")
    try:
        os.makedirs(target, exist_ok=True)

        with open(os.path.join(target, "cameras.txt"), "w", encoding="utf-8") as fh:
            fh.write(build_cameras_txt(fov_deg, resolution))

        rig = build_rig_rotations(views, active_view_names, fov_deg, resolution)
        with open(os.path.join(target, "rig_rotations.json"), "w", encoding="utf-8") as fh:
            json.dump(rig, fh, indent=2)

        selected = [v for v in views if v[0] in active_view_names]
        reference = GeometryProcessor.get_rotation_matrix(*selected[0][1:]) if selected else np.eye(3)
        f = focal_px_from_fov(fov_deg, resolution)
        cameras = []
        for index, (name, yaw, pitch, roll) in enumerate(selected):
            camera = {"image_prefix": name + "/", "camera_model_name": "PINHOLE",
                      "camera_params": [f, f, resolution/2, resolution/2]}
            if index == 0:
                camera["ref_sensor"] = True
            else:
                relative = GeometryProcessor.get_rotation_matrix(yaw, pitch, roll).T @ reference
                camera.update(cam_from_rig_rotation=rotation_matrix_to_quat(relative), cam_from_rig_translation=[0, 0, 0])
            cameras.append(camera)
        with open(os.path.join(target, "rig_config.json"), "w", encoding="utf-8") as fh:
            json.dump([{"cameras": cameras}], fh, indent=2)
        shutil.copyfile(Path(__file__).with_name('reconstruction.py'), os.path.join(target, 'reconstruct.py'))
        script_path = os.path.join(target, "reconstruct.sh")
        with open(script_path, "w", encoding="utf-8") as fh:
            fh.write(build_reconstruct_sh(fov_deg, resolution))
        os.chmod(script_path, os.stat(script_path).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

        with open(os.path.join(target, "README.txt"), "w", encoding="utf-8") as fh:
            fh.write(_README.format(app=APP_NAME, version=VERSION))

        logger.info(f"COLMAP priors written to {target}")
        return True
    except OSError as e:
        logger.error(f"Could not write COLMAP export to {target}: {e}")
        raise OSError(f"COLMAP export failed: {e}") from e
