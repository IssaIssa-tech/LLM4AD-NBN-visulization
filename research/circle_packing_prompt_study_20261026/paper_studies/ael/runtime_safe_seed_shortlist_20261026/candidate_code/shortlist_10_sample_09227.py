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
                              np.minimum(circles[:, 1], 1 - circles[:, 1])) * 0.1
    
    # Differential evolution optimization
    bounds = [(0, 1)] * 2 * n
    
    def objective(params):
        positions = params.reshape(-1, 2)
        radii = np.zeros(n)
        penalty = 0
        
        for i in range(n):
            x, y = positions[i]
            r = min(x, 1-x, y, 1-y)
            for j in range(n):
                if i == j:
                    continue
                dist = np.sqrt((positions[j,0]-x)**2 + (positions[j,1]-y)**2)
                r = min(r, dist - radii[j])
            radii[i] = max(r, 0)
            
            # Penalty for out-of-bounds
            if x < 0 or x > 1 or y < 0 or y > 1:
                penalty += 1000
                
        return -np.sum(radii) + penalty
    
    result = differential_evolution(
        objective,
        bounds,
        strategy='best1bin',
        maxiter=1000,
        popsize=15,
        mutation=(0.5, 1.0),
        recombination=0.7,
        seed=2025
    )
    
    # Final local optimization
    for i in range(n):
        def local_obj(params):
            x, y = params
            r = min(x, 1-x, y, 1-y)
            for j in range(n):
                if i == j:
                    continue
                dist = np.sqrt((circles[j,0]-x)**2 + (circles[j,1]-y)**2)
                r = min(r, dist - circles[j,2])
            return -r
        
        res = minimize(
            local_obj,
            circles[i, :2],
            method='Nelder-Mead',
            bounds=[(0, 1), (0, 1)]
        )
        x, y = res.x
        r = min(x, 1-x, y, 1-y)
        for j in range(n):
            if i == j:
                continue
            dist = np.sqrt((circles[j,0]-x)**2 + (circles[j,1]-y)**2)
            r = min(r, dist - circles[j,2])
        circles[i] = (x, y, r)
    
    return circles
