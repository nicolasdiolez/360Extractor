"""Bounded subprocess capture with cooperative cancellation."""
import subprocess
import os
import tempfile
import time


def capture(command, cancelled=lambda: False, timeout=30, limit=64 * 1024 * 1024):
    with tempfile.TemporaryFile() as output, tempfile.TemporaryFile() as errors:
        process = subprocess.Popen(command, stdout=output, stderr=errors)
        deadline = time.monotonic() + timeout
        try:
            while process.poll() is None:
                if cancelled():
                    raise InterruptedError('Metadata extraction cancelled')
                if time.monotonic() >= deadline:
                    raise TimeoutError('Metadata extraction timed out')
                if os.fstat(output.fileno()).st_size + os.fstat(errors.fileno()).st_size > limit:
                    raise ValueError('Metadata exceeds the configured capture limit')
                time.sleep(.02)
            if os.fstat(output.fileno()).st_size + os.fstat(errors.fileno()).st_size > limit:
                raise ValueError('Metadata exceeds the configured capture limit')
            if process.returncode:
                errors.seek(0)
                raise OSError(errors.read(4096).decode('utf-8', errors='replace'))
            output.seek(0)
            return output.read()
        finally:
            if process.poll() is None:
                process.kill()
            process.wait()
