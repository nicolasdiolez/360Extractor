import cv2
from PySide6.QtCore import QObject, Signal
from core.geometry import GeometryProcessor
from utils.image_utils import ImageUtils

class BlurAnalyzer:
    @staticmethod
    def analyze_sample(video_path, settings):
        """
        Analyzes a sample frame from the video to estimate blur scores.
        
        Args:
            video_path (str): Path to the video file.
            settings (dict): Processing settings (fov, camera_count, pitch_offset, etc.)
            
        Returns:
            dict: {
                'average': float,
                'min': float,
                'max': float,
                'details': list of (view_name, score)
            }
        """
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise IOError(f"Could not open video: {video_path}")
            
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        # Pick a frame from the middle, or at least a few seconds in to avoid intro black screens
        # If video is short, just take the first frame
        if frame_count > 60:
            target_frame = frame_count // 2
        else:
            target_frame = 0
            
        cap.set(cv2.CAP_PROP_POS_FRAMES, target_frame)
        ret, frame = cap.read()
        cap.release()
        
        if not ret or frame is None:
            raise IOError("Could not read frame from video.")
            
        # Extract settings
        out_res = settings.get('resolution', 1024)
        fov = settings.get('fov', 90)
        camera_count = settings.get('camera_count', 6)
        pitch_offset = settings.get('pitch_offset', 0)
        
        # Generate views
        views = GeometryProcessor.generate_views(camera_count, pitch_offset=pitch_offset)
        
        scores = []
        details = []
        
        src_h, src_w = frame.shape[:2]
        
        for name, y, p, r in views:
            map_x, map_y = GeometryProcessor.create_rectilinear_map(
                src_h, src_w, out_res, out_res, fov, y, p, r
            )
            
            rect_img = cv2.remap(frame, map_x, map_y, cv2.INTER_LINEAR, borderMode=cv2.BORDER_WRAP)
            score = ImageUtils.calculate_blur_score(rect_img)
            scores.append(score)
            details.append((name, score))
            
        if not scores:
            return {'average': 0, 'min': 0, 'max': 0, 'details': []}
            
        return {
            'average': sum(scores) / len(scores),
            'min': min(scores),
            'max': max(scores),
            'details': details
        }

class BlurAnalysisWorker(QObject):
    finished = Signal(dict)
    error = Signal(str)

    def __init__(self, video_path, settings):
        super().__init__()
        self.video_path = video_path
        self.settings = settings

    def run(self):
        try:
            result = BlurAnalyzer.analyze_sample(self.video_path, self.settings)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))