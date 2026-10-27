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
    
    # Halton sequence initialization
    sampler = qmc.Halton(d=2, seed=2025)
    points = sampler.random(n)
    circles = np.zeros((n, 3))
    circles[:, :2] = points
    circles[:, 2] = np.minimum(np.minimum(circles[:, 0], 1 - circles[:, 0]),
                              np.minimum(circles[:, 1], 1 - circles[:, 1])) * 0.15
    
    # Differential evolution with Voronoi partitioning
    for iteration in range(12000):
        temperature = 0.5 * (1 - (iteration/12000)**2)
        mutation_rate = 0.3 * (1 - iteration/12000)
        
        for i in range(n):
            x, y, r = circles[i]
            
            # Voronoi-based region constraints
            max_r = min(x, 1-x, y, 1-y)
            for j in range(n):
                if i == j:
                    continue
                dist = np.sqrt((circles[j,0]-x)**2 + (circles[j,1]-y)**2)
                max_r = min(max_r, dist - circles[j,2])
            
            best_pos = None
            best_r = 0
            for _ in range(15):
                # Differential evolution move
                if np.random.random() < mutation_rate:
                    a, b = np.random.choice(n, 2, replace=False)
                    new_x = np.clip(x + 0.5*(circles[a,0] - circles[b,0]), 0, 1)
                    new_y = np.clip(y + 0.5*(circles[a,1] - circles[b,1]), 0, 1)
                else:
                    step_size = 0.1 * temperature
                    new_x = np.clip(x + np.random.normal(0, step_size), 0, 1)
                    new_y = np.clip(y + np.random.normal(0, step_size), 0, 1)
                
                # Mirror reflection at boundaries
                if new_x <= 0 or new_x >= 1:
                    new_x = np.abs(new_x) % 1
                if new_y <= 0 or new_y >= 1:
                    new_y = np.abs(new_y) % 1
                
                current_r = min(new_x, 1-new_x, new_y, 1-new_y)
                for j in range(n):
                    if i == j:
                        continue
                    dist = np.sqrt((circles[j,0]-new_x)**2 + (circles[j,1]-new_y)**2)
                    current_r = min(current_r, dist - circles[j,2])
                
                if current_r > best_r:
                    best_r = current_r
                    best_pos = (new_x, new_y, current_r)
            
            # Probabilistic acceptance
            if best_r > r or np.random.random() < np.exp(5*(best_r - r)/temperature):
                if best_pos is not None:
                    circles[i] = best_pos
    
    return circles
