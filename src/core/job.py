from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
import os

@dataclass
class Job:
    file_path: str
    status: str = "Pending"  # Pending, Processing, Done, Error
    settings: Dict[str, Any] = field(default_factory=dict)

    @property
    def active_cameras(self) -> Optional[List[int]]:
        return self.settings.get('active_cameras', None)

    @property
    def filename(self) -> str:
        return os.path.basename(self.file_path)

    @property
    def output_format(self) -> str:
        return self.settings.get('output_format', 'jpg')

    @property
    def output_dir(self) -> str:
        return self.settings.get('custom_output_dir', '')

    @property
    def smart_blur(self) -> bool:
        return self.settings.get('smart_blur_enabled', False)

    @property
    def adaptive_mode(self) -> bool:
        return self.settings.get('adaptive_mode', False)

    @property
    def adaptive_threshold(self) -> float:
        return self.settings.get('adaptive_threshold', 0.5)

    @property
    def resolution(self) -> int:
        return self.settings.get('resolution', 2048)

    @property
    def export_telemetry(self) -> bool:
        return self.settings.get('export_telemetry', False)

    @property
    def interpolation_mode(self) -> str:
        return self.settings.get('interpolation_mode', 'linear')

    @property
    def feather_mask(self) -> bool:
        return self.settings.get('feather_mask', False)

    def summary(self) -> str:
        """Returns a short summary of the job settings."""
        # e.g., "High (-20°), 6 cams"
        is_360 = self.settings.get('is_360', True)
        
        # 360 settings vs Flat settings
        if is_360:
            pitch_val = self.settings.get('pitch_offset', 0)
            pitch_name = "Std"
            if pitch_val == -20: pitch_name = "High"
            elif pitch_val == 20: pitch_name = "Low"
            
            cams = self.settings.get('camera_count', 6)
            layout = self.settings.get('layout_mode', 'adaptive')
            layout_info = " (Ring)" if layout == 'ring' else (" (Cube)" if layout == 'cube' else " (Fibonacci)" if layout == 'fibonacci' else "")
            cam_str = f", {cams} cams{layout_info}"
            pitch_str = f"{pitch_name} ({pitch_val}°)"
        else:
            pitch_str = "Flat (Non-360)"
            cam_str = ""

        adaptive = " [Adaptive]" if self.adaptive_mode else ""
        
        # AI Mode info
        ai_mode = self.settings.get('ai_mode', 'None')
        ai_str = ""
        if ai_mode == 'Generate Mask':
            ai_str = " [AI Mask]"
        elif ai_mode == 'Skip Frame':
            ai_str = " [AI Skip]"
            
        return f"{pitch_str}{cam_str}{adaptive}{ai_str}"