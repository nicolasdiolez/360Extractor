# 360 Extractor Pro

High-performance desktop application and command-line tool for 360° video and image preprocessing. This tool generates optimized datasets for Gaussian Splatting and photogrammetry (COLMAP, RealityScan) by converting equirectangular media into rectilinear pinhole views and removing operators using AI.

> **v2.5.2** - PyTorch CUDA environment fixes and premium UI/UX overhaul with adaptive preview resolution, glassmorphism theme, and **native 360° image support**.

## Key Features

- **360° to Rectilinear:** Reproject equirectangular video and images to pinhole views with configurable FOV and overlap.
- **Dual Interface:** Graphical UI for ease of use and CLI for automation.
- **Advanced Control:** Multiple layouts (Ring, Cube Map, Fibonacci), inclination settings, and selective camera extraction.
- **AI-Powered:** Automatic operator/object removal (supports 80 COCO classes like humans, vehicles, plants) with adjustable confidence, mask inversion, and intelligent motion-based keyframing.
- **Metadata Integration:** Extract GPS/IMU data (GoPro, Insta360, DJI) and embed into EXIF.
- **Quality Control:** Automatic blur detection, filtering, and optional **Lanczos interpolation** for maximum sharpness.
- **AI-Powered Masking:** Next-gen operator removal with **Native Softness** (probabilistic alpha blending) for seamless photogrammetry integration.

## Installation

1.  **Clone the repository**
2.  **Install dependencies:**
    - **For CPU-only or Mac (Apple Silicon):**
      ```bash
      pip install -r requirements.txt
      ```
    - **For NVIDIA GPU acceleration (Windows/Linux):**
      We provide an automated interactive setup helper that installs CUDA PyTorch and handles all dependency conflicts. Run:
      ```bash
      python setup_cuda.py
      ```

      *Or manually install by forcing both `torch` and `torchvision` together from the custom PyTorch index before installing requirements:*
      ```bash
      pip install torch torchvision --index-url https://download.pytorch.org/whl/cu124
      pip install -r requirements.txt
      ```
      > [!IMPORTANT]
      > You must install `torch` and `torchvision` **together** using the `--index-url`. If you install them separately or omit torchvision, `pip` will resolve torchvision from standard PyPI and silently downgrade your `torch` package to the CPU-only version.
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
