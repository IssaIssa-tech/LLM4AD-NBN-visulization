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
    from scipy.optimize import differential_evolution
    
    np.random.seed(2025)
    if n == 0:
        return np.zeros((0, 3))
    
    # Halton sequence initialization
    sampler = qmc.Halton(d=2, seed=2025)
    points = sampler.random(n)
    initial_guess = np.zeros(n * 3)
    initial_guess[::3] = points[:, 0]
    initial_guess[1::3] = points[:, 1]
    initial_guess[2::3] = np.minimum(np.minimum(points[:, 0], 1 - points[:, 0]),
                                   np.minimum(points[:, 1], 1 - points[:, 1])) * 0.2
    
    # Bounds: x,y in [0,1], radius in [0,0.5]
    bounds = [(0, 1)] * 2 * n + [(0, 0.5)] * n
    
    def objective(params):
        circles = params.reshape(-1, 3)
        total_radius = np.sum(circles[:, 2])
        
        # Penalty for boundary violations
        penalty = 0
        for x, y, r in circles:
            if x - r < 0 or x + r > 1 or y - r < 0 or y + r > 1:
                penalty += 1000
        
        # Penalty for overlaps
        for i in range(n):
            for j in range(i + 1, n):
                dist = np.sqrt((circles[i,0]-circles[j,0])**2 + (circles[i,1]-circles[j,1])**2)
                if dist < circles[i,2] + circles[j,2]:
                    penalty += 1000 * (1 + circles[i,2] + circles[j,2] - dist)
        
        return -(total_radius - penalty)
    
    result = differential_evolution(
        objective,
        bounds,
        strategy='best1bin',
        maxiter=1000,
        popsize=15,
        mutation=(0.5, 1.0),
        recombination=0.7,
        seed=2025,
        polish=False,
        init='latinhypercube'
    )
    
    circles = result.x.reshape(-1, 3)
    circles[:, 2] = np.clip(circles[:, 2], 0, 0.5)
    return circles