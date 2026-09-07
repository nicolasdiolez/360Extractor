"""Check the selected interpreter and the dependencies of an execution mode."""
import argparse
import importlib
import importlib.metadata
import platform
import shutil
import sys
from pathlib import Path


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode',choices=['core','gui','ai','all'],default='all')
    parser.add_argument('--telemetry',action='store_true',help='Require FFmpeg and ffprobe')
    parser.add_argument('--ai-probe',action='store_true',help='Run one CPU inference with the default model')
    args=parser.parse_args()
    print(f'Python: {sys.executable}\nVersion: {platform.python_version()}\nPlatform: {platform.platform()}')
    dependencies={'numpy':'numpy','cv2':'opencv-python','defusedxml':'defusedxml','piexif':'piexif','PIL':'Pillow','tqdm':'tqdm'}
    if args.mode in ('gui','all'):
        dependencies['PySide6']='PySide6'
    if args.mode in ('ai','all') or args.ai_probe:
        dependencies.update(torch='torch',torchvision='torchvision',ultralytics='ultralytics')
    errors=[]
    for module,distribution in dependencies.items():
        try:
            loaded=importlib.import_module(module)
            try:
                version=importlib.metadata.version(distribution)
            except importlib.metadata.PackageNotFoundError:
                version=getattr(loaded,'__version__','unknown distribution')
            print(f'OK {module}: {version}')
        except Exception as exc:
            errors.append(f'{module}: {exc}')
    for executable in ('ffmpeg','ffprobe'):
        path=shutil.which(executable)
        print(f'{executable}: {path or "unavailable (required for embedded GPS)"}')
        if args.telemetry and not path:
            errors.append(f'{executable} is required')
    if args.ai_probe and not errors:
        try:
            import numpy as np
            sys.path.insert(0,str(Path(__file__).resolve().parent/'src'))
            from extractor360.core.ai_model import AIService
            service=AIService()
            service.device='cpu'
            _,mask=service.process_image(np.zeros((64,64,3),np.uint8),mode='generate_mask')
            if mask is None or mask.shape!=(64,64):
                raise RuntimeError('Unexpected inference output')
            print('CPU inference: OK (does not qualify segmentation accuracy or GPU)')
        except Exception as exc:
            errors.append(f'AI inference: {exc}')
    for error in errors:
        print(f'ERROR {error}',file=sys.stderr)
    return 1 if errors else 0


if __name__=='__main__':
    raise SystemExit(main())
