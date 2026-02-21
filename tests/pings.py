#!/usr/bin/env python3
"""
Questo script esegue test di connettività ICMP (Ping) end-to-end nella rete.
Verifica due scenari fondamentali:
1. Connettività dagli host interni verso i router esterni (Internet).
2. Connettività dai router esterni verso gli host, validando il percorso di ritorno.
Assicura che il piano dati sia operativo prima di procedere con l'automazione BGP.
"""

import yaml
import os
import subprocess

# --- CONFIGURAZIONE ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
YAML_FILE = os.path.join(BASE_DIR, "..", "topology", "data.yaml")
CLAB_PREFIX = "clab-project"

def print_header(msg):
    print(f"\n{'='*20} {msg} {'='*20}")

def load_topology():
    """Carica i dati della topologia una sola volta per ottimizzare i test"""
    try:
        with open(YAML_FILE, 'r') as f:
            data = yaml.safe_load(f)
        return {n['name']: n for n in data.get('nodes', [])}
    except Exception as e:
        print(f"[ERR] Errore caricamento YAML: {e}")
        return {}

def run_ping(node, destination, interface=None):
    """Esegue il comando ping all'interno del container Docker specificato"""
    container = f"{CLAB_PREFIX}-{node}"
    
    # -c 3: 3 pacchetti, -W 2: attende max 2 secondi per ogni risposta
    cmds = ["ping", "-c", "3", "-W", "2"]
    if interface:
        cmds.extend(["-I", interface]) # Forza l'interfaccia sorgente se specificata
    cmds.append(destination)

    full_cmd = ["docker", "exec", container] + cmds

    try:
        p = subprocess.run(full_cmd, capture_output=True, text=True, timeout=8)
        return p.returncode == 0 # True se il ping ha successo (exit code 0)
    except subprocess.TimeoutExpired:
        return False
    except Exception:
        return False

def test_connectivity():
    """Gestisce l'esecuzione dei test bidirezionali Host <-> Router"""
    nodes_data = load_topology()
    if not nodes_data:
        return
    
    nodes_from = ["n1", "n2"]
    nodes_to_check = ["r1", "r2", "r3"]

    # --- TEST 1: HOST -> ROUTER (Traffico in uscita) ---
    print_header("TEST: HOST -> ROUTER")
    header = f"{'DA (Node)':<12} | {'IP SORG':<15} | {'A (Router)':<12} | {'IP DEST':<15} | {'STATO'}"
    print(header)
    print("-" * len(header))

    for src in nodes_from:
        src_ip = nodes_data.get(src, {}).get('ipv4_address', "N/D").split('/')[0]
        for dst in nodes_to_check:
            ip_dst = nodes_data.get(dst, {}).get('ipv4_address', "").split('/')[0]
            if not ip_dst: continue
            
            success = run_ping(src, ip_dst)
            res_str = "[ OK ]" if success else "[ FAIL ]"
            print(f"{src:<12} | {src_ip:<15} | {dst:<12} | {ip_dst:<15} | {res_str}")

    # --- TEST 2: ROUTER -> HOST (Traffico di ritorno) ---
    print_header("TEST: ROUTER -> HOST (VIA INTERFACCIA)")
    header = f"{'DA (Router)':<12} | {'IP SORG (INT)':<15} | {'A (Node)':<12} | {'IP DEST':<15} | {'STATO'}"
    print(header)
    print("-" * len(header))

    for src in nodes_to_check:
        src_ip = nodes_data.get(src, {}).get('ipv4_address', "").split('/')[0]
        for dst in nodes_from:
            ip_dst = nodes_data.get(dst, {}).get('ipv4_address', "").split('/')[0]
            if not src_ip or not ip_dst: continue

            # Usa l'IP della Loopback del router come sorgente del ping
            success = run_ping(src, ip_dst, interface=src_ip)
            res_str = "[ OK ]" if success else "[ FAIL ]"
            print(f"{src:<12} | {src_ip:<15} | {dst:<12} | {ip_dst:<15} | {res_str}")

if __name__ == "__main__":
    test_connectivity()