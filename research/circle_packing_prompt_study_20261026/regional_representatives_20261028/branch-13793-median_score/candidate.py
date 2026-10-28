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
    np.random.seed(2025)
    
    if n == 0:
        return np.zeros((0, 3))
    
    # Sobol sequence initialization
    sampler = qmc.Sobol(d=2, scramble=False)
    points = sampler.random_base2(m=int(np.ceil(np.log2(n))))[:n]
    circles = np.zeros((n, 3))
    circles[:, :2] = points
    circles[:, 2] = 0.01
    
    # Simulated annealing optimization
    for iteration in range(1000):
        temperature = 0.25 * np.exp(-iteration / 200)
        
        for i in range(n):
            # Generate candidate position
            candidate = circles[i, :2] + temperature * np.random.normal(0, 0.1, 2)
            
            # Dynamic boundary constraints
            padding = 0.01 + 0.04 * (1 - np.exp(-iteration / 300))
            candidate = np.clip(candidate, padding, 1 - padding)
            
            # Calculate minimum distance
            min_dist = min(candidate[0], 1 - candidate[0], candidate[1], 1 - candidate[1])
            for j in range(n):
                if i == j:
                    continue
                dx = circles[j, 0] - candidate[0]
                dy = circles[j, 1] - candidate[1]
                dist = np.sqrt(dx**2 + dy**2) - circles[j, 2]
                if dist < min_dist:
                    min_dist = dist
            
            # Exponential radius scaling
            current_radius = min_dist * (0.7 + 0.3 * (1 - np.exp(-iteration / 150)))
            
            # Accept or reject move
            if current_radius > circles[i, 2] or np.random.rand() < np.exp((current_radius - circles[i, 2]) / temperature):
                circles[i, :2] = candidate
                circles[i, 2] = current_radius
    
    return circles