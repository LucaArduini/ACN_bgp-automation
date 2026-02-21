#!/usr/bin/env python3
"""
Questo script valida l'efficacia delle policy di Traffic Engineering applicate dal Manager.
Esegue dei traceroute dai nodi sorgente verso le destinazioni e confronta gli hop reali
rilevati con il percorso atteso (PE e GW) definito nel file 'final_routing_paths.json'.
È lo strumento principale per verificare che le modifiche BGP abbiano effettivamente 
cambiato l'instradamento dei flussi.
"""

import yaml
import os
import subprocess
import json
import sys

# --- CONFIGURAZIONE PERCORSI ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
YAML_FILE = os.path.join(BASE_DIR, "..", "topology", "data.yaml")
JSON_FILE = os.path.join(BASE_DIR, "..", "automation", "final_routing_paths.json")
CLAB_PREFIX = "clab-project"

def print_header(msg):
    print(f"\n{'='*20} {msg} {'='*20}")

def load_data():
    """Carica la topologia di rete e i flussi ottimizzati dal Manager"""
    if not os.path.exists(JSON_FILE):
        print(f"[ERR] File '{os.path.basename(JSON_FILE)}' non trovato.")
        print(f"[TIP] Esegui prima 'manager.py' per generare i percorsi, poi riprova.")
        sys.exit(1)

    try:
        with open(YAML_FILE, 'r') as f:
            topo = yaml.safe_load(f)
        with open(JSON_FILE, 'r') as f:
            flows = json.load(f)
        return topo, flows
    except Exception as e:
        print(f"[ERR] Errore durante il caricamento dei dati: {e}")
        sys.exit(1)

def get_node_ip(nodes, node_name):
    """Restituisce l'indirizzo IP di una specifica destinazione"""
    for n in nodes:
        if n['name'] == node_name:
            return str(n.get('ipv4_address', '')).split('/')[0]
    return None

def get_link_ip(topo, node_a, node_b):
    """
    Trova l'IP dell'interfaccia di node_b che guarda verso node_a.
    Questa funzione è critica poiché il traceroute mostra l'IP dell'interfaccia 
    di ingresso del router successivo (hop).
    """
    links = topo.get('links', [])
    nodes = topo.get('nodes', [])
    
    remote_port = None
    potential_a = [node_a, "lan"] 

    # Cerca il collegamento diretto o via LAN tra i due nodi
    for link in links:
        if link['a'] in potential_a and link['b'] == node_b:
            remote_port = link['b_port']
        elif link['b'] in potential_a and link['a'] == node_b:
            remote_port = link['a_port']
        if remote_port: break
            
    if not remote_port: return None

    # Recupera l'IP configurato sulla porta identificata
    for node in nodes:
        if node['name'] == node_b:
            for interface in node.get('interfaces', []):
                if interface['name'] == remote_port:
                    return str(interface['ipv4_address']).split('/')[0]
    return None

def run_traceroute(source_node, destination_ip):
    """Esegue traceroute all'interno del container sorgente e cattura l'output"""
    # Mappa il ruolo logico (ce) al container fisico (n)
    container_name = source_node.replace("ce", "n")
    full_container = f"{CLAB_PREFIX}-{container_name}"
    
    # -n: evita risoluzione DNS (veloce), -w 1: timeout breve per test reattivi
    cmd = ["docker", "exec", full_container, "traceroute", "-n", "-w", "1", "-m", "10", destination_ip]
    
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
        return p.stdout
    except Exception:
        return ""

def verify_traffic_engineering():
    """Confronta i percorsi reali rilevati con quelli calcolati dall'ottimizzatore"""
    topo_data, flows = load_data()
    nodes = topo_data.get('nodes', [])

    print_header("VERIFICA TRAFFIC ENGINEERING")
    
    header = f"{'SORGENTE':<10} | {'DEST':<10} | {'PERCORSO ATTESO':<22} | {'STATO'}"
    print(header)
    print("-" * len(header))

    for flow in flows:
        src = flow['source']
        dst = flow['destination']
        exp_pe = flow['path']['pe']
        exp_gw = flow['path']['gw']

        # 1. Recupero IP del router di destinazione finale
        dst_ip = get_node_ip(nodes, dst)
        if not dst_ip:
            print(f"{src:<10} | {dst:<10} | {'IP non trovato':<22} | [SKIP]")
            continue

        # 2. Analisi del percorso reale tramite traceroute
        output = run_traceroute(src, dst_ip)

        # 3. Identificazione degli IP che dovrebbero apparire come hop
        # IP del PE visto dal CE
        pe_hop_ip = get_link_ip(topo_data, src, exp_pe)
        # IP del GW visto dal PE
        gw_hop_ip = get_link_ip(topo_data, exp_pe, exp_gw)

        # Verifica se gli IP attesi sono presenti nella sequenza degli hop del traceroute
        pe_found = pe_hop_ip in output if pe_hop_ip else False
        gw_found = gw_hop_ip in output if gw_hop_ip else False

        # 4. Determinazione del risultato del test
        if pe_found and gw_found:
            status = "[ OK ]"
        else:
            errors = []
            if not pe_found: errors.append(f"No {exp_pe}")
            if not gw_found: errors.append(f"No {exp_gw}")
            status = f"[FAIL: {', '.join(errors)}]"

        path_str = f"{exp_pe} -> {exp_gw}"
        print(f"{src:<10} | {dst:<10} | {path_str:<22} | {status}")

        # Messaggi di debug per investigare eventuali fallimenti (percorsi non aggiornati)
        if not (pe_found and gw_found):
            print(f"   > IP attesi: PE={pe_hop_ip}, GW={gw_hop_ip}")

if __name__ == "__main__":
    verify_traffic_engineering()