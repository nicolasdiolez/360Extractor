import subprocess
import json
import logging
import bisect
import math
from typing import Optional, Tuple, List, Dict
import numpy as np
import piexif
from PIL import Image
from extractor360.core import exif_writer
from extractor360.utils.gpmf_parser import GPMFParser
from extractor360.utils.srt_parser import parse_srt_data
from extractor360.utils.camm_parser import parse_camm_data
from extractor360.utils.gpx_parser import parse_gpx_data
import os
import re
from pathlib import Path
from extractor360.utils.subprocess_utils import capture

logger = logging.getLogger(__name__)

_FFMPEG_INSTALL_HINT = (
    "Install FFmpeg first (macOS: 'brew install ffmpeg', Windows: 'winget install ffmpeg', "
    "Linux: 'sudo apt install ffmpeg') and make sure it is on your PATH."
)

class TelemetryHandler:
    def __init__(self, altitude_mode: str = 'absolute', cancelled=lambda: False):
        self.cancelled = cancelled
        self._times = []
        self._indexed_samples = None
        self.max_gap_seconds = 10.0
        self.metadata = {}
        self.has_gps = False
        self.gps_samples: List[Dict[str, float]] = []
        # Only affects DJI SRT clips that expose both rel_alt and abs_alt.
        # CAMM/GPMF/GPX sources carry a single altitude and ignore this.
        self.altitude_mode = altitude_mode

    @staticmethod
    def _sanitize_gps_samples(samples: List[Dict[str, float]]) -> List[Dict[str, float]]:
        """
        Validate GPS samples and return a clean, time-sorted list.

        Drops samples with missing/non-numeric coordinates, NaN/Inf values,
        coordinates outside the valid ranges (lat in [-90, 90], lon in
        [-180, 180]), or the (0,0) "Null Island" placeholder emitted by devices
        without a GPS fix (e.g. GoPro GPS5 before satellite lock). Sorting by
        timestamp is required for the bisect-based lookup in get_gps_at_time
        to be correct.
        """
        cleaned: List[Dict[str, float]] = []
        for s in samples or []:
            try:
                lat = float(s['lat'])
                lon = float(s['lon'])
                alt = float(s.get('alt', 0.0))
                ts = float(s.get('timestamp', 0.0))
            except (KeyError, TypeError, ValueError):
                continue

            if s.get('fix') not in (None, 2, 3):
                continue
            if not all(math.isfinite(v) for v in (lat, lon, alt, ts)):
                continue
            if not (-90.0 <= lat <= 90.0) or not (-180.0 <= lon <= 180.0):
                continue
            # (0,0) is the "no GPS fix yet" placeholder on several devices;
            # keeping it would geotag images at Null Island.
            if abs(lat) < 1e-4 and abs(lon) < 1e-4:
                continue

            cleaned.append({**s, 'lat': lat, 'lon': lon, 'alt': alt, 'timestamp': ts})

        cleaned.sort(key=lambda x: x['timestamp'])
        return cleaned

    def extract_metadata(self, video_path: str) -> bool:
        """
        Extracts metadata from the video file using ffmpeg.
        Checks for GPMF or CAMM streams, OR a sidecar .gpx file.
        """
        self.has_gps = False
        self.gps_samples = []
        self._times = []
        self.metadata = {'status': 'absent'}
        # Sidecars are matched case-insensitively, including SRT.
        source = Path(video_path)
        for sidecar in source.parent.iterdir():
            if sidecar.stem.casefold() == source.stem.casefold() and sidecar.suffix.lower() in ('.gpx', '.srt'):
                if sidecar.stat().st_size > 64 * 1024 * 1024:
                    raise ValueError('Sidecar exceeds 64 MiB')
                if sidecar.suffix.lower() == '.gpx':
                    self._extract_gpx_data(str(sidecar))
                else:
                    self.gps_samples = self._sanitize_gps_samples(parse_srt_data(sidecar.read_bytes(), self.altitude_mode))
                self.has_gps = bool(self.gps_samples)
                if self.has_gps:
                    self.metadata = {'status': 'valid', 'source': sidecar.name, 'time_source': 'sidecar_relative', 'alignment': 'track start assumed to equal video start'}
                    return True
        # 1. First Check for Sidecar GPX (Priority for Qoocam workflow)
        base_name = os.path.splitext(video_path)[0]
        gpx_path = f"{base_name}.gpx"
        
        # DEBUG: Print what we are looking for
        logger.info(f"Looking for GPX file at: {gpx_path}")
        
        if os.path.exists(gpx_path):
            logger.info(f"Found GPX sidecar file: {os.path.basename(gpx_path)}")
            success = self._extract_gpx_data(gpx_path)
            if success:
                self.has_gps = True
                return True

        try:
            # Check for streams using ffprobe
            cmd = [
                'ffprobe',
                '-v', 'quiet',
                '-print_format', 'json',
                '-show_streams',
                '-show_format',
                video_path
            ]
            data = json.loads(capture(cmd, self.cancelled))
            self.metadata = {'status': 'absent', 'format_tags': data.get('format', {}).get('tags', {})}
            self.metadata['video_start_pts'] = float(next((s.get('start_time', 0) for s in data.get('streams', []) if s.get('codec_type') == 'video'), 0))
            
            duration = 0.0
            try:
                duration = float(data.get('format', {}).get('duration', 0.0))
            except (ValueError, TypeError):
                duration = 0.0

            subtitle_stream_index = None

            for stream in data.get('streams', []):
                codec_tag_string = stream.get('codec_tag_string', '')
                codec_type = stream.get('codec_type', '')
                
                # Basic check for telemetry streams (GPMF, CAMM)
                if codec_type == 'data':
                    if 'gpmd' in codec_tag_string or 'camm' in codec_tag_string:
                        logger.info(f"Found telemetry stream: {codec_tag_string}")
                        
                        stream_index = stream.get('index')
                        if 'gpmd' in codec_tag_string:
                            self._extract_gpmf_data(video_path, stream_index)
                        elif 'camm' in codec_tag_string:
                            self._extract_camm_data(video_path, stream_index, duration)
                        
                        self.has_gps = bool(self.gps_samples)
                        self.metadata.update(status='valid' if self.has_gps else 'failed', source=codec_tag_string, time_source='packet_pts')
                        return self.has_gps
                
                # Check for subtitles (often used by DJI)
                if codec_type == 'subtitle' and subtitle_stream_index is None:
                    subtitle_stream_index = stream.get('index')
            
            # If no GPMF/CAMM found, try subtitles
            if subtitle_stream_index is not None:
                logger.info(f"No GPMF/CAMM found. Trying subtitle stream {subtitle_stream_index} for DJI telemetry.")
                self._extract_srt_data(video_path, subtitle_stream_index)
                if self.has_gps:
                    return True
                        
            logger.info("No known telemetry stream found.")
            return False
            
        except FileNotFoundError:
            self.metadata.update(status="failed", error="ffprobe unavailable")
            logger.error(f"ffprobe not found — telemetry extraction requires FFmpeg. {_FFMPEG_INSTALL_HINT}")
            return False
        except subprocess.CalledProcessError as e:
            logger.error(f"FFprobe error: {e}")
            return False
        except Exception as e:
            self.metadata.update(status="failed", error=str(e))
            logger.error(f"Error extracting metadata: {e}")
            return False

    def _metadata_packets(self, video_path, stream_index):
        raw = capture(['ffprobe', '-v', 'error', '-select_streams', str(stream_index),
                       '-show_packets', '-show_data', '-show_entries',
                       'packet=pts_time,duration_time,data', '-of', 'json', video_path], self.cancelled)
        for packet in json.loads(raw).get('packets', []):
            if self.cancelled():
                raise InterruptedError('Metadata extraction cancelled')
            if 'pts_time' not in packet:
                continue
            pieces = []
            for line in packet.get('data', '').splitlines():
                if ':' in line:
                    hexpart = line.split(':', 1)[1].strip().split('  ')[0]
                    if re.fullmatch(r'[0-9a-fA-F ]*', hexpart):
                        pieces.append(bytes.fromhex(hexpart))
            yield float(packet['pts_time']) - self.metadata.get('video_start_pts', 0), float(packet.get('duration_time', 0)), b''.join(pieces)

    def _extract_camm_data(self, video_path, stream_index, duration):
        samples = []
        for pts, _, data in self._metadata_packets(video_path, stream_index):
            samples.extend(parse_camm_data(data, timestamp=pts))
        self.gps_samples = self._sanitize_gps_samples(samples)
        self.has_gps = bool(self.gps_samples)

    def _extract_gpmf_data(self, video_path, stream_index):
        samples = []
        for pts, duration, data in self._metadata_packets(video_path, stream_index):
            packet_samples = GPMFParser().parse(data)
            if len(packet_samples) > 1 and duration <= 0:
                raise ValueError('GPMF packet has no duration; GPS sample timing cannot be established')
            for index, sample in enumerate(packet_samples):
                sample['timestamp'] = pts + index * duration / len(packet_samples)
                sample['time_source'] = 'packet_pts_interpolated'
            samples.extend(packet_samples)
        self.gps_samples = self._sanitize_gps_samples(samples)
        self.has_gps = bool(self.gps_samples)

    def _extract_srt_data(self, video_path: str, stream_index: int):
        """
        Extracts and parses SRT subtitle data from the video (DJI style).
        """
        try:
            cmd = [
                'ffmpeg',
                '-y',
                '-i', video_path,
                '-map', f'0:{stream_index}',
                '-f', 'srt',
                '-'
            ]
            raw_data = capture(cmd, self.cancelled)
            
            self.gps_samples = self._sanitize_gps_samples(parse_srt_data(raw_data, self.altitude_mode))

            if self.gps_samples:
                self.has_gps = True
                logger.info(f"Extracted {len(self.gps_samples)} GPS samples from subtitles (altitude: {self.altitude_mode}).")
            else:
                logger.warning("Subtitle stream found, but no GPS data extracted.")
                
        except FileNotFoundError:
            logger.error(f"ffmpeg not found — cannot extract the SRT subtitle stream. {_FFMPEG_INSTALL_HINT}")
        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg subtitle extraction failed: {e}")
        except Exception as e:
            logger.error(f"Error parsing SRT data: {e}")

    def _extract_gpx_data(self, gpx_path: str) -> bool:
        """
        Reads and parses a local GPX file.
        """
        try:
            with open(gpx_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            samples = self._sanitize_gps_samples(parse_gpx_data(content))
            if samples:
                self.gps_samples = samples
                logger.info(f"Loaded {len(samples)} samples from GPX sidecar.")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to load GPX sidecar: {e}")
            return False

    def get_gps_at_time(self, timestamp: float) -> Optional[Tuple[float, float, float]]:
        """
        Returns (lat, lon, alt) for a given video timestamp (in seconds).
        Interpolates between samples.
        """
        if not self.has_gps or not self.gps_samples:
            return None
            
        if self._indexed_samples is not self.gps_samples or len(self._times) != len(self.gps_samples):
            self._times = [s['timestamp'] for s in self.gps_samples]
            self._indexed_samples = self.gps_samples
        times = self._times
        if timestamp < times[0] or timestamp > times[-1]:
            return None
        
        # Find insertion point
        idx = bisect.bisect_left(times, timestamp)
        
        if idx < len(times) and times[idx] == timestamp:
            sample = self.gps_samples[idx]
            return sample['lat'], sample['lon'], sample['alt']
        if idx == 0:
            return (self.gps_samples[0]['lat'], self.gps_samples[0]['lon'], self.gps_samples[0]['alt'])
        if idx >= len(self.gps_samples):
            return (self.gps_samples[-1]['lat'], self.gps_samples[-1]['lon'], self.gps_samples[-1]['alt'])
            
        # Interpolate
        t1 = times[idx-1]
        t2 = times[idx]
        
        if t2 - t1 > self.max_gap_seconds:
            return None
        if t2 == t1:
            return (self.gps_samples[idx]['lat'], self.gps_samples[idx]['lon'], self.gps_samples[idx]['alt'])
            
        ratio = (timestamp - t1) / (t2 - t1)
        
        p1 = self.gps_samples[idx-1]
        p2 = self.gps_samples[idx]
        
        lat = p1['lat'] + (p2['lat'] - p1['lat']) * ratio
        delta_lon = (p2['lon'] - p1['lon'] + 180) % 360 - 180
        lon = (p1['lon'] + delta_lon * ratio + 180) % 360 - 180
        alt = p1['alt'] + (p2['alt'] - p1['alt']) * ratio
        
        return (lat, lon, alt)

    @staticmethod
    def _bearing_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Initial bearing from point 1 to point 2, degrees from true north."""
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        dlon = math.radians(lon2 - lon1)
        x = math.sin(dlon) * math.cos(phi2)
        y = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(dlon)
        return math.degrees(math.atan2(x, y)) % 360.0

    def get_heading_at_time(self, timestamp: float, window: float = 0.5,
                            min_distance_m: float = 0.5) -> Optional[float]:
        """Direction of travel (degrees from true north) at a video timestamp.

        Derived from the GPS track just before/after ``timestamp``. Returns
        ``None`` when there is no GPS or the rig is (nearly) stationary within
        the window — a bearing computed from GPS noise would be misleading.
        """
        if not self.has_gps or len(self.gps_samples) < 2:
            return None
        p1 = self.get_gps_at_time(max(0.0, timestamp - window))
        p2 = self.get_gps_at_time(timestamp + window)
        if p1 is None or p2 is None:
            return None
        lat1, lon1, _ = p1
        lat2, lon2, _ = p2
        # Local flat-earth distance approximation, fine at this scale.
        mid = math.radians((lat1 + lat2) / 2.0)
        dist_m = math.hypot((lat2 - lat1) * 111320.0,
                            (lon2 - lon1) * 111320.0 * math.cos(mid))
        if dist_m < min_distance_m:
            return None
        return self._bearing_deg(lat1, lon1, lat2, lon2)

    @staticmethod
    def build_gps_exif_bytes(lat: float, lon: float, alt: float = 0.0) -> bytes:
        """Build EXIF bytes carrying a GPS fix. Delegates to the EXIF writer."""
        return exif_writer.build_exif_bytes(gps=(lat, lon, alt))

    def save_image_with_gps(self, image_path: str, image: "np.ndarray", params, lat: float,
                            lon: float, alt: float = 0.0) -> bool:
        """Write ``image`` once with GPS EXIF embedded (no write-reload-rewrite).

        Thin wrapper over :mod:`extractor360.core.exif_writer`, kept for
        callers that only care about the geotag; the processor builds richer
        EXIF (intrinsics, capture time, view direction) itself.
        """
        exif_bytes = self.build_gps_exif_bytes(lat, lon, alt)
        return exif_writer.save_image_with_exif(image_path, image, params, exif_bytes)

    def embed_exif(self, image_path: str, lat: float, lon: float, alt: float = 0.0) -> bool:
        """
        Embeds GPS coordinates into an existing image file using piexif.

        Kept for callers that already have a file on disk; the processor now uses
        the in-memory :meth:`save_image_with_gps` to avoid the extra round-trip.
        """
        try:
            exif_bytes = self.build_gps_exif_bytes(lat, lon, alt)
            ext = os.path.splitext(image_path)[1].lower()
            if ext in ['.jpg', '.jpeg']:
                piexif.insert(exif_bytes, image_path)
            else:
                # For PNG/TIFF, use Pillow to save with EXIF
                # This might be slower as it re-saves the file, but it's reliable.
                with Image.open(image_path) as img:
                    img.save(image_path, exif=exif_bytes)

            return True

        except Exception as e:
            logger.error(f"Error embedding EXIF in {image_path}: {type(e).__name__} - {e}")
            return False
