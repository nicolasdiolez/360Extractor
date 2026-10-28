"""Inspect a small COLMAP sample and record capture exclusions in the project."""
from __future__ import annotations

import copy
import math
from datetime import datetime
from pathlib import Path
import threading
import uuid
from typing import Any, TYPE_CHECKING

from PySide6.QtCore import QThread, Signal, Qt, QTimer
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QFileDialog, QHBoxLayout, QLabel, QMessageBox,
                               QPushButton, QSpinBox, QTableWidget, QTableWidgetItem, QVBoxLayout)

from extractor360.core.alignment import AlignmentRunner, fingerprint, load_export
from extractor360.core.diagnostic import diagnostic_options, model_overview

if TYPE_CHECKING:
    from extractor360.ui.main_window import MainWindow


class AlignmentThread(QThread):
    progress = Signal(str)

    def __init__(self, job, destination, maximum, parent=None, mode='export'):
        super().__init__(parent)
        self.job = copy.deepcopy(job)
        self.destination, self.maximum = destination, maximum
        self.mode = mode
        self.cancelled = threading.Event()
        self.report: dict[str, Any] | None = None
        self.error: str | None = None

    def run(self):
        try:
            runner = AlignmentRunner(self.cancelled.is_set, self.progress.emit)
            self.report = (runner.run_source(self.job, self.destination, self.maximum) if self.mode == 'source'
                           else runner.run(self.job, self.destination, self.maximum))
        except Exception as exc:
            self.error = str(exc)


class AlignmentDialog(QDialog):
    def __init__(self, window: MainWindow, job):
        super().__init__(window)
        self._window, self.job = window, job
        self._thread: AlignmentThread | None = None
        self.report: dict[str, Any] | None = None
        self._close_requested = False
        options = diagnostic_options(job.diagnostic_settings)
        self.setWindowTitle(f'Alignment diagnostic — {job.filename}')
        self.setObjectName('alignmentDiagnostic')
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.resize(1050, 820)
        layout = QVBoxLayout(self)
        intro = QLabel('Test a source sample before full extraction, or images from the last 360 COLMAP export. Maximum 16 captures, '
                       '128 views, up to 1024 px/view, CPU, 5 minutes and a 256 MiB workspace limit.\n'
                       'An unregistered capture is a finding, not a diagnosis of its cause. '
                       'Excluding it does not necessarily improve reconstruction.')
        intro.setWordWrap(True)
        layout.addWidget(intro)
        self.mode = QComboBox()
        self.mode.addItem('From source — preliminary sample', 'source')
        self.mode.addItem('From last completed COLMAP export', 'export')
        mode = options['mode'] if job.diagnostic_settings else ('export' if job.result.get('output_dir') else 'source')
        self.mode.setCurrentIndex(self.mode.findData(mode))
        layout.addWidget(self.mode)
        self.scope = QLabel('')
        self.scope.setWordWrap(True)
        layout.addWidget(self.scope)
        controls = QHBoxLayout()
        controls.addWidget(QLabel('Maximum captures:'))
        self.maximum = QSpinBox()
        self.maximum.setRange(3, 16)
        self.maximum.setValue(options['maximum'])
        controls.addWidget(self.maximum)
        controls.addWidget(QLabel('Resolution:'))
        self.resolution = QComboBox()
        self.resolution.addItem('512 px', 512)
        self.resolution.addItem('1024 px', 1024)
        self.resolution.setCurrentIndex(self.resolution.findData(options['resolution']))
        controls.addWidget(self.resolution)
        self.run_button = QPushButton('Run COLMAP diagnostic…')
        self.run_button.clicked.connect(self.choose_destination)
        controls.addWidget(self.run_button)
        self.cancel_button = QPushButton('Cancel diagnostic')
        self.cancel_button.setEnabled(False)
        self.cancel_button.clicked.connect(self.cancel)
        controls.addWidget(self.cancel_button)
        layout.addLayout(controls)
        range_row = QHBoxLayout()
        self.range_check = QCheckBox('Limit to source frames (inclusive):')
        self.range_check.setChecked(options['frame_range'] is not None)
        range_row.addWidget(self.range_check)
        self.start_frame, self.end_frame = QSpinBox(), QSpinBox()
        self.start_frame.setRange(0, 2147483645)
        self.end_frame.setRange(2, 2147483647)
        known = [info[0] for key, info in window._media_info.items() if key[0] == job.file_path]
        start, end = options['frame_range'] or [0, max(2, known[-1] - 1) if known else 2]
        self.start_frame.setValue(start)
        self.end_frame.setValue(end)
        self.view_start, self.view_end = QPushButton('View start'), QPushButton('View end')
        for widget in (self.start_frame, self.view_start, QLabel('to'), self.end_frame, self.view_end):
            range_row.addWidget(widget)
        layout.addLayout(range_row)
        self.view_start.clicked.connect(lambda: self.view_source_frame(self.start_frame.value()))
        self.view_end.clicked.connect(lambda: self.view_source_frame(self.end_frame.value()))
        self.start_frame.valueChanged.connect(self.start_changed)
        self.end_frame.valueChanged.connect(self.end_changed)
        self.range_check.toggled.connect(self.options_changed)
        self.mode.currentIndexChanged.connect(self.options_changed)
        self.maximum.valueChanged.connect(self.options_changed)
        self.resolution.currentIndexChanged.connect(self.options_changed)
        self.headline = QLabel('No diagnostic yet')
        self.headline.setTextFormat(Qt.TextFormat.PlainText)
        self.headline.setStyleSheet('font-size: 16px; font-weight: bold;')
        self.headline.setWordWrap(True)
        layout.addWidget(self.headline)
        self.summary = QLabel('Choose a diagnostic source and an output folder to begin.')
        self.summary.setTextFormat(Qt.TextFormat.PlainText)
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)
        self.model_table = QTableWidget(0, 5)
        self.model_table.setHorizontalHeaderLabels(['Model', 'Captures', 'Source span', 'Missing tested captures', 'Kind'])
        self.model_table.horizontalHeader().setStretchLastSection(True)
        self.model_table.setMaximumHeight(140)
        self.model_table.setVisible(False)
        layout.addWidget(self.model_table)
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
        self.update_scope()
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

    def update_scope(self):
        window = (f'frames {self.start_frame.value()}–{self.end_frame.value()}' if self.range_check.isChecked() else 'the whole video')
        self.scope.setText(f'Source preflight samples {window} uniformly, independently of the export interval. '
                           'Current geometry/AI/nadir choices are retained; blur and motion rejection are disabled. '
                           'AI uses a local model on CPU. Extraction settings stay unchanged.'
                           if self.mode.currentData() == 'source' else
                           f'Test confirmed captures from {window} in the last matching completed export. '
                           'Pixels and masks are reused, without upscaling.')
        for widget in (self.start_frame, self.end_frame, self.view_start, self.view_end):
            widget.setEnabled(self.range_check.isChecked() and not self.busy)

    def current_options(self):
        return diagnostic_options({'mode': self.mode.currentData(), 'maximum': self.maximum.value(),
                                   'resolution': self.resolution.currentData(),
                                   'frame_range': [self.start_frame.value(), self.end_frame.value()] if self.range_check.isChecked() else None})

    def start_changed(self):
        if self.end_frame.value() < self.start_frame.value() + 2:
            self.end_frame.setValue(self.start_frame.value() + 2)
        self.options_changed()

    def end_changed(self):
        if self.start_frame.value() > self.end_frame.value() - 2:
            self.start_frame.setValue(self.end_frame.value() - 2)
        self.options_changed()

    def options_changed(self):
        self.job.diagnostic_settings = self.current_options()
        self._window.project_actions.mark_dirty()
        self.update_scope()
        if self.report:
            self.update_summary()

    def choose_destination(self):
        try:
            if self.mode.currentData() == 'source':
                from extractor360.core.preflight import source_plan
                source_plan(self.job, self.maximum.value())
            else:
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
        self.options_changed()
        self._close_requested = False
        self.run_button.setEnabled(False)
        self.maximum.setEnabled(False)
        self.mode.setEnabled(False)
        self.resolution.setEnabled(False)
        self.range_check.setEnabled(False)
        self.table.setEnabled(False)
        self.restore_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.path_label.setText(f'Diagnostic files: {destination}')
        self._thread = AlignmentThread(self.job, destination, self.maximum.value(), self, mode=self.mode.currentData())
        self.update_scope()
        self._thread.progress.connect(self.summary.setText)
        self._thread.finished.connect(self.finished_run)
        self._window.preview_widget.suspend()
        self.launch_when_preview_idle()

    def launch_when_preview_idle(self):
        if self._thread is None:
            return
        if self._window.preview_widget.threadpool.activeThreadCount():
            self.summary.setText('Waiting for the current preview to stop…')
            QTimer.singleShot(50, self.launch_when_preview_idle)
            return
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
        self.mode.setEnabled(True)
        self.resolution.setEnabled(True)
        self.range_check.setEnabled(True)
        self.update_scope()
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
        if not self._window._closing:
            self._window.preview_widget.resume()
        if self._close_requested:
            super().reject()

    def show_report(self, report):
        if (report.get('schema_version') != 1 or not isinstance(report.get('captures'), list)
                or len(report['captures']) > 10000):
            raise ValueError('Invalid saved diagnostic')
        # Validate before creating editable checkboxes from an imported project.
        for item in report['captures']:
            if (type(item.get('frame')) is not int or item['frame'] < 0
                    or item.get('state') not in ('registered', 'unregistered', 'excluded', 'not_sampled', 'filtered')
                    or not isinstance(item.get('models'), dict) or not isinstance(item.get('images'), list)):
                raise ValueError('Invalid capture in saved diagnostic')
        overview = model_overview(report)
        self.report = report
        self.model_table.setRowCount(len(overview['models']))
        self.model_table.setVisible(bool(overview['models']))
        for row, model in enumerate(overview['models']):
            kind = f'{model["capture_count"]}-capture fragment' if model['fragment'] else ('Largest' if model['model'] in overview['largest_ties'] else 'Separate / alternative model')
            values = (model['model'], str(model['capture_count']), self.span_text(model), str(len(model['missing_tested_frames'])), kind)
            for column, value in enumerate(values):
                cell = QTableWidgetItem(value)
                cell.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                self.model_table.setItem(row, column, cell)
        self.model_table.resizeColumnsToContents()
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
                time_source = {'decoder_timestamp': 'decoded', 'fps_estimate': 'FPS estimate', 'still_image': 'image'}.get(item.get('timestamp_source'), 'unavailable')
                timing = f'{seconds:.3f} s ({time_source})' if type(seconds) in (int, float) and math.isfinite(seconds) and seconds >= 0 else 'Unavailable in export'
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
        overview = model_overview(report)
        largest = overview['largest']
        if largest is None:
            headline = 'No reconstructed model in this sample'
        elif overview['only_fragments']:
            headline = f'Only fragments: {len(overview["models"])} model(s), at most {largest["capture_count"]} captures each'
        else:
            headline = f'Largest model: {largest["capture_count"]}/{len(report["sampled_frames"])} tested captures — {self.span_text(largest)}'
            if len(overview['largest_ties']) > 1:
                headline += ' (tied)'
        options = report.get('diagnostic_settings')
        stale = (report.get('fingerprint') != fingerprint(self.job)
                 or (options is not None and options != self.current_options())
                 or (options is None and bool(self.job.diagnostic_settings)))
        self.headline.setText(('Historical — ' if stale else '') + headline)
        scope = (f'Tested frames {report["sampled_frames"][0]}–{report["sampled_frames"][-1]}; ' if report['sampled_frames'] else '')
        scope += f'{report.get("resolution", "unknown")} px/view. '
        self.summary.setText(
            ('Source preflight: ' if report.get('mode') == 'source_preflight' else 'Export diagnostic: ')
            + scope + f'{report["registered_captures"]}/{len(report["sampled_frames"])} captures in any model; '
            f'{report["unregistered_captures"]} unregistered. '
            f'{len(report["models"])} model(s), including {overview["fragment_models"]} fragment(s) of 1–2 captures.\n'
            'Spans do not prove continuity between sampled captures. Overlapping models remain alternatives; '
            'fragments and low reprojection errors do not qualify 3D quality.\n'
            + ('COLMAP did not create a sparse model. A coarse sample can fail even when a larger export aligns.\n'
               if report.get('mapper_status') == 'no_model' else '')
            + (f'{report.get("filtered_captures", 0)} candidates produced no confirmed views before alignment. '
               + report.get('alignment_not_run', '') + '\n'
               if report.get('filtered_captures') or report.get('alignment_not_run') else '')
            + ('Historical result: selection/settings changed. Run again to measure their effect. ' if stale else '')
            + 'Checkboxes apply to all views of that frame in future extractions. Save the project to retain decisions.')

    @staticmethod
    def span_text(model):
        start, end = model['frame_span']
        text = f'frames {start}–{end}'
        if model['time_span'] is not None:
            a, b = model['time_span']
            text += f' / {a:.3f}–{b:.3f} s ({model["timing"]})'
        else:
            text += ' / time unavailable'
        return text

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
        self.view_source_frame(frame)

    def view_source_frame(self, frame):
        if self.busy:
            return
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
