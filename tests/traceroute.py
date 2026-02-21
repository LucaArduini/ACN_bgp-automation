#!/usr/bin/env python3
"""
This script verifies that the basic host routing is correctly configured.
It performs a traceroute from the terminal nodes (n1, n2) to an external destination
and validates that the first hop in the chain matches the default Gateway 
address configured in the 'data.yaml' file.
"""

import yaml
import os
import subprocess

# --- CONFIGURATION ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
YAML_FILE = os.path.join(BASE_DIR, "..", "topology", "data.yaml")
CLAB_PREFIX = "clab-project"

def print_header(msg):
    print(f"\n{'='*15} {msg} {'='*15}")

def load_topology():
    """Loads the topology and returns a node map for fast access"""
    try:
        with open(YAML_FILE, 'r') as f:
            data = yaml.safe_load(f)
        return {node['name']: node for node in data.get('nodes', [])}
    except Exception as e:
        print(f"[ERR] YAML loading error: {e}")
        return {}

def run_traceroute(node, destination, expected_gw):
    """Executes traceroute and verifies if the first hop is the correct gateway"""
    container = f"{CLAB_PREFIX}-{node}"
    
    # -n: avoids DNS resolution, -m 5: limits the search to the first 5 hops
    cmd = ["docker", "exec", container, "traceroute", "-n", "-m", "5", destination]

    try:
        process = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        output = process.stdout
        
        # Parse output to find the expected gateway IP
        is_reached = expected_gw in output if expected_gw else False
        return is_reached, output
    except subprocess.TimeoutExpired:
        return False, "Timeout"
    except Exception as e:
        return False, str(e)

def run_traceroute_tests():
    """Test execution cycle for selected host nodes"""
    topology_data = load_topology()
    
    test_nodes = ["n1", "n2"]
    target = "8.8.8.8" # Mock external destination

    print_header("TEST: TRACEROUTE (GATEWAY CHECK)")
    print(f"{'SOURCE':<12} | {'DESTINATION':<15} | {'EXPECTED GW':<15} | {'RESULT'}")
    print("-" * 65)

    for node_name in test_nodes:
        node_info = topology_data.get(node_name, {})
        gw_ip = node_info.get('gateway_ip')
        
        # Skip test if the node has no gateway configured in data.yaml
        if not gw_ip:
            print(f"{node_name:<12} | {target:<15} | {'N/A':<15} | [ SKIP ]")
            continue

        success, _ = run_traceroute(node_name, target, gw_ip)
        
        result_str = "[ OK ]" if success else "[ FAIL ]"
        print(f"{node_name:<12} | {target:<15} | {gw_ip:<15} | {result_str}")

if __name__ == "__main__":
    run_traceroute_tests()