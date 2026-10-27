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
    from scipy.optimize import minimize
    
    np.random.seed(2025)
    if n == 0:
        return np.zeros((0, 3))
    
    # Initial random placement
    points = np.random.rand(n, 2)
    radii = np.zeros(n)
    
    # Voronoi iteration
    for _ in range(50):
        vor = Voronoi(points)
        new_points = np.zeros_like(points)
        
        for i in range(n):
            region = vor.regions[vor.point_region[i]]
            if -1 in region or len(region) == 0:
                new_points[i] = points[i]
                continue
                
            vertices = vor.vertices[region]
            center = vertices.mean(axis=0)
            new_points[i] = np.clip(center, 0, 1)
        
        points = new_points
    
    # Calculate initial radii
    for i in range(n):
        radii[i] = min(points[i,0], 1-points[i,0], points[i,1], 1-points[i,1])
        for j in range(n):
            if i == j:
                continue
            dist = np.linalg.norm(points[i] - points[j])
            radii[i] = min(radii[i], dist - radii[j])
    
    # Gradient ascent refinement
    def objective(x):
        centers = x.reshape(-1, 2)
        r = np.zeros(n)
        for i in range(n):
            r[i] = min(centers[i,0], 1-centers[i,0], centers[i,1], 1-centers[i,1])
            for j in range(n):
                if i == j:
                    continue
                dist = np.linalg.norm(centers[i] - centers[j])
                r[i] = min(r[i], dist - r[j])
        return -np.sum(r)
    
    bounds = [(0, 1)] * (2 * n)
    res = minimize(objective, points.flatten(), bounds=bounds, method='L-BFGS-B')
    optimized_points = res.x.reshape(-1, 2)
    
    # Final radius calculation
    circles = np.zeros((n, 3))
    for i in range(n):
        r = min(optimized_points[i,0], 1-optimized_points[i,0], 
                optimized_points[i,1], 1-optimized_points[i,1])
        for j in range(n):
            if i == j:
                continue
            dist = np.linalg.norm(optimized_points[i] - optimized_points[j])
            r = min(r, dist - circles[j,2])
        circles[i] = [optimized_points[i,0], optimized_points[i,1], r]
    
    return circles
