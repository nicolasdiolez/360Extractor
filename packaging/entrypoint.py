"""Entry point for the frozen (PyInstaller) application.

Deliberately separate from ``src/main.py``: that one is a development shim that
patches ``sys.path`` so a plain checkout can run without installing. In a frozen
bundle the ``extractor360`` package is already importable, so the launcher just
calls into it.
"""
import multiprocessing

from extractor360.main import main

if __name__ == "__main__":
    # Required for frozen apps on Windows/macOS: without it, any library that
    # spawns a process (torch does) would re-launch the whole GUI instead.
    multiprocessing.freeze_support()
    main()
