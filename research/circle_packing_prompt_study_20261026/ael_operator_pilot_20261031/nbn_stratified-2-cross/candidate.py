import numpy as np
from scipy.spatial import Voronoi, voronoi_plot_2d
from scipy.spatial.distance import cdist
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
    import numpy as np
    from scipy.spatial import Voronoi
    from scipy.spatial.distance import cdist
    from scipy.optimize import minimize
    
    np.random.seed(2025)
    if n == 0:
        return np.zeros((0, 3))
    
    # Latin Hypercube Sampling initialization
    sampler = qmc.LatinHypercube(d=2, seed=2025)
    points = sampler.random(n)
    circles = np.zeros((n, 3))
    circles[:, :2] = points
    circles[:, 2] = np.minimum(np.minimum(circles[:, 0], 1 - circles[:, 0]), np.minimum(circles[:, 1], 1 - circles[:, 1])) * 0.1
    
    def objective(x):
        centers = x.reshape(-1, 2)
        radii = np.minimum(np.minimum(centers[:, 0], 1 - centers[:, 0]), np.minimum(centers[:, 1], 1 - centers[:, 1]))
        for i in range(n):
            for j in range(i+1, n):
                dist = np.sqrt(np.sum((centers[i] - centers[j])**2))
                radii[i] = min(radii[i], dist - radii[j])
                radii[j] = min(radii[j], dist - radii[i])
        return -np.sum(radii)
    
    def constraint(x):
        centers = x.reshape(-1, 2)
        radii = np.minimum(np.minimum(centers[:, 0], 1 - centers[:, 0]), np.minimum(centers[:, 1], 1 - centers[:, 1]))
        constraints = []
        for i in range(n):
            for j in range(i+1, n):
                dist = np.sqrt(np.sum((centers[i] - centers[j])**2))
                constraints.append(dist - radii[i] - radii[j])
        return np.array(constraints)
    
    # Optimization with periodic boundary handling
    x0 = circles[:, :2].flatten()
    bounds = [(0, 1)] * (2 * n)
    cons = {'type': 'ineq', 'fun': constraint}
    
    res = minimize(objective, x0, method='SLSQP', bounds=bounds, constraints=cons, options={'maxiter': 10000})
    
    optimized_centers = res.x.reshape(-1, 2)
    radii = np.minimum(np.minimum(optimized_centers[:, 0], 1 - optimized_centers[:, 0]), np.minimum(optimized_centers[:, 1], 1 - optimized_centers[:, 1]))
    
    # Final radius adjustment
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            dist = np.sqrt(np.sum((optimized_centers[i] - optimized_centers[j])**2))
            radii[i] = min(radii[i], dist - radii[j])
    
    circles = np.column_stack((optimized_centers, radii))
    return circles
