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
    *   *Motion Threshold:* Adjust sensitivity (mean optical-flow magnitude between kept frames). Higher values require more motion to trigger extraction. Default is 0.5. (CLI: `--motion-threshold`.)
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

You can define job settings in a JSON file for reuse or complex configurations.

CLI arguments override settings in the config file, which in turn override the
built-in defaults (`SettingsManager.DEFAULT_SETTINGS`). Any key you omit falls
back to its default; you only need to specify what you want to change.

### Minimal example (`config.json`):

```json
{
    "input": "videos/holiday.mp4",
    "output": "processed/holiday",
    "is_360": true,
    "interval_value": 2.0,
    "interval_unit": "Seconds",
    "output_format": "png",
    "camera_count": 8,
    "layout_mode": "fibonacci",
    "active_cameras": [0, 1, 2, 3, 4, 5, 6, 7],
    "ai_mode": "Generate Mask",
    "naming_mode": "realityscan"
}
```

> Set `"is_360": false` (or pass `--flat`) to process standard, non-panoramic
> media without reprojection.

### Complete key reference

Every supported key, with its default value. Keys are identical in the GUI,
the JSON config, and the CLI; the config file accepts exactly these names.

| Key | Default | Notes |
|-----|---------|-------|
| `is_360` | `true` | Reproject equirectangular input. `false` / `--flat` for standard media. |
| `resolution` | `2048` | Output width/height in px (square). |
| `fov` | `90` | Horizontal field of view per virtual camera, in degrees. |
| `camera_count` | `6` | Number of virtual pinhole cameras (2–36). |
| `pitch_offset` | `0` | Vertical tilt of horizontal cameras, in degrees. |
| `layout_mode` | `"ring"` | `ring`, `cube`, or `fibonacci`. |
| `active_cameras` | *(all)* | List of camera indices to keep, e.g. `[0,1,4]`. Omit for all. |
| `ai_mode` | `"None"` | `None`, `Generate Mask`, or `Skip Frame`. |
| `ai_confidence` | `0.25` | Detection confidence threshold (0–1). |
| `ai_invert_mask` | `true` | `true` = white keeps / black removes (COLMAP/RealityScan convention). |
| `ai_detect_humans` | `true` | Include the person class. |
| `ai_detect_vehicles` | `false` | Include the vehicle classes. |
| `ai_detect_plants` | `false` | Include the plant classes. |
| `ai_custom_classes` | `""` | Comma-separated extra class names. |
| `ai_mask_cameras` | *(all)* | Restrict masking to these faces only, e.g. `["Down"]` or `["Back","Down"]`. Cube faces: `Front,Right,Back,Left,Up,Down`; ring/fibonacci: `View_0,View_1,…`. Empty/omitted = mask every face. |
| `quality` | `95` | JPEG quality (1–100); ignored for PNG. |
| `output_format` | `"jpg"` | `jpg` or `png`. |
| `custom_output_dir` | `""` | Overrides the default per-video output folder. |
| `interval_value` | `1.0` | Sampling interval (paired with `interval_unit`). |
| `interval_unit` | `"Seconds"` | `Seconds` or `Frames`. |
| `blur_filter_enabled` | `false` | Enable blur rejection. |
| `smart_blur_enabled` | `false` | Relative (rolling-average) blur rejection on top of the floor. |
| `blur_threshold` | `100.0` | Sharpness floor (variance of Laplacian); higher is stricter. |
| `sharpening_enabled` | `false` | Apply an unsharp mask after reprojection. |
| `sharpening_strength` | `0.5` | Unsharp-mask strength when enabled. |
| `adaptive_mode` | `false` | Motion-based (intelligent) keyframing. |
| `adaptive_threshold` | `0.5` | Motion threshold (mean optical-flow magnitude) for adaptive keyframing. |
| `export_telemetry` | `false` | Extract GPS/IMU and embed GPS in EXIF. |
| `altitude_mode` | `"absolute"` | `absolute` or `relative` (DJI clips with both altitudes). |
| `interpolation_mode` | `"linear"` | Reprojection interpolation: `linear` or `lanczos`. |
| `feather_mask` | `false` | Soften mask edges instead of a hard binary mask. |
| `naming_mode` | `"realityscan"` | `realityscan`, `simple`, or `custom`. |
| `image_pattern` | `"{filename}_frame{frame}_{camera}"` | Custom mode only. |
| `mask_pattern` | `"{filename}_frame{frame}_{camera}_mask"` | Custom mode only. |

> Older config files using `interval` and `format` are still accepted as
> aliases for `interval_value` and `output_format`.
