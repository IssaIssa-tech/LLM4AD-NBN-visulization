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
    from scipy.spatial import KDTree
    
    np.random.seed(2025)
    if n == 0:
        return np.zeros((0, 3))
    
    # Halton sequence initialization
    sampler = qmc.Halton(d=2, seed=2025)
    points = sampler.random(n)
    circles = np.zeros((n, 3))
    circles[:, :2] = points
    circles[:, 2] = np.minimum(np.minimum(circles[:, 0], 1 - circles[:, 0]),
                              np.minimum(circles[:, 1], 1 - circles[:, 1])) * 0.2
    
    # Simulated annealing with cosine schedule
    tree = KDTree(circles[:, :2])
    for iteration in range(10000):
        temperature = 0.5 * (1 + np.cos(np.pi * iteration / 10000))
        voronoi_freq = 0.1 * np.exp(-iteration / 2000)
        
        for i in range(n):
            x, y, r = circles[i]
            
            # Neighbor-aware radius expansion with k-d tree
            neighbors = tree.query_ball_point([x, y], 0.3)
            max_r = min(x, 1-x, y, 1-y)
            for j in neighbors:
                if i == j:
                    continue
                dist = np.sqrt((circles[j,0]-x)**2 + (circles[j,1]-y)**2)
                max_r = min(max_r, dist - circles[j,2])
            
            best_pos = None
            best_r = 0
            for _ in range(10):
                if np.random.random() < voronoi_freq:
                    # Voronoi-based repulsion
                    step_size = 0.2 * temperature
                    new_x = np.clip(x + (np.random.random() - 0.5) * step_size, 0, 1)
                    new_y = np.clip(y + (np.random.random() - 0.5) * step_size, 0, 1)
                else:
                    step_size = 0.05 * temperature
                    new_x = np.clip(x + np.random.normal(0, step_size), 0, 1)
                    new_y = np.clip(y + np.random.normal(0, step_size), 0, 1)
                
                current_r = min(new_x, 1-new_x, new_y, 1-new_y)
                neighbors = tree.query_ball_point([new_x, new_y], 0.3)
                for j in neighbors:
                    if i == j:
                        continue
                    dist = np.sqrt((circles[j,0]-new_x)**2 + (circles[j,1]-new_y)**2)
                    current_r = min(current_r, dist - circles[j,2])
                
                if current_r > best_r:
                    best_r = current_r
                    best_pos = (new_x, new_y, current_r)
            
            # Simulated annealing acceptance
            if best_r > r or np.random.random() < np.exp((best_r - r)/temperature):
                if best_pos is not None:
                    circles[i] = best_pos
                    tree = KDTree(circles[:, :2])
    
    return circles
