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
    """Turnkey COLMAP script with the exact intrinsics fixed during BA."""
    f = focal_px_from_fov(fov_deg, resolution)
    c = resolution / 2.0
    params = f"{f:.6f},{f:.6f},{c:.6f},{c:.6f}"
    return f"""#!/usr/bin/env bash
# Turnkey COLMAP reconstruction for a {APP_NAME} export.
#
# The virtual cameras have EXACT known intrinsics (focal derived from the
# FOV setting), so they are passed to the feature extractor and FIXED during
# bundle adjustment — COLMAP only has to estimate the trajectory.
#
# Usage:   ./reconstruct.sh [images_dir] [workspace_dir]
# Default: images_dir = the parent folder of this script's directory.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${{BASH_SOURCE[0]}}")" && pwd)"
IMAGES_DIR="${{1:-$SCRIPT_DIR/..}}"
WORK_DIR="${{2:-$SCRIPT_DIR/workspace}}"
DB="$WORK_DIR/database.db"

mkdir -p "$WORK_DIR/sparse"

colmap feature_extractor \\
  --database_path "$DB" \\
  --image_path "$IMAGES_DIR" \\
  --ImageReader.camera_model PINHOLE \\
  --ImageReader.camera_params "{params}" \\
  --ImageReader.single_camera 1

colmap exhaustive_matcher --database_path "$DB"

colmap mapper \\
  --database_path "$DB" \\
  --image_path "$IMAGES_DIR" \\
  --output_path "$WORK_DIR/sparse" \\
  --Mapper.ba_refine_focal_length 0 \\
  --Mapper.ba_refine_principal_point 0 \\
  --Mapper.ba_refine_extra_params 0

echo "Sparse model written to $WORK_DIR/sparse"
echo "GLOMAP users: replace the mapper step with"
echo "  glomap mapper --database_path \\"$DB\\" --image_path \\"$IMAGES_DIR\\" --output_path \\"$WORK_DIR/sparse\\""
"""


_README = """COLMAP calibration priors — generated by {app} {version}
=========================================================

These files hand a reconstruction pipeline everything this export already
knows exactly, so it does not have to estimate it:

cameras.txt
    The one PINHOLE camera every exported view shares, in COLMAP text
    format. fx = fy = 0.5*width / tan(FOV/2); principal point at the image
    center. These values are exact by construction, not estimates.

rig_rotations.json
    The exact rotation of each virtual view relative to the rig, as
    [qw,qx,qy,qz] quaternions (see the "convention" field inside). All views
    of one frame share the same optical center (baseline 0). Useful to build
    COLMAP rig configurations, seed pose priors, or sanity-check a
    reconstruction.

reconstruct.sh
    A ready-to-run COLMAP pipeline using the exact intrinsics, kept FIXED
    during bundle adjustment. Requires `colmap` on your PATH. GLOMAP users:
    see the note the script prints at the end.

Masks: COLMAP expects a mask named "<image>.png" next to (or mirrored under
--ImageReader.mask_path) each "<image>". With the default RealityScan naming
this export writes "<image>.mask.png" instead; to produce COLMAP-convention
masks, use the custom naming mode with mask pattern "{{image_name}}.png".
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
        return False
