# Changelog

All notable changes to 360 Extractor Pro will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
