"""GPS samples shared by telemetry parsers and interpolation."""

from typing import NotRequired, TypedDict


class GPSSample(TypedDict):
    timestamp: float
    lat: float
    lon: float
    alt: float | None
    altitude_source: NotRequired[str]
    altitude_reference: NotRequired[str]
    time_source: NotRequired[str]
    fix: NotRequired[float | None]
    utc_epoch: NotRequired[float]
    gps_epoch: NotRequired[float]
    horizontal_accuracy: NotRequired[float]
    vertical_accuracy: NotRequired[float]
