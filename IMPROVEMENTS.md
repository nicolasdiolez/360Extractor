# Improvement roadmap

Updated 2026-10-27 after the independent product review. The direction is reliable, inspectable dataset preparation across reconstruction engines, with early alignment feedback and reversible correction of selections/masks. The [September follow-up](docs/implementation-2026-09-07/PROGRESSION.md) remains historical evidence; the [benchmark protocol](docs/BENCHMARK_PROTOCOL.md) now defines how new product choices are evaluated.

## Current order of work

1. **Export contracts and storage:** named mask profiles and rolling output-space checks are implemented in development sources; [validation](docs/implementation-2026-10-27/VALIDATION.md). Complete real Postshot/RealityScan import qualification before claiming end-to-end compatibility.
2. **Evidence before new selection features:** extend the existing-sample pilot with difficult indoor/museum scenes, reviewed masks, repetitions, geometry references and held-out splat views. Include a competitor on its supported platform. The present optical-flow filter has not demonstrated an advantage in the initial pilot.
3. **Saved projects and inspectable selection:** retain source identity, capture timestamps, decisions, manual mask corrections and export settings. Then implement verified resume on a validated index; keep new runs as the safe default.
4. **Early alignment diagnostics:** identify disconnected captures and propose targeted fixes. Use external reconstruction engines and maintain clear provenance instead of building a complete engine/editor.
5. **Target-platform qualification:** Windows/CUDA, consumer imports, clean-machine binaries and measured resource budgets remain release gates.

Native panorama export is an experimental alternative to measure, not a replacement already justified by the pilot. Full dual-fisheye stitching, a general 3D editor, a chatbot and generative pixel replacement are not current priorities.

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
- [ ] Complete bundled component/weight license notices and remaining platform distribution checks. The v4.0.3 macOS prerelease is already signed and notarized; do not treat that completed step as outstanding.
- [ ] Assign the next version/date, finalize notes, require CI and approve tested draft artifacts.

## Further reliability and product work

- [x] Output-volume preflight and rolling next-capture space guard (development sources; downstream reconstruction excluded).
- [ ] Verified resume, full source hashes and recovery behavior.
- [ ] Project/queue saving, complete mixed-value indicators, asynchronous metadata and accessibility/HiDPI acceptance.
- [ ] Annotated segmentation corpus, blur calibration and an optional whole-capture AI skip policy.
- [ ] GPS9/GPSU support, camera fixtures, sidecar offset calibration and validated orientation sources.
- [ ] End-to-end profiling and global RAM/VRAM budgets, bounded caches and staged processing.
- [ ] Separate core/gui/ai distributions and offline provisioning profiles.
- [x] Explicit mask naming/polarity profiles and recorded contracts (development sources).
- [ ] Consumer import qualification and reconstructed-quality comparisons for those profiles.
- [ ] Explicit HDR/ICC/alpha handling.

## Exploratory work, not current functionality

Native dual-fisheye stitching, IMU horizon leveling, generative inpainting, depth-assisted masking and managed cloud execution remain future ideas. JSON is the supported configuration format. CLI headless operation is available; it does not itself provide a cloud service.
