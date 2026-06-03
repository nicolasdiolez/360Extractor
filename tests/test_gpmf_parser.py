import unittest
import struct
import os
import sys

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from utils.gpmf_parser import GPMFParser

class TestGPMFParser(unittest.TestCase):
    def pack_klv(self, key: str, type_char: str, structure_size: int, count: int, data_bytes: bytes) -> bytes:
        header = struct.pack('>4scBH', key.encode('utf-8'), type_char.encode('utf-8'), structure_size, count)
        
        # Calculate padding
        total_size = len(data_bytes)
        padding = (4 - (total_size % 4)) % 4
        
        return header + data_bytes + (b'\x00' * padding)

    def test_parser_basic(self):
        # Create a mock GPMF stream
        # DEVC -> STRM -> SCAL, GPS5
        
        # 1. SCAL: 5 ints (100, 100, 10, 10, 10)
        # Type 'l' (int32, 4 bytes)
        # Structure size: 4
        # Count: 5
        scal_values = [100, 100, 10, 10, 10]
        scal_data = struct.pack('>5i', *scal_values)
        scal_block = self.pack_klv('SCAL', 'l', 4, 5, scal_data)
        
        # 2. GPS5: 1 sample (4000, 2000, 500, 10, 10)
        # Type 'l' (int32, 4 bytes)
        # Structure size: 20 (5 * 4 bytes)
        # Count: 1
        # Lat: 4000/100 = 40.0
        # Lon: 2000/100 = 20.0
        # Alt: 500/10 = 50.0
        gps_values = [4000, 2000, 500, 10, 10]
        gps_data = struct.pack('>5i', *gps_values)
        gps_block = self.pack_klv('GPS5', 'l', 20, 1, gps_data)
        
        # 3. STRM Container
        strm_payload = scal_block + gps_block
        # Type '\0' (nested), Structure size 1? No, usually generic. 
        # For containers, GPMF usually uses Type '\0' or similar? 
        # Wait, the parser logic just recurses based on Key. 
        # The Type/Size/Count for container is somewhat arbitrary but Size*Count must cover the payload.
        # Let's say Type 'm', Size 1, Count len(payload)
        strm_block = self.pack_klv('STRM', '\0', 1, len(strm_payload), strm_payload)
        
        # 4. DEVC Container
        devc_payload = strm_block
        devc_block = self.pack_klv('DEVC', '\0', 1, len(devc_payload), devc_payload)
        
        # Parse
        parser = GPMFParser()
        result = parser.parse(devc_block)
        
        self.assertEqual(len(result), 1)
        sample = result[0]
        self.assertAlmostEqual(sample['lat'], 40.0)
        self.assertAlmostEqual(sample['lon'], 20.0)
        self.assertAlmostEqual(sample['alt'], 50.0)
        self.assertEqual(sample['timestamp'], 0.0)

    def test_parser_multiple_samples(self):
        # 1. SCAL: 5 ints (10, 10, 1, 1, 1)
        scal_values = [10, 10, 1, 1, 1]
        scal_data = struct.pack('>5i', *scal_values)
        scal_block = self.pack_klv('SCAL', 'l', 4, 5, scal_data)
        
        # 2. GPS5: 2 samples
        # Sample 1: 100, 200, 30, ...
        # Sample 2: 110, 210, 31, ...
        gps_values_1 = [100, 200, 30, 0, 0]
        gps_values_2 = [110, 210, 31, 0, 0]
        gps_data = struct.pack('>5i', *gps_values_1) + struct.pack('>5i', *gps_values_2)
        gps_block = self.pack_klv('GPS5', 'l', 20, 2, gps_data)
        
        # Container
        strm_payload = scal_block + gps_block
        strm_block = self.pack_klv('STRM', '\0', 1, len(strm_payload), strm_payload)
        devc_block = self.pack_klv('DEVC', '\0', 1, len(strm_block), strm_block)
        
        parser = GPMFParser()
        result = parser.parse(devc_block)
        
        self.assertEqual(len(result), 2)
        self.assertAlmostEqual(result[0]['lat'], 10.0)
        self.assertAlmostEqual(result[1]['lat'], 11.0)
        
        # Check timestamps
        # Assuming ~18Hz default (0.055s)
        self.assertEqual(result[0]['timestamp'], 0.0)
        self.assertAlmostEqual(result[1]['timestamp'], 1.0/18.0)

if __name__ == '__main__':
    unittest.main()
