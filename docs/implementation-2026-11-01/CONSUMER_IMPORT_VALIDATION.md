# Consumer report import — implementation checks

Implemented on 2026-11-01 on `codex/consumer-report-import`, based on merged `dev` at `ad2b108` (PR #30). The [user guide](../CONSUMER_REPORTS.md) describes Studio, CLI, supported evidence and interpretation. This is source-level validation; no new consumer reconstruction or distributed binary was produced.

## Behavior exercised

- RealityScan registration CSV and the supplied tab-delimited input-state format: Windows paths, individual components, retained/rejected/disabled/unknown inputs, and no union of overlapping components. A missing registration camera is recorded as absent with unknown cause.
- Postshot COLMAP text and binary image identities: capture/direction coverage, spaces in filenames, explicit empty registered sets, duplicate/foreign/ambiguous names and truncated/nonfinite input rejection. The export index and completed manifest must agree on the confirmed view count.
- Logs: last UTC session when available, mask warnings associated with indexed masks, unmatched warnings preserved, and log-only membership left unknown. Session scope is displayed; no tracking count is used as a substitute for image identities.
- `.360proj` save/reopen retains imported facts independently of subsequent extraction results. Relocation preserves them; source replacement clears them. Derived totals are recomputed. Input/manifest/index digests and the source size/date identity remain attached to the report.
- Studio imports asynchronously, blocks conflicting project operations while importing, marks successful imports as unsaved project changes, and cancels before close without publishing a result. The table displays states, capture coverage and associated mask-warning counts. Removal only changes project history.
- CLI import works without opening Studio; an existing report is never overwritten. A publication failure leaves no successful report. Limits and cancellation fail explicitly.

## Checks

Environment: macOS arm64, Python 3.13, Qt offscreen. Temporary fixtures, test media, local mypy tooling/caches and the synthetic dialog preview were grouped in one dated temporary folder.

| Check | Result |
| :--- | :--- |
| Complete source test suite | **502 passed, 20 subtests passed**, 21.53 seconds |
| Ruff | Passed |
| Whole-project mypy | Passed, **56 source files** |
| Critical-contract mypy with untyped function bodies checked | Passed, **16 modules**, including both new importer modules |
| Release metadata consistency | Passed; version remains 4.0.3 |
| Diff whitespace check | Passed |
| Offscreen dialog inspection | Readable synthetic six-view fixture with mixed retention and a Down-mask warning |

The initial sandboxed full-suite run could not execute `ps` in the existing process-tree cancellation test. The final full suite was run with that access and passed. This was an execution-environment restriction, not an ignored test. CI is configured to include the new modules in its blocking type checks; remote CI has not been run for this local feature branch.

## Qualification still required

Fixtures follow the documented RealityScan report variables/registration format and Postshot COLMAP export. The custom RealityScan template has not yet been executed in RealityScan during this implementation session, and newly exported native Windows reports have not been round-tripped through this importer. Qualify those exports on the retained staircase projects before treating version compatibility as established.

Imported names do not verify source pixels or prove all exported views were submitted. Missing cameras do not identify the cause of exclusion. A log warning's filename association is not proof that it belongs to the selected run. No warning does not prove mask application or persistence. This change does not resolve Postshot's mask-reopen behavior, qualify reconstruction quality/repeatability, or validate a Windows/CUDA executable.
