"""
Questo modulo gestisce l'Ingress Traffic Engineering dell'AS65020.
Utilizza un modello MILP per ripartire equamente i flussi provenienti dai CE tra i due PE disponibili,
minimizzando lo sbilanciamento del carico in ingresso.
"""

import json
import numpy as np
from pathlib import Path
from scipy.optimize import milp, LinearConstraint, Bounds

BASE_DIR = Path(__file__).resolve().parent
JSON_PATH = BASE_DIR / "traffic_matrix.json"

def load_traffic_matrix():
    """Carica la matrice dei flussi dal file JSON"""
    with open(JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    if "traffic_matrix_raw" not in data:
        raise KeyError("Nel JSON manca la chiave 'traffic_matrix_raw'.")

    return np.asarray(data["traffic_matrix_raw"], dtype=float)

def _solve_partitioning_milp(c):
    """
    Risolve il problema del partizionamento dei flussi tra PE1 e PE2
    Restituisce il vettore binario x (0 o 1) che minimizza lo sbilanciamento.
    """
    c = np.asarray(c, dtype=float).ravel()
    n = c.size
    if n == 0:
        return np.array([], dtype=int)

    Csum = float(c.sum())

    # Funzione obiettivo: minimizzare t (lo sbilanciamento)
    obj = np.zeros(n + 1, dtype=float)
    obj[-1] = 1.0 

    # Vincoli: 
    # S1 - S2 <= t  => 2*c*x - Csum <= t
    # S2 - S1 <= t  => Csum - 2*c*x <= t
    A = np.zeros((2, n + 1), dtype=float)
    A[0, :n] =  2.0 * c
    A[0, -1] = -1.0
    A[1, :n] = -2.0 * c
    A[1, -1] = -1.0

    constraints = LinearConstraint(A, [-np.inf, -np.inf], [Csum, -Csum])

    bounds = Bounds(
        lb=np.r_[np.zeros(n), 0.0],
        ub=np.r_[np.ones(n),  np.inf]
    )

    # Variabili binarie per la scelta del PE e continua per t
    integrality = np.r_[np.ones(n, dtype=int), 0]

    res = milp(c=obj, integrality=integrality, bounds=bounds, constraints=constraints)
    if not res.success:
        raise RuntimeError(f"milp fallito: status={res.status}, message={res.message}")

    return np.rint(res.x[:n]).astype(int)

def ottimizzazione_scelta_PE(matrice_input=None):
    """
    Wrapper principale:
    1) Carica la matrice.
    2) Linearizza la matrice in un vettore c.
    3) Chiama il solver per ottenere la x ottima (0/1).
    4) Trasforma x in una scelta PE (1/2).
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
    # x=0 -> PE1, x=1 -> PE2
    x = _solve_partitioning_milp(c)
    
    # 4. Trasformazione output
    # Mappatura:
    # Se x[i] = 0 -> 1 (PE1), se x[i] = 1 -> 2 (PE2)
    # Se invece c[i] = 0 (flusso nullo), assegniamo 0 (nessun PE)
    scelta_pe_ottima = np.where(c != 0, x + 1, 0)
    
    return scelta_pe_ottima

if __name__ == "__main__":
    risultato = ottimizzazione_scelta_PE()
    print("Vettore Scelta PE (1 o 2):", risultato)