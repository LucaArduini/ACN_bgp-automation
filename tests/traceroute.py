import yaml
import os
import subprocess

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
YAML_FILE = os.path.join(BASE_DIR, "..", "topology", "data.yaml")

def load_topology(file_path=YAML_FILE):
    with open(file_path, 'r') as f:
        return yaml.safe_load(f)

def get_default_gateway(node):
    topology = load_topology()

    nodes = topology['nodes']

    nodes_map = {n['name']: n for n in nodes}

    default_gateway =  nodes_map.get(node)['gateway_ip'] if nodes_map.get(node) != None else None

    return default_gateway

def traceroute(node, destination):
    cmds = [
        "traceroute",
        destination
    ]

    full_cmd = ["docker", "exec", "-it", f"clab-project-{node}"]
    for c in cmds:
        full_cmd.extend([c])

    output = subprocess.run(full_cmd, check=True, capture_output=True)

    output_stdout = str(output.stdout)

    #print(output_stdout)

    if get_default_gateway(node) in output_stdout:
        print("Gateway reached")

traceroute("n1", "8.8.8.8")