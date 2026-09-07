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
