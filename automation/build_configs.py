"""
Questo script automatizza la generazione dei file di configurazione per i router FRR.
Il processo si articola in diverse fasi:
1. Caricamento dei dati astratti della rete dal file 'data.yaml'.
2. Analisi delle adiacenze per identificare i vicini BGP (iBGP ed eBGP).
3. Calcolo dei prefissi di rete da annunciare in base alle maschere di sottorete.
4. Rendering dei template Jinja2 ('config.j2') per produrre file .conf pronti 
   per essere caricati dai container FRR.
Include logiche specifiche per gestire il peering BGP sia su link punto-punto 
che attraverso segmenti LAN (bridge).
"""

import jinja2
import os
import yaml
import ipaddress
from jinja2 import Environment, FileSystemLoader

# Definizione dei percorsi per template, dati e output
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, "..", "templates")
TOPOLOGY_DIR = os.path.join(BASE_DIR, "..", "topology")
DATA_FILE = os.path.join(TOPOLOGY_DIR, "data.yaml")
OUTPUT_DIR = os.path.join(BASE_DIR, "..", "configs")

# Assicura l'esistenza della directory di output per le configurazioni
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Inizializzazione dell'ambiente Jinja2
environment = Environment(loader=FileSystemLoader(TEMPLATES_DIR), trim_blocks=True, lstrip_blocks=True)
template = environment.get_template("config.j2")

# Caricamento della topologia dal file YAML
with open(DATA_FILE, "r") as f:
    data = yaml.safe_load(f)

nodes = data['nodes']
links = data['links']
nodes_map = {n['name']: n for n in nodes}

def get_remote_ip(node_name, port_name):
    """Recupera l'indirizzo IP di un'interfaccia specifica su un nodo"""
    node = nodes_map.get(node_name)
    if node and 'interfaces' in node:
        for iface in node['interfaces']:
            if iface['name'] == port_name:
                return iface.get('ipv4_address')
    return None

def get_network_address(ip, mask):
    """Calcola l'indirizzo di rete dato IP e maschera"""
    try:
        interface = ipaddress.IPv4Interface(f"{ip}{mask}")
        return str(interface.network)
    except ValueError:
        return None

# Elaborazione di ogni nodo per generare la relativa configurazione
for node in nodes:

    # Salta gli host e i nodi senza interfacce (es. bridge)
    if node.get('role') == 'host' or 'interfaces' not in node:
        continue

    hostname = node['name']
    neighbors_dict = {}
    bgp_networks = set()
    
    local_asn = node['bgp']['asn'] if 'bgp' in node else None

    # Identificazione delle reti da annunciare via BGP
    if local_asn:
        for iface in node['interfaces']:
            mask = iface['ipv4_mask']
            if mask == '/24' or mask == '/32' or mask == '/28':
                net = get_network_address(iface['ipv4_address'], mask)
                if net: bgp_networks.add(net)

    # Identificazione dei vicini BGP tramite l'analisi dei link
    if local_asn:
        for link in links:
            if link['a'] == hostname:
                remote_name, remote_port = link['b'], link['b_port']
            elif link['b'] == hostname:
                remote_name, remote_port = link['a'], link['a_port']
            else:
                continue
            
            remote_node = nodes_map.get(remote_name)
            if not remote_node: continue

            # Peering su link punto-punto (Router-to-Router)
            if 'bgp' in remote_node:
                r_ip = get_remote_ip(remote_name, remote_port)
                if r_ip:
                    neighbors_dict[r_ip] = {
                        "ip": r_ip,
                        "remote_as": remote_node['bgp']['asn'],
                        "type": 'ibgp' if remote_node['bgp']['asn'] == local_asn else 'ebgp',
                        "description": f"Link_to_{remote_name}"
                    }
            
            # Peering attraverso bridge (Router-to-LAN-to-Router) per iBGP
            if remote_node.get('role') == 'bridge' or remote_node.get('kind') == 'bridge':
                for l in links:
                    p_name, p_port = ("", "")
                    if l['a'] == remote_name: p_name, p_port = l['b'], l['b_port']
                    elif l['b'] == remote_name: p_name, p_port = l['a'], l['a_port']
                    
                    if p_name and p_name != hostname:
                        p_node = nodes_map.get(p_name)
                        if p_node and 'bgp' in p_node and p_node['bgp']['asn'] == local_asn:
                            p_ip = get_remote_ip(p_name, p_port)
                            if p_ip:
                                neighbors_dict[p_ip] = {
                                    "ip": p_ip,
                                    "remote_as": local_asn,
                                    "type": 'ibgp',
                                    "description": f"iBGP_via_{remote_name}"
                                }

    # Rendering finale del file di configurazione
    config = template.render(
        device=node,
        interfaces=node['interfaces'],
        neighbors=list(neighbors_dict.values()),
        networks=list(bgp_networks)
    )
    
    # Scrittura del file .conf su disco
    with open(os.path.join(OUTPUT_DIR, f"{hostname}.conf"), "w", newline='\n') as f:
        f.write(config)
    print(f"Generata config per {hostname}")