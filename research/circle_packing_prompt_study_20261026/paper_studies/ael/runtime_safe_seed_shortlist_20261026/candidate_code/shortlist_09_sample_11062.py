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
    from scipy.stats import qmc
    from scipy.optimize import differential_evolution, minimize
    
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
    
    def fitness(params):
        x, y, r = params
        if r <= 0:
            return -np.inf
        if x - r < 0 or x + r > 1 or y - r < 0 or y + r > 1:
            return -np.inf
        for circle in circles:
            if np.allclose(circle, params):
                continue
            dist = np.sqrt((circle[0]-x)**2 + (circle[1]-y)**2)
            if dist < circle[2] + r:
                return -np.inf
        return r
    
    bounds = [(0, 1), (0, 1), (0, 1)]
    for i in range(n):
        result = differential_evolution(
            lambda p: -fitness(p),
            bounds,
            strategy='best1bin',
            maxiter=100,
            popsize=15,
            mutation=(0.5, 1.0),
            recombination=0.7,
            seed=2025
        )
        circles[i] = result.x
        
        # Local optimization
        res = minimize(
            lambda p: -fitness(p),
            circles[i],
            method='Nelder-Mead',
            bounds=bounds,
            options={'maxiter': 50}
        )
        if res.success:
            circles[i] = res.x
    
    return circles
