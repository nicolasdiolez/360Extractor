import struct
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

class GPMFParser:
    """
    Parses GoPro Metadata Format (GPMF) binary data to extract GPS information.
    """
    
    def __init__(self):
        self.scales: Dict[str, List[float]] = {}
        self.gps_data: List[Dict[str, float]] = []
        self.current_timestamp = 0.0
        # Assuming ~18Hz for GPS as default, but this is rough estimation
        # Real implementation would look for TSMP (Total Samples) or TICK to map time accurately
        self.sample_duration = 1.0 / 18.0 
        
    def parse(self, data: bytes) -> List[Dict[str, float]]:
        """
        Parses raw GPMF binary data.
        
        Args:
            data: Raw binary bytes extracted from the GPMF stream.
            
        Returns:
            List of dictionaries containing {timestamp, lat, lon, alt, ...}
        """
        self.gps_data = []
        self.scales = {} # Reset scales? Or keep them? GPMF usually repeats SCAL in each stream chunk.
        self.current_timestamp = 0.0
        
        if not data:
            return []
            
        self._parse_recursive(data)
        
        # Sort by timestamp just in case
        self.gps_data.sort(key=lambda x: x['timestamp'])
        
        return self.gps_data

    def _parse_recursive(self, data: bytes):
        offset = 0
        length = len(data)
        
        while offset + 8 <= length:
            # 1. Read Header
            # Key: 4 bytes
            key_bytes = data[offset:offset+4]
            key = key_bytes.decode('utf-8', errors='replace')
            
            # Type: 1 byte
            type_char = chr(data[offset+4])
            
            # Size: 1 byte (Structure Size)
            structure_size = data[offset+5]
            
            # Count: 2 bytes (Repeat Count) - Big Endian
            repeat_count = struct.unpack('>H', data[offset+6:offset+8])[0]
            
            offset += 8
            
            # Calculate Data Size
            total_data_size = structure_size * repeat_count
            
            # Calculate Padded Size (4-byte alignment)
            padded_size = (total_data_size + 3) & ~3
            
            if offset + total_data_size > length:
                logger.warning(f"Incomplete GPMF tag: {key}. Expected {total_data_size} bytes, got {length - offset}")
                break
                
            payload = data[offset:offset+total_data_size]
            
            # 2. Process Tag
            if key in ['DEVC', 'STRM']:
                # Container: Recurse
                # Note: DEVC/STRM payload contains other tags.
                # We assume the container payload is also a sequence of KLV tags.
                self._parse_recursive(payload)
                
            elif key == 'SCAL':
                self._handle_scal(payload, type_char, structure_size, repeat_count)
                
            elif key == 'GPS5':
                self._handle_gps5(payload, type_char, structure_size, repeat_count)
            
            # 3. Advance Offset (skip padding)
            # The next tag starts at offset + padded_size (relative to data start before header read)
            # Wait, my logic: offset was incremented by 8. 
            # Now I need to increment by padded_size.
            # But the padding is calculated on the data size.
            # Example: data size 5. padded size 8.
            # We read 5 bytes. We need to skip 3 more bytes.
            # So increment by padded_size.
            
            # However, if I recurse, the recursion handles the internal structure.
            # If I am at top level, I jump over the container's payload.
            # Yes, standard GPMF: Containers have size/count too.
            # If DEVC has size S and count C, total size is S*C.
            # We recurse into that S*C bytes.
            
            offset += padded_size

    def _unpack_values(self, data: bytes, type_char: str, structure_size: int, repeat_count: int) -> List[Any]:
        item_size = structure_size
        
        # Mapping for struct format
        # Big-endian is standard for GPMF
        fmt_map = {
            'b': 'b', # int8
            'B': 'B', # uint8
            's': '>h', # int16
            'S': '>H', # uint16
            'l': '>i', # int32
            'L': '>I', # uint32
            'f': '>f', # float
            'd': '>d', # double
            'J': '>Q', # uint64
        }
        
        fmt_char = fmt_map.get(type_char)
        if not fmt_char:
            return []
            
        # We have 'repeat_count' items.
        # But wait, structure_size might contain multiple values if it's a complex type?
        # Usually structure_size is the size of ONE element (e.g. 4 for int32).
        # repeat_count is how many elements.
        # However, for GPS5, structure_size is usually 20 (5 * 4 bytes).
        # And repeat_count is the number of samples.
        # So we treat each 'sample' as a list of values?
        # Let's handle generic unpacking:
        
        # If structure_size matches the type size, it's a simple array.
        # If structure_size is a multiple of type size, it's an array of arrays (e.g. vec3).
        
        type_size = struct.calcsize(fmt_char)
        elements_per_item = item_size // type_size
        
        if elements_per_item * type_size != item_size:
             # Structure size not aligned with type size?
             # Just try to unpack as stream of types
             pass
             
        total_elements = repeat_count * elements_per_item
        
        # Safety check
        if len(data) < total_elements * type_size:
            return []
            
        try:
            # Unpack all at once
            full_fmt = '>' + (fmt_map[type_char][1] * total_elements) # e.g. '>iiiii...'
            unpacked = struct.unpack(full_fmt, data[:total_elements * type_size])
            
            # Group by structure_size
            if elements_per_item > 1:
                # List of lists
                result = []
                for i in range(repeat_count):
                    chunk = unpacked[i*elements_per_item : (i+1)*elements_per_item]
                    result.append(list(chunk))
                return result
            else:
                return list(unpacked)
                
        except struct.error:
            return []

    def _handle_scal(self, payload: bytes, type_char: str, structure_size: int, repeat_count: int):
        # SCAL usually provides scaling factors for the associated stream.
        # It's usually a set of integers or floats.
        values = self._unpack_values(payload, type_char, structure_size, repeat_count)
        
        # For GPS5, SCAL usually has same dim as GPS5 (5 values).
        # If multiple samples of SCAL? Usually SCAL is count 1 (one set of scales).
        # But if it's count > 1, it might be changing scales? Uncommon.
        
        # Flatten if it came out as [[1,2,3,4,5]] due to structure logic
        if values and isinstance(values[0], list):
            # Take the last one? Or first? usually it's just one set.
            self.scales['GPS5'] = values[-1] # Assume latest applies
        else:
            self.scales['GPS5'] = values

    def _handle_gps5(self, payload: bytes, type_char: str, structure_size: int, repeat_count: int):
        values = self._unpack_values(payload, type_char, structure_size, repeat_count)
        
        # GPS5 usually: Lat, Lon, Alt, 2D Speed, 3D Speed.
        # Values are usually int32 ('l').
        # Need SCAL to convert.
        
        scales = self.scales.get('GPS5')
        if not scales:
            # Default scaling if missing? Or skip?
            # GoPro Lat/Lon are usually scaled by 10,000,000.
            scales = [10000000, 10000000, 1000, 1000, 1000] # Educated guess fallback
        
        # Make sure scales match dimensions
        # values is a list of lists (samples)
        
        for sample in values:
            if not isinstance(sample, list):
                # Should be list of 5 ints
                continue
                
            if len(sample) < 5:
                continue
                
            # Apply scaling
            # lat = sample[0] / scales[0]
            # lon = sample[1] / scales[1]
            # alt = sample[2] / scales[2]
            
            try:
                lat = float(sample[0]) / float(scales[0]) if len(scales) > 0 else sample[0]
                lon = float(sample[1]) / float(scales[1]) if len(scales) > 1 else sample[1]
                alt = float(sample[2]) / float(scales[2]) if len(scales) > 2 else sample[2]
                
                # Append data
                self.gps_data.append({
                    'timestamp': self.current_timestamp,
                    'lat': lat,
                    'lon': lon,
                    'alt': alt
                })
                
                # Increment timestamp
                self.current_timestamp += self.sample_duration
                
            except (ValueError, IndexError, ZeroDivisionError):
                continue

