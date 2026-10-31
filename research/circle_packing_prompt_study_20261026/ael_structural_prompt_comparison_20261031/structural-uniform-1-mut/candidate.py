import numpy as np
from scipy.spatial import Voronoi, voronoi_plot_2d
from scipy.optimize import minimize
from scipy.spatial.distance import cdist

def pack_circles(n: int) -> np.ndarray:
    """
    Pack n circles in a unit square to maximize sum of radii.
    
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
    
    # Initial placement using Voronoi diagram
    points = np.random.rand(n, 2)
    vor = Voronoi(points)
    regions = vor.regions
    vertices = vor.vertices
    
    # Filter out infinite regions
    finite_regions = [region for region in regions if -1 not in region]
    region_points = [vertices[region] for region in finite_regions]
    
    # Calculate initial radii based on Voronoi regions
    radii = np.array([min(np.linalg.norm(point - vertex) for vertex in region_points[i]) for i in range(len(region_points))])
    
    # Optimization function
    def objective(x):
        centers = x.reshape(-1, 2)
        dists = cdist(centers, centers) + np.eye(len(centers))
        radii = np.minimum(np.minimum(centers[:,0], 1-centers[:,0]), np.minimum(centers[:,1], 1-centers[:,1]))
        radii = np.minimum(radii, (dists - radii).min(axis=1))
        return -radii.sum()
    
    # L-BFGS-B optimization
    bounds = [(0, 1)] * (2 * n)
    res = minimize(objective, points.flatten(), method='L-BFGS-B', bounds=bounds, options={'maxiter': 1000})
    
    centers = res.x.reshape(-1, 2)
    radii = np.minimum(np.minimum(centers[:,0], 1-centers[:,0]), np.minimum(centers[:,1], 1-centers[:,1]))
    dists = cdist(centers, centers) + np.eye(len(centers))
    radii = np.minimum(radii, (dists - radii).min(axis=1))
    
    # Final greedy radius maximization
    for i in range(n):
        x, y = centers[i]
        max_r = min(x, 1-x, y, 1-y)
        for j in range(n):
            if i == j:
                continue
            dist = np.sqrt((centers[j,0]-x)**2 + (centers[j,1]-y)**2)
            max_r = min(max_r, dist - radii[j])
        radii[i] = max_r
    
    return np.column_stack((centers, radii))
