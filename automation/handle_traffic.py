import subprocess
import shlex
import yaml
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
YAML_FILE = os.path.join(BASE_DIR, "..", "topology", "data.yaml")

def load_topology(file_path=YAML_FILE):
    with open(file_path, 'r') as f:
        return yaml.safe_load(f)

def frr_cmd(container, cmds):
    full_cmd = ["docker", "exec", container, "vtysh"]
    for c in cmds:
        full_cmd.extend(["-c", c])
    subprocess.run(full_cmd, check=True)

def get_bgp_config(topo, node_name, neighbor_name):
    node = next((n for n in topo['nodes'] if n['name'] == node_name), None)
    neighbor = next((n for n in topo['nodes'] if n['name'] == neighbor_name), None)

    if not node:
        raise ValueError(f"Node {node_name} non trovato nel topology file")
    if not neighbor:
        raise ValueError(f"Neighbor {neighbor_name} non trovato nel topology file")
    
    local_asn = node['bgp']['asn']
    remote_asn = neighbor['bgp']['asn']
    neighbor_ip = None

    for link in topo['links']:
        if link['a'] == node_name and link['b'] == neighbor_name:
            neighbor_port = link['b_port']
            neighbor_iface = next(i for i in neighbor['interfaces'] if i['name'] == neighbor_port)
            neighbor_ip = neighbor_iface['ipv4_address']
            break
        elif link['b'] == node_name and link['a'] == neighbor_name:
            neighbor_port = link['a_port']
            neighbor_iface = next(i for i in neighbor['interfaces'] if i['name'] == neighbor_port)
            neighbor_ip = neighbor_iface['ipv4_address']
            break
            
    if not neighbor_ip:
        raise ValueError(f"No bgp session found between {node_name} and {neighbor_name}")

    container_name = f"clab-project-{node_name}"
    return container_name, local_asn, remote_asn, neighbor_ip

def get_local_config(topo, node_name, neighbor_name):

    node = next(n for n in topo['nodes'] if n['name'] == node_name)
    neighbor = next(n for n in topo['nodes'] if n['name'] == neighbor_name)

    if 'bgp' not in node or 'bgp' not in neighbor:
        raise ValueError("One of the nodes has no BGP configuration")

    if node['bgp']['asn'] != neighbor['bgp']['asn']:
        raise ValueError("Nodes are not in the same AS (not iBGP)")

    local_asn = node['bgp']['asn']

    bridges = set()

    for link in topo['links']:
        if link['a'] == node_name:
            bridges.add(link['b'])
        elif link['b'] == node_name:
            bridges.add(link['a'])

    common_bridge = None
    neighbor_iface = None

    for link in topo['links']:
    
        if link['a'] == node_name and link['b'] in bridges:
            bridge = link['b']

            for l in topo['links']:
                if l['a'] == neighbor_name and l['b'] == bridge:
                    common_bridge = bridge
                    neighbor_port = l['a_port']
                    neighbor_iface = next(
                        i for i in neighbor['interfaces']
                        if i['name'] == neighbor_port
                    )
                    break
        if common_bridge:
            break

    if not neighbor_iface:
        raise ValueError(
            f"{node_name} and {neighbor_name} do not share a LAN for iBGP"
        )

    neighbor_ip = neighbor_iface['ipv4_address']
    container_name = f"clab-project-{node_name}"

    return container_name, local_asn, neighbor_ip

def update_node_med(container, local_number, remote_number, interface, med, prefix, seq):

    route_map = f"MED-{interface.replace('.', '_')}"
    prefix_list = f"PL-{prefix.replace('.', '_').replace('/', '_')}"

    cmds = [
        "conf t",
        f"ip prefix-list {prefix_list} seq {seq} permit {prefix}",
        f"route-map {route_map} permit {seq}",
        f"match ip address prefix-list {prefix_list}",
        f"set metric {med}",
        "exit",
        f"router bgp {local_number}",
        f"neighbor {interface} route-map {route_map} out",
        "exit",
        "end",
    ]

    full_cmd = ["docker", "exec", container, "vtysh"]
    for c in cmds:
        full_cmd.extend(["-c", c])

    print("\n Executed command: ")
    print(" ".join(shlex.quote(x) for x in full_cmd))

    subprocess.run(full_cmd, check=True)

    subprocess.run(
        ["docker", "exec", container, "vtysh",
         "-c", f"clear bgp ipv4 unicast {interface} soft out"],
        check=True
    )

    print(f"[OK] {container}: neighbor {interface} → MED {med}")

def update_node_local_pref(container, local_as, neighbor_ip, local_pref):

    route_map = f"LP-{neighbor_ip.replace('.', '_')}"

    cmds = [
        "conf t",
        f"route-map {route_map} permit 10",
        f"set local-preference {local_pref}",
        "exit",
        f"router bgp {local_as}",
        f"neighbor {neighbor_ip} route-map {route_map} in",
        "exit",
        "end"
    ]

    subprocess.run(
        ["docker", "exec", container, "vtysh"] +
        sum([["-c", c] for c in cmds], []),
        check=True
    )

    subprocess.run(
        ["docker", "exec", container, "vtysh",
         "-c", f"clear bgp ipv4 unicast {neighbor_ip} soft in"],
        check=True
    )

    print(f"[OK] {container}: neighbor {neighbor_ip} → LOCAL_PREF {local_pref}")


def get_ipv4_address(node):
    topology = load_topology()

    nodes = topology['nodes']

    nodes_map = {n['name']: n for n in nodes}

    default_gateway =  nodes_map.get(node)['ipv4_address'] if nodes_map.get(node) != None else None

    return str(default_gateway)


def set_med(node, neighbor, med, destination, seq):
    topo = load_topology()
    prefix = get_ipv4_address(destination) + "/32"
    container, local_as, remote_as, neighbor_ip = get_bgp_config(topo, node, neighbor)
    update_node_med(container, local_as, remote_as, neighbor_ip, med, prefix, seq)

def set_local_pref(node, neighbor, local_pref):
    topo = load_topology()
    container, local_as, neighbor_ip = get_local_config(topo, node, neighbor)
    update_node_local_pref(container, local_as, neighbor_ip, local_pref)

def test_meds():
    set_med("pe1", "ce1", 100, "r1")

    set_med("pe2", "ce1", 200, "r1")



