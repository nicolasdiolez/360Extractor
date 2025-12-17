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

    def summary(self) -> str:
        """Returns a short summary of the job settings."""
        # e.g., "High (-20°), 6 cams"
        pitch_val = self.settings.get('pitch_offset', 0)
        pitch_name = "Std"
        if pitch_val == -20: pitch_name = "High"
        elif pitch_val == 20: pitch_name = "Low"
        
        cams = self.settings.get('camera_count', 6)
        layout = self.settings.get('layout_mode', 'adaptive')
        layout_info = " (Ring)" if layout == 'ring' else ""
        return f"{pitch_name} ({pitch_val}°), {cams} cams{layout_info}"