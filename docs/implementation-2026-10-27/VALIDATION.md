# Export contracts, storage and first comparison — 2026-10-27

Development branch: `codex/mask-profiles-storage-preflight`, based on `d4f942a`. Tests below exercise the changed source tree, not the public v4.0.3 binaries. No version, published tag or release asset was changed.

## Implemented behavior

- Studio and CLI expose mask profiles for RealityScan, COLMAP, Postshot Remove Occluders and custom/legacy behavior. The profile owns naming and polarity; the manifest records the convention. Old settings remain custom until a named profile is selected.
- The Postshot preset now writes white-ignore masks with `.mask.png` names, uses binary edges by default and disables the incompatible COLMAP mask export. Manual imports still need the correct target mask mode. Multi-selection tests verify that all selected jobs receive the contract while unrelated settings survive.
- The output volume is checked before creating the run/loading AI and before each capture is submitted for writing. The next-capture budget includes potential masks and a 256 MiB reserve. A simulated space drop preserves the previous confirmed capture and produces a failed manifest.
- Studio estimates now include masks, native flat dimensions and one capture per still image. Invalid/unknown video timing does not invent a 30 FPS estimate. The full-run compression range is advisory; model caches, external reconstructions and verified resume remain outside this guard.

## Local checks

Environment: macOS 26.7.1 arm64, Python 3.13.17, OpenCV 4.12.0, COLMAP 4.2.0 without GPU support. Reused the existing Python dependencies and model weights. Mypy 2.4.0 was installed only into the session's temporary validation directory.

| Check | Result |
| :--- | :--- |
| Full pytest suite, offscreen Qt | 330 passed, 20 subtests passed; no skips |
| Ruff | Passed |
| Whole-project mypy | Passed, 45 source files |
| Critical-body mypy plus both new core modules | Passed, 6 files |
| Release consistency and `git diff --check` | Passed; version remains 4.0.3 |
| Wheel installed outside checkout | Passed existing smoke: resources, CLI, flat pixels, Cube views, nadir mask and standalone reconstruction staging; both new modules import from the installed wheel |
| Studio render | Offscreen 1440×1000 inspected; profile label and output controls visible |
| Profile file contracts | Nine combinations: three profiles × JPEG/PNG/TIFF; actual names, dimensions, mask pixels, manifests and source preservation checked |

The wheel was built from an isolated small copy of the package sources and installed into a temporary environment sharing the existing system dependencies. This checks packaging/import behavior; it is not clean-machine dependency or frozen-binary qualification. The current OpenCV/NumPy stubs also required explicitly normalizing the optical-flow magnitude with `np.asarray` before taking its mean; motion regressions passed.

## Real mask export

Input: existing `360_cour.mp4`, 7680×3840, 110 frames at 25 FPS. Exported frames 0, 40 and 80 as six 512×512 Cube faces, JPEG quality 95, CPU YOLO26n segmentation scoped to Down plus a nadir disc. Ran once per profile:

| Profile | Confirmed images | Down masks | Ignored pixel value | Example filename |
| :--- | ---: | ---: | ---: | :--- |
| COLMAP | 18 | 3 | 0 | `360_cour_frame000000_Down.jpg.png` |
| Postshot | 18 | 3 | 255 | `360_cour_frame000000_Down.mask.png` |

For all three pairs, `postshot_mask == 255 - colmap_mask` at every pixel. Shapes were exactly 512×512. Ignored-pixel counts: 50,496; 34,025; 35,428. This verifies the written convention and combined AI/nadir pipeline. It does not measure whether every segmented pixel is semantically correct or certify an import/training run in Postshot. The chosen mode follows the [official Postshot contract](https://www.jawset.com/docs/d/Postshot%2BUser%2BGuide/Interface/Training%2BConfiguration).

## Sparse reconstruction pilot

Executed [benchmark_sparse.py](../../scripts/benchmark_sparse.py) under the [comparison protocol](../BENCHMARK_PROTOCOL.md). Two existing 8K/25 FPS outdoor clips; eight physical captures per clip. Regular and adaptive paths use six 512×512 views per capture. Native uses one 2048×1024 panorama per capture. No masks in these six runs, to isolate representation and sampling. Full metrics and source hashes: [benchmark-results.json](benchmark-results.json).

| Scene / method | Captures exported | Captures registered in largest model | Images in largest model | Sparse points in largest model | Models returned |
| :--- | ---: | ---: | ---: | ---: | ---: |
| Cour / regular | 8 | 8 | 48 | 2,298 | 1 |
| Cour / adaptive 0.5 | 8 | 8 | 48 | 2,271 | 1 |
| Cour / native | 8 | 8 | 8 | 1,838 | 1 |
| Louvre / regular | 8 | 8 | 48 | 347 | 2 |
| Louvre / adaptive 0.5 | 8 | 8 | 48 | 344 | 2 |
| Louvre / native | 8 | 8 | 8 | 553 | 1 |

The extra perspective model at the Louvre contains two captures already present in the largest model (35 points). It must not be counted as additional coverage or interpreted as eight positions split across two disconnected models.

Preparation/alignment times, one run only: Cour regular 6.1/10.8 s, adaptive 7.4/17.0 s, native 8.1/9.6 s; Louvre regular 20.5/7.7 s, adaptive 13.0/7.3 s, native 12.2/7.4 s. These timings include uncontrolled cache/machine effects and do not support a speed ranking.

The regular/adaptive JPEG files are byte-identical for each scene: the current adaptive filter removed **zero** captures at this threshold and sampling interval. Small differences in sparse points therefore reflect reconstruction variability, not better input selection. Mapper seed 0 does not eliminate all multithreaded nondeterminism.

Native panorama alignment is viable on both samples. It merits a controlled follow-up; it does not yet justify replacing perspective export. Pixel/feature budgets and interpolations differ, raw reprojection errors use different image geometry, there is no ground truth, and each case was run once. There was no dense reconstruction, held-out splat evaluation, reconstruction visual acceptance or competitor run. A count of registered images or sparse points is not a geometric quality score.

## Resulting direction and remaining gates

Keep the preparation layer as the product's core: saved projects, inspectable capture selection, correct consumer exports and local mask repairs. Extend the corpus and establish quality measurements before building a new selector. The next useful integration is a small alignment diagnostic that points to source captures requiring attention. Maintain native panorama as an experimental comparator alongside perspective views.

Still required: actual Postshot/RealityScan imports on supported target machines; museum/indoor masks with human reference labels; longer trajectories, repeated equal-budget trials, geometry and held-out splat evaluation; competitor testing; verified resume; Windows/CUDA and downloaded-binary qualification. No broad reconstruction-engine rewrite is justified by this pilot.

## Files and disk use

Session artifacts are grouped in the dated temporary directory `application360-direction-2026-10-27`: logs, tests, temporary typing/build environments, the Studio screenshot, real mask exports and both sparse comparisons. Originals were read in place; no source video/RAW was copied. Source size/mtime remained unchanged during the comparison; source hashes are recorded in the results.

The two comparison folders occupy approximately 0.088 GB and 0.054 GB counting allocated blocks once per inode, including hardlinked reconstruction images. This avoids counting the same image twice. The complete session inventory is provided separately; temporary outputs may be moved to Trash only after approval. Keep this report, the compact results, protocol and script in the repository.
