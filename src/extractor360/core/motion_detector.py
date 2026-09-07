import cv2
import numpy as np
from extractor360.utils.logger import logger

class MotionDetector:
    def __init__(self, target_size=(256, 144)):
        self.target_size = target_size

    def calculate_motion_score(self, frame1, frame2) -> float:
        """
        Calculates a motion score between two frames using Optical Flow.
        Returns the mean magnitude of the flow.
        """
        if frame1 is None or frame2 is None:
            raise ValueError("Motion comparison requires two images")

        # Resize and convert to grayscale for performance
        try:
            width = self.target_size[0]
            size = (width, max(1, round(width * frame1.shape[0] / frame1.shape[1])))
            gray1 = cv2.cvtColor(cv2.resize(frame1, size), cv2.COLOR_BGR2GRAY)
            gray2 = cv2.cvtColor(cv2.resize(frame2, size), cv2.COLOR_BGR2GRAY)

            # Calculate Optical Flow (Farneback)
            flow = cv2.calcOpticalFlowFarneback(
                prev=gray1,
                next=gray2,
                flow=None,
                pyr_scale=0.5,
                levels=3,
                winsize=15,
                iterations=3,
                poly_n=5,
                poly_sigma=1.2,
                flags=0
            )

            # Calculate magnitude of flow vectors
            magnitude, _ = cv2.cartToPolar(flow[..., 0], flow[..., 1])
            
            # Return mean magnitude
            return float(np.mean(magnitude))
            
        except Exception as e:
            logger.error(f"Error calculating motion score: {e}")
            raise RuntimeError("Could not compare motion") from e
