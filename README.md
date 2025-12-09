# 360 Extractor

High-performance desktop application for 360° video preprocessing. This tool generates optimized datasets for Gaussian Splatting and photogrammetry (COLMAP, RealityScan) by converting equirectangular footage into rectilinear pinhole views and removing operators using AI.

## Features

- **360° to Rectilinear:** Reproject equirectangular video to pinhole views with configurable FOV and overlap.
- **Advanced Camera Control:**
    - **Dynamic Camera Count:** Configure 2 to 36 cameras with intelligent distribution (Ring for <6, Cube for 6, Fibonacci Sphere for >6).
    - **Inclination:** Adjust camera pitch (Standard 0°, High -20°, Low +20°) for different capture scenarios.
- **Blur Filter:** Automatically detect and discard blurry frames based on a configurable threshold (Variance of Laplacian).
- **Flexible Extraction:** Control extraction frequency by Seconds or Frames.
- **AI Operator Removal:** Automatically detect and mask/remove people (operators) from the footage using YOLOv8.
- **Batch Processing:** Process multiple heavy (4K-8K) video files efficiently with individual settings.
- **Cross-Platform:** Built with Python & PySide6 for macOS (Apple Silicon optimized) and Windows.

## Installation

1.  **Clone the repository**
2.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

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

## Usage

Run the application:

*   **macOS / Linux:**
    ```bash
    python3 src/main.py
    ```

*   **Windows:**
    ```bash
    python src/main.py
    ```

### Batch Processing Workflow

1.  **Add Videos:** Drag and drop video files (`.mp4`, `.mov`, `.mkv`, `.avi`) into the drop zone or click to browse.
2.  **Configure Settings:**
    *   **Global Settings:** Adjust settings in the right panel when no video is selected to apply defaults to new videos.
    *   **Individual Settings:** Select a video in the queue to customize its specific settings (Interval, Camera Count, etc.). The settings panel title will update to show the filename.
3.  **Manage Queue:** Use "Remove Selected" or "Clear Queue" to manage the list.
4.  **Process:** Click "Process Queue" to start. A progress bar will track the overall progress.

### Settings Guide

*   **Extraction Interval:** Choose how often to extract frames.
    *   *Seconds:* Good for time-based sampling (e.g., every 1.0s).
    *   *Frames:* Good for exact frame stepping (e.g., every 30 frames).
*   **Camera Count:** Number of virtual pinhole cameras (2-36).
    *   *< 6:* Ring layout (equally spaced horizon).
    *   *6:* Cube layout (Front, Right, Back, Left, Up, Down).
    *   *> 6:* Fibonacci Sphere distribution for even coverage.
*   **Camera Inclination:** Adjust the vertical tilt of horizontal cameras.
    *   *Standard (0°):* Horizon level.
    *   *High / Perch (-20°):* Tilted down (good for cameras on a high stick).
    *   *Low / Ground (+20°):* Tilted up (good for low-angle captures).
*   **Blur Filter:**
    *   *Enable:* Toggle the blur detection system.
    *   *Threshold:* Adjust sensitivity (0-1000). Higher values are stricter (require sharper images). Default is 100.
    *   *Analyze Selected Video:* Click this button to scan a sample frame from the current video. It calculates the sharpness and recommends an optimal threshold value, simplifying configuration.
*   **AI Operator Removal:**
    *   *None:* No AI processing.
    *   *Skip Frame:* Discard frames where a person is detected.
    *   *Generate Mask:* Create a mask file for the detected person (for inpainting).

### Mask Naming Convention

When **Generate Mask** is used, files are named to be automatically detected by **RealityScan**:
*   Image: `filename.jpg`
*   Mask: `filename.jpg.mask.png`

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