"""Shared decoder-clock validation for extraction and chronological previews."""
import math


def frame_step(interval):
    """Normalize the Frames interval identically for export and estimates."""
    return max(1, int(interval))


class FrameClock:
    def __init__(self, fps):
        self.fps = float(fps)
        self.previous = None
        self.sources = set()

    @property
    def source(self):
        return next(iter(self.sources)) if len(self.sources) == 1 else "mixed" if self.sources else "unknown"

    def resolve(self, frame_index, decoder_seconds):
        timestamp = float(decoder_seconds)
        valid = math.isfinite(timestamp) and timestamp >= 0 and (frame_index == 0 or timestamp > 0)
        valid = valid and (self.previous is None or timestamp > self.previous)
        source = "decoder_timestamp"
        if not valid:
            if not math.isfinite(self.fps) or self.fps <= 0:
                raise ValueError("Decoder timestamp is unavailable and FPS cannot establish frame time")
            timestamp = frame_index / self.fps
            if self.previous is not None:
                timestamp = max(timestamp, self.previous + 1 / self.fps)
            source = "fps_estimate"
        self.previous = timestamp
        self.sources.add(source)
        return timestamp, source
