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
    sampler = qmc.Sobol(d=2, seed=2025)
    points = sampler.random(n)
    circles = np.zeros((n, 3))
    circles[:, :2] = points
    circles[:, 2] = np.minimum(np.minimum(circles[:, 0], 1 - circles[:, 0]),
                              np.minimum(circles[:, 1], 1 - circles[:, 1])) * 0.1
    
    # Momentum-based optimization
    velocity = np.zeros((n, 2))
    for iteration in range(15000):
        temperature = max(0.01, 0.5 * (1 - iteration / 15000))
        cauchy_prob = max(0.01, 0.3 * (1 - iteration / 15000))
        
        for i in range(n):
            x, y, r = circles[i]
            
            # Radius expansion with Delaunay-like constraints
            max_r = min(x, 1-x, y, 1-y)
            for j in range(n):
                if i == j:
                    continue
                dist = np.sqrt((circles[j,0]-x)**2 + (circles[j,1]-y)**2)
                max_r = min(max_r, dist - circles[j,2])
            
            best_pos = None
            best_r = 0
            for _ in range(15):
                if np.random.random() < cauchy_prob:
                    step_size = 0.2 * temperature
                    new_x = np.clip(x + np.random.standard_cauchy() * step_size, 0, 1)
                    new_y = np.clip(y + np.random.standard_cauchy() * step_size, 0, 1)
                else:
                    step_size = 0.02 * (1 - iteration/15000)
                    new_x = np.clip(x + velocity[i,0] + np.random.uniform(-step_size, step_size), 0, 1)
                    new_y = np.clip(y + velocity[i,1] + np.random.uniform(-step_size, step_size), 0, 1)
                
                current_r = min(new_x, 1-new_x, new_y, 1-new_y)
                for j in range(n):
                    if i == j:
                        continue
                    dist = np.sqrt((circles[j,0]-new_x)**2 + (circles[j,1]-new_y)**2)
                    current_r = min(current_r, dist - circles[j,2])
                
                if current_r > best_r:
                    best_r = current_r
                    best_pos = (new_x, new_y, current_r)
                    velocity[i] = np.array([new_x - x, new_y - y]) * 0.1
            
            # Threshold acceptance with momentum
            if best_r > r or (best_r > 0 and np.random.random() < (best_r / max(r, 1e-8)) ** (1/temperature)):
                if best_pos is not None:
                    circles[i] = best_pos
    
    return circles
