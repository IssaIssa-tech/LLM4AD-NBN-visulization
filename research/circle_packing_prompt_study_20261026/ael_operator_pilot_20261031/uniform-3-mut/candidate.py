import numpy as np
from scipy.spatial import Voronoi
from scipy.optimize import minimize
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
    
    # Voronoi-based optimization
    for _ in range(100):
        vor = Voronoi(circles[:, :2])
        for i in range(n):
            region = vor.regions[vor.point_region[i]]
            if -1 not in region and len(region) > 0:
                vertices = vor.vertices[region]
                center = np.mean(vertices, axis=0)
                circles[i, :2] = np.clip(center + np.random.normal(0, 0.01, 2), 0, 1)
    
    # Radius expansion with constraints
    for i in range(n):
        x, y, r = circles[i]
        max_r = min(x, 1-x, y, 1-y)
        for j in range(n):
            if i == j:
                continue
            dist = np.sqrt((circles[j,0]-x)**2 + (circles[j,1]-y)**2)
            max_r = min(max_r, dist - circles[j,2])
        circles[i, 2] = max_r * 0.95
    
    # Final refinement with Nelder-Mead
    def objective(positions):
        positions = positions.reshape(-1, 2)
        radii = np.zeros(n)
        for i in range(n):
            x, y = positions[i]
            max_r = min(x, 1-x, y, 1-y)
            for j in range(n):
                if i == j:
                    continue
                dist = np.sqrt((positions[j,0]-x)**2 + (positions[j,1]-y)**2)
                max_r = min(max_r, dist - radii[j])
            radii[i] = max_r
        return -np.sum(radii)
    
    bounds = [(0, 1)] * (2 * n)
    res = minimize(objective, circles[:, :2].flatten(), method='Nelder-Mead', 
                  bounds=bounds, options={'maxiter': 1000})
    
    final_pos = res.x.reshape(-1, 2)
    final_circles = np.zeros((n, 3))
    final_circles[:, :2] = final_pos
    for i in range(n):
        x, y = final_pos[i]
        max_r = min(x, 1-x, y, 1-y)
        for j in range(n):
            if i == j:
                continue
            dist = np.sqrt((final_pos[j,0]-x)**2 + (final_pos[j,1]-y)**2)
            max_r = min(max_r, dist - final_circles[j,2])
        final_circles[i, 2] = max_r
    
    return final_circles
