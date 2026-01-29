import jinja2
import os
import yaml
import sys
import ipaddress
from jinja2 import Environment, FileSystemLoader


# --- FUNZIONE DI VALIDAZIONE ---
def validate_data(data):
    """
    Esegue controlli di integrità sui dati della topologia:
    1. Nessun IP duplicato nella rete.
    2. Coerenza delle subnet sui link (stessa rete, maschera valida).
    """
    print("--- Avvio Validazione Dati ---")
    errors = []
    
    # Mappa per tracciare IP -> (Nodo, Interfaccia)
    seen_ips = {}
    # Mappa per facilitare il controllo dei link: "nodo:interfaccia" -> Oggetto IPv4Interface
    interface_map = {}

    # 1. CONTROLLO DUPLICATI E POPOLAZIONE MAPPE
    for node in data['nodes']:
        # Controlla IP di gestione (se presente a livello root del nodo)
        if 'ipv4_address' in node and node.get('role') != 'host': 
            # Nota: saltiamo gli host che potrebbero non avere maschera definita qui
            pass 

        if 'interfaces' in node:
            for iface in node['interfaces']:
                # Saltiamo interfacce senza IP (es. L2 puri)
                if 'ipv4_address' not in iface or 'ipv4_mask' not in iface:
                    continue
                
                ip_str = iface['ipv4_address']
                mask_str = iface['ipv4_mask']
                full_addr = f"{ip_str}{mask_str}"

                # Check Duplicati
                if ip_str in seen_ips:
                    prev_node, prev_iface = seen_ips[ip_str]
                    errors.append(f"[DUPLICATE IP] L'indirizzo {ip_str} è usato sia su {prev_node}:{prev_iface} che su {node['name']}:{iface['name']}")
                else:
                    seen_ips[ip_str] = (node['name'], iface['name'])

                # Salviamo l'oggetto interfaccia per i controlli successivi sui link
                try:
                    # ip_interface gestisce automaticamente calcoli di rete (es. 192.168.1.1/24)
                    if_obj = ipaddress.ip_interface(full_addr)
                    key = f"{node['name']}:{iface['name']}"
                    interface_map[key] = if_obj
                except ValueError as e:
                    errors.append(f"[INVALID IP] {node['name']}:{iface['name']} ha un IP non valido: {full_addr}. Errore: {e}")

    # 2. CONTROLLO LINK E DIMENSIONE SUBNET
    for link in data['links']:
        # Costruiamo le chiavi per cercare nella mappa (es. "pe1:eth1")
        endpoint_a = f"{link['a']}:{link['a_port']}"
        endpoint_b = f"{link['b']}:{link['b_port']}"

        # Se entrambe le estremità hanno un IP configurato, controlliamo la coerenza
        if endpoint_a in interface_map and endpoint_b in interface_map:
            ip_a = interface_map[endpoint_a]
            ip_b = interface_map[endpoint_b]

            # A. Controllo Corrispondenza Network
            # Se uno è 10.0.1.1/24 e l'altro 10.0.2.1/24 -> ERRORE
            if ip_a.network != ip_b.network:
                errors.append(f"[SUBNET MISMATCH] Link tra {endpoint_a} e {endpoint_b}: Le subnet non coincidono ({ip_a.network} vs {ip_b.network})")

            # B. Controllo Dimensione Maschera (Mask Size)
            # Per un link punto-punto servono almeno 2 IP disponibili.
            # Una /32 ha 1 solo IP -> Errore. Una /31 (2 IP) o /30 (4 IP) vanno bene.
            if ip_a.network.num_addresses < 2:
                 errors.append(f"[MASK TOO SMALL] Link tra {endpoint_a} e {endpoint_b}: La maschera {ip_a.with_netmask} è troppo piccola per un link (supporta solo {ip_a.network.num_addresses} IP)")

    # 3. ESITO
    if errors:
        print("!!! TROVATI ERRORI CRITICI NEI DATI !!!")
        for e in errors:
            print(f" - {e}")
        print("Generazione interrotta.")
        sys.exit(1) # Esce con codice di errore
    else:
        print("Validazione superata: Nessun duplicato e subnet coerenti.")


# -------------------- MAIN SCRIPT --------------------

# --- GESTIONE PERCORSI ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, "..", "templates")
TOPOLOGY_DIR = os.path.join(BASE_DIR, "..", "topology")

data_path = os.path.join(TOPOLOGY_DIR, "data.yaml")
output_path = os.path.join(TOPOLOGY_DIR, "network.clab.yml")

# --- SETUP JINJA2 ---
environment = Environment(
    loader=FileSystemLoader(TEMPLATES_DIR)
)
template = environment.get_template("topology.j2")

# --- LETTURA DATI ---
with open(data_path, 'r') as f:
    data = yaml.safe_load(f)

# --- VALIDAZIONE DATI ---
validate_data(data)

# --- GENERAZIONE FILE ---
content = template.render(nodes=data['nodes'], links=data['links'])
with open(output_path, 'w') as f:
    f.write(content)

print("Container lab network yaml file generated!")