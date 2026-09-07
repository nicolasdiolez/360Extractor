"""Checked, atomic file writes. Failed writes always raise."""
import json
import os
import tempfile
from pathlib import Path

import cv2


class FileManager:
    @staticmethod
    def ensure_directory(path) -> bool:
        Path(path).mkdir(parents=True, exist_ok=True)
        return True

    @staticmethod
    def save_image(path, image, params=None) -> bool:
        if not cv2.imwrite(str(path), image, params or []):
            raise OSError(f"Image encoder could not write {path}")
        return True

    @staticmethod
    def save_mask(path, mask) -> bool:
        return FileManager.save_image(path, mask)

    @staticmethod
    def write_pair(image_path, image, params, exif_bytes, mask_path, mask):
        from extractor360.core.exif_writer import save_image_with_exif
        temporary = []
        published = []
        pairs = [(image_path, image, False)]
        if mask is not None:
            pairs.append((mask_path, mask, True))
        try:
            for destination, pixels, is_mask in pairs:
                if os.path.lexists(destination):
                    raise FileExistsError(f"Refusing to overwrite {destination}")
                fd, name = tempfile.mkstemp(prefix=".writing-", suffix=Path(destination).suffix, dir=Path(destination).parent)
                os.close(fd)
                temporary.append((name, destination))
                if is_mask:
                    ok = FileManager.save_mask(name, pixels)
                elif exif_bytes is not None:
                    ok = save_image_with_exif(name, pixels, params, exif_bytes)
                else:
                    ok = FileManager.save_image(name, pixels, params)
                if not ok:
                    raise OSError(f"Writer failed for {destination}")
            # Both files are complete before either becomes visible.
            for name, destination in temporary:
                os.replace(name, destination)
                published.append(destination)
            return True
        except BaseException:
            for destination in published:
                Path(destination).unlink(missing_ok=True)
            raise
        finally:
            for name, _ in temporary:
                Path(name).unlink(missing_ok=True)

    @staticmethod
    def save_json(path, data):
        path = Path(path)
        fd, name = tempfile.mkstemp(prefix=".writing-", suffix=".json", dir=path.parent)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as stream:
                json.dump(data, stream, indent=2, allow_nan=False)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(name, path)
        finally:
            Path(name).unlink(missing_ok=True)
