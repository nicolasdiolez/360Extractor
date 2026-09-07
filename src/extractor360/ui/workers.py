"""Qt-side adapters around the Qt-free processing core."""
import copy
import threading

from PySide6.QtCore import QObject, QThread, Signal

from extractor360.core.analyzer import BlurAnalyzer
from extractor360.core.processor import ProcessingWorker


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
    job_cancelled = Signal(int)
    finished = Signal()

    def attach(self, worker):
        """Subscribe this bridge to all of a worker's events."""
        worker.progress_updated.connect(self.progress_updated.emit)
        worker.job_started.connect(self.job_started.emit)
        worker.job_finished.connect(self.job_finished.emit)
        worker.job_error.connect(self.job_error.emit)
        worker.job_cancelled.connect(self.job_cancelled.emit)
        worker.finished.connect(self.finished.emit)
        return self


class ProcessingThread(QThread):
    def __init__(self, worker, parent=None):
        super().__init__(parent)
        self.worker = worker

    def run(self):
        self.worker.run()


class ProcessingController(QObject):
    """Own one extraction until the thread has actually terminated."""

    finished = Signal()

    def __init__(self, jobs, parent=None):
        super().__init__(parent)
        self.worker = ProcessingWorker(copy.deepcopy(jobs))
        self.bridge = ProcessingBridge(self).attach(self.worker)
        self._thread = ProcessingThread(self.worker, self)
        self._thread.finished.connect(self.finished)

    def start(self):
        self._thread.start()

    def stop(self):
        self.worker.stop()

    def is_running(self):
        return self._thread.isRunning()


class BlurAnalysisWorker(QObject):
    """Runs the (pure) blur analysis in a QThread for the GUI."""

    finished = Signal(dict)
    error = Signal(str)

    def __init__(self, video_path, settings):
        super().__init__()
        self.video_path = video_path
        self.settings = settings
        self.cancelled = threading.Event()

    def stop(self):
        self.cancelled.set()

    def run(self):
        try:
            result = BlurAnalyzer.analyze_sample(self.video_path, self.settings, self.cancelled.is_set)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))
