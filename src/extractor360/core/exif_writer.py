"""
EXIF construction and single-write image saving.

The virtual cameras have exactly known intrinsics — the focal length derives
from the FOV setting — and photogrammetry tools (RealityScan, Metashape,
COLMAP) read them from EXIF to bootstrap calibration. This module writes them
on every exported image, together with the capture time and, when a GPS track
is available, the absolute view direction (GPSImgDirection).

All builders are pure; the only I/O is in :func:`save_image_with_exif`.
"""
import math
import os

import cv2
import piexif
from PIL import Image

from extractor360.core.version import APP_NAME, VERSION
from extractor360.utils.logger import logger

EXIF_MAKE = "360Extractor"
# 35mm-film reference width (mm) used for the equivalent focal length.
FULL_FRAME_WIDTH_MM = 36.0


def focal_35mm_from_fov(fov_deg: float) -> float:
    """35mm-equivalent focal length (mm) of a pinhole with this horizontal FOV.

    f_mm = 36 / (2 * tan(FOV/2)); e.g. FOV 90° -> 18 mm.
    """
    return FULL_FRAME_WIDTH_MM / (2.0 * math.tan(math.radians(fov_deg) / 2.0))


def focal_px_from_fov(fov_deg: float, width_px: int) -> float:
    """Focal length in pixels of a pinhole with this horizontal FOV and width."""
    return (0.5 * width_px) / math.tan(math.radians(fov_deg) / 2.0)


def _rational(value: float, den: int = 1000):
    return (int(round(value * den)), den)


def _deg_min_sec(value: float):
    abs_value = abs(value)
    deg = int(abs_value)
    minutes = (abs_value - deg) * 60
    seconds = (minutes - int(minutes)) * 60
    return (
        _rational(deg, 1000000),
        _rational(int(minutes), 1000000),
        _rational(seconds, 1000000),
    )


def build_exif_bytes(fov_deg=None, capture_dt=None, gps=None, heading_deg=None,
                     camera_model=None) -> bytes:
    """Build EXIF bytes; every block is optional.

    Args:
        fov_deg: horizontal FOV of the virtual pinhole. Writes FocalLength and
            FocalLengthIn35mmFilm (what photogrammetry tools read).
        capture_dt: naive/aware datetime of this frame. Writes
            DateTimeOriginal/Digitized (+ millisecond SubSecTimeOriginal).
        gps: (lat, lon, alt) tuple. Altitude sign goes into GPSAltitudeRef
            because GPSAltitude is an unsigned rational.
        heading_deg: absolute direction of this view (degrees from true
            north). Writes GPSImgDirection with ref 'T'.
        camera_model: EXIF Model string. Keep it identical for all views that
            share intrinsics so tools group them under one calibration.
    """
    zeroth, exif_ifd, gps_ifd = {}, {}, {}

    zeroth[piexif.ImageIFD.Software] = f"{APP_NAME} {VERSION}".encode()
    if camera_model:
        zeroth[piexif.ImageIFD.Make] = EXIF_MAKE.encode()
        zeroth[piexif.ImageIFD.Model] = str(camera_model).encode()

    if fov_deg:
        f35 = focal_35mm_from_fov(float(fov_deg))
        exif_ifd[piexif.ExifIFD.FocalLength] = _rational(f35)
        exif_ifd[piexif.ExifIFD.FocalLengthIn35mmFilm] = int(round(f35))

    if capture_dt is not None:
        stamp = capture_dt.strftime("%Y:%m:%d %H:%M:%S").encode()
        exif_ifd[piexif.ExifIFD.DateTimeOriginal] = stamp
        exif_ifd[piexif.ExifIFD.DateTimeDigitized] = stamp
        exif_ifd[piexif.ExifIFD.SubSecTimeOriginal] = f"{capture_dt.microsecond // 1000:03d}".encode()

    if gps is not None:
        lat, lon, alt = gps
        gps_ifd[piexif.GPSIFD.GPSLatitudeRef] = b'N' if lat >= 0 else b'S'
        gps_ifd[piexif.GPSIFD.GPSLatitude] = _deg_min_sec(lat)
        gps_ifd[piexif.GPSIFD.GPSLongitudeRef] = b'E' if lon >= 0 else b'W'
        gps_ifd[piexif.GPSIFD.GPSLongitude] = _deg_min_sec(lon)
        # GPSAltitude is an UNSIGNED rational; the sign lives in GPSAltitudeRef
        # (0 = above sea level, 1 = below).
        gps_ifd[piexif.GPSIFD.GPSAltitudeRef] = 0 if alt >= 0 else 1
        gps_ifd[piexif.GPSIFD.GPSAltitude] = _rational(abs(alt), 1000000)

    if heading_deg is not None:
        # Round to the stored precision BEFORE the final wrap so 359.999…
        # cannot round up to 360 (EXIF range is [0, 360)).
        direction = round(float(heading_deg) % 360.0, 2) % 360.0
        gps_ifd[piexif.GPSIFD.GPSImgDirectionRef] = b'T'  # true north (from the GPS track)
        gps_ifd[piexif.GPSIFD.GPSImgDirection] = _rational(direction, 100)

    return piexif.dump({"0th": zeroth, "Exif": exif_ifd, "GPS": gps_ifd, "1st": {}, "thumbnail": None})


def save_image_with_exif(path: str, image, params, exif_bytes: bytes) -> bool:
    """Write ``image`` once with the given EXIF embedded (no write-then-rewrite).

    - JPEG: encode with ``cv2.imencode`` (honoring ``params``, e.g. quality)
      and insert the EXIF straight into the encoded bytes.
    - PNG/TIFF: build the image with Pillow directly from the array (lossless)
      and save once with EXIF.

    Falls back to a plain write (no EXIF) if anything goes wrong, so an EXIF
    problem can never lose the image itself.
    """
    ext = os.path.splitext(path)[1].lower()
    try:
        if ext in ('.jpg', '.jpeg'):
            ok, buf = cv2.imencode(ext, image, params or [])
            if not ok:
                raise ValueError(f"cv2.imencode failed for {ext}")
            piexif.insert(exif_bytes, buf.tobytes(), path)
        else:
            rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB) if image.ndim == 3 else image
            Image.fromarray(rgb).save(path, exif=exif_bytes)
        return True
    except Exception as e:
        logger.error(f"Error writing {path} with EXIF: {type(e).__name__} - {e}")
        try:
            cv2.imwrite(path, image, params or [])
        except Exception:
            pass
        return False
