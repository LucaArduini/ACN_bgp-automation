import os
import sys
import subprocess
from paramiko import SSHClient, AutoAddPolicy, RSAKey
from scp import SCPClient
from dotenv import load_dotenv

load_dotenv()

REMOTE_HOST = os.getenv('REMOTE_HOST')

REMOTE_USER = os.getenv('REMOTE_USER')

REMOTE_PASS = os.getenv('REMOTE_PASS')

if not REMOTE_HOST:
    print("[-] Errore: La variabile REMOTE_HOST non è definita nel file .env")
    sys.exit(1)
    
if not REMOTE_USER:
    print("[-] Errore: La variabile REMOTE_USER non è definita nel file .env")
    sys.exit(1)


REMOTE_PROJECT_ROOT = f'/home/{REMOTE_USER}/ACN_bgp-automation' 

FILES_TO_TRANSFER = [
    os.path.join("topology", "network.clab.yml"),
    "configs",
    os.path.join("automation", "handle_traffic.py")
]

def run_script(script_path):
    """Esegue uno script python locale"""
    print(f"[*] Esecuzione locale di {script_path}...")
    try:
        if not os.path.exists(script_path):
            print(f"[-] Errore: Il file {script_path} non esiste.")
            sys.exit(1)
            
        subprocess.run(
            [sys.executable, script_path], 
            check=True
        )
        print(f"[+] {script_path} completato.\n")
    except subprocess.CalledProcessError:
        print(f"[-] Errore durante l'esecuzione di {script_path}.")
        sys.exit(1)

def upload_selected_files():
    """Copia solo i file specificati mantenendo la struttura delle directory"""
    print(f"[*] Connessione a {REMOTE_USER}@{REMOTE_HOST}...")
    
    ssh = SSHClient()
    ssh.set_missing_host_key_policy(AutoAddPolicy())
    
    try:
        ssh.connect(REMOTE_HOST, username=REMOTE_USER, password=REMOTE_PASS)
        
        with SCPClient(ssh.get_transport()) as scp:
            for item in FILES_TO_TRANSFER:
                if not os.path.exists(item):
                    print(f"[!] Attenzione: Il file/cartella locale '{item}' non esiste. Salto.")
                    continue

                remote_dest_path = os.path.join(REMOTE_PROJECT_ROOT, item).replace("\\", "/")
                
                remote_parent_dir = os.path.dirname(remote_dest_path)
                
                print(f"[*] Copia di '{item}' -> '{remote_dest_path}'")
                
                ssh.exec_command(f"mkdir -p {remote_parent_dir}")
                
                scp.put(item, remote_path=remote_dest_path, recursive=True)
                
        print(f"\n[+] File trasferiti con successo in {REMOTE_PROJECT_ROOT}")
        
    except Exception as e:
        print(f"[-] Errore durante il trasferimento SSH/SCP: {e}")
        sys.exit(1)
    finally:
        ssh.close()

def main():
 
    topo_script = os.path.join("automation", "build_topology.py")
    run_script(topo_script)

    config_script = os.path.join("automation", "build_configs.py")
    run_script(config_script)

    upload_selected_files()

    print("\n[ok] Deploy completato.")

if __name__ == "__main__":
    main()