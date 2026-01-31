import jinja2
import os
import yaml
import ipaddress
from jinja2 import Environment, FileSystemLoader

# --- Setup Paths & Jinja Environment ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, "..", "templates")
TOPOLOGY_DIR = os.path.join(BASE_DIR, "..", "topology")
DATA_FILE = os.path.join(TOPOLOGY_DIR, "data.yaml")
OUTPUT_DIR = os.path.join(BASE_DIR, "..", "configs")

os.makedirs(OUTPUT_DIR, exist_ok=True)

environment = Environment(loader=FileSystemLoader(TEMPLATES_DIR), trim_blocks=True, lstrip_blocks=True)
template = environment.get_template("config.j2")

# --- Load Topology Data ---
with open(DATA_FILE, "r") as f:
    data = yaml.safe_load(f)

nodes = data['nodes']
links = data['links']
nodes_map = {n['name']: n for n in nodes}

def get_remote_ip(node_name, port_name):
    """Helper: recupera l'IP configurato su una specifica interfaccia."""
    node = nodes_map.get(node_name)
    if node and 'interfaces' in node:
        for iface in node['interfaces']:
            if iface['name'] == port_name:
                return iface.get('ipv4_address')
    return None

def get_network_address(ip, mask):
    """Helper: calcola l'indirizzo di rete per il comando 'network' BGP."""
    try:
        interface = ipaddress.IPv4Interface(f"{ip}{mask}")
        return str(interface.network)
    except ValueError:
        return None

# --- Main Generation Loop ---
for node in nodes:
    
    # Ignora host o nodi L2
    if node.get('role') == 'host' or 'interfaces' not in node:
        continue

    hostname = node['name']
    neighbors_dict = {}
    bgp_networks = set()
    local_asn = node['bgp']['asn'] if 'bgp' in node else None

    # 1. Identifica le reti da annunciare (filtra link di transito /30)
    if local_asn:
        for iface in node['interfaces']:
            mask = iface['ipv4_mask']
            if mask == '/24' or mask == '/32' or mask == '/30':
                net = get_network_address(iface['ipv4_address'], mask)
                if net: bgp_networks.add(net)

    # 2. Neighbor Discovery
    if local_asn:
        for link in links:
            # Trova l'endpoint remoto del link
            if link['a'] == hostname:
                remote_name, remote_port = link['b'], link['b_port']
            elif link['b'] == hostname:
                remote_name, remote_port = link['a'], link['a_port']
            else:
                continue
            
            remote_node = nodes_map.get(remote_name)
            if not remote_node: continue

            # Caso A: Connessione Diretta (Punto-Punto)
            if 'bgp' in remote_node:
                r_ip = get_remote_ip(remote_name, remote_port)
                if r_ip:
                    neighbors_dict[r_ip] = {
                        "ip": r_ip,
                        "remote_as": remote_node['bgp']['asn'],
                        "type": 'ibgp' if remote_node['bgp']['asn'] == local_asn else 'ebgp',
                        "description": f"Link_to_{remote_name}"
                    }
            
            # Caso B: Connessione via Bridge (LAN condivisa)
            # Cerca altri router connessi allo stesso bridge per stabilire iBGP
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

    # Render template e scrittura su file
    config = template.render(
        device=node,
        interfaces=node['interfaces'],
        neighbors=list(neighbors_dict.values()),
        networks=list(bgp_networks)
    )
    
    with open(os.path.join(OUTPUT_DIR, f"{hostname}.conf"), "w") as f:
        f.write(config)
    print(f"Generata config per {hostname}")