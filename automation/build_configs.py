import jinja2
import os
import yaml
from jinja2 import Environment, FileSystemLoader


BASE_DIR = os.path.dirname(os.path.abspath(__file__))

TEMPLATES_DIR = os.path.join(BASE_DIR, "..", "templates")
TOPOLOGY_DIR = os.path.join(BASE_DIR, "..", "topology")
DATA_FILE = os.path.join(TOPOLOGY_DIR, "data.yaml")
OUTPUT_DIR = os.path.join(BASE_DIR, "..", "configs")

os.makedirs(OUTPUT_DIR, exist_ok=True)

environment = Environment(loader=FileSystemLoader(TEMPLATES_DIR), trim_blocks=True, lstrip_blocks=True)
template = environment.get_template("config.j2")

with open(DATA_FILE, "r") as f:
    data = yaml.safe_load(f)

nodes = data['nodes']
links = data['links']
nodes_map = {n['name']: n for n in nodes}

def get_interface_ip(node_name, port_name):
    node = nodes_map.get(node_name)
    if not node or 'interfaces' not in node:
        return None
    for iface in node['interfaces']:
        if iface['name'] == port_name:
            return iface['ip'].split('/')[0]
    return None

def get_remote_ip(node_name, port_name):
    """Cerca l'IP configurato sull'interfaccia di un nodo specifico"""
    node = nodes_map.get(node_name)
    if node and 'interfaces' in node:
        for iface in node['interfaces']:
            if iface['name'] == port_name:
                return iface.get('ipv4_address')
    return None

for node in nodes:

    if node['role'] == 'host': continue

    hostname = node['name']
    if 'interfaces' not in node: continue

    neighbors = []
    if 'bgp' in node:
        for link in links:
          
            if link['a'] == hostname:
                remote_name = link['b']
                remote_port = link['b_port']
            elif link['b'] == hostname:
                remote_name = link['a']
                remote_port = link['a_port']
            else:
                continue
            
            remote_node = nodes_map.get(remote_name)
            if remote_node and 'bgp' in remote_node:
                remote_ip = get_remote_ip(remote_name, remote_port)
                if remote_ip:
                    neighbors.append({
                        "ip": remote_ip,
                        "remote_as": remote_node['bgp']['asn'],
                        "description": f"Link_to_{remote_name}"
                    })

    config = template.render(
        device=node,
        interfaces=node['interfaces'],
        neighbors=neighbors
    )
    
    os.makedirs("configs", exist_ok=True)
    with open(f"configs/{hostname}.conf", "w") as f:
        f.write(config)
    print(f"Generata config per {hostname}")