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
    from scipy.optimize import differential_evolution, NonlinearConstraint, minimize
    
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
    
    # Fitness function with penalties
    def fitness(params):
        params = params.reshape(-1, 3)
        penalty = 0
        for i in range(n):
            x, y, r = params[i]
            # Boundary penalty
            if x - r < 0 or x + r > 1 or y - r < 0 or y + r > 1:
                penalty += 1000
            # Overlap penalty
            for j in range(i+1, n):
                dist = np.sqrt((params[j,0]-x)**2 + (params[j,1]-y)**2)
                if dist < params[j,2] + r:
                    penalty += 1000 * (params[j,2] + r - dist)
        return -np.sum(params[:, 2]) + penalty
    
    # Differential evolution optimization
    bounds = [(0, 1)] * 2 * n + [(0, 0.5)] * n
    result = differential_evolution(
        fitness,
        bounds,
        strategy='best1bin',
        maxiter=1000,
        popsize=15,
        mutation=(0.5, 1.0),
        recombination=0.7,
        seed=2025,
        tol=1e-6
    )
    
    circles = result.x.reshape(-1, 3)
    
    # Local refinement with Nelder-Mead
    for i in range(n):
        def local_opt(params):
            x, y, r = params
            penalty = 0
            if x - r < 0 or x + r > 1 or y - r < 0 or y + r > 1:
                penalty += 1000
            for j in range(n):
                if i == j:
                    continue
                dist = np.sqrt((circles[j,0]-x)**2 + (circles[j,1]-y)**2)
                if dist < circles[j,2] + r:
                    penalty += 1000 * (circles[j,2] + r - dist)
            return -r + penalty
        
        res = minimize(
            local_opt,
            circles[i],
            method='Nelder-Mead',
            bounds=[(0, 1), (0, 1), (0, 0.5)],
            options={'maxiter': 1000}
        )
        circles[i] = res.x
    
    return circles
