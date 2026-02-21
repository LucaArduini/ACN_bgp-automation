"""
This module manages the Ingress Traffic Engineering of AS65020.
It uses a MILP model to evenly distribute flows coming from CEs between the two available PEs,
minimizing the inbound load imbalance.
"""

import json
import numpy as np
from pathlib import Path
from scipy.optimize import milp, LinearConstraint, Bounds

BASE_DIR = Path(__file__).resolve().parent
JSON_PATH = BASE_DIR / "traffic_matrix.json"

def load_traffic_matrix():
    """Loads the flow matrix from the JSON file"""
    with open(JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    if "traffic_matrix_raw" not in data:
        raise KeyError("The key 'traffic_matrix_raw' is missing from the JSON.")

    return np.asarray(data["traffic_matrix_raw"], dtype=float)

def _solve_partitioning_milp(c):
    """
    Solves the flow partitioning problem between PE1 and PE2.
    Returns the binary vector x (0 or 1) that minimizes the imbalance.
    """
    c = np.asarray(c, dtype=float).ravel()
    n = c.size
    if n == 0:
        return np.array([], dtype=int)

    c_sum = float(c.sum())

    # Objective function: minimize t (the imbalance)
    obj = np.zeros(n + 1, dtype=float)
    obj[-1] = 1.0 

    # Constraints: 
    # S1 - S2 <= t  => 2*c*x - c_sum <= t
    # S2 - S1 <= t  => c_sum - 2*c*x <= t
    a_matrix = np.zeros((2, n + 1), dtype=float)
    a_matrix[0, :n] =  2.0 * c
    a_matrix[0, -1] = -1.0
    a_matrix[1, :n] = -2.0 * c
    a_matrix[1, -1] = -1.0

    constraints = LinearConstraint(a_matrix, [-np.inf, -np.inf], [c_sum, -c_sum])

    bounds = Bounds(
        lb=np.r_[np.zeros(n), 0.0],
        ub=np.r_[np.ones(n),  np.inf]
    )

    # Binary variables for PE selection and continuous variable for t
    integrality = np.r_[np.ones(n, dtype=int), 0]

    res = milp(c=obj, integrality=integrality, bounds=bounds, constraints=constraints)
    if not res.success:
        raise RuntimeError(f"milp failed: status={res.status}, message={res.message}")

    return np.rint(res.x[:n]).astype(int)

def optimize_pe_selection(input_matrix=None):
    """
    Main wrapper:
    1) Loads the matrix.
    2) Linearizes the matrix into a vector c.
    3) Calls the solver to obtain the optimal x (0/1).
    4) Transforms x into a PE choice (1/2).
    5) Returns the resulting vector.
    """
    # 1. Obtain the matrix (from input or file)
    if input_matrix is not None:
        matrix = np.asarray(input_matrix, dtype=float)
    else:
        matrix = load_traffic_matrix()
    
    # 2. Linearization (Transforms 2D to 1D for calculations)
    c = matrix.reshape(-1, order="C")
    
    # 3. Solver
    # x=0 -> PE1, x=1 -> PE2
    x = _solve_partitioning_milp(c)
    
    # 4. Output transformation
    # Mapping:
    # If x[i] = 0 -> 1 (PE1), if x[i] = 1 -> 2 (PE2)
    # If c[i] = 0 (null flow), assign 0 (no PE)
    optimal_pe_selection = np.where(c != 0, x + 1, 0)
    
    return optimal_pe_selection

if __name__ == "__main__":
    result = optimize_pe_selection()
    print("PE Selection Vector (1 or 2):", result)