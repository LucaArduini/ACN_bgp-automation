
import random
import yaml
import os
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
YAML_FILE = os.path.join(BASE_DIR, "..", "topology", "data.yaml")

LINK_CAPACITY = 1000

def load_topology_data():
    """Legge il file YAML e identifica le sorgenti (Righe) e le uscite (Colonne)"""
    if not os.path.exists(YAML_FILE):
        print(f"[ERR] File non trovato: {YAML_FILE}")
        return [], []

    try:
        with open(YAML_FILE, "r") as f:
            data = yaml.safe_load(f)
    except Exception as e:
        print(f"[ERR] Errore parsing YAML: {e}")
        return [], []

    in_nodes = []
    out_nodes = []
    
    if 'nodes' in data:
        in_roles = ['router', 'ce', 'host']

        out_roles = ['pe', 'up']
        
        in_nodes = [n['name'] for n in data['nodes'] 
                         if n.get('role') in in_roles]
        
        out_nodes = [n['name'] for n in data['nodes'] 
                         if n.get('role') in out_roles]
    
    return in_nodes, out_nodes

def generate_random_matrix(rows_labels, cols_labels):
    matrix = [[0] * len(cols_labels) for _ in range(len(rows_labels))]

    for i, source in enumerate(rows_labels):
        name = source.lower()
    
        if "r3" in name:
            volume = random.randint(600, 1500)
            
        elif "n1" in name:
            volume = random.randint(200, 500)
            
        elif "ce" in name:
            volume = random.randint(300, 900)
            
        else:
            volume = random.randint(10, 50)

        if len(cols_labels) > 0:
            chosen_exit_index = random.randint(0, len(cols_labels) - 1)
            matrix[i][chosen_exit_index] = volume

    print(f"{'Source':<8} | " + " | ".join([f"{col:>8}" for col in cols_labels]))
    print("-" * (12 + 11 * len(cols_labels) + 15))
    
    for i, row_label in enumerate(rows_labels):
        row_str = f"{row_label:<8} | "
    

        for val in matrix[i]:
            val_str = f"{val:>8}"
            val_str += " "
            row_str += val_str + "| "
            
        print(row_str)
    print("-" * (12 + 11 * len(cols_labels) + 15))

    data = {
        "timestamp": datetime.now().isoformat(),
        "rows_labels": rows_labels,
        "cols_labels": cols_labels,
        "link_capacity": LINK_CAPACITY,
        "matrix": matrix,
    }

    return data

IN_NODES, OUT_NODES = load_topology_data()

data = generate_random_matrix(IN_NODES, OUT_NODES)
matrix = data["matrix"]

loads = [0] * len(OUT_NODES)

for row in matrix:
    for col_idx, val in enumerate(row):
        loads[col_idx] += val

for i, node_name in enumerate(OUT_NODES):
    load = loads[i]
        
    print(f"Link to {node_name}: {load:>4} Mbps")
