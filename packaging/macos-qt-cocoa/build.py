"""Build the narrowly scoped Qt 6.12.0 Cocoa accessibility backport.

This tool writes only to the explicit work directory. It never changes an app,
signs code, uploads anything or removes an existing workspace.
"""
import argparse
import hashlib
import json
import platform
from pathlib import Path
import shutil
import subprocess
import urllib.request


def sha256(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-dir", required=True, type=Path)
    args = parser.parse_args()
    if platform.system() != "Darwin" or platform.machine() != "arm64":
        parser.error("This qualified recipe requires macOS arm64")
    for command in ("cmake", "ninja", "clang", "tar", "patch", "install_name_tool"):
        if shutil.which(command) is None:
            parser.error(f"Missing build tool: {command}")
    recipe = Path(__file__).resolve().parent
    root = args.work_dir.resolve()
    root.mkdir(parents=True, exist_ok=True)
    inputs = json.loads((recipe / "inputs.json").read_text())
    for name, item in inputs.items():
        path = root / name
        if not path.exists():
            if name == "upstream.patch":
                shutil.copyfile(recipe / name, path)
            else:
                with urllib.request.urlopen(item["url"], timeout=120) as response:
                    with path.open("xb") as destination:
                        shutil.copyfileobj(response, destination)
        if path.stat().st_size != item["bytes"] or sha256(path) != item["sha256"]:
            raise RuntimeError(f"Input verification failed: {path}; preserve and inspect it")

    def run(*command, cwd=root):
        subprocess.run(command, cwd=cwd, check=True)

    sdk = root / "sdk"
    source_parent = root / "source"
    source = source_parent / "qtbase-everywhere-src-6.12.0"
    # Extraction is intentionally not retried into a partially existing tree.
    if not sdk.exists():
        sdk.mkdir()
        run("tar", "-xf", str(root / "qtbase-sdk.7z"), "-C", str(sdk))
    if not source_parent.exists():
        source_parent.mkdir()
        run("tar", "-xf", str(root / "qtbase-source.tar.xz"), "-C", str(source_parent))
        run("patch", "--batch", "-p1", "-i", str(root / "upstream.patch"), cwd=source)
    run("patch", "--batch", "--dry-run", "-R", "-p1", "-i", str(root / "upstream.patch"), cwd=source)
    build = root / "build-recipe"
    run("cmake", "-S", str(recipe), "-B", str(build), "-G", "Ninja",
        f"-DCMAKE_PREFIX_PATH={sdk}", f"-DQTBASE_SOURCE_DIR={source}",
        "-DCMAKE_BUILD_TYPE=Release", "-DCMAKE_OSX_ARCHITECTURES=arm64",
        "-DCMAKE_OSX_DEPLOYMENT_TARGET=14.4")
    run("cmake", "--build", str(build), "--parallel", "4")
    output = root / "libqcocoa-pyinstaller.dylib"
    shutil.copyfile(build / "libqcocoa.dylib", output)
    run("install_name_tool", "-delete_rpath", str(sdk / "lib"),
        "-add_rpath", "@loader_path/../../../..",
        "-change", "@rpath/QtCore.framework/Versions/A/QtCore", "@rpath/QtCore",
        "-change", "@rpath/QtGui.framework/Versions/A/QtGui", "@rpath/QtGui", str(output))
    receipt = dict(qt="6.12.0", architecture="arm64", minimum_macos="14.4",
                   upstream_commit="b74d6cb3c5e8418602494ae549b60839d88ef858",
                   sha256_unsigned=sha256(output), inputs=inputs)
    (root / "build-receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(f"Built {output}; app replacement, signing and notarization are separate steps.")


if __name__ == "__main__":
    main()
