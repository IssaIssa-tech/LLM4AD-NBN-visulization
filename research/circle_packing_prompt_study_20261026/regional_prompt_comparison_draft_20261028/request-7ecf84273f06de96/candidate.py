import numpy as np
from scipy.optimize import minimize

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
    
    The algorithm uses a local search approach with perturbation and repair mechanisms. 
    It iteratively improves the positions of circles by randomly perturbing their centers within a small range,
    then repairing overlaps through a simple shift mechanism if necessary.
    """
    np.random.seed(2025)
    scipy_seed = 2025
    qmc_seed = 2025
    
    # Initialize random seeds for numpy and scipy sub-packages
    np.random.seed(qmc_seed)
    from scipy.stats import qmc
    qmc_gen = qmc.Halton(d=2, seed=scipy_seed)
    
    points = qmc_gen.random(n)
    circles = np.zeros((n, 3))
    circles[:, :2] = points
    
    # Perturb circle positions randomly within a small range
    for i in range(n):
        x, y = circles[i]
        r = np.minimum(x, 1-x, y, 1-y) * 0.1
        
        # Random perturbation with Metropolis criterion
        while True:
            new_x = max(0, min(1, x + np.random.normal()))
            new_y = max(0, min(1, y + np.random.normal()))
            
            if not any(np.sqrt((new_x - circle[0])**2 + (new_y - circle[1])**2) < r + circle[2] for circle in circles):
                break
        
        circles[i] = [new_x, new_y, r]
    
    # Repair overlaps by shifting circles
    def repair(circles):
        for i in range(n):
            x, y, r = circles[i]
            if any(np.sqrt((x - other[0])**2 + (y - other[1])**2) < r + other[2] for other in circles):
                dx, dy = np.random.uniform(-0.05, 0.05), np.random.uniform(-0.05, 0.05)
                x, y = max(0, min(1, x + dx)), max(0, min(1, y + dy))
                circles[i] = [x, y, r]
        return circles
    
    # Perform local search
    for _ in range(30000):
        repair(circles)
    
    return circles
