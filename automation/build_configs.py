"""
This script automates the generation of configuration files for FRR routers.
The process is divided into several phases:
1. Loading abstract network data from the 'data.yaml' file.
2. Adjacency analysis to identify BGP neighbors (iBGP and eBGP).
3. Calculation of network prefixes to announce based on subnet masks.
4. Rendering Jinja2 templates ('config.j2') to produce .conf files ready 
   to be loaded by FRR containers.
Includes specific logic to handle BGP peering both on point-to-point links 
and across LAN segments (bridges).
"""

import jinja2
import os
import yaml
import ipaddress
from jinja2 import Environment, FileSystemLoader

# Path definitions for templates, data, and output
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, "..", "templates")
TOPOLOGY_DIR = os.path.join(BASE_DIR, "..", "topology")
DATA_FILE = os.path.join(TOPOLOGY_DIR, "data.yaml")
OUTPUT_DIR = os.path.join(BASE_DIR, "..", "configs")

# Ensures the output directory for configurations exists
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Initializing Jinja2 environment
environment = Environment(loader=FileSystemLoader(TEMPLATES_DIR), trim_blocks=True, lstrip_blocks=True)
template = environment.get_template("config.j2")

# Loading topology from YAML file
with open(DATA_FILE, "r") as f:
    data = yaml.safe_load(f)

nodes = data['nodes']
links = data['links']
nodes_map = {n['name']: n for n in nodes}

def get_remote_ip(node_name, port_name):
    """Retrieves the IP address of a specific interface on a node"""
    node = nodes_map.get(node_name)
    if node and 'interfaces' in node:
        for iface in node['interfaces']:
            if iface['name'] == port_name:
                return iface.get('ipv4_address')
    return None

def get_network_address(ip, mask):
    """Calculates the network address given IP and mask"""
    try:
        interface = ipaddress.IPv4Interface(f"{ip}{mask}")
        return str(interface.network)
    except ValueError:
        return None

# Processing each node to generate its configuration
for node in nodes:

    # Skip hosts and nodes without interfaces (e.g., bridges)
    if node.get('role') == 'host' or 'interfaces' not in node:
        continue

    hostname = node['name']
    neighbors_dict = {}
    bgp_networks = set()
    
    local_asn = node['bgp']['asn'] if 'bgp' in node else None

    # Identifying networks to announce via BGP
    if local_asn:
        for iface in node['interfaces']:
            mask = iface['ipv4_mask']
            if mask == '/24' or mask == '/32' or mask == '/28':
                net = get_network_address(iface['ipv4_address'], mask)
                if net: bgp_networks.add(net)

    # Identifying BGP neighbors through link analysis
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

            # Peering on point-to-point links (Router-to-Router)
            if 'bgp' in remote_node:
                r_ip = get_remote_ip(remote_name, remote_port)
                if r_ip:
                    neighbors_dict[r_ip] = {
                        "ip": r_ip,
                        "remote_as": remote_node['bgp']['asn'],
                        "type": 'ibgp' if remote_node['bgp']['asn'] == local_asn else 'ebgp',
                        "description": f"Link_to_{remote_name}"
                    }
            
            # Peering through bridges (Router-to-LAN-to-Router) for iBGP
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

    # Final rendering of the configuration file
    config = template.render(
        device=node,
        interfaces=node['interfaces'],
        neighbors=list(neighbors_dict.values()),
        networks=list(bgp_networks)
    )
    
    # Writing the .conf file to disk
    with open(os.path.join(OUTPUT_DIR, f"{hostname}.conf"), "w", newline='\n') as f:
        f.write(config)
    print(f"Generated config for {hostname}")