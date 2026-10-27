"""Inspect a small COLMAP sample and record capture exclusions in the project."""
from __future__ import annotations

import copy
from datetime import datetime
from pathlib import Path
import threading
import uuid
from typing import Any, TYPE_CHECKING

from PySide6.QtCore import QThread, Signal, Qt
from PySide6.QtWidgets import (QDialog, QFileDialog, QHBoxLayout, QLabel, QMessageBox,
                               QPushButton, QSpinBox, QTableWidget, QTableWidgetItem, QVBoxLayout)

from extractor360.core.alignment import AlignmentRunner, fingerprint, load_export

if TYPE_CHECKING:
    from extractor360.ui.main_window import MainWindow


class AlignmentThread(QThread):
    progress = Signal(str)

    def __init__(self, job, destination, maximum, parent=None):
        super().__init__(parent)
        self.job = copy.deepcopy(job)
        self.destination, self.maximum = destination, maximum
        self.cancelled = threading.Event()
        self.report: dict[str, Any] | None = None
        self.error: str | None = None

    def run(self):
        try:
            runner = AlignmentRunner(self.cancelled.is_set, self.progress.emit)
            self.report = runner.run(self.job, self.destination, self.maximum)
        except Exception as exc:
            self.error = str(exc)


class AlignmentDialog(QDialog):
    def __init__(self, window: MainWindow, job):
        super().__init__(window)
        self._window, self.job = window, job
        self._thread: AlignmentThread | None = None
        self.report: dict[str, Any] | None = None
        self._close_requested = False
        self.setWindowTitle(f'Alignment diagnostic — {job.filename}')
        self.setObjectName('alignmentDiagnostic')
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.resize(900, 600)
        layout = QVBoxLayout(self)
        intro = QLabel('Test confirmed images from the last 360 COLMAP export. Maximum 16 captures, '
                       '128 views, 512 px/view, CPU, 5 minutes and a 256 MiB workspace limit.\n'
                       'An unregistered capture is a finding, not a diagnosis of its cause. '
                       'Excluding it does not necessarily improve reconstruction.')
        intro.setWordWrap(True)
        layout.addWidget(intro)
        controls = QHBoxLayout()
        controls.addWidget(QLabel('Maximum captures:'))
        self.maximum = QSpinBox()
        self.maximum.setRange(3, 16)
        self.maximum.setValue(8)
        controls.addWidget(self.maximum)
        self.run_button = QPushButton('Run COLMAP diagnostic…')
        self.run_button.clicked.connect(self.choose_destination)
        controls.addWidget(self.run_button)
        self.cancel_button = QPushButton('Cancel diagnostic')
        self.cancel_button.setEnabled(False)
        self.cancel_button.clicked.connect(self.cancel)
        controls.addWidget(self.cancel_button)
        layout.addLayout(controls)
        self.summary = QLabel('Extract this source with COLMAP export enabled, then run a diagnostic.')
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(['Include', 'Source frame', 'Source time', 'Alignment', 'Views / models'])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.itemChanged.connect(self.selection_changed)
        self.table.cellDoubleClicked.connect(lambda *_: self.view_capture())
        layout.addWidget(self.table)
        self.path_label = QLabel('')
        self.path_label.setWordWrap(True)
        layout.addWidget(self.path_label)
        actions = QHBoxLayout()
        self.restore_button = QPushButton('Restore all excluded captures')
        self.restore_button.setEnabled(bool(job.settings.get('excluded_frames')))
        self.restore_button.clicked.connect(self.restore_selection)
        actions.addWidget(self.restore_button)
        view = QPushButton('View selected source capture')
        view.clicked.connect(self.view_capture)
        actions.addWidget(view)
        close = QPushButton('Close')
        close.clicked.connect(self.close)
        actions.addWidget(close)
        layout.addLayout(actions)
        saved = job.result.get('alignment')
        if saved:
            try:
                self.show_report(saved)
            except (KeyError, TypeError, ValueError, AttributeError):
                self.report = None
                self.table.setRowCount(0)
                self.summary.setText('The saved diagnostic cannot be read. Run it again.')

    @property
    def busy(self):
        return self._thread is not None

    def choose_destination(self):
        try:
            load_export(self.job)
            parent = QFileDialog.getExistingDirectory(self, 'Choose diagnostic output folder')
            if parent:
                name = f'alignment-{datetime.now():%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:8]}'
                self.start(Path(parent) / name)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, 'Alignment diagnostic', str(exc))

    def start(self, destination):
        if self.busy:
            return
        self._close_requested = False
        self.run_button.setEnabled(False)
        self.maximum.setEnabled(False)
        self.table.setEnabled(False)
        self.restore_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.path_label.setText(f'Diagnostic files: {destination}')
        self._thread = AlignmentThread(self.job, destination, self.maximum.value(), self)
        self._thread.progress.connect(self.summary.setText)
        self._thread.finished.connect(self.finished_run)
        self._thread.start()

    def cancel(self):
        if self._thread:
            self._thread.cancelled.set()
            self.cancel_button.setEnabled(False)
            self.summary.setText('Cancelling; waiting for COLMAP to stop…')

    def finished_run(self):
        thread = self._thread
        if thread is None:
            return
        thread.wait()
        self._thread = None
        self.run_button.setEnabled(True)
        self.maximum.setEnabled(True)
        self.table.setEnabled(True)
        self.cancel_button.setEnabled(False)
        self.restore_button.setEnabled(bool(self.job.settings.get('excluded_frames')))
        if thread.report and not thread.cancelled.is_set() and any(job is self.job for job in self._window.jobs):
            self.job.result['alignment'] = thread.report
            self._window.project_actions.mark_dirty()
            self.show_report(thread.report)
        else:
            self.summary.setText(thread.error or 'Alignment cancelled. Previous diagnostic retained, if any.')
        thread.deleteLater()
        if self._close_requested:
            super().reject()

    def show_report(self, report):
        if (report.get('schema_version') != 1 or not isinstance(report.get('captures'), list)
                or len(report['captures']) > 10000):
            raise ValueError('Invalid saved diagnostic')
        # Validate before creating editable checkboxes from an imported project.
        for item in report['captures']:
            if (type(item.get('frame')) is not int or item['frame'] < 0
                    or item.get('state') not in ('registered', 'unregistered', 'excluded', 'not_sampled')
                    or not isinstance(item.get('models'), dict) or not isinstance(item.get('images'), list)):
                raise ValueError('Invalid capture in saved diagnostic')
        self.report = report
        shown = list(report['captures'])
        known = {item['frame'] for item in shown}
        shown += [{'frame': frame, 'images': [], 'models': {}, 'state': 'excluded'}
                  for frame in self.job.settings.get('excluded_frames', []) if frame not in known]
        shown.sort(key=lambda item: item['frame'])
        self.table.blockSignals(True)
        try:
            self.table.setRowCount(len(shown))
            excluded = set(self.job.settings.get('excluded_frames', []))
            for row, item in enumerate(shown):
                include = QTableWidgetItem()
                include.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsUserCheckable)
                include.setCheckState(Qt.CheckState.Unchecked if item['frame'] in excluded else Qt.CheckState.Checked)
                include.setData(Qt.ItemDataRole.UserRole, item['frame'])
                self.table.setItem(row, 0, include)
                seconds = item.get('timestamp_seconds')
                timing = f'{seconds:.3f} s ({item.get("timestamp_source", "unavailable")})' if type(seconds) in (int, float) else 'Unavailable in export'
                memberships = ', '.join(f'Model {name}: {count}/{len(item["images"])} views' for name, count in item['models'].items())
                for column, value in enumerate((str(item['frame']), timing, item['state'].replace('_', ' '), memberships or '—'), 1):
                    cell = QTableWidgetItem(value)
                    cell.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                    self.table.setItem(row, column, cell)
            self.table.resizeColumnsToContents()
        finally:
            self.table.blockSignals(False)
        self.update_summary()

    def update_summary(self):
        self.restore_button.setEnabled(not self.busy and bool(self.job.settings.get('excluded_frames')))
        if not self.report:
            return
        report = self.report
        stale = report.get('fingerprint') != fingerprint(self.job)
        self.summary.setText(
            f'{report["registered_captures"]}/{len(report["sampled_frames"])} sampled physical captures registered; '
            f'{report["unregistered_captures"]} unregistered. '
            f'{len(report["groups"])} disjoint group(s), {len(report["models"])} model(s). '
            'Models sharing captures are overlapping alternatives. Unsampled captures are untested.\n'
            + ('Historical result: selection/settings changed. Run again to measure their effect. ' if stale else '')
            + 'Checkboxes apply to all views of that frame in future extractions. Save the project to retain decisions.')

    def selection_changed(self, item):
        if self.busy or item.column() != 0:
            return
        frame = item.data(Qt.ItemDataRole.UserRole)
        excluded = set(self.job.settings.get('excluded_frames', []))
        if item.checkState() == Qt.CheckState.Checked:
            excluded.discard(frame)
        else:
            excluded.add(frame)
        self.job.settings['excluded_frames'] = sorted(excluded)
        self.selection_updated()

    def selection_updated(self):
        self._window.project_actions.mark_dirty()
        self._window.set_ui_from_settings(self.job.settings)
        for card in self._window._video_cards:
            if card.job is self.job:
                card.refresh()
        self._window.update_preview_display()
        self._window.update_estimate()
        self.update_summary()

    def restore_selection(self):
        if self.busy:
            return
        self.job.settings['excluded_frames'] = []
        self.selection_updated()
        if self.report:
            self.show_report(self.report)
        self.update_summary()

    def view_capture(self):
        row = self.table.currentRow()
        if self.busy or row < 0:
            return
        item = self.table.item(row, 0)
        if item is None:
            return
        frame = item.data(Qt.ItemDataRole.UserRole)
        for card in self._window._video_cards:
            if card.job is self.job:
                self._window.select_card(card)
                self._window.update_preview_display()
                self._window.preview_widget.seek_frame(frame)
                self.close()
                return

    def reject(self):
        if self.busy:
            self._close_requested = True
            self.cancel()
        else:
            super().reject()

    def closeEvent(self, event):
        if self.busy:
            self._close_requested = True
            self.cancel()
            event.ignore()
        else:
            event.accept()
