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
    from scipy.optimize import minimize
    from scipy.stats import qmc
    
    np.random.seed(2025)
    if n == 0:
        return np.zeros((0, 3))
    
    # Sobol sequence initialization
    sampler = qmc.Sobol(d=2, scramble=False, seed=2025)
    points = sampler.random(n)
    circles = np.zeros((n, 3))
    circles[:, :2] = points
    circles[:, 2] = np.minimum(np.minimum(circles[:, 0], 1 - circles[:, 0]),
                              np.minimum(circles[:, 1], 1 - circles[:, 1])) * 0.2
    
    # Optimization function
    def objective(x):
        centers = x.reshape(-1, 2)
        radii = np.zeros(n)
        for i in range(n):
            xi, yi = centers[i]
            r = min(xi, 1-xi, yi, 1-yi)
            for j in range(n):
                if i == j:
                    continue
                dist = np.sqrt((centers[j,0]-xi)**2 + (centers[j,1]-yi)**2)
                r = min(r, dist - radii[j])
            radii[i] = r
        return -np.sum(radii)
    
    # L-BFGS optimization
    bounds = [(0, 1)] * (2 * n)
    res = minimize(objective, circles[:, :2].flatten(), method='L-BFGS-B', bounds=bounds)
    
    # Final radius calculation
    centers = res.x.reshape(-1, 2)
    radii = np.zeros(n)
    for i in range(n):
        xi, yi = centers[i]
        r = min(xi, 1-xi, yi, 1-yi)
        for j in range(n):
            if i == j:
                continue
            dist = np.sqrt((centers[j,0]-xi)**2 + (centers[j,1]-yi)**2)
            r = min(r, dist - radii[j])
        radii[i] = r
    
    circles = np.column_stack((centers, radii))
    return circles
