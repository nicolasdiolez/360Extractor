import cv2
import numpy as np

class ImageUtils:
    @staticmethod
    def calculate_blur_score(image: np.ndarray) -> float:
        """
        Calculate the blur score of an image using the Laplacian variance method.
        Higher variance means more edges (less blurry).
        Lower variance means fewer edges (more blurry).
        
        Args:
            image (np.ndarray): The input image (BGR or Grayscale).
            
        Returns:
            float: The variance of the Laplacian (blur score).
        """
        if image is None:
            return 0.0
            
        # Convert to grayscale if necessary
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image
            
        return cv2.Laplacian(gray, cv2.CV_64F).var()