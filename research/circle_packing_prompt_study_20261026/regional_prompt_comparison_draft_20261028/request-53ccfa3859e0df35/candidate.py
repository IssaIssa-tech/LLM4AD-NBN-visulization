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
        
    Important: Set "all" random seeds to 2025, including the packages (such as scipy sub-packages) involving random seeds.
    """
    np.random.seed(2025)
    
    # Latin Hypercube initialization
    sampler = qmc.LatinHypercube(d=2, seed=2025)
    points = sampler.random(n)
    circles = np.zeros((n, 3))
    circles[:, :2] = points
    
    # Initial radius assignment based on distance from edges and neighbors
    for i in range(n):
        x, y = circles[i, :2]
        max_r = min(x, 1-x, y, 1-y)
        
        for j in range(n):
            if i == j:
                continue
            
            dist = np.sqrt((circles[j,0]-x)**2 + (circles[j,1]-y)**2)
            max_r = min(max_r, dist - circles[j,2])
        
        # Assign radius based on distance to edges and neighbors
        circles[i, 2] = max_r
    
    # Local search for each circle
    def objective(circles):
        return -np.sum(circles[:, 2])
    
    constraints = []
    for i in range(n):
        x, y, r = circles[i]
        
        # Radius expansion constraint
        constraints.append({'type': 'ineq', 'fun': lambda circles: np.sqrt((circles[0, 0]-x)**2 + (circles[0, 1]-y)**2) - (r + circles[0, 2])})
        for j in range(n):
            if i == j:
                continue
            dist = np.sqrt((circles[j,0]-x)**2 + (circles[j,1]-y)**2)
            constraints.append({'type': 'ineq', 'fun': lambda circles: dist - (r + circles[j, 2])})
    
    # Initial guess for local search
    initial_guess = np.random.rand(n, 3) * 0.5
    
    result = minimize(objective, initial_guess.flatten(), method='SLSQP', bounds=[(0, 1)]*6, constraints=constraints)
    
    if result.success:
        circles = result.x.reshape(-1, 3)
    
    return circles
