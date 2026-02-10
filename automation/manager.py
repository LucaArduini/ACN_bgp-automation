#!/usr/bin/env python3
import json
import os
import sys
import yaml
import numpy as np

# Impostiamo il path per trovare i moduli locali
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

import generate_traffic
import optimizer_CE_PE
import optimizer_PE_GW

# --- CONFIGURAZIONE PERCORSI ---
YAML_FILE = os.path.join(current_dir, "..", "topology", "data.yaml")
TRAFFIC_JSON = os.path.join(current_dir, "traffic_matrix.json")
FINAL_JSON = os.path.join(current_dir, "final_routing_paths.json")

class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def print_header(msg):
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*10} {msg} {'='*10}{Colors.ENDC}")

def get_gw_capacities():
    """Estrae le capacità dei gateway dal file topology/data.yaml"""
    cap_gw1, cap_gw2 = 100.0, 100.0
    try:
        if os.path.exists(YAML_FILE):
            with open(YAML_FILE, 'r') as f:
                data = yaml.safe_load(f)
                for node in data.get('nodes', []):
                    if node.get('name') == 'gw1': cap_gw1 = float(node.get('capacity', 100))
                    if node.get('name') == 'gw2': cap_gw2 = float(node.get('capacity', 100))
            print(f"{Colors.BLUE}[INFO] Capacità caricate da YAML: GW1={cap_gw1}M, GW2={cap_gw2}M{Colors.ENDC}")
    except Exception as e:
        print(f"{Colors.FAIL}[ERR] Errore lettura capacità: {e}{Colors.ENDC}")
    return cap_gw1, cap_gw2

def manage_pipeline():
    # ---------------------------------------------------------
    # 1) Generazione Traffico
    # ---------------------------------------------------------
    print_header("STEP 1: Generazione Traffico")
    generate_traffic.generate_and_save_traffic_matrix()

    # ---------------------------------------------------------
    # 2) Acquisizione Dati
    # ---------------------------------------------------------
    print_header("STEP 2: Acquisizione Dati")
    try:
        with open(TRAFFIC_JSON, 'r') as f:
            data = json.load(f)
        sources = data["topology_summary"]["source_routers"]
        pes = data["topology_summary"]["pe_routers"]
        destinations = data["topology_summary"]["destinations_routers"]
        raw_matrix = np.array(data["traffic_matrix_raw"])
    except Exception as e:
        print(f"{Colors.FAIL}[ERR] {e}{Colors.ENDC}"); return

    # ---------------------------------------------------------
    # 3) Ottimizzazione 1 (CE -> PE)
    # ---------------------------------------------------------
    print_header("STEP 3: Ottimizzazione CE -> PE")
    vettore_ce_pe = optimizer_CE_PE.ottimizzazione_scelta_PE(matrice_input=raw_matrix)
    
    print(f"{Colors.BLUE}[DEBUG] Vettore CE-PE 1D:{Colors.ENDC}\n{vettore_ce_pe}\n")
    
    dec_matrix_ce_pe = vettore_ce_pe.reshape((len(sources), len(destinations)))

    # NUOVA STAMPA: Tabella riassuntiva scelte PE
    print(f"{Colors.UNDERLINE}{'CE -> DESTINAZIONE':<28} | {'PE ASSEGNATO'}{Colors.ENDC}")
    for i, src in enumerate(sources):
        for j, dst in enumerate(destinations):
            if raw_matrix[i][j] > 0: # Solo flussi attivi
                choice = dec_matrix_ce_pe[i][j]
                pe_str = f"{Colors.CYAN}PE 1{Colors.ENDC}" if choice == 1 else f"{Colors.GREEN}PE 2{Colors.ENDC}"
                print(f"{src:<12} -> {dst:<12} | {pe_str}")

    # ---------------------------------------------------------
    # 4) Aggregazione Carico
    # ---------------------------------------------------------
    print_header("STEP 4: Matrice di Carico Aggregata (PE -> DEST)")
    agg_matrix = np.zeros((2, len(destinations)))
    for i in range(len(sources)):
        for j in range(len(destinations)):
            vol = raw_matrix[i][j]
            choice = dec_matrix_ce_pe[i][j]
            if choice == 1: agg_matrix[0][j] += vol
            elif choice == 2: agg_matrix[1][j] += vol

    # NUOVA STAMPA: Visualizzazione Matrice Aggregata
    header_dst = " | ".join([f"{d:>8}" for d in destinations])
    print(f"{'PE / DEST':<12} | {header_dst}")
    print("-" * (15 + len(header_dst)))
    for idx, pe_name in enumerate(pes):
        row_vals = " | ".join([f"{val:>8.0f}" for val in agg_matrix[idx]])
        color = Colors.CYAN if idx == 0 else Colors.GREEN
        print(f"{color}{pe_name:<12}{Colors.ENDC} | {row_vals}")

    # ---------------------------------------------------------
    # 5) Ottimizzazione 2 (PE -> GW)
    # ---------------------------------------------------------
    print_header("STEP 5: Ottimizzazione PE -> GW (Minimax Saturation)")
    cap_gw1, cap_gw2 = get_gw_capacities()
    
    vettore_pe_gw = optimizer_PE_GW.ottimizzazione_scelta_GW(cap_gw1, cap_gw2, matrice_input=agg_matrix)
    print(f"{Colors.BLUE}[DEBUG] Vettore PE-GW 1D:{Colors.ENDC}\n{vettore_pe_gw}\n")

    dec_matrix_pe_gw = vettore_pe_gw.reshape((2, len(destinations)))

    print(f"{Colors.UNDERLINE}{'PE -> DESTINAZIONE':<26} | {'GW ASSEGNATO'}{Colors.ENDC}")
    for i, pe_name in enumerate(pes):
        for j, dst in enumerate(destinations):
            if agg_matrix[i][j] > 0:
                gw_choice = dec_matrix_pe_gw[i][j]
                gw_str = f"{Colors.CYAN}GW 1{Colors.ENDC}" if gw_choice == 1 else f"{Colors.GREEN}GW 2{Colors.ENDC}"
                print(f"{pe_name:<10} -> {dst:<12} | {gw_str}")

    # ---------------------------------------------------------
    # 6) Esportazione JSON Finale
    # ---------------------------------------------------------
    print_header("STEP 6: Esportazione Percorsi End-to-End")
    final_paths = []
    for i, src in enumerate(sources):
        for j, dst in enumerate(destinations):
            volume = raw_matrix[i][j]
            if volume > 0:
                pe_idx = int(dec_matrix_ce_pe[i][j]) - 1
                gw_idx = int(dec_matrix_pe_gw[pe_idx][j])
                final_paths.append({
                    "source": src, "destination": dst, "volume_mbps": float(volume),
                    "path": {"pe": pes[pe_idx], "gw": f"gw{gw_idx}"}
                })

    try:
        with open(FINAL_JSON, 'w') as f:
            json.dump(final_paths, f, indent=4)
        print(f"{Colors.GREEN}[OK] JSON finale salvato: {FINAL_JSON}{Colors.ENDC}")
    except Exception as e:
        print(f"{Colors.FAIL}[ERR] {e}{Colors.ENDC}")

if __name__ == "__main__":
    manage_pipeline()