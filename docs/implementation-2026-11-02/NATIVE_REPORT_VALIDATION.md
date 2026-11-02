# Native consumer-report qualification

On 2026-11-02, reopen the retained staircase projects from the [merged-dev 16/31 comparison](../implementation-2026-11-01/DEV_REVALIDATION.md) on Windows/Shadow. Export fresh evidence with RealityScan **2.2.0.119430.RS** and Postshot **1.1.69**. No alignment, training or extraction was rerun, and the retained projects were not saved over. This qualifies report compatibility for these projects and versions, not a new reconstruction result.

The importer baseline is `dev` **f7807929482b873126bd0a46c4eb2b743fc1c253** (PR #31). Corrections and this report are prepared on `codex/native-consumer-report-validation`; they are not part of a published binary. [Compact measurements](native-report-results.json) retain input/index/manifest digests, component-specific capture/direction coverage and version information without absolute private paths.

## Native results

| Evidence | Confirmed views | Retained views | Physical captures with a retained view |
| :--- | ---: | ---: | ---: |
| RealityScan, 16 captures, largest of 12 components | 96 | 8 | 8/16 |
| RealityScan, 31 captures, largest of 12 components | 186 | 58 | 31/31 |
| Postshot, 31 captures, Image Set exported as text and binary | 186 | 118 in both, identical identities | 31/31 |
| Postshot, 16 captures, reopened failed project | 96 | No export available | Unknown to the importer |

RealityScan's native `exportReport` successfully executes the **exact product template**. Each of the 12 components reports every indexed input with native True/False alignment flags. The largest control component retains eight Left views. The dense component retains Left 31, Back 11, Up 7, Down 5, Front 4 and Right 0. The remaining 88/128 views are rejected **in that component**, not globally. Components remain separate.

Postshot's dense Image Set retains Left 31, Down 26, Right 26, Back 13, Up 13 and Front 9. Neither dense result retains all six views of any physical capture. Text and binary camera exports identify exactly the same 118 images. The other 68 indexed views are absent from that exported set, with unknown cause.

The failed 16-capture Postshot project reopens with **96 imported/selected images, 0 tracked cameras and 52 sparse points**. Its export action says **“There are no camera poses to export from this Image Set.”** The earlier two-view partial solver attempt is therefore not a saved two-camera model. No camera report was fabricated; importing the fresh log alone correctly leaves all 96 view memberships unknown.

Both consumer profiles still have **96 common JPEGs and 16 common masks** between the 16/31 datasets, all SHA-256 identical in a fresh read-only check. The four confirmed index digests also match the preparation records. No original media was copied to the internal disk.

## Masks and log scope

The fresh dense Postshot session (`2026-11-02 09:26:09 UTC`) repeats five unmatched-mask warnings, for Down frames **5, 8, 11, 13 and 16**. All five map to the confirmed mask index. They are **exactly the five Down views missing from the exported Image Set**; the other 26 Down views are retained. This is correspondence evidence, not proof of why those views are absent or whether masks affected training pixels. Do not treat these warnings alone as five failed mask applications to retained cameras.

The fresh control session (`2026-11-02 09:37:18 UTC`) has no warnings, but no camera export. That does not prove masking or tracking success. RealityScan was imported without a log, so its mask warnings remain unknown.

The accumulated Windows Postshot log also contains non-UTF-8 bytes in an older session. Session excerpts were cut at the last native UTC header **before decoding**, retaining exact session bytes; only these small excerpts were transferred. The importer now applies that same order to accumulated logs. The selected session still must be valid UTF-8; unsupported current-session bytes fail explicitly. Whole-input SHA-256 remains attached to an import, even when only the last session is interpreted. This is not automatic encoding detection or run separation within one session.

## Corrections and validation

- **Native Postshot IDs:** both formats start image/camera IDs at zero. Baseline `f780792` rejects both real files with `Invalid COLMAP image ID or pose`. Accept zero and read binary IDs as unsigned 32-bit values, matching COLMAP's [identifier types and invalid sentinels](https://github.com/colmap/colmap/blob/main/src/colmap/util/types.h). Continue rejecting negative/out-of-range text IDs, the invalid sentinel, duplicate IDs, invalid poses and malformed records. Added regressions cover zero in each field and unsigned boundaries.
- **Old log encoding:** locate the last UTC session in bytes before UTF-8 decoding. A regression ensures ignored older bytes cannot block a valid current session, while invalid current/no-header logs still fail and the input digest covers all original bytes.
- **Report contrast:** include the consumer dialog in the existing dark dialog stylesheet. The native report table, headers, labels, buttons and warnings are readable with a light system palette as well.

Five real imports completed through Studio's background import thread: both RealityScan reports, both dense Postshot formats and the control log. Saving and reopening the `.360proj` preserved every report. After reopening, filtering absent Down views displayed exactly five rows, each with one mapped warning. RealityScan's selected dense component displayed all 186 view states independently. These were macOS source/Qt offscreen checks with media preview disabled; they do not qualify Windows Studio or GPU inference. A real Postshot CLI import also succeeded with 186 confirmed views and five warnings.

Checks: **521 tests and 20 subtests passed**, no skips, in 25.15 seconds; all **33 importer tests** passed again after explicitly preserving UTF-8 BOM handling; Ruff, whole-project mypy (56 files), critical-contract mypy (16 modules), release metadata and whitespace checks passed. The initial sandboxed suite could not invoke `ps` for its child-process test; the final complete run had that access and passed. No remote CI, installed-wheel or distributed-binary validation is claimed for this local branch.

## Retained evidence and limits

Private native files, normalized receipts, the reopened `.360proj` and screenshots are retained locally under ignored `plans/application360-native-reports-2026-11-02/`. The six-file transfer archive is **32,099 bytes**, SHA-256 `b812471bacf78927b7834da68ec1558bce445a36857154fee533dbb8f358d72f`, verified after the authorized private-Drive transfer. It contains no image, video or splat model. Public source changes contain compact measurements and synthetic regressions only.

RealityScan **registration CSV** was not qualified here: `exportRegistration` without an explicit parameter file used the installation's current COLMAP export settings and created a COLMAP folder instead of CSV. The successful RealityScan qualification is the input-state template. For CSV, explicitly select **Internal/External camera parameters**, or supply the corresponding saved export settings, as described by the [RealityScan CLI documentation](https://rshelp.capturingreality.com/en-US/tutorials/commandline_1.htm).

Next: isolate mask behavior with a recorded masked/unmasked comparison on the same selected views, then at least three controlled repetitions per arm for repeatability. Other consumer versions, native registration CSV, non-UTF-8 active sessions, reconstruction quality and Windows/CUDA distribution remain unqualified. Keep extraction defaults, diagnostic limits and release status unchanged.
