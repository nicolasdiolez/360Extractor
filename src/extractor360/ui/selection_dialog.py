"""Edit source-specific extraction ranges without changing other jobs/defaults."""
from typing import cast
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QHBoxLayout, QHeaderView, QLabel,
                               QLineEdit, QMessageBox, QPushButton, QSpinBox, QTableWidget, QVBoxLayout)

from extractor360.core.selection import FrameSelection, normalize_ranges
from extractor360.core.capture_plan import baseline_frames, baseline_from_window, normalize_capture_plan, planned_frames, validate_plan_selection


class SelectionDialog(QDialog):
    def __init__(self, window, job, total):
        super().__init__(window)
        self._window, self.job, self.total = window, job, total
        self.ranges = normalize_ranges(job.settings.get('included_frame_ranges', []))
        self.capture_plan = normalize_capture_plan(job.settings.get('capture_plan'))
        self.setObjectName('extractionRanges')
        self.setWindowTitle(f'Extraction ranges — {job.filename}')
        self.resize(720, 640)
        layout = QVBoxLayout(self)
        help_text = QLabel(f'Keep portions of this video for extraction (frames 0–{total - 1}, endpoints included). '
                          'All views of each frame stay together. Individual exclusions still apply.\n'
                          f'Interval mode: {job.settings.get("interval_value", 1)} {job.settings.get("interval_unit", "Seconds")}, anchored at source start. '
                          'The 16/31 capture modes below use their frozen reference instead.')
        help_text.setWordWrap(True)
        help_text.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(help_text)
        self.all_source = QCheckBox('Whole source')
        self.all_source.setChecked(not self.ranges)
        layout.addWidget(self.all_source)
        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(['First source frame', 'Last source frame (included)'])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        layout.addWidget(self.table)
        row = QHBoxLayout()
        self.add_button = QPushButton('Add range')
        self.remove_button = QPushButton('Remove selected range')
        self.add_button.clicked.connect(lambda: self.add_range(0, total - 1))
        self.remove_button.clicked.connect(self.remove_range)
        row.addWidget(self.add_button)
        row.addWidget(self.remove_button)
        for text, column in [('Preview start', 0), ('Preview end', 1)]:
            button = QPushButton(text)
            button.clicked.connect(lambda checked=False, c=column: self.preview(c))
            row.addWidget(button)
        layout.addLayout(row)
        self.capture_mode = QComboBox()
        for title, mode in [('Sampling: current interval', 'interval'), ('Sampling: 16 reference captures', 'baseline'),
                            ('Sampling: 31 captures (16 reference + 15 midpoints)', 'densified')]:
            self.capture_mode.addItem(title, mode)
        self.capture_mode.setCurrentIndex(self.capture_mode.findData(self.capture_plan['mode'] if self.capture_plan else 'interval'))
        layout.addWidget(self.capture_mode)
        layout.addWidget(QLabel('Frozen reference — 16 increasing source-frame indices, separated by commas:'))
        self.baseline_edit = QLineEdit(', '.join(map(str, self.capture_plan['baseline_frames'])) if self.capture_plan else '')
        self.baseline_edit.setPlaceholderText('Paste the original 16 frame indices, or create a reference below')
        layout.addWidget(self.baseline_edit)
        reference_row = QHBoxLayout()
        self.build_reference = QPushButton('Create 16 from the selected range')
        self.build_reference.clicked.connect(self.create_reference)
        reference_row.addWidget(self.build_reference)
        self.use_diagnostic = QPushButton("Use last diagnostic's 16")
        self.use_diagnostic.clicked.connect(self.use_diagnostic_reference)
        self.use_diagnostic.setEnabled(bool(job.result.get('alignment')))
        reference_row.addWidget(self.use_diagnostic)
        layout.addLayout(reference_row)
        self.plan_summary = QLabel()
        self.plan_summary.setWordWrap(True)
        self.plan_summary.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self.plan_summary)
        self.capture_mode.currentIndexChanged.connect(self.update_plan_summary)
        self.baseline_edit.textChanged.connect(self.update_plan_summary)
        self.update_plan_summary()
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        for start, end in self.ranges or [[0, total - 1]]:
            self.add_range(start, end)
        self.all_source.toggled.connect(self.update_enabled)
        self.update_enabled()

    def add_range(self, start, end):
        row = self.table.rowCount()
        self.table.insertRow(row)
        for column, value in enumerate((start, end)):
            spin = QSpinBox()
            # Preserve stale endpoints visibly; never clamp them to a new source.
            spin.setRange(0, 2147483647)
            spin.setValue(value)
            self.table.setCellWidget(row, column, spin)
        self.table.selectRow(row)

    def remove_range(self):
        row = self.table.currentRow()
        if row >= 0:
            self.table.removeRow(row)

    def update_enabled(self):
        enabled = not self.all_source.isChecked()
        for widget in (self.table, self.add_button, self.remove_button):
            widget.setEnabled(enabled)

    def preview(self, column):
        row = self.table.currentRow()
        if row >= 0:
            frame = cast(QSpinBox, self.table.cellWidget(row, column)).value()
            if frame < self.total:
                self._window.preview_widget.seek_frame(frame)

    def read_ranges(self):
        ranges = [] if self.all_source.isChecked() else [
            [cast(QSpinBox, self.table.cellWidget(row, col)).value() for col in (0, 1)] for row in range(self.table.rowCount())]
        if not self.all_source.isChecked() and not ranges:
            raise ValueError('Add a range or select Whole source.')
        ranges = normalize_ranges(ranges)
        FrameSelection(ranges).validate_source(self.total)
        return ranges

    def read_plan(self):
        if self.capture_mode.currentData() == 'interval':
            return None
        try:
            frames = [int(text.strip()) for text in self.baseline_edit.text().split(',')]
        except ValueError:
            raise ValueError('Enter exactly 16 increasing source-frame indices separated by commas') from None
        return normalize_capture_plan({'mode': self.capture_mode.currentData(), 'baseline_frames': frames})

    def set_reference(self, frames):
        self.baseline_edit.setText(', '.join(map(str, baseline_frames(frames))))
        if self.capture_mode.currentData() == 'interval':
            self.capture_mode.setCurrentIndex(self.capture_mode.findData('baseline'))

    def create_reference(self):
        try:
            ranges = self.read_ranges() or [[0, self.total - 1]]
            if len(ranges) != 1:
                raise ValueError('Choose one continuous range to create a reference, or paste the original 16 indices')
            self.set_reference(baseline_from_window(*ranges[0]))
        except ValueError as exc:
            QMessageBox.warning(self, 'Capture reference', str(exc))

    def use_diagnostic_reference(self):
        try:
            report = self.job.result.get('alignment', {})
            if not isinstance(report, dict):
                raise ValueError('The saved diagnostic cannot be read; paste a verified reference instead')
            self.set_reference(report.get('requested_frames', report.get('sampled_frames')))
        except ValueError as exc:
            QMessageBox.warning(self, 'Capture reference', str(exc))

    def update_plan_summary(self):
        try:
            plan = self.read_plan()
            if plan is None:
                message = 'The current interval controls extraction. A reference is frozen only when saved in a 16/31 mode.'
            else:
                added = [f for f in planned_frames(plan) if f not in plan['baseline_frames']]
                message = ('16 reference captures stay fixed; the interval is bypassed. '
                           + ('15 inserted frames: ' + ', '.join(map(str, added)) + '. ' if added else '')
                           + 'Ranges/exclusions must retain every planned frame. Disable blur, motion and AI Skip Frame rejection.')
            self.plan_summary.setText(message)
        except ValueError as exc:
            self.plan_summary.setText(str(exc))

    def accept(self):
        try:
            ranges = self.read_ranges()
            plan = self.read_plan()
            validate_plan_selection({**self.job.settings, 'included_frame_ranges': ranges, 'capture_plan': plan}, self.total)
        except ValueError as exc:
            QMessageBox.warning(self, 'Extraction ranges', str(exc))
            return
        self.ranges = ranges
        self.capture_plan = plan
        super().accept()
