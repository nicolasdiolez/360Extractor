import os
import sys
import subprocess
import shutil
import time

def run_verification():
    print("=== Starting Verification: Selective Camera Direction ===")
    
    # Setup paths
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    test_video_path = os.path.join(base_dir, "tests", "temp_selective_video.mp4")
    output_dir = os.path.join(base_dir, "tests", "temp_selective_output")
    create_video_script = os.path.join(base_dir, "tests", "create_dummy_video.py")
    main_script = os.path.join(base_dir, "src", "main.py")

    # Clean up previous runs
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)
    if os.path.exists(test_video_path):
        os.remove(test_video_path)

    # 1. Create Dummy Video
    print(f"Creating dummy video at {test_video_path}...")
    subprocess.run([sys.executable, create_video_script, test_video_path], check=True)

    # 2. Run CLI with --active-cameras
    print("Running extraction with --active-cameras '0,2'...")
    cmd = [
        sys.executable, main_script,
        "--input", test_video_path,
        "--output", output_dir,
        "--active-cameras", "0,2",
        "--camera-count", "6", # Default is 6: Front(0), Right(1), Back(2), Left(3), Up(4), Down(5)
                               # Actually geometry.py says:
                               # 0: Front, 1: Right, 2: Back, 3: Left, 4: Up, 5: Down
                               # Wait, let's double check geometry.py output names in the loop
                               # In geometry.py:
                               # views.append(("Front", ...)) -> index 0
                               # views.append(("Right", ...)) -> index 1
                               # views.append(("Back", ...)) -> index 2
                               # ...
                               # But wait, processor.py iterates: for i, (name, y, p, r) in enumerate(views):
                               # So index 0 corresponds to "Front", index 2 corresponds to "Back".
        "--interval", "100", # High interval to just get 1 frame or so
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        print("Error running CLI:")
        print(result.stderr)
        sys.exit(1)
    
    print("CLI run completed.")

    # 3. Verify Output
    # The processor creates a subfolder based on filename
    video_name = os.path.splitext(os.path.basename(test_video_path))[0]
    processed_dir = os.path.join(output_dir, f"{video_name}_processed")
    
    if not os.path.exists(processed_dir):
        print(f"FAILED: Processed directory not found: {processed_dir}")
        sys.exit(1)
        
    files = os.listdir(processed_dir)
    print(f"Generated files: {files}")
    
    # We expect files ending in _Front.jpg (idx 0) and _Back.jpg (idx 2)
    # We DO NOT expect _Right.jpg (idx 1) etc.
    
    has_front = any("Front" in f for f in files)
    has_back = any("Back" in f for f in files)
    has_right = any("Right" in f for f in files)
    
    if has_front and has_back and not has_right:
        print("SUCCESS: Found Front (0) and Back (2), but not Right (1).")
    else:
        print("FAILED: Incorrect file distribution.")
        print(f"  Has Front (Expected True): {has_front}")
        print(f"  Has Back (Expected True): {has_back}")
        print(f"  Has Right (Expected False): {has_right}")
        sys.exit(1)

    # Cleanup
    print("Cleaning up...")
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)
    if os.path.exists(test_video_path):
        os.remove(test_video_path)
    print("Done.")

if __name__ == "__main__":
    run_verification()