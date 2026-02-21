"""
Questo script genera il file di orchestrazione 'network.clab.yml' per Containerlab.
Oltre alla generazione del file tramite Jinja2, lo script include un motore di 
validazione dei dati che previene errori comuni di configurazione di rete:
1. Rileva collisioni di indirizzi IP (IP duplicati).
2. Verifica la coerenza delle sottoreti sui link (entrambi gli endpoint sulla stessa rete).
3. Controlla che le maschere di sottorete siano sufficientemente ampie per ospitare i nodi.
Se la validazione fallisce, la generazione viene interrotta per evitare deploy errati.
"""

import jinja2
import os
import yaml
import sys
import ipaddress
from jinja2 import Environment, FileSystemLoader

def validate_data(data):
    """
    Esegue controlli di integrità sui dati della topologia:
    1. Nessun IP duplicato nella rete.
    2. Coerenza delle subnet sui link (stessa rete, maschera valida).
    """
    print("--- Avvio Validazione Dati ---")
    errors = []
    
    seen_ips = {}
    interface_map = {}

    # 1. CONTROLLO DUPLICATI E POPOLAZIONE MAPPE
    for node in data['nodes']:
        if 'ipv4_address' in node and node.get('role') != 'host': 
            pass 

        if 'interfaces' in node:
            for iface in node['interfaces']:
                if 'ipv4_address' not in iface or 'ipv4_mask' not in iface:
                    continue
                
                ip_str = iface['ipv4_address']
                mask_str = iface['ipv4_mask']
                full_addr = f"{ip_str}{mask_str}"

                # Rilevamento di indirizzi IP assegnati a più interfacce
                if ip_str in seen_ips:
                    prev_node, prev_iface = seen_ips[ip_str]
                    errors.append(f"[DUPLICATE IP] L'indirizzo {ip_str} è usato sia su {prev_node}:{prev_iface} che su {node['name']}:{iface['name']}")
                else:
                    seen_ips[ip_str] = (node['name'], iface['name'])

                # Validazione formale dell'indirizzo IPv4
                try:
                    if_obj = ipaddress.ip_interface(full_addr)
                    key = f"{node['name']}:{iface['name']}"
                    interface_map[key] = if_obj
                except ValueError as e:
                    errors.append(f"[INVALID IP] {node['name']}:{iface['name']} ha un IP non valido: {full_addr}. Errore: {e}")

    # 2. CONTROLLO COERENZA DEI LINK
    for link in data['links']:
        endpoint_a = f"{link['a']}:{link['a_port']}"
        endpoint_b = f"{link['b']}:{link['b_port']}"

        if endpoint_a in interface_map and endpoint_b in interface_map:
            ip_a = interface_map[endpoint_a]
            ip_b = interface_map[endpoint_b]

            # Verifica che entrambi i lati del link appartengano alla stessa sottorete
            if ip_a.network != ip_b.network:
                errors.append(f"[SUBNET MISMATCH] Link tra {endpoint_a} e {endpoint_b}: Le subnet non coincidono ({ip_a.network} vs {ip_b.network})")

            # Verifica che la maschera permetta almeno 2 host (punto-punto)
            if ip_a.network.num_addresses < 2:
                 errors.append(f"[MASK TOO SMALL] Link tra {endpoint_a} e {endpoint_b}: La maschera {ip_a.with_netmask} è troppo piccola")

    # Gestione esito validazione
    if errors:
        print("!!! TROVATI ERRORI CRITICI NEI DATI !!!")
        for e in errors:
            print(f" - {e}")
        print("Generazione interrotta.")
        sys.exit(1)
    else:
        print("Validazione superata: Nessun duplicato e subnet coerenti.")

# --- MAIN SCRIPT ---

# Configurazione percorsi e setup ambiente Jinja2
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, "..", "templates")
TOPOLOGY_DIR = os.path.join(BASE_DIR, "..", "topology")

data_path = os.path.join(TOPOLOGY_DIR, "data.yaml")
output_path = os.path.join(TOPOLOGY_DIR, "network.clab.yml")

# Setup del motore Jinja2
environment = Environment(
    loader=FileSystemLoader(TEMPLATES_DIR),
    trim_blocks=True,
    lstrip_blocks=True
)
template = environment.get_template("topology.j2")

# Lettura del file dei dati sorgente
with open(data_path, 'r') as f:
    data = yaml.safe_load(f)

# Validazione dei dati prima della generazione della topologia
validate_data(data)

# Rendering del file YAML per Containerlab
content = template.render(nodes=data['nodes'], links=data['links'])
with open(output_path, 'w', newline='\n') as f:
    f.write(content)

print("Container lab network yaml file generated!")