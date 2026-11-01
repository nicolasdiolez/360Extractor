"""Inclusive source-frame selections; empty ranges mean the whole source.

Ranges restrict eligibility without restarting the source's sampling cadence.
They are source-specific decisions, independent of diagnostic windows.
"""
from bisect import bisect_right


def normalize_ranges(value):
    if (not isinstance(value, list) or len(value) > 1000
            or any(not isinstance(pair, list) or len(pair) != 2
                   or any(type(n) is not int or not 0 <= n <= 2147483647 for n in pair)
                   or pair[0] > pair[1] for pair in value)):
        raise ValueError('included_frame_ranges must contain at most 1000 inclusive [start, end] frame pairs')
    result: list[list[int]] = []
    for start, end in sorted(value):
        if result and start <= result[-1][1] + 1:
            result[-1][1] = max(end, result[-1][1])
        else:
            result.append([start, end])
    return result


class FrameSelection:
    def __init__(self, ranges):
        self.ranges = normalize_ranges(ranges)
        self.starts = [pair[0] for pair in self.ranges]

    def contains(self, frame):
        if not self.ranges:
            return True
        index = bisect_right(self.starts, frame) - 1
        return index >= 0 and frame <= self.ranges[index][1]

    def validate_source(self, total, is_image=False):
        if self.ranges and (is_image or total <= 0 or self.ranges[-1][1] >= total):
            raise ValueError('Extraction ranges require a video with a known frame count and endpoints inside the source')

    def intervals(self, total, window=None):
        self.validate_source(total)
        low, high = window if window is not None else (0, total - 1)
        return [[max(start, low), min(end, high)] for start, end in self.ranges or [[0, total - 1]]
                if max(start, low) <= min(end, high)]

    def sampled_count(self, total, step, excluded=()):
        count = sum(end // step - (start - 1) // step for start, end in self.intervals(total))
        return count - sum(0 <= f < total and self.contains(f) and f % step == 0 for f in set(excluded))
