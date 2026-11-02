"""Exercise the actual frozen launcher and extraction, without source imports."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

import cv2
import numpy as np


def frozen_executable(dist, platform):
    if platform == "darwin":
        return dist / "360 Extractor.app/Contents/MacOS/360 Extractor"
    if platform == "win32":
        return dist / "360 Extractor/360 Extractor CLI.exe"
    return dist / "360 Extractor/360 Extractor"


def run_launcher(executable, arguments, root, env):
    result = subprocess.run(
        [str(executable), *arguments], cwd=root, env=env,
        capture_output=True, timeout=90,
    )
    # Windows' parent locale may be cp1252 while Python/Qt emit UTF-8. Keep
    # diagnostics printable even if a native dependency emits other bytes.
    stdout = result.stdout.decode('utf-8', errors='replace')
    stderr = result.stderr.decode('utf-8', errors='replace')
    if result.returncode:
        raise RuntimeError(f"Frozen launcher exited {result.returncode}:\n{stdout}\n{stderr}")
    return stdout


def check_cli_output(run):
    version = run("--version")
    if not re.search(r"(?m)^360 Extractor \d+\.\d+\.\d+\s*$", version):
        raise RuntimeError(f"Frozen launcher did not print its version: {version!r}")
    help_text = run("--help")
    if not all(option in help_text for option in ("--input", "--output", "--config")):
        raise RuntimeError(f"Frozen launcher did not print CLI help: {help_text!r}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dist", type=Path, required=True)
    parser.add_argument("--model-dir", type=Path, help="Provisioned standard weights for an additional AI extraction")
    args = parser.parse_args()
    executable = frozen_executable(args.dist, sys.platform).resolve(strict=True)

    with tempfile.TemporaryDirectory(prefix="360-frozen-smoke-") as directory:
        root = Path(directory)
        source = root / "flat.png"
        assert cv2.imwrite(str(source), np.full((64, 96, 3), 127, np.uint8))
        env = dict(os.environ, EXTRACTOR360_CONFIG_DIR=str(root / "config"))
        for key in ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV"):
            env.pop(key, None)
        # The application must bring its own Python and shared libraries.
        env["PATH"] = os.environ.get("SystemRoot", "C:\\Windows") + "\\System32" if sys.platform == "win32" else "/usr/bin:/bin"

        def run(*arguments):
            return run_launcher(executable, arguments, root, env)

        check_cli_output(run)
        run("--input", str(source), "--output", str(root / "output"), "--flat", "--format", "png")
        manifests = list((root / "output").rglob("manifest.json"))
        assert len(manifests) == 1, "Frozen executable did not produce one manifest"
        manifest = json.loads(manifests[0].read_text(encoding="utf-8"))
        assert manifest["status"] == "completed", manifest
        images = list(manifests[0].parent.glob("*.png"))
        assert len(images) == 1, "Frozen extraction did not write one image"
        image = cv2.imread(str(images[0]))
        assert image is not None and image.shape[:2] == (64, 96)
        assert np.all(image == 127), "Flat extraction altered the input pixels"
        print("FROZEN_SMOKE_OK: version/help text, completed manifest, one native-size PNG, exact pixels")
        if args.model_dir:
            # Hosted macOS VMs can report MPS available while GPU allocations
            # fail. Qualify portable CPU inference; GPU acceptance is separate.
            env["EXTRACTOR360_DEVICE"] = "cpu"
            env["EXTRACTOR360_MODEL_DIR"] = str(args.model_dir.resolve(strict=True))
            env["YOLO_CONFIG_DIR"] = str(root / "ultralytics")
            run("--input", str(source), "--output", str(root / "ai"), "--flat", "--format", "png", "--ai-mask")
            manifests = list((root / "ai").rglob("manifest.json"))
            assert len(manifests) == 1
            manifest = json.loads(manifests[0].read_text(encoding="utf-8"))
            assert manifest["status"] == "completed", manifest
            records = [json.loads(line) for line in (manifests[0].parent / "images.jsonl").read_text(encoding="utf-8").splitlines()]
            assert len(records) == 1 and records[0]["mask"], records
            mask = cv2.imread(str(manifests[0].parent / records[0]["mask"]), cv2.IMREAD_GRAYSCALE)
            assert mask is not None and mask.shape == (64, 96)
            print("FROZEN_AI_SMOKE_OK: model loading, CPU inference and native-size mask (synthetic input)")


if __name__ == "__main__":
    main()
