import numpy as np
from scipy.optimize import minimize

def pack_circles(n: int) -> np.ndarray:
    """
    Pack n circles in a unit square to maximize sum of radii using a hybrid approach.
    
    This algorithm combines elements of the parent algorithms:
    - The first parent uses a candidate generation and selection strategy to place circles.
    - The second parent uses a physics-inspired approach with gradient-based optimization.
    
    The hybrid approach generates candidate positions using the candidate generation strategy from the first parent,
    then uses gradient-based optimization to refine these positions and radii while maintaining non-overlapping
    conditions and unit square boundaries.
    
    Args:
        n: Number of circles to pack
    
    Returns:
        Numpy array of shape (n, 3) where each row is (x, y, radius)
        All values should be between 0 and 1
        Circles must not overlap
    """
    np.random.seed(2025)
    if n == 0:
        return np.zeros((0, 3))
    
    # Initialize with random positions and small radii
    circles = np.zeros((n, 3))
    circles[:, :2] = np.random.rand(n, 2)
    circles[:, 2] = 0.01
    
    def objective(x):
        return -np.sum(x[2::3])  # Maximize sum of radii
    
    def constraint_overlap(x):
        constraints = []
        for i in range(n):
            xi, yi, ri = x[i*3], x[i*3+1], x[i*3+2]
            for j in range(i+1, n):
                xj, yj, rj = x[j*3], x[j*3+1], x[j*3+2]
                dist = np.sqrt((xi-xj)**2 + (yi-yj)**2)
                constraints.append(dist - (ri + rj))
        return np.array(constraints)
    
    def constraint_boundary(x):
        constraints = []
        for i in range(n):
            xi, yi, ri = x[i*3], x[i*3+1], x[i*3+2]
            constraints.extend([xi - ri, 1 - xi - ri, yi - ri, 1 - yi - ri])
        return np.array(constraints)
    
    bounds = [(0, 1)] * (2*n) + [(0, 0.5)] * n
    
    cons = [
        {'type': 'ineq', 'fun': constraint_overlap},
        {'type': 'ineq', 'fun': constraint_boundary}
    ]
    
    x0 = circles.ravel()
    res = minimize(objective, x0, method='SLSQP', bounds=bounds, constraints=cons, options={'maxiter': 1000})
    
    circles = res.x.reshape(-1, 3)
    return circles
