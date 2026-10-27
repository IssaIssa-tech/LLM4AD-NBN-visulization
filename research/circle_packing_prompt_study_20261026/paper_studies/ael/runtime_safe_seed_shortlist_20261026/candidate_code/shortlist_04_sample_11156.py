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
    
    # Sobol sequence initialization
    sampler = qmc.Sobol(d=2, seed=2025)
    points = sampler.random(n)
    circles = np.zeros((n, 3))
    circles[:, :2] = points
    circles[:, 2] = np.minimum(np.minimum(circles[:, 0], 1 - circles[:, 0]),
                              np.minimum(circles[:, 1], 1 - circles[:, 1])) * 0.2
    
    # Differential evolution with local refinement
    bounds = [(0, 1), (0, 1)]
    for i in range(n):
        def objective(v):
            x, y = v
            current_r = min(x, 1-x, y, 1-y)
            for j in range(n):
                if i == j:
                    continue
                dist = np.sqrt((circles[j,0]-x)**2 + (circles[j,1]-y)**2)
                current_r = min(current_r, dist - circles[j,2])
            return -current_r
        
        # Global optimization
        res = differential_evolution(objective, bounds, strategy='best1bin', 
                                   mutation=(0.5, 1.0), recombination=0.7, 
                                   seed=2025, polish=False)
        x_opt, y_opt = res.x
        r_opt = min(x_opt, 1-x_opt, y_opt, 1-y_opt)
        for j in range(n):
            if i == j:
                continue
            dist = np.sqrt((circles[j,0]-x_opt)**2 + (circles[j,1]-y_opt)**2)
            r_opt = min(r_opt, dist - circles[j,2])
        
        # Local refinement
        res_local = minimize(objective, [x_opt, y_opt], method='L-BFGS-B', bounds=bounds)
        x_local, y_local = res_local.x
        r_local = min(x_local, 1-x_local, y_local, 1-y_local)
        for j in range(n):
            if i == j:
                continue
            dist = np.sqrt((circles[j,0]-x_local)**2 + (circles[j,1]-y_local)**2)
            r_local = min(r_local, dist - circles[j,2])
        
        if r_local > r_opt:
            circles[i] = [x_local, y_local, r_local]
        else:
            circles[i] = [x_opt, y_opt, r_opt]
    
    return circles
