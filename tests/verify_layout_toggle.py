import sys
import os

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from core.geometry import GeometryProcessor

def test_layout_toggle():
    print("Testing Adaptive Mode with n=6 (Expect Cube Layout)")
    views_adaptive = GeometryProcessor.generate_views(6, layout_mode='adaptive')
    names_adaptive = [v[0] for v in views_adaptive]
    print(f"Views: {names_adaptive}")
    
    if "Up" in names_adaptive and "Down" in names_adaptive:
        print("PASS: Adaptive mode produced Cube layout for n=6.")
    else:
        print("FAIL: Adaptive mode did NOT produce Cube layout for n=6.")

    print("\nTesting Ring Mode with n=6 (Expect Ring Layout)")
    views_ring = GeometryProcessor.generate_views(6, layout_mode='ring')
    names_ring = [v[0] for v in views_ring]
    print(f"Views: {names_ring}")
    
    if "Up" not in names_ring and "View_5" in names_ring:
        print("PASS: Ring mode produced Ring layout for n=6.")
    else:
        print("FAIL: Ring mode did NOT produce Ring layout for n=6.")

    print("\nTesting Adaptive Mode with n=4 (Expect Ring Layout)")
    views_small = GeometryProcessor.generate_views(4, layout_mode='adaptive')
    names_small = [v[0] for v in views_small]
    print(f"Views: {names_small}")
    
    if "View_3" in names_small:
         print("PASS: Adaptive mode produced Ring layout for n<6.")

if __name__ == "__main__":
    test_layout_toggle()
