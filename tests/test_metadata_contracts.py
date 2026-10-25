import json
import struct
from unittest.mock import patch

import pytest

from extractor360.core.telemetry import TelemetryHandler
from extractor360.utils.camm_parser import parse_camm_data
from extractor360.utils.gpmf_parser import GPMFParser
from extractor360.utils.gpx_parser import parse_gpx_data


def test_camm_complete_packet_and_pts():
    data=struct.pack('<HHdidd7f',0,6,1400000000.,3,48.,2.,100.,1.,2.,0.,0.,0.,1.)
    sample=parse_camm_data(data, timestamp=12.25)[0]
    assert sample['timestamp']==12.25
    assert sample['lat']==48 and sample['lon']==2 and sample['alt']==100
    assert sample['altitude_reference']=='wgs84_ellipsoid'
    assert sample['time_source']=='packet_pts'
    with pytest.raises(ValueError):
        parse_camm_data(data[:-1],timestamp=12.25)


def test_camm_type_zero_does_not_desynchronize():
    data=struct.pack('<HH3f',0,0,1.,2.,3.)+struct.pack('<HHddd',0,5,48.,2.,100.)
    assert parse_camm_data(data,timestamp=4)[0]['lat']==48


@pytest.mark.parametrize('namespace',['http://www.topografix.com/GPX/1/0','http://www.topografix.com/GPX/1/1',''])
def test_gpx_namespaces(namespace):
    data=f'<gpx xmlns="{namespace}"><trk><trkseg><trkpt lat="48" lon="2"><ele>123</ele><time>2026-01-01T00:00:00Z</time></trkpt></trkseg></trk></gpx>'
    result=parse_gpx_data(data)
    assert len(result)==1 and result[0]['alt']==123


def test_gpmf_byte_types():
    parser=GPMFParser()
    assert parser._unpack_values(b'\x00\xff','B',1,2)==[0,255]
    assert parser._unpack_values(b'\xff','b',1,1)==[-1]


def test_packet_hex_decode_preserves_pts_and_payload():
    handler=TelemetryHandler()
    raw=json.dumps({'packets':[{'pts_time':'5.5','duration_time':'0.5','data':'\n00000000: 0000 0500 0102 0304                      ........\n'}]}).encode()
    with patch('extractor360.core.telemetry.capture',return_value=raw):
        assert list(handler._metadata_packets('source.mp4',1))==[(5.5,.5,bytes.fromhex('0000050001020304'))]


def test_no_extrapolation_gap_or_long_way_around_globe():
    handler=TelemetryHandler()
    handler.gps_samples=[dict(timestamp=0,lat=20,lon=179,alt=10),dict(timestamp=2,lat=20,lon=-179,alt=10)]
    handler.has_gps=True
    assert handler.get_gps_at_time(-1) is None
    assert handler.get_gps_at_time(3) is None
    assert abs(handler.get_gps_at_time(1)[1])==180
    handler.gps_samples=[dict(timestamp=0,lat=20,lon=2,alt=10),dict(timestamp=100,lat=20,lon=3,alt=10)]
    assert handler.get_gps_at_time(50) is None


def test_missing_metadata_clears_previous_samples(tmp_path):
    handler=TelemetryHandler()
    handler.has_gps=True
    handler.gps_samples=[dict(timestamp=0,lat=20,lon=2,alt=10)]
    with patch('extractor360.core.telemetry.capture',side_effect=FileNotFoundError):
        assert not handler.extract_metadata(str(tmp_path/'video.mp4'))
    assert not handler.has_gps and handler.gps_samples==[]
    assert handler.metadata['status']=='failed'


def _srt(altitude='[rel_alt: 12.5]'):
    return ('1\n00:00:00,000 --> 00:00:01,000\n'
            f'[latitude: 48] [longitude: 2] {altitude}\n').encode()


def test_relative_only_srt_never_becomes_orthometric_altitude():
    from extractor360.utils.srt_parser import parse_srt_data
    handler = TelemetryHandler(altitude_mode='absolute')
    handler.gps_samples = handler._sanitize_gps_samples(parse_srt_data(_srt()))
    handler.has_gps = True
    assert handler.gps_samples[0]['altitude_reference'] == 'relative'
    assert handler.gps_samples[0]['altitude_source'] == 'rel_alt'
    assert handler.get_gps_at_time(0) == (48, 2, 12.5)
    assert handler.get_gps_at_time(0, orthometric=True) == (48, 2, None)


def test_missing_gpx_elevation_and_interpolation_preserve_horizontal_fix():
    content = '<gpx><trk><trkseg><trkpt lat="48" lon="2"><time>2026-01-01T00:00:00Z</time></trkpt><trkpt lat="49" lon="3"><ele>100</ele><time>2026-01-01T00:00:02Z</time></trkpt></trkseg></trk></gpx>'
    handler = TelemetryHandler()
    handler.gps_samples = handler._sanitize_gps_samples(parse_gpx_data(content))
    handler.has_gps = True
    assert handler.gps_samples[0]['alt'] is None
    assert handler.gps_samples[0]['altitude_source'] == 'missing'
    assert handler.get_gps_at_time(0, orthometric=True) == (48, 2, None)
    assert handler.get_gps_at_time(1, orthometric=True) == (48.5, 2.5, None)


def test_altitude_interpolation_does_not_mix_references():
    handler = TelemetryHandler()
    handler.gps_samples = [dict(timestamp=0, lat=48, lon=2, alt=10, altitude_reference='relative'),
                           dict(timestamp=2, lat=49, lon=3, alt=100, altitude_reference='absolute')]
    handler.has_gps = True
    assert handler.get_gps_at_time(1) == (48.5, 2.5, None)


def test_embedded_srt_metadata_reports_success(tmp_path):
    handler = TelemetryHandler()
    probe = {'streams': [{'index': 1, 'codec_type': 'subtitle'}]}
    with patch('extractor360.core.telemetry.capture', side_effect=[json.dumps(probe).encode(), _srt()]):
        assert handler.extract_metadata(str(tmp_path / 'clip.mp4'))
    assert handler.metadata['status'] == 'valid'
    assert handler.metadata['source'] == 'embedded_srt'
    assert handler.metadata['time_source'] == 'subtitle_pts'


def test_sidecar_priority_and_capture_date_are_independent(tmp_path):
    # Create SRT first: filesystem iteration order must not determine priority.
    (tmp_path / 'Clip.SRT').write_bytes(_srt())
    gpx = tmp_path / 'clip.GPX'
    gpx.write_text('<gpx><trk><trkseg><trkpt lat="50" lon="3"><ele>123</ele><time>2026-01-01T00:00:00Z</time></trkpt></trkseg></trk></gpx>')
    probe = {'format': {'tags': {'creation_time': '2026-10-23T00:00:00Z'}}}
    handler = TelemetryHandler()
    with patch('extractor360.core.telemetry.capture', return_value=json.dumps(probe).encode()):
        assert handler.extract_metadata(str(tmp_path / 'CLIP.mp4'))
        assert handler.metadata['source'] == 'clip.GPX'
        assert handler.metadata['format_tags']['creation_time'] == '2026-10-23T00:00:00Z'
        gpx.write_text('invalid xml')
        assert handler.extract_metadata(str(tmp_path / 'CLIP.mp4'))
        assert handler.metadata['source'] == 'Clip.SRT'


def test_sidecar_gps_works_without_ffprobe(tmp_path):
    (tmp_path / 'clip.srt').write_bytes(_srt())
    handler = TelemetryHandler()
    with patch('extractor360.core.telemetry.capture', side_effect=FileNotFoundError('ffprobe')):
        assert handler.extract_metadata(str(tmp_path / 'clip.mp4'))
    assert handler.metadata['status'] == 'valid'
    assert handler.metadata['container_status'] == 'unavailable'
