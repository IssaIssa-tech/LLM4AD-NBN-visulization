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
    
    # Latin Hypercube initialization
    sampler = qmc.LatinHypercube(d=2, seed=2025)
    points = sampler.random(n)
    circles = np.zeros((n, 3))
    circles[:, :2] = points
    circles[:, 2] = np.minimum(np.minimum(circles[:, 0], 1 - circles[:, 0]),
                              np.minimum(circles[:, 1], 1 - circles[:, 1])) * 0.15
    
    # Simulated annealing with cosine schedule
    for iteration in range(20000):
        temperature = 0.6 * (1 + np.cos(iteration * np.pi / 20000))
        levy_prob = max(0.15 - iteration * 0.0000075, 0.005)
        density_gradient = np.mean(circles[:, 2]) / 0.18
        
        for i in range(n):
            x, y, r = circles[i]
            
            # Radius expansion with repulsive forces
            max_r = min(x, 1-x, y, 1-y)
            for j in range(n):
                if i == j:
                    continue
                dist = np.sqrt((circles[j,0]-x)**2 + (circles[j,1]-y)**2)
                max_r = min(max_r, dist - circles[j,2])
            
            best_pos = None
            best_r = 0
            for _ in range(12):
                if np.random.random() < levy_prob:
                    step_size = 0.25 * temperature * density_gradient
                    new_x = np.clip(x + np.random.normal(0, 1) * step_size * np.random.standard_cauchy(), 0, 1)
                    new_y = np.clip(y + np.random.normal(0, 1) * step_size * np.random.standard_cauchy(), 0, 1)
                else:
                    step_size = 0.04 * (1 - iteration/20000) * density_gradient
                    new_x = np.clip(x + np.random.uniform(-step_size, step_size), 0, 1)
                    new_y = np.clip(y + np.random.uniform(-step_size, step_size), 0, 1)
                
                current_r = min(new_x, 1-new_x, new_y, 1-new_y)
                for j in range(n):
                    if i == j:
                        continue
                    dist = np.sqrt((circles[j,0]-new_x)**2 + (circles[j,1]-new_y)**2)
                    current_r = min(current_r, dist - circles[j,2])
                
                if current_r > best_r:
                    best_r = current_r
                    best_pos = (new_x, new_y, current_r)
            
            # Acceptance with modified criterion
            if best_r > r or np.random.random() < np.exp(6*(best_r - r)/temperature):
                if best_pos is not None:
                    circles[i] = best_pos
    
    return circles
