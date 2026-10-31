import numpy as np
from scipy.spatial import Voronoi, voronoi_plot_2d
from scipy.spatial.distance import cdist
from scipy.optimize import minimize

def pack_circles(n: int) -> np.ndarray:
    """
    Pack n circles in a unit square to maximize sum of radii using a hybrid approach.
    
    Args:
        n: Number of circles to pack
    
    Returns:
        Numpy array of shape (n, 3) where each row is (x, y, radius)
        All values should be between 0 and 1
        Circles must not overlap
    """
    np.random.seed(2025)
    if n == 0:
        return np.zeros((0, 3))
    
    # Initialize with random points and small radii
    points = np.random.rand(n, 2)
    radii = np.full(n, 0.01)
    
    def objective(vars):
        points = vars.reshape(n, 2)
        radii = np.sqrt((vars[n:] ** 2) / 2)
        dist_matrix = cdist(points, points) + np.diag(np.full(n, np.inf))
        min_dists = dist_matrix.min(axis=1)
        return -np.sum(radii)  # Negative because we will use a minimizer
    
    def constraint(vars):
        points = vars.reshape(n, 2)
        radii = np.sqrt((vars[n:] ** 2) / 2)
        dist_matrix = cdist(points, points) + np.diag(np.full(n, np.inf))
        min_dists = dist_matrix.min(axis=1)
        return min_dists - radii
    
    cons = {'type': 'ineq', 'fun': constraint}
    bounds = [(0, 1)] * (2 * n)
    x0 = np.concatenate((points.flatten(), radii ** 2))
    
    # Use a more efficient optimization method with a smaller maxiter
    result = minimize(objective, x0, method='SLSQP', bounds=bounds, constraints=cons, options={'maxiter': 500})
    
    points = result.x[:2 * n].reshape(n, 2)
    radii = np.sqrt((result.x[2 * n:] ** 2) / 2)
    
    circles = np.column_stack((points, radii))
    return circles
