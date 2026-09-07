# Changelog

Versioned entries describe their historical candidates/releases. Version 4.0.1 prepares the Studio feedback preview after a frozen-launcher failure in the unpublished 4.0.0 draft. Availability and qualification are described on the corresponding GitHub release.

## [Unreleased]

No changes recorded after the 4.0.1 candidate.

## [4.0.1] - 2026-09-07

Feedback preview containing the Studio changes described in 4.0.0 below.

### Fixed

- Exclude the obsolete pkg_resources namespace from the frozen bundle and pin the build tools while retaining setuptools 84.0.0 and the dependency security floors. The original 4.0.0 macOS draft binary failed in PyInstaller's legacy runtime hook before application startup with a missing NullProvider attribute; that draft was not published.
- Provide null console streams in windowed executables so CLI dependencies can operate on Windows without an attached console.

### Added

- Run the actual frozen executable after every macOS/Windows build: launcher, short flat extraction, completed manifest, native image dimensions and exact PNG pixels. Source tests alone had not detected the startup failure.

### Known limitations

- An intermittent Windows Studio native crash (0xC0000005) was reproduced during the first extraction in post-merge CI, while other stress runs passed on the same code. Its cause is unknown and this packaging correction does not claim to fix it. Windows remains experimental in this preview.
- The real-camera, GPU, clean-machine, segmentation and reconstruction qualification limits listed for 4.0.0 remain applicable.

## [4.0.0] - 2026-09-07

360 Extractor Studio introduces the new three-column interface and the reliability corrections from the September audit. Existing CLI entry points remain available; Python imports move to the extractor360 package. A short manual test by the maintainer was positive. The narrower qualification limits below remain applicable.

### Changed

- **Breaking import change:** move the former top-level core/ui/utils packages into `extractor360`. The development launcher `python src/main.py`, console command `360extractor` and `python -m extractor360` remain available.
- Rename the distribution to `360-extractor`; keep the application name 360 Extractor.
- Keep the processing core Qt-free. Studio runs it through a ProcessingController/ProcessingThread (QThread) and bridges callback events to Qt. The CLI runs synchronously and imports AI only on demand.
- Introduce Studio's three-column interface, expandable advanced controls and app icon; preserve per-job edits, persistent defaults, naming, quality and active-view selections. Presets remain starting points, not certified reconstruction profiles.
- Calculate preview projections at export resolution before display reduction, use real AI/nadir overlays and retain timeline scrubbing. Automatic playback is not implemented.
- Give each extraction a new source-specific run folder. Add shared settings/naming validation, checked image/mask writes, a confirmed image index and schema-2 state/provenance manifests. Automatic resume is not implemented.
- Sample seconds using decoder timestamps with an identified FPS fallback; tile projection work and use bounded preview/thumbnail pools and small AI batches.

### Fixed

- Restore Studio extraction, card state/progress updates, reruns, cancellation and deferred shutdown; add subprocess regression coverage for normal process exit.
- Report model loading/inference and output-writing failures instead of treating them as successful outputs. Match masks to original image dimensions and implement explicit smoothing of binary-mask edges.
- Keep blur history per view, remove forced acceptance of rejected views and update motion reference only after a successful write. AI skip remains per view.
- Correct CAMM type 5/6 layouts, GPMF GPS5 scales/fix handling and packet timing; support GPX 1.0/1.1 and SRT sidecars and bound telemetry subprocesses/interpolation.
- Stop presenting filesystem mtime as capture time or GPS travel direction as optical heading. Omit unknown/relative EXIF altitude. Capture timestamps are conditional on available container metadata.
- Package the Qt stylesheet in wheels and include the reconstruction runner in the PyInstaller data.

### Added

- Calibration EXIF for virtual 360 views, with focal length derived from projection FOV and stable camera labels. GPS is optional; orientation is not inferred from travel direction.
- COLMAP calibration and rig exports: cameras.txt, rig_rotations.json, rig_config.json, reconstruct.py, a shell wrapper and instructions. The runner stages per-camera images/separate masks, applies rig_configurator before sequential matching and fixes calibration during mapping. Real reconstruction qualification is pending.
- Explicit trust for custom .pt models and a stable weight cache with application-specific Ultralytics settings.
- Security constraints and a hashed macOS arm64/Python 3.13 dependency resolution, qualified in a separate environment. Existing user environments are not automatically upgraded.
- Core CI on Ubuntu/macOS/Windows, dedicated Qt jobs on macOS/Windows, blocking critical-interface typing and version/changelog checks. A Tests (pytest) aggregate preserves the status required by main and only passes when every core/Studio matrix job succeeds.
- A release workflow that validates/tests dependencies, builds macOS/Windows apps and creates a draft release. It refuses to overwrite already published assets. Downloaded binaries still require clean-machine qualification before publication.
- Consolidated CLI/settings/contributor guides, acceptance protocol and current roadmap, with older audits identified as historical evidence.

### Qualification remaining

Real camera/codec/GPS corpora, segmentation accuracy, COLMAP reconstruction, Windows/GPU profiles, clean-machine binaries and complete distribution notices remain open. GPS9, IMU orientation, native stitching, HDR/ICC/alpha workflows and project/resume support are not claimed as implemented. See the [implementation follow-up](docs/implementation-2026-09-07/PROGRESSION.md) for evidence and all eight workstreams.

## [3.3.0] - 2026-07-13

Performance & comfort release (audit sprint "v3.3"). Faster extraction, a
smoother UI, and two new masking/quality-of-life features.

### Added
- **Nadir disc mask (no AI)**: mask the pole/tripod at the bottom of a capture
  with a configurable disc on the `Down` face (Cube layout). Works standalone
  and combines with the AI mask when both are enabled. GUI toggle + radius in
  the AI section; CLI `--nadir-mask` / `--nadir-radius`.
- **Selectable segmentation model**: choose the YOLO size (`n`/`s`/`m`/`l`/`x`)
  or a custom `.pt` — larger models catch partial operators (arm, pole) that
  nano misses. GUI dropdown; CLI `--ai-model`. Non-nano weights are
  auto-downloaded on first use.
- **Per-job `manifest.json`**: each output folder now gets a manifest recording
  the settings used and how many frames/views were extracted or skipped (blur,
  motion, AI) plus timing — for reproducibility and support ("why only N
  images?").
- **"Open output folder"**: a button on each finished queue card and in the
  batch-completion dialog opens the results in the file browser.
- **Pre-launch estimate**: the action bar shows an approximate count and disk
  size (e.g. "~840 images (140 frames × 6 views), ~2.1 GB") so large exports are
  never a surprise.
- **Tests**: EXIF write round-trip for JPEG/PNG/TIFF (incl. negative altitude
  and lossless-pixel checks), plus CLI coverage for the new flags.

### Changed
- **Faster frame decoding**: skipped frames now use `cap.grab()` (decode only)
  instead of `cap.read()` (decode + color-convert + copy) — a large speed-up at
  long extraction intervals on high-resolution video.
- **Faster reprojection**: reprojection maps are converted to fixed-point
  (`CV_16SC2`) once, which makes `cv2.remap` markedly faster with no visible
  quality change (verified bit-identical for linear/lanczos).
- **Single-write EXIF**: geotagged images are now written once — the JPEG EXIF
  is inserted into the in-memory encoded bytes (no recompression), and PNG/TIFF
  are written straight from the array — instead of the previous
  write-then-reload-then-rewrite round-trip.
- **AI model loads in the worker thread**: clicking "Start Processing" no longer
  freezes the UI while YOLO loads (or downloads on first run); a "Loading AI
  model…" status is shown instead.
- **Preview debounce**: dragging a spinbox now coalesces into a single preview
  render after a short pause, and a generation guard prevents a stale preview
  from overwriting a newer one.

### Fixed
- **Blur analysis respects layout and flat media**: "Analyze Selected Video"
  now uses the job's actual layout (Cube/Fibonacci frame very differently from
  Ring) and skips reprojection for flat/non-360 media, so the recommended
  threshold is meaningful. Its default resolution was aligned with the export
  default (2048) so the score scale matches what is written.

## [3.2.1] - 2026-07-13

Bugfix release from a full application audit.

### Fixed
- **CLI exit code now reflects job failures**: the CLI previously always exited
  with code `0`, even when some (or all) jobs failed, so batch automation could
  not detect errors. It now exits `1` and logs how many jobs failed.
- **"Null Island" GPS samples rejected**: several devices (e.g. GoPro before
  satellite lock) emit `(0,0)` GPS samples when they have no fix. These passed
  range validation and could geotag output images in the Gulf of Guinea. The
  shared sanitizer now drops the exact `(0,0)` placeholder for all telemetry
  sources (GPMF/CAMM/SRT/GPX); legitimate equator or prime-meridian crossings
  (lat=0 *or* lon=0 alone) are still kept.
- **`--format` accepts `tiff`**: the GUI and the processor already supported
  TIFF output, but the CLI rejected it.
- **Frame interval rounding**: the seconds-based interval was truncated instead
  of rounded (e.g. 29.97 fps × 1s → every 29 frames), causing a slow drift.
- **Per-face masking + flat media**: combining `--ai-mask-cameras` (or the
  face checkboxes) with flat/non-360 media silently disabled AI masking (the
  single "flat" view never matches a face name). The face filter is now
  ignored in flat mode with an explicit warning, and masking applies to the
  whole frame as requested.
- **Version single-sourced**: `pyproject.toml` was stuck at `3.1.0` while the
  app reported `3.2.0` (same class of bug as issue #7). The version is now read
  dynamically from `core/version.py`, so it can no longer diverge.
- **Actionable error when FFmpeg is missing**: telemetry extraction requires
  the system `ffmpeg`/`ffprobe` binaries; a missing install now produces a
  clear "install FFmpeg" message instead of a generic error.

### Added
- **`--version` CLI flag.**
- **Tests** for the GPS sample sanitizer (`tests/test_telemetry.py`).

### Removed
- Dead `get_arg()` helper in `main.py` (superseded by `build_settings()` in
  3.1.1).

### Docs
- **README**: documented the FFmpeg prerequisite (installation commands per OS).
- **`docs/CLI.md`**: fixed the stale `--motion-threshold` default (`0.5`, not
  `5.0`) and its range description, documented `tiff` in `--format`, added
  `--version`.
- **`docs/SETTINGS.md`**: `output_format` now documents `tiff`.

### CI
- CI now also runs on pushes to `dev` (previously only `main` and pull
  requests), so work-in-progress on the development branch is validated
  before a PR exists.
- The test job installs `piexif`/`Pillow` so `core.telemetry` is importable
  by the new telemetry tests.

## [3.2.0] - 2026-06-27

### Added
- **Per-face AI masking scope** (issue #14): AI masking can now be restricted to
  a subset of cubemap faces instead of being applied to every view. This avoids
  YOLO masking people in paintings/posters on the walls when you only need to
  remove the operator (e.g. on the `Down` or `Back` face). New setting
  `ai_mask_cameras` (list of face names; empty = all faces, the previous
  behavior). Exposed in the GUI as face checkboxes under "AI Processing" (Cube
  layout), and on the CLI via `--ai-mask-cameras "Down,Back"`. Inference only
  runs on the selected faces, so unselected faces are also a little cheaper.

## [3.1.1] - 2026-06-17

### Fixed
- **CLI config keys silently dropped**: the CLI hand-built the settings dict it
  passed to the processor and omitted several keys (`blur_threshold`,
  `interpolation_mode`, `ai_confidence`, `ai_invert_mask`, `feather_mask`,
  `sharpening_strength`) and misread others (`interval_value`/`interval_unit`
  were read from the wrong key and the unit forced to `Seconds`; `output_format`
  was read as `format`). As a result, e.g. `blur_threshold` from the config was
  ignored and the processor's hard-coded default of `100.0` was always used.
  CLI settings are now seeded from `SettingsManager.DEFAULT_SETTINGS` and merged
  as defaults < config file < CLI args, so every key flows through. Older configs
  using `interval`/`format` are still accepted as aliases.
- **`quality` missing from defaults**: `quality` was read by the processor but
  absent from `DEFAULT_SETTINGS`; it is now defined there (`95`).

### Added
- **`build_settings()`** in `core.settings_manager`, a unit-testable function for
  the defaults/config/CLI merge used by CLI mode.
- **Tests** (`tests/test_cli_settings.py`), including a regression guard that
  asserts every key the processor reads via `settings.get(...)` is present in the
  assembled settings dict.

### Docs
- **`docs/SETTINGS.md`**: corrected the example config (which used non-functional
  `interval`/`format`/`ai_mask`/`adaptive` keys), added a complete key reference
  table generated from the defaults, and fixed the adaptive Motion Threshold
  default (`0.5`, not `5.0`).

## [3.1.0] - 2026-06-09

### Added
- **DJI Altitude in EXIF**: GPS altitude is now extracted from DJI SRT telemetry. DJI clips (incl. Avata 360) pack altitude as `[rel_alt: … abs_alt: …]` rather than a plain `[altitude:]` field, which previously caused all EXIF altitudes to be written as `0`.
- **Altitude Source Selection**: New `Altitude Source` setting (GUI dropdown under Telemetry, `--altitude-mode {absolute,relative}` in the CLI, `altitude_mode` in JSON config). `absolute` (above sea level, default) is recommended for RealityScan/COLMAP geo-referencing; `relative` is height above takeoff. Falls back gracefully when only one altitude is present.

### Fixed
- **Negative EXIF Altitude**: `embed_exif` now writes the unsigned `GPSAltitude` rational with the correct `GPSAltitudeRef` (0 = above / 1 = below sea level) instead of producing an invalid negative rational for below-sea-level altitudes.

## [3.0.0] - 2026-05-29

### Added
- **Non-360 (Flat) Media Support**: New "360° Input" toggle in the GUI (and `--flat` flag in the CLI) lets you process standard video and images without equirectangular reprojection. Blur filtering, AI masking, sharpening, telemetry and naming all still apply. When disabled, the 360-only controls (FOV, virtual cameras, layout, inclination) are turned off.
- **CLI Image Inputs**: Directory scans now also pick up image files (`.jpg`, `.jpeg`, `.png`, `.tiff`, `.tif`) in addition to video.
- **Packaging (`pyproject.toml`)**: Standardized project metadata, dependencies, a `360extractor` console entry point, and `ruff`/`mypy`/`pytest` configuration. Optional extras: `[gpu]` and `[dev]`.
- **Continuous Integration**: GitHub Actions workflow running `ruff` (blocking, real-bug rules) and the test suite on every push/PR, plus informational full-lint and `mypy` reports.
- **Tests**: Added unit tests for the SRT and CAMM telemetry parsers (`tests/test_parsers.py`).

### Dependencies
- **Declared `Pillow`**: `Pillow` (used by the EXIF writer for PNG/TIFF) was a runtime dependency that was previously undeclared; it is now in `requirements.txt`/`pyproject.toml`.

### Fixed
- **Video Handle Leak**: `process_video` now wraps processing in `try/finally`, guaranteeing the `cv2.VideoCapture` handle is released even if an exception occurs mid-processing (previously the file could remain locked).
- **Window Close During Processing**: `closeEvent` now stops running workers and waits for their `QThread`s, preventing "QThread destroyed while running" crashes and orphaned threads.
- **Misleading Completion Dialog**: A failed job no longer aborts the whole batch and no longer triggers a false "Success" dialog. The final message is now conditional (success / completed with N errors / cancelled), failing jobs are marked "Error", and a new `job_error` signal reports per-job failures.
- **GPS Data Validation**: GPS samples from all sources (GPMF/CAMM/SRT/GPX) are now validated (NaN/Inf and out-of-range coordinates dropped) and sorted by timestamp, fixing potentially corrupt EXIF GPS and incorrect time lookups.
- **Preview vs Export Mismatch**: The live preview now uses the selected layout mode (Ring/Cube/Fibonacci) instead of always defaulting to Ring.
- **UX Settings Sync Trap**: Toggling settings in the UI now always targets the active job because the newly added/dropped job card in the queue is automatically selected.
- **Card Settings Summary**: Job cards in the queue now explicitly display the `[Flat]` and `[AI Mask]` / `[AI Skip]` statuses to prevent any confusion about what settings are currently active on each job.


### Changed
- **Path Safety**: Custom output filename patterns are confined to the destination folder via `os.path.basename`, preventing path traversal.
- **Unified Default Layout**: `layout_mode` now defaults consistently to `ring` (`adaptive` kept as a legacy alias).
- **Logging**: Processing errors are logged with full tracebacks via the logger (`exc_info=True`) instead of `print`/`traceback.print_exc`; remaining `print()` calls in `SettingsManager` and `VideoCard` now use the logger.
- **Code Cleanup**: Removed duplicated mask-building logic in `ai_model.py` (now a shared `_build_mask`/`_empty_mask` helper), and removed unused imports and dead local variables across the codebase.

## [2.5.2] - 2026-05-25

### Added
- **Automated GPU Setup Script**: Introduced `setup_cuda.py`, a cross-platform helper to guide users through installing PyTorch and torchvision with full CUDA support.

### Fixed
- **PyTorch CUDA Downgrade**: Resolved dependency resolution conflicts where installing `requirements.txt` implicitly pulled `torchvision` from standard PyPI and uninstalled/downgraded the custom CUDA-compatible PyTorch installation.
- **Environment Diagnostics**: Updated `check_env.py` to recommend installing both `torch` and `torchvision` together from PyTorch's custom CUDA wheels index.

## [2.5.1] - 2026-05-19

### Added
- **PyTorch & GPU Diagnostics**: Added comprehensive environment verification for PyTorch version, MPS (Apple Silicon), and CUDA (NVIDIA) support inside `check_env.py`.
- **NVIDIA GPU Installation Guide**: Scinded standard installation instructions and introduced a specialized step-by-step path to enable GPU acceleration under Windows/Linux inside `README.md`.

### Fixed
- **PyTorch Import Shadowing**: Resolved circular import issues caused by local test script naming (`torch.py`) shadowing the official `torch` package.

## [2.5.0] - 2026-04-02

### Added
- **Native 360° Image Support**: Added support for static panoramic images (.jpg, .png, .tiff, etc.), allowing users to run single frames through the exact same reprojection and AI masking pipeline as videos.
- **High-Quality (Lanczos) Interpolation**: New optional reprojection mode available in Settings, using `cv2.INTER_LANCZOS4` for sharper textures in photogrammetry.
- **Native AI Softness**: Upgraded segmentation mask pipeline to use YOLO26 raw probability tensors instead of polygon-filling.
- **Soft Mask Toggle**: Users can now choose between "Hard Edged" (crisp/high-precision) and "Native Softness" (professional alpha blending) in AI settings.
- **Premium Design System**: Complete visual redesign (`v3.0`) using HSL-harmonized colors, glassmorphism effects, and professional branding.
- **Adaptive Preview**: Redesigned `PreviewWidget` with dynamic aspect ratio and high-resolution rendering (1024px) for crisp image quality.
- **Responsive Layout**: Implemented auto-scaling previews and improved pane management for a better workflow on large screens.
- **Empty States**: Added graphical empty state illustrations for better user feedback when no video is selected.
- **Logo & Branding**: New refined logo section in the sidebar with a cleaner standard look.

### Fixed
- **Threading Stability**: Resolved a `RuntimeError` when submitting save tasks after worker shutdown (e.g., on job cancellation).
- **Mask Feathering Refinement**: Improved the localized softness calculation to avoid "hazy" subject rendering.
- **Bootstrap Bug**: Resolved a critical `AttributeError` in `VideoCard` during concurrent job addition.
- **Font Optimization**: Fixed the "Inter" font populating delay by providing a robust system-native font stack.

## [2.4.1] - 2026-04-02

### Changed
- **Mask Refinement**: Mask dilation kernel size is now dynamic and proportional to output resolution (`max(3, image_width * 0.005)`), fixing halo and over-masking issues across different export resolutions.
- **CLI Interface**: Exposed YOLO object targeting via CLI arguments (`--targets humans,vehicles,plants`, `--custom-classes`) replacing the need for config files in headless environments.

## [2.4.0] - 2026-03-31

### Added
- **Dynamic AI Targets**: Added the ability to target specific object classes (Humans, Vehicles, Plants) or enter custom class queries from the 80 available COCO categories using YOLO.
- **AI Confidence Tuning**: Added a UI slider to dynamically regulate the YOLO inference confidence limit.
- **Mask Inversion**: Added a toggle switch in the UI and backend logic to invert the binary mask generation.

## [2.3.1] - 2026-02-26

### Fixed
- **Version Display Mismatch**: GUI sidebar was showing a hardcoded `v2.1.1` instead of the current version. The sidebar now dynamically imports from `core.version`, preventing future drift.
- **Version Constant**: Updated `core/version.py` which was still set to `2.2.2` after the v2.3.0 release.

## [2.3.0] - 2026-02-19

### Changed
- **Performance (AI Batching)**: Dramatically improved inference speeds by batch processing all camera views simultaneously.
- **Performance (I/O)**: Implemented `ThreadPoolExecutor` for asynchronous image and mask saving.
- **Security**: Mitigated potential XML vulnerabilities (XXE/Billion Laughs) in the GPX parser by migrating to `defusedxml`.

## [2.2.2] - 2026-02-11

### Fixed
- **Windows Encoding Fix**: Resolved `UnicodeDecodeError` on non-UTF-8 systems (e.g., Chinese Windows) by enforcing UTF-8 decoding for FFmpeg/probe output.
- **GPU Debugging**: Added detailed PyTorch and CUDA version logging to assist in diagnosing "No GPU detected" issues.

## [2.2.1] - 2026-02-11

### Fixed
- **Critical AI Loading Fix**: Resolved `Segment26` class error by upgrading Ultralytics core to `8.4.14+`.
- **Mask Refinement**: Added morphological dilation to prevent "halos" around masked subjects.
- **Legacy Cleanup**: Removed fallback logic for deprecated YOLOv8 models.

## [2.2.0] - 2026-01-27

### Changed
- **AI Model Upgrade** - Migrated from YOLO11 to **YOLO26** (Feb 2026).
- **NMS-Free Architecture** - Implemented end-to-end inference for deterministic latency.
- **Performance** - +43% CPU inference speed upgrade.
- Updated `ultralytics` dependency to `8.4.0+`.

## [2.1.1] - 2026-01-20

### Added
- **Documentation Restructuring** - Modular documentation in `docs/` directory for better readability
- **Log panel** - Collapsible panel with color-coded log levels (INFO, WARNING, ERROR)
- **Keyboard shortcuts** - Del (remove), Ctrl+O (open), Space (preview), Ctrl+Return (start), Escape (cancel)
- **Multi-selection** - Ctrl+click to select multiple videos in queue
- **GPU detection** - Warning displayed when running on CPU without GPU acceleration
- **CHANGELOG.md** - Version history tracking

### Changed
- Improved thread cleanup in video card thumbnail loading

## [2.0.0] - 2026-01-05

### Added
- **Modern UI with sidebar navigation** - Complete redesign with Videos, Settings, Export, and Advanced pages
- **Video cards** - Visual queue with thumbnails, status indicators, and progress bars
- **Toggle switches** - Animated modern toggles replacing checkboxes
- **Collapsible sections** - Organized settings with smooth animations
- **GPX sidecar support** - Auto-detect `.gpx` files for cameras like Kandao Qoocam 3 Ultra
- **Flexible file naming** - RealityScan, Simple suffix, or custom patterns with placeholders
- **Unit tests** - 20 tests covering geometry, parsers, and core functionality

### Changed
- Settings panel reorganized into collapsible sections
- Dark theme with electric blue accent color
- Improved drop zone styling

### Fixed
- Thread cleanup for video thumbnails
- Font warnings on non-macOS systems
- Error handling in file manager

## [1.1.0] - 2026-01-05

### Added
- Flexible naming system with pattern placeholders
- GPX sidecar file support for Qoocam cameras
- Smart blur mode with adaptive threshold

### Changed
- Improved blur detection algorithm
- Better GPS interpolation

## [1.0.0] - Initial Release

### Added
- 360° to rectilinear reprojection
- Multiple camera layouts: Ring, Cube, Fibonacci
- AI operator removal with YOLOv8
- GPS/IMU metadata extraction (GPMF, CAMM, SRT)
- Blur filter with configurable threshold
- Adaptive interval with optical flow
- Batch processing queue
- CLI mode with tqdm progress bar
