import yaml
import json
import random
import os
import sys
from datetime import datetime

# --- CONFIGURAZIONE PERCORSI ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
YAML_FILE = os.path.join(BASE_DIR, "..", "topology", "data.yaml")
JSON_FILE = os.path.join(BASE_DIR, "traffic_prediction.json")

# Capacità ipotetica di un singolo link di upstream (es. 1 Gigabit)
LINK_CAPACITY_MBPS = 1000


def load_topology_data():
    """Legge il file YAML e identifica le sorgenti/destinazioni logiche"""
    if not os.path.exists(YAML_FILE):
        print(f"[ERR] File non trovato: {YAML_FILE}")
        sys.exit(1)

    try:
        with open(YAML_FILE, "r") as f:
            data = yaml.safe_load(f)
    except Exception as e:
        print(f"[ERR] Errore parsing YAML: {e}")
        sys.exit(1)

    # Identifichiamo i nodi rilevanti: CE (Clienti) e INTERNET (R3/Upstream)
    nodes = []
    
    # Cerchiamo i CE nel file YAML
    if 'nodes' in data:
        for n in data['nodes']:
            if n.get('role') == 'ce':
                nodes.append(n['name'])
    
    # Aggiungiamo esplicitamente "INTERNET" che rappresenta il mondo esterno
    nodes.append("INTERNET")
    
    return nodes


def generate_random_matrix(nodes):
    """
    Genera una matrice di traffico NxN dove N sono i nodi (CE + Internet).
    Le celle rappresentano il volume di traffico in Mbps.
    """
    size = len(nodes)
    matrix = [[0] * size for _ in range(size)]

    # Decidiamo casualmente uno scenario di carico
    scenario = random.choice(["NORMAL", "HIGH_DOWNLOAD", "HIGH_UPLOAD"])
    
    print(f"\n--- Generazione Scenario: {scenario} ---")

    for i, src in enumerate(nodes):
        for j, dst in enumerate(nodes):
            
            # Regola 1: Diagonale vuota (nessun traffico verso se stessi)
            if i == j:
                matrix[i][j] = 0
                continue
            
            # Logica di generazione basata sullo scenario
            volume = 0
            
            # Caso A: Traffico TRA Clienti (CE -> CE)
            # Solitamente basso o nullo in questi scenari, ma mettiamo un valore residuo
            if src != "INTERNET" and dst != "INTERNET":
                volume = random.randint(0, 50) 
            
            # Caso B: UPLOAD (CE -> INTERNET)
            elif src != "INTERNET" and dst == "INTERNET":
                if scenario == "HIGH_UPLOAD":
                    volume = random.randint(600, 900) # Saturazione possibile
                else:
                    volume = random.randint(50, 200)  # Normale
            
            # Caso C: DOWNLOAD (INTERNET -> CE)
            elif src == "INTERNET" and dst != "INTERNET":
                if scenario == "HIGH_DOWNLOAD":
                    volume = random.randint(700, 1100) # Saturazione molto probabile
                else:
                    volume = random.randint(300, 600)  # Normale
            
            matrix[i][j] = volume

    return matrix, scenario


def print_matrix(nodes, matrix):
    """Stampa la matrice in formato leggibile"""
    
    # Intestazione Colonne
    header = f"{'Sorgente \\ Destinazione':<25} | " + " | ".join([f"{n:>10}" for n in nodes])
    separator = "-" * len(header)
    
    print("\n" + separator)
    print(header)
    print(separator)
    
    # Righe
    for i, src in enumerate(nodes):
        row_str = f"{src:<25} | "
        for val in matrix[i]:
            # Formattazione condizionale per evidenziare valori alti
            val_str = f"{val:>10}"
            row_str += val_str + " | "
        print(row_str)
        
    print(separator)
    print("\nLEGENDA:")
    print(" - Cella [i][j] = Traffico in Mbps generato da riga 'i' diretto verso colonna 'j'.")
    print(f" - Capacità Link Upstream (Riferimento): {LINK_CAPACITY_MBPS} Mbps.")
    print(" - Esempio: Se riga 'INTERNET' e colonna 'ce1' ha valore 800, significa 800 Mbps in Download per CE1.")


def save_to_json(nodes, matrix, scenario):
    """Salva la matrice e i metadati in un file JSON"""
    
    # Trasformiamo la matrice in una lista di flussi più facile da parsare per il Manager
    flows = []
    for i, src in enumerate(nodes):
        for j, dst in enumerate(nodes):
            if matrix[i][j] > 0:
                flows.append({
                    "src": src,
                    "dst": dst,
                    "volume_mbps": matrix[i][j]
                })

    data = {
        "timestamp": datetime.now().isoformat(),
        "scenario": scenario,
        "link_capacity_mbps": LINK_CAPACITY_MBPS,
        "nodes": nodes,
        "matrix_raw": matrix, # Salviamo anche la matrice grezza per debug
        "traffic_flows": flows # Lista pulita per il Manager
    }

    try:
        with open(JSON_FILE, "w") as f:
            json.dump(data, f, indent=4)
        print(f"\n[OK] Dati salvati correttamente in: {JSON_FILE}")
    except Exception as e:
        print(f"\n[ERR] Errore salvataggio JSON: {e}")



def main():
    # 1. Carica Topologia
    nodes = load_topology_data()
    
    # 2. Genera Matrice
    matrix, scenario = generate_random_matrix(nodes)
    
    # 3. Visualizza
    print_matrix(nodes, matrix)
    
    # 4. Salva
    save_to_json(nodes, matrix, scenario)

if __name__ == "__main__":
    main()