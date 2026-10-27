import numpy as np
from scipy.stats import qmc

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
    if n == 0:
        return np.zeros((0, 3))
    
    # Halton sequence initialization
    sampler = qmc.Halton(d=2, seed=2025)
    points = sampler.random(n)
    circles = np.zeros((n, 3))
    circles[:, :2] = points
    circles[:, 2] = np.minimum(np.minimum(circles[:, 0], 1 - circles[:, 0]),
                              np.minimum(circles[:, 1], 1 - circles[:, 1])) * 0.2
    
    # Deterministic initialization and local refinement
    for i in range(n):
        x, y = circles[i, :2]
        max_r = min(x, 1-x, y, 1-y)
        
        # Local search to refine circle positions
        for _ in range(50):
            step_size = 0.05 * (1 - i/100)**2
            new_x = np.clip(x + np.random.uniform(-step_size, step_size), 0, 1)
            new_y = np.clip(y + np.random.uniform(-step_size, step_size), 0, 1)
            
            # Check for overlap with other circles and adjust if necessary
            valid = True
            for j in range(n):
                if i == j:
                    continue
                dist = np.sqrt((circles[j,0]-new_x)**2 + (circles[j,1]-new_y)**2)
                if dist < circles[j, 2] + max_r:
                    valid = False
                    break
            
            if valid:
                x, y = new_x, new_y
                max_r = min(x, 1-x, y, 1-y) * 0.2
        
        # Final adjustment to ensure all circles fit within the unit square
        circles[i] = np.clip(circles[i], 0, 1)
    
    return circles
