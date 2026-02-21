"""
Questo modulo gestisce l'applicazione pratica delle policy BGP sui router FRR.
Traduce le decisioni dell'ottimizzatore in comandi CLI (vtysh) per modificare 
dinamicamente MED e Local Preference tramite l'uso di Route Maps.
"""

import subprocess
import shlex
import yaml
import os

# --- CONFIGURAZIONE PERCORSI ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
YAML_FILE = os.path.join(BASE_DIR, "..", "topology", "data.yaml")

def load_topology(file_path=YAML_FILE):
    with open(file_path, 'r') as f:
        return yaml.safe_load(f)

def get_ipv4_address(node_name):
    """Recupera l'indirizzo IP identificativo di un nodo dal file di dati"""
    topo = load_topology()
    node = next((n for n in topo['nodes'] if n['name'] == node_name), None)
    if not node or 'ipv4_address' not in node:
        return None
    return str(node['ipv4_address'])

def get_bgp_config(topo, node_name, neighbor_name):
    """
    Recupera info BGP per sessioni eBGP (CE-PE)
    Trova l'indirizzo IP di un vicino BGP analizzando i link fisici della topologia.
    Restituisce il nome del container, ASN locale e IP del vicino.
    """
    node = next((n for n in topo['nodes'] if n['name'] == node_name), None)
    neighbor = next((n for n in topo['nodes'] if n['name'] == neighbor_name), None)

    if not node or not neighbor:
        raise ValueError(f"Nodo {node_name} o {neighbor_name} non trovato")
    
    local_asn = node['bgp']['asn']
    neighbor_ip = None

    # Scansione di tutti i link per trovare quello che unisce i due router specificati
    for link in topo['links']:
        # Se il nodo corrente è il lato 'a', cerchiamo l'IP del lato 'b'
        if link['a'] == node_name and link['b'] == neighbor_name:
            neighbor_port = link['b_port']
            neighbor_iface = next(i for i in neighbor['interfaces'] if i['name'] == neighbor_port)
            neighbor_ip = neighbor_iface['ipv4_address']
            break
        # Se il nodo corrente è il lato 'b', cerchiamo l'IP del lato 'a'
        elif link['b'] == node_name and link['a'] == neighbor_name:
            neighbor_port = link['a_port']
            neighbor_iface = next(i for i in neighbor['interfaces'] if i['name'] == neighbor_port)
            neighbor_ip = neighbor_iface['ipv4_address']
            break
            
    if not neighbor_ip:
        raise ValueError(f"Nessuna sessione BGP tra {node_name} e {neighbor_name}")

    container_name = f"clab-project-{node_name}"
    return container_name, local_asn, neighbor_ip

def get_local_config(topo, node_name, neighbor_name):
    """
    Recupera info BGP per sessioni iBGP (PE-GW)
    """
    node = next(n for n in topo['nodes'] if n['name'] == node_name)
    neighbor = next(n for n in topo['nodes'] if n['name'] == neighbor_name)
    
    neighbor_ip = None
    # Cerca l'IP del vicino cercando l'interfaccia corretta
    neighbor_ip = neighbor['interfaces'][0]['ipv4_address']
    container_name = f"clab-project-{node_name}"
    local_asn = node['bgp']['asn']

    return container_name, local_asn, neighbor_ip

def update_node_med(container, local_as, neighbor_ip, med, prefix, seq):
    """
    Configura il MED via vtysh per influenzare il traffico in ingresso (Inbound TE).
    Procedura: 
    1. Isola il traffico tramite Prefix-List.
    2. Crea una Route-Map che applica la metrica al prefisso matchato.
    3. Associa la Route-Map al neighbor BGP specifico in uscita (out).
    """
    # Trasformiamo l'IP in una stringa sicura per i nomi delle configurazioni FRR
    safe_ip = neighbor_ip.replace('.', '_').replace('/', '')
    route_map = f"RM_MED_OUT_{safe_ip}"
    prefix_list = f"PL_{prefix.replace('.', '_').replace('/', '_')}"

    cmds = [
        "conf t",
        # Creazione della prefix-list per identificare la destinazione specifica
        f"ip prefix-list {prefix_list} seq {seq} permit {prefix}",
        # Definizione della route-map: se il prefisso corrisponde, imposta il MED
        f"route-map {route_map} permit {seq}",
        f"  match ip address prefix-list {prefix_list}",
        f"  set metric {med}",
        "exit",
        # Regola finale permissiva (catch-all) per non filtrare il resto del traffico BGP
        f"route-map {route_map} permit 65535",
        "exit",
        # Applicazione della policy alla sessione BGP verso il vicino
        f"router bgp {local_as}",
        f"  neighbor {neighbor_ip} route-map {route_map} out",
        "exit",
        "end"
    ]

    # Composizione del comando finale per Docker exec
    vtysh_cmd = ["docker", "exec", container, "vtysh"]
    for c in cmds:
        vtysh_cmd.extend(["-c", c])
    
    try:
        # Invio dei comandi a FRR
        subprocess.run(vtysh_cmd, check=True, stdout=subprocess.DEVNULL)
        # Notifica ai vicini delle modifiche tramite BGP Soft Reset (senza interrompere la sessione)
        subprocess.run(["docker", "exec", container, "vtysh", "-c", 
                    f"clear bgp ipv4 unicast {neighbor_ip} soft out"], 
                    check=True, stdout=subprocess.DEVNULL)
    except subprocess.CalledProcessError as e:
        print(f"[ERR] Errore esecuzione comando su {container}: {e}")

def update_node_local_pref(container, local_as, neighbor_ip, local_pref, prefix, seq):
    """
    Configura la Local Preference per influenzare il traffico in uscita (Outbound TE).
    A differenza del MED, la Local Preference viene applicata sugli annunci ricevuti (in).
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
        # Permette il traffico che non deve essere modificato
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
        # Forza il ricalcolo delle rotte migliori basato sulla nuova Local Preference
        subprocess.run(["docker", "exec", container, "vtysh", "-c", 
                    f"clear bgp ipv4 unicast {neighbor_ip} soft in"], 
                    check=True, stdout=subprocess.DEVNULL)
    except subprocess.CalledProcessError as e:
        print(f"[ERR] Errore esecuzione comando su {container}: {e}")

# --- WRAPPERS PUBBLICI ---

def set_med(node, neighbor, med, destination, seq):
    """Interfaccia semplificata per applicare Inbound Traffic Engineering"""
    topo = load_topology()
    dest_ip = get_ipv4_address(destination)
    if not dest_ip:
        print(f"[ERR] Destinazione {destination} non trovata")
        return
    
    prefix = dest_ip + "/32"
    try:
        container, local_as, neighbor_ip = get_bgp_config(topo, node, neighbor)
        update_node_med(container, local_as, neighbor_ip, med, prefix, seq)
    except Exception as e:
        print(f"[ERR] set_med {node}->{neighbor} fallito: {e}")

def set_local_pref(node, neighbor, local_pref, destination, seq):
    """Interfaccia semplificata per applicare Outbound Traffic Engineering"""
    topo = load_topology()
    dest_ip = get_ipv4_address(destination)
    if not dest_ip:
        print(f"[ERR] Destinazione {destination} non trovata")
        return

    prefix = dest_ip + "/32"
    try:
        container, local_as, neighbor_ip = get_local_config(topo, node, neighbor)
        update_node_local_pref(container, local_as, neighbor_ip, local_pref, prefix, seq)
    except Exception as e:
        print(f"[ERR] set_local_pref {node}<-{neighbor} fallito: {e}")