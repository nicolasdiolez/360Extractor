# Import RealityScan and Postshot evidence

Development sources provide **Project → RealityScan / Postshot Reports…** for one selected source. This reads existing reconstruction evidence; it does not launch either consumer or change extraction settings. The downloadable v4.0.3 preview does not include this feature.

[Native staircase qualification](implementation-2026-11-02/NATIVE_REPORT_VALIDATION.md) exercised the supplied template in RealityScan 2.2 and both COLMAP formats in Postshot 1.1.69. That follow-up corrects zero-based Postshot IDs and documents the failed-project case; it does not certify every consumer version or registration CSV.

Choose the completed extraction folder containing `manifest.json` and `images.jsonl`, then the camera/input report and optionally a consumer log. The folder does not need a `colmap/` subfolder and may use either destination mask profile. Select one component or Image Set to inspect its view states, physical-capture coverage, directions and mask warnings. Filter by state, filename, direction or frame; the view table pages in groups of 200.

## Supported evidence

| Consumer / evidence | What it establishes |
| :--- | :--- |
| RealityScan registration CSV, default **Internal/External camera parameters** format with a `#name` column | Names in the exported registration are retained. Other confirmed images are **not retained in that export**, with unknown cause. Select the intended component and export all its registered cameras. |
| RealityScan input-state report from the supplied template | Each component stays separate. Aligned inputs are retained; enabled but unaligned inputs are rejected **in that component**; disabled inputs are distinguished. Inputs missing from the report remain unknown. |
| Postshot **Image Set → Actions → Export COLMAP database**, text or binary, `images.txt` / `images.bin` | Camera identities present in that Image Set. Other confirmed images are not retained in that exported set; this does not establish whether they were submitted, excluded manually or failed tracking. Camera and point files are not required for identity analysis. |
| Optional UTF-8 log | WARNING/ERROR lines, including mask warnings. Mask filenames are matched against the confirmed index; unmatched warnings remain visible. A log alone leaves all view membership unknown. |

Postshot's camera export is in the **Image Set actions**, distinct from **File → Export Cameras** (animated cameras). See the [Postshot Image Set guide](https://activation.jawset.com/docs/d/Postshot%2BUser%2BGuide/Interface/Scene%2BTree/Image%2BSet). Camera membership does not by itself establish which images participated in a particular training interval or whether their masks were applied correctly.

If Postshot reports **Image Set is empty** and refuses to export camera poses, import its log alone. Coverage remains unknown; partial solver counts are not camera identities. For RealityScan registration CSV, explicitly select **Internal/External camera parameters**. Naming a CLI output `.csv` does not select that format: `exportRegistration` uses current export settings unless a parameter file is supplied.

Use **Save RealityScan report template…**, or the CLI below, to obtain a plain-text report template. Export it from the project with RealityScan's `exportReport` command, for example:

```text
RealityScan.exe -load "project.rsproj" -exportReport "input-states.txt" "360extractor-realityscan.txt"
```

The template iterates components, selects each one and reports its input names and alignment flags. The interpretation follows the [RealityScan image-report documentation](https://rshelp.capturingreality.com/en-US/appbasics/reports_fav_images.htm) and [component selection documentation](https://rshelp.capturingreality.com/en-US/appbasics/reports_fav_components.htm). It is a tab-delimited format; tabs/newlines in names are unsupported. A report with no identifiable component inputs is rejected. Arbitrary HTML reports, `.rsproj` and `.psht` files are not parsed.

## Meaning and limits

- Capture indices, directions, timestamps and mask associations come from the **confirmed extraction index**, never from guessing a filename suffix. Custom filenames are supported.
- Cross-platform paths match exact index-relative names first, then an unambiguous basename. Matching is case-sensitive. Foreign or ambiguous camera names, duplicates, nonfinite/truncated COLMAP records and incomplete exports fail the import. No inferred camera is silently accepted.
- Coverage denominators are exported views/captures, not an assumed six views per capture, and not proof of all images submitted to the consumer. Physical-capture coverage distinguishes at least one retained view from all exported views retained. No union of components is represented as a coherent reconstruction.
- Logs use the **last UTC session header** when present; otherwise they use the entire supplied file. Scope is selected before UTF-8 decoding, so older sessions with a different encoding do not block a valid current session. The selected scope must still be UTF-8. A session may contain several runs. Provide a run-specific excerpt when necessary. Warning-to-mask association is a filename correspondence, not proof of the warning's source run. Tracking counts and partial solver attempts are deliberately not used to infer view membership.
- No supplied log means warnings are **unknown**. No warning in a supplied scope does not prove correct mask persistence or pixel effects.
- Input-file SHA-256 digests, manifest/index digests, export run ID and source size/date are retained with the normalized facts. Names and size/date are not source-pixel verification. No media is copied or reconstructed during import.

## Persistence and CLI

Imports are retained separately from the latest extraction result in `.360proj`. Save the project after import. A new extraction retains them as historical evidence; replacing a source with a different size/date clears its imported reports. Relocation with the same source identity preserves them. Old projects without this optional field remain readable. Derived coverage is recomputed from validated facts on reopen.

**Save selected report as JSON…** writes a standalone receipt and facts to a new filename. Removing an import from the project never deletes its original files. Imports are bounded to 16 MiB per input, 20,000 confirmed views, 128 components, 100,000 memberships and 1,000 warnings, with at most 10 reports per source. Project files retain their existing 16 MiB total limit. Import runs off the UI thread and can be cancelled; project save/replacement and extraction wait for it to end.

```sh
# Native Postshot camera identities plus mask warnings
python -m extractor360 --import-consumer-report postshot \
  --dataset /path/to/completed-export \
  --camera-report /path/to/postshot-colmap/images.txt \
  --consumer-log /path/to/Postshot.log \
  --report-output /path/to/new-postshot-report.json

# RealityScan input-state template, then import its exported report
python -m extractor360 --write-realityscan-template /path/to/new-360extractor-realityscan.txt
python -m extractor360 --import-consumer-report realityscan \
  --dataset /path/to/completed-export \
  --camera-report /path/to/input-states.txt \
  --report-output /path/to/new-realityscan-report.json
```

Omit `--camera-report` for a log-only import with unknown coverage. CLI imports do not edit `.360proj`. Existing output files are never overwritten. The importer is independent of Qt and model libraries. Source tests and format fixtures do not qualify every consumer version, solver result, Windows binary or reconstruction quality.
