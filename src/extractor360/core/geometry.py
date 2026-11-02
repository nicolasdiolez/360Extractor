import numpy as np

class GeometryProcessor:
    """
    Handles mathematical operations for reprojecting Equirectangular images
    to Rectilinear (Pinhole) views.
    """

    # Lanczos4 reads up to four neighbouring rows. Padding the latitude axis
    # independently keeps those taps at the same pole while longitude wraps.
    _LATITUDE_PADDING = 4

    @staticmethod
    def prepare_equirectangular_maps(map_x, map_y):
        """Compile maps for :meth:`remap_equirectangular` (linear or Lanczos4).

        These maps address a vertically edge-extended source. Keep the pair
        together with the matching remapper; ordinary cv2.remap would read the
        wrong latitude from the original source.
        """
        import cv2

        return cv2.convertMaps(
            map_x, map_y + GeometryProcessor._LATITUDE_PADDING, cv2.CV_16SC2
        )

    @staticmethod
    def prepare_equirectangular_source(frame):
        """Extend latitude once per source frame, reusable across all views."""
        import cv2

        padding = GeometryProcessor._LATITUDE_PADDING
        return cv2.copyMakeBorder(frame, padding, padding, 0, 0, cv2.BORDER_REPLICATE)

    @staticmethod
    def remap_equirectangular(frame, map1, map2, interpolation, *, source_is_prepared=False):
        """Sample periodic longitude and edge-extended latitude separately.

        Merely clamping map_y is insufficient: Lanczos still samples outside
        the first/last row. Replicate four rows on either pole so BORDER_WRAP
        applies only to the longitude taps for every generated latitude.
        """
        import cv2

        extended = frame if source_is_prepared else GeometryProcessor.prepare_equirectangular_source(frame)
        return cv2.remap(extended, map1, map2, interpolation, borderMode=cv2.BORDER_WRAP)

    @staticmethod
    def generate_views(n, pitch_offset=0, layout_mode='ring'):
        """
        Generate a list of (name, yaw, pitch, roll) tuples for n cameras.
        
        Args:
            n (int): Number of cameras (2-36). Ignored if layout_mode is 'cube'.
            pitch_offset (float): Offset in degrees for vertical inclination (e.g. -20 for High/Perch)
            layout_mode (str): 'ring', 'cube', or 'fibonacci'.
            
        Returns:
            list: List of (name, yaw, pitch, roll) tuples.
        """
        views = []
        
        if layout_mode == 'cube':
            # Cube layout (exactly 6 views)
            # Front, Right, Back, Left, Up, Down
            # Apply pitch_offset only to horizontal views
            
            # Horizontal ring
            views.append(("Front", 0.0, pitch_offset, 0))
            views.append(("Right", 90.0, pitch_offset, 0))
            views.append(("Back", 180.0, pitch_offset, 0))
            views.append(("Left", 270.0, pitch_offset, 0))
            
            # Vertical poles (fixed at +/- 90)
            views.append(("Up", 0.0, 90.0, 0))
            views.append(("Down", 0.0, -90.0, 0))
            
        elif layout_mode == 'fibonacci':
            # Fibonacci Sphere layout
            # Use the Golden Section Spiral algorithm to distribute points evenly
            dst = 2.0 / n
            inc = np.pi * (3.0 - np.sqrt(5.0))
            
            for i in range(n):
                # y goes from 1 to -1
                y = 1 - (i * dst) - (dst / 2)
                r = np.sqrt(1 - y*y)
                phi = i * inc
                
                x = np.cos(phi) * r
                z = np.sin(phi) * r
                
                # Convert (x, y, z) to (yaw, pitch)
                # Pitch is elevation from XZ plane (asin y)
                pitch_deg = np.degrees(np.arcsin(y))
                
                # Yaw is angle in XZ plane
                # using atan2(x, z) to match camera coordinate system orientation
                # (Z is forward 0, X is right 90)
                yaw_deg = np.degrees(np.arctan2(x, z))
                
                # Normalize yaw to 0-360
                yaw_deg = yaw_deg % 360.0
                
                # Apply pitch_offset to the calculated pitch
                final_pitch = pitch_deg + pitch_offset
                
                views.append((f"View_{i}", yaw_deg, final_pitch, 0))

        else:
            # Default to 'ring' layout (equidistant along horizon)
            for i in range(n):
                yaw = (i * 360.0) / n
                views.append((f"View_{i}", yaw, pitch_offset, 0))
                
        return views

    @staticmethod
    def get_rotation_matrix(yaw_deg, pitch_deg, roll_deg):
        """
        Calculate the 3D rotation matrix for given yaw, pitch, and roll.
        
        Args:
            yaw_deg (float): Rotation around Y axis (Horizontal pan)
            pitch_deg (float): Rotation around X axis (Vertical tilt)
            roll_deg (float): Rotation around Z axis
            
        Returns:
            np.ndarray: 3x3 Rotation matrix
        """
        # Convert to radians
        yaw = np.radians(yaw_deg)
        pitch = np.radians(pitch_deg)
        roll = np.radians(roll_deg)
        
        # Rx (Pitch)
        rx = np.array([
            [1, 0, 0],
            [0, np.cos(pitch), -np.sin(pitch)],
            [0, np.sin(pitch), np.cos(pitch)]
        ])
        
        # Ry (Yaw)
        ry = np.array([
            [np.cos(yaw), 0, np.sin(yaw)],
            [0, 1, 0],
            [-np.sin(yaw), 0, np.cos(yaw)]
        ])
        
        # Rz (Roll)
        rz = np.array([
            [np.cos(roll), -np.sin(roll), 0],
            [np.sin(roll), np.cos(roll), 0],
            [0, 0, 1]
        ])
        
        # R = Ry * Rx * Rz (Yaw -> Pitch -> Roll order is common)
        return ry @ rx @ rz

    @staticmethod
    def create_rectilinear_map(src_h, src_w, dest_h, dest_w, fov_deg, yaw_deg, pitch_deg, roll_deg, cancelled=None):
        """Project float64 ray tiles into float32 maps without full-frame ray arrays."""
        if min(src_h, src_w, dest_h, dest_w) <= 0 or not 0 < fov_deg < 180:
            raise ValueError("Positive dimensions and a FOV between 0 and 180 degrees are required")
        focal = (0.5 * dest_w) / np.tan(0.5 * np.radians(fov_deg))
        rotation = GeometryProcessor.get_rotation_matrix(yaw_deg, pitch_deg, roll_deg)
        map_x = np.empty((dest_h, dest_w), dtype=np.float32)
        map_y = np.empty((dest_h, dest_w), dtype=np.float32)
        for start in range(0, dest_h, 256):
            if cancelled is not None and cancelled():
                raise InterruptedError("Projection cancelled")
            end = min(dest_h, start + 256)
            x, y = np.meshgrid(np.arange(dest_w), np.arange(start, end))
            x_norm = (x - dest_w / 2) / focal
            y_norm = (y - dest_h / 2) / focal
            rays = np.stack((x_norm, y_norm, np.ones_like(x_norm)), axis=-1).reshape(-1, 3)
            rotated = rays @ rotation.T
            xr, yr, zr = rotated[:, 0], rotated[:, 1], rotated[:, 2]
            theta = np.arctan2(xr, zr)
            radius = np.sqrt(xr**2 + yr**2 + zr**2)
            phi = np.arcsin(np.clip(yr / radius, -1, 1))
            map_x[start:end] = ((theta / (2 * np.pi) + 0.5) * src_w).reshape(end-start, dest_w)
            map_y[start:end] = ((phi / np.pi + 0.5) * src_h).reshape(end-start, dest_w)
        return map_x, map_y
