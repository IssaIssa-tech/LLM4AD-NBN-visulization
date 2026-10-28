import numpy as np
from scipy.optimize import differential_evolution

def pack_circles(n: int) -> np.ndarray:
    """
    Pack n circles in a unit square to maximize the sum of radii.
    
    Args:
        n: Number of circles to pack
    
    Returns:
        Numpy array of shape (n, 3) where each row is (x, y, radius)
        All values should be between 0 and 1
        Circles must not overlap
        
    Important: Set "all" random seeds to 2025, including the packages (such as scipy sub-packages) involving random seeds.
    
    The algorithm uses differential evolution for optimization. It iteratively refines the positions of circles by minimizing the distance between them and maximizing their radii within the unit square.
    """
    np.random.seed(2025)
    if n == 0:
        return np.zeros((0, 3))
    
    # Latin Hypercube initialization
    sampler = qmc.LatinHypercube(d=2, seed=2025)
    points = sampler.random(n)
    circles = np.zeros((n, 3))
    circles[:, :2] = points
    
    def objective_function(circles):
        for i in range(n):
            x, y, r = circles[i]
            if not (x >= 0 and x <= 1 and y >= 0 and y <= 1):
                return -np.inf
            for j in range(i + 1, n):
                dx, dy = circles[j][0] - circles[i][0], circles[j][1] - circles[i][1]
                dist = np.sqrt(dx**2 + dy**2)
                if dist < r + circles[j][2]:
                    return -np.inf
        total_radius = sum(circles[:, 2])
        return -total_radius
    
    result = differential_evolution(objective_function, [(0, 1), (0, 1), (-0.5, 0.5)], seed=2025)
    
    circles[:, 2] = np.clip(result['x'], 0, 0.49)  # Limiting the radius to be less than half of the unit square side
    
    return circles
