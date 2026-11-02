# Source alignment preflight — 2026-10-28

Development branch `codex/studio-projects`, PR [#26](https://github.com/nicolasdiolez/360Extractor/pull/26) targeting `dev`. This extends the [October 27 export diagnostic](../implementation-2026-10-27/ALIGNMENT_VALIDATION.md). Published binaries, tags and stable-release status are unchanged.

## Delivered behavior

Studio can prepare a small diagnostic directly from a stitched 2:1 360 video, without a previous extraction. A supervised helper seeks to 3–16 uniformly distributed source frames, confirms the decoder positions and passes only those frames through the existing processing pipeline. It retains camera geometry, AI scope and nadir policy, while recording the reduced-resolution JPEG/COLMAP-mask settings and disabled blur/motion/telemetry filters. Original job settings and any previous export association are preserved. Builtin AI weights must already be local; custom weights retain the explicit-trust requirement. Inference runs on CPU, with the Studio preview drained first.

Sampling and COLMAP share one five-minute deadline and a monitored 256 MiB workspace budget. Up to 128 views are allowed. The parent supervises and reaps the active process; cancellation also terminates its process tree. The disk bound is monitored rather than a filesystem quota and can briefly be exceeded between checks. Reports, settings and command logs remain available after failure.

COLMAP 4.2's specific mapper exit with no sparse model is now a negative measurement rather than a generic tool failure. Other exits remain errors. Candidates yielding no confirmed views are reported as filtered before alignment, never counted as unregistered. Fewer than three confirmed captures prevents alignment. The report and exact-frame exclusions persist in `.360proj`; the latest full extraction still replaces the previous result. See [Studio projects](../PROJECTS.md).

## Verification

- Full local offscreen suite: **397 tests and 20 subtests passed**, no skips, Python 3.13 on macOS arm64 with existing AI dependencies. The final run allowed process inspection for the real parent/child cancellation assertion; an earlier sandboxed run could not execute `ps`.
- Added regressions cover bounded sampling without allocating a full-video frame list, exclusion ranks, settings isolation, custom trust, missing offline weights, exact decoder positions, a real helper subprocess, filtered outcomes, recognized versus unrelated COLMAP failures, process-tree cancellation and Studio source-mode routing/preview suspension.
- Ruff, release consistency and whitespace checks pass. Whole-project mypy checks 50 source files; stricter body checks cover nine critical modules including the new source sampler.
- Installed wheel tested outside the checkout with isolated imports: resources, console/module CLI, extraction, project/exclusion roundtrip, alignment summary, reconstruction staging and the new sampling-helper entry. The helper confirms exactly frames 0, 2 and 4 and their 18 cube views from a synthetic video. Local wheel validation reused installed dependencies; fresh cross-platform environments and final-commit checks are tracked on PR #26.
- Actual Studio source preflight exercised with no prior export, local AI on the Down face, report display and save/reopen. Original settings remained unchanged and no full-export association was invented.
- Cancellation during real 8K source sampling stopped/reaped the helper (return code -9, about 1.1 s from start with cancellation requested after one second). The automated process-tree test additionally starts and checks a real child process.

## Existing-source measurements

Sources were read in place. COLMAP 4.2.0 CPU on macOS, six cube views, 90° FOV, four COLMAP threads, up to 4096 SIFT features/view, sequential overlap 10, quadratic overlap disabled, seed 0, fixed intrinsics/rig. The staircase used the deterministic Down nadir mask without AI. Cour also used the existing `yolo26n-seg.pt` model on Down. These are individual functional pilots, not performance or segmentation benchmarks.

| Source / experiment | Views per capture | Resolution | Captures registered | Models / groups | Time |
| --- | ---: | ---: | ---: | ---: | ---: |
| Cour, direct Studio preflight with AI | 6 | 512 px | 8/8 | 1 / 1 | 36.35 s total |
| Bobillot staircase, direct preflight | 6 | 512 px | 0/8 | 0 / 0 | 29.10 s total |
| Bobillot staircase, larger preflight sample | 6 | 512 px | 0/16 | 0 / 0 | 67.08 s total |
| Bobillot staircase, same eight frames at higher resolution | 6 | 1024 px | 0/8 | 0 / 0 | 22.78 s alignment only |

The staircase source has 344 frames, 7680×3840 pixels at 25 fps. The eight-frame sample is `[0, 49, 98, 147, 196, 245, 294, 343]`; the 16-frame sample is `[0, 23, 46, 69, 91, 114, 137, 160, 183, 206, 229, 252, 274, 297, 320, 343]`. Its mapper could not initialize a sparse model in all three cases. The first attempt exposed the generic-error handling corrected here; final reports retain the negative result. The 1024 px comparison is a separate bounded experiment, not a change to the product's 512 px preflight limit. Its timing excludes extraction and must not be compared directly with the total preflight times.

Increasing resolution alone did not rescue this eight-frame sample. That does **not** establish the cause of failure, prove the source unusable or qualify automatic capture rejection. A denser reference reconstruction and more difficult scenes are needed before calibrating warnings. No geometric truth, pose accuracy, dense reconstruction quality, splat quality or competitor ranking was measured.

Follow-up on the same date: the [denser reference](DENSER_REFERENCE.md) reconstructs a 36-capture main model from 64 captures at 1024 px, and one complete 16-capture model in a short initial window. At 512 px the corresponding positive counts consist only of two-capture fragments. This confirms why the preliminary negative result must not reject the source and why total registration alone is insufficient.

## Practical limits and next direction

Source preflight samples independently of the full-export interval and disables blur/motion filters. Its exact-frame exclusions do not define time ranges; a later export may select different frames. Treat it as a quick, reviewable experiment rather than an acceptance gate. Keep full settings and evidence visible, qualify negative outcomes against denser references, and avoid adding unexplained quality scores or automatically deleting failed captures.

Real COLMAP and source AI were exercised on macOS only. CI checks helper logic and installed packages on Linux/macOS/Windows, with Studio tests on macOS/Windows; it does not qualify real Windows/CUDA reconstruction, consumer imports or the distributed frozen executable. The helper's frozen-app entry is implemented but requires binary qualification. Flat cameras, native panorama reconstruction and multi-source rigs remain outside this feature. Source identities use size/mtime rather than complete content hashes.

Local evidence is grouped in `application360-preflight-2026-10-28/mesures`: reports, settings, confirmed indexes, commands, logs, project and inspected screenshots. Temporary tooling, caches and reconstruction workspaces are disposable under the user's cleanup authorization. Source media stay in place and Trash is not emptied.
