# RealityScan and Postshot pilots — 2026-10-28

Consolidated on 2026-11-01 from retained local evidence. This records existing trials; no reconstruction was rerun during consolidation. Application source commit: `5fec65ccfb52385ebebd5b5e0c7ea454e81e1ae2`, after PR #26, with [integrated CI](https://github.com/nicolasdiolez/360Extractor/actions/runs/40678698548) passing. No application code, default FOV, version, tag or release was changed by these trials.

## Setup and provenance

Inputs were prepared on macOS from original media in place. Consumers ran on Windows with an NVIDIA RTX A4500, 20,470 MiB VRAM and driver 595.97: **RealityScan 2.2** and **Postshot 1.0.1 (2025-09-26)**. These results apply to those installed versions; they do not qualify the 360 Extractor Windows binary or CUDA inference.

Each of the four baseline cases used 16 physical captures × six Cube views: 96 JPEG images, 1024 × 1024 pixels, quality 95, 90° FOV and 16 binary Down masks. Cour used local YOLO26n-seg person masking on Down plus the 40% nadir disc. Louvre and the two staircase windows used the same nadir disc without AI. Blur/motion filters and telemetry export were disabled. Louvre includes passers-by without lateral AI masking in this pilot.

Images were identical between the RealityScan/Postshot profiles; masks were exact binary complements. Source identities were checked unchanged and all four transferred archive hashes verified. Frame selections, source hashes and compact results are in [consumer-results.json](consumer-results.json).

The local evidence set is `plans/application360-consumers-2026-10-28/` (ignored by Git): `LISEZMOI.txt`, `preparation.json`, `status.json` and `fov-comparison.json`. The compact JSON records their SHA-256 fingerprints at consolidation. Consumer projects, linked inputs and raw logs remain privately retained. Private filesystem paths, cloud identifiers and media are deliberately excluded from this public summary. It is a transcription of recorded observations, not an independent remeasurement of the Windows artifacts.

## Baseline outcomes

RealityScan counts below describe the largest component. Postshot counts describe the recorded tracking outcome; the final staircase case has no confirmed final image count.

| Case | RealityScan components | Largest component: images / physical captures | Median reprojection error | Postshot tracked images | Postshot outcome |
| :--- | ---: | :--- | ---: | ---: | :--- |
| Cour | 1 | 91/96 images; 16/16 captures | 0.508263 px | 95/96 | Training reached 5,000 steps; project reopened and rendered. |
| Louvre | 6 | 26/96 images; 12/16 captures | 0.407206 px | 38/96 | Camera tracking aborted before training. |
| Staircase, beginning | 15 | 10/96 images; 9/16 captures | 0.608477 px | 3/96 | Camera tracking failed before training. |
| Staircase, end | 2 | 2/96 images; 2/16 captures | 0.589508 px | Unknown | Failed to create a sparse model; no training. |

Cour's RealityScan project was reopened and its untextured preview displayed: 74,990 triangles and 37,499 vertices, connected major wall surfaces, irregular relief and incomplete boundaries. This limited inspection did not accept a final textured asset or establish metric accuracy.

Postshot's CLI required a Studio license, so all consumer training pilots ran through its Free interface. Settings were Use All Images, Splat3, Remove Occluders and a 5 kStep limit. Cour reached about 1.79 million splats; two reviewed views showed coherent walls, doors, windows and rails, with a soft ground surface. The saved project reopened successfully. The three failing cases were saved separately. Mask presence and mode were checked, but no masked/unmasked ablation established their per-pixel consumer effect.

Cour is a positive integration reference. The other three results are not accepted complete-scene reconstructions. Six virtual faces still represent one physical capture; image counts and low residuals cannot establish complete coverage or faithful geometry. Success in a bounded COLMAP diagnostic is not a guarantee of success in another consumer, whose camera treatment and reconstruction settings differ.

## Paired FOV experiment

An additional trial on the beginning of the staircase changed FOV from 90° to 110°, keeping the same 16 source frames (0–82), six views, 1024 px, quality 95, nadir policy and consumer settings. Source identity and frame/camera/timestamp indexes were checked; masks were pixel-identical to the control, images identical across destination profiles and profile masks complementary. Focal EXIF was checked: 18 mm at 90°, approximately 12.604 mm at 110° (35 mm-equivalent integer rounded to 13).

| Measurement | 90° baseline | 110° trial |
| :--- | ---: | ---: |
| RealityScan components | 15 | 10 |
| Largest component images | 10/96 | 20/96 |
| Largest component physical captures | 9/16 | 7/16 |
| Largest component median reprojection error | 0.608477 px | 0.407314 px |
| Postshot tracked images | 3/96 | 2/96 |
| Postshot initial sparse points | 133 | 39 |
| Postshot training | Failed before training | Failed before training |

**Counting correction:** RealityScan's combined component report repeated the active component's camera list. Largest-component coverage was rechecked by explicitly selecting the maximal component before a separate camera report: 9 captures at 90°, 7 at 110°, with Louvre 12 and staircase end 2 reconfirmed. Coverage of unverified smaller components remains unknown. The 110° largest component covers frames 5, 11, 16, 22, 27, 33 and 38.

The extra registered faces and lower residual at 110° did not improve physical-capture coverage or rescue Postshot. This single paired pilot gives no basis for changing the default to 110° or claiming 90° is universally better. Changing FOV also changes angular detail and peripheral content; a pixel-identical nadir mask covers a different angular cone.

## Limits and next experiment

These are five pilots per consumer (four baseline cases and one FOV variant), without repeated runs or geometric ground truth. Failure causes remain unresolved: sampling/overlap, stitching, source quality, scene motion, resolution and engine settings are possible factors. No complete-scene quality, camera-family compatibility, mask accuracy, held-out splat quality or clean-machine distribution acceptance is established. Historical Windows native application crashes are not resolved by these consumer runs.

At consolidation, the next proposed experiment was: at 90°, interleave one source capture in each of the 15 gaps between the existing 16 beginning-of-staircase captures, for 31 total. Preserve endpoints, resolution, masks and consumer settings; record the exact added frames and decoded times. Compare largest-component capture fraction, temporal span and gaps, fragmentation, visual result, runtime and disk/memory cost against the existing control. Budget the expanded workspace separately; do not silently raise the product diagnostic's 16-capture limit. Keep Cour as a positive control.

Follow the [benchmark protocol](../BENCHMARK_PROTOCOL.md) for repetitions and quality measurements. The [active roadmap](../../IMPROVEMENTS.md) separates completed pilots, implemented features and remaining product/distribution work.

Follow-up: the [2026-11-01 paired sampling pilot](../implementation-2026-11-01/SAMPLING_COMPARISON.md) has now executed fresh 16/31-capture cases. It enabled Postshot training with the denser input while RealityScan remained fragmented. The dated results above are unchanged.
