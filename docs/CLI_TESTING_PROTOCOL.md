# Acceptance protocol — Studio, CLI and release binaries

Use this protocol for the current correction branch before promotion to a public release. It complements automated tests with real-media checks. Results from earlier audits are dated evidence, not proof that a new candidate passed.

## Preparation and evidence

Install from the [README](../README.md#install-from-source) using an isolated environment and the exact candidate branch/commit. Use Python 3.13 for the locally qualified macOS arm64 profile, or record the different interpreter/platform you test. A Python 3.8 environment and installing only requests/tqdm are insufficient.

Record:

- Candidate commit, app version, OS/architecture, Python/dependency profile or binary asset checksum.
- Camera model, codec, source dimensions/duration/frame rate, stitching software and known GPS reference if relevant.
- Command or settings, run folder, manifest state/counts, observed behavior and pass/fail/blocked for each applicable case.

Choose a short stitched 360 clip, a flat video/image, and a longer representative production clip. Include real operator/tripod footage for masks and a known GPS sample for telemetry. Keep originals unchanged and use a separate destination such as `acceptance-output`. Replace example paths below with your files.

```sh
python check_env.py --mode all
python check_env.py --mode core --telemetry
python -m pytest -q
```

The telemetry check requires ffmpeg and ffprobe. A missing optional tool blocks that feature's qualification; it does not establish failure of basic extraction. Use offscreen Qt test configuration if the environment has no display, as described in [CONTRIBUTING.md](../CONTRIBUTING.md).

## Studio checks

| Case | Action | Expected evidence |
| :--- | :--- | :--- |
| Import/layout | Open Studio, add the 360 clip, select Cube, inspect every face, then add flat media and disable 360 input for that card. | Responsive previews; Cube face labels correct; flat retains its proportions. Additional imports remain available. |
| Per-job settings | Give two cards different resolutions/quality, select both and change only interval. Inspect each separately. | Only edited values are shared; other settings remain per-job. Record any misleading mixed-value display. |
| Persistence | With no selected job, set defaults; close and reopen Studio, then add media. | Defaults persist. A saved queue is not expected: project-file persistence is not implemented. |
| Extraction | Run a short Cube job with filters/AI disabled; open its output from the card. | Successful card state, completed manifest, six images per selected source frame, correct folder. |
| Rerun | Run the same job again. | New numbered folder; prior files unchanged. |
| Masks | Enable AI on Down plus the nadir disc; inspect image and mask at full size. | Matching dimensions and alignment; black ignore/white keep with default convention; no unwanted masking on other faces. Precision must be assessed visually. |
| Cancel/close | Start a longer job, cancel, relaunch, then close during processing. | Cancellation/partial output identified, next run works, normal process exit. Long native decoder/GPU calls can delay cancellation. |
| Display | Test your normal window size, scaling and keyboard navigation. | Important controls remain reachable; record clipping, focus or usability defects. |

Presets are starting points; they do not prove compatibility with the software named in their labels. Do not expect automatic timeline playback, IMU leveling or native stitching.

## CLI checks

### Cube, selected views, flat and configuration

```sh
360extractor --input videos/trip.mp4 --output acceptance-output/cube --layout cube --resolution 512 --interval 1 --format png
360extractor --input videos/trip.mp4 --output acceptance-output/selective --layout cube --resolution 512 --active-cameras "0,2"
360extractor --input clips/interview.mp4 --output acceptance-output/flat --flat
360extractor --config config.json
```

Use the config example in [SETTINGS.md](SETTINGS.md#configuration-files). Each destination is a parent containing `source_processed` and later numbered run folders. Check `images.jsonl` against actual files and confirm `manifest.json` state/counts. Cube has Front/Right/Back/Left/Up/Down; the selective case has Front/Back only. Flat has one view per accepted sample at native dimensions.

Do not derive exact output counts solely from duration × FPS: decoder timestamps, the interval and active filters affect sampling. For every accepted frame in the unfiltered Cube case, six indexed views are expected. Run twice and verify that the first dataset's contents are unchanged.

### AI, nadir and motion

```sh
360extractor --input videos/trip.mp4 --output acceptance-output/masks --layout cube --resolution 512 --ai-mask --ai-mask-cameras Down --nadir-mask
360extractor --input videos/trip.mp4 --output acceptance-output/skip --layout cube --resolution 512 --ai-skip
360extractor --input videos/trip.mp4 --output acceptance-output/motion --layout cube --resolution 512 --adaptive --motion-threshold 0.5
```

Compare masks against the real subjects, including limbs and tripod boundaries. Mask generation does not reconstruct the hidden background. AI skip is per view, so partial camera sets can be expected. Compare motion selection with a fixed-interval baseline; fewer images are only expected if the actual motion/threshold warrants rejection. Record CPU/MPS/CUDA from logs; a CPU smoke test does not qualify GPU operation.

### Failure paths

- Try a nonexistent input: expect nonzero exit and an explicit error.
- Try `--resolution 0` with an existing input: expect exit 2 and no exported images (the parent destination may exist).
- Try a custom multi-view video name without `{camera}` or `{frame}`: expect a naming failure before image writes.
- Interrupt a long run: expect handled CLI interruption to return 130 and partial output to remain identifiable. In Bash read `echo $?` immediately; in PowerShell read `$LASTEXITCODE` immediately.
- Check that missing GPS is reported separately: overall extraction can succeed without geotags. Never infer GPS success from exit 0 alone.

A forced process kill/power cut can leave a `running` manifest. There is no automatic resume or guarantee of a two-file atomic transaction across that failure.

## GPS and reconstruction qualification

With footage whose GPS/time reference is known:

```sh
360extractor --input videos/trip.mp4 --output acceptance-output/gps --layout cube --resolution 512 --export-telemetry
```

Inspect manifest telemetry status and the output EXIF. Compare several positions/times against known reference points, including trace gaps. Latitude/longitude are expected only where valid GPS exists. Altitude is omitted unless the source is confirmed orthometric and `gps_altitude_reference` is set accordingly; relative altitude is always omitted. Do not expect IMU or GPS-derived optical heading. GPS9 is unsupported. Sidecar start alignment is an assumption that needs verification for each source.

For COLMAP, use a clip with enough movement, overlap and texture:

```sh
360extractor --input videos/trip.mp4 --output acceptance-output/colmap --layout cube --export-colmap --nadir-mask
python acceptance-output/colmap/trip_processed/colmap/reconstruct.py
```

Verify the installed COLMAP has `rig_configurator`, then inspect its log/database/model: correct camera grouping, separate masks, configured rig, registered captures and reconstruction geometry. The runner's default workspace must not exist already; pass a new workspace path for another attempt. Merely creating calibration files does not pass reconstruction acceptance. Test RealityScan/Metashape/Postshot import separately if that is the intended workflow.

## Release decision

For the exact candidate, record pass/fail/blocked with artifact paths for each applicable case. Fix blocking regressions. Disclose unsupported features rather than marking them passed. Require CI on the final commit, then follow the [release procedure](../CONTRIBUTING.md#preparing-and-publishing-a-release).

Repeat launch/extraction/AI/persistence/cancellation using the **downloaded draft binaries** on clean target machines without the developer environment. Record OS, architecture and asset checksum. Qualification of the source checkout alone is insufficient to publish working macOS/Windows binaries.
