# Studio alignment diagnostic — 2026-10-27

Development branch `codex/studio-projects`, PR [#26](https://github.com/nicolasdiolez/360Extractor/pull/26) targeting `dev`. This extends the project-persistence implementation; it does not update the published 4.0.3 binaries or authorize a stable release.

## Behavior and boundaries

The Project menu runs a small CPU COLMAP 4.2 alignment from a **completed 360 perspective-rig export**. Its confirmed index, source size/mtime, export run, settings, rig and mask polarity are checked before creating a new workspace. It samples at most 16 physical captures and 128 views, downscales copies to at most 512 pixels with matching intrinsics, configures the rig before matching, and limits each view to 4096 features. Cancellation, five-minute timeout, a monitored 256 MiB workspace budget and a rolling free-space reserve stop and reap the subprocess. Polling can overshoot a size limit briefly; this is not a filesystem quota.

The report separates unregistered captures from excluded and unsampled ones. It counts physical source frames and retains per-model view counts. Models sharing captures are overlapping alternatives, not separate disconnected groups. Checkboxes record zero-based source-frame exclusions for all views, without changing the sampling cadence. Decisions survive save/open and new extraction. Restoring excluded frames remains possible after they disappear from a subsequent export. Changing the selection marks previous measurements historical; replacing the source clears its frame decisions.

Source navigation requests an exact frame and checks the decoder's returned position. New confirmed indexes include decoded seconds and their provenance; older exports display timing as unavailable. The latest diagnostic summary is saved inside the latest result; a new extraction replaces that result, retaining the frame decisions. See the [user guide](../PROJECTS.md).

## Verification

- Full offscreen suite: **380 passed, 20 subtests passed**, no skips, using the installed local AI dependencies and existing model. Added coverage includes cadence in Frames/Seconds, all-view exclusions, project reopening, restoring decisions, source replacement, stale/partial exports, mixed masks, exact-frame confirmation, malformed model records, overlapping models, fresh workspaces, and subprocess cancellation/timeout/space failures.
- Real Qt lifecycle test now saves the queue, closes Studio, reopens the project and extracts before exercising repeat/error/cancel/close.
- Ruff, release consistency and whitespace checks pass. Whole-project mypy passes for 49 source files; stricter body checks cover eight critical modules, including both alignment modules.
- Installed-wheel smoke outside the checkout passes: site-packages import, resources, CLI, flat/cube pixels, nadir mask, project/exclusion roundtrip, alignment summary and portable COLMAP staging. Local installation reuses existing dependencies; CI builds fresh wheels for all three systems.
- The foundation commit `f9b6674` passed the complete remote CI: core and installed wheels on Linux/macOS/Windows, Studio on macOS/Windows, including 100 Windows lifecycle repetitions. The diagnostic candidate's exact-commit CI is tracked on PR #26; these foundation results alone do not validate the later change.
- Actual Studio display inspected; Louvre save/close/reopen, table, checkbox persistence, real diagnostic launch and source-frame 102 navigation verified.

## Existing-source pilots

macOS arm64, Python 3.13, COLMAP 4.2.0 CPU. Reused the earlier confirmed Cour and Louvre datasets without rewriting them or copying source videos. Pilot settings: six cube views, 512 px, eight physical captures, four threads, sequential matching overlap 10, seed 0, fixed intrinsics and rig transforms.

| Export / selection | Captures tested | Registered captures | Models | Disjoint groups | Diagnostic time |
| --- | ---: | ---: | ---: | ---: | ---: |
| Cour, all eight | 8 | 8 | 1 | 1 | 12.496 s |
| Louvre, all eight | 8 | 8 | 1 | 1 | 8.260 s |
| Louvre, frame 68 excluded, run through Studio | 7 | 7 | 2 | 1 | 8.417 s |

In the last run, the models share frames 0 and 34. One contains all seven included captures. Reporting two disconnected groups would be incorrect. This exclusion was a functional test, not a recommendation to reject frame 68 or evidence of improved reconstruction.

These clips do not exercise difficult registration failures. Synthetic model fixtures verify unregistered and disjoint/overlapping reporting. No geometric truth, pose accuracy, dense reconstruction, splat quality, segmentation quality or competitor ranking follows from these counts. Timing is a single local run, not a performance benchmark.

## Remaining work

This first diagnostic requires an existing export; it does not yet prepare a cheap preliminary extraction from the source. Flat-camera intrinsics, multiple sources, native panorama diagnostics, masks edited by hand, inferred failure causes and automatic rejection are outside this implementation. Real COLMAP was exercised on macOS only; Windows/CUDA, installed consumer workflows and clean-machine distributed binaries remain unqualified. Pixel identity checks use file size/mtime, not complete content hashes.

Session tools and experiments are grouped in `application360-alignment-2026-10-27`. Reports, command logs, project, screenshots and verification records are retained; temporary tooling, caches and diagnostic working data are disposable under the user's cleanup instruction. No source video/RAW was copied and Trash is not emptied.
