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
    "topology",
    "configs",
    "teardown.sh",
    "bootstrap.sh",
    "Dockerfile.manager",
    os.path.join("automation", "manager.py"),
    os.path.join("automation", "generate_traffic.py"),
    os.path.join("automation", "optimizer_CE_PE.py"),
    os.path.join("automation", "optimizer_PE_GW.py"),
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
    """Cancella la cartella remota, la ricrea e copia i file specificati"""
    print(f"[*] Connessione a {REMOTE_USER}@{REMOTE_HOST}...")
    
    ssh = SSHClient()
    ssh.set_missing_host_key_policy(AutoAddPolicy())
    
    try:
        ssh.connect(REMOTE_HOST, username=REMOTE_USER, password=REMOTE_PASS)
        
        # --- PULIZIA RADICALE (Tabula Rasa) ---
        print(f"[*] Cancellazione totale di {REMOTE_PROJECT_ROOT}...")
        # Esegue rm -rf. È importante attendere che finisca prima di procedere.
        stdin, stdout, stderr = ssh.exec_command(f"rm -rf {REMOTE_PROJECT_ROOT}")
        exit_status = stdout.channel.recv_exit_status()
        
        if exit_status != 0:
            print(f"[-] Errore durante la cancellazione: {stderr.read().decode()}")
            # Non usciamo, proviamo comunque a ricreare e sovrascrivere
        
        print(f"[*] Ricreazione cartella root {REMOTE_PROJECT_ROOT}...")
        ssh.exec_command(f"mkdir -p {REMOTE_PROJECT_ROOT}")
        # --------------------------------------

        with SCPClient(ssh.get_transport()) as scp:
            for item in FILES_TO_TRANSFER:
                if not os.path.exists(item):
                    print(f"[!] Attenzione: Il file/cartella locale '{item}' non esiste. Salto.")
                    continue

                # Normalizza i percorsi per Linux (forward slash)
                item_linux = item.replace("\\", "/")
                
                # Calcola il percorso remoto di destinazione
                if os.path.isdir(item):
                    # Se è una cartella (es. "configs"), la destinazione è la root del progetto.
                    # SCP creerà "configs" dentro "ACN_bgp-automation/"
                    parent_dir = os.path.dirname(item_linux) 
                    remote_dest_path = os.path.join(REMOTE_PROJECT_ROOT, parent_dir).replace("\\", "/")
                else:
                    # Se è un file, percorso completo
                    remote_dest_path = os.path.join(REMOTE_PROJECT_ROOT, item_linux).replace("\\", "/")
                
                # Determina quale cartella padre creare sul remoto prima di copiare
                if os.path.isdir(item):
                    remote_parent_mkdir = remote_dest_path
                else:
                    remote_parent_mkdir = os.path.dirname(remote_dest_path)
                
                print(f"[*] Copia di '{item}' -> '{remote_dest_path}'")
                
                # Assicura che la sottocartella di destinazione esista
                ssh.exec_command(f"mkdir -p {remote_parent_mkdir}")
                
                scp.put(item, remote_path=remote_dest_path, recursive=True, preserve_times=True)
        
        # --- CAMBIO PERMESSI ---
        print(f"[*] Imposto i permessi (755) su {REMOTE_PROJECT_ROOT}...")
        stdin, stdout, stderr = ssh.exec_command(f"chmod -R 755 {REMOTE_PROJECT_ROOT}")
        
        # Attendiamo che il comando finisca e controlliamo errori
        if stdout.channel.recv_exit_status() == 0:
            print(f"[+] Permessi aggiornati con successo.")
        else:
            print(f"[-] Errore permessi: {stderr.read().decode()}")
        # ---------------------------------

        print(f"\n[+] Deploy completato con successo in {REMOTE_PROJECT_ROOT}")
        
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

    print("\n[ok] Script terminato.")

if __name__ == "__main__":
    main()