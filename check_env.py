# -*- coding: utf-8 -*-
import sys

def check_imports():
    print("Verifying environment for 360 Extractor...")
    print("-" * 40)
    
    missing_packages = []
    
    # Check opencv-python
    try:
        import cv2
        print(f"✅ opencv-python (cv2) found: {cv2.__version__}")
    except ImportError:
        missing_packages.append("opencv-python")
        print("❌ opencv-python (cv2) NOT found")
    except Exception as e:
        missing_packages.append(f"opencv-python (Error: {e})")
        print(f"❌ opencv-python (cv2) error: {e}")

    # Check numpy
    try:
        import numpy
        print(f"✅ numpy found: {numpy.__version__}")
    except ImportError:
        missing_packages.append("numpy")
        print("❌ numpy NOT found")
    except Exception as e:
        missing_packages.append(f"numpy (Error: {e})")
        print(f"❌ numpy error: {e}")

    # Check PySide6
    try:
        import PySide6
        print(f"✅ PySide6 found: {PySide6.__version__}")
    except ImportError:
        missing_packages.append("PySide6")
        print("❌ PySide6 NOT found")
    except Exception as e:
        missing_packages.append(f"PySide6 (Error: {e})")
        print(f"❌ PySide6 error: {e}")

    # Check ultralytics
    try:
        import ultralytics
        print(f"✅ ultralytics found: {ultralytics.__version__}")
    except ImportError:
        missing_packages.append("ultralytics")
        print("❌ ultralytics NOT found")
    except Exception as e:
        missing_packages.append(f"ultralytics (Error: {e})")
        print(f"❌ ultralytics error: {e}")

    # Check PyTorch & GPU acceleration (CUDA/MPS)
    try:
        import torch
        print(f"✅ PyTorch found: {torch.__version__}")
        if torch.cuda.is_available():
            print(f"   - GPU Acceleration (CUDA): Available (Device: {torch.cuda.get_device_name(0)})")
        elif torch.backends.mps.is_available():
            print("   - GPU Acceleration (MPS): Available (Apple Silicon)")
        else:
            print("   - GPU Acceleration: NOT Available (Running on CPU)")
            if "+cpu" in torch.__version__:
                print("     ⚠️  You have the CPU-only version of PyTorch installed.")
                print("     If you have an NVIDIA GPU, reinstall PyTorch with CUDA support:")
                print("     pip install --force-reinstall torch --index-url https://download.pytorch.org/whl/cu121")
            else:
                print("     If you have a compatible GPU, please check your CUDA drivers or PyTorch installation.")
    except ImportError:
        missing_packages.append("torch")
        print("❌ PyTorch NOT found")
    except Exception as e:
        missing_packages.append(f"torch (Error: {e})")
        print(f"❌ PyTorch error: {e}")

    print("-" * 40)
    
    if missing_packages:
        print("⚠️  Missing or broken packages detected:")
        for pkg in missing_packages:
            print(f"   - {pkg}")
        print("\nPlease install the required dependencies by running:")
        print("   pip install -r requirements.txt")
        sys.exit(1)
    else:
        print("🎉 Environment verified! Ready to run 360 Extractor.")
        sys.exit(0)

if __name__ == "__main__":
    check_imports()