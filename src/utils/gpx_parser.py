import defusedxml.ElementTree as ET
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

def parse_gpx_data(gpx_content: str) -> list[dict]:
    """
    Parses GPX XML content and returns a list of dictionaries with:
    {
        'timestamp': float (seconds from start of track),
        'lat': float,
        'lon': float,
        'alt': float
    }
    """
    try:
        root = ET.fromstring(gpx_content)
        
        # Define namespaces often found in GPX
        namespaces = {
            'gpx': 'http://www.topografix.com/GPX/1/1',
            'gpx10': 'http://www.topografix.com/GPX/1/0'
        }
        
        # Try to find trkpts with or without namespace
        points = []
        
        # Helper to find elements
        def find_all_points(element):
            # Try namespaced first (GPX 1.1)
            pts = element.findall('.//gpx:trkpt', namespaces)
            if not pts:
                # Try GPX 1.0 or no namespace
                pts = element.findall('.//trkpt')
            return pts

        trkpts = find_all_points(root)
        
        if not trkpts:
            logger.warning("No track points found in GPX data.")
            return []

        parsed_points = []
        start_time = None

        for pt in trkpts:
            try:
                lat = float(pt.get('lat'))
                lon = float(pt.get('lon'))
                
                # Elevation
                ele_elem = pt.find('gpx:ele', namespaces) if pt.find('gpx:ele', namespaces) is not None else pt.find('ele')
                alt = float(ele_elem.text) if ele_elem is not None else 0.0
                
                # Time
                time_elem = pt.find('gpx:time', namespaces) if pt.find('gpx:time', namespaces) is not None else pt.find('time')
                if time_elem is not None and time_elem.text:
                    # Parse ISO format (e.g., 2023-10-27T10:00:00Z)
                    # Python 3.7+ fromisoformat handles simple Z, but let's be safe
                    t_str = time_elem.text.replace('Z', '+00:00')
                    dt = datetime.fromisoformat(t_str)
                    epoch = dt.timestamp()
                    
                    if start_time is None:
                        start_time = epoch
                    
                    rel_time = epoch - start_time
                    
                    parsed_points.append({
                        'timestamp': rel_time,
                        'lat': lat,
                        'lon': lon,
                        'alt': alt
                    })
            except (ValueError, TypeError) as e:
                continue

        logger.info(f"Successfully parsed {len(parsed_points)} GPX points.")
        return parsed_points

    except ET.ParseError as e:
        logger.error(f"XML Parse Error in GPX: {e}")
        return []
    except Exception as e:
        logger.error(f"Unexpected error parsing GPX: {e}")
        return []
