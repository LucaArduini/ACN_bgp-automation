import subprocess
import sys
import os

def install_requirements():
    requirements_file = "requirements.txt"

    # Controllo se il file esiste
    if not os.path.exists(requirements_file):
        print(f"[-] Errore: Il file '{requirements_file}' non è stato trovato nella directory corrente.")
        sys.exit(1)

    print(f"[*] Inizio installazione delle librerie da {requirements_file}...")
    
    try:
        # sys.executable assicura che pip venga lanciato per l'ambiente python corrente
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", requirements_file])
        print("\n[+] Installazione completata con successo.")
        
    except subprocess.CalledProcessError as e:
        print(f"\n[-] Si è verificato un errore durante l'installazione.")
        sys.exit(1)

if __name__ == "__main__":
    install_requirements()