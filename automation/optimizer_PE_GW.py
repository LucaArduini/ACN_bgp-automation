"""
This module manages the Egress Traffic Engineering of AS65020.
It uses a MILP model to select the optimal Gateway (GW1 or GW2),
minimizing the maximum percentage saturation of the upstream links (Minimax).
"""

import json
import numpy as np
from pathlib import Path
from scipy.optimize import milp, LinearConstraint, Bounds

BASE_DIR = Path(__file__).resolve().parent
JSON_PATH = BASE_DIR / "traffic_matrix.json"

def load_traffic_matrix():
    """
    Reads traffic_matrix.json. 
    Note: used only for stand-alone testing. The manager will directly pass the aggregated matrix.
    """
    with open(JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    if "traffic_matrix_raw" not in data:
        raise KeyError("'traffic_matrix_raw' key not found.")
    return np.asarray(data["traffic_matrix_raw"], dtype=float)


def _solve_minimax_saturation(c, cap1, cap2):
    """
    MILP Solver for load balancing based on percentage saturation.
    Determines which GW to use for each PE and destination 
    by minimizing the percentage saturation of the upstream links.
    """
    # Objective: Minimize t, where t is the maximum saturation between the two GWs.
    # Constraints:
    #   - (Traffic on GW1) / cap1 <= t  => Load_GW1 - cap1*t <= 0
    #   - (Traffic on GW2) / cap2 <= t  => Load_GW2 - cap2*t <= 0

    c = np.asarray(c, dtype=float).ravel()
    n = c.size
    if n == 0: return np.array([], dtype=int)

    c_sum = float(c.sum())

    # Variables: [x_1, x_2, ..., x_n, t]
    # We minimize only t (the last element)
    obj = np.zeros(n + 1, dtype=float)
    obj[-1] = 1.0 

    a_matrix = np.zeros((2, n + 1), dtype=float)
    
    # GW2 Constraint (where x=1): c*x - cap2*t <= 0
    a_matrix[0, :n] = c
    a_matrix[0, -1] = -float(cap2)
    
    # GW1 Constraint (where x=0): Load_GW1 = c_sum - c*x. 
    # c_sum - c*x <= cap1*t  => -c*x - cap1*t <= -c_sum
    a_matrix[1, :n] = -c
    a_matrix[1, -1] = -float(cap1)

    constraints = LinearConstraint(
        a_matrix, 
        lb=[-np.inf, -np.inf], 
        ub=[0.0, -c_sum]
    )

    bounds = Bounds(
        lb=np.r_[np.zeros(n), 0.0],
        ub=np.r_[np.ones(n),  np.inf]
    )

    integrality = np.r_[np.ones(n, dtype=int), 0]

    res = milp(c=obj, integrality=integrality, bounds=bounds, constraints=constraints)
    
    if not res.success:
        raise RuntimeError(f"GW Optimization failed: {res.message}")

    return np.rint(res.x[:n]).astype(int)


def optimize_gw_selection(cap1, cap2, input_matrix=None):
    """
    Main wrapper:
    1) Loads the matrix.
    2) Linearizes the matrix into a vector c.
    3) Calls the solver to obtain the optimal x (0/1).
    4) Transforms x into a GW choice (1/2).
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
    # x=0 -> GW1, x=1 -> GW2
    x = _solve_minimax_saturation(c, cap1, cap2)
    
    # 4. Output transformation
    # Mapping: c[i] = 0 -> 0, x=0 -> 1 (GW1), x=1 -> 2 (GW2)
    optimal_gw_selection = np.where(c != 0, x + 1, 0)
    
    return optimal_gw_selection

if __name__ == "__main__":
    result = optimize_gw_selection(1000, 1000)
    print("GW Selection Vector (1 or 2):", result)