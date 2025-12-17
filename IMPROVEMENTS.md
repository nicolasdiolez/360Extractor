# 360 Extractor Improvements & Todo List

This document tracks planned improvements and known issues for 360 Extractor.

## High Priority

- [ ] **Improve CLI for Headless/Cloud Usage**
    - **Context:** GitHub issue report indicates a need for better CLI support for users running on cloud GPU servers (headless environments).
    - **Current State:** `src/main.py` only launches the GUI (`QApplication`). No argument parsing exists.
    - **Goal:** Implement `argparse` in `src/main.py` to allow running extraction jobs without opening the GUI.
    - **Requirements:**
        - Flags for input file/directory.
        - Flags for output directory.
        - Flags for extraction settings (interval, format, AI toggle).
        - Bypass `QApplication` execution if arguments are present.

- [ ] **Add "Selective Camera Direction"** (User Request)
    - **Context:** User wants to choose specific camera angles/directions (e.g., "Front 3 cameras only" or "Exclude rear cameras").
    - **Goal:** Add a UI/CLI mechanism to select active cameras from the N generated views.

- [ ] **Add Essential Technical Improvements**
    - **Robust Logging System:** Replace `print` statements with Python's `logging` module. Essential for debugging headless/cloud jobs where you can't see the GUI console.
    - **Configuration File Support (JSON/YAML):** Allow loading settings from a file. This is crucial for the CLI to avoid massive command strings (e.g., `--config job_settings.json`).
    - **CLI Progress Bar:** Implement `tqdm` or similar to show progress in the terminal since there will be no GUI progress bar.

## Future Ideas

- [ ] **Smart Masking (NeRF/Gaussian Splatting Prep)**
    - **Context:** Training NeRFs or Gaussian Splats requires clean static scenes. Moving objects (people, cars, leaves) cause artifacts ("floaters" or blurring). Current removal leaves holes; masking is preferred by advanced pipelines.
    - **Goal:** Elevate the AI module to export precise binary masks alongside images.
        - Option to mask *all* dynamic objects (classes: person, car, bicycle, etc.).
        - Ensure mask format is compatible with RealityCapture/Nerfstudio (e.g., Black=Subject, White=Background).
    - **Impact:** Significantly cleaner high-end 3D reconstructions with less manual cleanup work.

- [ ] **Intelligent Keyframing (Optical Flow)**
    - **Context:** Extracting frames at fixed time intervals (e.g., every 0.5s) is inefficient if the camera is stationary or moving slowly, creating redundant data that bloats datasets.
    - **Goal:** Implement an "Adaptive Interval" mode using optical flow analysis.
        - Calculate pixel motion between potential frames.
        - Only extract a frame if significant scene change/parallax is detected.
    - **Impact:** Maximizes dataset quality while minimizing size. Ensures every extracted frame contributes new geometric information.

- [ ] **GPS/IMU Metadata Integration**
    - **Context:** Many 360 cameras (GoPro Max, Insta360) record rich telemetry (GPS, gyroscope, accelerometer). Photogrammetry software often spends 50%+ of processing time just calculating camera positions ("Alignment").
    - **Goal:** Extract telemetry data (GPMF/CAMM) from source videos.
        - Embed rough pose/location data into extracted images (EXIF) or a sidecar file (`transforms.json`).
    - **Impact:** Provides "priors" to photogrammetry engines, drastically speeding up alignment and providing real-world scale/orientation automatically.