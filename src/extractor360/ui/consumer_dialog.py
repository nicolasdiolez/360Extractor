"""Import consumer evidence and inspect individual components without running them."""
from __future__ import annotations

import copy
from pathlib import Path
import threading
from typing import Any

from PySide6.QtCore import QThread, Qt
from PySide6.QtWidgets import (QComboBox, QDialog, QFileDialog, QHBoxLayout, QLabel, QLineEdit,
                               QMessageBox, QPlainTextEdit, QPushButton, QTableWidget,
                               QTableWidgetItem, QVBoxLayout)

from extractor360.core.consumer_reports import (MAX_REPORTS, STATES, coverage, import_report,
                                                validate_reports, write_report, write_template)

LABELS = dict(retained='Retained', rejected='Rejected in component', not_retained='Not retained (reason unknown)',
              disabled='Alignment disabled', unknown='Unknown')


class ConsumerImportThread(QThread):
    def __init__(self, dataset, consumer, cameras, log, parent):
        super().__init__(parent)
        self.arguments = (dataset, consumer, cameras or None, log or None)
        self.cancelled = threading.Event()
        self.report: dict[str, Any] | None = None
        self.error: str | None = None

    def run(self):
        try:
            self.report = import_report(*self.arguments, cancelled=self.cancelled.is_set)
        except Exception as exc:
            self.error = str(exc)


class ConsumerReportDialog(QDialog):
    def __init__(self, window, job):
        super().__init__(window)
        self._window, self.job = window, job
        self._thread: ConsumerImportThread | None = None
        self.closing = False
        self.setWindowTitle(f'Consumer reports — {job.filename}')
        self.setObjectName('consumerReports')
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.resize(1100, 820)
        layout = QVBoxLayout(self)
        intro = QLabel('Import evidence against a completed extraction. Each component / Image Set is shown separately.\n'
                       'Not retained means absent from that exported set; it does not prove a failed alignment. '
                       'A log alone cannot identify retained views. Names do not prove identical input pixels.')
        intro.setWordWrap(True)
        layout.addWidget(intro)
        controls = QHBoxLayout()
        self.consumer = QComboBox()
        self.consumer.addItem('RealityScan', 'realityscan')
        self.consumer.addItem('Postshot', 'postshot')
        controls.addWidget(self.consumer)
        template = QPushButton('Save RealityScan report template…')
        template.clicked.connect(self.save_template)
        controls.addWidget(template)
        layout.addLayout(controls)
        self.dataset = self.path_row(layout, 'Extraction folder', folder=True)
        self.dataset.setText(job.result.get('output_dir', ''))
        self.cameras = self.path_row(layout, 'Camera / input report', file_filter='Reports (*.csv *.txt *.bin);;All files (*)')
        self.log = self.path_row(layout, 'Optional consumer log', file_filter='Logs (*.log *.txt);;All files (*)')
        note = QLabel('RealityScan: registration CSV or the supplied input-state template. Postshot: Image Set > Actions > '
                      'Export COLMAP database > images.txt / images.bin. Logs use the last UTC session (or the entire file without a header). '
                      'A session can contain several runs; only warnings are read from it.')
        note.setWordWrap(True)
        layout.addWidget(note)
        actions = QHBoxLayout()
        self.import_button = QPushButton('Import report')
        self.import_button.clicked.connect(self.start_import)
        actions.addWidget(self.import_button)
        self.cancel_button = QPushButton('Cancel import')
        self.cancel_button.setEnabled(False)
        self.cancel_button.clicked.connect(self.cancel)
        actions.addWidget(self.cancel_button)
        self.export_button = QPushButton('Save selected report as JSON…')
        self.export_button.clicked.connect(self.save_selected)
        actions.addWidget(self.export_button)
        close = QPushButton('Close')
        close.clicked.connect(self.close)
        actions.addWidget(close)
        layout.addLayout(actions)
        self.saved = QComboBox()
        layout.addWidget(self.saved)
        remove = QPushButton('Remove selected report from project')
        remove.clicked.connect(self.remove_selected)
        layout.addWidget(remove)
        self.models = QComboBox()
        layout.addWidget(self.models)
        self.summary = QLabel('No imported report. Reports are retained in the project when you save it.')
        self.summary.setTextFormat(Qt.TextFormat.PlainText)
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)
        self.details = QPlainTextEdit()
        self.details.setReadOnly(True)
        self.details.setMaximumHeight(170)
        layout.addWidget(self.details)
        filters = QHBoxLayout()
        self.state = QComboBox()
        self.state.addItem('All view states', None)
        for key in STATES:
            self.state.addItem(LABELS[key], key)
        filters.addWidget(self.state)
        self.search = QLineEdit()
        self.search.setPlaceholderText('Filter filename, source frame or direction')
        filters.addWidget(self.search)
        self.previous, self.next = QPushButton('Previous 200'), QPushButton('Next 200')
        filters.addWidget(self.previous)
        filters.addWidget(self.next)
        layout.addLayout(filters)
        self.page = 0
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(['Image', 'Source frame', 'Direction', 'State', 'Capture coverage', 'Mask warnings'])
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)
        self.warnings = QPlainTextEdit()
        self.warnings.setReadOnly(True)
        self.warnings.setMaximumHeight(130)
        layout.addWidget(self.warnings)
        self.saved.currentIndexChanged.connect(self.select_report)
        self.models.currentIndexChanged.connect(self.refresh)
        self.state.currentIndexChanged.connect(self.reset_page)
        self.search.textChanged.connect(self.reset_page)
        self.previous.clicked.connect(lambda: self.turn_page(-1))
        self.next.clicked.connect(lambda: self.turn_page(1))
        validate_reports(job.consumer_reports)
        self.populate()

    @property
    def busy(self):
        return self._thread is not None

    def path_row(self, layout, label, folder=False, file_filter=''):
        row = QHBoxLayout()
        row.addWidget(QLabel(label))
        field = QLineEdit()
        row.addWidget(field)
        button = QPushButton('Browse…')
        def browse():
            path = (QFileDialog.getExistingDirectory(self, label) if folder else
                    QFileDialog.getOpenFileName(self, label, '', file_filter)[0])
            if path:
                field.setText(path)
        button.clicked.connect(browse)
        row.addWidget(button)
        layout.addLayout(row)
        return field

    def populate(self):
        self.saved.blockSignals(True)
        self.saved.clear()
        for index, report in enumerate(self.job.consumer_reports):
            self.saved.addItem(f"{index + 1}. {report['consumer']} — run {report['dataset']['run_id']}")
        self.saved.setCurrentIndex(len(self.job.consumer_reports) - 1)
        self.saved.blockSignals(False)
        self.select_report()

    def selected(self):
        index = self.saved.currentIndex()
        return self.job.consumer_reports[index] if 0 <= index < len(self.job.consumer_reports) else None

    def remove_selected(self):
        if not self.busy and self.selected() is not None:
            self.job.consumer_reports.pop(self.saved.currentIndex())
            self._window.project_actions.mark_dirty()
            self.populate()

    def select_report(self):
        self.models.blockSignals(True)
        self.models.clear()
        report = self.selected()
        if report:
            self.consumer.setCurrentIndex(self.consumer.findData(report['consumer']))
            for model in report['models']:
                self.models.addItem(f"{model['label']} [{model['id']}]", model['id'])
            if not report['models']:
                self.models.addItem('Log only — view membership unknown', None)
        self.models.blockSignals(False)
        self.reset_page()

    def reset_page(self):
        self.page = 0
        self.refresh()

    def turn_page(self, delta):
        self.page = max(0, self.page + delta)
        self.refresh()

    def refresh(self):
        report = self.selected()
        self.export_button.setEnabled(report is not None and not self.busy)
        if report is None:
            self.table.setRowCount(0)
            self.summary.setText('No imported report. Save the project to retain imports.')
            self.details.clear()
            self.warnings.clear()
            self.previous.setEnabled(False)
            self.next.setEnabled(False)
            return
        data = coverage(report, self.models.currentData())
        current = self.job.result.get('run_id') == report['dataset']['run_id']
        counts = ', '.join(f'{LABELS[k]}: {v}' for k, v in data['totals'].items())
        capture_counts = data['capture_totals']
        self.summary.setText(f"{'Last extraction' if current else 'Historical export'} — {counts}. "
                             f"Known retained physical captures: {capture_counts['any_retained']}/{capture_counts['exported']}; "
                             f"{capture_counts['all_retained']} with all exported views retained. "
                             'Coverage uses confirmed exported views, not six assumed views per capture. Save the project to retain imports.')
        def describe(values):
            return ', '.join(f'{LABELS[k]} {values[k]}' for k in STATES if values.get(k))
        self.details.setPlainText('Direction coverage\n' + '\n'.join(f'{key}: {describe(value)}' for key, value in data['directions'].items()))
        warning_counts: dict[str, int] = {}
        for warning in report['warnings']:
            if warning['kind'] == 'mask' and warning['image']:
                warning_counts[warning['image']] = warning_counts.get(warning['image'], 0) + 1
        text = self.search.text().casefold()
        rows = [v for v in data['views'] if (self.state.currentData() is None or self.state.currentData() == v['state'])
                and (not text or text in f"{v['image']} {v['frame']} {v['camera']}".casefold())]
        self.page = min(self.page, max(0, (len(rows) - 1) // 200))
        shown = rows[self.page * 200:(self.page + 1) * 200]
        self.previous.setEnabled(self.page > 0)
        self.next.setEnabled((self.page + 1) * 200 < len(rows))
        self.table.setRowCount(len(shown))
        for i, row in enumerate(shown):
            values = (row['image'], str(row['frame']), row['camera'], LABELS[row['state']],
                      describe(data['captures'][str(row['frame'])]),
                      'Unknown' if report['log_scope'] is None else str(warning_counts.get(row['image'], 0)))
            for j, value in enumerate(values):
                self.table.setItem(i, j, QTableWidgetItem(value))
        self.table.resizeColumnsToContents()
        warning_text = ('Log not supplied; mask warnings unknown.' if report['log_scope'] is None else
                        f"Log scope: {report['log_scope']}\n" + ('\n'.join(
                            f"{'Mapped to ' + w['image'] if w['mapped'] else 'Unmapped'}: {w['message']}"
                            for w in report['warnings']) or 'No warnings found in this log scope.'))
        self.warnings.setPlainText(warning_text)

    def start_import(self):
        if self.busy:
            return
        if len(self.job.consumer_reports) >= MAX_REPORTS:
            QMessageBox.warning(self, 'Consumer reports', f'This source already has {MAX_REPORTS} saved reports.')
            return
        self.import_button.setEnabled(False)
        self.export_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.summary.setText('Reading reports…')
        self._thread = ConsumerImportThread(self.dataset.text(), self.consumer.currentData(),
                                          self.cameras.text(), self.log.text(), self)
        self._thread.finished.connect(self.finished_import)
        self._thread.start()

    def finished_import(self):
        thread, self._thread = self._thread, None
        if thread is None:
            return
        self.import_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        if not thread.cancelled.is_set() and not self.closing:
            if thread.error:
                QMessageBox.warning(self, 'Consumer reports', thread.error)
            elif thread.report is not None:
                identity = thread.report['dataset']['source_identity']
                expected = self.job.source_identity
                if expected is None or any(identity.get(k) != expected.get(k) for k in ('size_bytes', 'mtime_ns')):
                    QMessageBox.warning(self, 'Consumer reports', 'This export does not match the selected source size/date. Locate the source or choose its export.')
                else:
                    self.job.consumer_reports.append(copy.deepcopy(thread.report))
                    self._window.project_actions.mark_dirty()
                    self.populate()
        thread.deleteLater()
        self.refresh()
        if self.closing:
            self.close()

    def cancel(self):
        if self._thread:
            self._thread.cancelled.set()

    def closeEvent(self, event):
        if self.busy:
            self.closing = True
            self.cancel()
            event.ignore()
        else:
            event.accept()

    def reject(self):
        # Escape uses reject(), bypassing closeEvent. Keep the same cancellation
        # contract and wait for the worker before dismissing the dialog.
        if self.busy:
            self.closing = True
            self.cancel()
        else:
            super().reject()

    def save_template(self):
        path = QFileDialog.getSaveFileName(self, 'Save RealityScan input-state template', '360extractor-realityscan.txt', 'Text (*.txt)')[0]
        if path:
            try:
                write_template(Path(path))
            except (OSError, ValueError) as exc:
                QMessageBox.warning(self, 'Consumer reports', str(exc))

    def save_selected(self):
        report = self.selected()
        if report:
            path = QFileDialog.getSaveFileName(self, 'Save consumer report (new file)', 'consumer-report.json', 'JSON (*.json)')[0]
            if path:
                try:
                    write_report(Path(path), report)
                except (OSError, ValueError) as exc:
                    QMessageBox.warning(self, 'Consumer reports', str(exc))
