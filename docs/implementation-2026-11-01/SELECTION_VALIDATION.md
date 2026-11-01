# Directional diagnostics and extraction ranges

Implemented on 2026-11-01 on `codex/directional-diagnostics-extraction-ranges`, based on development commit `9b26c77`. This is source implementation and local validation, pending integration and distribution qualification.

## Behavior

- Each new diagnostic model retains its registered image identities. The report/UI derive aligned versus confirmed tested views, counts per virtual camera, absent directions and exact images missing from that individual model. They never combine alternative models into broader coverage. Old reports without those identities retain capture statistics but display unknown directional coverage.
- A synthetic 16-capture/six-direction case with only Left registered reports 16/16 physical captures, 16/96 tested views and 1/6 tested directions. Images aligned in another model remain absent from the selected model. These are counts of virtual-camera directions, not solid-angle or geometric-quality measurements.
- Studio offers a per-video range editor with inclusive source-frame endpoints, boundary previews and explicit Whole source restoration. CLI accepts repeated `--frame-range START END`; projects/manifests store normalized `included_frame_ranges`. Defaults remain unrestricted. Other jobs, new media and global preferences retain their own settings.
- Ranges intersect individual exclusions and diagnostic windows. They preserve sampling cadence anchored at source start, all views of each selected capture and decoded timestamps. They affect storage estimates and preview labels. Source relocation preserves decisions; replacement with a different source identity clears them.
- The worker validates bounds before output/model allocation. It decodes from source start and stops after the last selected endpoint, rather than treating that intentional stop as premature EOF. A genuinely early decode failure still fails the run. Seconds-based estimates remain approximate, using nominal FPS; per-frame exclusions are deducted exactly only for frame-based estimates.

## Checks

Local environment: macOS arm64, Python 3.13.16; Qt tests use `QT_QPA_PLATFORM=offscreen` with isolated preferences and synthetic small media.

- Full suite: **437 tests and 20 subtests passed**, no skips. The first sandboxed focused run could not use `ps` in the child-process lifecycle check; the complete run with process-inspection access passed.
- Subsequent UI changes received a focused Qt/preview rerun: **48 tests passed**, including missing-direction details, legacy reports, range save/open, other-job isolation, invalid bounds, cancellation and outside-range preview labels.
- Whole-project mypy: **53 source files** passed. Strict body checks: **13 critical modules**, including selection, storage and the range editor, passed; CI now includes these modules.
- Ruff, release consistency (unchanged version 4.0.3) and whitespace checks passed.
- Isolated Qt component renders were inspected with synthetic data. Fixed the range editor's contrast/header sizing and the missing-view panel's background. These renders are layout checks, not actual staircase reconstruction evidence.

## Remaining scope

This change does not add a graphical range timeline, a complete candidate/rejection browser, automatic baseline-preserving densification, a 31-capture diagnostic, or a RealityScan/Postshot result importer. Existing limits remain 16 captures / 128 views / five minutes / monitored 256 MiB. Range extraction retains decoding from the beginning, so no fast-seek performance guarantee is made. Actual reconstruction quality, Postshot mask-reopen warnings, repeated consumer comparisons, Windows/CUDA execution and downloadable binaries were not requalified in this implementation session.

Generated test data, tool dependencies/caches and synthetic UI renders are grouped under one dated temporary directory. No original media were copied or changed. The repository also retains the preceding paired consumer pilot and measurements as the evidence motivating this work.
