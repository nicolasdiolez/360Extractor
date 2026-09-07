"""Minimal callback-based events so the processing core does not depend on Qt.

The API mirrors the subset of Qt signals this codebase uses (``connect`` /
``emit``): the CLI subscribes plain functions directly, and the GUI bridges
these events to real Qt signals (see ``extractor360.ui.workers``), which Qt
then delivers queued on the GUI thread.
"""


class Event:
    """A tiny synchronous multicast callback list."""

    def __init__(self):
        self._callbacks = []

    def connect(self, callback):
        self._callbacks.append(callback)

    def disconnect(self, callback=None):
        """Remove one subscriber, or all of them when called without argument."""
        if callback is None:
            self._callbacks.clear()
        else:
            try:
                self._callbacks.remove(callback)
            except ValueError:
                pass

    def emit(self, *args):
        # Iterate over a copy so a callback may disconnect during dispatch.
        for callback in list(self._callbacks):
            callback(*args)
