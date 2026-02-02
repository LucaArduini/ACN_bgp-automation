import subprocess
import shlex

def frr_cmd(container, cmds):
    full_cmd = ["docker", "exec", container, "vtysh"]
    for c in cmds:
        full_cmd.extend(["-c", c])
    subprocess.run(full_cmd, check=True)

def update_node_med(container, local_number, as_number, interface, med):

    route_map = f"MED-{interface}"

    cmds = [
        "conf t",
        f"route-map {route_map} permit 10",
        f"set metric {med}",
        "exit",
        f"router bgp {local_number}",
        f"neighbor {interface} remote-as {as_number}",
        f"neighbor {interface} route-map {route_map} out",
        "exit",
        "end",
        "write"
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


def update_node_local_pref(container, local_number, as_number, interface, local_pref):
    route_map = f"LOCALPREF-{interface}"

    cmds = [
        "conf t",
        f"route-map {route_map} permit 10",
        f"set local-preference {local_pref}",
        "exit",
        f"router bgp {local_number}",
        f"neighbor {interface} remote-as {as_number}",
        f"neighbor {interface} route-map {route_map} out",
        "exit",
        "end",
        "write"
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

    print(f"[OK] {container}: neighbor {interface} → LOCAL_PREF {local_pref}")

update_node_med(
    "clab-project-pe1",
    65020,
    65001,
    "10.1.11.1",
    10
)

update_node_med(
    "clab-project-pe2",
    65020,
    65001,
    "10.1.12.2",
    80
)

update_node_local_pref()