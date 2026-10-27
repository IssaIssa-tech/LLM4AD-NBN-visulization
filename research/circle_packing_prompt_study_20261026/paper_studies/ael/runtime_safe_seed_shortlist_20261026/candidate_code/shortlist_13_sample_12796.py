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
    from scipy.optimize import differential_evolution, basinhopping
    
    np.random.seed(2025)
    if n == 0:
        return np.zeros((0, 3))
    
    # Latin Hypercube Sampling initialization
    sampler = qmc.LatinHypercube(d=2, seed=2025)
    points = sampler.random(n)
    circles = np.zeros((n, 3))
    circles[:, :2] = points
    circles[:, 2] = np.minimum(np.minimum(circles[:, 0], 1 - circles[:, 0]),
                              np.minimum(circles[:, 1], 1 - circles[:, 1])) * 0.18
    
    # Differential evolution with local refinement
    def evaluate_positions(params):
        params = params.reshape(-1, 2)
        radii = np.zeros(n)
        for i in range(n):
            x, y = params[i]
            radii[i] = min(x, 1-x, y, 1-y)
            for j in range(n):
                if i == j:
                    continue
                dist = np.sqrt((params[j,0]-x)**2 + (params[j,1]-y)**2)
                radii[i] = min(radii[i], dist - radii[j])
        return -np.sum(radii)
    
    bounds = [(0, 1)] * (2 * n)
    result = differential_evolution(evaluate_positions, bounds, maxiter=100, popsize=15, seed=2025)
    
    # Basin-hopping for global optimization
    def local_optimize(params):
        return evaluate_positions(params)
    
    minimizer_kwargs = {"method": "L-BFGS-B", "bounds": bounds}
    result = basinhopping(local_optimize, result.x, niter=20, minimizer_kwargs=minimizer_kwargs, seed=2025)
    
    # Final radius calculation
    optimized_pos = result.x.reshape(-1, 2)
    circles[:, :2] = optimized_pos
    for i in range(n):
        x, y = optimized_pos[i]
        max_r = min(x, 1-x, y, 1-y)
        for j in range(n):
            if i == j:
                continue
            dist = np.sqrt((optimized_pos[j,0]-x)**2 + (optimized_pos[j,1]-y)**2)
            max_r = min(max_r, dist - circles[j,2])
        circles[i, 2] = max_r
    
    return circles
