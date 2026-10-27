"""Studio document actions; processing and model loading remain elsewhere."""
from __future__ import annotations

import copy
import hashlib
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QFileDialog, QMessageBox

from extractor360.core.project import Project, read_project, write_project, relink_source, source_identity, source_problem
from extractor360.core.version import APP_NAME

if TYPE_CHECKING:
    from extractor360.ui.main_window import MainWindow


class ProjectActions:
    def __init__(self, window: MainWindow):
        self.window = window
        self.project_id = Project().project_id
        self.path: Path | None = None
        self.digest: str | None = None
        self.dirty = False
        self.loading = False
        menu = window.menuBar().addMenu('&Project')
        self.menu = menu
        for label, shortcut, callback in [
            ('&New Project', QKeySequence.StandardKey.New, self.new),
            ('&Open Project…', QKeySequence.StandardKey.Open, self.open),
            ('&Save Project', QKeySequence.StandardKey.Save, self.save),
            ('Save Project &As…', QKeySequence.StandardKey.SaveAs, self.save_as),
        ]:
            action = QAction(label, window)
            action.setShortcut(QKeySequence(shortcut))
            action.triggered.connect(callback)
            menu.addAction(action)
        menu.addSeparator()
        self.locate_action = menu.addAction('Locate Selected Source…', self.locate_source)
        menu.addAction('Alignment Diagnostic…', window.open_alignment)
        self.update_title()

    def busy(self) -> bool:
        return self.window.is_processing or self.window._blur_thread is not None or self.window.alignment_busy()

    def update_title(self):
        name = self.path.name if self.path else 'Untitled project'
        self.window.setWindowTitle(f'{APP_NAME} Studio — {name}' + (' *' if self.dirty else ''))

    def mark_dirty(self):
        if not self.loading:
            self.dirty = True
            self.update_title()

    def snapshot(self) -> Project:
        return Project(jobs=list(self.window.jobs), default_settings=copy.deepcopy(self.window.default_settings),
                       selected_job_ids=[card.job.job_id for card in self.window._selected_cards],
                       project_id=self.project_id)

    def confirm_discard(self) -> bool:
        if not self.dirty:
            return True
        answer = QMessageBox.question(self.window, 'Unsaved project', 'Save project changes before continuing?',
                                      QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
                                      QMessageBox.StandardButton.Save)
        if answer == QMessageBox.StandardButton.Save:
            return self.save()
        return answer == QMessageBox.StandardButton.Discard

    def _error(self, exc):
        QMessageBox.warning(self.window, 'Project', str(exc))

    def save_to(self, path: Path, expected_digest: str | None = None):
        if self.busy():
            raise ValueError('Wait for extraction or analysis to finish before saving the project')
        path = Path(path).absolute()
        if path == self.path:
            expected_digest = self.digest
        digest = write_project(path, self.snapshot(), expected_digest)
        self.path, self.digest = path, digest
        self.dirty = False
        self.update_title()

    def save(self) -> bool:
        if self.path is None:
            return self.save_as()
        try:
            self.save_to(self.path)
        except (OSError, ValueError, TypeError) as exc:
            self._error(exc)
            return False
        return True

    def save_as(self) -> bool:
        if self.busy():
            return False
        name, _ = QFileDialog.getSaveFileName(self.window, 'Save 360 Extractor Project',
                                            str(self.path or Path.cwd() / 'Untitled.360proj'),
                                            '360 Extractor Project (*.360proj)')
        if not name:
            return False
        path = Path(name)
        if path.suffix.lower() != '.360proj':
            path = path.with_name(path.name + '.360proj')
        try:
            digest = None
            if path.exists() and path.absolute() != self.path:
                answer = QMessageBox.question(self.window, 'Replace project', f'Replace {path.name}?',
                                              QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                              QMessageBox.StandardButton.No)
                if answer != QMessageBox.StandardButton.Yes:
                    return False
                digest = hashlib.sha256(path.read_bytes()).hexdigest()
            self.save_to(path, digest)
        except (OSError, ValueError, TypeError) as exc:
            self._error(exc)
            return False
        return True

    def load_from(self, path: Path) -> bool:
        if self.busy():
            raise ValueError('Wait for extraction or analysis to finish before opening a project')
        # Parse everything first: a malformed file must not discard the queue.
        project, digest = read_project(path)
        if not self.confirm_discard():
            return False
        # Save in the prompt can update this very file. Do not install the
        # stale snapshot read before consent (or a concurrently changed file).
        project, digest = read_project(path)
        self.install(project, Path(path).absolute(), digest)
        return True

    def open(self):
        if self.busy() or self.window._closing:
            return
        path, _ = QFileDialog.getOpenFileName(self.window, 'Open 360 Extractor Project',
                                            str(self.path.parent) if self.path else '',
                                            '360 Extractor Project (*.360proj)')
        if path:
            try:
                self.load_from(Path(path))
            except (OSError, ValueError, TypeError) as exc:
                self._error(exc)

    def new(self):
        if self.busy() or self.window._closing or not self.confirm_discard():
            return
        self.install(Project(default_settings=self.window.settings_manager.get_all()), None, None)

    def install(self, project: Project, path: Path | None, digest: str | None):
        window = self.window
        self.loading = True
        try:
            window.preview_widget.update_preview(None, {})
            for card in window._video_cards:
                card._cleanup_thread()
                card.hide()
                window.cards_layout.removeWidget(card)
                card.deleteLater()
            window._video_cards.clear()
            window._selected_cards.clear()
            window.jobs.clear()
            window._media_info.clear()
            window._job_settings_revisions.clear()
            window.default_settings = copy.deepcopy(project.default_settings)
            window.set_ui_from_settings(window.default_settings)
            window._append_jobs(project.jobs)
            self.project_id, self.path, self.digest = project.project_id, path, digest
            by_id = {card.job.job_id: card for card in window._video_cards}
            for job_id in project.selected_job_ids:
                card = by_id[job_id]
                window._selected_cards.append(card)
                card.setSelected(True)
            if window._selected_cards:
                window.set_ui_from_settings(window._selected_cards[-1].job.settings)
            window._update_queue_ui_state()
            window.update_preview_display()
            window.update_estimate()
            for job in window.jobs:
                problem = source_problem(job)
                if problem:
                    window.log_panel.log(f'{job.filename}: {problem}', 'WARNING')
            self.dirty = False
            self.update_title()
        finally:
            self.loading = False

    def locate_source(self):
        window = self.window
        if self.busy() or window._closing:
            return
        if len(window._selected_cards) != 1:
            self._error('Select exactly one source to locate')
            return
        job = window._selected_cards[0].job
        name, _ = QFileDialog.getOpenFileName(window, 'Locate Source', job.file_path,
                                            'Media (*.mp4 *.mov *.avi *.mkv *.insv *.jpg *.jpeg *.png *.tif *.tiff)')
        if not name:
            return
        try:
            source = str(Path(name).resolve(strict=True))
            if any(other is not job and Path(other.file_path).resolve() == Path(source) for other in window.jobs):
                raise ValueError('This source is already in the project')
            if job.source_identity != source_identity(source):
                answer = QMessageBox.question(window, 'Confirm source',
                    'This file has a different size/date, or its original identity is unavailable. '
                    'Use it with the saved settings? The old result association will be cleared.',
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
                if answer != QMessageBox.StandardButton.Yes:
                    return
            relink_source(job, source)
            self.install(self.snapshot(), self.path, self.digest)
            self.mark_dirty()
        except (OSError, ValueError) as exc:
            self._error(exc)
