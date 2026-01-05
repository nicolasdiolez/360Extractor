# 360 Extractor Pro

High-performance desktop application and command-line tool for 360° video preprocessing. This tool generates optimized datasets for Gaussian Splatting and photogrammetry (COLMAP, RealityScan) by converting equirectangular footage into rectilinear pinhole views and removing operators using AI.

> **v2.0** - New modern UI with sidebar navigation, video cards, and improved user experience.

## Features

- **360° to Rectilinear:** Reproject equirectangular video to pinhole views with configurable FOV and overlap.
- **Modern UI (v2.0):**
    - **Sidebar Navigation:** Quick access to Videos, Settings, Export, and Advanced sections.
    - **Video Cards:** Visual queue with thumbnails, status indicators, and progress tracking.
    - **Collapsible Sections:** Organized settings with smooth animations.
    - **Real-time Preview:** Live preview with blur score indicator.
- **Dual Interface:**
    - **GUI:** User-friendly interface with drag-and-drop support, real-time preview, and batch processing queue.
    - **CLI:** Headless mode for server environments with a real-time visual progress bar.
- **Advanced Camera Control:**
    - **Dynamic Camera Count:** Configure 2 to 36 cameras.
    - **Layout Modes:** Choose from three explicit layout strategies:
        - **Ring:** Evenly spaced along the horizon.
        - **Cube Map:** Fixed 6 cameras (Front, Right, Back, Left, Up, Down). Ignores camera count (forces 6).
        - **Fibonacci:** Evenly distributed on a sphere.
    - **Selective Extraction:** Render only specific camera angles (e.g., only Front and Back) to save processing time and storage.
    - **Inclination:** Adjust camera pitch (Standard 0°, High -20°, Low +20°) for different capture scenarios.
- **Blur Filter:** Automatically detect and discard blurry frames based on a configurable threshold (Variance of Laplacian).
- **GPS/IMU Metadata Integration:** Extract GPS and accelerometer data from GoPro (GPMF), Insta360 (CAMM), or DJI (SRT Subtitles) videos and embed it into the output EXIF tags.
    - Includes custom lightweight parsers for GPMF (GoPro) and CAMM (Insta360) to extract GPS data directly, without external dependencies.
    - Supports DJI drone telemetry embedded as subtitles (SRT) as a fallback.
    - **GPX Sidecar Support:** Automatically detects `video.gpx` files for cameras like Kandao Qoocam 3 Ultra.
- **Flexible File Naming:** Choose between RealityScan-compatible naming, simple suffix, or fully custom patterns with placeholders.
- **Flexible Extraction:** Control extraction frequency by Seconds or Frames.
- **Intelligent Keyframing (Adaptive Interval):** Uses Optical Flow to skip static scenes and only extract frames when significant motion occurs (configurable threshold).
- **AI Operator Removal:** Automatically detect and mask/remove people (operators) from the footage using YOLOv8.
- **Configuration Support:** Save and load job settings using JSON configuration files.
- **Batch Processing:** Process multiple heavy (4K-8K) video files efficiently.
- **Cross-Platform:** Built with Python & PySide6 for macOS (Apple Silicon optimized) and Windows.

## Installation

1.  **Clone the repository**
2.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
    *Note: `tqdm` is required for the CLI progress bar.*

3.  **Verify environment:**
    Run the verification script to ensure all dependencies are correctly installed:

    *   **macOS / Linux:**
        ```bash
        python3 check_env.py
        ```
    *   **Windows:**
        ```bash
        python check_env.py
        ```

4.  **Run tests (optional):**
    ```bash
    python3 -m pytest tests/ -v
    ```

## Usage

### GUI Mode (Graphical Interface)

Run the application without arguments to launch the GUI:

*   **macOS / Linux:**
    ```bash
    python3 src/main.py
    ```

*   **Windows:**
    ```bash
    python src/main.py
    ```

#### Batch Processing Workflow (GUI)
1.  **Add Videos:** Drag and drop video files (`.mp4`, `.mov`, `.mkv`, `.avi`) into the drop zone or click to browse.
2.  **Configure Settings:**
    *   **Global Settings:** Adjust settings in the right panel when no video is selected to apply defaults to new videos.
    *   **Individual Settings:** Select a video in the queue to customize its specific settings (Interval, Camera Count, etc.). The settings panel title will update to show the filename.
3.  **Manage Queue:** Use "Remove Selected" or "Clear Queue" to manage the list.
4.  **Process:** Click "Process Queue" to start. A progress bar will track the overall progress.

### CLI Mode (Command Line Interface)

Run the application in headless mode by providing the `--input` argument or a configuration file. This is ideal for automation or server environments.

> **Note on Flags:** Boolean flags (like `--ai-mask`, `--ai-skip`, `--adaptive`, `--export-telemetry`) are toggles. Including them enables the feature; they do not take a value (e.g., use `--ai-mask`, not `--ai-mask true`).

- **Visual Progress:** Displays a real-time progress bar (via `tqdm`) showing the completion percentage and estimated time remaining for both individual files and the entire batch.

#### Basic Syntax
```bash
python src/main.py --input <video_path> --output <output_dir> [options]
```

#### CLI Arguments
| Flag | Description | Default |
| :--- | :--- | :--- |
| `--input`, `-i` | Path to input video file or directory. **(Required)** | - |
| `--output`, `-o` | Path to output directory. | `./output` |
| `--config` | Path to a JSON configuration file. | - |
| `--interval` | Extraction interval in seconds. | `1.0` |
| `--format` | Output image format (`jpg` or `png`). | `jpg` |
| `--camera-count` | Number of virtual cameras (2-36). | `6` |
| `--active-cameras` | Comma-separated list of camera indices to extract (e.g., `0,2,4`). | All |
| `--resolution` | Output image resolution (width/height). | `2048` |
| `--layout` | Camera layout mode: `ring`, `cube`, or `fibonacci`. | `ring` |
| `--quality` | JPEG quality (1-100). | `95` |
| `--ai-mask` | Enable AI masking (Generate Mask) for operator removal. | `False` |
| `--ai-skip` | Enable AI frame skipping (discard frames with persons). | `False` |
| `--ai` | Alias for `--ai-mask` (for backward compatibility). | `False` |
| `--adaptive` | Enable intelligent keyframing (skip static scenes). | `False` |
| `--motion-threshold` | Sensitivity for motion detection (0.0-100.0). Higher = needs more motion to extract. | `5.0` |
| `--export-telemetry` | Extract GPS/IMU metadata and embed it into output images (EXIF). | `False` |

#### Examples

**1. Basic Extraction:**
Extract frames every 1.0 seconds from a video.
```bash
python src/main.py --input videos/trip.mp4 --output frames/trip --interval 1.0
```

**2. Selective Cameras:**
Extract only the Front (0) and Back (2) cameras from a standard 6-camera setup.
```bash
python src/main.py --input videos/trip.mp4 --output frames/trip --active-cameras "0,2"
```
*Camera Indices for 6-camera layout: 0:Front, 1:Right, 2:Back, 3:Left, 4:Up, 5:Down.*

**3. Using a Config File:**
Run a job defined in a JSON file.
```bash
python src/main.py --config my_job.json
```

## Configuration

You can define job settings in a JSON file for reuse or complex configurations.

**Structure (`config.json`):**
```json
{
    "input": "videos/holiday.mp4",
    "output": "processed/holiday",
    "interval": 2.0,
    "format": "png",
    "camera_count": 6,
    "active_cameras": [0, 1, 2, 3],
    "resolution": 2048,
    "quality": 100,
    "ai": true
}
```

*Note: CLI arguments override settings found in the configuration file.*

## Settings Guide (GUI & General)

*   **Extraction Interval:** Choose how often to extract frames.
    *   *Seconds:* Good for time-based sampling (e.g., every 1.0s).
    *   *Frames:* Good for exact frame stepping (e.g., every 30 frames).
*   **Camera Count:** Number of virtual pinhole cameras (2-36).
*   **Camera Layout:** Select the geometric arrangement of cameras.
    *   *Ring:* Evenly spaced along the horizon.
    *   *Cube Map:* Fixed 6 cameras (Front, Right, Back, Left, Up, Down). Ignores camera count (forces 6).
    *   *Fibonacci:* Evenly distributed on a sphere.
*   **Camera Inclination:** Adjust the vertical tilt of horizontal cameras.
    *   *Standard (0°):* Horizon level.
    *   *High / Perch (-20°):* Tilted down (good for cameras on a high stick).
    *   *Low / Ground (+20°):* Tilted up (good for low-angle captures).
*   **Blur Filter:**
    *   *Enable:* Toggle the blur detection system.
    *   *Threshold:* Adjust sensitivity (0-1000). Higher values are stricter (require sharper images). Default is 100.
    *   *Analyze Selected Video (GUI Only):* Click this button to scan a sample frame from the current video. It calculates the sharpness and recommends an optimal threshold value.
*   **AI Operator Removal:**
    *   *None:* No AI processing.
    *   *Skip Frame:* Discard frames where a person is detected.
    *   *Generate Mask:* Create a mask file for the detected person (for inpainting).
*   **Intelligent Keyframing (Adaptive Interval):**
    *   *Enable:* Toggle adaptive extraction.
    *   *Motion Threshold:* Adjust sensitivity (0.0-100.0). Higher values require more motion to trigger extraction. Default is 5.0.

### File Naming Options

The application supports three naming conventions:

| Mode | Image | Mask |
|------|-------|------|
| **RealityScan** | `video_frame000001_front.jpg` | `video_frame000001_front.jpg.mask.png` |
| **Simple Suffix** | `video_frame000001_front.jpg` | `video_frame000001_front_mask.png` |
| **Custom** | User-defined pattern | User-defined pattern |

**Custom Pattern Placeholders:**
- `{filename}` - Original video name
- `{frame}` - 6-digit frame number
- `{camera}` - Camera name (front, back, etc.)
- `{ext}` - File extension

## Author

**Nicolas Diolez**

## License

This project is licensed under the **GNU Affero General Public License v3.0 (AGPL-3.0)**.

This licensing is required because the project uses **YOLOv8** by **Ultralytics**, which is AGPL-3.0 licensed. By using this software, you agree to comply with the terms of the AGPL-3.0.

See the [LICENSE](LICENSE) file for details.

## Credits / Acknowledgments

Special thanks to the following projects and teams:

*   **[Ultralytics](https://github.com/ultralytics/ultralytics)** for the state-of-the-art YOLOv8 model used for operator removal.
*   **[The Qt Company](https://www.qt.io/)** for PySide6, enabling the cross-platform user interface.
*   **[OpenCV](https://opencv.org/)** for the computer vision library used for image processing.
