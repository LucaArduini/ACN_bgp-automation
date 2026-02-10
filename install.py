import subprocess
import sys
import os

def is_venv():
    """Ritorna True se lo script è eseguito in un ambiente virtuale."""
    return (
        hasattr(sys, 'real_prefix') or
        (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix)
    )

def install_requirements():
    requirements_file = "requirements.txt"

    # 1. Controllo esistenza file
    if not os.path.exists(requirements_file):
        print(f"[-] Errore: Il file '{requirements_file}' non è stato trovato.")
        sys.exit(1)

    # 2. Controllo Virtual Environment (Best Practice)
    if not is_venv():
        print("-" * 60)
        print("[!] ATTENZIONE: Non sei in un ambiente virtuale (venv/conda).")
        print("[!] Si consiglia caldamente di usarne uno per evitare conflitti di librerie.")
        print("-" * 60)
        risposta = input("Vuoi procedere comunque con l'installazione globale? (s/n): ").lower()
        if risposta != 's':
            print("[*] Installazione annullata. Crea un venv con: python -m venv venv")
            sys.exit(0)

    print(f"[*] Inizio procedure di installazione...")

    try:
        # 3. Aggiornamento pip (previene errori con pacchetti scientifici pesanti)
        print("[*] Aggiornamento di pip in corso...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade", "pip"])

        # 4. Installazione requirements
        print(f"[*] Installazione delle librerie da {requirements_file}...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", requirements_file])
        
        print("\n[+] Configurazione completata con successo.")
        print("[+] Ora puoi avviare 'python manager.py'.")
        
    except subprocess.CalledProcessError as e:
        print(f"\n[-] Errore critico durante l'installazione (Codice: {e.returncode}).")
        sys.exit(1)

if __name__ == "__main__":
    install_requirements()