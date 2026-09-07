# Command-line guide

This guide describes the correction branch, before its next release. Install the project using the [README](../README.md#install-from-source). Commands below run from the repository root with that environment activated. `python -m extractor360`, `360extractor` and the development launcher `python src/main.py` use the same entry point.

## Starting a job

```sh
360extractor --input videos/trip.mp4 --output out --layout cube --interval 1 --resolution 2048
```

Providing `--input` or `--config` selects CLI mode. With neither, the application opens Studio. The processing core does not import Qt; AI libraries load only when AI processing is requested. The standard installation still installs GUI and AI dependencies; separate lightweight distributions are not available yet.

Supported extensions are `.mp4`, `.avi`, `.mov`, `.mkv`, `.insv`, `.jpg`, `.jpeg`, `.png`, `.tif` and `.tiff`, case-insensitively. The installed decoder must support the actual codec. 360 input must already be stitched; raw dual-fisheye stitching is not implemented.

Directory input is recursive and deduplicated. Scans exclude the destination, generated `_processed` folders and folders containing `manifest.json`. Explicit input files can be selected individually. The destination is a parent folder: each source gets a new `trip_processed`, then `trip_processed_001`, etc. Without `--output` or JSON `output`, CLI uses `./output` as that parent.

## Arguments

Defaults below apply when neither a JSON config nor an explicit argument overrides them. Use `--help` or `-h` to list accepted arguments. Boolean flags take no value: use `--ai-mask`, not `--ai-mask true`. To turn off a feature enabled in JSON, edit that JSON setting; there is no general `--no-*` counterpart.

| Flag | Meaning | Default |
| :--- | :--- | :--- |
| `--input`, `-i` | Source file or directory; can instead be supplied as JSON `input`. | Required for CLI processing |
| `--output`, `-o` | Parent destination; can instead be supplied as JSON `output`. | `./output` |
| `--config` | JSON object; YAML is not supported. | None |
| `--version` | Print the application version and exit. | — |
| `--flat` | Process standard media at native resolution; no panorama projection. | Disabled |
| `--interval` | Sampling interval in seconds, 0.001–86400. Overrides both interval value and unit in JSON. | `1.0` |
| `--format` | `jpg`, `png` or `tiff` (saved with `.tif`). | `jpg` |
| `--camera-count` | 1–64 virtual views for Ring/Fibonacci. Cube always generates six before active-view selection. | `6` |
| `--active-cameras` | Comma-separated zero-based indices, e.g. `0,2`. Indices depend on layout. | All |
| `--resolution` | Square projection size, 16–8192 px, subject to the projection memory budget. Flat ignores this size. | `2048` |
| `--layout` | `ring`, `cube` or `fibonacci`. | `ring` |
| `--quality` | JPEG quality, 1–100. | `95` |
| `--ai-mask` | Generate masks for selected classes and views. | Disabled |
| `--ai-skip` | Reject each view containing a selected target; other views of the same capture can remain. | Disabled |
| `--ai` | Legacy alias for `--ai-mask`. If skip and mask flags are combined, skip takes precedence. | Disabled |
| `--ai-model` | `n`, `s`, `m`, `l`, `x`, their `yolo26*-seg.pt` names, or a trusted custom `.pt` path. Model size does not guarantee scene accuracy. | `yolo26n-seg.pt` |
| `--trust-custom-model` | Explicitly permit loading a trusted custom model, which can execute code. | Disabled |
| `--targets` | Comma-separated groups: `humans`, `vehicles`, `plants`. Replaces the group selection from JSON. Plants means COCO potted plant. | `humans` |
| `--custom-classes` | Additional COCO names, e.g. `bicycle,dog`. Unknown class names are rejected when AI is enabled. | Empty |
| `--ai-mask-cameras` | AI scope for masking or skipping: Cube face names or Ring/Fibonacci `View_0`, etc. Names must be active in the layout. Empty means all; flat ignores face scope. | All |
| `--nadir-mask` | Add a disc to the active Cube Down view; works without AI and combines with AI masks. No Down view means no nadir disc. | Disabled |
| `--nadir-radius` | Disc radius as a percentage of half the smaller image dimension, 0–100. | `40` |
| `--adaptive` | Enable motion-based sampling. | Disabled |
| `--motion-threshold` | Mean optical-flow threshold, 0–1000000; practical values require scene calibration. Larger needs more motion. | `0.5` |
| `--export-telemetry` | Extract supported GPS metadata; no IMU orientation export. Missing GPS is reported and images can still be written without geotags. | Disabled |
| `--altitude-mode` | DJI source selection: `absolute` or `relative`. Relative altitude is omitted from EXIF; absolute also requires a verified orthometric reference. | `absolute` |
| `--no-exif-intrinsics` | Disable synthetic calibration EXIF. Capture dates require an available container timestamp; travel direction is never optical heading. GPS export is controlled separately. | Calibration enabled |
| `--export-colmap` | Write virtual calibration, rig configuration and a reconstruction runner for 360 output. Full reconstruction qualification is pending. | Disabled |
| `--naming-mode` | `realityscan`, `simple` or `custom`. | `realityscan` |
| `--image-pattern` | Custom image pattern, e.g. `{filename}_{frame}_{camera}{ext}`. | See settings guide |
| `--mask-pattern` | Custom mask pattern, e.g. `{image_name}.mask.png`. Providing a pattern implies custom mode unless a mode is explicit. | See settings guide |

FOV, pitch, blur, interpolation, feather, altitude reference and the projection memory budget are configured in JSON; they do not each have a dedicated CLI flag. See the [complete settings reference](SETTINGS.md).

## Examples

Front and Back are Cube indices 0 and 2. Ring is the default and has `View_*` names, not Cube faces:

```sh
360extractor --input videos/trip.mp4 --output out/selective --layout cube --active-cameras "0,2"
```

Mask people only on Down; add a nadir disc if needed:

```sh
360extractor --input videos/museum.mp4 --output out/museum --layout cube --ai-mask --ai-mask-cameras Down --nadir-mask
```

Standard video without panorama projection:

```sh
360extractor --input clips/interview.mp4 --output out/interview --flat
```

Use the JSON example in [SETTINGS.md](SETTINGS.md#configuration-files), which includes its input and output paths:

```sh
360extractor --config config.json
```

Custom naming, including frame and camera so different outputs cannot collide:

```sh
360extractor --input videos/trip.mp4 --output out/custom --layout cube --naming-mode custom --image-pattern "{filename}_{frame}_{camera}{ext}" --mask-pattern "{image_name}.mask.png"
```

Only for a custom model whose source you trust:

```sh
360extractor --input videos/trip.mp4 --output out/trusted --ai-mask --ai-model /path/to/trusted.pt --trust-custom-model
```

For COLMAP:

```sh
360extractor --input videos/trip.mp4 --output out/colmap --layout cube --export-colmap
python out/colmap/trip_processed/colmap/reconstruct.py
```

The runner requires a COLMAP executable with `rig_configurator`. It creates a new workspace; rerunning against an existing workspace fails rather than replacing it. Pass a new destination as its positional argument to run again. It stages images per camera, separates masks, applies the rig before sequential matching and fixes calibration during mapping. This is a preparation workflow awaiting real reconstruction validation, not a reconstruction-quality guarantee.

## Results and errors

`manifest.json` schema 2 contains the settings, source/run identity, actual write counts and state (`running`, `completed`, `failed`, `cancelled`). `images.jsonl` indexes confirmed images and optional masks by source frame and camera. Frames start at index 0; filters may leave gaps or incomplete sets of views.

Seconds sampling uses decoder timestamps, with an identified FPS fallback when unavailable. Frame sampling uses `max(1, int(interval_value))`; use an integer JSON value for exact stepping. CLI progress/ETA is an estimate based on decoder information and does not prove that GPS was recovered.

| Exit | Meaning |
| :--- | :--- |
| `0` | Processing ended without a job failure; inspect counts and telemetry status for suitability. |
| `1` | Input/config-loading error, output preparation error, malformed camera-list text or job failure. |
| `2` | Argument-parser error or shared settings-validation failure. |
| `130` | Keyboard interruption handled by the CLI. |

Configuration validation precedes model loading and image writes, but the CLI can create the parent output folder earlier. Image/mask pairs are staged before publication; a power cut can still leave partial state. Do not treat a `running` manifest from an interrupted process as complete. Automatic resume is not implemented.

For a repeatable manual check, use the [acceptance protocol](CLI_TESTING_PROTOCOL.md). Current qualification limits are tracked in the [implementation status](implementation-2026-09-07/PROGRESSION.md).
