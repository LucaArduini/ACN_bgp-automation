"""
This script simulates the traffic monitoring and prediction system for AS65020.
Its task is to periodically generate the "Traffic Prediction Matrix" required 
by Task 3 of the project. The script:
1. Analyzes the topology (data.yaml) to identify source nodes (CE) and destination nodes (Router).
2. Generates a random traffic matrix (in Mbps) applying an unbalanced load policy 
   (one zero value per row) to test the optimizer's effectiveness.
3. Produces a text report on the console for debugging.
4. Saves the data to a JSON file (traffic_matrix.json) that will be consumed by the Manager
   for Traffic Engineering decisions.
"""

import yaml
import json
import random
import os
import sys
from datetime import datetime

# Path definition for input/output data
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
YAML_FILE = os.path.join(BASE_DIR, "..", "topology", "data.yaml")
JSON_FILE = os.path.join(BASE_DIR, "traffic_matrix.json")


def load_topology_data():
    """Analyzes data.yaml to map router roles in the network"""
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
    
    # Classify nodes based on the role defined in the topology
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
    
    # Sorting to ensure consistent matrix structure
    source_routers.sort()
    pe_routers.sort()
    destinations_routers.sort()

    print(f"--- Topology Discovery ---")
    print(f"Source Routers (CE):      {source_routers}")
    print(f"PE Routers:               {pe_routers}")
    print(f"Destination Routers:      {destinations_routers}")
    
    return source_routers, pe_routers, destinations_routers


def generate_traffic_matrix(source_routers, destinations_routers):
    """Generates a random traffic demand with unbalancing patterns"""
    matrix = []

    print(f"\n--- Generating Traffic Matrix (Source -> Destination) ---")
    
    for src in source_routers:
        row = []
        # Force one link to zero traffic to simulate non-uniform flows
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
    """Displays the generated matrix in a readable tabular format"""
    
    header = f"{'Source / Destination':<20} | " + " | ".join([f"{d:>8}" for d in destinations_routers])
    separator = "-" * len(header)
    
    print("\n" + separator)
    print(header)
    print(separator)
    
    for i, src in enumerate(source_routers):
        row_str = f"{src:<20} | "
        for val in matrix[i]:
            row_str += f"{val:>8} | "
        print(row_str)
        
    print(separator)
    print("\nTRAFFIC POLICY: 1 zero per row, others 1-100 Mbps.")


def save_to_json(source_routers, pe_routers, destinations_routers, matrix):
    """Serializes the matrix and metadata into JSON for the automation system"""
    
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
    """Main function for the traffic monitoring cycle"""
    # 1. Retrieve node lists
    source_routers, pe_routers, destinations_routers = load_topology_data()
    
    if not source_routers or not destinations_routers:
        print("[ERR] Missing Source or Destination nodes in topology.")
        return

    # 2. Create the load matrix
    matrix = generate_traffic_matrix(source_routers, destinations_routers)
    
    # 3. Console logging
    print_matrix(source_routers, destinations_routers, matrix)
    
    # 4. Export for the Manager
    save_to_json(source_routers, pe_routers, destinations_routers, matrix)

if __name__ == "__main__":
    generate_and_save_traffic_matrix()