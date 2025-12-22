#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
import os
import argparse
import json
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QCoreApplication

from ui.main_window import MainWindow
from core.settings_manager import SettingsManager
from core.job import Job
from core.processor import ProcessingWorker
from utils.logger import logger

# Try importing tqdm for progress bar
try:
    from tqdm import tqdm
    TQDM_AVAILABLE = True
except ImportError:
    TQDM_AVAILABLE = False

def parse_arguments():
    parser = argparse.ArgumentParser(description="Application360 Video Extractor")
    parser.add_argument("--config", type=str, help="Path to JSON configuration file")
    parser.add_argument("--input", "-i", type=str, help="Path to input video file or directory (CLI mode)")
    parser.add_argument("--output", "-o", type=str, help="Path to output directory (CLI mode)")
    parser.add_argument("--interval", type=float, help="Extraction interval in seconds (default: 1.0)")
    parser.add_argument("--format", type=str, choices=['jpg', 'png'], help="Output image format (default: jpg)")
    parser.add_argument("--ai", action="store_true", help="Enable AI masking (Legacy alias for --ai-mask)")
    parser.add_argument("--ai-mask", action="store_true", help="Enable AI masking (Generate Mask)")
    parser.add_argument("--ai-skip", action="store_true", help="Enable AI frame skipping (Skip Frame)")
    parser.add_argument("--camera-count", type=int, help="Number of virtual cameras (default: 6)")
    parser.add_argument("--quality", type=int, help="JPEG quality (1-100, default: 95)")
    parser.add_argument("--active-cameras", type=str, help="Comma-separated list of active camera indices (e.g. '0,1,4')")
    parser.add_argument("--resolution", type=int, help="Output image resolution (width/height) (default: 2048)")
    parser.add_argument("--layout", type=str, choices=['ring', 'cube', 'fibonacci'], help="Camera layout mode (ring/cube/fibonacci, default: ring)")
    parser.add_argument("--adaptive", action="store_true", help="Enable adaptive interval (motion-based)")
    parser.add_argument("--motion-threshold", type=float, help="Motion threshold for adaptive interval (default: 0.5)")
    parser.add_argument("--export-telemetry", action="store_true", help="Export GPS/IMU metadata (if available)")
    return parser.parse_args()

def load_config(config_path):
    """Load configuration from a JSON file."""
    if not os.path.exists(config_path):
        logger.error(f"Configuration file not found: {config_path}")
        sys.exit(1)
    
    try:
        with open(config_path, 'r') as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing configuration file: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error loading configuration file: {e}")
        sys.exit(1)

def run_cli(args):
    logger.info("Starting Application360 in CLI Mode...")
    
    # Load config file if provided
    config = {}
    if args.config:
        config = load_config(args.config)
        logger.info(f"Loaded configuration from {args.config}")

    # Helper to get value from args (priority) or config or default
    def get_arg(arg_name, config_name, default=None):
        val = getattr(args, arg_name)
        if val is not None: # Explicitly set in CLI
            # Handle boolean flags specifically if needed, but argparse defaults store_true to False
            # If the user didn't set --ai, it's False. We only want to override if True? 
            # Actually, standard behavior is CLI overrides config. 
            # But for flags that default to False, we check if they are True.
            if arg_name == 'ai' and val is False:
                 # Check config
                 return config.get(config_name, default)
            return val
        return config.get(config_name, default)

    # Determine Input
    input_path = args.input or config.get('input')
    if not input_path:
        logger.error("Error: Input path is required (via --input or config file).")
        sys.exit(1)
        
    if not os.path.exists(input_path):
        logger.error(f"Error: Input path not found: {input_path}")
        sys.exit(1)
    
    # Determine Output
    output_path = args.output or config.get('output')
    if not output_path:
        # If output not specified, maybe use input directory? 
        # For safety, let's require it or default to "output" folder in current dir
        output_path = os.path.join(os.getcwd(), "output")
        logger.warning(f"No output path specified. Using default: {output_path}")

    # Ensure output directory exists
    if not os.path.exists(output_path):
        try:
            os.makedirs(output_path)
            logger.info(f"Created output directory: {output_path}")
        except OSError as e:
            logger.error(f"Error creating output directory {output_path}: {e}")
            sys.exit(1)
            
    # Prepare jobs
    files_to_process = []
    if os.path.isdir(input_path):
        for root, dirs, files in os.walk(input_path):
            for f in files:
                if f.lower().endswith(('.mp4', '.avi', '.mov', '.mkv')):
                    files_to_process.append(os.path.join(root, f))
    else:
        files_to_process.append(input_path)
        
    if not files_to_process:
        logger.error("No video files found.")
        sys.exit(1)

    logger.info(f"Found {len(files_to_process)} file(s) to process.")

    # Parse Active Cameras
    active_cameras_str = args.active_cameras or config.get('active_cameras')
    active_cameras = None
    if active_cameras_str:
        try:
            # Handle list from JSON or string from CLI
            if isinstance(active_cameras_str, list):
                active_cameras = [int(x) for x in active_cameras_str]
            else:
                active_cameras = [int(x.strip()) for x in active_cameras_str.split(',')]
        except ValueError:
            logger.error(f"Error: Invalid format for active-cameras: {active_cameras_str}")
            sys.exit(1)

    # Prepare settings
    # Note: args.interval etc are None if not provided because I removed default in add_argument for some
    # Actually I should verify defaults logic. 
    # To properly support "CLI overrides Config overrides Default", I removed defaults from add_argument 
    # except for flags where it's trickier.
    # Let's adjust get_arg logic to handle defaults manually.
    
    interval = args.interval if args.interval is not None else config.get('interval', 1.0)
    fmt = args.format if args.format is not None else config.get('format', 'jpg')
    cam_count = args.camera_count if args.camera_count is not None else config.get('camera_count', 6)
    quality = args.quality if args.quality is not None else config.get('quality', 95)
    resolution = args.resolution if args.resolution is not None else config.get('resolution', 2048)
    layout_mode = args.layout if args.layout is not None else config.get('layout_mode', 'ring')
    
    # AI Mode logic
    ai_mode = 'None'
    if args.ai_skip:
        ai_mode = 'Skip Frame'
    elif args.ai_mask or args.ai:
        ai_mode = 'Generate Mask'
    else:
        # Check config
        ai_mode = config.get('ai_mode', 'None')
        # Handle legacy config 'ai': boolean if ai_mode is still None
        if ai_mode == 'None' and config.get('ai', False):
            ai_mode = 'Generate Mask'

    # Adaptive Mode logic
    adaptive = args.adaptive
    if not adaptive:
        adaptive = config.get('adaptive_mode', False)
    
    motion_threshold = args.motion_threshold if args.motion_threshold is not None else config.get('adaptive_threshold', 0.5)
    
    export_telemetry = args.export_telemetry
    if not export_telemetry:
        export_telemetry = config.get('export_telemetry', False)

    settings = {
        'interval_value': interval,
        'interval_unit': 'Seconds',
        'output_format': fmt,
        'camera_count': cam_count,
        'quality': quality,
        'layout_mode': layout_mode,
        'ai_mode': ai_mode,
        'custom_output_dir': output_path,
        'active_cameras': active_cameras,
        # Defaults for others (could be exposed to config later)
        'resolution': resolution,
        'fov': config.get('fov', 90),
        'pitch_offset': config.get('pitch_offset', 0),
        'blur_filter_enabled': config.get('blur_filter_enabled', False),
        'smart_blur_enabled': config.get('smart_blur_enabled', False),
        'sharpening_enabled': config.get('sharpening_enabled', False),
        'adaptive_mode': adaptive,
        'adaptive_threshold': motion_threshold,
        'export_telemetry': export_telemetry
    }

    jobs = [Job(file_path=f, settings=settings) for f in files_to_process]
    
    # Initialize Core Application for Signal/Slot support
    core_app = QCoreApplication(sys.argv)

    worker = ProcessingWorker(jobs)
    
    # Progress Bar Handling
    if TQDM_AVAILABLE:
        current_job_idx = [0] # Use a list to make it mutable in closures
        pbar = tqdm(total=100, unit="%", bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt}% [{elapsed}<{remaining}]')
        
        def update_progress(val, msg):
            # Calculate global percentage: (current_job * 100 + current_val) / total_jobs
            overall_pct = (current_job_idx[0] * 100 + val) / len(jobs)
            pbar.set_description(msg.split(" - ")[0]) # Show current file in description
            pbar.n = round(overall_pct, 1)
            pbar.refresh()
            
        def on_job_started(idx):
            current_job_idx[0] = idx
            
        def on_finished():
            pbar.n = 100
            pbar.refresh()
            pbar.close()
            logger.info("All jobs finished.")
            
        def on_error(err):
            pbar.write(f"ERROR: {err}") # Write above bar
            
        worker.progress_updated.connect(update_progress)
        worker.job_started.connect(on_job_started)
        worker.error_occurred.connect(on_error)
        worker.finished.connect(on_finished)
        
    else:
        # Fallback to logging
        worker.progress_updated.connect(lambda val, msg: logger.info(f"[{val}%] {msg}"))
        worker.error_occurred.connect(lambda err: logger.error(f"ERROR: {err}"))
        worker.finished.connect(lambda: logger.info("All jobs finished."))
    
    # Run processing synchronously
    try:
        worker.run()
    except KeyboardInterrupt:
        if TQDM_AVAILABLE: pbar.close()
        logger.info("\nProcess interrupted by user.")
        worker.stop()
        sys.exit(1)
    except Exception as e:
        if TQDM_AVAILABLE: pbar.close()
        logger.error(f"An unexpected error occurred: {e}")
        sys.exit(1)

def main():
    args = parse_arguments()
    
    # Check if CLI required arguments are present (input is strictly required via CLI or Config)
    # But here we only check if we should go to CLI mode vs GUI mode.
    # If --input or --config is passed, we assume CLI mode.
    if args.input or args.config:
        run_cli(args)
    else:
        # GUI Mode
        app = QApplication(sys.argv)
        
        # Initialize settings
        SettingsManager()
    
        window = MainWindow()
        window.show()
        
        sys.exit(app.exec())

if __name__ == "__main__":
    main()