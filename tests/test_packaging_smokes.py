"""Distribution contracts without building the multi-gigabyte frozen bundle."""
import os
from pathlib import Path
import runpy
import subprocess
import sys
from types import ModuleType, SimpleNamespace

import pytest

import smoke_frozen


ROOT = Path(__file__).resolve().parents[1]


def evaluate_spec(monkeypatch, platform):
    """Run the real spec with inert PyInstaller builders and hook collectors."""
    hooks = ModuleType("PyInstaller.utils.hooks")
    hooks.collect_all = lambda package: ([], [], [])
    hooks.collect_dynamic_libs = lambda package, search_patterns: []
    for name in ("PyInstaller", "PyInstaller.utils"):
        monkeypatch.setitem(sys.modules, name, ModuleType(name))
    monkeypatch.setitem(sys.modules, "PyInstaller.utils.hooks", hooks)
    builds = []

    def builder(kind):
        def build(*args, **kwargs):
            result = SimpleNamespace(kind=kind, args=args, kwargs=kwargs,
                                     scripts=["entrypoint"], pure=["modules"],
                                     binaries=["shared libraries"], datas=["shared resources"])
            builds.append(result)
            return result
        return build

    monkeypatch.setattr(sys, "platform", platform)
    runpy.run_path(str(ROOT / "360Extractor.spec"), init_globals={
        "SPECPATH": str(ROOT), **{name: builder(name) for name in ("Analysis", "PYZ", "EXE", "COLLECT", "BUNDLE")},
    })
    return builds


def test_windows_launchers_share_one_bundle_and_keep_console_diagnostics(monkeypatch):
    builds = evaluate_spec(monkeypatch, "win32")
    assert len([item for item in builds if item.kind == "Analysis"]) == 1
    archives = [item for item in builds if item.kind == "PYZ"]
    assert len(archives) == 1
    executables = [item for item in builds if item.kind == "EXE"]
    assert [(item.kwargs["name"], item.kwargs["console"]) for item in executables] == [
        ("360 Extractor", False), ("360 Extractor CLI", True)]
    assert all(item.args[0] is archives[0] and item.kwargs["exclude_binaries"] for item in executables)
    assert all(item.kwargs["contents_directory"] == "_internal" for item in executables)
    collections = [item for item in builds if item.kind == "COLLECT"]
    assert len(collections) == 1
    assert collections[0].args[:2] == tuple(executables)
    assert collections[0].args[2:] == (["shared libraries"], ["shared resources"])
    assert not any(item.kind == "BUNDLE" for item in builds)
    assert smoke_frozen.frozen_executable(Path("dist"), "win32").name == "360 Extractor CLI.exe"


def test_macos_keeps_one_windowed_application(monkeypatch):
    builds = evaluate_spec(monkeypatch, "darwin")
    executables = [item for item in builds if item.kind == "EXE"]
    assert len(executables) == 1 and executables[0].kwargs["console"] is False
    bundles = [item for item in builds if item.kind == "BUNDLE"]
    assert len(bundles) == 1 and bundles[0].kwargs["name"] == "360 Extractor.app"
    assert smoke_frozen.frozen_executable(Path("dist"), "darwin").as_posix() == "dist/360 Extractor.app/Contents/MacOS/360 Extractor"


def test_frozen_output_is_decoded_from_bytes_without_parent_locale(monkeypatch, tmp_path):
    received = []

    def execute(command, **kwargs):
        received.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0, "Vidéos".encode() + b"\xff", b"\xfe")

    monkeypatch.setattr(smoke_frozen.subprocess, "run", execute)
    assert smoke_frozen.run_launcher(Path("launcher"), ["--version"], tmp_path, {}) == "Vidéos\ufffd"
    assert "text" not in received[0][1] and "encoding" not in received[0][1]


def test_frozen_error_preserves_utf8_and_non_utf8_diagnostics(monkeypatch, tmp_path):
    monkeypatch.setattr(smoke_frozen.subprocess, "run", lambda command, **kwargs:
                        subprocess.CompletedProcess(command, 2, b"", "Échec".encode() + b"\xff"))
    with pytest.raises(RuntimeError, match="Échec\ufffd"):
        smoke_frozen.run_launcher(Path("launcher"), ["--input", "absent"], tmp_path, {})


@pytest.mark.parametrize('version,help_text', [
    ("", ""),
    ("360 Extractor", "--input --output --config"),
    ("360 Extractor 4.0.1\n", ""),
    ("360 Extractor 4.0.1\n", "unrelated help"),
])
def test_frozen_smoke_rejects_success_without_real_console_text(version, help_text):
    with pytest.raises(RuntimeError, match="did not print"):
        smoke_frozen.check_cli_output(lambda option: version if option == "--version" else help_text)


def test_frozen_smoke_accepts_visible_version_and_cli_help():
    smoke_frozen.check_cli_output(lambda option:
                                 "360 Extractor 4.0.1\n" if option == "--version" else "--input --output --config")


def test_installed_smoke_rejects_checkout_import_instead_of_qualifying_source(tmp_path):
    env = dict(os.environ, PYTHONPATH=str(ROOT / "src"))
    result = subprocess.run([sys.executable, str(ROOT / "scripts" / "smoke_installed.py"),
                             "--checkout", str(ROOT), "--work-dir", str(tmp_path)],
                            cwd=tmp_path, env=env, capture_output=True, timeout=30)
    assert result.returncode != 0
    assert "Expected the installed wheel in site-packages" in result.stderr.decode("utf-8", errors="replace")
    assert not list(tmp_path.iterdir())
