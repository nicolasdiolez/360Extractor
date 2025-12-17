import struct
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

def parse_camm_data(raw_data: bytes, duration: float = 0.0) -> List[Dict[str, float]]:
    """
    Parses raw CAMM data stream (Insta360 format).
    
    Args:
        raw_data: Binary data from the CAMM stream.
        duration: Total duration of the video in seconds (used for timestamp estimation).
        
    Returns:
        List of dictionaries containing 'timestamp', 'lat', 'lon', 'alt'.
    """
    offset = 0
    length = len(raw_data)
    samples = []
    
    # Iterate through the binary stream
    # Each packet: reserved (2 bytes), type (2 bytes), data (variable)
    
    while offset < length:
        # Check if we have enough bytes for header
        if offset + 4 > length:
            break
            
        try:
            # Little-endian: reserved (H), type (H)
            reserved, packet_type = struct.unpack_from('<HH', raw_data, offset)
        except struct.error:
            break
            
        current_header_offset = offset
        offset += 4
        
        payload_size = 0
        is_gps = False
        
        # Determine payload size based on type
        # Type 6: GPS (lat, lon, alt) -> double, double, float -> 8+8+4 = 20 bytes
        if packet_type == 6:
            payload_size = 20
            is_gps = True
        elif packet_type == 2: # Gyro: 3 floats -> 12 bytes
            payload_size = 12
        elif packet_type == 3: # Accel: 3 floats -> 12 bytes
            payload_size = 12
        elif packet_type == 1: # Exposure/Time: 8 bytes? (Educated guess for Insta360)
             # If we don't handle this, we might desync.
             # However, without exact spec, assume 8 bytes or risk desync.
             payload_size = 8
        elif packet_type == 0: # Reserved/Empty
             payload_size = 0
        else:
             # Unknown type. 
             payload_size = -1
             
        if payload_size >= 0:
            if offset + payload_size > length:
                break
                
            if is_gps:
                try:
                    lat, lon, alt = struct.unpack_from('<ddf', raw_data, offset)
                    # Basic validation (ignore 0,0 island unless valid)
                    if -90 <= lat <= 90 and -180 <= lon <= 180 and (abs(lat) > 0.0001 or abs(lon) > 0.0001):
                         samples.append({
                            'lat': lat,
                            'lon': lon,
                            'alt': float(alt)
                        })
                except struct.error:
                    pass
            
            offset += payload_size
        else:
            # Unknown type or size. Scan for next likely header.
            # Look for 0x0000 (reserved) aligned to ... actually just scan bytes.
            # logger.debug(f"Unknown CAMM type {packet_type} at {current_header_offset}. Scanning for next packet.")
            
            scan_ptr = current_header_offset + 1
            found = False
            while scan_ptr < length - 4:
                # Check for 0x0000
                try:
                    possible_reserved = struct.unpack_from('<H', raw_data, scan_ptr)[0]
                    if possible_reserved == 0:
                        # Check next 2 bytes for plausible type (1, 2, 3, 6)
                        possible_type = struct.unpack_from('<H', raw_data, scan_ptr + 2)[0]
                        if possible_type in [1, 2, 3, 6]:
                            offset = scan_ptr
                            found = True
                            break
                except struct.error:
                    break
                scan_ptr += 1
            
            if not found:
                break # Can't recover
                
    # Assign timestamps
    # If we have duration, we distribute samples evenly.
    # Insta360 GPS is typically 5Hz or 10Hz.
    if samples:
        num_samples = len(samples)
        if duration > 0:
            for i, sample in enumerate(samples):
                sample['timestamp'] = (i / num_samples) * duration
        else:
            # If no duration, we can't do much. 
            # Default to 5Hz (0.2s) just to have something?
            # Or log warning.
            logger.warning("CAMM data found but no duration provided. Assuming 5Hz.")
            for i, sample in enumerate(samples):
                sample['timestamp'] = i * 0.2

    logger.info(f"Parsed {len(samples)} CAMM GPS samples.")
    return samples
