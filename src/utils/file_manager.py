import os
import cv2
import logging

logger = logging.getLogger(__name__)


class FileManager:
    @staticmethod
    def ensure_directory(path) -> bool:
        """Ensures the directory exists. Returns True on success."""
        try:
            if not os.path.exists(path):
                os.makedirs(path)
            return True
        except OSError as e:
            logger.error(f"Failed to create directory {path}: {e}")
            return False

    @staticmethod
    def save_image(path, image, params=None) -> bool:
        """Saves an image. Returns True on success."""
        try:
            if params:
                cv2.imwrite(path, image, params)
            else:
                cv2.imwrite(path, image)
            return True
        except Exception as e:
            logger.error(f"Failed to save image {path}: {e}")
            return False
        
    @staticmethod
    def save_mask(path, mask) -> bool:
        """Saves a mask image. Returns True on success."""
        try:
            cv2.imwrite(path, mask)
            return True
        except Exception as e:
            logger.error(f"Failed to save mask {path}: {e}")
            return False