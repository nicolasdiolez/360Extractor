# Changelog

All notable changes to 360 Extractor Pro will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
