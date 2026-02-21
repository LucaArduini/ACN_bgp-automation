#!/usr/bin/env python3
"""
This script validates the effectiveness of the Traffic Engineering policies applied by the Manager.
It performs traceroutes from source nodes to destinations and compares the actual hops 
detected with the expected path (PE and GW) defined in the 'final_routing_paths.json' file.
It is the primary tool to verify that BGP modifications have effectively 
changed flow routing.
"""

import yaml
import os
import subprocess
import json
import sys

# --- PATH CONFIGURATION ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
YAML_FILE = os.path.join(BASE_DIR, "..", "topology", "data.yaml")
JSON_FILE = os.path.join(BASE_DIR, "..", "automation", "final_routing_paths.json")
CLAB_PREFIX = "clab-project"

def print_header(msg):
    print(f"\n{'='*20} {msg} {'='*20}")

def load_data():
    """Loads network topology and optimized flows from the Manager"""
    if not os.path.exists(JSON_FILE):
        print(f"[ERR] File '{os.path.basename(JSON_FILE)}' not found.")
        print(f"[TIP] Run 'manager.py' first to generate the paths, then try again.")
        sys.exit(1)

    try:
        with open(YAML_FILE, 'r') as f:
            topology = yaml.safe_load(f)
        with open(JSON_FILE, 'r') as f:
            flows = json.load(f)
        return topology, flows
    except Exception as e:
        print(f"[ERR] Error while loading data: {e}")
        sys.exit(1)

def get_node_ip(nodes, node_name):
    """Returns the IP address of a specific destination"""
    for node in nodes:
        if node['name'] == node_name:
            return str(node.get('ipv4_address', '')).split('/')[0]
    return None

def get_link_ip(topology, node_a, node_b):
    """
    Finds the IP of the interface on node_b that faces towards node_a.
    This function is critical because traceroute shows the IP of the 
    ingress interface of the next router (hop).
    """
    links = topology.get('links', [])
    nodes = topology.get('nodes', [])
    
    remote_port = None
    potential_a = [node_a, "lan"] 

    # Search for direct connection or via LAN between the two nodes
    for link in links:
        if link['a'] in potential_a and link['b'] == node_b:
            remote_port = link['b_port']
        elif link['b'] in potential_a and link['a'] == node_b:
            remote_port = link['a_port']
        if remote_port: break
            
    if not remote_port: return None

    # Retrieves the IP configured on the identified port
    for node in nodes:
        if node['name'] == node_b:
            for interface in node.get('interfaces', []):
                if interface['name'] == remote_port:
                    return str(interface['ipv4_address']).split('/')[0]
    return None

def run_traceroute(source_node, destination_ip):
    """Executes traceroute inside the source container and captures the output"""
    # Maps logical role (ce) to physical container (n)
    container_name = source_node.replace("ce", "n")
    full_container = f"{CLAB_PREFIX}-{container_name}"
    
    # -n: avoids DNS resolution (fast), -w 1: short timeout for responsive tests
    cmd = ["docker", "exec", full_container, "traceroute", "-n", "-w", "1", "-m", "10", destination_ip]
    
    try:
        process = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
        return process.stdout
    except Exception:
        return ""

def validate_traffic_engineering():
    """Compares actual detected paths with those calculated by the optimizer"""
    topology_data, flows = load_data()
    nodes = topology_data.get('nodes', [])

    print_header("TRAFFIC ENGINEERING VERIFICATION")
    
    table_header = f"{'SOURCE':<10} | {'DEST':<10} | {'EXPECTED PATH':<22} | {'STATUS'}"
    print(table_header)
    print("-" * len(table_header))

    for flow in flows:
        source = flow['source']
        destination = flow['destination']
        expected_pe = flow['path']['pe']
        expected_gw = flow['path']['gw']

        # 1. Retrieve the IP of the final destination router
        destination_ip = get_node_ip(nodes, destination)
        if not destination_ip:
            print(f"{source:<10} | {destination:<10} | {'IP not found':<22} | [SKIP]")
            continue

        # 2. Analyze the actual path via traceroute
        output = run_traceroute(source, destination_ip)

        # 3. Identify IPs that should appear as hops
        # PE IP as seen from the CE
        pe_hop_ip = get_link_ip(topology_data, source, expected_pe)
        # GW IP as seen from the PE
        gw_hop_ip = get_link_ip(topology_data, expected_pe, expected_gw)

        # Verify if expected IPs are present in the traceroute hop sequence
        pe_found = pe_hop_ip in output if pe_hop_ip else False
        gw_found = gw_hop_ip in output if gw_hop_ip else False

        # 4. Determine test result
        if pe_found and gw_found:
            status = "[ OK ]"
        else:
            errors = []
            if not pe_found: errors.append(f"No {expected_pe}")
            if not gw_found: errors.append(f"No {expected_gw}")
            status = f"[FAIL: {', '.join(errors)}]"

        path_string = f"{expected_pe} -> {expected_gw}"
        print(f"{source:<10} | {destination:<10} | {path_string:<22} | {status}")

        # Debug messages to investigate failures (non-updated paths)
        if not (pe_found and gw_found):
            print(f"   > Expected IPs: PE={pe_hop_ip}, GW={gw_hop_ip}")

if __name__ == "__main__":
    validate_traffic_engineering()