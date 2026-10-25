"""CAMM GPS records (Google Camera Motion Metadata specification).

https://developers.google.com/streetview/publish/camm-spec
A media demuxer must provide packet PTS for synchronization. The legacy duration
argument only produces explicitly estimated timestamps for standalone raw dumps.
"""
import math
import struct

_SIZES = {0: 12, 1: 8, 2: 12, 3: 12, 4: 12, 5: 24, 6: 56, 7: 12}


def parse_camm_data(raw_data: bytes, duration: float = 0.0, timestamp=None) -> list[dict]:
    samples = []
    offset = 0
    while offset + 4 <= len(raw_data):
        reserved, kind = struct.unpack_from('<HH', raw_data, offset)
        size = _SIZES.get(kind)
        if reserved or size is None or offset + 4 + size > len(raw_data):
            raise ValueError(f'Invalid or truncated CAMM packet at byte {offset}')
        offset += 4
        sample = None
        if kind == 5:
            lat, lon, alt = struct.unpack_from('<ddd', raw_data, offset)
            sample = dict(lat=lat, lon=lon, alt=alt, altitude_reference='unspecified')
        elif kind == 6:
            epoch, fix, lat, lon, alt, hacc, vacc, ve, vn, vu, sacc = struct.unpack_from('<didd7f', raw_data, offset)
            if fix in (2, 3):
                sample = dict(lat=lat, lon=lon, alt=alt, gps_epoch=epoch, fix=fix,
                              horizontal_accuracy=hacc, vertical_accuracy=vacc,
                              altitude_reference='wgs84_ellipsoid')
        if sample and all(math.isfinite(sample[k]) for k in ('lat', 'lon', 'alt')):
            if -90 <= sample['lat'] <= 90 and -180 <= sample['lon'] <= 180 and (abs(sample['lat']) > .0001 or abs(sample['lon']) > .0001):
                samples.append(sample)
        offset += size
    if offset != len(raw_data):
        raise ValueError('Truncated CAMM header')
    for index, sample in enumerate(samples):
        sample['timestamp'] = float(timestamp) if timestamp is not None else (index * duration / len(samples) if duration > 0 else index * .2)
        sample['time_source'] = 'packet_pts' if timestamp is not None else 'estimated'
    return samples
