# CLI Mode Documentation

This document provides detailed information about using the 360 Extractor Pro in headless mode. This is ideal for automation or server environments.

## Overview

Run the application in headless mode by providing the `--input` argument or a configuration file.

The CLI is fully headless: it never loads Qt, and the AI stack (torch/ultralytics) is only imported when an AI mode is actually enabled. On servers you can install `opencv-python-headless` instead of `opencv-python` to avoid needing system OpenGL libraries.

> **Note on Flags:** Boolean flags (like `--ai-mask`, `--ai-skip`, `--adaptive`, `--export-telemetry`) are toggles. Including them enables the feature; they do not take a value (e.g., use `--ai-mask`, not `--ai-mask true`).

## Visual Progress

The CLI displays a real-time progress bar (via `tqdm`) showing the completion percentage and estimated time remaining for both individual files and the entire batch.

## Basic Syntax

```bash
python src/main.py --input <video_path> --output <output_dir> [options]
```

## CLI Arguments Reference

| Flag | Description | Default |
| :--- | :--- | :--- |
| `--input`, `-i` | Path to input video/image file or directory. **(Required)** | - |
| `--output`, `-o` | Path to output directory. | `./output` |
| `--config` | Path to a JSON configuration file. | - |
| `--version` | Print the application version and exit. | - |
| `--flat` | Treat input as standard (non-360) media; disables equirectangular reprojection. | `False` |
| `--interval` | Extraction interval in seconds. | `1.0` |
| `--format` | Output image format (`jpg`, `png`, or `tiff`). | `jpg` |
| `--camera-count` | Number of virtual cameras (2-36). | `6` |
| `--active-cameras` | Comma-separated list of camera indices to extract (e.g., `0,2,4`). | All |
| `--resolution` | Output image resolution (width/height). | `2048` |
| `--layout` | Camera layout mode: `ring`, `cube`, or `fibonacci`. | `ring` |
| `--quality` | JPEG quality (1-100). | `95` |
| `--ai-mask` | Enable AI masking (Generate Mask) for operator removal. | `False` |
| `--ai-skip` | Enable AI frame skipping (discard frames with persons). | `False` |
| `--ai` | Alias for `--ai-mask` (for backward compatibility). | `False` |
| `--ai-model` | Segmentation model: size letter (`n`/`s`/`m`/`l`/`x`), a model name, or a path to a custom `.pt`. Larger models catch partial operators (arm, pole) at the cost of speed; non-nano weights are auto-downloaded on first use. | `yolo26n-seg.pt` |
| `--ai-mask-cameras` | Restrict AI masking to these faces only, comma-separated (e.g. `Down` or `Back,Down`). Cube faces: `Front,Right,Back,Left,Up,Down`; ring/fibonacci: `View_0,View_1,…`. Empty = all faces. | All |
| `--nadir-mask` | Add a disc mask over the pole/tripod on the `Down` face (Cube layout). No AI needed; combines with the AI mask when both are on. | `False` |
| `--nadir-radius` | Nadir mask radius as a percentage of the `Down` face. | `40` |
| `--adaptive` | Enable intelligent keyframing (skip static scenes). | `False` |
| `--motion-threshold` | Motion threshold for adaptive keyframing (mean optical-flow magnitude between kept frames; useful range ≈ 0–10). Higher = needs more motion to extract. | `0.5` |
| `--export-telemetry` | Extract GPS/IMU metadata and embed it into output images (EXIF). | `False` |
| `--altitude-mode` | EXIF GPS altitude source for DJI clips that expose both: `absolute` (above sea level, best for RealityScan/COLMAP) or `relative` (above takeoff). | `absolute` |
| `--naming-mode` | Naming convention: `realityscan`, `simple`, or `custom`. | `realityscan` |
| `--image-pattern` | Custom image filename pattern (e.g., `{filename}_{frame}`). | - |
| `--mask-pattern` | Custom mask filename pattern (e.g., `{image_name}_mask`). | - |

## Examples

### 1. Basic Extraction
Extract frames every 1.0 seconds from a video.
```bash
python src/main.py --input videos/trip.mp4 --output frames/trip --interval 1.0
```

### 2. Selective Cameras
Extract only the Front (0) and Back (2) cameras from a standard 6-camera setup.
```bash
python src/main.py --input videos/trip.mp4 --output frames/trip --active-cameras "0,2"
```
*Camera Indices for 6-camera layout: 0:Front, 1:Right, 2:Back, 3:Left, 4:Up, 5:Down.*

### 3. Mask the Operator on One Face Only
Generate masks but restrict them to the `Down` face (the operator/monopod),
leaving people in paintings or posters on the other faces untouched.
```bash
python src/main.py --input videos/museum.mp4 --output frames/museum --layout cube --ai-mask --ai-mask-cameras "Down"
```

### 4. Standard (Non-360) Media
Process a regular (non-panoramic) video or image without reprojection.
```bash
python src/main.py --input clips/interview.mp4 --output frames/interview --flat
```

### 5. Using a Config File
Run a job defined in a JSON file.
```bash
python src/main.py --config my_job.json
```
