# Improvement roadmap

This is the current roadmap after the September 2026 corrections. The detailed [implementation follow-up](docs/implementation-2026-09-07/PROGRESSION.md) maps all 37 findings to the eight workstreams. The [original audit plan](docs/audit-2026-09-07/PLAN.md) is a dated proposal; its estimates and open boxes do not override the follow-up.

## Implemented in the correction branch

- Studio processing controller, job states, cooperative cancellation, bounded preview/thumbnail work and tested process shutdown.
- Shared validation, new run folders, checked image/mask writes, confirmed output index and state/provenance manifests.
- Per-job settings preservation, preferences, working naming/quality controls and preview/export pixel checks.
- Binary/feathered masks, AI failure propagation, class/face selection, nadir disc and explicit custom-model trust.
- CAMM type 5/6 GPS records, GPMF GPS5 scales/fix/packet times, GPX/SRT sidecars and bounded interpolation/subprocesses. Here CAMM types 5/6 are distinct from GPMF's GPS5/GPS9 record names.
- Virtual COLMAP calibration, rig configuration and separate mask staging through a portable runner.
- Tiled projection, packaged QSS, expanded CI, macOS dependency resolution and release safeguards.

These implementations are not all qualified on real camera/GPU/software combinations. See the [acceptance protocol](docs/CLI_TESTING_PROTOCOL.md) and dated validation evidence.

## Before public release

- [ ] Complete real-media Studio/CLI acceptance and fix any regressions found.
- [ ] Qualify intended camera/codec/GPS combinations and the actual target reconstruction workflow.
- [ ] Validate GPU operation and Windows dependency profiles; produce suitable platform locks.
- [ ] Build and test downloaded release binaries on clean target machines, including model/tool provisioning.
- [ ] Complete bundled component/weight license notices and distribution signing/notarization policy.
- [ ] Assign the next version/date, finalize notes, require CI and approve tested draft artifacts.

## Further reliability and product work

- [ ] Verified resume, full source hashes, disk-space preflight and recovery behavior.
- [ ] Project/queue saving, complete mixed-value indicators, asynchronous metadata and accessibility/HiDPI acceptance.
- [ ] Annotated segmentation corpus, blur calibration and an optional whole-capture AI skip policy.
- [ ] GPS9/GPSU support, camera fixtures, sidecar offset calibration and validated orientation sources.
- [ ] End-to-end profiling and global RAM/VRAM budgets, bounded caches and staged processing.
- [ ] Separate core/gui/ai distributions and offline provisioning profiles.
- [ ] Qualified software-specific export profiles and documented reconstruction outcomes.
- [ ] Explicit HDR/ICC/alpha handling.

## Exploratory work, not current functionality

Native dual-fisheye stitching, IMU horizon leveling, generative inpainting, depth-assisted masking and managed cloud execution remain future ideas. JSON is the supported configuration format. CLI headless operation is available; it does not itself provide a cloud service.
