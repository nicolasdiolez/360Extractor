"""Configure PyTorch in an isolated environment using an official wheel index."""
import argparse
from pathlib import Path
import re
import subprocess
import sys


def run(command):
    result = subprocess.run(command, check=False)
    if result.returncode:
        raise RuntimeError(f'Installation command failed (exit {result.returncode})')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--index-url', help='Official index from https://pytorch.org/get-started/locally/')
    args = parser.parse_args()
    if sys.prefix == sys.base_prefix:
        parser.error('Create and activate a virtual environment first')
    url = args.index_url or input('Official PyTorch wheel index URL (cpu or cuXXX): ').strip()
    if not re.fullmatch(r'https://download\.pytorch\.org/whl/(cpu|cu\d+)', url):
        parser.error('Use an official https://download.pytorch.org/whl/cpu or cuXXX index')
    project = Path(__file__).resolve().parent
    constraints = str(project / 'constraints' / 'security-minimums.txt')
    pip = [sys.executable, '-m', 'pip']
    torch = pip + ['install', '--upgrade', 'torch', 'torchvision', '--index-url', url, '-c', constraints]
    try:
        run(torch + ['--dry-run'])
        run(torch)
        run(pip + ['install', str(project), '-c', constraints])
        run(pip + ['check'])
        probe = 'import torch; print(torch.__version__); print("CUDA:",torch.cuda.is_available())'
        if url.endswith('cpu'):
            probe += '; print("CPU installation verified")'
        else:
            probe += '; assert torch.cuda.is_available(), "CUDA is unavailable; check the driver and selected index"'
        run([sys.executable, '-c', probe])
    except (OSError, RuntimeError) as exc:
        print(f'GPU setup failed: {exc}', file=sys.stderr)
        return 1
    print('Installation verified. Run python check_env.py --ai-probe for an inference test.')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130)
