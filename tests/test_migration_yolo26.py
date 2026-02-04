import sys
import os
import time

# Add src to path
sys.path.append(os.path.join(os.getcwd(), 'src'))

try:
    from core.ai_model import AIService
    from ultralytics import YOLO
    import ultralytics
    print(f"Ultralytics version: {ultralytics.__version__}")
except ImportError as e:
    print(f"Error importing modules: {e}")
    sys.exit(1)

def test_load_model():
    print("Testing AIService initialization with YOLO26...")
    try:
        # This should trigger download if not present
        ai = AIService('yolo26n-seg.pt')
        print("Model loaded successfully!")
        
        # Verify internal model name if possible, or just the object
        print(f"Model object: {ai.model}")
        return True
    except Exception as e:
        print(f"Failed to load model: {e}")
        return False

if __name__ == "__main__":
    if test_load_model():
        print("VERIFICATION SUCCESS")
    else:
        print("VERIFICATION FAILED")
        sys.exit(1)
