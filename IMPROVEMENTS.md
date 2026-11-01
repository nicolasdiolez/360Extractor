# Improvement roadmap

Updated 2026-11-01 after consolidating the October 28 trials, executing the paired 16/31-capture staircase pilot and repeating it with the merged capture-plan implementation. This is the active roadmap for reliable, inspectable dataset preparation: prepare, diagnose, correct, export and verify in the target application. Dated reports retain their original scope; new evidence updates this roadmap rather than rewriting earlier results.

## Implemented, exercised and distributed

The tested functional baseline is `dev` at `3bba6be` (PR #29). The public [v4.0.3 prerelease](https://github.com/nicolasdiolez/360Extractor/releases/tag/v4.0.3) predates projects, mask profiles, rolling storage checks and alignment diagnostics. These development features are not in that downloadable binary, even though the source version still reads 4.0.3. Version/build identification needs to distinguish the next candidate. The earlier repository inventory recorded `main` at v4.0.1 and GitHub's latest stable release as v3.3; this consumer revalidation did not re-audit or publish releases.

| Capability | Development sources | Real-world evidence / remaining limit |
| :--- | :--- | :--- |
| Destination mask profiles and storage guard | Implemented in Studio/CLI | Written mask conventions checked; RealityScan/Postshot pilots executed. No guarantee that the whole extraction, models and reconstruction fit on disk. |
| `.360proj` save/open, relocation and frame exclusions | Implemented | Save/reopen and source checks exercised. No autosave, full run history, recovery or verified extraction resume. |
| Source/export alignment diagnostic | Implemented, including frame windows and 512/1024 px | Cour, Louvre and staircase windows exercised with COLMAP on macOS. A positive diagnostic does not qualify another reconstruction engine or the whole video. |
| RealityScan/Postshot consumer workflow | Four baseline cases, one FOV trial and two paired 16/31 observations per consumer | Fresh merged-dev exports preserve all common pixels. Dense Postshot again trains (118/186 views, 5 kSteps, reopened; pilot: 121/186). RealityScan remains fragmented. Final geometry, mask persistence and repeatability remain unqualified. |
| Downloadable macOS v4.0.3 | Signed and notarized | Existing-Mac artifact checks passed. Clean-machine acceptance and binaries containing the newer development features remain open. |
| Downloadable Windows / CUDA | Experimental | Hosted CI passes. Consumer trials on a Windows GPU machine do not qualify the 360 Extractor Windows executable or its CUDA inference. |

The [consumer report](docs/implementation-2026-10-28/CONSUMER_VALIDATION.md) and [compact measurements](docs/implementation-2026-10-28/consumer-results.json) now preserve the findings previously retained only under ignored `plans/`. The [benchmark protocol](docs/BENCHMARK_PROTOCOL.md) defines further comparisons.

## Current order of work

The first follow-up implementation ([PR #28](https://github.com/nicolasdiolez/360Extractor/pull/28)), merged into `dev`, adds per-model directional coverage and missing views, plus saved per-video extraction ranges in Studio/CLI. See the [implementation checks and limits](docs/implementation-2026-11-01/SELECTION_VALIDATION.md). This does not change the 16-capture diagnostic limit or qualify another reconstruction engine.

1. **Make consumer results inspectable and repeatable.** The [new run with merged dev](docs/implementation-2026-11-01/DEV_REVALIDATION.md) verifies the 96 common JPEGs and 16 common masks by SHA-256 for each consumer profile. Postshot again changes from tracking failure to a reopened 5 kStep splat, now with 118/186 accepted views. RealityScan grows from 8 to 58 views in its largest component, covering 8/16 versus 31/31 physical captures, but still produces 12 fragments in each case. The [earlier pilot](docs/implementation-2026-11-01/SAMPLING_COMPARISON.md) produced different counts from identical image bytes; the cause is not isolated. Prioritize a durable consumer-result importer (accepted/rejected views, physical captures, directions and mask warnings), then qualify the five unmatched Down masks on Postshot reopen with a separate masked/unmasked test. Run at least three repetitions per arm under a recorded cache/seed protocol before judging repeatability or timing. Keep current defaults and diagnostic limits; an explicit denser diagnostic needs its own resource qualification. No complete-scene or held-out quality claim is established.
2. **Complete inspectable extraction selection.** Saved inclusion ranges now restrict full extraction in `dev` (PR #28), preserve global cadence and combine with existing exact-frame exclusions. The editor provides boundary previews; diagnostics respect both extraction ranges and their separate test window. Controlled 16-to-31 densification preserving the original indices is implemented by [PR #29](https://github.com/nicolasdiolez/360Extractor/pull/29), with a frozen Studio/CLI plan and a reusable staircase configuration; see [validation and limits](docs/implementation-2026-11-01/DENSIFICATION_VALIDATION.md). Remaining: graphical timeline editing and an inspectable candidate list with selection/rejection reasons. Evaluate better window-based selection against fixed sampling on the same corpus; the current optical-flow filter demonstrated no benefit in the initial pilot.
3. **Add persistent manual mask correction.** Brush/polygon corrections and controllable margins should survive reopening and export through each destination profile. Measure missed occluders and false removal on annotated examples, including artwork, hands and poles. The consumer pilots verified association/mode, not the per-pixel effect of every mask.
4. **Complete project recovery and resource planning.** Add autosave/recovery, complete run history and verified resume using source/settings checks plus a validated output index. Retain fresh run folders as the current safe behavior. Extend planning to model caches and reconstruction workspaces, with measured RAM/VRAM and disk use.
5. **Qualify an identifiable next distribution candidate.** Prepare version/build identification and accurate notes for the implemented features; test the exact downloaded binaries, projects, diagnostics, AI and cancel/close behavior on clean target machines. Qualify Windows/CUDA separately and retain its experimental status until supported by evidence. A stable release remains a separate maintainer decision.

Continue the corpus with longer trajectories and annotated indoor/museum scenes, repeated runs, geometry references and held-out splat views. Preserve Cour as the positive integration control and the three difficult windows as regression cases. Diagnose their failures without assuming a single cause. Compare an independent tool only on a supported, available platform. See the [consumer limits](docs/implementation-2026-10-28/CONSUMER_VALIDATION.md#limits-and-next-experiment).

Native panorama export is an experimental alternative to measure, not a replacement already justified by the pilot. Full dual-fisheye stitching, a general 3D editor, a chatbot and generative pixel replacement are not current priorities.

## Established implementation in dev

- Studio processing controller, job states, cooperative cancellation, bounded preview/thumbnail work and tested process shutdown.
- Shared validation, new run folders, checked image/mask writes, confirmed output index and state/provenance manifests.
- Per-job settings preservation, preferences, working naming/quality controls and preview/export pixel checks.
- Binary/feathered masks, AI failure propagation, class/face selection, nadir disc and explicit custom-model trust.
- CAMM type 5/6 GPS records, GPMF GPS5 scales/fix/packet times, GPX/SRT sidecars and bounded interpolation/subprocesses. Here CAMM types 5/6 are distinct from GPMF's GPS5/GPS9 record names.
- Virtual COLMAP calibration, rig configuration and separate mask staging through a portable runner.
- Tiled projection, packaged QSS, expanded CI, macOS dependency resolution and release safeguards.
- Named mask contracts and rolling storage checks; [implementation validation](docs/implementation-2026-10-27/VALIDATION.md).
- Saved projects, source relocation and reversible capture exclusions; [project validation](docs/implementation-2026-10-27/PROJECTS_VALIDATION.md).
- Bounded source/export diagnostics with largest-model spans, tested gaps, fragments and persisted choices; [window/model validation](docs/implementation-2026-10-28/WINDOWS_VALIDATION.md).

These implementations are not all qualified on real camera/GPU/software combinations. See the [acceptance protocol](docs/CLI_TESTING_PROTOCOL.md) and dated validation evidence.

## Before the next distribution / stable-release decision

- [ ] Complete real-media Studio/CLI acceptance and fix any regressions found.
- [ ] Extend the completed consumer pilots to repeatable reconstruction-quality acceptance; qualify intended camera/codec/GPS combinations separately.
- [ ] Validate GPU operation and Windows dependency profiles; produce suitable platform locks.
- [ ] Build and test downloaded release binaries on clean target machines, including model/tool provisioning.
- [ ] Complete bundled component/weight license notices and remaining platform distribution checks. The v4.0.3 macOS prerelease is already signed and notarized; do not treat that completed step as outstanding.
- [ ] Assign the next version/date, finalize notes, require CI and approve tested draft artifacts.

## Further reliability and product work

- [x] Output-volume preflight and rolling next-capture space guard (development sources; downstream reconstruction excluded).
- [ ] Verified resume, full source hashes and recovery behavior.
- [x] Explicit project/queue save/open with source relocation and last-result references (development sources).
- [ ] Autosave and full run history; persistent viewport state.
- [x] Bounded source/export diagnostics, frame windows and individual-model coverage (development sources).
- [x] Saved extraction inclusion ranges and individual exclusions (PR #28).
- [x] Controlled 16-to-31 extraction preserving the frozen baseline (PR #29); fresh real-media exports and a new consumer pair verified after merge. The staircase example now matches the pilot's enabled EXIF intrinsics.
- [ ] Graphical range timeline and inspectable selection/rejection decisions.
- [ ] Persistent manual mask corrections and annotated quality measurements.
- [ ] Complete mixed-value indicators, asynchronous metadata and accessibility/HiDPI acceptance.
- [ ] Annotated segmentation corpus, blur calibration and an optional whole-capture AI skip policy.
- [ ] GPS9/GPSU support, camera fixtures, sidecar offset calibration and validated orientation sources.
- [ ] End-to-end profiling and global RAM/VRAM budgets, bounded caches and staged processing.
- [ ] Separate core/gui/ai distributions and offline provisioning profiles.
- [x] Explicit mask naming/polarity profiles and recorded contracts (development sources).
- [x] Four RealityScan 2.2 and four Postshot 1.0.1 baseline pilots; one additional FOV110 trial per consumer. Results and limits recorded, not general compatibility certification.
- [x] Paired 16-versus-31-capture pilot at 90° on the beginning of the staircase; one run per case/consumer, with results and limits recorded.
- [x] Repeat the staircase pair with merged `dev`, verify common image/mask hashes and retain native consumer projects.
- [ ] Durable consumer-result import, Postshot physical-capture/direction counts and unmatched-mask association/persistence on reopen.
- [ ] Controlled repeatability qualification with at least three runs per arm; record cache state and seed availability.
- [ ] Repeated consumer quality comparisons, mask-effect checks and complete-scene acceptance.
- [ ] Explicit HDR/ICC/alpha handling.

## Exploratory work, not current functionality

Native dual-fisheye stitching, IMU horizon leveling, generative inpainting, depth-assisted masking and managed cloud execution remain future ideas. JSON is the supported configuration format. CLI headless operation is available; it does not itself provide a cloud service.
