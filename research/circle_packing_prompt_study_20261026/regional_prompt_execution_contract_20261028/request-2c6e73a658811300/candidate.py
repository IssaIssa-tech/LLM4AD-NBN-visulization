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
                              np.minimum(circles[:, 1], 1 - circles[:, 1])) * 0.1
    
    # Simulated annealing with logarithmic cooling, simplified for brevity
    temperature = 0.5 / np.log(30000)
    levy_prob = 0.2 * (np.random.rand() < 0.9)
    
    for iteration in range(30000):
        if np.random.rand() < levy_prob:
            step_size = 0.4 * temperature
            new_x = np.clip(circles[iteration, 0] + np.random.normal(), 0, 1)
            new_y = np.clip(circles[iteration, 1] + np.random.normal(), 0, 1)
        else:
            step_size = 0.03 * (1 - iteration/30000)**3
            new_x = np.clip(circles[iteration, 0] + np.random.uniform(-step_size, step_size), 0, 1)
            new_y = np.clip(circles[iteration, 1] + np.random.uniform(-step_size, step_size), 0, 1)
        
        current_r = min(new_x, 1-new_x, new_y, 1-new_y)
        for j in range(n):
            if iteration == j:
                continue
            dist = np.sqrt((circles[j,0]-new_x)**2 + (circles[j,1]-new_y)**2)
            current_r = min(current_r, dist - circles[j,2])
        
        if current_r > circles[iteration, 2]:
            circles[iteration] = [new_x, new_y, current_r]
    
    return circles
