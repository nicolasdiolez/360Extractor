import json
from pathlib import Path

from utils.logger import logger

class SettingsManager:
    _instance = None
    
    DEFAULT_SETTINGS = {
        "is_360": True,
        "resolution": 2048,
        "fov": 90,
        "camera_count": 6,
        "pitch_offset": 0,
        "layout_mode": "ring",
        "ai_mode": "None",
        "ai_confidence": 0.25,
        "ai_invert_mask": True,
        "ai_detect_humans": True,
        "ai_detect_vehicles": False,
        "ai_detect_plants": False,
        "ai_custom_classes": "",
        "quality": 95,
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
        "altitude_mode": "absolute",
        "interpolation_mode": "linear",
        "feather_mask": False,
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
            logger.warning(f"Error loading settings from {self.config_file}: {e}. Using defaults.")

    def save_settings(self, settings=None):
        """Write settings to the JSON file."""
        if settings:
            self.settings.update(settings)
            
        try:
            self.config_dir.mkdir(parents=True, exist_ok=True)
            with open(self.config_file, 'w') as f:
                json.dump(self.settings, f, indent=4)
        except OSError as e:
            logger.error(f"Error saving settings to {self.config_file}: {e}")

    def get(self, key, default=None):
        """Get a setting value."""
        return self.settings.get(key, default)

    def set(self, key, value):
        """Set a setting value."""
        self.settings[key] = value

    def get_all(self):
        """Return a copy of all settings."""
        return self.settings.copy()

def build_settings(args, config, active_cameras=None, output_path=""):
    """Assemble the settings dict consumed by the processor.

    Precedence, lowest to highest: ``SettingsManager.DEFAULT_SETTINGS`` < config
    file < explicit CLI arguments. Seeding from ``DEFAULT_SETTINGS`` guarantees
    every key the processor reads is present even when the config file omits it,
    which avoids silent fallbacks to hard-coded defaults (for example, a missing
    ``blur_threshold`` previously reverted to ``100.0`` no matter what the config
    file said, because the CLI never copied the key through).

    ``args`` is the parsed ``argparse.Namespace``. ``active_cameras`` and
    ``output_path`` are resolved by the caller (they involve validation / IO).
    """
    settings = SettingsManager.DEFAULT_SETTINGS.copy()

    # Config file overrides defaults. Keys share the names used in
    # DEFAULT_SETTINGS and the processor (interval_value, output_format,
    # blur_threshold, interpolation_mode, ...), so they map straight through.
    settings.update(config)

    # Backward-compatible aliases for older config files.
    if 'interval' in config and 'interval_value' not in config:
        settings['interval_value'] = config['interval']
    if 'format' in config and 'output_format' not in config:
        settings['output_format'] = config['format']

    # --- Explicit CLI arguments override the config file (when provided) ---
    cli_overrides = {
        'resolution': args.resolution,
        'camera_count': args.camera_count,
        'quality': args.quality,
        'layout_mode': args.layout,
        'output_format': args.format,
        'altitude_mode': args.altitude_mode,
        'ai_custom_classes': args.custom_classes,
        'naming_mode': args.naming_mode,
        'image_pattern': args.image_pattern,
        'mask_pattern': args.mask_pattern,
    }
    for key, value in cli_overrides.items():
        if value is not None:
            settings[key] = value

    # --interval is expressed in seconds.
    if args.interval is not None:
        settings['interval_value'] = args.interval
        settings['interval_unit'] = 'Seconds'

    # Flat (non-360) input.
    if getattr(args, 'flat', False):
        settings['is_360'] = False

    # AI mode: CLI flags win; otherwise honor the legacy boolean 'ai' config key.
    if getattr(args, 'ai_skip', False):
        settings['ai_mode'] = 'Skip Frame'
    elif getattr(args, 'ai_mask', False) or getattr(args, 'ai', False):
        settings['ai_mode'] = 'Generate Mask'
    elif settings.get('ai_mode', 'None') == 'None' and config.get('ai', False):
        settings['ai_mode'] = 'Generate Mask'

    # Adaptive interval.
    if getattr(args, 'adaptive', False):
        settings['adaptive_mode'] = True
    if args.motion_threshold is not None:
        settings['adaptive_threshold'] = args.motion_threshold

    # Telemetry.
    if getattr(args, 'export_telemetry', False):
        settings['export_telemetry'] = True

    # AI detection targets.
    if args.targets is not None:
        targets = [t.strip().lower() for t in args.targets.split(',')]
        settings['ai_detect_humans'] = 'humans' in targets
        settings['ai_detect_vehicles'] = 'vehicles' in targets
        settings['ai_detect_plants'] = 'plants' in targets

    # A supplied pattern without an explicit mode implies custom naming.
    if (args.image_pattern or args.mask_pattern) and not args.naming_mode:
        settings['naming_mode'] = 'custom'

    # Values resolved by the caller.
    settings['active_cameras'] = active_cameras
    settings['custom_output_dir'] = output_path

    return settings
