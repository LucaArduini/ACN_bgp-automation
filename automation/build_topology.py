"""
This script generates the 'network.clab.yml' orchestration file for Containerlab.
In addition to file generation via Jinja2, the script includes a data 
validation engine that prevents common network configuration errors:
1. Detects IP address collisions (duplicate IPs).
2. Verifies subnet consistency on links (both endpoints on the same network).
3. Checks that subnet masks are wide enough to accommodate the nodes.
If validation fails, generation is aborted to prevent incorrect deployments.
"""

import jinja2
import os
import yaml
import sys
import ipaddress
from jinja2 import Environment, FileSystemLoader

def validate_data(data):
    """
    Performs integrity checks on topology data:
    1. No duplicate IPs in the network.
    2. Subnet consistency on links (same network, valid mask).
    """
    print("--- Starting Data Validation ---")
    errors = []
    
    seen_ips = {}
    interface_map = {}

    # 1. DUPLICATE CHECK AND MAP POPULATION
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

                # Detection of IP addresses assigned to multiple interfaces
                if ip_str in seen_ips:
                    prev_node, prev_iface = seen_ips[ip_str]
                    errors.append(f"[DUPLICATE IP] The address {ip_str} is used on both {prev_node}:{prev_iface} and {node['name']}:{iface['name']}")
                else:
                    seen_ips[ip_str] = (node['name'], iface['name'])

                # Formal IPv4 address validation
                try:
                    if_obj = ipaddress.ip_interface(full_addr)
                    key = f"{node['name']}:{iface['name']}"
                    interface_map[key] = if_obj
                except ValueError as e:
                    errors.append(f"[INVALID IP] {node['name']}:{iface['name']} has an invalid IP: {full_addr}. Error: {e}")

    # 2. LINK CONSISTENCY CHECK
    for link in data['links']:
        endpoint_a = f"{link['a']}:{link['a_port']}"
        endpoint_b = f"{link['b']}:{link['b_port']}"

        if endpoint_a in interface_map and endpoint_b in interface_map:
            ip_a = interface_map[endpoint_a]
            ip_b = interface_map[endpoint_b]

            # Verify that both sides of the link belong to the same subnet
            if ip_a.network != ip_b.network:
                errors.append(f"[SUBNET MISMATCH] Link between {endpoint_a} and {endpoint_b}: Subnets do not match ({ip_a.network} vs {ip_b.network})")

            # Verify that the mask allows at least 2 hosts (point-to-point)
            if ip_a.network.num_addresses < 2:
                 errors.append(f"[MASK TOO SMALL] Link between {endpoint_a} and {endpoint_b}: The mask {ip_a.with_netmask} is too small")

    # Validation outcome management
    if errors:
        print("!!! CRITICAL DATA ERRORS FOUND !!!")
        for e in errors:
            print(f" - {e}")
        print("Generation aborted.")
        sys.exit(1)
    else:
        print("Validation successful: No duplicates and consistent subnets.")

# --- MAIN SCRIPT ---

# Path configuration and Jinja2 environment setup
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, "..", "templates")
TOPOLOGY_DIR = os.path.join(BASE_DIR, "..", "topology")

data_path = os.path.join(TOPOLOGY_DIR, "data.yaml")
output_path = os.path.join(TOPOLOGY_DIR, "network.clab.yml")

# Jinja2 engine setup
environment = Environment(
    loader=FileSystemLoader(TEMPLATES_DIR),
    trim_blocks=True,
    lstrip_blocks=True
)
template = environment.get_template("topology.j2")

# Reading source data file
with open(data_path, 'r') as f:
    data = yaml.safe_load(f)

# Validating data before topology generation
validate_data(data)

# Rendering YAML file for Containerlab
content = template.render(nodes=data['nodes'], links=data['links'])
with open(output_path, 'w', newline='\n') as f:
    f.write(content)

print("Container lab network yaml file generated!")