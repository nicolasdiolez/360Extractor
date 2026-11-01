# Staircase sampling pilot — 16 versus 31 captures at 90°

Executed on 2026-11-01 from development commit `9b26c77cd8a49dd2b71c3eb288d5b54a70abd81e`. **Denser sampling unlocked Postshot training in this paired pilot; RealityScan still reconstructed disconnected fragments.** This does not qualify a complete staircase asset or justify changing extraction defaults.

Follow-up using the merged capture-plan implementation: [dev revalidation at `3bba6be`](DEV_REVALIDATION.md). The measurements below remain the original pilot results.

## Controlled inputs

Both cases cover source frames 0–82, or 0–3.28 seconds, from the same stitched 7680 × 3840, 25 fps staircase video. The 16 original captures are retained byte for byte. The 31-capture case adds the floor midpoint of each of the 15 original gaps: frames 2, 8, 13, 19, 24, 30, 35, 41, 46, 52, 57, 63, 68, 74 and 79. Decoded timestamps were recorded; the maximum gap decreases from 0.24 to 0.12 seconds.

Unchanged settings: six Cube faces, 90° FOV, 1024 × 1024 JPEG quality 95, binary 40% Down nadir mask, no AI, blur/motion filtering, sharpening or telemetry. There are 96 versus 186 images and 16 versus 31 masks. Images are identical across consumer profiles, masks have complementary polarity, and the source hash is unchanged. The additional captures were extracted through the application worker; Studio's diagnostic limit remains 16.

Inputs and transferred archive hashes were checked. Measurements, frame lists, versions and settings are in [sampling-results.json](sampling-results.json). Media and native projects remain in the private qualification workspace, outside Git.

## Fresh paired results

Consumers ran sequentially on Shadow Windows build 26200, RTX A4500, driver 595.97. RealityScan was **2.2.0.119430.RS**; the current Postshot GUI and log identify **1.1.69 (2026-08-18)**. Both controls were rerun in the current session. The October 28 measurements are historical references, not the control for this comparison.

The fresh RealityScan control differs from the historical run (17 versus 10 views in the largest component). The cause was not isolated; import order, caches and solver variation were not independently controlled. Do not attribute that historical difference to the capture-count change.

| Measurement | 16 captures | 31 captures |
| :--- | :--- | :--- |
| RealityScan components | 14 | 15 |
| Largest component: registered views | 17/96 (17.7%) | 31/186 (16.7%) |
| Largest component: physical captures | 16/16 | 31/31 |
| Largest component: view directions | 16 Left + 1 Up | 31 Left |
| Largest component: median reprojection error | 0.629 px | 0.755 px |
| Reported alignment time | 35 s | 85 s |
| Preview triangles | 6,900 | 14,200 |
| Postshot tracking result | Failed: 2/96 partial registrations; 0 accepted in saved image set | 121/186 accepted (65.1%) |
| Postshot initial sparse points | 38 | 5,419 |
| Postshot tracking time from log | 13.838 s | 190.810 s |
| Postshot training | Not started | 5,000 steps reached in 71.141 s |
| Saved Postshot project | 76,879 bytes | 398,497,517 bytes; reopened successfully |

RealityScan used the same instance and command sequence, without parameter changes between cases. Each imported, aligned and preview project was saved separately. Largest-component camera coverage was exported only after explicit maximal-component selection, avoiding the earlier component-report counting issue. Both largest components span the full tested interval, but almost exclusively through the Left face. More physical captures and triangles therefore do not establish broader scene coverage or better geometry.

Both preview projects were reopened and rendered from the first source capture's Left view (camera index 9 in the control and 30 in the dense case, verified by name). Both show coarse, faceted surfaces and distorted boundaries; the dense preview is not a complete usable staircase. These are Preview meshes, not final textured reconstructions. Automatic overview renders and camera index 0 use different source views between projects and were not used as matched-view evidence.

Postshot used All Images, Compute From Images, pose quality 3 (High), Remove Occluders, Splat3, a 3840 px size cap, 3 million maximum splats, anti-aliasing enabled, photometric compensation disabled and a 5 kStep limit. Masks were selected explicitly for each import. The 31-capture project reopened with 121 tracked views. Inspected rendered views show recognizable stairs, railings and doors, with soft detail, smeared surfaces and artifacts. These are inspection views around training cameras, not held-out quality measurements.

On reopening, Postshot logged five unmatched Down masks, for frames 0, 2, 5, 8 and 11. Their relation to rejected cameras has not been established. Import association and mask mode were checked, but per-pixel application and persistence of every mask are **not fully qualified**.

The reopened image set displays 121 imported / 121 selected / 121 tracked images, whereas the original run used 186 / 186 / 121. The saved image set therefore exposes a reduced input list. The native project and all original input files are retained; the five warnings should be checked against that reduced list before attributing them to a naming or mask-polarity defect.

## Interpretation and next work

- Retain the denser staircase case as a useful Postshot integration regression alongside Cour. Retain the failed 16-capture project and fragmented RealityScan cases.
- Repeat the paired runs before claiming repeatability or generalizing a sampling rule. The benchmark protocol requires at least three repetitions for that claim; this pilot contains one run per case per consumer, with no controlled cold/warm cache policy or exposed seed.
- Add per-direction coverage to diagnostic reporting. A largest model containing every sampled timestamp can still cover only one face of the panorama. Enumerate Postshot's physical captures and view directions separately before comparing them with RealityScan coverage.
- Investigate the five mask warnings and test masked/unmasked behavior independently. Do not combine a mask-policy change with the next sampling comparison.
- Preserve the current FOV and bounded diagnostic defaults. Next selection work should expose inclusion ranges, rejected views and their reasons; denser sampling alone did not solve RealityScan.

Peak RAM/VRAM and global consumer cache growth were not measured. Timings are reported observations, not a speed ranking. No geometric reference, complete-scene acceptance, held-out splat test, downloaded-binary qualification or Windows/CUDA application validation was performed.
