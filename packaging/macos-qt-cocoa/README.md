# Qt 6.12.0 Cocoa accessibility backport

The v4.1.0 macOS CI candidate crashed while the native accessibility API inspected
Qt tables in the consumer-report and extraction-range dialogs. The two recorded
crashes were SIGSEGV/SIGBUS inside `libqcocoa.dylib` during accessibility traversal.
Source/offscreen CI and frozen CLI tests did not expose this native Cocoa defect.

This recipe applies the official Qt fix
[`b74d6cb3c5e8418602494ae549b60839d88ef858`](https://github.com/qt/qtbase/commit/b74d6cb3c5e8418602494ae549b60839d88ef858)
for [QTBUG-149612](https://qt-project.atlassian.net/browse/QTBUG-149612) to the
official Qt 6.12.0 source. It prevents native accessibility elements from deleting
interfaces whose lifetime they do not own. Accessibility remains enabled.

Only the Cocoa platform plugin is rebuilt. The app's Python code, Qt Core/Gui and
other dependencies remain those of the original CI artifact. This is a temporary,
explicit dependency backport, not an application-source fix or a general Qt upgrade.
It must not be applied to another Qt version. Prefer a subsequently qualified
official Qt maintenance release containing the fix for future builds.

## Reproduce

Use macOS arm64 with Xcode command-line tools, CMake, Ninja and Python >=3.11.
Check available disk space first. The downloads total about 83 MB; the extracted
SDK/source and build require additional space. Use a dedicated external workspace
when the internal disk is constrained.

```sh
python packaging/macos-qt-cocoa/build.py --work-dir /absolute/path/to/qt-cocoa-fix
```

`inputs.json` pins the URLs, sizes and SHA-256 of the official SDK, source archive
and upstream patch. Existing downloads are verified before use. Invalid downloads
or a patch that cannot be verified fail instead of being discarded. The work
directory is a trusted build workspace: do not edit its SDK or sources. Use a
fresh directory after inspecting a partial-build failure. The checked-in patch
retains its upstream authorship.

The CMake target matches the SDK features: OpenGL, accessibility and session
manager enabled, Vulkan disabled. It compiles arm64 with macOS 14.4 minimum,
matching the original bundled Qt runtime. The SDK's unquoted `-idirafter` option
is adapted for volume paths containing spaces. The final plugin uses the same
relative Qt library references as PyInstaller; it has no SDK-directory runtime
search path. Compiler/SDK differences may change the binary hash.

## Apply to a release candidate

1. Extract a fresh copy of the exact downloaded CI ZIP into an isolated folder.
   Verify its checksum and that its Qt Core/Gui runtime is exactly 6.12.0.
2. Preserve the original plugin's hash. Replace only
   `Contents/Frameworks/PySide6/Qt/plugins/platforms/libqcocoa.dylib` with
   `libqcocoa-pyinstaller.dylib`. The existing code signature is now invalid.
3. Include the patch, recipe, input manifest and Qt license texts with the
   distribution, and make the corresponding source archive available alongside it.
4. Sign all native files and nested bundles from the inside out with Developer ID,
   then sign the app, using hardened runtime and a secure timestamp. Verify the
   signature strictly. Submit the new ZIP for Apple notarization, require Accepted,
   staple and validate its new ticket. A previous notarization does not cover it.
5. Package, hash and re-extract the final ZIP. Verify payload identity and
   Gatekeeper. Exercise the actual Cocoa GUI with accessibility active: open a
   project, read different reports, close the report, open/edit ranges, save,
   extract, quit/reopen and cancel. A successful offscreen run is insufficient.

Record application commit, original/final ZIP hashes, plugin hashes, build receipt,
signing/notarization results and observed GUI behavior in the release acceptance.
Do not move the application tag or replace an already public release's assets.

## Source and licenses

Qt is copyright The Qt Company Ltd. and its contributors. The Cocoa sources carry
their upstream license notices (LGPL-3.0-only / GPL alternatives / commercial).
No copyright notice is removed by this recipe. The source archive identified in
`inputs.json`, the exact patch and this build recipe form the corresponding source
for this rebuilt plugin. Qt's `LICENSES/` directory is included with the release
support material. This recipe does not constitute an inventory of all other
dependencies shipped by the application.
