import json
import os
import sys
import numpy as np  # Necessario per il reshape

# Impostiamo il path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

import generate_traffic
import optimizer

# --- CLASSE PER I COLORI ---
class Colors:
    HEADER = '\033[95m'  # Viola
    BLUE = '\033[94m'    # Blu
    CYAN = '\033[96m'    # Ciano
    GREEN = '\033[92m'   # Verde
    WARNING = '\033[93m' # Giallo
    FAIL = '\033[91m'    # Rosso
    ENDC = '\033[0m'     # Reset
    BOLD = '\033[1m'     # Grassetto
    UNDERLINE = '\033[4m'

def print_header(msg):
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*10} {msg} {'='*10}{Colors.ENDC}")

def manage_pipeline():
    # ---------------------------------------------------------
    # 1) Generazione Traffico
    # ---------------------------------------------------------
    print_header("STEP 1: Generazione Traffico")
    generate_traffic.generate_and_save_traffic_matrix()
    print(f"{Colors.GREEN}[OK] Matrice generata e salvata.{Colors.ENDC}")
    
    # ---------------------------------------------------------
    # 2) Lettura JSON e Topology Discovery
    # ---------------------------------------------------------
    print_header("STEP 2: Acquisizione Dati")
    json_path = os.path.join(current_dir, "traffic_matrix.json")
    
    try:
        with open(json_path, 'r') as f:
            data = json.load(f)
            
        topology = data.get("topology_summary", {})
        sources = topology.get("source_routers", [])
        destinations = topology.get("destinations_routers", [])
        
        # Estraiamo la matrice grezza
        raw_matrix = np.array(data.get("traffic_matrix_raw"))
        
        print(f" -> File JSON:   {Colors.CYAN}{json_path}{Colors.ENDC}")
        print(f" -> Sorgenti:    {Colors.BOLD}{len(sources)}{Colors.ENDC} {sources}")
        print(f" -> Destinazioni:{Colors.BOLD}{len(destinations)}{Colors.ENDC} {destinations}")
        
    except Exception as e:
        print(f"{Colors.FAIL}[ERR] Errore nella lettura del JSON: {e}{Colors.ENDC}")
        return

    # ---------------------------------------------------------
    # 3) Ottimizzazione
    # ---------------------------------------------------------
    print_header("STEP 3: Ottimizzazione e Assegnazione PE")
    
    if raw_matrix is not None:
        # Calcolo
        vettore_ottimo = optimizer.ottimizzazione_scelta_PE(matrice_input=raw_matrix)
        
        # --- MIGLIORIA VISIVA: TABELLA DEI FLUSSI ---
        # Il vettore è 1D, ma noi sappiamo che corrisponde a (Sources x Destinations).
        # Lo "ricostruiamo" in forma di matrice per abbinarlo ai nomi dei router.
        
        num_src = len(sources)
        num_dst = len(destinations)
        
        # Reshape del vettore 1D in matrice 2D (uguale alla matrice di traffico)
        decision_matrix = vettore_ottimo.reshape((num_src, num_dst))
        
        print(f"{Colors.UNDERLINE}{'FLUSSO (Sorg -> Dest)':<28} | {'TRAFFICO':<10} | {'PE ASSEGNATO'}{Colors.ENDC}")
        
        total_pe1 = 0
        total_pe2 = 0
        
        for i, src in enumerate(sources):
            for j, dst in enumerate(destinations):
                traffic_vol = raw_matrix[i][j]
                pe_choice = decision_matrix[i][j] # 0, 1, o 2
                
                if traffic_vol > 0:
                    # Colora la scelta del PE
                    if pe_choice == 1:
                        pe_str = f"{Colors.CYAN}PE 1{Colors.ENDC}"
                        total_pe1 += traffic_vol
                    elif pe_choice == 2:
                        pe_str = f"{Colors.GREEN}PE 2{Colors.ENDC}"
                        total_pe2 += traffic_vol
                    else:
                        pe_str = f"{Colors.FAIL}ERR{Colors.ENDC}"

                    print(f"{src:<12} -> {dst:<12} | {traffic_vol:>4.0f} Mbps  | {pe_str}")
        
        # --- RIEPILOGO FINALE ---
        print("\n" + "-"*50)
        print(f"{Colors.BOLD}STATISTICHE DI BILANCIAMENTO:{Colors.ENDC}")
        print(f"Carico Totale su {Colors.CYAN}PE 1{Colors.ENDC}: {total_pe1} Mbps")
        print(f"Carico Totale su {Colors.GREEN}PE 2{Colors.ENDC}: {total_pe2} Mbps")
        
        diff = abs(total_pe1 - total_pe2)
        print(f"Sbilanciamento:      {Colors.WARNING}{diff} Mbps{Colors.ENDC}")
        
    else:
        print(f"{Colors.FAIL}[ERR] Matrice non trovata.{Colors.ENDC}")

if __name__ == "__main__":
    manage_pipeline()