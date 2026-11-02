"""Entry point for the frozen (PyInstaller) application.

Deliberately separate from ``src/main.py``: that one is a development shim that
patches ``sys.path`` so a plain checkout can run without installing. In a frozen
bundle the ``extractor360`` package is already importable, so the launcher just
calls into it.
"""
import multiprocessing
import os
import sys

# Windows' GUI launcher has no console streams; libraries still expect file-like
# objects. Command-line users have the sibling "360 Extractor CLI.exe", whose
# console bootloader supplies real streams for help, progress and errors.
for stream in ("stdin", "stdout", "stderr"):
    if getattr(sys, stream) is None:
        setattr(sys, stream, open(os.devnull, "r" if stream == "stdin" else "w"))

from extractor360.main import main

if __name__ == "__main__":
    # Required for frozen apps on Windows/macOS: without it, any library that
    # spawns a process (torch does) would re-launch the whole GUI instead.
    multiprocessing.freeze_support()
    main()
