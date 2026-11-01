"""Edit source-specific extraction ranges without changing other jobs/defaults."""
from typing import cast
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QDialog, QDialogButtonBox, QHBoxLayout, QHeaderView, QLabel,
                               QMessageBox, QPushButton, QSpinBox, QTableWidget, QVBoxLayout)

from extractor360.core.selection import FrameSelection, normalize_ranges


class SelectionDialog(QDialog):
    def __init__(self, window, job, total):
        super().__init__(window)
        self._window, self.job, self.total = window, job, total
        self.ranges = normalize_ranges(job.settings.get('included_frame_ranges', []))
        self.setObjectName('extractionRanges')
        self.setWindowTitle(f'Extraction ranges — {job.filename}')
        self.resize(640, 420)
        layout = QVBoxLayout(self)
        help_text = QLabel(f'Keep portions of this video for extraction (frames 0–{total - 1}, endpoints included). '
                          'All views of each frame stay together. Individual exclusions still apply.\n'
                          f'Current interval: {job.settings.get("interval_value", 1)} {job.settings.get("interval_unit", "Seconds")}. '
                          'Sampling stays anchored at source start; range boundaries are not forced captures.')
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

    def accept(self):
        try:
            ranges = [] if self.all_source.isChecked() else [
                [cast(QSpinBox, self.table.cellWidget(row, col)).value() for col in (0, 1)] for row in range(self.table.rowCount())]
            if not self.all_source.isChecked() and not ranges:
                raise ValueError('Add a range or select Whole source.')
            ranges = normalize_ranges(ranges)
            FrameSelection(ranges).validate_source(self.total)
        except ValueError as exc:
            QMessageBox.warning(self, 'Extraction ranges', str(exc))
            return
        self.ranges = ranges
        super().accept()
