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

logger = logging.getLogger(__name__)

_FFMPEG_INSTALL_HINT = (
    "Install FFmpeg first (macOS: 'brew install ffmpeg', Windows: 'winget install ffmpeg', "
    "Linux: 'sudo apt install ffmpeg') and make sure it is on your PATH."
)

class TelemetryHandler:
    def __init__(self, altitude_mode: str = 'absolute'):
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

            if not all(math.isfinite(v) for v in (lat, lon, alt, ts)):
                continue
            if not (-90.0 <= lat <= 90.0) or not (-180.0 <= lon <= 180.0):
                continue
            # (0,0) is the "no GPS fix yet" placeholder on several devices;
            # keeping it would geotag images at Null Island.
            if abs(lat) < 1e-4 and abs(lon) < 1e-4:
                continue

            cleaned.append({'lat': lat, 'lon': lon, 'alt': alt, 'timestamp': ts})

        cleaned.sort(key=lambda x: x['timestamp'])
        return cleaned

    def extract_metadata(self, video_path: str) -> bool:
        """
        Extracts metadata from the video file using ffmpeg.
        Checks for GPMF or CAMM streams, OR a sidecar .gpx file.
        """
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
            result = subprocess.run(cmd, capture_output=True, text=True, check=True, encoding='utf-8', errors='replace')
            data = json.loads(result.stdout)
            
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
                        self.has_gps = True
                        logger.info(f"Found telemetry stream: {codec_tag_string}")
                        
                        stream_index = stream.get('index')
                        if 'gpmd' in codec_tag_string:
                            self._extract_gpmf_data(video_path, stream_index)
                        elif 'camm' in codec_tag_string:
                            self._extract_camm_data(video_path, stream_index, duration)
                        
                        return True
                
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
            logger.error(f"ffprobe not found — telemetry extraction requires FFmpeg. {_FFMPEG_INSTALL_HINT}")
            return False
        except subprocess.CalledProcessError as e:
            logger.error(f"FFprobe error: {e}")
            return False
        except Exception as e:
            logger.error(f"Error extracting metadata: {e}")
            return False

    def _extract_camm_data(self, video_path: str, stream_index: int, duration: float):
        """
        Extracts and parses CAMM data from the video.
        """
        try:
            cmd = [
                'ffmpeg',
                '-y',
                '-i', video_path,
                '-map', f'0:{stream_index}',
                '-f', 'data',
                '-'
            ]
            result = subprocess.run(cmd, capture_output=True, check=True)
            raw_data = result.stdout
            
            self.gps_samples = self._sanitize_gps_samples(parse_camm_data(raw_data, duration))
            if self.gps_samples:
                self.has_gps = True
                logger.info(f"Extracted {len(self.gps_samples)} CAMM GPS samples.")
            else:
                logger.warning("CAMM stream found but no GPS samples extracted.")
                
        except FileNotFoundError:
            logger.error(f"ffmpeg not found — cannot extract the CAMM stream. {_FFMPEG_INSTALL_HINT}")
        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg extraction failed for CAMM: {e}")
        except Exception as e:
            logger.error(f"Error parsing CAMM data: {e}")

    def _extract_gpmf_data(self, video_path: str, stream_index: int):
        """
        Extracts and parses GPMF data from the video.
        """
        try:
            cmd = [
                'ffmpeg',
                '-y',
                '-i', video_path,
                '-map', f'0:{stream_index}',
                '-f', 'data',
                '-'
            ]
            # Use a large buffer size for subprocess to prevent hanging on large outputs
            result = subprocess.run(cmd, capture_output=True, check=True)
            raw_data = result.stdout
            
            parser = GPMFParser()
            self.gps_samples = self._sanitize_gps_samples(parser.parse(raw_data))
            logger.info(f"Extracted {len(self.gps_samples)} GPS samples.")
            
        except FileNotFoundError:
            logger.error(f"ffmpeg not found — cannot extract the GPMF stream. {_FFMPEG_INSTALL_HINT}")
        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg extraction failed: {e}")
        except Exception as e:
            logger.error(f"Error parsing GPMF data: {e}")

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
            result = subprocess.run(cmd, capture_output=True, check=True)
            raw_data = result.stdout
            
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
            
        times = [s['timestamp'] for s in self.gps_samples]
        
        # Find insertion point
        idx = bisect.bisect_left(times, timestamp)
        
        if idx == 0:
            return (self.gps_samples[0]['lat'], self.gps_samples[0]['lon'], self.gps_samples[0]['alt'])
        if idx >= len(self.gps_samples):
            return (self.gps_samples[-1]['lat'], self.gps_samples[-1]['lon'], self.gps_samples[-1]['alt'])
            
        # Interpolate
        t1 = times[idx-1]
        t2 = times[idx]
        
        if t2 == t1:
            return (self.gps_samples[idx]['lat'], self.gps_samples[idx]['lon'], self.gps_samples[idx]['alt'])
            
        ratio = (timestamp - t1) / (t2 - t1)
        
        p1 = self.gps_samples[idx-1]
        p2 = self.gps_samples[idx]
        
        lat = p1['lat'] + (p2['lat'] - p1['lat']) * ratio
        lon = p1['lon'] + (p2['lon'] - p1['lon']) * ratio
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
