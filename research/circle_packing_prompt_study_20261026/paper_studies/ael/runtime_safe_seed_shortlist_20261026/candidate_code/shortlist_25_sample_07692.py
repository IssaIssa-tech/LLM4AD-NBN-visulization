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
                              np.minimum(circles[:, 1], 1 - circles[:, 1])) * 0.1
    
    def evaluate_positions(params):
        positions = params.reshape(-1, 2)
        radii = np.zeros(n)
        for i in range(n):
            x, y = positions[i]
            max_r = min(x, 1-x, y, 1-y)
            for j in range(n):
                if i == j:
                    continue
                dist = np.sqrt((positions[j,0]-x)**2 + (positions[j,1]-y)**2)
                max_r = min(max_r, dist - radii[j])
            radii[i] = max_r
        return -np.sum(radii)
    
    bounds = [(0, 1)] * (2 * n)
    result = differential_evolution(
        evaluate_positions,
        bounds,
        strategy='best1bin',
        maxiter=500,
        popsize=15,
        mutation=(0.5, 1.0),
        recombination=0.7,
        seed=2025
    )
    
    # Final local optimization
    final_positions = result.x.reshape(-1, 2)
    final_circles = np.zeros((n, 3))
    final_circles[:, :2] = final_positions
    for i in range(n):
        x, y = final_positions[i]
        max_r = min(x, 1-x, y, 1-y)
        for j in range(n):
            if i == j:
                continue
            dist = np.sqrt((final_positions[j,0]-x)**2 + (final_positions[j,1]-y)**2)
            max_r = min(max_r, dist - final_circles[j,2])
        final_circles[i, 2] = max_r
    
    return final_circles
