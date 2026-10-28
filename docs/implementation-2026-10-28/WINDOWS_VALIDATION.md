# Diagnostic windows and individual-model coverage — 2026-10-28

Development sources on `codex/studio-projects`, PR [#26](https://github.com/nicolasdiolez/360Extractor/pull/26), targeting `dev`. This implements the two product changes supported by the [denser staircase reference](DENSER_REFERENCE.md). No version, release tag or distributed binary changes.

## Behavior

The headline identifies the largest **individual** reconstruction and its capture/frame/time span. Ties are explicit. Reports made exclusively of one-/two-capture fragments say **Only fragments**, even when many captures appear somewhere in those models. The separate model table lists spans, fragment status and missing tested captures within each model's span. Overlapping alternatives are never merged into a fictitious single reconstruction. A temporal span is not a claim of continuous coverage between samples.

Source and export diagnostics accept an optional inclusive range of zero-based source-frame indices and a 512/1024 px choice. Boundary buttons close the dialog and navigate to the requested source frame in Studio. Actual result times come from the decoded/recorded timestamps, with FPS fallback explicitly identified. Bounds deliberately do not infer frame positions from nominal FPS. Source mode projects from the original video at the chosen resolution; export mode never upscales existing images. The normal extraction cadence and settings remain unchanged.

Each job saves its diagnostic mode, maximum captures, resolution and range in an optional `.360proj` job field, independently of extraction settings and last results. New extraction retains the choices. Replacing a source clears its range, while relocating the same source retains it. Old projects without these fields remain readable. Current readers recompute model summaries from historical reports; changing choices marks the displayed result historical rather than rewriting it.

Both resolutions keep the existing limits: 3–16 captures, at most 128 views, four COLMAP CPU threads, a five-minute deadline and a monitored 256 MiB workspace shared with source sampling. The supervisor still stops/reaps the process tree on cancellation, timeout or space failure. Higher resolution does not increase those budgets. Existing model trust, offline CPU inference, exclusion and source-identity checks remain in force.

## Automated and installed-package checks

- Full local offscreen suite: **415 tests and 20 subtests passed**, no skips, with the existing local AI stack. The run permits process inspection for the parent/child cancellation test.
- New coverage includes overlapping alternatives versus individual-model size, ties, two-capture-only fragments, missing tested captures, timestamp provenance, malformed options, bounded range sampling with exclusions, a real source helper at 1024 px, rejecting out-of-source ranges, no export upscaling, per-job save/open isolation, persistence through a new extraction, source replacement, old-project compatibility and historical UI state.
- Ruff, release consistency and whitespace checks pass. Whole-project mypy checks 51 source files; stricter function-body checks cover ten critical modules.
- Installed-wheel smoke outside the checkout passes with isolated imports. Its helper extracts exactly frames 1, 2 and 3 from the requested window at 1024 px, confirms 18 cube views, and roundtrips the diagnostic choices through a project. Local wheel validation reuses installed dependencies; fresh cross-platform checks are tracked on PR #26.

## Real Studio checks

The same application dialog launches each source diagnostic, saves the project, closes Studio, reopens it, and checks the restored choices and headline. Extraction settings and previous-export associations are checked for preservation. All sources are read in place. The Cour control uses the existing local segmentation model on Down; Louvre and staircase use the existing no-AI/nadir settings. COLMAP is 4.2.0 CPU on macOS arm64. Screenshots and exact requested frame lists are retained locally.

| Source / range | Resolution | Selected captures | Largest model | Total registered | Total diagnostic time |
| --- | ---: | ---: | ---: | ---: | ---: |
| Cour, whole video | 512 px | 8 | 8 | 8 | 27.352 s |
| Louvre, frames 0–102 | 1024 px | 8 | 8 | 8 | 47.211 s |
| Staircase, frames 0–82 | 1024 px | 16 | 16 | 16 | 71.355 s |
| Staircase, frames 261–343 | 1024 px | 16 | 0 | 0 | 70.857 s |

The first three runs each return one model; the final window correctly reports no model. Source-mode times include the helper's original-video sampling, unlike the earlier reference's alignment-only timings. They are single local runs, not performance benchmarks. The new first-window sampler chooses uniformly within the specified endpoints, so a few interior frames differ from the earlier window drawn from a 64-capture global sample. The diagnostic result still reconstructs all 16 selected captures in one model.

The end-boundary button was exercised against the original staircase video: Studio displayed **Frame 82**, with **PTS** timing, and retained the correct source. Reopening the older 512 px first-window report displayed **Historical — Only fragments: 5 model(s), at most 2 captures each**, with the per-model spans and missing tested captures. The positive, negative and historical-fragment screens were visually checked.

## Limits and retained evidence

This validates diagnostic behavior and a few existing scenes, not camera-pose accuracy, complete surfaces, segmentation quality or Gaussian splats. A successful local window does not validate the rest of the video. Missing tested captures do not identify the physical cause. Real COLMAP/AI were exercised on macOS; Windows/CUDA hardware and new frozen binaries remain unqualified. Schema 1 readers predating this feature may discard optional diagnostic choices when resaving.

Private evidence is retained under the ignored `plans/application360-windows-2026-10-28/` folder: reports, settings, indexes, logs, screenshots, reopened projects and verification records. Temporary tools, test caches and reconstruction workspaces are disposable under the user's existing Trash instruction; original media and prior retained evidence stay in place.
