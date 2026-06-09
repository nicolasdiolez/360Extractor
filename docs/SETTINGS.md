# Settings and Configuration Guide

This guide explains the various settings available in the 360 Extractor Pro GUI and how to use JSON configuration files for batch processing and CLI mode.

## Core Settings

*   **360° Input:** Toggle whether the source is 360° equirectangular media.
    *   *Enabled (default):* Media is reprojected into rectilinear pinhole views (the camera/layout settings below apply).
    *   *Disabled (flat / non-360):* Standard video and images are processed as-is, at their native resolution. Blur filtering, AI masking, sharpening, telemetry and naming still apply, but the camera/layout/inclination settings are ignored. (CLI: `--flat`.)
*   **Extraction Interval:** Choose how often to extract frames.
    *   *Seconds:* Good for time-based sampling (e.g., every 1.0s).
    *   *Frames:* Good for exact frame stepping (e.g., every 30 frames).
*   **Camera Count:** Number of virtual pinhole cameras (2-36). *(360° input only.)*
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
*   **Telemetry (Export GPS/IMU):**
    *   *Enable:* Extract GPS/IMU metadata (GoPro GPMF, Insta360 CAMM, DJI SRT, or a sidecar `.gpx`) and embed GPS coordinates into each output image's EXIF.
    *   *Altitude Source:* For DJI clips that expose both a relative and an absolute altitude (`[rel_alt: … abs_alt: …]`), choose which one to write to EXIF. **Absolute** (above sea level) is recommended for RealityScan/COLMAP geo-referencing and scale; **Relative** is height above the takeoff point. Other devices carry a single altitude and ignore this setting. Default is `absolute`. (CLI: `--altitude-mode`.)

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
    "is_360": true,
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

> Set `"is_360": false` (or pass `--flat`) to process standard, non-panoramic
> media without reprojection.
