# Controlled 16-to-31 capture plans

Implemented on 2026-11-01 on `codex/controlled-densification`, based on `dev` at `c5f901d` (PR #28). This qualifies source behavior with synthetic media; external consumer reconstruction has not been repeated for this implementation.

## Contract and reproduction

The saved reference is an explicit ordered list of 16 source frames. `baseline` exports that list; `densified` retains every reference frame and inserts the floor midpoint of each of its 15 gaps. No frame is shifted to fill exclusions, disjoint ranges or an impossible gap. Conflicts and rejection filters fail before output/model allocation. Interval settings are preserved but bypassed. All active virtual-camera views stay together, with decoded timestamps and explicit timestamp fallback as before.

The staircase reference in [staircase-capture-plan.json](staircase-capture-plan.json) exactly matches the preceding [pilot's measurements](sampling-results.json): frames 0–82 and added frames **2, 8, 13, 19, 24, 30, 35, 41, 46, 52, 57, 63, 68, 74, 79**. It retains Cube/FOV90/1024/JPEG95 and the 40% Down nadir mask, with AI, rejection, sharpening and telemetry disabled. The [project guide](../PROJECTS.md#controlled-16-to-31-densification) supplies Studio steps and paired CLI commands using one configuration.

Projects preserve the plan per source. Relocation keeps it; replacement clears it. Manifests retain requested/added/fully confirmed frames and a common source-size/mtime/settings signature; index records label original versus inserted views. Failed writes or early decoding cannot produce a completed plan, and cancellation retains explicit partial status. Source/export COLMAP diagnostics sample only planned candidates while retaining the existing 16-capture / 128-view / five-minute / monitored 256 MiB limits.

## Local evidence

Environment: macOS arm64, Python 3.13.16, offscreen Qt with isolated preferences. Tiny synthetic MJPEG sources are decoded by OpenCV; no original footage was copied.

- **485 tests and 20 subtests passed** after PR #29 review fixes, with no skips. Includes the existing lifecycle, AI contracts, source helper and project regressions.
- Paired exports exercised both frame/seconds interval settings and RealityScan/Postshot mask profiles. They produce exactly **96/186 confirmed images** and **16/31 Down masks**. All 16 common captures' JPEG and mask bytes are identical within each synthetic pair; timestamps match decoded source positions. Original video bytes remain unchanged.
- The historical 0–82 frame lists and checked-in configuration are asserted against the pilot. Invalid/duplicate/out-of-order references, impossible gaps, bounds, exclusions, rejection filters, partial writes, early decode failure and cancellation are covered.
- Real CLI subprocesses generate both modes from one saved config. Studio tests cover reference freezing, mode switching, project save/reopen, other-job isolation, unrelated multi-selection edits and source-specific reset. Preview labels distinguish unplanned frames.
- Source helper and export diagnostics with a 31-capture plan retain their 16-frame bound and sample the original 16 in the complete staircase window. COLMAP command execution is stubbed in this regression; it does not measure alignment quality.
- Whole-project mypy: **54 source files**. Additional body checks: **14 critical modules**, including the new plan implementation; the CI command includes it. Ruff, unchanged version 4.0.3 release consistency and whitespace checks pass.
- A rendered Qt range editor with the dense staircase plan was inspected for contrast, frame-list readability and accessible Save/Cancel controls. This is synthetic layout evidence.

PR review reproduced a conflict between diagnostic exclusions and the frozen plan: unchecking a planned frame mutated the settings, then raised an error while refreshing the summary and left an unsaveable selection. The diagnostic now refuses that edit without changing the checkbox/project. It also retains a valid historical report when current inspector settings conflict with the plan, instead of raising or treating the report as unreadable. Five added regression cases cover original/inserted frames, allowed exclusions outside the plan and conflicting settings followed by recovery. The focused diagnostic/project/plan suite passed 74 tests; final CI repeats the blocking type and platform checks.

## Limits and next measurement

This implementation regenerates both exports from the same source; it does not copy previously generated pixels or reopen consumer projects. Matching comparison signatures are settings/source-identity evidence, not cryptographic source verification, model determinism or byte equality. For strict real-media comparison, verify the common image/mask hashes and retain the exact application/environment alongside both manifests. The source-size/mtime identity retains its documented limitations.

The RealityScan/Postshot pilot remains one historical run per case/consumer. This implementation does not resolve the Postshot mask-reopen warnings, establish repeatable 3D quality, raise the COLMAP diagnostic limit or qualify a new distributed binary/Windows-CUDA inference path. Decode still starts at the beginning of the source; no long-video seek speedup is claimed.

Generated validation media, type-check tools/caches and the Qt render are grouped in `/private/tmp/2026-11-01-360-densification` for approved cleanup after validation.
