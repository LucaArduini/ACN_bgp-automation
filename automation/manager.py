#!/usr/bin/env python3
"""
This script coordinates the entire AS65020 automation system.
The Manager orchestrates traffic generation, runs optimization 
algorithms to balance loads (Ingress and Egress), and applies 
BGP configurations to FRR routers in real time.
"""

import json
import os
import sys
import yaml
import numpy as np

from handle_traffic import set_med, set_local_pref

# Path configuration for local automation modules
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

import generate_traffic
import optimizer_CE_PE
import optimizer_PE_GW

# --- PATH CONFIGURATION ---
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
    """Retrieves the upstream link capacities defined in data.yaml"""
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

            print(f"{Colors.BLUE}[INFO] Capacities loaded from YAML: GW1={cap_gw1}, GW2={cap_gw2}{Colors.ENDC}")
    except Exception as e:
        print(f"{Colors.FAIL}[ERR] Error reading capacity: {e}{Colors.ENDC}")
    return cap_gw1, cap_gw2

def manage_pipeline():
    """Main Network Automation system pipeline"""

    # ---------------------------------------------------------
    # 1) Traffic Generation
    # ---------------------------------------------------------
    print_header("STEP 1: Traffic Generation")
    generate_traffic.generate_and_save_traffic_matrix()

    # ---------------------------------------------------------
    # 2) Data Acquisition
    # ---------------------------------------------------------
    print_header("STEP 2: Data Acquisition")
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
    # 3) Optimization 1 (CE -> PE)
    # ---------------------------------------------------------
    print_header("STEP 3: Optimization CE -> PE")
    ce_pe_vector = optimizer_CE_PE.optimize_pe_selection(input_matrix=raw_matrix)
    print(f"{Colors.BLUE}[DEBUG] 1D CE-PE Vector:{Colors.ENDC}\n{ce_pe_vector}\n")
    
    ce_pe_dec_matrix = ce_pe_vector.reshape((len(sources), len(destinations)))

    # Print CE -> PE optimization results
    print(f"{Colors.UNDERLINE}{'CE -> DESTINATION':<28} | {'ASSIGNED PE'}{Colors.ENDC}")
    for i, src in enumerate(sources):
        for j, dst in enumerate(destinations):
            if raw_matrix[i][j] > 0:
                choice = ce_pe_dec_matrix[i][j]
                pe_str = f"{Colors.GREEN}PE 1{Colors.ENDC}" if choice == 1 else f"{Colors.GREEN}PE 2{Colors.ENDC}"
                print(f"{src:<12} -> {dst:<12} | {pe_str}")

    # ---------------------------------------------------------
    # 4) BGP MED Configuration (Inbound TE for PEs)
    # ---------------------------------------------------------
    print_header("STEP 4: BGP MED Configuration (PE Selection)")
    default_med = 100
    seq_med = 10

    print(f"{Colors.UNDERLINE}{'CE (Flow Source)':<20} | {'DESTINATION':<14} | {'Node (PE)':<18} | {'MED'}{Colors.ENDC}")
    
    for i, src in enumerate(sources):
        for j, dst in enumerate(destinations):
            choice = int(ce_pe_dec_matrix[i][j])
            
            # If the optimizer returned 0, skip this source-destination pair
            if choice == 0:
                continue
            
            # Assign lower MED to the chosen PE (preferred) and higher to the other (backup)
            for pe_idx in [1, 2]:
                pe_name = f"pe{pe_idx}"
                
                if pe_idx == choice:
                    # Preferred (Low MED)
                    med_val = default_med
                    color = Colors.GREEN
                else:
                    # Backup (High MED)
                    med_val = default_med + 100
                    color = Colors.CYAN

                set_med(pe_name, src, med_val, dst, seq_med)
                seq_med += 10
                print(f"{src:<20} | {dst:<14} | {color}{pe_name:<18}{Colors.ENDC} | {med_val}")
            
            print("-" * 64)

    # ---------------------------------------------------------
    # 5) Load Aggregation
    # ---------------------------------------------------------
    print_header("STEP 5: Aggregated Load Matrix (PE -> DEST)")
    aggregated_matrix = np.zeros((2, len(destinations)))
    for i in range(len(sources)):
        for j in range(len(destinations)):
            vol = raw_matrix[i][j]
            choice = ce_pe_dec_matrix[i][j]
            if choice == 1: aggregated_matrix[0][j] += vol
            elif choice == 2: aggregated_matrix[1][j] += vol

    header_dst = " | ".join([f"{d:>8}" for d in destinations])
    print(f"{'PE / DEST':<12} | {header_dst}")
    print("-" * (15 + len(header_dst)))
    
    for idx, pe_name in enumerate(pes):
        row_vals = " | ".join([f"{val:>8.0f}" for val in aggregated_matrix[idx]])
        print(f"{pe_name:<12} | {row_vals}")

    # ---------------------------------------------------------
    # 6) Optimization 2 (PE -> GW)
    # ---------------------------------------------------------
    print_header("STEP 6: PE -> GW Optimization (Minimax Saturation)")
    cap_gw1, cap_gw2 = get_gw_capacities()
    
    pe_gw_vector = optimizer_PE_GW.optimize_gw_selection(cap_gw1, cap_gw2, input_matrix=aggregated_matrix)
    print(f"{Colors.BLUE}[DEBUG] 1D PE-GW Vector:{Colors.ENDC}\n{pe_gw_vector}\n")

    pe_gw_dec_matrix = pe_gw_vector.reshape((2, len(destinations)))

    # Print PE -> GW optimization results
    print(f"{Colors.UNDERLINE}{'PE -> DESTINATION':<26} | {'ASSIGNED GW'}{Colors.ENDC}")
    for i, pe_name in enumerate(pes):
        for j, dst in enumerate(destinations):
            if aggregated_matrix[i][j] > 0:
                gw_choice = pe_gw_dec_matrix[i][j]
                gw_str = f"{Colors.GREEN}GW 1{Colors.ENDC}" if gw_choice == 1 else f"{Colors.GREEN}GW 2{Colors.ENDC}"
                print(f"{pe_name:<10} -> {dst:<12} | {gw_str}")

    # ---------------------------------------------------------
    # 7) BGP Local Preference Configuration (Outbound TE)
    # ---------------------------------------------------------
    print_header("STEP 7: BGP Local Preference Configuration (GW Selection)")
    default_local_pref = 100
    seq_lp = 10

    print(f"{Colors.UNDERLINE}{'PE (Flow Source)':<20} | {'DESTINATION':<14} | {'Node (GW)':<18} | {'LOCAL PREF'}{Colors.ENDC}")

    for i, pe_name in enumerate(pes):
        for j, dst in enumerate(destinations):
            gw_choice = int(pe_gw_dec_matrix[i][j])
            
            # If the optimizer returned 0 for this PE-GW route, skip it
            if gw_choice == 0:
                continue
            
            # Assign higher LP to the chosen GW (preferred) and lower to the other (backup)
            for gw_idx in [1, 2]:
                gw_name = f"gw{gw_idx}"
                
                if gw_idx == gw_choice:
                    # Preferred (High Local Pref)
                    lp_val = default_local_pref + 100
                    color = Colors.GREEN
                else:
                    # Backup (Low Local Pref)
                    lp_val = default_local_pref
                    color = Colors.CYAN

                set_local_pref(pe_name, gw_name, lp_val, dst, seq_lp)
                        
                seq_lp += 10
                print(f"{pe_name:<20} | {dst:<14} | {color}{gw_name:<18}{Colors.ENDC} | {lp_val}")
            
            print("-" * 71)

    # ---------------------------------------------------------
    # 8) Final JSON Export
    # ---------------------------------------------------------
    print_header("STEP 8: End-to-End Paths Export")
    final_paths = []
    for i, src in enumerate(sources):
        for j, dst in enumerate(destinations):
            volume = raw_matrix[i][j]
            if volume > 0:
                pe_idx = int(ce_pe_dec_matrix[i][j]) - 1
                gw_idx = int(pe_gw_dec_matrix[pe_idx][j])
                final_paths.append({
                    "source": src, "destination": dst, "volume_mbps": float(volume),
                    "path": {"pe": pes[pe_idx], "gw": f"gw{gw_idx}"}
                })

    try:
        with open(FINAL_JSON, 'w') as f:
            json.dump(final_paths, f, indent=4)
        print(f"{Colors.GREEN}[OK] Final JSON saved: {FINAL_JSON}{Colors.ENDC}")
    except Exception as e:
        print(f"{Colors.FAIL}[ERR] {e}{Colors.ENDC}")

if __name__ == "__main__":
    manage_pipeline()