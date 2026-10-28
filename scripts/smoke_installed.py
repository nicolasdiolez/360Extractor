"""Qualify an installed wheel outside the checkout, without pytest path injection.

Run with the target environment's Python: python -I smoke_installed.py.
Uses synthetic images, the deterministic nadir mask and a simulated COLMAP
executable. It never loads an AI model or performs a real reconstruction.
"""
import argparse
from importlib import metadata, resources
import json
import os
from pathlib import Path
import site
import subprocess
import sys
import sysconfig
import tempfile


def verify_installation(checkout):
    import extractor360
    from extractor360.core.version import VERSION

    package = Path(extractor360.__file__).resolve().parent
    site_roots = [Path(path).resolve() for path in site.getsitepackages()]
    if not any(package.is_relative_to(root) for root in site_roots) or package.is_relative_to(checkout):
        raise RuntimeError(f"Expected the installed wheel in site-packages, imported {package}")
    distribution = metadata.distribution("360-extractor")
    if distribution.version != VERSION:
        raise RuntimeError("Installed package version differs from distribution metadata")
    if not any(entry.name == "360extractor" and entry.value == "extractor360.main:main"
               for entry in distribution.entry_points if entry.group == "console_scripts"):
        raise RuntimeError("Installed wheel lacks the 360extractor console entry point")
    stylesheet = resources.files("extractor360.ui").joinpath("styles.qss").read_text(encoding="utf-8")
    if not stylesheet.strip():
        raise RuntimeError("Installed wheel stylesheet is empty")
    runner = resources.files("extractor360.core").joinpath("reconstruction.py")
    if not runner.is_file():
        raise RuntimeError("Installed wheel lacks the standalone COLMAP runner")
    print(f"INSTALLED_PACKAGE: {package} ({VERSION})")
    return VERSION


def run_command(command, root, env):
    result = subprocess.run(command, cwd=root, env=env, capture_output=True, timeout=90)
    stdout = result.stdout.decode("utf-8", errors="replace")
    stderr = result.stderr.decode("utf-8", errors="replace")
    if result.returncode:
        raise RuntimeError(f"Installed command exited {result.returncode}:\n{stdout}\n{stderr}")
    return stdout


def completed_dataset(destination):
    manifests = list(destination.rglob("manifest.json"))
    if len(manifests) != 1:
        raise RuntimeError(f"Expected one installed-wheel manifest in {destination}")
    manifest = json.loads(manifests[0].read_text(encoding="utf-8"))
    if manifest["status"] != "completed":
        raise RuntimeError(f"Installed-wheel extraction failed: {manifest}")
    records = [json.loads(line) for line in
               (manifests[0].parent / "images.jsonl").read_text(encoding="utf-8").splitlines()]
    if manifest["extraction"]["images_written"] != len(records):
        raise RuntimeError("Confirmed index count differs from the manifest")
    return manifests[0].parent, records


def exercise(root, version):
    import cv2
    import numpy as np

    env = dict(os.environ, EXTRACTOR360_CONFIG_DIR=str(root / "config"),
               YOLO_CONFIG_DIR=str(root / "ultralytics"), QT_QPA_PLATFORM="offscreen")
    for key in ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV"):
        env.pop(key, None)
    command = [sys.executable, "-I", "-m", "extractor360"]
    expected = f"360 Extractor {version}"
    if run_command([*command, "--version"], root, env).strip() != expected:
        raise RuntimeError("Isolated installed module did not print the expected version")
    console = Path(sysconfig.get_path("scripts")) / ("360extractor.exe" if sys.platform == "win32" else "360extractor")
    if run_command([str(console), "--version"], root, env).strip() != expected:
        raise RuntimeError("Installed console entry point did not print the expected version")
    help_text = run_command([str(console), "--help"], root, env)
    if not all(option in help_text for option in ("--input", "--output", "--config")):
        raise RuntimeError("Installed console entry point did not print CLI help")

    flat = root / "flat.png"
    pixels = np.full((64, 96, 3), 127, np.uint8)
    if not cv2.imwrite(str(flat), pixels):
        raise RuntimeError("Could not create the synthetic flat fixture")
    run_command([str(console), "--input", str(flat), "--output", str(root / "flat-output"),
                 "--flat", "--format", "png"], root, env)
    dataset, records = completed_dataset(root / "flat-output")
    if len(records) != 1 or not np.array_equal(cv2.imread(str(dataset / records[0]["image"])), pixels):
        raise RuntimeError("Installed flat extraction changed the native dimensions or pixels")

    panorama = root / "panorama.png"
    if not cv2.imwrite(str(panorama), np.full((64, 128, 3), 127, np.uint8)):
        raise RuntimeError("Could not create the synthetic panorama fixture")
    run_command([str(console), "--input", str(panorama), "--output", str(root / "cube-output"),
                 "--layout", "cube", "--resolution", "32", "--format", "png",
                 "--nadir-mask", "--export-colmap"], root, env)
    dataset, records = completed_dataset(root / "cube-output")
    if len(records) != 6 or {record["camera"] for record in records} != {"Front", "Right", "Back", "Left", "Up", "Down"}:
        raise RuntimeError("Installed cube extraction did not confirm all six views")
    for record in records:
        image = cv2.imread(str(dataset / record["image"]))
        if image is None or image.shape != (32, 32, 3):
            raise RuntimeError("Installed cube extraction has invalid image geometry")
    down = next(record for record in records if record["camera"] == "Down")
    mask = cv2.imread(str(dataset / down["mask"]), cv2.IMREAD_GRAYSCALE) if down["mask"] else None
    if mask is None or mask.shape != (32, 32) or mask[16, 16] != 0 or mask[0, 0] != 255:
        raise RuntimeError("Installed nadir mask is missing or does not exclude the tripod disc")

    from extractor360.core.job import Job
    from extractor360.core.project import Project, read_project, write_project, source_identity, source_problem
    job = Job(str(panorama), settings={'resolution': 32, 'layout_mode': 'cube', 'active_cameras': [0, 5], 'excluded_frames': [2]},
              result={'status': 'completed', 'output_dir': str(dataset)}, source_identity=source_identity(str(panorama)))
    document = Project(jobs=[job], selected_job_ids=[job.job_id])
    project_file = root / 'capture.360proj'
    write_project(project_file, document)
    reopened, _ = read_project(project_file)
    if (reopened.jobs[0].job_id != job.job_id or reopened.jobs[0].status != 'Pending'
            or reopened.jobs[0].settings['active_cameras'] != [0, 5]
            or reopened.jobs[0].settings['excluded_frames'] != [2]
            or reopened.jobs[0].result['output_dir'] != str(dataset) or source_problem(reopened.jobs[0])):
        raise RuntimeError('Installed project save/open did not preserve source, settings and result')

    from extractor360.core.alignment import sample_frames, summarize
    sample = sample_frames(range(10), [2], 3)
    frames = {frame: {'frame': frame, 'images': [f'Front/frame{frame}.jpg']} for frame in sample}
    report = summarize(frames, sample, set(), {'0': {frames[sample[0]]['images'][0]}})
    if report['registered_captures'] != 1 or report['unregistered_captures'] != 2:
        raise RuntimeError('Installed alignment summary counted virtual views as captures')

    # Exercise the same helper entry used by a frozen app, without Qt or COLMAP.
    # The source process must load this installed package, not the checkout.
    sample_source = root / 'preflight.avi'
    encoder = cv2.VideoWriter(str(sample_source), cv2.VideoWriter_fourcc(*'MJPG'), 10, (64, 32))
    if not encoder.isOpened():
        raise RuntimeError('Could not create the preflight video fixture')
    for value in (20, 60, 100, 140, 180):
        encoder.write(np.full((32, 64, 3), value, np.uint8))
    encoder.release()
    sample_root = root / 'preflight'
    sample_root.mkdir()
    request = sample_root / 'sample-request.json'
    request.write_text(json.dumps({'source': str(sample_source), 'source_identity': source_identity(str(sample_source)),
                                  'settings': {'layout_mode': 'cube', 'resolution': 32, 'exif_intrinsics': False},
                                  'maximum': 3}), encoding='utf-8')
    run_command([str(console), '--diagnostic-sample', str(request)], root, env)
    sampled = json.loads((sample_root / 'sample-result.json').read_text(encoding='utf-8'))
    if sampled['requested_frames'] != [0, 2, 4] or sampled['result']['extraction']['images_written'] != 18:
        raise RuntimeError('Installed preflight helper did not export exactly the requested source frames')

    # Execute the exported, standalone runner in an isolated interpreter. Only
    # COLMAP discovery and its external processes are simulated.
    harness = '''import json, runpy, sys
namespace = runpy.run_path(sys.argv[1])
module = namespace['main'].__globals__
module['shutil'].which = lambda name: 'colmap'
module['subprocess'].run = lambda command, check: print(json.dumps(command))
sys.argv = sys.argv[1:]
namespace['main']()
'''
    workspace = root / "reconstruction"
    output = run_command([sys.executable, "-I", "-c", harness,
                          str(dataset / "colmap" / "reconstruct.py"), str(workspace)], root, env)
    commands = [json.loads(line) for line in output.splitlines()]
    if [item[1] for item in commands] != ["feature_extractor", "rig_configurator", "sequential_matcher", "mapper"]:
        raise RuntimeError("Installed runner did not configure its rig before matching")
    names = (workspace / "images.txt").read_text(encoding="utf-8").splitlines()
    if len(names) != 6 or any(not (workspace / "images" / name).is_file() for name in names):
        raise RuntimeError("Installed runner staged an incomplete confirmed image index")
    if not (workspace / "masks" / (next(name for name in names if name.startswith("Down/")) + ".png")).is_file():
        raise RuntimeError("Installed runner did not stage the separate COLMAP mask")
    print("INSTALLED_SMOKE_OK: site-packages, QSS, module/console CLI, flat pixels, six cube views, nadir mask, project roundtrip, standalone COLMAP staging/order")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkout", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--work-dir", type=Path, help="Parent for temporary synthetic fixtures")
    args = parser.parse_args()
    version = verify_installation(args.checkout.resolve())
    with tempfile.TemporaryDirectory(prefix="360-wheel-smoke-", dir=args.work_dir) as directory:
        exercise(Path(directory), version)


if __name__ == "__main__":
    main()
