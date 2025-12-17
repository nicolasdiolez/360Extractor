import numpy as np
import cv2

class GeometryProcessor:
    """
    Handles mathematical operations for reprojecting Equirectangular images
    to Rectilinear (Pinhole) views.
    """

    @staticmethod
    def generate_views(n, pitch_offset=0, layout_mode='adaptive'):
        """
        Generate a list of (name, yaw, pitch, roll) tuples for n cameras.
        
        Args:
            n (int): Number of cameras (2-36)
            pitch_offset (float): Offset in degrees for vertical inclination (e.g. -20 for High/Perch)
            layout_mode (str): 'adaptive' (default) or 'ring'.
                               'adaptive' uses Ring for <6, Cube for 6, Fib for >6.
                               'ring' forces horizon-only ring layout.
            
        Returns:
            list: List of (name, yaw, pitch, roll) tuples.
        """
        views = []
        
        # Force Ring layout if requested OR if n < 6 (adaptive default)
        if layout_mode == 'ring' or (layout_mode == 'adaptive' and n < 6):
            # Ring layout (equidistant along horizon)
            for i in range(n):
                yaw = (i * 360.0) / n
                views.append((f"View_{i}", yaw, pitch_offset, 0))
                
        elif n == 6:
            # Cube layout
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
            
        else:
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
    def create_rectilinear_map(src_h, src_w, dest_h, dest_w, fov_deg, yaw_deg, pitch_deg, roll_deg):
        """
        Generate mapping coordinates for cv2.remap to convert Equirectangular to Rectilinear.
        
        Args:
            src_h (int): Height of source equirectangular image
            src_w (int): Width of source equirectangular image
            dest_h (int): Height of destination rectilinear image
            dest_w (int): Width of destination rectilinear image
            fov_deg (float): Horizontal Field of View in degrees
            yaw_deg (float): View direction yaw
            pitch_deg (float): View direction pitch
            roll_deg (float): View direction roll
            
        Returns:
            tuple: (map_x, map_y) for use with cv2.remap
        """
        # 1. Calculate focal length from FOV
        # tan(FOV/2) = (W/2) / f  =>  f = (W/2) / tan(FOV/2)
        f = (0.5 * dest_w) / np.tan(0.5 * np.radians(fov_deg))
        cx, cy = dest_w / 2, dest_h / 2
        
        # 2. Create meshgrid for target image pixels
        x, y = np.meshgrid(np.arange(dest_w), np.arange(dest_h))
        
        # 3. Convert to normalized camera coordinates (z=1 plane)
        # Using standard camera coordinate system: X right, Y down, Z forward
        x_norm = (x - cx) / f
        y_norm = (y - cy) / f
        z_norm = np.ones_like(x_norm)
        
        # Stack into (H, W, 3) vectors
        xyz = np.stack((x_norm, y_norm, z_norm), axis=-1)
        
        # 4. Apply Rotation
        # We rotate the ray vectors from the camera frame into the world frame
        R = GeometryProcessor.get_rotation_matrix(yaw_deg, pitch_deg, roll_deg)
        
        # Flatten to (N, 3) for matrix multiplication
        xyz_flat = xyz.reshape(-1, 3)
        # R is 3x3, xyz_flat is Nx3. We want v_rot = R * v.
        # Transpose logic: (R @ v.T).T = v @ R.T
        xyz_rotated = xyz_flat @ R.T
        
        # 5. Convert Rotated Cartesian to Spherical Coordinates
        x_rot = xyz_rotated[:, 0]
        y_rot = xyz_rotated[:, 1]
        z_rot = xyz_rotated[:, 2]
        
        # Longitude (theta) = atan2(x, z)
        theta = np.arctan2(x_rot, z_rot)
        
        # Latitude (phi) = asin(y / r)
        r = np.sqrt(x_rot**2 + y_rot**2 + z_rot**2)
        phi = np.arcsin(y_rot / r)
        
        # 6. Map Spherical to Equirectangular UV
        # theta in [-pi, pi] -> map to [0, W]
        # phi in [-pi/2, pi/2] -> map to [0, H]
        
        # Source U: (theta / (2*pi) + 0.5) * src_w
        uf = (theta / (2 * np.pi) + 0.5) * src_w
        
        # Source V: (phi / pi + 0.5) * src_h
        vf = (phi / np.pi + 0.5) * src_h
        
        # 7. Reshape back to image dimensions
        map_x = uf.reshape(dest_h, dest_w).astype(np.float32)
        map_y = vf.reshape(dest_h, dest_w).astype(np.float32)
        
        return map_x, map_y