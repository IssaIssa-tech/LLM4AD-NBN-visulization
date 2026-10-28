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
    
    # Sobol sequence initialization
    sampler = qmc.Sobol(d=2, seed=2025)
    points = sampler.random(n)
    circles = np.zeros((n, 3))
    circles[:, :2] = points
    
    # Initial placement with deterministic random seeds for reproducibility
    circles[:, 2] = np.minimum(np.minimum(circles[:, 0], 1 - circles[:, 0]),
                              np.minimum(circles[:, 1], 1 - circles[:, 1])) * 0.2

    # Simulated annealing with exponential cooling and local search for improvement
    for iteration in range(4000):
        temperature = 0.5 * np.exp(-iteration / 100)
        
        for i in range(n):
            x, y, r = circles[i]
            
            # Radius expansion
            max_r = min(x, 1-x, y, 1-y)
            for j in range(n):
                if i == j:
                    continue
                dist = np.sqrt((circles[j,0]-x)**2 + (circles[j,1]-y)**2)
                max_r = min(max_r, dist - circles[j,2])
            
            # Local search to improve placement
            for _ in range(5):
                if np.random.random() < 0.9:
                    step_size = 0.3 * temperature
                    new_x = np.clip(x + np.random.normal(0, step_size) * np.random.standard_cauchy(), 0, 1)
                    new_y = np.clip(y + np.random.normal(0, step_size) * np.random.standard_cauchy(), 0, 1)
                else:
                    step_size = 0.04 * (1 - iteration/200)**2
                    new_x = np.clip(x + np.random.uniform(-step_size, step_size), 0, 1)
                    new_y = np.clip(y + np.random.uniform(-step_size, step_size), 0, 1)
                
                current_r = min(new_x, 1-new_x, new_y, 1-new_y)
                for j in range(n):
                    if i == j:
                        continue
                    dist = np.sqrt((circles[j,0]-new_x)**2 + (circles[j,1]-new_y)**2)
                    current_r = min(current_r, dist - circles[j,2])
                
                # Acceptance with Metropolis criterion
                if current_r > r or np.random.random() < np.exp((current_r - r)/temperature):
                    if current_r > max_r:
                        circles[i] = (new_x, new_y, current_r)
    
    return circles
