#!/usr/bin/env python3
"""
This script performs end-to-end ICMP (Ping) connectivity tests in the network.
It verifies two fundamental scenarios:
1. Connectivity from internal hosts to external routers (Internet).
2. Connectivity from external routers back to hosts, validating the return path.
Ensures that the data plane is operational before proceeding with BGP automation.
"""

import yaml
import os
import subprocess

# --- CONFIGURATION ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
YAML_FILE = os.path.join(BASE_DIR, "..", "topology", "data.yaml")
CLAB_PREFIX = "clab-project"

def print_header(msg):
    print(f"\n{'='*20} {msg} {'='*20}")

def load_topology():
    """Loads topology data once to optimize tests"""
    try:
        with open(YAML_FILE, 'r') as f:
            data = yaml.safe_load(f)
        return {node['name']: node for node in data.get('nodes', [])}
    except Exception as e:
        print(f"[ERR] YAML loading error: {e}")
        return {}

def run_ping(node, destination, interface=None):
    """Executes the ping command inside the specified Docker container"""
    container = f"{CLAB_PREFIX}-{node}"
    
    # -c 3: 3 packets, -W 2: waits max 2 seconds for each response
    ping_cmds = ["ping", "-c", "3", "-W", "2"]
    if interface:
        ping_cmds.extend(["-I", interface]) # Force source interface if specified
    ping_cmds.append(destination)

    full_cmd = ["docker", "exec", container] + ping_cmds

    try:
        process = subprocess.run(full_cmd, capture_output=True, text=True, timeout=8)
        return process.returncode == 0 # True if ping succeeds (exit code 0)
    except subprocess.TimeoutExpired:
        return False
    except Exception:
        return False

def run_connectivity_tests():
    """Manages the execution of bidirectional Host <-> Router tests"""
    topology_data = load_topology()
    if not topology_data:
        return
    
    source_nodes = ["n1", "n2"]
    routers_to_check = ["r1", "r2", "r3"]

    # --- TEST 1: HOST -> ROUTER (Outbound traffic) ---
    print_header("TEST: HOST -> ROUTER")
    table_header = f"{'FROM (Node)':<12} | {'SOURCE IP':<15} | {'TO (Router)':<12} | {'DEST IP':<15} | {'STATUS'}"
    print(table_header)
    print("-" * len(table_header))

    for src in source_nodes:
        src_ip = topology_data.get(src, {}).get('ipv4_address', "N/A").split('/')[0]
        for dst in routers_to_check:
            dest_ip = topology_data.get(dst, {}).get('ipv4_address', "").split('/')[0]
            if not dest_ip: continue
            
            is_success = run_ping(src, dest_ip)
            status_str = "[ OK ]" if is_success else "[ FAIL ]"
            print(f"{src:<12} | {src_ip:<15} | {dst:<12} | {dest_ip:<15} | {status_str}")

    # --- TEST 2: ROUTER -> HOST (Return traffic) ---
    print_header("TEST: ROUTER -> HOST (VIA INTERFACE)")
    table_header = f"{'FROM (Router)':<12} | {'SRC IP (INT)':<15} | {'TO (Node)':<12} | {'DEST IP':<15} | {'STATUS'}"
    print(table_header)
    print("-" * len(table_header))

    for src in routers_to_check:
        src_ip = topology_data.get(src, {}).get('ipv4_address', "").split('/')[0]
        for dst in source_nodes:
            dest_ip = topology_data.get(dst, {}).get('ipv4_address', "").split('/')[0]
            if not src_ip or not dest_ip: continue

            # Uses the router's Loopback IP as the ping source
            is_success = run_ping(src, dest_ip, interface=src_ip)
            status_str = "[ OK ]" if is_success else "[ FAIL ]"
            print(f"{src:<12} | {src_ip:<15} | {dst:<12} | {dest_ip:<15} | {status_str}")

if __name__ == "__main__":
    run_connectivity_tests()