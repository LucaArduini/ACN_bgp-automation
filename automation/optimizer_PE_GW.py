"""
Questo modulo gestisce l'Egress Traffic Engineering dell'AS65020.
Utilizza un modello MILP per selezionare il Gateway (GW1 o GW2) ottimale,
minimizzando la saturazione percentuale massima dei link di upstream (Minimax).
"""

import json
import numpy as np
from pathlib import Path
from scipy.optimize import milp, LinearConstraint, Bounds

BASE_DIR = Path(__file__).resolve().parent
JSON_PATH = BASE_DIR / "traffic_matrix.json"

def load_traffic_matrix():
    """
    Legge traffic_matrix.json. 
    Nota: viene usato solo per test stand-alone. Il manager passerà direttamente la matrice aggregata.
    """
    with open(JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    if "traffic_matrix_raw" not in data:
        raise KeyError("Chiave 'traffic_matrix_raw' non trovata.")
    return np.asarray(data["traffic_matrix_raw"], dtype=float)


def _solve_minimax_saturation(c, cap1, cap2):
    """
    Solver MILP per il bilanciamento del carico basato sulla saturazione percentuale.
    Determina per ogni PE e destinazione quale GW utilizzare 
    minimizzando la saturazione percentuale dei link di upstream.
    """
    # Obiettivo: Minimizzare t, dove t è la massima saturazione tra i due GW.
    # Vincoli:
    #   - (Traffico su GW1) / cap1 <= t  => Load_GW1 - cap1*t <= 0
    #   - (Traffico su GW2) / cap2 <= t  => Load_GW2 - cap2*t <= 0

    c = np.asarray(c, dtype=float).ravel()
    n = c.size
    if n == 0: return np.array([], dtype=int)

    Csum = float(c.sum())

    # Variabili: [x_1, x_2, ..., x_n, t]
    # Minimizziamo solo t (l'ultimo elemento)
    obj = np.zeros(n + 1, dtype=float)
    obj[-1] = 1.0 

    A = np.zeros((2, n + 1), dtype=float)
    
    # Vincolo GW2 (dove x=1): c*x - cap2*t <= 0
    A[0, :n] = c
    A[0, -1] = -float(cap2)
    
    # Vincolo GW1 (dove x=0): Load_GW1 = Csum - c*x. 
    # Csum - c*x <= cap1*t  => -c*x - cap1*t <= -Csum
    A[1, :n] = -c
    A[1, -1] = -float(cap1)

    constraints = LinearConstraint(
        A, 
        lb=[-np.inf, -np.inf], 
        ub=[0.0, -Csum]
    )

    bounds = Bounds(
        lb=np.r_[np.zeros(n), 0.0],
        ub=np.r_[np.ones(n),  np.inf]
    )

    integrality = np.r_[np.ones(n, dtype=int), 0]

    res = milp(c=obj, integrality=integrality, bounds=bounds, constraints=constraints)
    
    if not res.success:
        raise RuntimeError(f"Ottimizzazione GW fallita: {res.message}")

    return np.rint(res.x[:n]).astype(int)


def ottimizzazione_scelta_GW(cap1, cap2, matrice_input=None):
    """
    Wrapper principale:
    1) Carica la matrice.
    2) Linearizza la matrice in un vettore c.
    3) Chiama il solver per ottenere la x ottima (0/1).
    4) Trasforma x in una scelta GW (1/2).
    5) Restituisce il vettore risultante.
    """
    # 1. Otteniamo la matrice (da input o da file)
    if matrice_input is not None:
        matrice = np.asarray(matrice_input, dtype=float)
    else:
        matrice = load_traffic_matrix()
    
    # 2. Linearizzazione (Trasforma 2D in 1D per i calcoli)
    c = matrice.reshape(-1, order="C")
    
    # 3. Solver
    # x=0 -> GW1, x=1 -> GW2
    x = _solve_minimax_saturation(c, cap1, cap2)
    
    # 4. Trasformazione output
    # Mappatura: c[i] = 0 -> 0, x=0 -> 1 (GW1), x=1 -> 2 (GW2)
    scelta_gw_ottima = np.where(c != 0, x + 1, 0)
    
    return scelta_gw_ottima

if __name__ == "__main__":
    risultato = ottimizzazione_scelta_GW(1000, 1000)
    print("Vettore Scelta GW (1 o 2):", risultato)