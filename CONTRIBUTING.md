# Contributing to 360 Extractor

Thanks for taking the time to help. Bug reports, feature requests and pull requests are all welcome.

## Reporting bugs and requesting features

Please use the issue templates — [bug report](https://github.com/nicolasdiolez/360Extractor/issues/new?template=bug_report.yml) or [feature request](https://github.com/nicolasdiolez/360Extractor/issues/new?template=feature_request.yml).

For a bug, the two things that make it fixable fastest are:

- **The `manifest.json`** written next to your output images. It records the exact settings used and how many frames/views were extracted or skipped (blur, motion, AI) — it usually answers "why did I only get N images?" on its own.
- **The camera and media type** (GoPro Max, Insta360 X4, DJI, flat video…), since telemetry and stitching differ per vendor.

## Development setup

```bash
git clone https://github.com/nicolasdiolez/360Extractor.git
cd 360Extractor
pip install -r requirements.txt        # or: pip install -e ".[dev]"
python3 check_env.py                   # verifies OpenCV / torch / device
```

FFmpeg (`ffmpeg` + `ffprobe` on your PATH) is required for GPS/IMU telemetry extraction.

Run the app from a plain checkout:

```bash
python3 src/main.py            # GUI
python3 src/main.py --help     # CLI
python -m extractor360         # equivalent, once installed
```

## Project layout

Everything lives in a single package, `src/extractor360/`:

| Path | Role |
| :--- | :--- |
| `extractor360/core/` | Processing core — **must stay Qt-free** so the CLI and servers never load a GUI stack. |
| `extractor360/ui/` | PySide6 GUI. It bridges the core's plain callback events to Qt signals. |
| `extractor360/utils/` | Telemetry parsers (GPMF/CAMM/SRT/GPX), IO helpers. |
| `scripts/` | Release tooling (not shipped in the wheel). |
| `tests/` | pytest suite. |

Two rules worth knowing before you refactor:

- **The core does not import Qt or torch at module level.** The AI stack is imported lazily, only when an AI mode is enabled. A test guards this — please keep it passing.
- **The version has a single source of truth**: `src/extractor360/core/version.py`. `pyproject.toml` derives it dynamically. Never hard-code a version anywhere else.

## Before you open a pull request

```bash
pytest          # the whole suite must stay green
ruff check .    # must be clean
```

Both run in CI (Ubuntu, macOS and Windows).

- Branch from `dev` and target `dev` (`main` is protected and only receives releases).
- Use [Conventional Commits](https://www.conventionalcommits.org/): `feat:`, `fix:`, `perf:`, `docs:`, `test:`, `ci:`, `build:`, `chore:`.
- Add a test when you fix a bug — ideally one that fails before the fix.
- Update the `[Unreleased]` section of [CHANGELOG.md](CHANGELOG.md) for anything user-visible.

## Cutting a release (maintainers)

The release is fully automated from a tag, and guarded so the metadata can never drift:

1. Bump `VERSION` in `src/extractor360/core/version.py`.
2. Turn the `[Unreleased]` CHANGELOG section into a versioned one: `## [X.Y.Z] - YYYY-MM-DD`.
3. Check it locally: `python scripts/check_release.py`.
4. Tag and push: `git tag vX.Y.Z && git push origin vX.Y.Z`.

`.github/workflows/release.yml` then verifies that `version.py`, `pyproject.toml`, the CHANGELOG entry and the tag all agree, builds the macOS and Windows apps with PyInstaller, extracts the release notes from the CHANGELOG, and opens a **draft** GitHub Release with the binaries attached. Review the draft, smoke-test the binaries, then hit Publish.

Tags must use the canonical `vX.Y.Z` form (the older two-component tags like `v3.3` are grandfathered but no new ones are accepted).

## License

By contributing, you agree that your contributions will be licensed under the [AGPL-3.0](LICENSE).
