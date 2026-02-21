"""
This module manages the practical application of BGP policies on FRR routers.
It translates optimizer decisions into CLI commands (vtysh) to dynamically 
modify MED and Local Preference using Route Maps.
"""

import subprocess
import shlex
import yaml
import os

# --- PATH CONFIGURATION ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
YAML_FILE = os.path.join(BASE_DIR, "..", "topology", "data.yaml")

def load_topology(file_path=YAML_FILE):
    with open(file_path, 'r') as f:
        return yaml.safe_load(f)

def get_ipv4_address(node_name):
    """Retrieves the identifying IP address of a node from the data file"""
    topo = load_topology()
    node = next((n for n in topo['nodes'] if n['name'] == node_name), None)
    if not node or 'ipv4_address' not in node:
        return None
    return str(node['ipv4_address'])

def get_bgp_config(topo, node_name, neighbor_name):
    """
    Retrieves BGP info for eBGP sessions (CE-PE).
    Finds the IP address of a BGP neighbor by analyzing the physical links in the topology.
    Returns the container name, local ASN, and neighbor IP.
    """
    node = next((n for n in topo['nodes'] if n['name'] == node_name), None)
    neighbor = next((n for n in topo['nodes'] if n['name'] == neighbor_name), None)

    if not node or not neighbor:
        raise ValueError(f"Node {node_name} or {neighbor_name} not found")
    
    local_asn = node['bgp']['asn']
    neighbor_ip = None

    # Scan all links to find the one connecting the two specified routers
    for link in topo['links']:
        # If current node is side 'a', we look for the IP of side 'b'
        if link['a'] == node_name and link['b'] == neighbor_name:
            neighbor_port = link['b_port']
            neighbor_iface = next(i for i in neighbor['interfaces'] if i['name'] == neighbor_port)
            neighbor_ip = neighbor_iface['ipv4_address']
            break
        # If current node is side 'b', we look for the IP of side 'a'
        elif link['b'] == node_name and link['a'] == neighbor_name:
            neighbor_port = link['a_port']
            neighbor_iface = next(i for i in neighbor['interfaces'] if i['name'] == neighbor_port)
            neighbor_ip = neighbor_iface['ipv4_address']
            break
            
    if not neighbor_ip:
        raise ValueError(f"No BGP session between {node_name} and {neighbor_name}")

    container_name = f"clab-project-{node_name}"
    return container_name, local_asn, neighbor_ip

def get_local_config(topo, node_name, neighbor_name):
    """
    Retrieves BGP info for iBGP sessions (PE-GW)
    """
    node = next(n for n in topo['nodes'] if n['name'] == node_name)
    neighbor = next(n for n in topo['nodes'] if n['name'] == neighbor_name)
    
    neighbor_ip = None
    # Look for the neighbor's IP by checking the correct interface
    neighbor_ip = neighbor['interfaces'][0]['ipv4_address']
    container_name = f"clab-project-{node_name}"
    local_asn = node['bgp']['asn']

    return container_name, local_asn, neighbor_ip

def update_node_med(container, local_as, neighbor_ip, med, prefix, seq):
    """
    Configures MED via vtysh to influence inbound traffic (Inbound TE).
    Procedure: 
    1. Isolate traffic via Prefix-List.
    2. Create a Route-Map that applies the metric to the matched prefix.
    3. Associate the Route-Map with the specific BGP neighbor on output (out).
    """
    # Transform the IP into a safe string for FRR configuration names
    safe_ip = neighbor_ip.replace('.', '_').replace('/', '')
    route_map = f"RM_MED_OUT_{safe_ip}"
    prefix_list = f"PL_{prefix.replace('.', '_').replace('/', '_')}"

    cmds = [
        "conf t",
        # Create the prefix-list to identify the specific destination
        f"ip prefix-list {prefix_list} seq {seq} permit {prefix}",
        # Define the route-map: if the prefix matches, set the MED
        f"route-map {route_map} permit {seq}",
        f"  match ip address prefix-list {prefix_list}",
        f"  set metric {med}",
        "exit",
        # Final permissive rule (catch-all) to avoid filtering the rest of the BGP traffic
        f"route-map {route_map} permit 65535",
        "exit",
        # Apply the policy to the BGP session towards the neighbor
        f"router bgp {local_as}",
        f"  neighbor {neighbor_ip} route-map {route_map} out",
        "exit",
        "end"
    ]

    # Compose final command for Docker exec
    vtysh_cmd = ["docker", "exec", container, "vtysh"]
    for c in cmds:
        vtysh_cmd.extend(["-c", c])
    
    try:
        # Send commands to FRR
        subprocess.run(vtysh_cmd, check=True, stdout=subprocess.DEVNULL)
        # Notify neighbors of changes via BGP Soft Reset (without dropping the session)
        subprocess.run(["docker", "exec", container, "vtysh", "-c", 
                    f"clear bgp ipv4 unicast {neighbor_ip} soft out"], 
                    check=True, stdout=subprocess.DEVNULL)
    except subprocess.CalledProcessError as e:
        print(f"[ERR] Error executing command on {container}: {e}")

def update_node_local_pref(container, local_as, neighbor_ip, local_pref, prefix, seq):
    """
    Configures Local Preference to influence outbound traffic (Outbound TE).
    Unlike MED, Local Preference is applied to received advertisements (in).
    """
    safe_ip = neighbor_ip.replace('.', '_').replace('/', '')
    route_map = f"RM_LP_IN_{safe_ip}"
    prefix_list = f"PL_{prefix.replace('.', '_').replace('/', '_')}"

    cmds = [
        "conf t",
        f"ip prefix-list {prefix_list} seq {seq} permit {prefix}",
        f"route-map {route_map} permit {seq}",
        f"  match ip address prefix-list {prefix_list}",
        f"  set local-preference {local_pref}",
        "exit",
        # Allow traffic that shouldn't be modified
        f"route-map {route_map} permit 65535",
        "exit",
        f"router bgp {local_as}",
        f"  neighbor {neighbor_ip} route-map {route_map} in",
        "exit",
        "end"
    ]

    vtysh_cmd = ["docker", "exec", container, "vtysh"]
    for c in cmds:
        vtysh_cmd.extend(["-c", c])

    try:
        subprocess.run(vtysh_cmd, check=True, stdout=subprocess.DEVNULL)
        # Force recalculation of best paths based on the new Local Preference
        subprocess.run(["docker", "exec", container, "vtysh", "-c", 
                    f"clear bgp ipv4 unicast {neighbor_ip} soft in"], 
                    check=True, stdout=subprocess.DEVNULL)
    except subprocess.CalledProcessError as e:
        print(f"[ERR] Error executing command on {container}: {e}")

# --- PUBLIC WRAPPERS ---

def set_med(node, neighbor, med, destination, seq):
    """Simplified interface to apply Inbound Traffic Engineering"""
    topo = load_topology()
    dest_ip = get_ipv4_address(destination)
    if not dest_ip:
        print(f"[ERR] Destination {destination} not found")
        return
    
    prefix = dest_ip + "/32"
    try:
        container, local_as, neighbor_ip = get_bgp_config(topo, node, neighbor)
        update_node_med(container, local_as, neighbor_ip, med, prefix, seq)
    except Exception as e:
        print(f"[ERR] set_med {node}->{neighbor} failed: {e}")

def set_local_pref(node, neighbor, local_pref, destination, seq):
    """Simplified interface to apply Outbound Traffic Engineering"""
    topo = load_topology()
    dest_ip = get_ipv4_address(destination)
    if not dest_ip:
        print(f"[ERR] Destination {destination} not found")
        return

    prefix = dest_ip + "/32"
    try:
        container, local_as, neighbor_ip = get_local_config(topo, node, neighbor)
        update_node_local_pref(container, local_as, neighbor_ip, local_pref, prefix, seq)
    except Exception as e:
        print(f"[ERR] set_local_pref {node}<-{neighbor} failed: {e}")