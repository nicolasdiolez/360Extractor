# 360 Extractor Pro

High-performance desktop application and command-line tool for 360° video preprocessing. This tool generates optimized datasets for Gaussian Splatting and photogrammetry (COLMAP, RealityScan) by converting equirectangular footage into rectilinear pinhole views and removing operators using AI.

> **v2.2.0** - YOLO26 integration (NMS-Free), +43% performance boost, and updated dependencies.

## Key Features

- **360° to Rectilinear:** Reproject equirectangular video to pinhole views with configurable FOV and overlap.
- **Dual Interface:** Graphical UI for ease of use and CLI for automation.
- **Advanced Control:** Multiple layouts (Ring, Cube Map, Fibonacci), inclination settings, and selective camera extraction.
- **AI-Powered:** Automatic operator removal and intelligent motion-based keyframing.
- **Metadata Integration:** Extract GPS/IMU data (GoPro, Insta360, DJI) and embed into EXIF.
- **Quality Control:** Automatic blur detection and filtering.

## Installation

1.  **Clone the repository**
2.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
3.  **Verify environment:**
    ```bash
    python3 check_env.py
    ```

## Quick Start

### GUI Mode
Launch the graphical interface for interactive processing:
```bash
python3 src/main.py
```

### CLI Mode
Process videos via command line for automation:
```bash
python3 src/main.py --input <video_path> --output <output_dir> --interval 1.0
```

## Documentation

For detailed information on configuration and usage, please refer to:

- 🖥️ **[GUI & Settings Guide](docs/SETTINGS.md)**: Detailed explanation of all processing parameters, layout modes, AI filters, and JSON configuration.
- ⌨️ **[CLI Reference](docs/CLI.md)**: Complete list of command-line arguments, flags, and automation examples.

## Author

**Nicolas Diolez**

## License

This project is licensed under the **GNU Affero General Public License v3.0 (AGPL-3.0)**.
Required by usage of YOLO26 (Ultralytics). See [LICENSE](LICENSE) for details.

## Credits

Special thanks to **Ultralytics** (YOLO26), **The Qt Company** (PySide6), and **OpenCV**.
