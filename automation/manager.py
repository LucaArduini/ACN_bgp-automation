#!/usr/bin/env python3
"""
Questo script coordina l'intero sistema di automazione dell'AS65020.
Il Manager orchestra la generazione del traffico, esegue gli algoritmi di 
ottimizzazione per bilanciare i carichi (Ingress ed Egress) e applica le 
configurazioni BGP ai router FRR in tempo reale.
"""

import json
import os
import sys
import yaml
import numpy as np

from handle_traffic import set_med, set_local_pref

# Configurazione dei path per i moduli locali di automazione
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
    """Recupera le capacità dei link di upstream definite in data.yaml"""
    cap_gw1, cap_gw2 = 100.0, 100.0
    try:
        if os.path.exists(YAML_FILE):
            with open(YAML_FILE, 'r') as f:
                data = yaml.safe_load(f)

                for link in data.get('links', []):
                    if 'capacity' in link:
                        capacity = float(link['capacity'])
                        if link.get('a') == 'gw1' or link.get('b') == 'gw1': cap_gw1 = capacity
                        if link.get('a') == 'gw2' or link.get('b') == 'gw2': cap_gw2 = capacity

            print(f"{Colors.BLUE}[INFO] Capacità caricate da YAML: GW1={cap_gw1}, GW2={cap_gw2}{Colors.ENDC}")
    except Exception as e:
        print(f"{Colors.FAIL}[ERR] Errore lettura capacità: {e}{Colors.ENDC}")
    return cap_gw1, cap_gw2

def manage_pipeline():
    """Pipeline principale del sistema di Network Automation"""

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

    # Stampa risultati ottimizzazione CE -> PE
    print(f"{Colors.UNDERLINE}{'CE -> DESTINAZIONE':<28} | {'PE ASSEGNATO'}{Colors.ENDC}")
    for i, src in enumerate(sources):
        for j, dst in enumerate(destinations):
            if raw_matrix[i][j] > 0:
                choice = dec_matrix_ce_pe[i][j]
                pe_str = f"{Colors.GREEN}PE 1{Colors.ENDC}" if choice == 1 else f"{Colors.GREEN}PE 2{Colors.ENDC}"
                print(f"{src:<12} -> {dst:<12} | {pe_str}")

    # ---------------------------------------------------------
    # 4) Configurazione BGP MED (Inbound TE per i PE)
    # ---------------------------------------------------------
    print_header("STEP 4: Configurazione BGP MED (Scelta PE)")
    default_med = 100
    seq_med = 10

    print(f"{Colors.UNDERLINE}{'CE (Origine Flusso)':<20} | {'DESTINAZIONE':<14} | {'Nodo (PE)':<18} | {'MED'}{Colors.ENDC}")
    
    for i, src in enumerate(sources):
        for j, dst in enumerate(destinations):
            choice = int(dec_matrix_ce_pe[i][j])
            
            # Se l'ottimizzatore ha restituito 0, saltiamo questa coppia sorgente-destinazione
            if choice == 0:
                continue
            
            # Assegniamo MED più basso al PE scelto (preferito) e più alto all'altro (backup)
            for pe_idx in [1, 2]:
                pe_name = f"pe{pe_idx}"
                
                if pe_idx == choice:
                    # È il prescelto
                    med_val = default_med
                    color = Colors.GREEN
                else:
                    # È il backup
                    med_val = default_med + 100
                    color = Colors.CYAN

                set_med(pe_name, src, med_val, dst, seq_med)
                seq_med += 10
                print(f"{src:<20} | {dst:<14} | {color}{pe_name:<18}{Colors.ENDC} | {med_val}")
            
            print("-" * 65)

    # ---------------------------------------------------------
    # 5) Aggregazione Carico
    # ---------------------------------------------------------
    print_header("STEP 5: Matrice di Carico Aggregata (PE -> DEST)")
    agg_matrix = np.zeros((2, len(destinations)))
    for i in range(len(sources)):
        for j in range(len(destinations)):
            vol = raw_matrix[i][j]
            choice = dec_matrix_ce_pe[i][j]
            if choice == 1: agg_matrix[0][j] += vol
            elif choice == 2: agg_matrix[1][j] += vol

    header_dst = " | ".join([f"{d:>8}" for d in destinations])
    print(f"{'PE / DEST':<12} | {header_dst}")
    print("-" * (15 + len(header_dst)))
    
    for idx, pe_name in enumerate(pes):
        row_vals = " | ".join([f"{val:>8.0f}" for val in agg_matrix[idx]])
        print(f"{pe_name:<12} | {row_vals}")

    # ---------------------------------------------------------
    # 6) Ottimizzazione 2 (PE -> GW)
    # ---------------------------------------------------------
    print_header("STEP 6: Ottimizzazione PE -> GW (Minimax Saturation)")
    cap_gw1, cap_gw2 = get_gw_capacities()
    
    vettore_pe_gw = optimizer_PE_GW.ottimizzazione_scelta_GW(cap_gw1, cap_gw2, matrice_input=agg_matrix)
    print(f"{Colors.BLUE}[DEBUG] Vettore PE-GW 1D:{Colors.ENDC}\n{vettore_pe_gw}\n")

    dec_matrix_pe_gw = vettore_pe_gw.reshape((2, len(destinations)))

    # Stampa risultati ottimizzazione PE -> GW
    print(f"{Colors.UNDERLINE}{'PE -> DESTINAZIONE':<26} | {'GW ASSEGNATO'}{Colors.ENDC}")
    for i, pe_name in enumerate(pes):
        for j, dst in enumerate(destinations):
            if agg_matrix[i][j] > 0:
                gw_choice = dec_matrix_pe_gw[i][j]
                gw_str = f"{Colors.GREEN}GW 1{Colors.ENDC}" if gw_choice == 1 else f"{Colors.GREEN}GW 2{Colors.ENDC}"
                print(f"{pe_name:<10} -> {dst:<12} | {gw_str}")

    # ---------------------------------------------------------
    # 7) Configurazione BGP Local Preference (Outbound TE)
    # ---------------------------------------------------------
    print_header("STEP 7: Configurazione BGP Local Preference (Scelta GW)")
    default_local_pref = 100
    seq_lp = 10

    print(f"{Colors.UNDERLINE}{'PE (Origine Flusso)':<20} | {'DESTINAZIONE':<14} | {'Nodo (GW)':<18} | {'LOCAL PREF'}{Colors.ENDC}")

    for i, pe_name in enumerate(pes):
        for j, dst in enumerate(destinations):
            gw_choice = int(dec_matrix_pe_gw[i][j])
            
            # Se l'ottimizzatore ha restituito 0 per questa rotta PE-GW, saltiamo
            if gw_choice == 0:
                continue
            
            # Assegniamo LP più basso al GW scelto (preferito) e più alto all'altro (backup)
            for gw_idx in [1, 2]:
                gw_name = f"gw{gw_idx}"
                
                if gw_idx == gw_choice:
                    # Preferito (Local Pref ALTA)
                    lp_val = default_local_pref + 100
                    color = Colors.GREEN
                else:
                    # Backup (Local Pref BASSA)
                    lp_val = default_local_pref
                    color = Colors.CYAN

                set_local_pref(pe_name, gw_name, lp_val, dst, seq_lp)
                        
                seq_lp += 10
                print(f"{pe_name:<20} | {dst:<14} | {color}{gw_name:<18}{Colors.ENDC} | {lp_val}")
            
            print("-" * 65)

    # ---------------------------------------------------------
    # 8) Esportazione JSON Finale
    # ---------------------------------------------------------
    print_header("STEP 8: Esportazione Percorsi End-to-End")
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