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

This record is a preparation checkpoint, not a completed binary qualification. CI must pass on the accepted release commit. The tag workflow builds a draft; the downloaded artifacts must then be tested and their SHA-256 fingerprints recorded in the release evidence.

| Check | Required evidence |
| --- | --- |
| macOS artifact | Downloaded CI ZIP, Developer ID signature, Apple notarization/stapled ticket, Gatekeeper result and final ZIP fingerprint. |
| macOS CLI | Version/help, real extraction, destination masks, 16/31 common-output identity and real consumer-report imports. |
| Studio | Launch, project save/reopen, diagnostics, report display and cancellation/close; record any untested cases. |
| Windows artifact | Exact downloaded x64 ZIP, launch/extraction, masks, persistence and cancellation on Shadow; CUDA qualification recorded separately. |
| Distribution | Clean-machine/browser first-launch status, model/tool provisioning and bundled dependency notices. |

Real media remain on their original volume. Temporary downloads, extracted bundles and acceptance outputs are grouped in one dated external-disk workspace, with a separate cleanup approval at the end.

## Publication limits

Publish only after the applicable checks pass, with accurate artifact-specific notes. An explicitly accepted feedback preview may retain disclosed qualification gaps, but is not stable-release certification. In particular, a successful RealityScan/Postshot run on Shadow does not qualify 360 Extractor's Windows executable or CUDA inference.

The historical intermittent Windows native shutdown crash has not been conclusively explained. Broad camera/GPS correctness, complete-scene geometry, mask effects and repeatability remain separate investigations. The staircase still has fragmented RealityScan models; 31 captures enabling Postshot training does not establish a universal sampling default.

Autosave/recovery, persistent manual mask corrections and graphical selection editing remain subsequent product work; they are not claimed by 4.1.0.
