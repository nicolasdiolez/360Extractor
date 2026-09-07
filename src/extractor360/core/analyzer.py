import cv2
from extractor360.core.geometry import GeometryProcessor
from extractor360.utils.image_utils import ImageUtils

class BlurAnalyzer:
    @staticmethod
    def analyze_sample(video_path, settings, cancelled=lambda: False):
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
            cap.release()
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

        # Extract settings. Default resolution matches the export default (2048)
        # so the recommended threshold reflects what will actually be written —
        # the Laplacian blur score scales with resolution.
        out_res = settings.get('resolution', 2048)
        fov = settings.get('fov', 90)
        camera_count = settings.get('camera_count', 6)
        pitch_offset = settings.get('pitch_offset', 0)
        layout_mode = settings.get('layout_mode', 'ring')
        if layout_mode == 'adaptive':  # legacy alias
            layout_mode = 'ring'
        is_360 = settings.get('is_360', True)

        scores = []
        details = []

        src_h, src_w = frame.shape[:2]

        if not is_360:
            # Flat / non-360 media is exported as-is: score the frame directly
            # instead of remapping a non-equirectangular image (which would give
            # a meaningless threshold).
            score = ImageUtils.calculate_blur_score(frame)
            scores.append(score)
            details.append(("flat", score))
        else:
            # Use the same layout as the export so the recommended threshold
            # matches the views that will actually be produced (Cube/Fibonacci
            # frame very differently from Ring).
            views = GeometryProcessor.generate_views(
                camera_count, pitch_offset=pitch_offset, layout_mode=layout_mode
            )
            active = settings.get('active_cameras')
            for index, (name, y, p, r) in enumerate(views):
                if cancelled():
                    raise InterruptedError("Analysis cancelled")
                if active is not None and index not in active:
                    continue
                map_x, map_y = GeometryProcessor.create_rectilinear_map(
                    src_h, src_w, out_res, out_res, fov, y, p, r
                )

                rect_img = cv2.remap(frame, map_x, map_y, cv2.INTER_LANCZOS4 if settings.get("interpolation_mode") == "lanczos" else cv2.INTER_LINEAR, borderMode=cv2.BORDER_WRAP)
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

# The Qt worker wrapper (BlurAnalysisWorker) lives in extractor360.ui.workers:
# the analysis itself is pure and must stay importable without Qt.