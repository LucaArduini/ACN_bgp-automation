"""
Questo script funge da coordinatore principale per il deployment del progetto.
L'orchestrator automatizza l'intero workflow iniziale:
1. Esegue localmente gli script di generazione per la topologia e le configurazioni dei router.
2. Stabilisce una connessione SSH con il server remoto specificato nel file .env.
3. Sincronizza i file necessari tramite SCP, gestendo la pulizia del workspace remoto
   e la normalizzazione dei percorsi tra sistemi operativi diversi.
4. Imposta i permessi corretti sul server remoto per consentire l'esecuzione degli script di bootstrap.
"""

import os
import sys
import subprocess
from paramiko import SSHClient, AutoAddPolicy, RSAKey
from scp import SCPClient
from dotenv import load_dotenv

# Caricamento delle variabili d'ambiente per l'accesso remoto
load_dotenv()

REMOTE_HOST = os.getenv('REMOTE_HOST')
REMOTE_USER = os.getenv('REMOTE_USER')
REMOTE_PASS = os.getenv('REMOTE_PASS')

# Validazione delle credenziali necessarie al deployment
if not REMOTE_HOST:
    print("[-] Errore: La variabile REMOTE_HOST non è definita nel file .env")
    sys.exit(1)
    
if not REMOTE_USER:
    print("[-] Errore: La variabile REMOTE_USER non è definita nel file .env")
    sys.exit(1)

# Definizione della root del progetto sul server di destinazione
REMOTE_PROJECT_ROOT = f'/home/{REMOTE_USER}/ACN_bgp-automation' 

# Elenco dei file e delle directory essenziali da trasferire al server
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

def run_script(script_path):
    """Esegue uno script python locale per la generazione degli artefatti"""
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
    """Gestisce la sessione SSH e il trasferimento dei file tramite SCP"""
    print(f"[*] Connessione a {REMOTE_USER}@{REMOTE_HOST}...")
    
    ssh = SSHClient()
    ssh.set_missing_host_key_policy(AutoAddPolicy())
    
    try:
        ssh.connect(REMOTE_HOST, username=REMOTE_USER, password=REMOTE_PASS)
        
        # Pulizia della directory remota per garantire un deploy pulito
        print(f"[*] Cancellazione totale di {REMOTE_PROJECT_ROOT} (richiede sudo)...")
        # Usiamo 'sudo -S' per leggere la password da 'echo' ed eseguire il comando come root
        cmd_rm = f"echo '{REMOTE_PASS}' | sudo -S rm -rf {REMOTE_PROJECT_ROOT}"
        stdin, stdout, stderr = ssh.exec_command(cmd_rm)
        exit_status = stdout.channel.recv_exit_status()
        
        if exit_status != 0:
            print(f"[-] Errore durante la cancellazione: {stderr.read().decode()}")
        
        print(f"[*] Ricreazione cartella root {REMOTE_PROJECT_ROOT}...")
        ssh.exec_command(f"mkdir -p {REMOTE_PROJECT_ROOT}")

        # Trasferimento dei file tramite SCPClient
        with SCPClient(ssh.get_transport()) as scp:
            for item in FILES_TO_TRANSFER:
                if not os.path.exists(item):
                    print(f"[!] Attenzione: Il file/cartella locale '{item}' non esiste. Salto.")
                    continue

                # Normalizzazione dei separatori di percorso per ambiente Linux
                item_linux = item.replace("\\", "/")
                
                # Calcolo della destinazione remota mantenendo la struttura delle cartelle
                if os.path.isdir(item):
                    parent_dir = os.path.dirname(item_linux) 
                    remote_dest_path = os.path.join(REMOTE_PROJECT_ROOT, parent_dir).replace("\\", "/")
                else:
                    remote_dest_path = os.path.join(REMOTE_PROJECT_ROOT, item_linux).replace("\\", "/")
                
                # Creazione ricorsiva delle directory genitrici sul server remoto
                if os.path.isdir(item):
                    remote_parent_mkdir = remote_dest_path
                else:
                    remote_parent_mkdir = os.path.dirname(remote_dest_path)
                
                print(f"[*] Copia di '{item}' -> '{remote_dest_path}'")
                
                ssh.exec_command(f"mkdir -p {remote_parent_mkdir}")
                scp.put(item, remote_path=remote_dest_path, recursive=True, preserve_times=True)
        
        # Impostazione dei permessi di esecuzione per gli script shell trasferiti
        print(f"[*] Imposto i permessi (755) su {REMOTE_PROJECT_ROOT}...")
        cmd_chmod = f"echo '{REMOTE_PASS}' | sudo -S chmod -R 755 {REMOTE_PROJECT_ROOT}"
        stdin, stdout, stderr = ssh.exec_command(cmd_chmod)
        
        if stdout.channel.recv_exit_status() == 0:
            print(f"[+] Permessi aggiornati con successo.")
        else:
            print(f"[-] Errore permessi: {stderr.read().decode()}")
            
        # Per sicurezza, ci assicuriamo che l'utente 'student' sia il proprietario di tutto
        print(f"[*] Reimposto la proprietà dei file all'utente {REMOTE_USER}...")
        cmd_chown = f"echo '{REMOTE_PASS}' | sudo -S chown -R {REMOTE_USER}:{REMOTE_USER} {REMOTE_PROJECT_ROOT}"
        ssh.exec_command(cmd_chown)

        print(f"\n[+] Deploy completato con successo in {REMOTE_PROJECT_ROOT}")
        
    except Exception as e:
        print(f"[-] Errore durante il trasferimento SSH/SCP: {e}")
        sys.exit(1)
    finally:
        ssh.close()

def main():
    """Workflow principale: generazione locale -> deploy remoto"""
    
    # 1. Generazione file YAML di Containerlab a partire dai dati
    topo_script = os.path.join("automation", "build_topology.py")
    run_script(topo_script)

    # 2. Generazione delle configurazioni FRR tramite template Jinja2
    config_script = os.path.join("automation", "build_configs.py")
    run_script(config_script)

    # 3. Trasferimento degli artefatti sul server remoto
    upload_selected_files()

    print("\n[ok] Script terminato.")

if __name__ == "__main__":
    main()