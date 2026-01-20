# Settings and Configuration Guide

This guide explains the various settings available in the 360 Extractor Pro GUI and how to use JSON configuration files for batch processing and CLI mode.

## Core Settings

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

## Advanced Processing

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

## File Naming

The application supports three naming conventions:

| Mode | Image | Mask |
|------|-------|------|
| **RealityScan** | `video_frame000001_front.jpg` | `video_frame000001_front.jpg.mask.png` |
| **Simple Suffix** | `video_frame000001_front.jpg` | `video_frame000001_front_mask.png` |
| **Custom** | User-defined pattern | User-defined pattern |

### Custom Pattern Placeholders:
- `{filename}` - Original video name
- `{frame}` - 6-digit frame number
- `{camera}` - Camera name (front, back, etc.)
- `{ext}` - File extension

---

## Configuration Files (JSON)

You can define job settings in a JSON file for reuse or complex configurations. CLI arguments override settings found in the configuration file.

### Structure Example (`config.json`):

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
    "ai_mask": true,
    "adaptive": false,
    "naming_mode": "realityscan"
}
```
