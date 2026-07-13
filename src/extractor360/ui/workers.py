"""Qt-side adapters around the Qt-free processing core."""
from PySide6.QtCore import QObject, Signal

from extractor360.core.analyzer import BlurAnalyzer


class ProcessingBridge(QObject):
    """Re-emits the core worker's plain events as Qt signals.

    The core :class:`~extractor360.core.processor.ProcessingWorker` fires its
    events synchronously on the worker thread. Routing them through this
    QObject (which lives in the GUI thread) makes Qt deliver them as queued
    signals on the GUI thread — the same guarantees the old QObject-based
    worker provided.
    """

    progress_updated = Signal(int, str)
    job_started = Signal(int)
    job_finished = Signal(int)
    job_error = Signal(int, str)
    finished = Signal()

    def attach(self, worker):
        """Subscribe this bridge to all of a worker's events."""
        worker.progress_updated.connect(self.progress_updated.emit)
        worker.job_started.connect(self.job_started.emit)
        worker.job_finished.connect(self.job_finished.emit)
        worker.job_error.connect(self.job_error.emit)
        worker.finished.connect(self.finished.emit)
        return self


class BlurAnalysisWorker(QObject):
    """Runs the (pure) blur analysis in a QThread for the GUI."""

    finished = Signal(dict)
    error = Signal(str)

    def __init__(self, video_path, settings):
        super().__init__()
        self.video_path = video_path
        self.settings = settings

    def run(self):
        try:
            result = BlurAnalyzer.analyze_sample(self.video_path, self.settings)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))
