import cv2
import numpy as np
import os
import time
from collections import deque
from PySide6.QtCore import QObject, Signal

from core.geometry import GeometryProcessor
from core.ai_model import AIService
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
             # Note: Using 'yolov8n-seg.pt' (nano) for performance.
             self.ai_service = AIService('yolov8n-seg.pt')

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
        out_res = job.settings.get('resolution', 1024)
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
                        save_name = f"{name_no_ext}_frame{frame_idx:06d}_{name}{ext}"
                        FileManager.save_image(os.path.join(output_dir, save_name), final_img, save_params)
                        
                        if mask_or_skip is not None and isinstance(mask_or_skip, np.ndarray):
                            # RealityScan naming convention: [Filename].[ext].mask.png
                            # Masks are typically kept as PNG for transparency support
                            mask_name = f"{save_name}.mask.png"
                            FileManager.save_mask(os.path.join(output_dir, mask_name), mask_or_skip)
            
            frame_idx += 1
            
        cap.release()

        if skipped_blur_count > 0:
            logger.info(f"Total blurry views skipped for {filename}: {skipped_blur_count}")