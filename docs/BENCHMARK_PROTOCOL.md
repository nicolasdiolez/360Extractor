# Reconstruction comparison protocol

Start with the existing qualification samples. The objective is to decide which preparation steps improve usable reconstructions, and to identify failures early enough to repair the input dataset.

## Corpus and controls

Use stable scene IDs, source SHA-256, camera/codec, dimensions, duration, decoded timestamps and the exact source/software versions. Read originals in place; keep generated data in one dated directory on a volume with sufficient space. Do not publish private paths or media without permission.

The initial outdoor clips are `360_cour.mp4` and `360_ArcLouvre.mp4`, both stitched 8K 2:1 panoramas already used in the project environment. Extend with Palais Royal, the staircase after confirming decoding, the existing flat video/photo fixtures, and an annotated museum scene with real people, painted people, tripod and stitching boundaries. A file named “360” is not proof of equirectangular projection: validate its geometry first. Two short outdoor clips cannot qualify indoor or object scans.

Freeze a shared candidate list of physical capture indices/timestamps. Compare:

1. Regular sampling with current virtual perspective cameras.
2. Current optical-flow selection at a recorded threshold.
3. Native equirectangular COLMAP on the same regular captures.
4. A future selection based on geometric overlap, trackability and blur, only after its proposal and rejection reasons are inspectable.
5. An independent end-to-end tool on the same corpus, when its target machine and license are available. Candidate tools from the product review include 360 Gaussian Pro and the LichtFeld 360 workflow; their advertised capabilities are not measured results.

Test mask policies separately from sampling: none, nadir only, Down-scoped AI, whole-scene AI and a manually reviewed reference. Keep intended static scene content, especially people in artwork. Record false removal of useful pixels, missed occluders and correction time, not just segmentation confidence. No generative filling in source observations.

## Small sparse pilot

With the repository's Python environment and a COLMAP build supporting `EQUIRECTANGULAR`:

```sh
df -h /System/Volumes/Data
PYTHONPATH=src python scripts/benchmark_sparse.py \
  --input /path/to/360_cour.mp4 \
  --output /path/to/dated-benchmark/cour \
  --captures 8 --resolution 512
```

The output must not exist. Run the second scene in another fresh subfolder. The script hashes the original, runs real application extraction for regular/adaptive cases, then samples the native panoramas at the regular case's exact frame indices. It records commands, timings, manifests, source metadata, software environment, all sparse models and physical capture counts. The source size/mtime is checked afterwards; this is not a second full content hash.

Pilot settings: six 512×512 Cube views at 90°, or 2048×1024 native panoramas; JPEG quality 95; no masks, sharpening or blur filter; adaptive threshold 0.5. COLMAP uses CPU SIFT with up to 8192 features per image, four threads, sequential overlap 10 without quadratic overlap, fixed calibration/rig, mapper seed 0 and minimum model size 3 for this small sample. The native pipeline is a benchmark path, not a new Studio export mode.

The pixel and feature budgets differ between representations: six faces contain 1.57 M pixels per capture, the native panorama 2.10 M. Per-image feature limits are not per-capture limits. Interpolation differs as well. Consequently this is an integration pilot, not an equal-budget quality or speed ranking. COLMAP's native spherical mode is documented as generally faster but less accurate than perspective rendering; measure rather than assume that holds for a particular scene. [COLMAP 4.1 release notes](https://colmap.github.io/changelog.html#colmap-4-1-0-06-26-2026).

Before larger runs, budget extraction, database, sparse/dense reconstruction, models and rendering together. The application's output guard excludes downstream COLMAP files. A 32-capture/1024-face run can be much larger than this eight-capture pilot.

## Measurements that decide the next feature

| Question | Evidence |
| :--- | :--- |
| Does the sequence align coherently? | Fraction of physical captures registered in the largest model; all components; missing spans; trajectory and reprojection inspection. Do not count six virtual views as six positions. |
| Is geometry better? | Fixed control distances or reference geometry, completeness and repeated surface errors. Sparse point count and residuals alone cannot establish accuracy. |
| Is a splat useful? | Fixed held-out real views, exposure policy and training budget; visual review plus PSNR/SSIM or perceptual metrics. Mask out dynamic regions by a predeclared policy. |
| Does selection save work? | Capture/image count, peak RAM/VRAM, unique allocated bytes, preparation/alignment/training time, and human repair time. |
| Are masks interoperable? | Pixel polarity, names, dimensions and a real import into each target application's exact version and mask mode. |
| Is it repeatable? | At least three repetitions with recorded seeds, machine state and cold/warm cache policy; retain failures. |

For the proper comparison, run both an equal pixel/feature budget experiment and the recommended settings for each consumer. Compare errors in a common geometry/angular system or against shared ground truth; raw reprojection pixels across different projections/resolutions are not directly comparable. Preserve camera/rig associations when matching and evaluating held-out captures.

## Decision gates

- Keep regular sampling as the baseline until a selector reduces input or repair time while preserving coverage and reconstruction quality across the annotated corpus. A smaller dataset alone is not success.
- Keep panorama-native output experimental until downstream consumers, masks, camera conventions and geometry are verified. Retain perspective export for interoperability.
- Build a small alignment diagnostic before a general reconstruction interface: report disconnected groups, failed captures and areas to revisit. Every proposed repair must map back to source indices and remain reversible.
- Stabilize a saved project model (sources, selection, mask edits, export contracts, results) before adding more independent settings. Resume requires source/settings verification and a validated output index, not merely finding an existing folder.
- Qualify Windows/CUDA and actual target applications separately from local macOS source tests. A passing source benchmark does not qualify a downloadable binary.

First results: [2026-10-27 validation](implementation-2026-10-27/VALIDATION.md).
