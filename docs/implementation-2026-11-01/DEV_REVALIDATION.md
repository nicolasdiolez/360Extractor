# Staircase revalidation with the merged capture-plan implementation

Executed on 2026-11-01 from `dev` commit **`3bba6bec552cbf1059ad32c22dfec45d21e79141`** (PR #29). The controlled densification preserves the original images and masks on real footage. The new 31-capture export again enables Postshot training where the new 16-capture control fails. RealityScan remains fragmented. This is a second paired observation, not a repeatability or final-asset qualification.

## Inputs and controls

Four independent application-worker extractions used the normal `capture_plan` implementation: baseline/densified for RealityScan and Postshot. They did not reuse the pilot's exported pixels or use a diagnostic-frame override. Source decoding used macOS arm64, Python 3.13.17, OpenCV 4.12.0 and NumPy 2.2.6, matching the pilot environment.

The same source frames 0–82 (0–3.28 seconds), original 16 indices and 15 inserted midpoint indices were retained. Controls were Cube/six views, FOV 90°, 1024 px, JPEG 95, binary 40% Down nadir mask, EXIF intrinsics enabled, no AI, rejection filters, sharpening or telemetry. Destination mask profiles differed only as required by their contracts.

- Each arm confirms 96/186 JPEGs and 16/31 masks with no failed writes.
- **All 96 common JPEGs and 16 common masks have identical SHA-256 hashes within each consumer pair.** Decoded timestamps and comparison signatures also match.
- Every newly generated image and mask, including the 15 added captures, is byte-identical to its historical counterpart. The source SHA-256 is unchanged before/after extraction.
- JPEGs are identical across consumer profiles; their masks have exactly complementary polarity. Archive and transported-file hashes were verified on Windows.

The checked-in [staircase configuration](staircase-capture-plan.json) previously disabled EXIF intrinsics. This revalidation used the original manifests, which enabled them. The example is now corrected to `exif_intrinsics: true`; this changes the example, not the application defaults.

## Fresh consumer results

Consumers ran sequentially on the same Shadow Windows machine, RTX A4500. Versions remain RealityScan **2.2.0.119430.RS** and Postshot **1.1.69 (2026-08-18)**. [Compact measurements](dev-revalidation-results.json) distinguish this run from the [earlier pilot](SAMPLING_COMPARISON.md).

| Measurement | 16 captures | 31 captures |
| :--- | ---: | ---: |
| RealityScan components | 12 | 12 |
| Largest component: registered views | 8/96 | 58/186 |
| Largest component: physical captures | 8/16 | 31/31 |
| Directions in that component | Left: 8 | Left: 31; Back: 11; Up: 7; Down: 5; Front: 4 |
| Median / mean reprojection error, px | 0.650 / 0.733 | 0.748 / 0.804 |
| Alignment time | 99 s | 85 s |
| Preview triangles | 4,060 | 17,522 |
| Postshot accepted views | Failure; 2/96 partial registrations | 118/186 (63.4%) |
| Initial sparse points | 52 | 4,830 |
| Tracking time from log | 12.413 s | 134.419 s |
| Training | Not started | 5,000 steps, 64.621 s |
| Saved project size | 75,447 bytes | 397,869,403 bytes |

RealityScan imported the same historical global settings before each case. Its imported input nodes and their order exactly match the pilot. The eleven alignment settings exported from all four components agree: High, 10,000 features/Mpx, 80,000/image, Ultra sensitivity, 40,000 preselected features, downscale 1, 2 px maximum error, camera-position setting enabled, Brown3 and final optimization enabled. Binary global-config exports differ; these files are not treated as proof of a parameter difference or of complete configuration identity.

Postshot used All Images, Compute From Images, High/3, explicit Remove Occluders masks, Splat3, 3840 px cap, 3 M maximum splats, anti-aliasing on, photometric compensation off and 5 kSteps. Adding mask files resets its displayed step limit to 30 kSteps; the limit was restored to 5 kSteps and checked after mask association in both imports. The dense project reopened with 118 imported/selected/tracked views. Inspected camera views show recognizable stairs, doors and railings, with soft surfaces, dark artifacts and smearing. These are training-camera inspection views, not held-out measurements.

## Limits and next work

The five unmatched-mask warnings recur on reopening, now for Down frames **5, 8, 11, 13 and 16** (the pilot warned for 0, 2, 5, 8 and 11). Their relationship to rejected views and actual per-pixel masking remains unqualified. Preserve these failures for a separate masked/unmasked test and a consumer-result importer; do not change mask policy within the sampling comparison.

RealityScan's largest components differ from the pilot's 17/31 views, despite identical input bytes, import order and reported alignment parameters. Postshot also changes from 121 to 118 accepted views. The cause is not isolated: there is no controlled random seed or cold/warm cache protocol. One new run per arm does not satisfy the benchmark's three-repetition gate. Do not attribute these differences to the capture-plan implementation or claim a speed improvement from these timings.

Imported/aligned/preview RealityScan projects and both Postshot projects are retained privately with their dependencies and logs. Automated common-camera preview rendering was blocked by Windows Defender; that command was not retried and protections were unchanged. No matched-view RealityScan image comparison or reference-geometry accuracy measurement is claimed. Postshot physical-capture/direction coverage still needs a reliable consumer export/import path; total registered views cannot substitute for it.

Keep FOV and diagnostic limits unchanged. Priorities remain consumer mask association/persistence validation, durable reconstruction reports with per-direction coverage and missing views, and controlled repeated quality measurements. This validates source extraction on macOS and these consumer runs on Windows; it does not qualify a downloadable binary, Windows extraction or CUDA inference.
