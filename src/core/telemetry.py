import subprocess
import json
import logging
import bisect
from typing import Optional, Tuple, Any, List, Dict
import piexif
from PIL import Image
from utils.gpmf_parser import GPMFParser
from utils.srt_parser import parse_srt_data
from utils.camm_parser import parse_camm_data
from utils.gpx_parser import parse_gpx_data
import os

logger = logging.getLogger(__name__)

class TelemetryHandler:
    def __init__(self):
        self.metadata = {}
        self.has_gps = False
        self.gps_samples: List[Dict[str, float]] = []

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
            
            self.gps_samples = parse_camm_data(raw_data, duration)
            if self.gps_samples:
                self.has_gps = True
                logger.info(f"Extracted {len(self.gps_samples)} CAMM GPS samples.")
            else:
                logger.warning("CAMM stream found but no GPS samples extracted.")
                
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
            self.gps_samples = parser.parse(raw_data)
            logger.info(f"Extracted {len(self.gps_samples)} GPS samples.")
            
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
            
            self.gps_samples = parse_srt_data(raw_data)
            
            if self.gps_samples:
                self.has_gps = True
                logger.info(f"Extracted {len(self.gps_samples)} GPS samples from subtitles.")
            else:
                logger.warning("Subtitle stream found, but no GPS data extracted.")
                
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
            
            samples = parse_gpx_data(content)
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

    def embed_exif(self, image_path: str, lat: float, lon: float, alt: float = 0.0) -> bool:
        """
        Embeds GPS coordinates into the image EXIF data using piexif.
        """
        try:
            # Load existing EXIF or create new
            try:
                exif_dict = piexif.load(image_path)
            except Exception:
                exif_dict = {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}, "thumbnail": None}

            # Helper to convert to rational
            def to_rational(number):
                return (int(number * 1000000), 1000000)

            def to_deg_min_sec(value):
                abs_value = abs(value)
                deg = int(abs_value)
                min_val = (abs_value - deg) * 60
                sec = (min_val - int(min_val)) * 60
                return (to_rational(deg), to_rational(int(min_val)), to_rational(sec))

            lat_deg = to_deg_min_sec(lat)
            lon_deg = to_deg_min_sec(lon)
            
            gps_ifd = {
                piexif.GPSIFD.GPSLatitudeRef: b'N' if lat >= 0 else b'S',
                piexif.GPSIFD.GPSLatitude: lat_deg,
                piexif.GPSIFD.GPSLongitudeRef: b'E' if lon >= 0 else b'W',
                piexif.GPSIFD.GPSLongitude: lon_deg,
                piexif.GPSIFD.GPSAltitudeRef: 0, # Above sea level
                piexif.GPSIFD.GPSAltitude: to_rational(alt)
            }
            
            exif_dict['GPS'] = gps_ifd
            exif_bytes = piexif.dump(exif_dict)
            
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
