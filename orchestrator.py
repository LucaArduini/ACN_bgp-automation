"""
This script acts as the main coordinator for the project deployment.
The orchestrator automates the entire initial workflow:
1. Runs generation scripts locally for the topology and router configurations.
2. Establishes an SSH connection with the remote server specified in the .env file.
3. Synchronizes the necessary files via SCP, managing remote workspace cleanup 
   and path normalization between different operating systems.
4. Sets the correct permissions on the remote server to allow the execution of bootstrap scripts.
"""

import os
import sys
import subprocess
from paramiko import SSHClient, AutoAddPolicy, RSAKey
from scp import SCPClient
from dotenv import load_dotenv

# Loading environment variables for remote access
load_dotenv()

REMOTE_HOST = os.getenv('REMOTE_HOST')
REMOTE_USER = os.getenv('REMOTE_USER')
REMOTE_PASS = os.getenv('REMOTE_PASS')

# Validation of credentials needed for deployment
if not REMOTE_HOST:
    print("[-] Error: The REMOTE_HOST variable is not defined in the .env file")
    sys.exit(1)
    
if not REMOTE_USER:
    print("[-] Error: The REMOTE_USER variable is not defined in the .env file")
    sys.exit(1)

# Definition of the project root on the target server
REMOTE_PROJECT_ROOT = f'/home/{REMOTE_USER}/ACN_bgp-automation' 

# List of essential files and directories to transfer to the server
FILES_TO_TRANSFER = [
    "topology",
    "configs",
    "tests",
    "teardown.sh",
    "bootstrap.sh",
    "Dockerfile.manager",
    os.path.join("automation", "manager.py"),
    os.path.join("automation", "generate_traffic.py"),
    os.path.join("automation", "optimizer_CE_PE.py"),
    os.path.join("automation", "optimizer_PE_GW.py"),
    os.path.join("automation", "handle_traffic.py")
]

def run_local_script(script_path):
    """Executes a local python script for artifact generation"""
    print(f"[*] Local execution of {script_path}...")
    try:
        if not os.path.exists(script_path):
            print(f"[-] Error: The file {script_path} does not exist.")
            sys.exit(1)
            
        subprocess.run(
            [sys.executable, script_path], 
            check=True
        )
        print(f"[+] {script_path} completed.\n")
    except subprocess.CalledProcessError:
        print(f"[-] Error during execution of {script_path}.")
        sys.exit(1)

def upload_selected_files():
    """Manages the SSH session and file transfer via SCP"""
    print(f"[*] Connecting to {REMOTE_USER}@{REMOTE_HOST}...")
    
    ssh_client = SSHClient()
    ssh_client.set_missing_host_key_policy(AutoAddPolicy())
    
    try:
        ssh_client.connect(REMOTE_HOST, username=REMOTE_USER, password=REMOTE_PASS)
        
        # Cleaning the remote directory to ensure a clean deployment
        print(f"[*] Total deletion of {REMOTE_PROJECT_ROOT} (requires sudo)...")
        # We use 'sudo -S' to read the password from 'echo' and execute the command as root
        delete_command = f"echo '{REMOTE_PASS}' | sudo -S rm -rf {REMOTE_PROJECT_ROOT}"
        stdin, stdout, stderr = ssh_client.exec_command(delete_command)
        exit_status = stdout.channel.recv_exit_status()
        
        if exit_status != 0:
            print(f"[-] Error during deletion: {stderr.read().decode()}")
        
        print(f"[*] Recreating root folder {REMOTE_PROJECT_ROOT}...")
        ssh_client.exec_command(f"mkdir -p {REMOTE_PROJECT_ROOT}")

        # Transferring files via SCPClient
        with SCPClient(ssh_client.get_transport()) as scp:
            for item in FILES_TO_TRANSFER:
                if not os.path.exists(item):
                    print(f"[!] Warning: Local file/folder '{item}' does not exist. Skipping.")
                    continue

                # Normalizing path separators for Linux environment
                linux_item = item.replace("\\", "/")
                
                # Calculating remote destination while maintaining folder structure
                if os.path.isdir(item):
                    parent_directory = os.path.dirname(linux_item) 
                    remote_destination_path = os.path.join(REMOTE_PROJECT_ROOT, parent_directory).replace("\\", "/")
                else:
                    remote_destination_path = os.path.join(REMOTE_PROJECT_ROOT, linux_item).replace("\\", "/")
                
                # Recursive creation of parent directories on the remote server
                if os.path.isdir(item):
                    remote_mkdir_path = remote_destination_path
                else:
                    remote_mkdir_path = os.path.dirname(remote_destination_path)
                
                print(f"[*] Copying '{item}' -> '{remote_destination_path}'")
                
                ssh_client.exec_command(f"mkdir -p {remote_mkdir_path}")
                scp.put(item, remote_path=remote_destination_path, recursive=True, preserve_times=True)
        
        # Setting execution permissions for the transferred shell scripts
        print(f"[*] Setting permissions (755) on {REMOTE_PROJECT_ROOT}...")
        chmod_command = f"echo '{REMOTE_PASS}' | sudo -S chmod -R 755 {REMOTE_PROJECT_ROOT}"
        stdin, stdout, stderr = ssh_client.exec_command(chmod_command)
        
        if stdout.channel.recv_exit_status() == 0:
            print(f"[+] Permissions updated successfully.")
        else:
            print(f"[-] Permissions error: {stderr.read().decode()}")
            
        # For security, we ensure the 'student' user is the owner of everything
        print(f"[*] Resetting file ownership to user {REMOTE_USER}...")
        chown_command = f"echo '{REMOTE_PASS}' | sudo -S chown -R {REMOTE_USER}:{REMOTE_USER} {REMOTE_PROJECT_ROOT}"
        ssh_client.exec_command(chown_command)

        print(f"\n[+] Deployment successfully completed in {REMOTE_PROJECT_ROOT}")
        
    except Exception as e:
        print(f"[-] Error during SSH/SCP transfer: {e}")
        sys.exit(1)
    finally:
        ssh_client.close()

def main():
    """Main workflow: local generation -> remote deployment"""
    
    # 1. Generating Containerlab YAML file from data
    topology_script = os.path.join("automation", "build_topology.py")
    run_local_script(topology_script)

    # 2. Generating FRR configurations via Jinja2 templates
    config_generation_script = os.path.join("automation", "build_configs.py")
    run_local_script(config_generation_script)

    # 3. Transferring artifacts to the remote server
    upload_selected_files()

    print("\n[ok] Script terminated.")

if __name__ == "__main__":
    main()