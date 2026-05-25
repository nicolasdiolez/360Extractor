# -*- coding: utf-8 -*-
"""
360 Extractor - PyTorch CUDA GPU Setup Helper
Automates the correct installation of PyTorch and torchvision with CUDA support
to prevent pip from downgrading back to the CPU-only version.
"""

import os
import sys
import subprocess
import shutil

# Terminal formatting helpers
def print_success(msg):
    print(f"  \033[92m✅ {msg}\033[0m")

def print_warning(msg):
    print(f"  \033[93m⚠️  {msg}\033[0m")

def print_error(msg):
    print(f"  \033[91m❌ {msg}\033[0m")

def print_info(msg):
    print(f"  \033[94mℹ️  {msg}\033[0m")

def print_step(msg):
    print(f"\n\033[1;36m=== {msg} ===\033[0m")

def is_virtual_env():
    # Detects standard venv, virtualenv, or conda env
    return (
        hasattr(sys, 'real_prefix') or 
        (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix) or
        'CONDA_PREFIX' in os.environ
    )

def check_nvidia_smi():
    """Checks if nvidia-smi command is available, indicating NVIDIA GPU driver presence."""
    return shutil.which("nvidia-smi") is not None

def run_command(command, description):
    """Runs a shell command and streams the output."""
    print_info(f"Running: {' '.join(command)}")
    try:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True
        )
        
        # Print output in real time
        for line in process.stdout:
            print(f"    {line.strip()}")
            
        process.wait()
        
        if process.returncode == 0:
            print_success(f"Successfully completed: {description}")
            return True
        else:
            print_error(f"Failed: {description} (Exit code: {process.returncode})")
            return False
    except Exception as e:
        print_error(f"Error executing command: {e}")
        return False

def setup_gpu():
    print_step("360 Extractor Pro - PyTorch CUDA Setup Helper")
    
    # 1. OS Check
    is_win = sys.platform.startswith('win')
    is_linux = sys.platform.startswith('linux')
    is_mac = sys.platform.startswith('darwin')
    
    if is_mac:
        print_info("Operating System detected: macOS")
        print_success("macOS uses Apple Silicon GPU (MPS) natively with the standard PyTorch installation.")
        print_success("You do not need to install CUDA. Simply run:")
        print("    pip install -r requirements.txt")
        print("    python check_env.py")
        return True
        
    print_info(f"Operating System detected: {'Windows' if is_win else 'Linux'}")
    
    # 2. Virtual Env Check
    if not is_virtual_env():
        print_warning("No virtual environment (venv or Conda) detected.")
        print_warning("It is highly recommended to run this inside an active virtual environment to avoid permission errors.")
        choice = input("    Do you want to proceed anyway? (y/N): ").strip().lower()
        if choice != 'y':
            print_info("Setup aborted. Please activate your environment and try again.")
            return False
    else:
        env_type = "Conda" if 'CONDA_PREFIX' in os.environ else "venv/virtualenv"
        print_success(f"Active Virtual Environment detected ({env_type})")

    # 3. NVIDIA GPU Driver Check
    has_nvidia = check_nvidia_smi()
    if not has_nvidia:
        print_warning("NVIDIA System Management Interface (nvidia-smi) was not found on your system path.")
        print_warning("This might mean you do not have an NVIDIA GPU, or the drivers are not properly installed/configured.")
        choice = input("    Do you still want to force PyTorch CUDA installation? (y/N): ").strip().lower()
        if choice != 'y':
            print_info("Setup aborted.")
            return False
    else:
        print_success("NVIDIA GPU / Driver detected on the system.")

    # 4. Prompt CUDA Version
    print_step("Select CUDA / PyTorch Configuration")
    print("  [1] CUDA 12.4 (Recommended for modern RTX 30/40-series cards) - Default")
    print("  [2] CUDA 12.1 (For systems requiring older drivers)")
    print("  [3] CPU-Only (If you do not have an NVIDIA GPU)")
    print("  [4] Abort Setup")
    
    choice = input("\n  Enter choice [1-4] (default: 1): ").strip()
    if not choice:
        choice = '1'
        
    if choice == '4':
        print_info("Setup aborted.")
        return False
        
    index_url = None
    cuda_name = ""
    if choice == '1':
        index_url = "https://download.pytorch.org/whl/cu124"
        cuda_name = "CUDA 12.4"
    elif choice == '2':
        index_url = "https://download.pytorch.org/whl/cu121"
        cuda_name = "CUDA 12.1"
    elif choice == '3':
        index_url = None
        cuda_name = "CPU-Only"
    else:
        print_error("Invalid choice. Setup aborted.")
        return False

    # 5. Uninstall Existing Packages
    print_step("Step 1: Uninstalling existing PyTorch packages to prevent conflicts")
    pip_cmd = [sys.executable, "-m", "pip"]
    
    uninstall_cmd = pip_cmd + ["uninstall", "torch", "torchvision", "torchaudio", "-y"]
    run_command(uninstall_cmd, "Uninstalling existing torch, torchvision, and torchaudio")

    # 6. Install PyTorch with selected acceleration
    print_step(f"Step 2: Installing PyTorch + torchvision for {cuda_name}")
    if index_url:
        # Crucial: Install BOTH torch and torchvision together from the same custom index url
        install_cmd = pip_cmd + ["install", "torch", "torchvision", "--index-url", index_url]
    else:
        install_cmd = pip_cmd + ["install", "torch", "torchvision"]
        
    success = run_command(install_cmd, f"Installing PyTorch and torchvision ({cuda_name})")
    if not success:
        print_error("Failed to install PyTorch packages. Please check internet connection or permissions.")
        return False

    # 7. Install requirements.txt
    print_step("Step 3: Installing remaining application dependencies")
    if os.path.exists("requirements.txt"):
        req_cmd = pip_cmd + ["install", "-r", "requirements.txt"]
        success = run_command(req_cmd, "Installing dependencies from requirements.txt")
        if not success:
            print_warning("Some dependencies failed to install. You may need to run `pip install -r requirements.txt` manually.")
    else:
        print_warning("requirements.txt file not found in current directory. Skipping.")

    # 8. Verification Check
    print_step("Step 4: Verifying Installation")
    try:
        # Run standard python script block to check
        code = "import torch; print(f'Torch: {torch.__version__} | CUDA Available: {torch.cuda.is_available()} | GPU: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else None}')"
        verify_cmd = [sys.executable, "-c", code]
        
        # Execute synchronously and grab stdout
        result = subprocess.run(verify_cmd, capture_output=True, text=True, check=True)
        print_success("PyTorch Verification Check:")
        print(f"      {result.stdout.strip()}")
        
        # Check if CUDA is actually available
        import torch
        if choice in ['1', '2'] and not torch.cuda.is_available():
            print_warning("Installation finished, but PyTorch reports CUDA is still NOT available.")
            print_warning("Please verify that your NVIDIA drivers are properly installed and up-to-date.")
        elif choice == '3':
            print_success("Successfully configured for CPU execution!")
        else:
            print_success("GPU Acceleration is FULLY ACTIVE and ready to use!")
            
    except Exception as e:
        print_error(f"Verification check failed: {e}")
        print_warning("Please try running `python check_env.py` to see the full diagnostics.")

    print("\n" + "=" * 40)
    print_success("Setup process finished! You can now launch 360 Extractor:")
    print("    python src/main.py")
    print("=" * 40 + "\n")
    return True

if __name__ == "__main__":
    try:
        setup_gpu()
    except KeyboardInterrupt:
        print("\n\n❌ Setup interrupted by user.")
        sys.exit(1)
