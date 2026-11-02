# 4.1.0 feedback-preview preparation

Prepared on 2026-11-02 with the maintainer's approval to integrate the native-report correction, remove merged work branches, promote the accepted development sources to main and qualify a new **prerelease**, excluded from Latest. Published tags and assets remain unchanged; v3.3 remains the latest stable release.

## Scope

- Saved `.360proj` projects, source relocation and extraction exclusions/ranges.
- Destination mask profiles and output-volume storage checks.
- Bounded source/export alignment diagnostics with individual-model and direction coverage.
- Controlled 16-to-31 capture plans preserving the frozen baseline.
- RealityScan/Postshot report imports, saved per-source evidence and mapped mask warnings.
- Native Postshot zero-based IDs, appended-log session decoding and readable report dialogs.

The current public v4.0.3 binaries predate these features. Version 4.1.0 identifies this new candidate; older manifests that say 4.0.3 must still be interpreted with their recorded commit and dated evidence.

## Integration and source evidence

The native-report correction was reviewed and merged into dev as `64bee0d` in [PR #32](https://github.com/nicolasdiolez/360Extractor/pull/32), from `0130736` against dev `f780792`. Its [qualification record](NATIVE_REPORT_VALIDATION.md) describes 521 passing tests plus 20 subtests, native report identities, project persistence and the limits of those source checks. Both PR #32 CI runs passed all ten jobs, including installed wheels on all three systems and 100 Windows extraction/shutdown repetitions. These results do not qualify a new frozen binary.

The 4.1.0 source candidate also passed **521 tests and 20 subtests**, without skips, on macOS/Python 3.13 in 22.82 seconds; Ruff, release consistency and whitespace checks passed. Its application code is unchanged from the corrected native-report commit apart from the version identifier.

At the initial release inventory, the four branches of PRs #28–31 are wholly reachable from dev, main is 30 commits behind dev without divergent commits, and no other PR is open. The four merged work branches and the merged PR #32 branch have now been removed locally and remotely, with their commits retained in dev and the PRs. Unmerged work, tags, release assets and the unrelated local product-audit folder were preserved.

## Artifact acceptance

The immutable application tag is `v4.1.0` at `e2400c3ae174f0b3408c2f7144de140e0edf63d9`,
promoted in [PR #33](https://github.com/nicolasdiolez/360Extractor/pull/33).
The [release workflow](https://github.com/nicolasdiolez/360Extractor/actions/runs/41431637790)
passed all 14 jobs. Its Mac build passed 520 tests plus 20 subtests (one skip),
and Windows passed 518 tests plus 20 subtests (three skips). Both frozen CPU-AI
smokes passed. These counts retain the skips; they are not full AI qualification.

### Native macOS blocker and dependency correction

The original downloaded Mac ZIP has SHA-256
`4a81a7ce4dec1e12d01ad619a3c899baac3532b61e2c834236668daa89fda4e2`.
After Developer ID signing and successful notarization, the actual Cocoa Studio
still crashed twice while accessibility inspected table dialogs. Native crash
reports identify SIGSEGV/SIGBUS in `libqcocoa.dylib`; the maintainer confirmed that
the app quit without intervention. That candidate was **not published**.

The correction rebuilds only the Qt 6.12.0 Cocoa plugin with the official
[QTBUG-149612 fix](https://github.com/qt/qtbase/commit/b74d6cb3c5e8418602494ae549b60839d88ef858).
The [version-specific recipe](../../packaging/macos-qt-cocoa/README.md) pins the
source, SDK and patch inputs, keeps accessibility enabled, and describes the
separate signature/notarization steps. The app's tagged Python sources are
unchanged. A source wheel does not contain this native dependency backport.

On the corrected copy, native accessibility observation, consumer-report display,
reopening extraction ranges, 16-to-31 editing, saving/reopening the project, real
Cube extraction (186 views), normal quit, cancellation and subsequent operation
passed. The source diagnostic completed on eight captures at 512 px and correctly
reported zero reconstructed models. This is successful diagnostic execution, not
successful 3D reconstruction. Original user preferences remained byte-identical.

The final recipe-built plugin was separately signed and notarized. Apple accepted
submission `b9c661ef-4a52-44cc-870c-827d74a55da0`; the new ticket was stapled and
validated. Gatekeeper accepts the re-extracted ZIP as **Notarized Developer ID**.
All 3,854 payload files matched the tested bundle after packaging. The final Mac
ZIP is 329,044,097 bytes, SHA-256
`73de4351a924454608bc681b1546c29ecf78e0d263980f2cd46cf1b854d5d7f9`.
Its Qt runtime requires macOS 14.4 or later on Apple Silicon. Actual native testing
was on the maintainer's Mac, not on a fresh macOS 14.4 installation.

### Windows downloaded binary

The unchanged Windows ZIP has SHA-256
`8de3c168a1b8089759b131459250d8c304d36792fdf6058670ad7644f98b9f16`.
It was downloaded directly from the draft and tested on Shadow Windows 11 build
26200. A synthetic video produced 96/186 views for the 16/31 plans, with all 96
common JPEGs and 16 common masks byte-identical. The actual staircase JPEG retained
its decoded pixels in flat PNG export. Native RealityScan/Postshot reports imported,
including 118 Postshot retained views and five mapped mask warnings; text and binary
COLMAP memberships agreed. The failed-run log alone left membership unknown.

Studio import/preview, per-project Cube/256-pixel settings, save/quit/reopen,
24-view extraction, cancellation, and rerunning after cancellation passed.
The standard small segmentation model was provisioned into a fresh cache and CPU
inference passed. Automatic device selection explicitly reported **PyTorch
2.15.0+cpu, CUDA unavailable**. This Windows asset does not provide CUDA inference;
GPU qualification requires a separate CUDA-enabled distribution. The original
360 video was tested on Mac, not copied to Shadow for this Windows fixture.

This record distinguishes observed binary checks from the remaining qualification
below. The tag workflow produced a draft; the corrected Mac dependency is a documented
post-build operation, like Developer ID signing. CI on the recipe branch does not
itself run the native accessibility regression or build the backport.

| Check | Required evidence |
| --- | --- |
| macOS artifact | Downloaded CI ZIP, Developer ID signature, Apple notarization/stapled ticket, Gatekeeper result and final ZIP fingerprint. |
| macOS CLI | Version/help, real extraction, destination masks, 16/31 common-output identity and real consumer-report imports. |
| Studio | Launch, project save/reopen, diagnostics, report display and cancellation/close; record any untested cases. |
| Windows artifact | Exact downloaded x64 ZIP, launch/extraction, masks, persistence and cancellation on Shadow; CUDA qualification recorded separately. |
| Distribution | Clean-machine/browser first-launch status, model/tool provisioning and bundled dependency notices. |

Real media remain on their original volume. Temporary downloads, extracted bundles and acceptance outputs are grouped in one dated external-disk workspace, with a separate cleanup approval at the end.

### Final archive regression

The full private frozen-CLI harness was rerun against the re-extracted corrected
Mac ZIP. It passed version/help, real 16/31 exports for both mask profiles, 96
byte-identical common JPEGs and 16 common masks per profile, flat decoded-pixel
identity, native report imports, invalid-input preflight, fresh rerun folders,
CPU AI, interruption exit 130 and unchanged original source metadata. The actual
final Studio also reopened reports and ranges and completed a 186-view extraction.

## Publication limits

Publish only after the applicable checks pass, with accurate artifact-specific notes. An explicitly accepted feedback preview may retain disclosed qualification gaps, but is not stable-release certification. In particular, a successful RealityScan/Postshot run on Shadow does not qualify 360 Extractor's Windows executable or CUDA inference.

The historical intermittent Windows native shutdown crash has not been conclusively explained. Broad camera/GPS correctness, complete-scene geometry, mask effects and repeatability remain separate investigations. The staircase still has fragmented RealityScan models; 31 captures enabling Postshot training does not establish a universal sampling default.

Autosave/recovery, persistent manual mask corrections and graphical selection editing remain subsequent product work; they are not claimed by 4.1.0.
