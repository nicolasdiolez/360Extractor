import cv2
import numpy as np
import os
import time
from collections import deque
from PySide6.QtCore import QObject, Signal

from core.geometry import GeometryProcessor
from core.ai_model import AIService
from core.motion_detector import MotionDetector
from core.telemetry import TelemetryHandler
from utils.file_manager import FileManager
from utils.image_utils import ImageUtils
from utils.logger import logger

class ProcessingWorker(QObject):
    """
    Worker class to handle video processing in a separate thread.
    """
    progress_updated = Signal(int, str) # value (0-100), message
    job_started = Signal(int)
    job_finished = Signal(int)
    finished = Signal()
    error_occurred = Signal(str)

    def __init__(self, jobs):
        super().__init__()
        self.jobs = jobs
        self.is_running = True
        
        # Initialize AI Service if needed
        self.ai_service = None
        needs_ai = any(job.settings.get('ai_mode', 'None') != 'None' for job in self.jobs)
        
        if needs_ai:
             # Initialize YOLO model
             # Note: Using 'yolo26n-seg.pt' (nano) for maximum performance (NMS-free).
             self.ai_service = AIService('yolo26n-seg.pt')

        self.motion_detector = MotionDetector()

    def stop(self):
        self.is_running = False

    def run(self):
        total_jobs = len(self.jobs)
        
        for i, job in enumerate(self.jobs):
            if not self.is_running:
                break
            
            self.job_started.emit(i)
            try:
                self.process_video(job, i, total_jobs)
                self.job_finished.emit(i)
            except Exception as e:
                import traceback
                traceback.print_exc()
                self.error_occurred.emit(f"Error processing {os.path.basename(job.file_path)}: {str(e)}")
        
        self.finished.emit()

    def generate_filename(self, pattern, context):
        """
        Generates a filename based on the provided pattern and context variables.
        Context: {filename}, {frame}, {camera}, {ext}, {image_name}
        """
        result = pattern
        for key, value in context.items():
            result = result.replace(f"{{{key}}}", str(value))
        return result

    def process_video(self, job, job_index, total_jobs):
        file_path = job.file_path
        filename = os.path.basename(file_path)
        name_no_ext = os.path.splitext(filename)[0]

        # Determine Output Directory
        custom_dir = job.output_dir
        # If custom_dir is provided, use it as base. Otherwise use file's directory.
        if custom_dir and os.path.isdir(custom_dir):
            base_output_dir = custom_dir
        else:
            base_output_dir = os.path.dirname(file_path)

        # Create a specific subfolder for this video to keep things organized
        output_dir = os.path.join(base_output_dir, f"{name_no_ext}_processed")
        
        try:
            FileManager.ensure_directory(output_dir)
        except OSError as e:
            # If we can't create the directory (e.g. permission error), raise it
            raise IOError(f"Cannot create or access output directory {output_dir}: {e}")

        # Determine Output Format & Params
        fmt = job.output_format.lower()
        if fmt not in ['jpg', 'png', 'tiff']:
            fmt = 'jpg'
        
        ext = f".{fmt}"
        if fmt == 'tiff':
            ext = '.tif'
        
        save_params = []
        if fmt == 'jpg':
            quality = job.settings.get('quality', 95)
            save_params = [cv2.IMWRITE_JPEG_QUALITY, quality]
        elif fmt == 'png':
            save_params = [cv2.IMWRITE_PNG_COMPRESSION, 3]
        elif fmt == 'tiff':
            save_params = [cv2.IMWRITE_TIFF_COMPRESSION, 1] # 1 = NONE

        cap = cv2.VideoCapture(file_path)
        if not cap.isOpened():
            raise IOError(f"Could not open video: {file_path}")

        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames_video = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if total_frames_video <= 0: total_frames_video = 1 # Prevent division by zero
        
        # Calculate extraction interval
        interval_value = float(job.settings.get('interval_value', 1.0))
        interval_unit = job.settings.get('interval_unit', 'Seconds')
        
        if interval_unit == 'Frames':
            interval = int(max(1, interval_value))
        else: # Seconds
            interval = int(max(1, fps * interval_value))
        
        # Geometry Settings
        out_res = job.resolution
        fov = job.settings.get('fov', 90)
        camera_count = job.settings.get('camera_count', 6)
        pitch_offset = job.settings.get('pitch_offset', 0)
        layout_mode = job.settings.get('layout_mode', 'adaptive')
        
        # AI Mode per job
        ai_mode_ui = job.settings.get('ai_mode', 'None')
        ai_mode_internal = 'none'
        if ai_mode_ui == 'Skip Frame':
            ai_mode_internal = 'skip_frame'
        elif ai_mode_ui == 'Generate Mask':
            ai_mode_internal = 'generate_mask'

        # Blur Filter Settings
        blur_enabled = job.settings.get('blur_filter_enabled', False)
        smart_blur_enabled = job.settings.get('smart_blur_enabled', False)
        blur_threshold = job.settings.get('blur_threshold', 100.0)
        skipped_blur_count = 0
        
        # Adaptive Blur State
        blur_history = deque(maxlen=10)
        consecutive_blur_skips = 0

        # Sharpening Settings
        sharpen_enabled = job.settings.get('sharpening_enabled', False)
        sharpen_strength = job.settings.get('sharpening_strength', 0.5)

        # Adaptive Settings
        adaptive_mode = job.adaptive_mode
        adaptive_threshold = job.adaptive_threshold
        last_extracted_frame = None
        
        # Telemetry Setup
        telemetry_handler = None
        current_gps = None
        if job.export_telemetry:
            telemetry_handler = TelemetryHandler()
            logger.info(f"Extracting telemetry for {filename}...")
            telemetry_handler.extract_metadata(file_path)

        # Generate views based on camera count
        views = GeometryProcessor.generate_views(camera_count, pitch_offset=pitch_offset, layout_mode=layout_mode)
        
        maps = {}
        src_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        src_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        self.progress_updated.emit(0, f"Generating maps for {filename}...")
        
        active_cams = job.active_cameras

        for i, (name, y, p, r) in enumerate(views):
            if active_cams is not None and i not in active_cams:
                continue

            maps[name] = GeometryProcessor.create_rectilinear_map(
                src_h, src_w, out_res, out_res, fov, y, p, r
            )

        frame_idx = 0
        job_start_time = time.time()
        
        while self.is_running:
            ret, frame = cap.read()
            if not ret:
                break
            
            if frame_idx % interval == 0:
                # Update GPS for current time
                if telemetry_handler:
                    current_time = frame_idx / fps if fps > 0 else 0
                    current_gps = telemetry_handler.get_gps_at_time(current_time)

                # Progress calculation (per job 0-100%)
                current_job_progress = int((frame_idx / total_frames_video) * 100)
                
                # ETA Calculation
                elapsed = time.time() - job_start_time
                if frame_idx > 0 and elapsed > 0:
                    rate = frame_idx / elapsed # frames per second
                    remaining_frames = total_frames_video - frame_idx
                    eta_seconds = remaining_frames / rate
                    eta_min = int(eta_seconds // 60)
                    eta_sec = int(eta_seconds % 60)
                    eta_str = f"ETA: {eta_min}m {eta_sec}s"
                else:
                    eta_str = "ETA: --m --s"

                self.progress_updated.emit(
                    current_job_progress,
                    f"Processing {filename} - Frame {frame_idx}/{total_frames_video} - {eta_str}"
                )

                # Adaptive Check
                if adaptive_mode:
                    if last_extracted_frame is not None:
                        motion_score = self.motion_detector.calculate_motion_score(last_extracted_frame, frame)
                        if motion_score <= adaptive_threshold:
                            # Skip extraction
                            frame_idx += 1
                            continue
                    
                    last_extracted_frame = frame.copy()

                for name, _, _, _ in views:
                    if name not in maps:
                        continue

                    map_x, map_y = maps[name]
                    # 1. Reproject
                    rect_img = cv2.remap(frame, map_x, map_y, cv2.INTER_LINEAR, borderMode=cv2.BORDER_WRAP)
                    
                    # 2. Blur Detection
                    if blur_enabled:
                        score = ImageUtils.calculate_blur_score(rect_img)
                        is_blurry = False
                        
                        if smart_blur_enabled:
                            # 1. Check Minimum Floor (Safety net against black/garbage frames)
                            if score < blur_threshold:
                                is_blurry = True
                            
                            # 2. Adaptive Check
                            elif len(blur_history) > 0:
                                avg_score = sum(blur_history) / len(blur_history)
                                if score < avg_score * 0.6:
                                    is_blurry = True
                                    
                            # 3. Safety Override (Force accept if too many consecutive skips)
                            if is_blurry:
                                consecutive_blur_skips += 1
                                if consecutive_blur_skips > 5:
                                    logger.warning(f"Force accepting frame due to consecutive skips: {filename} - Frame {frame_idx}")
                                    is_blurry = False
                                    consecutive_blur_skips = 0
                            
                            # 4. Update History (if accepted, either naturally or forced)
                            if not is_blurry:
                                consecutive_blur_skips = 0
                                blur_history.append(score)
                        else:
                            # Standard Mode
                            if score < blur_threshold:
                                is_blurry = True

                        if is_blurry:
                            logger.info(f"Skipped blurry view: {filename} - Frame {frame_idx} - {name} (Score: {score:.1f})")
                            skipped_blur_count += 1
                            continue

                    # 3. Sharpening (Post-Reprojection Recovery)
                    if sharpen_enabled:
                        gaussian = cv2.GaussianBlur(rect_img, (0, 0), 2.0)
                        rect_img = cv2.addWeighted(rect_img, 1.0 + sharpen_strength, gaussian, -sharpen_strength, 0)

                    # 4. AI Processing
                    final_img = rect_img
                    mask_or_skip = None
                    
                    if self.ai_service and ai_mode_internal != 'none':
                        final_img, result_extra = self.ai_service.process_image(rect_img, mode=ai_mode_internal)
                        
                        if ai_mode_internal == 'skip_frame' and result_extra is True:
                            # Person detected, skip this view
                            continue
                        elif ai_mode_internal == 'generate_mask':
                            mask_or_skip = result_extra
                    
                    
                    # 5. Save
                    if final_img is not None:
                        # Naming Logic
                        naming_mode = job.settings.get('naming_mode', 'realityscan')
                        
                        # Context variables for naming
                        ctx = {
                            'filename': name_no_ext,
                            'frame': f"{frame_idx:06d}",
                            'camera': name,
                            'ext': ext
                        }
                        
                        save_name = ""
                        mask_name = ""

                        if naming_mode == 'realityscan':
                             # Standard RealityScan: [orig_name]_frame[X]_[cam].jpg
                             save_name = f"{name_no_ext}_frame{frame_idx:06d}_{name}{ext}"
                             # Mask: [image_name].mask.png
                             mask_name = f"{save_name}.mask.png"
                             
                        elif naming_mode == 'simple':
                            # Simple Suffix: [orig_name]_frame[X]_[cam].jpg
                            save_name = f"{name_no_ext}_frame{frame_idx:06d}_{name}{ext}"
                            # Mask: [orig_name]_frame[X]_[cam]_mask.png
                            mask_name = f"{name_no_ext}_frame{frame_idx:06d}_{name}_mask.png"
                            
                        elif naming_mode == 'custom':
                            img_pattern = job.settings.get('image_pattern', '{filename}_frame{frame}_{camera}')
                            mask_pattern = job.settings.get('mask_pattern', '{filename}_frame{frame}_{camera}_mask')
                            
                            # Generate Image Name
                            # Note: pattern likely doesn't include extension, so we add it if missing or just append
                            # Ideally, pattern is the "stem". We enforce {ext} if user put it, or append standard ext
                            if '{ext}' in img_pattern:
                                save_name = self.generate_filename(img_pattern, ctx)
                            else:
                                save_name = self.generate_filename(img_pattern, ctx) + ext
                                
                            # Update context with the generated image name (excluding ext mostly, but let's see usage)
                            # Ideally {image_name} is the full filename of the image
                            ctx['image_name'] = save_name
                            
                            if '{ext}' in mask_pattern:
                                mask_name = self.generate_filename(mask_pattern, ctx)
                            else:
                                mask_name = self.generate_filename(mask_pattern, ctx) + ".png" # Masks always png

                        full_save_path = os.path.join(output_dir, save_name)
                        FileManager.save_image(full_save_path, final_img, save_params)
                        
                        if current_gps:
                            telemetry_handler.embed_exif(full_save_path, *current_gps)

                        if mask_or_skip is not None and isinstance(mask_or_skip, np.ndarray):
                            FileManager.save_mask(os.path.join(output_dir, mask_name), mask_or_skip)
            
            frame_idx += 1
            
        cap.release()

        if skipped_blur_count > 0:
            logger.info(f"Total blurry views skipped for {filename}: {skipped_blur_count}")