"""
Unit and integration tests for 360 Extractor Studio UI components.
Tests 3-column architecture, progressive disclosure drawers, multi-face viewport, and presets.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from extractor360.ui.collapsible_section import CollapsibleDrawer, CollapsibleSection
from extractor360.ui.main_window import MainWindow
from extractor360.ui.preview_widget import PreviewWidget


@pytest.fixture(scope="session")
def qapp():
    """Ensure single QApplication instance for UI tests."""
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    app = QApplication.instance() or QApplication([])
    return app


def test_collapsible_drawer(qapp):
    """Test CollapsibleDrawer toggle behavior."""
    drawer = CollapsibleDrawer("Advanced Optics", is_open=False)
    assert not drawer.isExpanded()
    assert drawer.content_widget.isHidden()

    drawer.setExpanded(True)
    assert drawer.isExpanded()
    assert not drawer.content_widget.isHidden()

    drawer.setExpanded(False)
    assert not drawer.isExpanded()
    assert drawer.content_widget.isHidden()


def test_collapsible_section(qapp):
    """Test CollapsibleSection expand/collapse."""
    sec = CollapsibleSection("Camera Settings", is_open=True)
    assert sec.isExpanded()
    sec.setExpanded(False)
    assert not sec.isExpanded()


def test_preview_widget_face_switcher(qapp):
    """Test PreviewWidget face selection and signals."""
    widget = PreviewWidget()
    assert widget.current_face == "Front"

    changed_faces = []
    widget.face_changed.connect(changed_faces.append)

    widget.set_face("Down")
    assert widget.current_face == "Down"
    assert "Down" in changed_faces
    assert widget.face_buttons["Down"].property("active") is True
    assert widget.face_buttons["Front"].property("active") is not True


def test_studio_main_window_init(qapp):
    """Test MainWindow initialization in Studio mode."""
    window = MainWindow()
    assert window.windowTitle().startswith("360 Extractor")
    assert window.left_panel is not None
    assert window.center_panel is not None
    assert window.right_panel is not None
    assert window.preset_combo is not None
    assert window.preview_widget is not None


def test_studio_settings_sync(qapp):
    """Test settings get/set roundtrip with 100% of parameters."""
    window = MainWindow()
    settings = window.get_settings_from_ui()

    assert "is_360" in settings
    assert "layout_mode" in settings
    assert "resolution" in settings
    assert "fov" in settings
    assert "ai_mode" in settings
    assert "nadir_mask_radius" in settings
    assert "export_colmap" in settings
    assert "exif_intrinsics" in settings

    # Modify settings and apply
    settings["resolution"] = 4096
    settings["fov"] = 110
    settings["nadir_mask_radius"] = 45.0
    settings["ai_mode"] = "Generate Mask"

    window.set_ui_from_settings(settings)
    synced = window.get_settings_from_ui()

    assert synced["resolution"] == 4096
    assert synced["fov"] == 110
    assert synced["nadir_mask_radius"] == 45.0
    assert synced["ai_mode"] == "Generate Mask"


def test_studio_presets(qapp):
    """Test workflow preset application."""
    window = MainWindow()

    # Apply Postshot preset
    window.apply_preset("Postshot (3D Gaussian Splatting)")
    s = window.get_settings_from_ui()
    assert s["layout_mode"] == "cube"
    assert s["ai_mode"] == "Generate Mask"
    assert s["feather_mask"] is False
    assert s["export_colmap"] is False
    assert s["mask_profile"] == "postshot"
    assert s["ai_invert_mask"] is False
    assert s["naming_mode"] == "postshot"

    # Apply RealityScan preset
    window.apply_preset("RealityScan / Metashape")
    s2 = window.get_settings_from_ui()
    assert s2["feather_mask"] is False
    assert s2["naming_mode"] == "realityscan"


def test_studio_media_queue_add_remove(qapp):
    """Test adding media, selecting cards, and removing cards."""
    window = MainWindow()

    with tempfile.TemporaryDirectory() as tmp:
        f1 = Path(tmp) / "video_1.mp4"
        f2 = Path(tmp) / "video_2.mp4"
        f1.write_bytes(b"\x00" * 100)
        f2.write_bytes(b"\x00" * 100)

        window.add_videos_from_paths([str(f1), str(f2)])
        assert len(window.jobs) == 2
        assert len(window._video_cards) == 2

        # Card 2 should be active/selected
        assert window._video_cards[1].isSelected()

        # Remove card 1
        window.remove_video(window._video_cards[0])
        assert len(window.jobs) == 1
        assert len(window._video_cards) == 1


def test_studio_estimate_calculation(qapp):
    """Test real-time estimate calculation."""
    window = MainWindow()
    with tempfile.TemporaryDirectory() as tmp:
        f = Path(tmp) / "test_360.mp4"
        f.write_bytes(b"\x00" * 1000)
        window.add_videos_from_paths([str(f)])

        window.update_estimate()
        assert "images" in window.estimation_label.text()
        assert window.extract_btn.isEnabled()


def test_selection_preserves_unedited_settings_and_models(qapp,tmp_path):
    import cv2
    import numpy as np
    window=MainWindow()
    files=[]
    for index in range(2):
        path=tmp_path/f'view{index}.png'
        cv2.imwrite(str(path),np.zeros((16,32,3),np.uint8))
        files.append(str(path))
    window.add_videos_from_paths(files)
    first,second=window.jobs
    first.settings.update(quality=87,active_cameras=[1],ai_model='yolo26l-seg.pt',pitch_offset=13,ai_mask_cameras=['View_1'])
    second.settings.update(quality=65,ai_model='yolo26x-seg.pt')
    window.select_card(window._video_cards[0])
    current=window.get_settings_from_ui()
    for key in ('quality','active_cameras','ai_model','pitch_offset','ai_mask_cameras'):
        assert current[key]==first.settings[key]
    window.toggle_card_selection(window._video_cards[1])
    window.fov_spin.setValue(100)
    assert first.settings['fov']==second.settings['fov']==100
    assert first.settings['quality']==87 and second.settings['quality']==65
    assert first.settings['ai_model']=='yolo26l-seg.pt'
    window.close()


def test_preferences_persist_without_touching_user_config(qapp):
    from extractor360.core.settings_manager import SettingsManager
    window=MainWindow()
    window.quality_spin.setValue(81)
    assert window.settings_manager.config_file.is_file()
    window.close()
    SettingsManager._instance=None
    assert SettingsManager().get('quality')==81


@pytest.fixture
def settings_window(qapp, tmp_path, monkeypatch):
    """Exercise settings without scheduling unrelated model/preview work."""
    import cv2
    import numpy as np
    monkeypatch.setattr(MainWindow, 'update_preview_display', lambda self: None)
    window = MainWindow()
    paths = []
    for name in ('first.png', 'second.png'):
        path = tmp_path / name
        assert cv2.imwrite(str(path), np.zeros((16, 32, 3), np.uint8))
        paths.append(str(path))
    window.add_videos_from_paths(paths)
    return window


def test_preset_applies_explicit_fields_to_every_selected_job(settings_window):
    window = settings_window
    first, second = window.jobs
    first.settings.update(output_format='jpg', ai_model='trusted-custom.pt', trust_custom_model=True, quality=83)
    second.settings.update(output_format='png', layout_mode='ring', camera_count=8, active_cameras=[7], quality=65)
    window.select_card(window._video_cards[1])
    window.toggle_card_selection(window._video_cards[0])
    window.apply_preset('RealityScan / Metashape')
    for job in window.jobs:
        assert job.settings['output_format'] == 'jpg'
        assert job.settings['layout_mode'] == 'cube'
        assert job.settings['active_cameras'] is None
        assert job.settings['ai_mask_cameras'] == ['Down']
    assert first.settings['ai_model'] == 'trusted-custom.pt'
    assert first.settings['trust_custom_model'] is True
    assert (first.settings['quality'], second.settings['quality']) == (83, 65)


def test_unrelated_edit_preserves_valid_values_and_precision(settings_window):
    window = settings_window
    unusual = dict(fov=160.123456, blur_threshold=5000.12345, sharpening_strength=3.12345,
                   ai_confidence=0.000123, adaptive_threshold=500.12345, interval_value=0.00123,
                   nadir_mask_radius=0.0)
    window.jobs[0].settings.update(unusual)
    window.jobs[1].settings.update(blur_threshold=9000.54321, fov=175.54321)
    window.select_card(window._video_cards[1])
    window.toggle_card_selection(window._video_cards[0])
    assert {key: window.get_settings_from_ui()[key] for key in unusual} == unusual
    window.quality_spin.setValue(81)
    assert {key: window.jobs[0].settings[key] for key in unusual} == unusual
    assert window.jobs[1].settings['blur_threshold'] == 9000.54321
    assert window.jobs[1].settings['fov'] == 175.54321
    assert all(job.settings['quality'] == 81 for job in window.jobs)


def test_utf8_preferences_and_valid_values_survive_window_startup(qapp, tmp_path, monkeypatch):
    import json
    from extractor360.core.settings_manager import SettingsManager
    config = tmp_path / 'preferences' / 'config.json'
    config.parent.mkdir(parents=True, exist_ok=True)
    values = dict(fov=160.123456, blur_threshold=5000.12345, sharpening_strength=3.12345,
                  custom_output_dir=str(tmp_path / 'Vidéos été'))
    config.write_text(json.dumps(values, ensure_ascii=False), encoding='utf-8')
    SettingsManager._instance = None
    monkeypatch.setattr(MainWindow, 'update_preview_display', lambda self: None)
    window = MainWindow()
    assert {key: window.default_settings[key] for key in values} == values
    window.quality_spin.setValue(81)
    saved = json.loads(config.read_text(encoding='utf-8'))
    assert {key: saved[key] for key in values} == values


def test_bad_mask_face_preferences_fall_back_without_crashing_studio(qapp, tmp_path):
    from extractor360.core.settings_manager import SettingsManager
    config = tmp_path / 'preferences' / 'config.json'
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text('{"ai_mask_cameras": [1], "ai_mode": "None"}', encoding='utf-8')
    SettingsManager._instance = None
    window = MainWindow()
    assert window.default_settings['ai_mask_cameras'] == []


def test_mask_face_controls_follow_camera_count_without_broadening_scope(settings_window):
    window = settings_window
    window.jobs[1].settings.update(layout_mode='ring', camera_count=6, ai_mask_cameras=['View_1'])
    window.select_card(window._video_cards[1])
    window.cam_count_spin.setValue(8)
    assert set(window.mask_face_checks) == {f'View_{i}' for i in range(8)}
    assert window.jobs[1].settings['ai_mask_cameras'] == ['View_1']
    window.mask_face_checks['View_7'].setChecked(True)
    window.cam_count_spin.setValue(4)
    assert 'View_6' not in window.mask_face_checks
    assert 'unavailable' in window.mask_face_checks['View_7'].text()
    assert window.mask_face_checks['View_7'].isChecked()


@pytest.mark.parametrize('field,value', [('fov', 120), ('blur_threshold', 321)])
def test_late_blur_analysis_does_not_overwrite_an_edited_job(settings_window, field, value):
    import copy
    window = settings_window
    job = window.jobs[1]
    window._blur_job = job
    window._blur_settings = copy.deepcopy(job.settings)
    window._blur_revision = window._job_settings_revisions.get(id(job), 0)
    widget = window.fov_spin if field == 'fov' else window.blur_threshold_spin
    widget.setValue(value)
    expected = copy.deepcopy(job.settings)
    window._on_blur_analysis_finished({'average': 5000})
    assert job.settings == expected


def test_frame_count_estimate_includes_zero_and_last_frame(settings_window):
    window = settings_window
    for job in window.jobs:
        video = Path(job.file_path).with_suffix('.mp4')
        video.touch()
        job.file_path = str(video)
        job.settings.update(is_360=False, interval_unit='Frames', interval_value=10.9)
        key = (job.file_path, os.path.getmtime(job.file_path))
        window._media_info[key] = (101, 10.0, 64, 32)
    window.update_estimate()
    assert 'Estimated 22 images' in window.estimation_label.text()


def test_named_mask_profile_applies_contract_to_entire_selection(settings_window):
    window = settings_window
    first, second = window.jobs
    first.settings.update(ai_invert_mask=False, naming_mode='postshot', quality=83)
    second.settings.update(ai_invert_mask=True, naming_mode='simple', export_colmap=True, quality=65)
    window.select_card(window._video_cards[1])
    window.toggle_card_selection(window._video_cards[0])
    window.mask_profile_combo.setCurrentIndex(window.mask_profile_combo.findData('postshot'))
    for job in window.jobs:
        assert job.settings['mask_profile'] == job.settings['naming_mode'] == 'postshot'
        assert job.settings['ai_invert_mask'] is False
        assert job.settings['export_colmap'] is False
    assert (first.settings['quality'], second.settings['quality']) == (83, 65)
    assert not window.ai_invert_toggle.isEnabled()
    window.mask_profile_combo.setCurrentIndex(window.mask_profile_combo.findData('custom'))
    assert window.ai_invert_toggle.isEnabled()


def test_image_estimate_is_one_capture_at_native_size(settings_window):
    window = settings_window
    for job in window.jobs:
        job.settings.update(is_360=False, resolution=8192, interval_value=0.001)
    window.update_estimate()
    assert 'Estimated 2 images' in window.estimation_label.text()
    assert '0.0–0.0 GiB' in window.estimation_label.text()


@pytest.mark.parametrize('action', ['start', 'cancel', 'close'])
def test_extraction_waits_for_preview_without_blocking_ui(settings_window, qapp, monkeypatch, action):
    import threading
    import time
    from PySide6.QtCore import QRunnable
    from extractor360.ui import main_window
    window = settings_window
    for job in window.jobs:
        job.settings.update(is_360=False)
    entered, release = threading.Event(), threading.Event()
    class NativePreview(QRunnable):
        def run(self):
            entered.set()
            assert release.wait(10)
    window.preview_widget.threadpool.start(NativePreview())
    assert entered.wait(5)
    controller = main_window.ProcessingController
    started = []
    def create_controller(*args, **kwargs):
        assert window.preview_widget.threadpool.activeThreadCount() == 0
        started.append(True)
        return controller(*args, **kwargs)
    monkeypatch.setattr(main_window, 'ProcessingController', create_controller)
    try:
        window.start_processing()
        assert window.is_processing and window._waiting_for_preview
        assert not started
        assert window.preview_widget._suspended
        qapp.processEvents()
        if action == 'cancel':
            window.cancel_processing()
        elif action == 'close':
            window.close()
    finally:
        release.set()
    assert window.preview_widget.threadpool.waitForDone(5000)
    deadline = time.monotonic() + 10
    while window.is_processing or (action == 'start' and not started):
        qapp.processEvents()
        assert time.monotonic() < deadline
        time.sleep(.005)
    qapp.processEvents()
    if action == 'start':
        assert started == [True]
        assert all(job.status == 'Done' for job in window.jobs)
        assert not window.preview_widget._suspended
    else:
        assert not started
        assert all(job.status == 'Pending' for job in window.jobs)
