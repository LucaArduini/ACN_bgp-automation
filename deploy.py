import os
import sys
import subprocess
from paramiko import SSHClient, AutoAddPolicy
from scp import SCPClient

# --- CONFIGURAZIONE ---
REMOTE_HOST = '192.168.56.101'
REMOTE_USER = 'student'
REMOTE_PASS = 'student'
# Creiamo una cartella dedicata per mantenere l'ordine e far funzionare i path relativi
REMOTE_PROJECT_ROOT = '/home/student/ACN_bgp-automation' 

# Lista dei file/cartelle da copiare (percorsi relativi alla root del progetto)
FILES_TO_TRANSFER = [
    os.path.join("topology", "network.clab.yml"),
    "configs",                       # Copia l'intera cartella
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

                # Calcola il percorso di destinazione remoto
                # Esempio: topology/network.clab.yml -> /home/student/ACN_bgp-automation/topology/network.clab.yml
                remote_dest_path = os.path.join(REMOTE_PROJECT_ROOT, item).replace("\\", "/")
                
                # Calcola la cartella genitore remota per creare la struttura se manca
                remote_parent_dir = os.path.dirname(remote_dest_path)
                
                print(f"[*] Copia di '{item}' -> '{remote_dest_path}'")
                
                # Crea la cartella remota (mkdir -p) prima di copiare
                ssh.exec_command(f"mkdir -p {remote_parent_dir}")
                
                # Esegue la copia (recursive=True gestisce automaticamente le cartelle come 'configs')
                scp.put(item, remote_path=remote_dest_path, recursive=True)
                
        print(f"\n[+] File trasferiti con successo in {REMOTE_PROJECT_ROOT}")
        
    except Exception as e:
        print(f"[-] Errore durante il trasferimento SSH/SCP: {e}")
        sys.exit(1)
    finally:
        ssh.close()

def main():
    # 1. Runnare build_topology.py
    topo_script = os.path.join("automation", "build_topology.py")
    run_script(topo_script)

    # 2. Runnare build_configs.py
    config_script = os.path.join("automation", "build_configs.py")
    run_script(config_script)

    # 3. Copiare file selettivi
    upload_selected_files()

    print("\n[ok] Deploy completato.")

if __name__ == "__main__":
    main()