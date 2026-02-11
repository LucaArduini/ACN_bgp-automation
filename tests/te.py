import yaml
import os
import subprocess
import json

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
YAML_FILE = os.path.join(BASE_DIR, "..", "topology", "data.yaml")


JSON_FILE = os.path.join(BASE_DIR, "..", "automation", "final_routing_paths.json")

def load_topology(file_path=YAML_FILE):
    try:
        with open(file_path, 'r') as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        return {"nodes": []}

def load_flows():
    with open(JSON_FILE, 'r') as f:
        return json.load(f)

def get_remote_interface_ip(source_node, target_node):
    topology = load_topology()
    links = topology.get('links', [])
    nodes = topology.get('nodes', [])
    
    remote_port = None
    
    potential_sources = [source_node, "lan"] 

    for link in links:

        for s in potential_sources:
            if link['a'] == s and link['b'] == target_node:
                remote_port = link['b_port']
            elif link['b'] == s and link['a'] == target_node:
                remote_port = link['a_port']
            if remote_port: break
        if remote_port: break
            
    if not remote_port:
        return None

    for node in nodes:
        if node['name'] == target_node:
            for interface in node.get('interfaces', []):
                if interface['name'] == remote_port:
     
                    return str(interface['ipv4_address']).split('/')[0]
                    
    return None

def traceroute(node, destination):
    cmds = [
        "traceroute",
        destination
    ]

    full_cmd = ["docker", "exec", "-it", f"clab-project-{node}"]
    for c in cmds:
        full_cmd.extend([c])

    output = subprocess.run(full_cmd, check=True, capture_output=True, text=True)

    return output.stdout


def get_ipv4_address(node):
    topology = load_topology()

    nodes = topology['nodes']

    nodes_map = {n['name']: n for n in nodes}

    ip =  nodes_map.get(node)['ipv4_address'] if nodes_map.get(node) != None else None

    return str(ip)

def verify_flows():
    flows = load_flows()
    
    print(f"{'SOURCE':<10} | {'DEST':<10} | {'EXPECTED PATH':<20} | {'STATUS':<10}")
    print("-" * 60)

    for flow in flows:
        src = flow['source']
        dst = flow['destination']
        expected_pe = flow['path']['pe']
        expected_gw = flow['path']['gw']

        dst_ip = get_ipv4_address(dst)

        print(dst_ip)
        
        output = traceroute(src, dst_ip)

        print(expected_pe)
        
        pe_found = get_remote_interface_ip("ce1", expected_pe) in output

        print(expected_gw)
        gw_found = get_remote_interface_ip(expected_pe, expected_gw) in output
        
        
        if pe_found and gw_found:
            status = "✅ OK"
        else:
            missing = []
            if not pe_found: missing.append(expected_pe)
            if not gw_found: missing.append(expected_gw)
            status = f"❌ FAIL (Missing: {', '.join(missing)})"

        expected_str = f"{expected_pe} -> {expected_gw}"
        print(f"{src:<10} | {dst:<10} | {expected_str:<20} | {status}")

        if not (pe_found and gw_found):
             print(f"   [Debug Output]:\n{output}")

if __name__ == "__main__":
    verify_flows()