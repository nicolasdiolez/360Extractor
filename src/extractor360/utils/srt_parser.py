import re
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)

def parse_srt_data(raw_data: bytes, altitude_mode: str = 'absolute') -> List[Dict[str, float]]:
    """
    Parses SRT subtitle data to extract GPS telemetry.
    
    Expected format (DJI style):
    1
    00:00:00,000 --> 00:00:00,032
    [latitude: 12.34567] [longitude: 123.45678] [rel_alt: 1.300 abs_alt: 50.5] ...

    DJI drones (incl. Avata 360) do NOT emit a plain `[altitude: X]` field. They
    pack altitude as `[rel_alt: <relative-to-takeoff> abs_alt: <above-sea-level>]`.

    Args:
        raw_data: Raw bytes of the SRT file/stream
        altitude_mode: Which altitude to store in 'alt' when a DJI clip exposes
            both. 'absolute' (default) uses abs_alt (above sea level, the right
            choice for RealityScan/COLMAP geo-referencing); 'relative' uses
            rel_alt (height above takeoff). A legacy `[altitude: X]` field and a
            `GPS(lat,lon,alt)` fallback are honored for non-DJI devices regardless
            of mode.

    Returns:
        List of dictionaries containing:
        - timestamp: float (seconds)
        - lat: float
        - lon: float
        - alt: float (per altitude_mode, falling back to whatever is available)
    """
    prefer_relative = str(altitude_mode).lower() == 'relative'
    try:
        text_data = raw_data.decode('utf-8', errors='ignore')
    except Exception as e:
        logger.error(f"Error decoding SRT data: {e}")
        return []

    samples = []
    
    # Split by double newlines to get blocks
    # Normalize line endings first
    text_data = text_data.replace('\r\n', '\n')
    blocks = text_data.strip().split('\n\n')
    
    # Regex patterns
    # Matches: [latitude: 12.345] or [latitude : 12.345]
    lat_pattern = re.compile(r'\[\s*latitude\s*:\s*([-\d.]+)\s*\]', re.IGNORECASE)
    lon_pattern = re.compile(r'\[\s*longitude\s*:\s*([-\d.]+)\s*\]', re.IGNORECASE)
    # DJI: [rel_alt: 1.300 abs_alt: 425.971]  (absolute = above sea level)
    abs_alt_pattern = re.compile(r'\babs_alt\s*:\s*([-\d.]+)', re.IGNORECASE)
    rel_alt_pattern = re.compile(r'\brel_alt\s*:\s*([-\d.]+)', re.IGNORECASE)
    # Legacy / generic: [altitude: 50.5]
    alt_pattern = re.compile(r'\[\s*altitude\s*:\s*([-\d.]+)\s*\]', re.IGNORECASE)

    # Alternative: GPS(lat, lon, alt)
    gps_pattern = re.compile(r'GPS\s*\(\s*([-\d.]+)\s*,\s*([-\d.]+)\s*,\s*([-\d.]+)\s*\)', re.IGNORECASE)

    for block in blocks:
        lines = block.split('\n')
        # We need at least index, time, and text
        if len(lines) < 3:
            continue
            
        time_line = lines[1]
        
        # Combine all subsequent lines as text content
        content = " ".join(lines[2:])
        
        # Parse Timestamp
        # Format: HH:MM:SS,mmm --> HH:MM:SS,mmm
        try:
            if '-->' not in time_line:
                continue
                
            start_str = time_line.split('-->')[0].strip()
            # Parse HH:MM:SS,mmm
            parts = start_str.split(':')
            if len(parts) != 3:
                continue
                
            h = int(parts[0])
            m = int(parts[1])
            s_parts = parts[2].split(',')
            
            if len(s_parts) != 2:
                continue
                
            s = int(s_parts[0])
            ms = int(s_parts[1])
            
            timestamp = h * 3600 + m * 60 + s + ms / 1000.0
            
        except (ValueError, IndexError):
            continue

        # Extract Coordinates
        lat = None
        lon = None
        alt = 0.0
        
        lat_match = lat_pattern.search(content)
        lon_match = lon_pattern.search(content)

        if lat_match and lon_match:
            try:
                lat = float(lat_match.group(1))
                lon = float(lon_match.group(1))
                # Pick altitude according to altitude_mode. When the preferred
                # source is absent we fall back to the other DJI field, then to
                # the legacy generic [altitude:] field.
                abs_match = abs_alt_pattern.search(content)
                rel_match = rel_alt_pattern.search(content)
                alt_match = alt_pattern.search(content)
                abs_val = float(abs_match.group(1)) if abs_match else None
                rel_val = float(rel_match.group(1)) if rel_match else None
                legacy_val = float(alt_match.group(1)) if alt_match else None

                if prefer_relative:
                    candidates = (rel_val, legacy_val, abs_val)
                else:
                    candidates = (abs_val, legacy_val, rel_val)
                alt = next((v for v in candidates if v is not None), 0.0)
            except ValueError:
                continue
        else:
            # Try fallback GPS pattern
            gps_match = gps_pattern.search(content)
            if gps_match:
                try:
                    lat = float(gps_match.group(1))
                    lon = float(gps_match.group(2))
                    alt = float(gps_match.group(3))
                except ValueError:
                    continue

        if lat is not None and lon is not None:
            samples.append({
                'timestamp': timestamp,
                'lat': lat,
                'lon': lon,
                'alt': alt
            })

    return samples
