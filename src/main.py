#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
import os
import argparse
import json
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QCoreApplication

from ui.main_window import MainWindow
from core.settings_manager import SettingsManager, build_settings
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
    parser.add_argument("--flat", action="store_true", help="Treat input as standard (non-360) media; disables equirectangular reprojection")
    parser.add_argument("--adaptive", action="store_true", help="Enable adaptive interval (motion-based)")
    parser.add_argument("--motion-threshold", type=float, help="Motion threshold for adaptive interval (default: 0.5)")
    parser.add_argument("--export-telemetry", action="store_true", help="Export GPS/IMU metadata (if available)")
    parser.add_argument("--altitude-mode", type=str, choices=['absolute', 'relative'], help="EXIF altitude source for DJI clips: 'absolute' (above sea level, default) or 'relative' (above takeoff)")
    
    # AI Targets
    parser.add_argument("--targets", type=str, help="Comma-separated list of basic targets (humans,vehicles,plants)")
    parser.add_argument("--custom-classes", type=str, help="Custom classes to detect (comma separated)")
    parser.add_argument("--ai-mask-cameras", type=str, help="Restrict AI masking to these faces only, comma-separated (e.g. 'Down' or 'Back,Down'; cube faces: Front,Right,Back,Left,Up,Down; ring/fibonacci: View_0,View_1,...). Empty = all faces.")
    
    # Naming Control
    parser.add_argument("--naming-mode", type=str, choices=['realityscan', 'simple', 'custom'], help="Naming convention for output files")
    parser.add_argument("--image-pattern", type=str, help="Custom pattern for image filenames")
    parser.add_argument("--mask-pattern", type=str, help="Custom pattern for mask filenames")
    
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
    supported_exts = (
        '.mp4', '.avi', '.mov', '.mkv',          # video
        '.jpg', '.jpeg', '.png', '.tiff', '.tif' # image
    )
    if os.path.isdir(input_path):
        for root, dirs, files in os.walk(input_path):
            for f in files:
                if f.lower().endswith(supported_exts):
                    files_to_process.append(os.path.join(root, f))
    else:
        files_to_process.append(input_path)

    if not files_to_process:
        logger.error("No supported video/image files found.")
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

    # Build the settings dict the processor consumes.
    # Precedence: DEFAULT_SETTINGS < config file < explicit CLI arguments.
    settings = build_settings(args, config, active_cameras, output_path)

    jobs = [Job(file_path=f, settings=settings) for f in files_to_process]
    
    # Initialize Core Application for Signal/Slot support. The instance must be
    # kept alive for the duration of processing even though it is not referenced.
    core_app = QCoreApplication(sys.argv)  # noqa: F841

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