"""
This script automates the installation of the Python dependencies required for the project.
The script reads the list of packages from the 'requirements.txt' file and uses pip for installation.
"""

import subprocess
import sys
import os

def install_requirements():
    # Name of the file containing the list of external libraries
    requirements_file = "requirements.txt"

    if not os.path.exists(requirements_file):
        print(f"[-] Error: The file '{requirements_file}' was not found in the current directory.")
        sys.exit(1)

    print(f"[*] Starting installation of libraries from {requirements_file}...")
    
    try:
        # Executes pip install using the current Python interpreter for consistency
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", requirements_file])
        print("\n[+] Installation completed successfully.")
        
    except subprocess.CalledProcessError as e:
        print(f"\n[-] An error occurred during installation.")
        sys.exit(1)

if __name__ == "__main__":
    install_requirements()