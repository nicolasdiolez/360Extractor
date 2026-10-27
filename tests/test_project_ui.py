"""Exercise save/open, dirty state and missing-media repair through Studio."""
import copy
from pathlib import Path

import cv2
import numpy as np
import pytest
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

from extractor360.core.processor import ProcessingWorker
from extractor360.core.project import source_identity, source_problem
from extractor360.ui.main_window import MainWindow


@pytest.fixture(scope='module')
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(qapp, tmp_path, monkeypatch):
    monkeypatch.setattr(MainWindow, 'update_preview_display', lambda self: None)
    instance = MainWindow()
    instance.default_settings.update(resolution=32, layout_mode='cube', exif_intrinsics=False)
    files = []
    for name in ('one.png', 'two.png'):
        source = tmp_path / name
        assert cv2.imwrite(str(source), np.full((32, 64, 3), 100, np.uint8))
        files.append(str(source))
    instance.add_videos_from_paths(files)
    return instance


def test_save_open_keeps_per_job_choices_and_preferences(window, tmp_path):
    first, second = window.jobs
    first.settings.update(quality=80, active_cameras=[0, 5], mask_profile='postshot')
    second.settings.update(quality=68, layout_mode='ring', active_cameras=[1], pitch_offset=17.12345)
    window.select_card(window._video_cards[0])
    window.toggle_card_selection(window._video_cards[1])
    preferences = copy.deepcopy(window.settings_manager.get_all())
    target = tmp_path / 'capture.360proj'
    window.project_actions.save_to(target)
    assert not window.project_actions.dirty
    other = MainWindow()
    assert other.project_actions.load_from(target)
    assert [job.job_id for job in other.jobs] == [first.job_id, second.job_id]
    assert [card.job.job_id for card in other._selected_cards] == [first.job_id, second.job_id]
    assert [job.settings['quality'] for job in other.jobs] == [80, 68]
    assert other.jobs[0].settings['active_cameras'] == [0, 5]
    assert other.jobs[1].settings['pitch_offset'] == 17.12345
    assert other.settings_manager.get_all() == preferences
    assert not other.project_actions.dirty and not other.is_processing
    other.quality_spin.setValue(70)
    assert other.project_actions.dirty and other.windowTitle().endswith(' *')
    assert all(job.settings['quality'] == 70 for job in other.jobs)
    assert other.jobs[1].settings['active_cameras'] == [1]


def test_invalid_open_and_cancel_leave_current_queue_intact(window, tmp_path, monkeypatch):
    original = list(window.jobs)
    bad = tmp_path / 'broken.360proj'
    bad.write_text('{broken')
    with pytest.raises(ValueError): window.project_actions.load_from(bad)
    assert window.jobs == original and window.project_actions.dirty
    valid = tmp_path / 'valid.360proj'
    window.project_actions.save_to(valid)
    window.quality_spin.setValue(60)
    monkeypatch.setattr(QMessageBox, 'question', lambda *a: QMessageBox.StandardButton.Cancel)
    assert not window.project_actions.load_from(valid)
    assert window.jobs == original and window.jobs[-1].settings['quality'] == 60


def test_new_save_cancel_and_close_failure_keep_window_usable(window, tmp_path, monkeypatch):
    window.show()
    original = list(window.jobs)
    monkeypatch.setattr(QMessageBox, 'question', lambda *a: QMessageBox.StandardButton.Cancel)
    window.project_actions.new()
    window.close()
    assert window.isVisible() and not window._closing and window.jobs == original
    assert not window.preview_widget._closed and not window.preview_widget._suspended
    monkeypatch.setattr(QMessageBox, 'question', lambda *a: QMessageBox.StandardButton.Save)
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *a: ('', ''))
    window.close()
    assert window.isVisible() and window.project_actions.dirty
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *a: (str(tmp_path / 'absent' / 'save.360proj'), ''))
    errors = []
    monkeypatch.setattr(window.project_actions, '_error', errors.append)
    window.close()
    assert errors and window.isVisible() and window.project_actions.dirty
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *a: (str(tmp_path / 'saved.360proj'), ''))
    window.close()
    assert not window.isVisible() and (tmp_path / 'saved.360proj').is_file()


def test_external_project_edit_is_not_overwritten(window, tmp_path, monkeypatch):
    target = tmp_path / 'capture.360proj'
    window.project_actions.save_to(target)
    window.quality_spin.setValue(60)
    target.write_text('external edit')
    errors = []
    monkeypatch.setattr(window.project_actions, '_error', errors.append)
    assert not window.project_actions.save()
    assert 'changed on disk' in str(errors[0])
    assert target.read_text() == 'external edit' and window.project_actions.dirty


def test_open_same_project_after_save_prompt_uses_newly_saved_content(window, tmp_path, monkeypatch):
    target = tmp_path / 'same.360proj'
    window.project_actions.save_to(target)
    window.quality_spin.setValue(63)
    monkeypatch.setattr(QMessageBox, 'question', lambda *a: QMessageBox.StandardButton.Save)
    assert window.project_actions.load_from(target)
    assert window.jobs[-1].settings['quality'] == 63
    assert not window.project_actions.dirty
    assert window.project_actions.save()  # The installed digest must also be current.


def test_missing_source_stays_visible_and_can_be_relocated(window, tmp_path, monkeypatch):
    target = tmp_path / 'capture.360proj'
    first = window.jobs[0]
    first.settings['quality'] = 79
    window.select_card(window._video_cards[0])
    window.project_actions.save_to(target)
    moved = tmp_path / 'moved.png'
    Path(first.file_path).rename(moved)
    window.project_actions.load_from(target)
    job = window.jobs[0]
    assert len(window.jobs) == 2 and 'missing' in source_problem(job)
    assert window._video_cards[0]._status_label.text() == 'Check source'
    assert not window.extract_btn.isEnabled()
    window.start_processing()
    assert not window.is_processing
    monkeypatch.setattr(QFileDialog, 'getOpenFileName', lambda *a: (str(moved), ''))
    window.project_actions.locate_source()
    assert source_problem(job) is None and job.job_id == first.job_id
    assert job.settings['quality'] == 79 and window.extract_btn.isEnabled()
    assert window.project_actions.dirty


def test_changed_source_requires_explicit_confirmation(window, tmp_path, monkeypatch):
    job = window.jobs[0]
    window.select_card(window._video_cards[0])
    Path(job.file_path).write_bytes(b'different media')
    original = copy.deepcopy(job.source_identity)
    monkeypatch.setattr(QFileDialog, 'getOpenFileName', lambda *a: (job.file_path, ''))
    monkeypatch.setattr(QMessageBox, 'question', lambda *a: QMessageBox.StandardButton.No)
    window.project_actions.locate_source()
    assert job.source_identity == original
    monkeypatch.setattr(QMessageBox, 'question', lambda *a: QMessageBox.StandardButton.Yes)
    window.project_actions.locate_source()
    assert job.source_identity == source_identity(job.file_path)


def test_custom_model_trust_requires_user_action_after_open(window, tmp_path):
    window.jobs[0].settings.update(ai_model=str(tmp_path / 'custom.pt'), trust_custom_model=True, ai_mode='Generate Mask')
    window.select_card(window._video_cards[0])
    target = tmp_path / 'custom.360proj'
    window.project_actions.save_to(target)
    window.project_actions.load_from(target)
    assert not window.jobs[0].settings['trust_custom_model']
    assert not window.trust_model_toggle.isChecked()
    window.trust_model_toggle.setChecked(True)
    assert window.jobs[0].settings['trust_custom_model']
    window.ai_model_combo.setCurrentIndex(0)
    assert not window.jobs[0].settings['trust_custom_model']


def test_trust_is_not_granted_to_a_mixed_model_selection(window, tmp_path):
    window.jobs[0].settings.update(ai_model=str(tmp_path / 'first.pt'), trust_custom_model=False)
    window.jobs[1].settings.update(ai_model=str(tmp_path / 'second.pt'), trust_custom_model=False)
    window.select_card(window._video_cards[0])
    window.toggle_card_selection(window._video_cards[1])
    assert not window.trust_model_toggle.isEnabled()
    assert all(not job.settings['trust_custom_model'] for job in window.jobs)


def test_late_blur_result_cannot_edit_reopened_project(window, tmp_path):
    target = tmp_path / 'reopened.360proj'
    window.project_actions.save_to(target)
    old = window.jobs[0]
    window._blur_job = old
    window._blur_settings = copy.deepcopy(old.settings)
    window._blur_revision = 0
    window.project_actions.load_from(target)
    before = copy.deepcopy(window.jobs[0].settings)
    window._on_blur_analysis_finished({'average': 800})
    assert window.jobs[0].settings == before


def test_opened_completed_job_runs_to_new_folder(window, tmp_path):
    worker = ProcessingWorker(window.jobs)
    worker.run()
    assert worker.error_count == 0
    previous = [job.result['output_dir'] for job in window.jobs]
    target = tmp_path / 'complete.360proj'
    window.project_actions.save_to(target)
    window.project_actions.load_from(target)
    assert all(job.status == 'Pending' for job in window.jobs)
    assert [job.result['output_dir'] for job in window.jobs] == previous
    worker = ProcessingWorker(window.jobs)
    worker.run()
    assert worker.error_count == 0
    assert all(job.result['output_dir'] != old for job, old in zip(window.jobs, previous))
    assert all(Path(old, 'manifest.json').exists() for old in previous)


def test_document_actions_refuse_busy_worker(window, tmp_path):
    window.is_processing = True
    with pytest.raises(ValueError, match='Wait'): window.project_actions.save_to(tmp_path / 'busy.360proj')
    with pytest.raises(ValueError, match='Wait'): window.project_actions.load_from(tmp_path / 'any.360proj')
    window.is_processing = False


def test_cancel_close_while_waiting_for_preview_restores_controls(window, monkeypatch):
    window.show()
    window._waiting_for_preview = True
    window.is_processing = True
    for widget in (window.left_panel, window.right_panel, window.top_nav, window.project_actions.menu):
        widget.setEnabled(False)
    monkeypatch.setattr(QMessageBox, 'question', lambda *a: QMessageBox.StandardButton.Cancel)
    window.close()
    assert window.isVisible() and not window._closing and not window.is_processing
    assert not window.preview_widget._closed and not window.preview_widget._suspended
    assert all(widget.isEnabled() for widget in (window.left_panel, window.right_panel, window.top_nav, window.project_actions.menu))


def alignment_report(job):
    from extractor360.core.alignment import fingerprint
    return {'schema_version': 1, 'fingerprint': fingerprint(job),
            'registered_captures': 1, 'unregistered_captures': 1, 'sampled_frames': [0, 2],
            'groups': [{'models': ['0'], 'frames': [0]}], 'models': [{'model': '0', 'frames': [0]}],
            'captures': [{'frame': 0, 'images': ['Front/frame0.jpg'], 'models': {'0': 1}, 'state': 'registered'},
                         {'frame': 2, 'images': ['Front/frame2.jpg'], 'models': {}, 'state': 'unregistered'}]}


def test_alignment_selection_saved_reopened_and_source_navigation(window, tmp_path):
    from PySide6.QtCore import Qt
    from extractor360.ui.alignment_dialog import AlignmentDialog
    job = window.jobs[0]
    window.select_card(window._video_cards[0])
    report = alignment_report(job)
    job.result['alignment'] = report
    dialog = AlignmentDialog(window, job)
    dialog.table.item(1, 0).setCheckState(Qt.CheckState.Unchecked)
    assert job.settings['excluded_frames'] == [2]
    assert 'Historical' in dialog.summary.text() and window.project_actions.dirty
    target = tmp_path / 'decisions.360proj'
    window.project_actions.save_to(target)
    dialog.close()
    window.project_actions.load_from(target)
    job = window.jobs[0]
    assert job.settings['excluded_frames'] == [2] and job.result['alignment'] == report
    dialog = AlignmentDialog(window, job)
    assert dialog.table.item(1, 0).checkState() == Qt.CheckState.Unchecked
    dialog.table.selectRow(1)
    dialog.view_capture()
    assert window._selected_cards[0].job is job and window.preview_widget._exact_frame == 2


def test_excluded_captures_can_be_restored_after_new_export(window):
    from extractor360.ui.alignment_dialog import AlignmentDialog
    job = window.jobs[0]
    job.settings['excluded_frames'] = [99]
    job.result = {}  # A new extraction replaces the previous diagnostic.
    dialog = AlignmentDialog(window, job)
    assert dialog.restore_button.isEnabled()
    dialog.restore_selection()
    assert job.settings['excluded_frames'] == [] and window.project_actions.dirty
    assert not dialog.restore_button.isEnabled()
    dialog.close()


def test_alignment_thread_blocks_actions_then_drains_on_close(window, tmp_path, monkeypatch, qapp):
    import time
    from extractor360.core.alignment import AlignmentRunner
    from extractor360.ui.alignment_dialog import AlignmentDialog
    entered = []
    def run(runner, *args):
        entered.append(True)
        while not runner.cancelled():
            time.sleep(.005)
        raise InterruptedError('Alignment cancelled')
    monkeypatch.setattr(AlignmentRunner, 'run', run)
    window.show()
    window.alignment_dialog = AlignmentDialog(window, window.jobs[0])
    dialog = window.alignment_dialog
    dialog.show()
    dialog.start(tmp_path / 'diagnostic')
    deadline = time.monotonic() + 5
    while not entered:
        qapp.processEvents()
        assert time.monotonic() < deadline
    with pytest.raises(ValueError, match='Wait'):
        window.project_actions.save_to(tmp_path / 'busy.360proj')
    window.start_processing()
    assert not window.is_processing
    monkeypatch.setattr(window.project_actions, 'confirm_discard', lambda: True)
    window.close()
    while window.isVisible() or dialog.busy:
        qapp.processEvents()
        time.sleep(.005)
        assert time.monotonic() < deadline
    assert dialog._thread is None


def test_alignment_delivers_result_only_after_thread_finishes(window, tmp_path, monkeypatch, qapp):
    import time
    from extractor360.core.alignment import AlignmentRunner
    from extractor360.ui.alignment_dialog import AlignmentDialog
    job = window.jobs[0]
    report = alignment_report(job)
    monkeypatch.setattr(AlignmentRunner, 'run', lambda *args: report)
    dialog = AlignmentDialog(window, job)
    dialog.start(tmp_path / 'diagnostic')
    deadline = time.monotonic() + 5
    while dialog.busy:
        qapp.processEvents()
        time.sleep(.005)
        assert time.monotonic() < deadline
    assert job.result['alignment'] == report and window.project_actions.dirty
    assert dialog.table.rowCount() == 2 and dialog.run_button.isEnabled()
    dialog.close()
