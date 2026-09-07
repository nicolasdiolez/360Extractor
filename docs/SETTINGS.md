# Settings and configuration

This reference describes the current correction branch. See [installation](../README.md#install-from-source), [CLI arguments](CLI.md) and [qualification status](implementation-2026-09-07/PROGRESSION.md).

## Studio behavior

Select a queue card to edit its settings. Multiple selection changes the fields you edit while preserving other per-job values. Studio does not yet display every mixed value explicitly; inspect individual cards when settings differ. With no selected job, edits update defaults for subsequent imports. Preferences are stored in `~/.application360/config.json`, overridable with `EXTRACTOR360_CONFIG_DIR`. A saved queue/project file is not implemented.

Preset selection resets settings to a complete profile. Presets labelled for reconstruction tools are starting points, not verified compatibility certifications. Preview uses the selected layout and export resolution before reducing its display size; masks require real model inference. Timeline scrubbing is supported; automatic playback is not. Analyze samples one video frame and suggests a blur threshold from its view scores; this is a heuristic, not an optimal threshold for the whole clip.

Cube indices are **0 Front, 1 Right, 2 Back, 3 Left, 4 Up, 5 Down**. Ring and Fibonacci instead use `View_0` through `View_(N-1)`. Flat has one view, `flat`, at index 0. Camera indices always refer to the full generated layout before selection. Nadir masking needs an active Down view.

## Configuration files

JSON settings use the keys below; CLI flags use their own names. Not every key has a GUI control or CLI flag. YAML is not supported. In CLI mode, precedence is **built-in defaults < JSON config < explicitly supplied CLI arguments**; Studio's saved preferences do not seed a CLI job.

Save this as `config.json`, substituting existing media and the desired destination. Relative paths are interpreted from the process working directory, not the config file's directory:

```json
{
  "input": "videos/trip.mp4",
  "output": "out/config",
  "is_360": true,
  "layout_mode": "cube",
  "active_cameras": [0, 2],
  "resolution": 1024,
  "interval_value": 2,
  "interval_unit": "Seconds",
  "output_format": "png",
  "ai_mode": "None"
}
```

Run `360extractor --config config.json`. JSON `input` and `output` select CLI paths; `output` takes precedence over the core's `custom_output_dir`. Legacy `interval` and `format` alias `interval_value` and `output_format` when the canonical key is absent; legacy `ai: true` enables mask generation if no AI mode is already selected.

## Complete settings reference

Defaults below come from `SettingsManager.DEFAULT_SETTINGS`. Numeric ranges describe core validation; some Studio controls expose a narrower range. Use the CLI/config for values beyond those controls rather than assuming the UI can round-trip them. Settings must have the expected types; numbers must be finite. Unknown keys are not a supported extension mechanism and may be ignored.

| Key | Default | Meaning |
| :--- | :--- | :--- |
| `is_360` | `true` | Stitched equirectangular input. False keeps native flat dimensions. |
| `resolution` | `2048` | Square projection size, 16–8192 px; ignored for flat dimensions. |
| `fov` | `90` | Projection FOV, 1–179 degrees. Studio exposes 45–140. |
| `camera_count` | `6` | 1–64 for Ring/Fibonacci; Cube generates six. |
| `pitch_offset` | `0` | −90 to +90 degrees. Ring: every view; Cube: four horizontal views; Fibonacci: added to each generated pitch. |
| `layout_mode` | `"ring"` | ring, cube or fibonacci. Legacy adaptive is normalized to ring; it does not enable motion filtering. |
| `ai_mode` | `"None"` | None, Generate Mask or Skip Frame. Skip rejects individual views, not the entire capture. |
| `ai_model` | `"yolo26n-seg.pt"` | n/s/m/l/x resolve to standard yolo26 segmentation weights. Custom .pt paths require trust. Unrecognized short names currently fall back to nano; inspect the active-model log. |
| `trust_custom_model` | `false` | Must be explicitly true for a custom model; .pt loading can execute code. |
| `ai_confidence` | `0.25` | Detection threshold, 0–1. |
| `ai_invert_mask` | `true` | True: black ignores the subject, white keeps background. Required for masks exported to COLMAP. |
| `ai_detect_humans` | `true` | COCO person. |
| `ai_detect_vehicles` | `false` | COCO car, motorcycle, airplane, bus, train, truck and boat. Add bicycle via custom classes if needed. |
| `ai_detect_plants` | `false` | COCO potted plant only; not general vegetation. |
| `ai_custom_classes` | `""` | Additional comma-separated COCO names, e.g. bicycle,dog; not arbitrary text-prompt detection. |
| `ai_mask_cameras` | `[]` | Empty list/null means all. Accepts names or comma-separated names; applies to either AI mode. Flat ignores face scope. |
| `nadir_mask_enabled` | `false` | Disc on the active Cube Down face, independently of AI. No inpainting. |
| `nadir_mask_radius` | `40.0` | 0–100 percent of half the smaller Down-view dimension. 40 gives radius 0.2 × side for a square image. |
| `quality` | `95` | JPEG quality 1–100; ignored for PNG/TIFF. |
| `output_format` | `"jpg"` | jpg, png or tiff; TIFF filenames end in .tif. |
| `custom_output_dir` | `""` | Studio/core parent destination; empty means alongside the source. CLI overrides it using --output or JSON output, otherwise ./output. |
| `interval_value` | `1.0` | 0.001–86400. Seconds use decoder time. Frames uses max(1, int(value)); use whole numbers. |
| `interval_unit` | `"Seconds"` | Seconds or Frames. |
| `blur_filter_enabled` | `false` | Enable per-view sharpness rejection. |
| `smart_blur_enabled` | `false` | Rolling per-view relative blur threshold when blur filtering is enabled. |
| `blur_threshold` | `100.0` | Variance-of-Laplacian floor, 0–1000000000. Higher is stricter; depends on resolution/content. |
| `sharpening_enabled` | `false` | Unsharp mask after projection and blur scoring. |
| `sharpening_strength` | `0.5` | 0–5; Studio exposes 0–2. |
| `adaptive_mode` | `false` | Motion-based selection; reference updates after at least one view is saved. |
| `adaptive_threshold` | `0.5` | Mean optical-flow threshold, 0–1000000. Studio exposes 0.1–10. |
| `export_telemetry` | `false` | Supported GPS extraction and geotags, not IMU orientation. Missing GPS does not necessarily fail image extraction. |
| `altitude_mode` | `"absolute"` | absolute or relative DJI source selection. Relative is omitted from GPS EXIF. |
| `exif_intrinsics` | `true` | Virtual-camera calibration tags for 360 views. Capture time only when container creation_time is recovered through telemetry. No fabricated heading or filesystem capture date. |
| `gps_altitude_reference` | `"unknown"` | Use orthometric only after confirming mean-sea-level altitude. Unknown/unverified altitude is omitted; relative mode remains omitted. |
| `export_colmap` | `false` | 360 calibration/rig files plus Python runner. Requires real reconstruction qualification. |
| `interpolation_mode` | `"linear"` | linear or lanczos. |
| `feather_mask` | `false` | Smooth edges of a binary mask; not probabilities, alpha-channel preservation or background reconstruction. |
| `naming_mode` | `"realityscan"` | realityscan, simple or custom. See naming rules below. |
| `image_pattern` | `"{filename}_frame{frame}_{camera}"` | Custom image pattern; append the output extension if omitted. |
| `mask_pattern` | `"{filename}_frame{frame}_{camera}_mask"` | Custom mask pattern; PNG extension appended if needed. |

Two additional supported controls are supplied outside that default dictionary:

| Key | Default | Meaning |
| :--- | :--- | :--- |
| `active_cameras` | `null` | All generated views. Otherwise a nonempty list of valid integer indices; duplicates are removed. Empty/out-of-range lists are rejected. |
| `memory_budget_mb` | `1536` | Projection working-set estimate limit, 128–65536 MiB. It does not bound all decoder RAM or GPU VRAM. |

## Naming and output layout

Names preserve the generated camera's case. For source `trip.mp4`, first frame and Cube Front:

| Mode | Image | Mask, when generated |
| :--- | :--- | :--- |
| realityscan | `trip_frame000000_Front.jpg` | `trip_frame000000_Front.jpg.mask.png` |
| simple | `trip_frame000000_Front.jpg` | `trip_frame000000_Front_mask.png` |
| custom | Defined by image_pattern | Defined by mask_pattern |

| Placeholder | Value |
| :--- | :--- |
| `{filename}` | Source stem without extension. |
| `{frame}` | Zero-based source frame index, padded to six digits. Use `{frame}` directly, without an additional numeric format. |
| `{camera}` | Generated view name, e.g. Front, View_0 or flat. |
| `{ext}` | Image extension **including the dot**, e.g. .jpg or .tif. |
| `{image_name}` | Complete resolved image filename; available in the mask pattern only. |

A valid custom pair is `"{filename}_{frame}_{camera}{ext}"` and `"{image_name}.mask.png"`. Video names must contain `{frame}` and multi-view names `{camera}`. Masks need equivalent identifiers or `{image_name}`. Image extensions must match the selected format. Paths, reserved Windows names, unsafe characters and collisions are rejected before image writes.

The output parent contains a new folder for each run. `manifest.json` schema 2 records initial `running` state, then `completed`, `failed` or `cancelled`; `images.jsonl` records confirmed pairs with view/frame identity. Files are not overwritten or automatically resumed. An abrupt shutdown can leave incomplete pairs/index data and a running manifest; staged writes do not provide a two-file power-loss transaction.

## Models and metadata

Standard weights use `~/.cache/360-extractor/models`, or `EXTRACTOR360_MODEL_DIR`. Missing weights may download on first use. The application sets an app-specific Ultralytics settings directory unless `YOLO_CONFIG_DIR` is already set. Provision weights before offline operation. Model load/inference failures are errors, not successful empty masks.

Embedded GPS uses supported CAMM 5/6 or GPMF GPS5 data; GPS9 is explicitly unsupported. GPX 1.0/1.1 and SRT sidecars are matched by source stem, case-insensitively. Their alignment assumes the sidecar begins at video start. FFprobe is used for embedded metadata; the environment diagnostic checks both ffmpeg and ffprobe. Positions are interpolated only inside the trace and across gaps no longer than ten seconds.

Unknown/relative altitude is omitted from EXIF. Set `gps_altitude_reference` to `orthometric` only with evidence for that source. The GPS trajectory does not establish optical heading; IMU orientation and auto-leveling are not exported. Capture time is omitted when its source is unknown. Telemetry status must be checked separately from overall extraction success.

COLMAP masks require `ai_invert_mask: true` (black means ignore). The runner consumes the confirmed image index, builds camera folders and a separate mask tree, applies the virtual rig and invokes sequential matching. Calibration files represent the ideal projection, not evidence of reconstruction accuracy or camera-vendor compatibility. GPS9, HDR/ICC/alpha processing and real reconstruction qualification remain open in the [implementation plan](implementation-2026-09-07/PROGRESSION.md).
