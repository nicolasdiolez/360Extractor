# Studio project persistence — 2026-10-27

Branch `codex/studio-projects`, based on the previously validated mask/storage commit `ee6b3af`. This is a source implementation, not a published binary update. Version remains 4.0.3.

## Delivered behavior

- Project menu: New, Open, Save, Save As and Locate Selected Source; standard shortcuts and unsaved-change prompts.
- A small versioned `.360proj` document preserves queue order, stable job IDs, per-media settings, selected cards, defaults and last-result references. Media are referenced, not copied.
- Relative references survive moving the project folder. Missing/changed media stay visible for explicit relocation; source size/mtime is checked again by the worker before output creation.
- Loading a custom model path never grants trust. Studio exposes explicit consent, clears it on model changes and disables granting trust to a selection of different models.
- Invalid documents preserve the current queue. Failed writes preserve the previous project; external document changes trigger a Save As error. Reopening completed jobs makes them Pending; a new extraction creates new run folders.
- Close waits for active workers, then offers saving. Cancelling the dialog restores preview and controls; it does not restart cancelled extraction.

## Verification

| Check | Result |
| :--- | :--- |
| Full offscreen pytest suite | 358 passed, 20 subtests passed; no skips |
| Ruff and diff whitespace check | Passed |
| Whole-project mypy | Passed, 47 source files |
| Critical-body mypy including both project modules | Passed, 6 files |
| Release consistency | Passed, version unchanged |
| Installed-wheel smoke outside checkout | Passed, including project save/open and existing extraction/reconstruction-staging checks |
| Existing real sources in Studio | Cour and Arc du Louvre saved, queue cleared, project reopened; IDs/settings/source size/mtime retained; no automatic processing |
| Offscreen Studio screenshot | 1440×1000 inspected |

The real-source document is 5,502 bytes and contains two external video references. Different quality values, camera selection and mask profiles survive reopening. The videos were not copied or rewritten. No further reconstruction quality claim follows from this persistence test.

Regression coverage includes a moved project directory, Save As rebasing, Unicode paths, missing/changed media, explicit source confirmation, preserving settings on relocation, clearing old result associations for changed media, malformed/future schemas, duplicate sources/IDs, unsafe relative paths, failed atomic replacement, external edit conflicts, first save without hardlink support, custom-model trust, unsaved close cancellation/failure, close during preview draining, late blur results from a previous project, blocked document actions during processing and fresh output folders after reopening completed jobs.

The CI workflow now places document-core tests in the cross-platform core matrix and project UI tests in the Studio matrix; both new modules join stricter typing checks. CI was configured but not remotely executed during this local session. Local wheel validation reused installed dependencies; it is not a clean-machine or frozen-binary qualification. No physical Windows/exFAT test was performed; the unsupported-hardlink fallback is covered by simulation.

## Limits

This version provides explicit save/open. It does not implement autosave, crash recovery, verified extraction resume, a complete run history, manual capture rejection, mask painting or viewport-position persistence. Source identity is size/mtime, not cryptographic verification. Output folders are historical references whose contents are not revalidated on open. Existing-file publication uses staged replacement; optimistic external-change detection does not lock out simultaneous writers. A first save on a filesystem without hardlinks uses exclusive writing and may be incomplete after power loss.

The user guide is [PROJECTS.md](../PROJECTS.md).

## Cleanup

With Nicolas's authorization, 33 prior-session tool/cache/test items (about 0.239 GB of allocated blocks, hardlinks counted once) were moved to macOS Trash. The approximately 0.146 GB of prior measurements, masks, logs and screenshot were preserved. Trash was not emptied, so this does not claim reclaimed disk space.

This implementation's work is grouped in a separate dated `application360-projects-2026-10-27` directory. After validation, 37 additional tool/build/test items (about 0.128 GB) were moved to Trash under the same cleanup instruction. The real-source project, its screenshot/verification and logs remain (under 1 MB, plus inventory receipts). No source video or RAW copy was created; Trash was not emptied.
