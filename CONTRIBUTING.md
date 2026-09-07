# Contributing to 360 Extractor

## Report a problem

Use the [bug report](https://github.com/nicolasdiolez/360Extractor/issues/new?template=bug_report.yml) or [feature request](https://github.com/nicolasdiolez/360Extractor/issues/new?template=feature_request.yml) template. Include the source camera/media type, operating system, application version **and commit** when testing development code, the command or settings, and expected versus actual output.

The run's `manifest.json` and relevant log messages help explain settings, states and counts. Review paths, timestamps and location metadata before sharing them publicly. A missing manifest can itself be useful evidence of a failure before job initialization.

## Development setup

The correction profile has been tested locally on macOS arm64 with Python 3.13; CI uses Python 3.11. The package declares Python >=3.10, but that declaration does not qualify every interpreter/platform combination. Start from the branch under review rather than assuming the default branch contains it.

```sh
git clone https://github.com/nicolasdiolez/360Extractor.git
cd 360Extractor
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]" -c constraints/security-minimums.txt
python check_env.py --mode all
```

The example selects Python 3.13 explicitly. On Windows, select an installed Python 3.11 or 3.13 interpreter, create the environment with `python -m venv .venv` and activate it with `.venv\Scripts\Activate.ps1` in PowerShell instead. See [README installation](README.md#install-from-source) for model caching and the optional GPU helper. `requirements.txt` installs the application with safety constraints but does not include pytest/ruff/mypy; use the development extra above when contributing.

The ordinary install includes the GUI and AI stack. The processing core is Qt-free, but separately packaged core/gui/ai distributions are still planned. Install FFmpeg/ffprobe when exercising embedded GPS and check them with `python check_env.py --mode core --telemetry`. GPS export does not include IMU orientation.

Run Studio with `python -m extractor360`; pass `--input` or `--config` for CLI mode. `python src/main.py` remains a development launcher.

## Project layout and contracts

| Path | Role |
| :--- | :--- |
| `src/extractor360/core/` | Processing, settings validation, output planning, geometry, AI service, telemetry and reconstruction export. |
| `src/extractor360/ui/` | Studio, Qt controller/bridge, previews and thumbnails. |
| `src/extractor360/utils/` | Parsers, checked writes and bounded subprocess capture. |
| `scripts/` | Release tooling and documentation illustration helpers; not part of the wheel. |
| `tests/` | Automated regression tests. |
| `constraints/` | Security floors and the qualified macOS arm64/Python 3.13 dependency resolution. |
| `docs/` | User guides, acceptance protocol and dated audit evidence. |

`ProcessingWorker` must remain importable without Qt or torch. AIService can import torch when lazy-loaded for AI work. Studio owns a `ProcessingThread` (QThread) through `ProcessingController`; the core reports plain callback events through `ProcessingBridge`. See [ARCHITECTURE.md](ARCHITECTURE.md).

Version is single-sourced from `src/extractor360/core/version.py`. Build configuration derives it dynamically. Do not change historical audit numbers or old release notes to describe current behavior; update the active guides, `[Unreleased]` and the current implementation follow-up.

## Checks before a pull request

```sh
python -m pytest -q
python -m ruff check .
python scripts/check_release.py
```

For offscreen Qt tests, prefix pytest with `QT_QPA_PLATFORM=offscreen` on macOS/Linux; in PowerShell set `$env:QT_QPA_PLATFORM="offscreen"` first. Tests isolate application preferences and library configuration. AI contract tests can skip when the AI dependencies are missing, so a lightweight run is not full AI validation.

CI runs core tests on Ubuntu/macOS/Windows and Qt tests on macOS/Windows. Ruff and the four critical type checks are blocking; whole-project mypy remains informational. The release workflow additionally tests its full installed environment and checks dependency advisories before building. A green CI result does not qualify physical cameras, GPU inference or the distributed binary.

Use a focused branch and a pull request against the intended integration branch. The established development flow targets `dev`; a direct promotion to `main` must be an explicit maintainer decision. Use Conventional Commit prefixes such as `fix:`, `feat:`, `docs:` and `test:`. Add meaningful regression coverage for behavior changes and update [CHANGELOG.md](CHANGELOG.md).

## Preparing and publishing a release

The next version/date has **not** been assigned. The current code still reports 3.3.0 while its changes are under `[Unreleased]`; this is development state, not an already published new version.

1. Run the [acceptance protocol](docs/CLI_TESTING_PROTOCOL.md) on representative real media. Record the exact commit, environment, results and unresolved limits. Resolve blocking failures and require CI on the final candidate.
2. Merge the accepted candidate through review into the release branch (`main` for a public release). Do not merge unrelated local changes or reuse an existing published version.
3. Choose the new semantic version, set `VERSION`, and move the relevant `[Unreleased]` notes to `## [X.Y.Z] - YYYY-MM-DD` with the actual release date. Keep a new `[Unreleased]` section for future work. Update README download/status text only to match artifacts actually available.
4. Run `python scripts/check_release.py`, and preview notes with `python scripts/release_notes.py vX.Y.Z -o release_notes.md`. Here X.Y.Z is a placeholder for the chosen version. Commit and push that preparation and require CI again.
5. Tag that exact accepted commit with the new canonical `vX.Y.Z` tag and push the tag. Do not move an existing release tag. This triggers release validation, macOS/Windows PyInstaller builds and creation of a **draft** GitHub Release.
6. Download and test those exact draft binaries on clean target machines, including real extraction, model provisioning/inference, settings persistence and close/cancel. Verify architecture, third-party license notices and offline/dependency prerequisites. Signed/notarized distribution and Windows/CUDA profiles remain qualification work.
7. If checks pass, publish the draft with accurate notes and limits. If they fail, retain the draft, correct the candidate and rebuild under the project's versioning policy. The workflow refuses to replace an already public release's assets.

A source wheel smoke test does not replace steps 5–6. The workflow prepares a draft; it does not itself approve production readiness. Do not infer download availability from historical screenshots or a local `dist/` directory.

## License

Contributions are licensed under [AGPL-3.0](LICENSE). Distributors must also inventory the licenses/notices of bundled dependencies, model weights and external tools; that inventory is not completed by the application license alone.
