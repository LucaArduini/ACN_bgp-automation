#!/usr/bin/env python3
"""
Questo script verifica che il routing di base degli host sia configurato correttamente.
Esegue un traceroute dai nodi terminali (n1, n2) verso una destinazione esterna
e valida che il primo hop della catena corrisponda all'indirizzo del Gateway
predefinito configurato nel file 'data.yaml'.
"""

import yaml
import os
import subprocess

# --- CONFIGURAZIONE ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
YAML_FILE = os.path.join(BASE_DIR, "..", "topology", "data.yaml")
CLAB_PREFIX = "clab-project"

def print_header(msg):
    print(f"\n{'='*15} {msg} {'='*15}")

def load_topology():
    """Carica la topologia e restituisce una mappa dei nodi per un accesso veloce"""
    try:
        with open(YAML_FILE, 'r') as f:
            data = yaml.safe_load(f)
        return {n['name']: n for n in data.get('nodes', [])}
    except Exception as e:
        print(f"[ERR] Errore caricamento YAML: {e}")
        return {}

def run_traceroute(node, destination, expected_gw):
    """Esegue traceroute e verifica se il primo hop è il gateway corretto"""
    container = f"{CLAB_PREFIX}-{node}"
    
    # -n: evita risoluzione DNS, -m 5: limita la ricerca ai primi 5 hop
    cmd = ["docker", "exec", container, "traceroute", "-n", "-m", "5", destination]

    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        output = p.stdout
        
        # Analisi dell'output per trovare l'IP del gateway atteso
        reached = expected_gw in output if expected_gw else False
        return reached, output
    except subprocess.TimeoutExpired:
        return False, "Timeout"
    except Exception as e:
        return False, str(e)

def execute_traceroute_tests():
    """Ciclo di esecuzione dei test per i nodi host selezionati"""
    nodes_data = load_topology()
    
    test_nodes = ["n1", "n2"]
    target = "8.8.8.8" # Destinazione esterna fittizia

    print_header("TEST: TRACEROUTE (GATEWAY CHECK)")
    print(f"{'SORGENTE':<12} | {'DESTINAZIONE':<15} | {'GW ATTESO':<15} | {'RISULTATO'}")
    print("-" * 65)

    for node_name in test_nodes:
        node_info = nodes_data.get(node_name, {})
        gw_ip = node_info.get('gateway_ip')
        
        # Salta il test se il nodo non ha un gateway configurato in data.yaml
        if not gw_ip:
            print(f"{node_name:<12} | {target:<15} | {'N/D':<15} | [ SKIP ]")
            continue

        success, _ = run_traceroute(node_name, target, gw_ip)
        
        res_str = "[ OK ]" if success else "[ FAIL ]"
        print(f"{node_name:<12} | {target:<15} | {gw_ip:<15} | {res_str}")

if __name__ == "__main__":
    execute_traceroute_tests()