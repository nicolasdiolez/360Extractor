"""Tests never read or write the developer's saved preferences."""
import sys
import os
import tempfile

import pytest

_ultralytics_config = tempfile.TemporaryDirectory(prefix='360-tests-ultralytics-')
_previous_ultralytics_config = os.environ.get('YOLO_CONFIG_DIR')
os.environ['YOLO_CONFIG_DIR'] = _ultralytics_config.name


def pytest_unconfigure(config):
    if _previous_ultralytics_config is None:
        os.environ.pop('YOLO_CONFIG_DIR', None)
    else:
        os.environ['YOLO_CONFIG_DIR'] = _previous_ultralytics_config
    _ultralytics_config.cleanup()



@pytest.fixture(autouse=True)
def isolated_preferences(tmp_path, monkeypatch):
    monkeypatch.setenv('EXTRACTOR360_CONFIG_DIR', str(tmp_path / 'preferences'))
    from extractor360.core.settings_manager import SettingsManager
    SettingsManager._instance = None
    yield
    if 'PySide6.QtWidgets' in sys.modules:
        from PySide6.QtCore import QThreadPool
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance()
        if app:
            for widget in app.topLevelWidgets():
                if hasattr(widget, 'shutdown'):
                    widget.shutdown()
                widget.close()
            QThreadPool.globalInstance().waitForDone(5000)
            for _ in range(10):
                app.processEvents()
    SettingsManager._instance = None
