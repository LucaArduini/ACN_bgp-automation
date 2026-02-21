"""
Questo script automatizza l'installazione delle dipendenze Python necessarie al progetto.
Il file legge l'elenco dei pacchetti dal file 'requirements.txt' e utilizza pip per l'installazione.
"""

import subprocess
import sys
import os

def install_requirements():
    # Nome del file contenente l'elenco delle librerie esterne
    requirements_file = "requirements.txt"

    if not os.path.exists(requirements_file):
        print(f"[-] Errore: Il file '{requirements_file}' non è stato trovato nella directory corrente.")
        sys.exit(1)

    print(f"[*] Inizio installazione delle librerie da {requirements_file}...")
    
    try:
        # Esegue pip install utilizzando l'interprete Python corrente per coerenza
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", requirements_file])
        print("\n[+] Installazione completata con successo.")
        
    except subprocess.CalledProcessError as e:
        print(f"\n[-] Si è verificato un errore durante l'installazione.")
        sys.exit(1)

if __name__ == "__main__":
    install_requirements()