import json
import random
import time
from datetime import datetime

IN = ["N1", "N2"]
OUT = ["UP1", "UP2"]
LINK_CAPACITY = 1000

def generate_random_matrix():
    n1_volume = random.randint(400, 1100)
    n2_volume = random.randint(10, 150)

    volumes = {
        "N1": n1_volume,
        "N2": n2_volume
    }

    matrix = [
        [0, 0], # Riga N1
        [0, 0]  # Riga N2
    ]

    matrix[random.randint(0, 1)][random.randint(0, 1)] = volumes["N1"]
    matrix[random.randint(0, 1)][random.randint(0, 1)] = volumes["N2"]

    data = {
        "timestamp": datetime.now().isoformat(),
        "rows_labels": IN,
        "cols_labels": OUT,
        "link_capacity": LINK_CAPACITY,
        "matrix": matrix,
    }

    return data

data = generate_random_matrix()
matrix = data["matrix"]

load_up1 = matrix[0][0] + matrix[1][0]
load_up2 = matrix[0][1] + matrix[1][1]

print(f"Carico Totale UP1: {load_up1} Mbps")
print(f"Carico Totale UP2: {load_up2} Mbps")

if load_up1 > (data["link_capacity"] * 0.8):
    print("up1 is congested, increasing local pref on gw2")
