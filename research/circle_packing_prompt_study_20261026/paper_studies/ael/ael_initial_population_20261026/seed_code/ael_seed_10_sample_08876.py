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
    
    np.random.seed(2025)
    if n == 0:
        return np.zeros((0, 3))
    
    # Fibonacci lattice initialization
    phi = (1 + np.sqrt(5)) / 2
    indices = np.arange(n)
    circles = np.zeros((n, 3))
    circles[:, 0] = (indices / phi) % 1
    circles[:, 1] = indices / n
    circles[:, 2] = np.minimum(np.minimum(circles[:, 0], 1 - circles[:, 0]),
                              np.minimum(circles[:, 1], 1 - circles[:, 1])) * 0.25
    
    # Differential evolution optimization
    for iteration in range(30000):
        diversity = np.std(circles[:, :2], axis=0).mean()
        mutation_rate = 0.1 + 0.4 * (1 - iteration/30000) * diversity
        
        for i in range(n):
            x, y, r = circles[i]
            
            # Radius expansion
            max_r = min(x, 1-x, y, 1-y)
            for j in range(n):
                if i == j:
                    continue
                dist = np.sqrt((circles[j,0]-x)**2 + (circles[j,1]-y)**2)
                max_r = min(max_r, dist - circles[j,2])
            
            best_pos = None
            best_r = 0
            for _ in range(20):
                if np.random.random() < mutation_rate:
                    # Differential mutation
                    a, b, c = np.random.choice(n, 3, replace=False)
                    new_x = np.clip(x + 0.5 * (circles[a,0] - x) + 0.5 * (circles[b,0] - circles[c,0]), 0, 1)
                    new_y = np.clip(y + 0.5 * (circles[a,1] - y) + 0.5 * (circles[b,1] - circles[c,1]), 0, 1)
                else:
                    # Local perturbation
                    step_size = 0.05 * (1 - iteration/30000)
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
            
            if best_pos is not None:
                circles[i] = best_pos
    
    return circles
