# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the 360 Extractor desktop app.

Versioned on purpose: the previous macOS build was produced by hand, so it was
neither reproducible nor buildable in CI. `.github/workflows/release.yml` uses
this exact spec on macOS and Windows.

Build locally with:
    pyinstaller 360Extractor.spec --noconfirm

Produces a one-directory bundle (not one-file): the app carries the whole AI
stack (torch + ultralytics), and a one-file build would unpack ~1 GB into a
temp dir on every launch.
"""
import ast
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all

SPEC_DIR = Path(SPECPATH)  # noqa: F821 — injected by PyInstaller
SRC_DIR = SPEC_DIR / "src"
PKG_DIR = SRC_DIR / "extractor360"

APP_NAME = "360 Extractor"
BUNDLE_ID = "com.nicolasdiolez.extractor360"


def _read_version() -> str:
    """Single-source the version from version.py (never hard-code it here)."""
    tree = ast.parse((PKG_DIR / "core" / "version.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "VERSION":
                    return node.value.value
    raise RuntimeError("VERSION not found in extractor360/core/version.py")


VERSION = _read_version()

# The Qt stylesheet is loaded at runtime relative to the ui package directory,
# so it must land at extractor360/ui/styles.qss inside the bundle.
datas = [
    (str(PKG_DIR / "ui" / "styles.qss"), "extractor360/ui"),
    (str(PKG_DIR / "core" / "reconstruction.py"), "extractor360/core"),
]
binaries = []
hiddenimports = [
    # Imported lazily (only when an AI mode is enabled), so make sure the
    # analyzer keeps it in the bundle.
    "extractor360.core.ai_model",
]

# Ultralytics ships YAML configs it loads at runtime; without collect_all the
# frozen app imports but dies on first inference.
for package in ("ultralytics",):
    pkg_datas, pkg_binaries, pkg_hiddenimports = collect_all(package)
    datas += pkg_datas
    binaries += pkg_binaries
    hiddenimports += pkg_hiddenimports

a = Analysis(  # noqa: F821
    [str(SPEC_DIR / "packaging" / "entrypoint.py")],
    pathex=[str(SRC_DIR)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # Other Qt bindings would clash with PySide6; tkinter is unused.
    # setuptools >=82 no longer provides pkg_resources. An empty residual
    # namespace can still be collected and trigger PyInstaller's legacy hook,
    # which crashes before main(). Preserve the normal ImportError fallback.
    excludes=["tkinter", "PyQt5", "PyQt6", "PySide2", "pkg_resources"],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)  # noqa: F821

exe = EXE(  # noqa: F821
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,  # GUI app: no terminal window on launch
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(  # noqa: F821
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name=APP_NAME,
)

if sys.platform == "darwin":
    app = BUNDLE(  # noqa: F821
        coll,
        name=f"{APP_NAME}.app",
        icon=None,
        bundle_identifier=BUNDLE_ID,
        version=VERSION,
        info_plist={
            "CFBundleName": APP_NAME,
            "CFBundleDisplayName": APP_NAME,
            "CFBundleShortVersionString": VERSION,
            "CFBundleVersion": VERSION,
            "NSHighResolutionCapable": True,
            # The app only reads media the user explicitly picks.
            "NSHumanReadableCopyright": "AGPL-3.0 — Nicolas Diolez",
        },
    )
