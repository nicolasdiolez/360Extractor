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
    parser.add_argument("--ai", action="store_true", help="Enable AI processing (Generate Mask)")
    parser.add_argument("--camera-count", type=int, help="Number of virtual cameras (default: 6)")
    parser.add_argument("--quality", type=int, help="JPEG quality (1-100, default: 95)")
    parser.add_argument("--active-cameras", type=str, help="Comma-separated list of active camera indices (e.g. '0,1,4')")
    parser.add_argument("--layout", type=str, choices=['adaptive', 'ring'], help="Camera layout mode (adaptive/ring, default: adaptive)")
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
    layout_mode = args.layout if args.layout is not None else config.get('layout_mode', 'adaptive')
    
    # AI Mode logic
    ai_enabled = args.ai # This is True/False from CLI
    if not ai_enabled:
        ai_enabled = config.get('ai', False)
    
    settings = {
        'interval_value': interval,
        'interval_unit': 'Seconds',
        'output_format': fmt,
        'camera_count': cam_count,
        'quality': quality,
        'layout_mode': layout_mode,
        'ai_mode': 'Generate Mask' if ai_enabled else 'None',
        'custom_output_dir': output_path,
        'active_cameras': active_cameras,
        # Defaults for others (could be exposed to config later)
        'resolution': config.get('resolution', 1024),
        'fov': config.get('fov', 90),
        'pitch_offset': config.get('pitch_offset', 0),
        'blur_filter_enabled': config.get('blur_filter_enabled', False),
        'smart_blur_enabled': config.get('smart_blur_enabled', False),
        'sharpening_enabled': config.get('sharpening_enabled', False)
    }

    jobs = [Job(file_path=f, settings=settings) for f in files_to_process]
    
    # Initialize Core Application for Signal/Slot support
    core_app = QCoreApplication(sys.argv)

    worker = ProcessingWorker(jobs)
    
    # Progress Bar Handling
    if TQDM_AVAILABLE:
        # Create a progress bar
        # We'll use a total of 100 * num_jobs, or simpler: just update description
        # Since ProcessingWorker emits 0-100 per job, it's a bit tricky to map to a single global bar 
        # unless we know total frames.
        # But we can have a bar that updates 0-100 for current job.
        
        pbar = tqdm(total=100, unit="%", bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]')
        
        def update_progress(val, msg):
            pbar.set_description(msg.split(" - ")[0]) # Shorten msg
            pbar.n = val
            pbar.refresh()
            
        def on_finished():
            pbar.close()
            logger.info("All jobs finished.")
            
        def on_error(err):
            pbar.write(f"ERROR: {err}") # Write above bar
            
        worker.progress_updated.connect(update_progress)
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