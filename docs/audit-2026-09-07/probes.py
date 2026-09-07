"""Read-only application audit probes. All media/config outputs stay in a temp dir.

Run from the repository: python docs/audit-2026-09-07/probes.py
These probes document current behavior; they are not regression acceptance tests.
"""
import copy
import json
import logging
import os
from pathlib import Path
import struct
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
import cv2
import numpy as np
from extractor360.core.job import Job
from extractor360.core.processor import ProcessingWorker
from extractor360.core.settings_manager import SettingsManager
from extractor360.utils.file_manager import FileManager
from extractor360.utils.camm_parser import parse_camm_data
from extractor360.utils.gpmf_parser import GPMFParser
from extractor360.utils.gpx_parser import parse_gpx_data

results = {}


def record(key, fn):
    try:
        results[key] = fn()
    except Exception as exc:
        results[key] = {"exception": type(exc).__name__, "message": str(exc)}


def core_probe(base, name, overrides, failing_write=False):
    folder = base / name
    folder.mkdir()
    source = folder / "source.png"
    cv2.imwrite(str(source), np.full((64, 128, 3), 120, np.uint8))
    settings = copy.deepcopy(SettingsManager.DEFAULT_SETTINGS)
    settings.update(resolution=32, layout_mode="cube", custom_output_dir=str(folder))
    settings.update(overrides)
    worker = ProcessingWorker([Job(str(source), settings=settings)])
    events = []
    worker.job_finished.connect(lambda idx: events.append(["finished", idx]))
    worker.job_error.connect(lambda idx, err: events.append(["error", idx, err]))
    if failing_write:
        with patch("extractor360.core.processor.exif_writer.save_image_with_exif", side_effect=OSError("simulated disk full")):
            worker.run()
    else:
        worker.run()
    worker.io_pool.shutdown(wait=True)
    output = folder / "source_processed"
    manifest = json.loads((output / "manifest.json").read_text()) if (output / "manifest.json").exists() else {}
    return {"error_count": worker.error_count, "events": events,
            "actual_images": len(list(output.glob("*.jpg"))),
            "reported_images": manifest.get("extraction", {}).get("images_written"),
            "output_exists": output.exists(),
            "unexpected_source_output": (folder / "source_processed").exists()}


with tempfile.TemporaryDirectory(prefix="360-audit-") as tmp:
    base = Path(tmp)
    record("filemanager_ignores_imwrite_false", lambda: FileManager.save_image(str(base / "missing" / "out.jpg"), np.zeros((4, 4, 3), np.uint8)))
    record("async_write_failure", lambda: core_probe(base, "write_error", {}, True))
    record("custom_filename_collision", lambda: core_probe(base, "collision", {"naming_mode": "custom", "image_pattern": "same"}))
    record("zero_cameras", lambda: core_probe(base, "zero", {"layout_mode": "ring", "camera_count": 0}))
    record("invalid_camera_selection", lambda: core_probe(base, "inactive", {"active_cameras": [99]}))
    record("nonexistent_output_fallback", lambda: core_probe(base, "fallback", {"custom_output_dir": str(base / "requested_but_missing")}))
    record("gpmf_byte_type", lambda: GPMFParser()._unpack_values(b"\x01", "B", 1, 1))
    record("camm_standard_type5", lambda: parse_camm_data(struct.pack("<HHddd", 0, 5, 48.0, 2.0, 100.0), 1))
    record("camm_standard_type6", lambda: parse_camm_data(struct.pack("<HHdidd7f", 0, 6, 1400000000., 3, 48., 2., 100., 1., 1., 0., 0., 0., 1.), 1))
    record("gpx10_namespaced", lambda: parse_gpx_data('<gpx xmlns="http://www.topografix.com/GPX/1/0"><trk><trkseg><trkpt lat="48" lon="2"><time>2026-01-01T00:00:00Z</time></trkpt></trkseg></trk></gpx>'))
    # Invalid JSON root uses a disposable SettingsManager configuration.
    with patch.object(SettingsManager, "load_settings", lambda self: None):
        SettingsManager._instance = None
        manager = SettingsManager()
    manager.config_dir = base
    manager.config_file = base / "config.json"
    manager.config_file.write_text("[]")
    record("settings_json_array", manager.load_settings)
    manager.settings = copy.deepcopy(SettingsManager.DEFAULT_SETTINGS)

    from PySide6.QtWidgets import QApplication
    from extractor360.ui.main_window import MainWindow
    from extractor360.ui.preview_widget import PreviewWorker
    from extractor360.ui.workers import ProcessingBridge
    from extractor360.ui.log_panel import LogPanel
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    # Avoid thumbnail threads: the start button only requires one Job.
    window.jobs = [Job(str(base / "dummy.png"))]
    record("gui_start", window.start_processing)
    results["gui_stuck_processing_after_failure"] = window.is_processing
    results["bridge_contract"] = {name: hasattr(ProcessingBridge, name) for name in ["log_message", "all_finished", "finished", "attach"]}
    results["worker_contract"] = {name: hasattr(ProcessingWorker, name) for name in ["start", "cancel", "run", "stop"]}
    results["log_contract"] = {name: hasattr(LogPanel, name) for name in ["append_log", "log"]}
    window.is_processing = False
    window.jobs = []
    record("blur_slot_dict", lambda: window._on_blur_analysis_finished({"average": 20., "min": 10., "max": 30., "details": []}))
    results["missing_gui_settings"] = sorted(set(SettingsManager.DEFAULT_SETTINGS) - set(window.get_settings_from_ui()))
    results["custom_pattern_widgets_have_no_parent"] = window.image_pattern_input.parent() is None and window.mask_pattern_input.parent() is None
    results["initial_preset_vs_layout"] = [window.preset_combo.currentText(), window.layout_combo.currentData(), window.cam_count_spin.isEnabled()]
    # Loading a selected job must not replace its settings midway through signals.
    settings = copy.deepcopy(SettingsManager.DEFAULT_SETTINGS)
    settings.update(ai_custom_classes="dog", blur_filter_enabled=True,
                    adaptive_mode=True, export_telemetry=True, active_cameras=[1],
                    ai_model="yolo26l-seg.pt", interpolation_mode="lanczos", image_pattern="custom")
    card = SimpleNamespace(job=Job("dummy.png", settings=settings), refresh=lambda: None)
    window._selected_cards = [card]
    window.update_preview_display = lambda: None
    window.update_estimate = lambda: None
    window.set_ui_from_settings(settings)
    results["selection_settings_mutations"] = {k: [v, card.job.settings.get(k)] for k, v in settings.items() if card.job.settings.get(k) != v}
    window._selected_cards = []
    window.input_360_toggle.setChecked(False)
    window.apply_preset("COLMAP Calibrated Rig")
    results["colmap_preset_from_flat"] = window.get_settings_from_ui()["is_360"]
    window.preset_combo.setCurrentIndex(3)
    window.set_ui_from_settings(copy.deepcopy(SettingsManager.DEFAULT_SETTINGS))
    window.show()
    for drawer in [window.adv_camera, window.adv_quality, window.adv_ai, window.adv_export]:
        drawer.setExpanded(True)
    app.processEvents()
    window.grab().save(str(Path(__file__).with_name("studio-audit.png")))
    results["window_render_size"] = [window.width(), window.height()]
    log = window.log_panel
    before = log.log_text.toPlainText()
    logging.getLogger("Application360").info("audit-duplicate-marker")
    app.processEvents()
    results["duplicate_log_occurrences"] = log.log_text.toPlainText()[len(before):].count("audit-duplicate-marker")
    log.clear_logs()
    for idx in range(600):
        log.log(f"line {idx}")
    results["log_limit"] = {"block_count": log.log_text.document().blockCount(), "retained_lines": log.log_text.toPlainText().count("[INFO]")}
    # A constant image with AI disabled still obtains a colored synthetic overlay.
    image_path = base / "uniform.png"
    cv2.imwrite(str(image_path), np.full((64, 128, 3), 120, np.uint8))
    scores = []
    for overlay in [False, True]:
        preview = PreviewWorker(str(image_path), {"is_360": False, "ai_mode": "None", "nadir_mask_enabled": False}, "Down", show_ai_mask=overlay, show_nadir_disc=False)
        preview.signals.blur_score.connect(scores.append)
        preview.run()
    results["blur_uniform_without_then_with_fake_overlay"] = scores
    window.preview_widget._debounce.stop()
    window.preview_widget.threadpool.waitForDone()
    window.close()
    logging.getLogger().removeHandler(log.log_handler)
    logging.getLogger("Application360").removeHandler(log.log_handler)
    app.processEvents()

target = Path(__file__).with_name("probe-results.json")
target.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n")
print(json.dumps(results, ensure_ascii=False, indent=2))
