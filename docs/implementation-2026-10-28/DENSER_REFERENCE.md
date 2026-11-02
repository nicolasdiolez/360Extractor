# Denser staircase reference — 2026-10-28

Follow-up to [source preflight validation](PREFLIGHT_VALIDATION.md), using development commit `d93b48c6348d2b307b994fc989b1b125cfc5238c`. This is an experiment on the existing Bobillot staircase video, not a change to the product's 16-capture / 512 px diagnostic limits. No new model, dependency, release or source-media copy was needed.

## Finding

The earlier zero-registration results do **not** establish that this source is unusable. A denser 1024 px sample reconstructs one model spanning 36 of 64 physical captures, plus two isolated two-capture fragments. The first 16 densely spaced captures also reconstruct together at 1024 px. The last 16 do not initialize a model at either tested resolution.

Resolution and temporal spacing both matter in this example. At 512 px, 64 captures produce a superficially positive total of 26 registrations, but only 13 independent two-capture fragments. Showing that percentage alone would be misleading. The largest model, its temporal coverage and fragmentation are more useful evidence.

## Controlled setup

Source: 344 frames, 7680×3840 pixels, 25 fps, read in place. The 64 source frames are `round(i * 343 / 63)` for `i = 0..63`, spaced by five or six frames (0.20–0.24 s). The previous eight-frame 1024 px sample is exactly every ninth capture in this set. The first and last windows use the first/last 16 captures from the same set, covering 0–3.28 s and 10.44–13.72 s respectively.

The normal processing pipeline exported only this explicit selection, using a separate experimental job and exclusions for the other source frames. Existing user jobs and their decisions were not modified. Every selected capture has six cube views, 90° FOV, JPEG quality 95, fixed intrinsics and rig transforms, no AI, the existing Down nadir disc, and no blur/motion rejection. Confirmed indexes, timestamps and source size/mtime were checked. Subsequent cases reuse these pixels; 512 px cases resize with area interpolation and nearest-neighbor mask scaling, as in the product diagnostic.

COLMAP 4.2.0 CPU on macOS arm64, four threads, at most 4096 SIFT features per view, sequential overlap 10, quadratic overlap disabled, random seed 0 and the same mapper settings as the earlier pilots. Rigs are configured before matching. The sequential overlap remains a count of neighboring captures, so its temporal span changes with sampling density. Each experiment starts a fresh database/workspace; no matching or reconstruction state is carried between cases.

The full reference has a separate 15-minute / monitored 1 GiB experiment bound. It does not bypass or expand the application diagnostic's limits. The ordinary 16-capture/512 px window tests run through the existing `AlignmentRunner` and its normal limits. Before work, the internal disk had about 25 GiB free.

## Results

Counts below refer to physical captures, not the six virtual images assigned each rig pose. “Largest model” is one reconstruction, not the union of overlapping alternatives. In these cases all returned models are disjoint.

| Selection | Resolution | Captures in any model | Largest model | Models | Alignment time |
| --- | ---: | ---: | ---: | ---: | ---: |
| Previous eight, full video | 1024 px | 0/8 | 0 | 0 | 22.78 s |
| 64, full video | 1024 px | 40/64 | **36** | 3 | 175.62 s |
| Same 64, full video | 512 px | 26/64 | **2** | 13 | 107.18 s |
| First 16, 0–3.28 s | 512 px | 10/16 | **2** | 5 | 21.50 s |
| Same first 16 | 1024 px | **16/16** | **16** | 1 | 37.53 s |
| Last 16, 10.44–13.72 s | 512 px | 0/16 | 0 | 0 | 14.47 s |
| Same last 16 | 1024 px | 0/16 | 0 | 0 | 32.14 s |

The 64-capture reference took **193.42 s including source extraction**. Other times start from already extracted images and include preparation/alignment/model export; they are not comparable end-to-end performance benchmarks. Each case ran once. The two local windows were exploratory follow-ups after observing the full reference, not a held-out validation set.

The principal 1024 px reference model covers all 36 sampled captures from frame 0 through frame 191 (0–7.64 s), contains 3517 sparse points, and has mean track length 3.157 observations and mean reprojection error 1.146 px. Its other models contain only frames `[218, 245]` and `[256, 261]`, with 66 and 60 points respectively. Their mean track length is two. The first-window 1024 px model contains 1370 points with mean track length 3.056 and mean reprojection error 1.141 px.

These residuals describe the optimizer's internal fit. They do not measure metric accuracy, validate moving-person masking or prove that the reconstructed surfaces are correct. Rig registration can assign poses to all six views even when some have few or no triangulated observations. A two-capture fragment is not evidence of a continuous reconstruction of the sequence.

## Direction supported by the evidence

1. **Report the largest individual model and its time coverage prominently.** Separate two-capture fragments from longer models, retain the per-model detail and show where continuity breaks. A connected group formed by overlapping alternatives must not be presented as one verified reconstruction. Do not turn total registered captures or low reprojection error into a quality score.
2. **Evaluate a bounded local-window mode at 1024 px.** It should show which time range was tested and retain an explicit global time/space budget. The first-window result supports this direction; it does not justify silently raising every diagnostic's cost or calling the whole video valid after one successful window.
3. **Inspect difficult intervals separately.** The final window remains unresolved at both resolutions. More frames or resolution alone are not a demonstrated universal fix. Check actual overlap, blur, repetitive surfaces, source orientation and operator/mask coverage before attributing a cause or advising deletion.
4. **Qualify these choices on additional existing scenes before changing defaults.** This single staircase is evidence against a global 8–16-frame/512 px diagnostic as a rejection gate, not a calibrated threshold or a comparison of reconstruction engines.

The recommended rig order and fixed known poses match the [COLMAP 4.2 rig documentation](https://github.com/colmap/colmap/blob/4.2.0/doc/rigs.rst). COLMAP's [capture and reconstruction guidance](https://colmap.github.io/tutorial.html) also distinguishes texture, overlap and viewpoint diversity, and recommends investigating matching/initialization when registration fails. Those are hypotheses to investigate here; the tests above do not identify a single physical cause.

## Evidence and scope

Private evidence is retained under the ignored project folder `plans/application360-reference-2026-10-28/`: reports, confirmed indexes, source identity/settings, COLMAP commands/logs, feature/pair statistics, compact poses, a sparse PLY reference and a temporal comparison chart. Temporary image sets, databases, full reconstruction workspaces and helper scripts are moved to Trash under the existing cleanup authorization. Original videos and earlier evidence remain in place.

This work measures sparse alignment. It does not produce or qualify a dense mesh, Gaussian splat, clean-machine binary, Windows/GPU execution or geometric ground truth. No application behavior changed in this follow-up.
