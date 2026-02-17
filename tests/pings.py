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

def get_ipv4_address(node):
    topology = load_topology()

    nodes = topology['nodes']

    nodes_map = {n['name']: n for n in nodes}

    default_gateway =  nodes_map.get(node)['ipv4_address'] if nodes_map.get(node) != None else None

    return str(default_gateway)


def ping(node, destination):
    cmds = [
        "ping",
        "-c",
        "4",
        destination
    ]

    full_cmd = ["docker", "exec", f"clab-project-{node}"]
    for c in cmds:
        full_cmd.extend([c])

    p = subprocess.run(full_cmd, capture_output=True, timeout=6, text=True)

    try:
        output_stdout = str(p.stdout)
        
        if p.returncode == 0:
            if "ttl" in output_stdout:
                print(f"Node reached. Ping from {node} to {destination} works.")
                return True


    except subprocess.TimeoutExpired:
        print("timeout")
        return False

def ping_interface(node, interface, destination):
    cmds = [
        "ping",
        "-I",
        interface,
        "-c",
        "4",
        destination
    ]

    full_cmd = ["docker", "exec", f"clab-project-{node}"]
    for c in cmds:
        full_cmd.extend([c])

    p = subprocess.run(full_cmd, capture_output=True, timeout=8, text=True)

    try:
        output_stdout = str(p.stdout)
        
        if p.returncode == 0:
            if "ttl" in output_stdout:
                print(f"Node reached. Ping from {node} to {destination} works.")
                return True


    except subprocess.TimeoutExpired:
        print("timeout")
        return False

nodes_from = [
    "n1",
    "n2"
]

nodes_to_check = [
    "r1",
    "r2",
    "r3"
]

for n1 in nodes_from:
    for n2 in nodes_to_check:
        ping(n1, get_ipv4_address(n2))

for n1 in nodes_to_check:
    for n2 in nodes_from:
        ping_interface(n1, get_ipv4_address(n1), get_ipv4_address(n2))