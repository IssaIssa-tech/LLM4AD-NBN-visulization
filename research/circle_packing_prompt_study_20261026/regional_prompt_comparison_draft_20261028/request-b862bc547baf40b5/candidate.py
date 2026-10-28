import numpy as np
from scipy.optimize import minimize

def pack_circles(n: int) -> np.ndarray:
    """
    Pack n circles in a unit square to maximize sum of radii.
    
    Args:
        n: Number of circles to pack
    
    Returns:
        Numpy array of shape (n, 3) where each row is (x, y, radius)
        All values should be between 0 and 1
        Circles must not overlap
        
    Important: Set "all" random seeds to 2025, including the packages involving random seeds.
    """
    np.random.seed(2025)
    
    # Latin Hypercube initialization for circle placement
    sampler = qmc.LatinHypercube(d=2, seed=2025)
    points = sampler.random(n)
    circles = np.zeros((n, 3))
    circles[:, :2] = points
    
    # Function to calculate the sum of radii and constraints
    def objective(circles):
        return -np.sum(circles[:, 2])
    
    def constraint1(x):
        r1, x1, y1, r2, x2, y2 = x
        return np.sqrt((x1 - x2)**2 + (y1 - y2)**2) - (r1 + r2)
    
    def constraint2(x):
        return 1 - x[0] - x[1]
    
    # Constraints for the unit square boundary
    constraints = [{'type': 'ineq', 'fun': lambda x: np.sqrt((x[0])**2 + (x[1])**2) - 1},
                   {'type': 'ineq', 'fun': constraint1},
                   {'type': 'ineq', 'fun': constraint2}]
    
    # Initial guess for the circle centers and radii
    initial_guess = np.array([np.random.rand(3, n)]).T
    
    # Minimize the negative sum of radii to maximize it
    result = minimize(objective, initial_guess, method='SLSQP', constraints=constraints)
    
    if not result.success:
        raise ValueError("Optimization failed")
    
    circles[:, 2] = result.x.reshape(-1)
    return circles
