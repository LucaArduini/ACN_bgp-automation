import yaml
import json
import random
import os
import sys
from datetime import datetime

# --- CONFIGURATION PATHS ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
YAML_FILE = os.path.join(BASE_DIR, "..", "topology", "data.yaml")
JSON_FILE = os.path.join(BASE_DIR, "traffic_matrix.json")


def load_topology_data():
    """
    Reads the YAML file and identifies:
    - Source Routers (role: ce)
    - PE Routers (role: pe)
    - Destination Routers (role: router)
    """
    if not os.path.exists(YAML_FILE):
        print(f"[ERR] File not found: {YAML_FILE}")
        sys.exit(1)

    try:
        with open(YAML_FILE, "r") as f:
            data = yaml.safe_load(f)
    except Exception as e:
        print(f"[ERR] Error parsing YAML: {e}")
        sys.exit(1)

    source_routers = []
    pe_routers = []
    destinations_routers = []
    
    if 'nodes' in data:
        for n in data['nodes']:
            role = n.get('role')
            name = n.get('name')
            
            if role == 'ce':
                source_routers.append(name)
            elif role == 'pe':
                pe_routers.append(name)
            elif role == 'router':
                destinations_routers.append(name)
    
    # Sorting for a consistent matrix layout
    source_routers.sort()
    pe_routers.sort()
    destinations_routers.sort()

    print(f"--- Topology Discovery ---")
    print(f"Source Routers (CE):      {source_routers}")
    print(f"PE Routers:               {pe_routers}")
    print(f"Destination Routers:      {destinations_routers}")
    
    return source_routers, pe_routers, destinations_routers


def generate_traffic_matrix(source_routers, destinations_routers):
    """
    Generates a matrix: Rows = Source Routers, Columns = Destination Routers.
    Rule: For each row, one column is 0, the others are random(1, 100).
    """
    matrix = []

    print(f"\n--- Generating Traffic Matrix (Source -> Destination) ---")
    
    for src in source_routers:
        row = []
        # Randomly select one index in the destinations list to be 0
        zero_index = random.randint(0, len(destinations_routers) - 1)
        
        for i in range(len(destinations_routers)):
            if i == zero_index:
                val = 0
            else:
                val = random.randint(1, 100)
            row.append(val)
        
        matrix.append(row)

    return matrix


def print_matrix(source_routers, destinations_routers, matrix):
    """Prints the matrix in a readable table format."""
    
    # Table Header
    header = f"{'Source / Destination':<20} | " + " | ".join([f"{d:>8}" for d in destinations_routers])
    separator = "-" * len(header)
    
    print("\n" + separator)
    print(header)
    print(separator)
    
    # Table Rows
    for i, src in enumerate(source_routers):
        row_str = f"{src:<20} | "
        for val in matrix[i]:
            row_str += f"{val:>8} | "
        print(row_str)
        
    print(separator)
    print("\nTRAFFIC POLICY: 1 zero per row, others 1-100 Mbps.")


def save_to_json(source_routers, pe_routers, destinations_routers, matrix):
    """Saves matrix and metadata to JSON with a human-readable timestamp."""
    
    # Build list of active flows
    flows = []
    for i, src in enumerate(source_routers):
        for j, dst in enumerate(destinations_routers):
            volume = matrix[i][j]
            if volume > 0:
                flows.append({
                    "from": src,
                    "to": dst,
                    "volume_mbps": volume
                })

    # Human readable timestamp
    readable_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    output_data = {
        "timestamp": readable_time,
        "topology_summary": {
            "source_routers": source_routers,
            "pe_routers": pe_routers,
            "destinations_routers": destinations_routers
        },
        "traffic_matrix_raw": matrix,
        "active_flows": flows
    }

    try:
        with open(JSON_FILE, "w", newline='\n') as f:
            json.dump(output_data, f, indent=4)
        print(f"\n[OK] Traffic matrix saved to: {JSON_FILE}")
    except Exception as e:
        print(f"\n[ERR] Failed to save JSON: {e}")


def generate_and_save_traffic_matrix():
    # 1. Extract lists from data.yaml
    source_routers, pe_routers, destinations_routers = load_topology_data()
    
    if not source_routers or not destinations_routers:
        print("[ERR] Missing Source or Destination nodes in topology.")
        return

    # 2. Generate the Source x Destination matrix
    matrix = generate_traffic_matrix(source_routers, destinations_routers)
    
    # 3. Print to console
    print_matrix(source_routers, destinations_routers, matrix)
    
    # 4. Save to automation/traffic_matrix.json
    save_to_json(source_routers, pe_routers, destinations_routers, matrix)

if __name__ == "__main__":
    generate_and_save_traffic_matrix()