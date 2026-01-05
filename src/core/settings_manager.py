import json
import os
from pathlib import Path

class SettingsManager:
    _instance = None
    
    DEFAULT_SETTINGS = {
        "resolution": 2048,
        "fov": 90,
        "camera_count": 6,
        "pitch_offset": 0,
        "layout_mode": "ring",
        "ai_mode": "None",
        "output_format": "jpg",
        "custom_output_dir": "",
        "interval_value": 1.0,
        "interval_unit": "Seconds",
        "blur_filter_enabled": False,
        "smart_blur_enabled": False,
        "blur_threshold": 100.0,
        "sharpening_enabled": False,
        "sharpening_strength": 0.5,
        "adaptive_mode": False,
        "adaptive_threshold": 0.5,
        "export_telemetry": False,
        "naming_mode": "realityscan",
        "image_pattern": "{filename}_frame{frame}_{camera}",
        "mask_pattern": "{filename}_frame{frame}_{camera}_mask"
    }

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SettingsManager, cls).__new__(cls)
            cls._instance.initialized = False
        return cls._instance

    def __init__(self):
        if self.initialized:
            return
            
        self.settings = self.DEFAULT_SETTINGS.copy()
        
        # Determine config path: ~/.application360/config.json
        self.config_dir = Path.home() / ".application360"
        self.config_file = self.config_dir / "config.json"
        
        self.load_settings()
        self.initialized = True

    def load_settings(self):
        """Load settings from the JSON file. If file doesn't exist or is corrupt, use defaults."""
        if not self.config_file.exists():
            return

        try:
            with open(self.config_file, 'r') as f:
                loaded_settings = json.load(f)
                # Update current settings with loaded values
                # This ensures any new defaults keys are preserved if missing in file
                for key, value in loaded_settings.items():
                    self.settings[key] = value
        except (json.JSONDecodeError, OSError) as e:
            print(f"Error loading settings from {self.config_file}: {e}. Using defaults.")

    def save_settings(self, settings=None):
        """Write settings to the JSON file."""
        if settings:
            self.settings.update(settings)
            
        try:
            self.config_dir.mkdir(parents=True, exist_ok=True)
            with open(self.config_file, 'w') as f:
                json.dump(self.settings, f, indent=4)
        except OSError as e:
            print(f"Error saving settings to {self.config_file}: {e}")

    def get(self, key, default=None):
        """Get a setting value."""
        return self.settings.get(key, default)

    def set(self, key, value):
        """Set a setting value."""
        self.settings[key] = value

    def get_all(self):
        """Return a copy of all settings."""
        return self.settings.copy()