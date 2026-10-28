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
    
    Modified differential evolution algorithm for circle packing optimization.
    """
    np.random.seed(2025)
    if n == 0:
        return np.zeros((0, 3))
    
    # Latin Hypercube initialization
    sampler = qmc.LatinHypercube(d=2, seed=2025)
    points = sampler.random(n)
    circles = np.zeros((n, 3))
    circles[:, :2] = points
    
    # Differential Evolution for local search and repair
    def objective_function(circles):
        sum_radii = np.sum(circles[:, 2])
        return -sum_radii

    bounds = [(0, 1), (0, 1)] * n + [(-0.5, 0.5)] * n
    
    result = differential_evolution(objective_function, bounds)
    
    circles[:, 2] = np.clip(result.pos, 0, 0.49)  # Limit radii to be less than half the side length of unit square
    return circles
