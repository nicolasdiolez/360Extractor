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
    assert s["feather_mask"] is True
    assert s["export_colmap"] is True

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
        assert "pinhole images" in window.estimation_label.text()
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
