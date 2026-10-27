# Studio projects

Development sources provide **Project → New / Open / Save / Save As**, with standard shortcuts (Cmd on macOS, Ctrl elsewhere). Projects use `.360proj` and contain versioned UTF-8 JSON. They reference media in place; saving does not copy videos, images or model weights.

## Saving and reopening

1. Add media and configure each job. Multiple selection applies only the fields you edit.
2. Choose **Project → Save Project** (Cmd/Ctrl+S) and a `.360proj` filename.
3. Open it later with **Project → Open Project** (Cmd/Ctrl+O).

The project preserves queue order, stable job identifiers, each job's settings (active cameras, AI face scope, sampling, mask profile, output and custom model paths), defaults for new media, selected cards at save time and the latest extraction result. The title's `*` indicates unsaved content changes. Open, New and Close offer Save, Discard or Cancel. Failed saves keep the document dirty and the queue intact.

Opening a project does not replace global preferences. A new untitled empty window retains the existing preference-editing behavior. Selection changes alone do not trigger an unsaved-content warning; selection is recorded when you explicitly save.

Project actions are blocked during extraction; Open/Save also wait for blur analysis. Closing stops and drains active work before asking whether to save. Cancelling that dialog keeps Studio usable, but does not restart a cancelled extraction.

## Missing or changed sources

Files inside the project's folder use relative references. Moving that folder together with its media, custom model and exports preserves those references. External files use absolute references. Save As recalculates references without moving anything.

Source identity contains size and modification time. Missing, inaccessible or changed sources remain visible as **Check source**; preview, analysis and extraction require resolution first. Select one card, then **Project → Locate Selected Source**. Reconnect its disk or choose the original at its new location. If size/date differs, Studio asks before accepting it and clears the old result association. It keeps the job identifier and settings; existing outputs remain untouched.

Size/date is a lightweight check, **not a content hash**. Same-size changes with preserved timestamps can go undetected. Foreign-platform absolute paths require relocation. Studio does not search disks or infer replacement files by name.

## Custom models and previous results

Custom model paths and AI settings are saved. A project's trust flag cannot authorize code execution: reopened projects set it to false. For a known model, open **Advanced AI & Target Classes** and explicitly check **Trust this custom model (can execute code)**. Changing models clears trust. A selection containing different models cannot grant trust to all of them together.

The last result retains its run ID, counters, status and output folder when available. The card's Open button opens that folder; its tooltip identifies it as a recorded result whose outputs have not been revalidated. Reopened jobs are **Pending**. Pressing Extract creates fresh run folders. Reopening is not extraction resume and does not verify or repair old outputs. Only the latest result is retained, not a complete run history.

## File integrity and limits

The document is validated before replacing the queue or saving. Unsupported schemas, malformed settings, duplicate jobs/sources and invalid selections produce an error. Correct invalid settings before saving; they are not silently reset. This version does not autosave or create crash-recovery documents.

Saving an existing project writes and flushes a temporary file beside it, then replaces the project. A failed write before replacement preserves the previous file. A document digest detects external changes and asks you to use Save As; this is optimistic conflict detection, not multi-process locking. Power-loss durability depends on the filesystem.

First saves use exclusive publication. On filesystems without hardlinks, such as exFAT, they fall back to exclusive writing; a power loss can leave an incomplete new file. Subsequent saves use staged replacement. Project files are limited to 16 MiB and 10,000 sources; media and models are never embedded.

This Studio format is separate from CLI `--config`. Manual capture exclusion, mask painting, persisted viewport position, complete run history, autosave and verified resume remain future work. [Implementation validation](implementation-2026-10-27/PROJECTS_VALIDATION.md).
