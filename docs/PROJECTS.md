# Studio projects

Development sources provide **Project → New / Open / Save / Save As**, with standard shortcuts (Cmd on macOS, Ctrl elsewhere). Projects use `.360proj` and contain versioned UTF-8 JSON. They reference media in place; saving does not copy videos, images or model weights.

## Saving and reopening

1. Add media and configure each job. Multiple selection applies only the fields you edit.
2. Choose **Project → Save Project** (Cmd/Ctrl+S) and a `.360proj` filename.
3. Open it later with **Project → Open Project** (Cmd/Ctrl+O).

The project preserves queue order, stable job identifiers, each job's settings (active cameras, AI face scope, sampling, mask profile, output and custom model paths), defaults for new media, selected cards at save time and the latest extraction result. Each source also retains its diagnostic mode, capture limit, resolution and optional frame range separately from extraction settings. The title's `*` indicates unsaved content changes. Open, New and Close offer Save, Discard or Cancel. Failed saves keep the document dirty and the queue intact.

Opening a project does not replace global preferences. A new untitled empty window retains the existing preference-editing behavior. Selection changes alone do not trigger an unsaved-content warning; selection is recorded when you explicitly save.

Project actions are blocked during extraction; Open/Save also wait for blur analysis and alignment diagnostics. Closing stops and drains active work before asking whether to save. Cancelling that dialog keeps Studio usable, but does not restart cancelled work.

## Missing or changed sources

Files inside the project's folder use relative references. Moving that folder together with its media, custom model and exports preserves those references. External files use absolute references. Save As recalculates references without moving anything.

Source identity contains size and modification time. Missing, inaccessible or changed sources remain visible as **Check source**; preview, analysis and extraction require resolution first. Select one card, then **Project → Locate Selected Source**. Reconnect its disk or choose the original at its new location. If size/date differs, Studio asks before accepting it and clears the old result association. It keeps the job identifier and settings; existing outputs remain untouched.

Size/date is a lightweight check, **not a content hash**. Same-size changes with preserved timestamps can go undetected. Replacing a source with a different identity also clears its capture exclusions and diagnostic frame range: frame numbers belong to that source. Foreign-platform absolute paths require relocation. Studio does not search disks or infer replacement files by name.

## Custom models and previous results

Custom model paths and AI settings are saved. A project's trust flag cannot authorize code execution: reopened projects set it to false. For a known model, open **Advanced AI & Target Classes** and explicitly check **Trust this custom model (can execute code)**. Changing models clears trust. A selection containing different models cannot grant trust to all of them together.

The last result retains its run ID, counters, status and output folder when available. The card's Open button opens that folder; its tooltip identifies it as a recorded result whose outputs have not been revalidated. Reopened jobs are **Pending**. Pressing Extract creates fresh run folders. Reopening is not extraction resume and does not verify or repair old outputs. Only the latest result is retained, not a complete run history.

## File integrity and limits

The document is validated before replacing the queue or saving. Unsupported schemas, malformed settings, duplicate jobs/sources and invalid selections produce an error. Correct invalid settings before saving; they are not silently reset. This version does not autosave or create crash-recovery documents.

Saving an existing project writes and flushes a temporary file beside it, then replaces the project. A failed write before replacement preserves the previous file. A document digest detects external changes and asks you to use Save As; this is optimistic conflict detection, not multi-process locking. Power-loss durability depends on the filesystem.

First saves use exclusive publication. On filesystems without hardlinks, such as exFAT, they fall back to exclusive writing; a power loss can leave an incomplete new file. Subsequent saves use staged replacement. Project files are limited to 16 MiB and 10,000 sources; media and models are never embedded.

This Studio format is separate from CLI `--config`. Mask painting, persisted viewport position, complete run history, autosave and verified resume remain future work. [Implementation validation](implementation-2026-10-27/PROJECTS_VALIDATION.md).

## Extraction ranges

Select one video, then **Project → Extraction Ranges** or **Extraction ranges for selected video…** in Output & Calibration. Uncheck **Whole source**, add inclusive zero-based frame ranges and save. Overlapping/adjacent ranges are merged. Empty selections and out-of-source endpoints are rejected; **Whole source** explicitly restores unrestricted extraction. **Preview start/end** seeks the selected boundary in Studio. Save the project to retain these decisions. They apply only to that video and are not copied to new media or other selected jobs. Relocation preserves ranges; replacement with a different source identity clears them.

The existing interval controls density within the selected portions. Sampling remains anchored at source start: with a two-frame interval, range 1–7 exports frames 2, 4 and 6 before exclusions/filters, not 1, 3, 5 and 7. Range endpoints are not forced captures. Individual frame exclusions take precedence. All virtual views of a retained frame stay together; the preview labels frames outside the ranges. Source/export diagnostics intersect these ranges with their own diagnostic window.

CLI accepts repeated `--frame-range START END`, for example `--frame-range 0 82 --frame-range 100 150`, or JSON `"included_frame_ranges": [[0, 82], [100, 150]]`. An empty list means the whole source. Ranges require a video with a known decoder frame count. They are recorded in settings/manifest; counts distinguish sampled frames outside ranges from individual exclusions. Storage estimates account for ranges; seconds remain nominal-FPS estimates before filtering. Decoding proceeds from source start to retain timestamp/cadence checks, then stops after the last included endpoint. This is selective export, not a promise of fast seeking through long videos. Earlier decode failures still fail the run.

## Controlled 16-to-31 densification

In **Project → Extraction Ranges**, keep one continuous source-frame range, then **Create 16 from the selected range**. Alternatively paste the original 16 increasing indices, or use **Use last diagnostic's 16** to retain that diagnostic's requested frame list. Save **Sampling: 16 reference captures**, export, then reopen the editor and choose **Sampling: 31 captures (16 reference + 15 midpoints)**. Save the project and export again with the same geometry, resolution, masks and other settings. Each export gets its own fresh folder. The reference remains fixed when toggling modes or reopening the project; it is never recalculated from the new count.

The dense case keeps all 16 reference indices and adds `floor((a + b) / 2)` between each neighboring pair. A gap without an interior frame is rejected rather than producing fewer than 31 or moving the original frames. Creating a new reference from a range is an explicit action and does not skip exclusions. Every planned frame must remain inside the extraction ranges and outside the exclusion list. Conflicts are errors before export. Disable blur/motion rejection and AI **Skip Frame**; nadir and AI mask generation remain available. Switching back to **Sampling: current interval** clears the plan and restores ordinary interval/exclusion behavior.

The plan bypasses the interval value without changing it. Estimates count exactly 16 or 31 captures; compression/storage sizes remain estimates. Preview marks frames outside the plan. Source relocation preserves it; source replacement and adding a new video clear it. Other jobs and global preferences retain their choices. A controlled CLI run requires one input video.

`manifest.json` records the frozen `settings.capture_plan` and `capture_sampling`: method, original/added/requested/fully confirmed frame lists and a `comparison_signature`. The signature should match between the pair: it covers the baseline, other settings and source size/mtime, excluding the mode and output destination. It does not hash the source contents or prove pixel identity. `images.jsonl` identifies each confirmed view as `baseline` or `inserted`, with its decoded timestamp. A capture is confirmed only after all its active views are written; failure/cancellation remains explicit. Both modes regenerate pixels, so preserve the same source, application/environment and settings and check common image/mask hashes for strict comparisons, especially with AI.

For the staircase window, use the checked-in [reference configuration](implementation-2026-11-01/staircase-capture-plan.json):

```sh
360extractor --input /path/to/staircase.mp4 --config docs/implementation-2026-11-01/staircase-capture-plan.json --capture-mode baseline --output /path/to/pair/control16
360extractor --input /path/to/staircase.mp4 --config docs/implementation-2026-11-01/staircase-capture-plan.json --capture-mode densified --output /path/to/pair/dense31
```

Both use 90° Cube, 1024 px, JPEG 95 and the same Down nadir mask. The configuration uses the Postshot profile; repeat both commands with `--mask-profile realityscan` for that consumer. For a new window, `--capture-window START END` creates and records its 16-frame reference; `--capture-baseline` accepts exactly 16 explicit indices. `--capture-mode interval` clears a saved plan. These flags override JSON configuration. Save/reuse the recorded reference to compare later runs.

COLMAP diagnostics still test **at most 16 captures / 128 views**. With a plan active they sample only planned frames within the diagnostic window; they do not qualify the whole 31-capture export. The external RealityScan/Postshot comparison remains a separate step. See the [densification validation](implementation-2026-11-01/DENSIFICATION_VALIDATION.md).

## Alignment diagnostic and capture decisions

Select one source and choose **Project → Alignment Diagnostic**. Two modes are available for a single stitched 360 video:

- **From source — preliminary sample** works before a full export. It selects frames uniformly within the chosen range (or the whole video), independently of the export interval, and extracts only those frames in a supervised helper. The video must have a known frame count and 2:1 equirectangular geometry. Each seek is checked against the decoder's reported frame position. Current cameras, projection, AI scope and nadir policy are retained. Sampling uses JPEG quality 95 at the selected 512 or 1024 pixel resolution, COLMAP masks and no blur/motion rejection or telemetry export; adaptations are recorded in the report. Extraction settings and any previous export association remain unchanged. AI runs on CPU using already available weights; missing models are reported without downloading them. Custom models still require explicit trust.
- **From last completed COLMAP export** uses that export's confirmed index and calibrated perspective rig. It refuses a changed source, partial export or changed extraction settings. It samples included exported captures evenly across their ordered frame indices, retaining existing pixels and masks in reduced copies.

Flat cameras, multiple-source rigs and native panorama reconstruction are outside this diagnostic's scope.

Install COLMAP 4.2 on PATH separately. Choose a maximum of 3–16 physical captures (default 8), 512 or 1024 pixels (default 512), and an output parent folder. Source mode projects directly at the chosen resolution, independently of full-export resolution; export mode never upscales existing pixels. Each run creates a new dated folder, keeps each capture's views together, scales intrinsics and retains mask polarity. Originals are never rewritten. COLMAP uses at most 128 views, four CPU threads and 4096 features per view. Both resolutions share the same five-minute deadline and monitored 256 MiB workspace budget, including source sampling. Higher resolution can reach those limits sooner. Cancellation/time/space failure stops the active process tree; polling can briefly overshoot the disk threshold. Studio drains its preview before starting. The workspace and logs remain available after failure. Nothing is installed or downloaded automatically.

To inspect a portion, enable **Limit to source frames (inclusive)** and enter its first and last zero-based source-frame numbers. **View start / View end** closes the dialog and seeks that exact boundary in Studio, where the frame number and decoded time are visible. Reopen the diagnostic to continue with the saved choices. These bounds deliberately use frame indices rather than inferring them from nominal FPS. A range needs at least three included captures; out-of-source bounds are rejected. Exclusions are respected inside the range. In export mode, only already confirmed captures in that range can be tested. Save the project to retain the choices; new extraction preserves them without limiting the full extraction. Older project files without these optional choices remain readable.

The headline describes the **largest individual model**, its capture count, aligned/tested views, represented/tested directions and source span. Ties are identified, and results containing only one-/two-capture fragments say **Only fragments**, even when the total registered count is high. The model table lists each model's coverage, missing directions, frame/time span, missing tested captures inside that span and fragment status. Select a model to read counts per virtual camera and the exact confirmed tested images absent from that model; those images may belong to another model. These denominators cover confirmed tested views, not filtered-out views, untested directions, measured solid angle or the whole scene. Older reports without registered image identities display unknown direction coverage rather than inferred counts.

Spans use confirmed decoded timestamps; an FPS fallback is labelled, and absent timing stays unavailable. A span does not prove continuous coverage of unsampled intervals. Overlapping alternatives are never combined into one reconstructed model. Changing diagnostic choices or extraction/selection settings marks the displayed result historical without rewriting its measurements.

The capture table distinguishes **registered**, **unregistered**, **excluded**, **not sampled** and **filtered**. Filtered candidates produced no confirmed views before alignment; they are not registration failures. Fewer than three confirmed captures prevents alignment. Counts refer to physical captures, with registered views per model shown separately. COLMAP's recognized no-model outcome is reported as a negative diagnostic; other command errors remain errors. A coarse sample can fail when a larger export aligns. Missing registration alone does not diagnose blur, overlap or mask errors, and is not an instruction to discard a capture. Neither registration percentages, fragments nor low reprojection errors establish geometric accuracy, dense reconstruction or Gaussian Splatting quality.

Select a row and choose **View selected source capture** to inspect its source frame in Studio. Seeking reports an error if the decoder cannot confirm that frame. New export indexes retain decoded timestamps (or an explicit FPS fallback); older indexes show timing as unavailable.

Uncheck **Include** to exclude that exact physical frame, across all virtual views, from future extractions and diagnostics. Full extraction preserves its sampling cadence: the following adjacent frame is not substituted automatically. A new source preflight redistributes its small sample among the remaining included frames. Different export intervals can select entirely different frame indices; exclusions do not define time ranges or exclude neighboring frames. They do not delete existing output. Rechecking includes a frame again if sampling and filters otherwise select it. **Restore all excluded captures** also works when a subsequent export no longer contains those frames. Save the `.360proj` to retain decisions. CLI configuration accepts the same `excluded_frames` list of zero-based frame indices; it does not read `.360proj` directly.

The latest diagnostic summary is embedded in the last result; changing selection marks it historical until rerun. New extraction replaces that last result, while retaining selection decisions. Saved diagnostics are historical measurements, not ongoing validation of files on disk. Diagnostic input size/mtime checks do not hash every pixel. Keep the JSON report and logs for evidence; after use, the diagnostic image copies/database/models can be discarded without affecting the export or project. See the [source preflight validation and real-scene limits](implementation-2026-10-28/PREFLIGHT_VALIDATION.md).
