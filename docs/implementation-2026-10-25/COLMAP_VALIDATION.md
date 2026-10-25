# COLMAP correction qualification — 2026-10-25

Local candidate **4.0.3**, branch `codex/fix-colmap-mask-reconstruction`, based on
`f3fcad319397d22fb8b192e3da72da4d42d575cb`. The existing 4.0.2 tag and draft assets
were not replaced. This report records a local macOS build, not a published or
CI-built 4.0.3 release.

## Defect and correction

The 4.0.2 exported runner always passed `--ImageReader.mask_path`. On COLMAP 4.2,
an export without masks therefore imported zero images (`MASK_ERROR`), followed
by a rig configuration failure. The same images imported when this option was
omitted.

The runner now omits the option for an entirely unmasked export. For a mixed
export, it stages white keep-all PNG masks for unmasked views, using the common
dimensions of the existing export masks. Existing masks and source images are
preserved. Invalid or inconsistent mixed-mask dimensions fail before staging.
PNG generation uses the standard library; the exported runner still works with
isolated Python and does not require the application or Pillow to be installed.

## Source and packaging checks

- macOS 26.7.1 / arm64, Python 3.13; dependencies installed from
  `constraints/macos-arm64-py313.lock`, build tools from
  `packaging/requirements-build.txt`, in a temporary external-drive environment.
- Full suite: **312 passed, 20 subtests passed, no skips**. Targeted COLMAP suite:
  **58 passed, 15 subtests passed**.
- Ruff, whole-project mypy, critical-module checks with untyped bodies enabled,
  release consistency and `pip check`: passed.
- Installed-wheel smoke outside the checkout: passed.
- PyInstaller bundle built from an exact snapshot of the corrected tracked
  source files. ZIP created with `ditto`, extracted into a new directory, and
  that extracted executable used for the following tests.
- Frozen smoke: visible version/help, native-size flat PNG with exact pixels,
  standard model loading, CPU inference and valid mask: passed.
- GUI startup/QSS and normal exit with isolated preferences: passed. This is
  not a repeat of the complete Studio interaction acceptance matrix.

Artifact: `360-Extractor-macos-arm64-4.0.3.zip`, 312,321,815 bytes.

SHA-256: `8ae871d336c68c0d860f6781407a5fb92ee19b48632968d5e2e49f089d37c3d2`.

## Real-media reconstruction

The exact ZIP executable read a real stitched HEVC panorama, 7680×3840, 25 fps,
110 decoded frames, 4.4 seconds, with an operator visible. Cube resolution was
512, interval two seconds, PNG output: three accepted instants and six views
per instant. Each exported standalone runner was then executed using isolated
Python and the installed COLMAP 4.2.0, with a new workspace.

| Case | Exported masks | Staged masks | Registered images | Cameras / captures / rigs | 3D points | Mean reprojection error |
| --- | ---: | ---: | ---: | --- | ---: | ---: |
| No masks | 0 | 0 | 18 | 6 / 3 / 1 | 90 | 0.368323 px |
| AI on Down + nadir disc | 3 | 18 | 18 | 6 / 3 / 1 | 91 | 0.367270 px |
| AI on all views | 18 | 18 | 18 | 6 / 3 / 1 | 92 | 0.364444 px |

All three runs completed feature extraction, rig configuration, sequential
matching and mapping. Model files and database records were inspected, all 18
images were registered, and the reconstructed coordinates were finite. The
mixed case retained the three original masks byte for byte and supplied fifteen
512×512 all-white masks. A plot of all three sparse models was visually checked.

This validates the observed failure and reconstruction execution on this short
sample. Sparse models of 90–92 points do not establish dense reconstruction
quality, metric accuracy, broad camera compatibility or robustness across long
captures. Stitching software/camera provenance was not established.

## Additional real-media checks

- Rerun of the same Cube job: a new numbered folder, all prior dataset and
  reconstruction file hashes unchanged.
- Real flat HEVC clip: three native-resolution PNGs, valid index and manifest.
- Real photograph: exported PNG exactly equal to the decoded JPEG pixels.
- Real vertical rafting clip: three images/masks on CPU and three on Apple MPS;
  the log confirms MPS inference. This checks operation, not segmentation recall.
- SIGINT during a longer real video: exit 130, cancelled manifest and three
  confirmed output images.
- No media originals were altered. User preferences remained unchanged.

## Release limits and retained evidence

The specific COLMAP blocker is resolved in this locally built candidate. The
bundle passes deep/strict ad-hoc signature verification, but Gatekeeper still
rejects it. Developer ID signing/notarization and clean-machine acceptance remain
open. Windows was neither rebuilt nor executed in this session; the user asked
to limit physical-machine qualification to macOS. No new remote tag, GitHub
release or public binary was created.

The local evidence folder `colmap-fix-4.0.3-2026-10-25` contains the ZIP, artifact
and model checksums, source snapshot hashes/diff, dependency profile, test/build
logs, real-media commands, manifests/indexes, output hashes, COLMAP databases,
binary/text models, sample masks/images and the GUI capture. It is retained
outside the temporary build and test directories. Media paths and private
samples are intentionally not committed to the repository.
