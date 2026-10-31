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
    
    # Latin Hypercube initialization
    sampler = qmc.LatinHypercube(d=2, seed=2025)
    points = sampler.random(n)
    circles = np.zeros((n, 3))
    circles[:, :2] = points
    circles[:, 2] = np.minimum(np.minimum(circles[:, 0], 1 - circles[:, 0]),
                              np.minimum(circles[:, 1], 1 - circles[:, 1])) * 0.15
    
    # Improved local search using a grid-based approach
    grid_size = 0.05
    grid = np.arange(0, 1 + grid_size, grid_size)
    for i in range(n):
        x, y, r = circles[i]
        best_r = r
        best_pos = (x, y, r)
        for gx in grid:
            for gy in grid:
                if abs(gx - x) < grid_size and abs(gy - y) < grid_size:
                    continue
                current_r = min(gx, 1-gx, gy, 1-gy)
                for j in range(n):
                    if i == j:
                        continue
                    dist = np.sqrt((circles[j,0]-gx)**2 + (circles[j,1]-gy)**2)
                    current_r = min(current_r, dist - circles[j,2])
                if current_r > best_r:
                    best_r = current_r
                    best_pos = (gx, gy, current_r)
        circles[i] = best_pos
    
    return circles
