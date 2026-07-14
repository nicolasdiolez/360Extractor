#!/usr/bin/env python3
"""Back-compat launcher: the code moved into the `extractor360` package.

Keeps the documented `python3 src/main.py [...]` invocation working from a
plain checkout (no pip install). This shim is not part of the wheel; installed
users get the `360extractor` entry point or `python -m extractor360`.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from extractor360.main import main  # noqa: E402

if __name__ == "__main__":
    main()
