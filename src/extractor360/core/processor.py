import cv2
import numpy as np
import os
import time
import json
import uuid
import concurrent.futures
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone

from extractor360.core import colmap_export, exif_writer
from extractor360.core.events import Event
from extractor360.core.validation import validate_settings
from extractor360.core.output_plan import create_output_directory, output_names, preflight_names
from extractor360.core.geometry import GeometryProcessor
from extractor360.core.motion_detector import MotionDetector
from extractor360.core.telemetry import TelemetryHandler
from extractor360.core.ai_classes import (
    PRESETS, parse_custom_classes, resolve_ai_model_name, DEFAULT_AI_MODEL,
)
from extractor360.core.settings_manager import normalize_mask_faces
from extractor360.core.version import APP_NAME, VERSION
from extractor360.utils.file_manager import FileManager
from extractor360.utils.image_utils import ImageUtils
from extractor360.utils.logger import logger

class ProcessingWorker:
    """
    Qt-free worker that processes a list of jobs.

    Progress is reported through plain callback events (see
    ``extractor360.core.events``): the CLI connects functions directly, the GUI
    bridges them to Qt signals via ``extractor360.ui.workers.ProcessingBridge``.
    Run it on whatever thread suits the caller (the GUI uses a plain
    ``threading.Thread``; the CLI calls ``run()`` synchronously).
    """

    def __init__(self, jobs):
        self.progress_updated = Event()  # (value 0-100, message)
        self.job_started = Event()       # (job index)
        self.job_finished = Event()      # (job index)
        self.job_cancelled = Event()
        self.job_error = Event()         # (job index, error message)
        self.finished = Event()          # ()
        self.error_occurred = Event()    # (error message)

        self.jobs = jobs
        self.is_running = True
        self.error_count = 0

        # The AI model is loaded lazily from run() (i.e. on the worker thread),
        # not here on the GUI thread: loading YOLO — and, on first launch,
        # downloading it — would otherwise freeze the UI right after the user
        # clicks "Start Processing". self._ai_model_name caches which model is
        # currently loaded so we only reload when a job needs a different one.
        self.ai_service = None
        self._ai_model_name = None

        self.motion_detector = MotionDetector()
        self.io_pool = concurrent.futures.ThreadPoolExecutor(max_workers=4)

    def _ensure_ai_service(self, model_name):
        """Load (or reuse) the YOLO model on the worker thread.

        Emits a progress message first so the UI shows "Loading AI model…"
        instead of appearing frozen while the model loads/downloads.
        """
        if self.ai_service is not None and self._ai_model_name == model_name:
            return self.ai_service
        self.progress_updated.emit(0, f"Loading AI model ({model_name})…")
        # Heavy import (torch/ultralytics) done lazily so the core stays
        # importable — and AI-less jobs runnable — without the AI stack.
        from extractor360.core.ai_model import AIService
        self.ai_service = AIService(model_name)
        self._ai_model_name = model_name
        return self.ai_service

    def stop(self):
        self.is_running = False


    @staticmethod
    def _build_nadir_mask(shape, radius_pct, invert_mask):
        """Build a circular nadir mask for the Down view.

        A filled disc at the image centre marks the pole/tripod area as "ignore".
        The convention matches the AI mask: with ``invert_mask`` (default), the
        keep area is white (255) and the disc is black (0); otherwise it is
        flipped so the two masks can be combined consistently.
        """
        h, w = shape[:2]
        keep_val, ignore_val = (255, 0) if invert_mask else (0, 255)
        mask = np.full((h, w), keep_val, dtype=np.uint8)
        radius = int(max(0.0, min(100.0, radius_pct)) / 100.0 * (min(h, w) / 2.0))
        if radius > 0:
            cv2.circle(mask, (w // 2, h // 2), radius, ignore_val, thickness=-1)
        return mask

    def run(self):
        total_jobs = len(self.jobs)
        self.error_count = 0
        try:
            for i, job in enumerate(self.jobs):
                if not self.is_running:
                    job.status = "Cancelled"
                    job.result = {"status": "cancelled", "images_written": 0}
                    self.job_cancelled.emit(i)
                    continue
                self.job_started.emit(i)
                try:
                    self.process_video(job, i, total_jobs)
                    if not self.is_running:
                        job.status = "Cancelled"
                        self.job_cancelled.emit(i)
                    else:
                        job.status = "Done"
                        self.progress_updated.emit(100, f"Finished {job.filename}")
                        self.job_finished.emit(i)
                except Exception as exc:
                    if not self.is_running:
                        job.status = "Cancelled"
                        job.result["status"] = "cancelled"
                        self.job_cancelled.emit(i)
                        continue
                    logger.error(f"Error processing {job.filename}: {exc}", exc_info=True)
                    self.error_count += 1
                    job.status = "Error"
                    self.job_error.emit(i, str(exc))
                    self.error_occurred.emit(f"Error processing {job.filename}: {exc}")
        finally:
            self.io_pool.shutdown(wait=True)
            self.finished.emit()

    def process_video(self, job, job_index, total_jobs):
        job.result = {"run_id": uuid.uuid4().hex, "status": "running", "extraction": {"images_written": 0}}
        started = time.monotonic()
        try:
            job.settings = validate_settings(job.settings)
            stat = os.stat(job.file_path)
            job.result["source_identity"] = {"size_bytes": stat.st_size, "mtime_ns": stat.st_mtime_ns, "hash_verified": False}
            self._process_video(job, job_index, total_jobs)
            job.result['status'] = 'completed' if self.is_running else 'cancelled'
        except BaseException as exc:
            if isinstance(exc, KeyboardInterrupt):
                self.stop()
            job.result.update(status='cancelled' if isinstance(exc, KeyboardInterrupt) or not self.is_running else 'failed', error=str(exc))
            raise
        finally:
            job.result['elapsed_seconds'] = round(time.monotonic() - started, 3)
            output_dir = job.result.get('output_dir')
            if output_dir:
                self._write_manifest(output_dir, job, job.result)

    def generate_filename(self, pattern, context):
        """
        Generates a filename based on the provided pattern and context variables.
        Context: {filename}, {frame}, {camera}, {ext}, {image_name}
        """
        result = pattern
        for key, value in context.items():
            result = result.replace(f"{{{key}}}", str(value))
        return result

    def _process_video(self, job, job_index, total_jobs):
        file_path = job.file_path
        filename = os.path.basename(file_path)
        name_no_ext = os.path.splitext(filename)[0]

        output_dir = create_output_directory(file_path, job.output_dir)
        job.result['output_dir'] = output_dir
        self._write_manifest(output_dir, job, job.result)

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

        is_image = file_path.lower().endswith(('.jpg', '.jpeg', '.png', '.tiff', '.tif'))

        cap = None
        current_image_frame = None
        skipped_blur_count = 0

        # Wrap the whole processing in try/finally so the video capture handle
        # is always released, even if an exception is raised mid-processing.
        try:
            if is_image:
                current_image_frame = cv2.imread(file_path)
                if current_image_frame is None:
                    raise IOError(f"Could not open image: {file_path}")
                fps = 0
                total_frames_video = 1
                interval = 1
            else:
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
                    # Round instead of truncating: at 29.97 fps a 1s interval
                    # means 30 frames, not 29 (which would drift over time).
                    interval = max(1, round(fps * interval_value))

            # Geometry Settings
            out_res = job.resolution
            fov = job.settings.get('fov', 90)
            camera_count = job.settings.get('camera_count', 6)
            pitch_offset = job.settings.get('pitch_offset', 0)
            layout_mode = job.settings.get('layout_mode', 'ring')
            if layout_mode == 'adaptive':  # legacy alias
                layout_mode = 'ring'

            # Non-360 (flat) media is processed as-is, without equirectangular
            # reprojection. All other steps (blur filter, AI masking, sharpening,
            # telemetry) still apply.
            is_360 = job.settings.get('is_360', True)

            # AI Mode per job
            ai_mode_ui = job.settings.get('ai_mode', 'None')
            ai_mode_internal = 'none'
            if ai_mode_ui == 'Skip Frame':
                ai_mode_internal = 'skip_frame'
            elif ai_mode_ui == 'Generate Mask':
                ai_mode_internal = 'generate_mask'

            # Segmentation model (nano by default). Loaded lazily below only if a
            # job actually needs AI, on the worker thread.
            ai_model_name = resolve_ai_model_name(job.settings.get('ai_model', DEFAULT_AI_MODEL))

            ai_confidence = job.settings.get('ai_confidence', 0.25)
            ai_invert_mask = job.settings.get('ai_invert_mask', True)
            ai_feather_mask = job.settings.get('feather_mask', False)

            # Per-face masking scope: restrict AI masking to a subset of views
            # (e.g. only the face that contains the operator), leaving the other
            # faces untouched. Useful when YOLO would otherwise mask people in
            # paintings/posters on the other faces. None/empty => all faces.
            mask_face_filter = normalize_mask_faces(job.settings.get('ai_mask_cameras', None))
            if mask_face_filter and not is_360:
                # Flat media has a single view named "flat" that face names like
                # "Down" can never match, which would silently disable masking.
                logger.warning(
                    "Per-face masking scope is ignored for flat (non-360) media; "
                    "AI masking applies to the whole frame."
                )
                mask_face_filter = None
            elif mask_face_filter:
                logger.info(f"AI masking restricted to faces: {sorted(mask_face_filter)}")

            # Interpolation Settings
            interp_mode = job.settings.get('interpolation_mode', 'linear')
            interp_flag = cv2.INTER_LANCZOS4 if interp_mode == 'lanczos' else cv2.INTER_LINEAR

            target_classes = []
            if job.settings.get('ai_detect_humans', True):
                target_classes.extend(PRESETS["Humans"])
            if job.settings.get('ai_detect_vehicles', False):
                target_classes.extend(PRESETS["Vehicles"])
            if job.settings.get('ai_detect_plants', False):
                target_classes.extend(PRESETS["Plants"])

            custom_classes_str = job.settings.get('ai_custom_classes', '')
            if custom_classes_str:
                target_classes.extend(parse_custom_classes(custom_classes_str))

            target_classes = list(set(target_classes))
            if not target_classes:
                target_classes = [0] # fallback to human

            # Blur Filter Settings
            blur_enabled = job.settings.get('blur_filter_enabled', False)
            smart_blur_enabled = job.settings.get('smart_blur_enabled', False)
            blur_threshold = job.settings.get('blur_threshold', 100.0)

            # Adaptive Blur State
            blur_history = defaultdict(lambda: deque(maxlen=10))

            # Nadir mask (no AI): a disc on the Down view covering the pole/tripod
            # at the bottom of the capture. Combines with the AI mask when both
            # are on. Only meaningful for a cube layout that has a "Down" face
            # (the "no Down face" warning is emitted once views are known below).
            nadir_mask_enabled = job.settings.get('nadir_mask_enabled', False)
            nadir_mask_radius = float(job.settings.get('nadir_mask_radius', 40.0))

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
            current_heading = None
            if job.export_telemetry:
                telemetry_handler = TelemetryHandler(altitude_mode=job.altitude_mode, cancelled=lambda: not self.is_running)
                logger.info(f"Extracting telemetry for {filename}...")
                telemetry_handler.extract_metadata(file_path)
                job.result["telemetry"] = telemetry_handler.metadata
                if not telemetry_handler.has_gps:
                    logger.warning("No valid GPS samples were extracted; output will not be geotagged")

            # EXIF enrichment (I1): the virtual cameras have exactly known
            # intrinsics, so write them (focal from FOV + a stable Make/Model
            # per rig) plus per-frame capture time on every image —
            # photogrammetry tools group and bootstrap calibration from these.
            exif_enabled = job.settings.get('exif_intrinsics', True)
            camera_model_label = f"Virtual Pinhole {fov}deg" if is_360 else None

            # Filesystem modification time is not a capture timestamp.
            capture_start = None
            if telemetry_handler:
                creation = telemetry_handler.metadata.get('format_tags', {}).get('creation_time')
                if creation:
                    try:
                        capture_start = datetime.fromisoformat(creation.replace('Z', '+00:00'))
                    except ValueError:
                        pass
            job.result['capture_time_source'] = 'container_creation_time' if capture_start else 'unknown'

            # Generate views and reprojection maps (only for 360 input).
            maps = {}
            if is_360:
                views = GeometryProcessor.generate_views(camera_count, pitch_offset=pitch_offset, layout_mode=layout_mode)

                if is_image:
                    src_h, src_w = current_image_frame.shape[:2]
                else:
                    src_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                    src_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

                self.progress_updated.emit(0, f"Generating maps for {filename}...")

                active_cams = job.active_cameras

                selected_views = [v for i, v in enumerate(views) if active_cams is None or i in active_cams]
                preflight_names(job.settings, name_no_ext, selected_views, is_image)
                for i, (name, y, p, r) in enumerate(views):
                    if not self.is_running:
                        return
                    if active_cams is not None and i not in active_cams:
                        continue

                    map_x, map_y = GeometryProcessor.create_rectilinear_map(
                        src_h, src_w, out_res, out_res, fov, y, p, r, cancelled=lambda: not self.is_running
                    )
                    # Convert to fixed-point (CV_16SC2): cv2.remap is markedly
                    # faster on these than on two float32 maps, with no visible
                    # quality change (verified bit-identical for linear/lanczos).
                    maps[name] = cv2.convertMaps(map_x, map_y, cv2.CV_16SC2)
            else:
                # Flat / non-360 media: a single passthrough "view".
                views = [("flat", 0.0, 0.0, 0.0)]
                preflight_names(job.settings, name_no_ext, views, is_image)
                self.progress_updated.emit(0, f"Processing {filename} (flat / non-360)...")

            active_view_names = set(maps.keys()) if is_360 else {"flat"}
            # Yaw of each view, used to turn the GPS heading (direction of
            # travel) into an absolute per-view direction (GPSImgDirection).
            view_yaws = {name: yaw for name, yaw, _p, _r in views}

            # Nadir mask only makes sense on a downward-looking "Down" face.
            if nadir_mask_enabled and not any(n.lower() == 'down' for n in active_view_names):
                logger.warning(
                    "Nadir mask is enabled but no 'Down' face is active "
                    "(needs the Cube layout with the Down camera); it will have no effect."
                )

            # Load the segmentation model now (on the worker thread) so the GUI
            # doesn't freeze, and only when this job actually needs it.
            if ai_mode_internal != 'none':
                self._ensure_ai_service(ai_model_name)

            # Manifest counters (see the manifest.json written at the end).
            frames_processed = 0       # frames hit at the extraction interval
            frames_skipped_motion = 0  # skipped by the adaptive/motion filter
            images_written = 0         # image files actually saved
            written_view_names = set()
            next_extract_time = 0.0
            views_skipped_ai = 0       # views dropped by AI "Skip Frame"

            frame_idx = 0
            job_start_time = time.time()

            while self.is_running:
                if is_image:
                    if frame_idx > 0:
                        break
                    frame = current_image_frame
                else:
                    if not cap.grab():
                        break
                    sample_time = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000
                    if frame_idx and sample_time <= 0:
                        sample_time = frame_idx / fps if fps > 0 else 0.0
                    due = frame_idx % interval == 0 if interval_unit == 'Frames' else sample_time + 1e-8 >= next_extract_time
                    if not due:
                        frame_idx += 1
                        continue
                    ret, frame = cap.retrieve()
                    if not ret or frame is None:
                        raise IOError(f'Could not decode selected frame {frame_idx}')
                    if interval_unit == 'Seconds':
                        next_extract_time = (int(sample_time / interval_value) + 1) * interval_value

                # Reached only on extraction points (or the single image frame).
                if is_image or interval_unit == 'Seconds' or frame_idx % interval == 0:
                    frame_time = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000 if cap is not None else 0.0
                    if frame_idx and frame_time <= 0:
                        frame_time = frame_idx / fps if fps > 0 else 0.0
                        job.result["frame_time_source"] = "fps_estimate"
                    else:
                        job.result["frame_time_source"] = "decoder_timestamp"

                    # Update GPS fix and travel heading for the current time
                    if telemetry_handler:
                        current_gps = telemetry_handler.get_gps_at_time(frame_time)
                        if current_gps and (job.altitude_mode == "relative" or job.settings.get("gps_altitude_reference") != "orthometric"):
                            current_gps = (current_gps[0], current_gps[1], None)
                        # Direction of travel does not establish optical orientation.
                        current_heading = None

                    frame_dt = None
                    if capture_start is not None:
                        frame_dt = capture_start + timedelta(seconds=frame_time)

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
                                frames_skipped_motion += 1
                                frame_idx += 1
                                continue



                    frames_processed += 1

                    batch_images = []
                    batch_contexts = []
                    batch_names = []

                    for name, _, _, _ in views:
                        if is_360:
                            if name not in maps:
                                continue

                            map_x, map_y = maps[name]
                            # 1. Reproject
                            rect_img = cv2.remap(frame, map_x, map_y, interp_flag, borderMode=cv2.BORDER_WRAP)
                        else:
                            # Flat passthrough at native resolution. Copy so the
                            # async I/O save is not affected by the next cap.read().
                            rect_img = frame.copy()

                        # 2. Blur Detection
                        if blur_enabled:
                            score = ImageUtils.calculate_blur_score(rect_img)
                            is_blurry = False

                            if smart_blur_enabled:
                                history = blur_history[name]
                                is_blurry = score < blur_threshold or (bool(history) and score < sum(history) / len(history) * 0.6)
                                if not is_blurry:
                                    history.append(score)
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

                        batch_images.append(rect_img)
                        batch_names.append(name)
                        batch_contexts.append({
                            'filename': name_no_ext,
                            'frame': f"{frame_idx:06d}",
                            'camera': name,
                            'ext': ext
                        })

                    # 4. AI Processing
                    ai_results = []
                    if batch_images:
                        if self.ai_service and ai_mode_internal != 'none':
                            if mask_face_filter is None:
                                ai_results = self.ai_service.process_batch(
                                    batch_images, mode=ai_mode_internal, conf=ai_confidence,
                                    classes=target_classes, invert_mask=ai_invert_mask,
                                    feather_mask=ai_feather_mask
                                )
                            else:
                                # Only run inference on the selected faces; the
                                # rest pass through untouched (no mask, never skipped).
                                eligible_idx = [
                                    i for i, n in enumerate(batch_names)
                                    if n.lower() in mask_face_filter
                                ]
                                ai_results = [(img, None) for img in batch_images]
                                if eligible_idx:
                                    sub_results = self.ai_service.process_batch(
                                        [batch_images[i] for i in eligible_idx],
                                        mode=ai_mode_internal, conf=ai_confidence,
                                        classes=target_classes, invert_mask=ai_invert_mask,
                                        feather_mask=ai_feather_mask
                                    )
                                    for slot, res in zip(eligible_idx, sub_results):
                                        ai_results[slot] = res
                        else:
                            ai_results = [(img, None) for img in batch_images]

                    # 4b. Nadir mask (no AI): overlay a disc on the Down view.
                    # Combines with the AI mask when present, otherwise stands
                    # alone so it works even with AI masking off.
                    if nadir_mask_enabled and ai_results:
                        for idx, name in enumerate(batch_names):
                            if name.lower() != 'down':
                                continue
                            img_i, mask_i = ai_results[idx]
                            if img_i is None:
                                continue  # view dropped by AI "Skip Frame"
                            disc = self._build_nadir_mask(img_i.shape, nadir_mask_radius, ai_invert_mask)
                            if isinstance(mask_i, np.ndarray):
                                # Union of ignore regions: ignore=0 with the default
                                # invert convention (min wins), else ignore=255 (max).
                                combined = cv2.min(mask_i, disc) if ai_invert_mask else cv2.max(mask_i, disc)
                            else:
                                combined = disc
                            ai_results[idx] = (img_i, combined)

                    # 5. Save (Multi-threaded I/O)
                    futures = []
                    for i, (final_img, mask_or_skip) in enumerate(ai_results):
                        if final_img is None and mask_or_skip is True:
                            views_skipped_ai += 1
                            continue # Skipped

                        name = batch_names[i]
                        save_name, mask_name = output_names(job.settings, name_no_ext, frame_idx, name)

                        full_save_path = os.path.join(output_dir, save_name)
                        full_mask_path = os.path.join(output_dir, mask_name)

                        # Per-view EXIF: intrinsics + capture time (when
                        # enrichment is on) and GPS fix + absolute direction
                        # (heading of travel + this view's yaw) when available.
                        exif_bytes = None
                        if exif_enabled or current_gps is not None:
                            view_heading = None
                            if current_heading is not None:
                                view_heading = (current_heading + view_yaws.get(name, 0.0)) % 360.0
                            exif_bytes = exif_writer.build_exif_bytes(
                                fov_deg=fov if (exif_enabled and is_360) else None,
                                capture_dt=frame_dt if exif_enabled else None,
                                gps=current_gps,
                                heading_deg=view_heading,
                                camera_model=camera_model_label if exif_enabled else None,
                            )

                        # Submit to thread pool (with safety check for shutdown)
                        if not self.is_running:
                            break

                        futures.append((self.io_pool.submit(
                            FileManager.write_pair, full_save_path, final_img, save_params,
                            exif_bytes, full_mask_path,
                            mask_or_skip if isinstance(mask_or_skip, np.ndarray) else None
                        ), {"image": save_name, "mask": mask_name if isinstance(mask_or_skip, np.ndarray) else None, "camera": name, "frame": frame_idx}))

                    failures = []
                    accepted = 0
                    for future, record in futures:
                        try:
                            if not future.result():
                                raise OSError("Writer did not confirm the output")
                            images_written += 1
                            accepted += 1
                            written_view_names.add(record["camera"])
                            with open(os.path.join(output_dir, "images.jsonl"), "a", encoding="utf-8") as index_file:
                                index_file.write(json.dumps(record) + "\n")
                        except Exception as exc:
                            failures.append(str(exc))
                    job.result['extraction'] = dict(
                        interval_frames=interval, frames_processed=frames_processed,
                        frames_skipped_motion=frames_skipped_motion, images_written=images_written,
                        views_skipped_blur=skipped_blur_count, views_skipped_ai=views_skipped_ai,
                        writes_failed=len(failures),
                    )
                    if failures:
                        raise OSError("; ".join(failures))
                    if accepted and adaptive_mode:
                        last_extracted_frame = frame.copy()

                frame_idx += 1
            if not is_image and self.is_running and frame_idx < total_frames_video - 1:
                raise IOError(f"Decoder stopped at frame {frame_idx}, expected {total_frames_video}; output is partial")
        finally:
            if cap:
                cap.release()

        if skipped_blur_count > 0:
            logger.info(f"Total blurry views skipped for {filename}: {skipped_blur_count}")

        # COLMAP priors (I1-N2): exact shared intrinsics + exact cam-from-rig
        # rotations + a turnkey reconstruction script.
        if self.is_running and images_written and job.settings.get('export_colmap', False):
            if is_360:
                colmap_export.write_colmap_export(
                    output_dir, views, written_view_names, fov, out_res
                )
            else:
                logger.warning(
                    "COLMAP export skipped: flat (non-360) media has no virtual rig "
                    "with known intrinsics."
                )

        # Per-job manifest: reproducibility + support ("why only N images?").
        duration_seconds = (total_frames_video / fps) if fps else 0.0
        job.result.update({
            "video": {
                "fps": round(fps, 3),
                "total_frames": total_frames_video,
                "duration_seconds": round(duration_seconds, 2),
            },
            "extraction": {
                "interval_frames": interval,
                "frames_processed": frames_processed,
                "frames_skipped_motion": frames_skipped_motion,
                "images_written": images_written,
                "views_skipped_blur": skipped_blur_count,
                "views_skipped_ai": views_skipped_ai,
            },
            "elapsed_seconds": round(time.time() - job_start_time, 2),
        })

    def _write_manifest(self, output_dir, job, stats):
        """Write a manifest.json in the job's output folder.

        Records the settings used and how many frames/views were extracted or
        skipped, so a run can be reproduced and support questions answered.
        """
        manifest = {
            "app": APP_NAME,
            "version": VERSION,
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "source_file": job.file_path,
            "output_dir": output_dir,
            "settings": job.settings,
            **stats,
        }
        manifest["schema_version"] = 2
        FileManager.save_json(os.path.join(output_dir, "manifest.json"), manifest)
