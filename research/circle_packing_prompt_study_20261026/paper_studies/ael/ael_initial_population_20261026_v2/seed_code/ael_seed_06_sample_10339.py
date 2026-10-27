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
    from scipy.spatial import Delaunay
    
    np.random.seed(2025)
    if n == 0:
        return np.zeros((0, 3))
    
    # Fibonacci spiral initialization
    golden_angle = np.pi * (3 - np.sqrt(5))
    theta = golden_angle * np.arange(n)
    r = np.sqrt(np.arange(n) / n) * 0.5
    circles = np.zeros((n, 3))
    circles[:, 0] = 0.5 + r * np.cos(theta)
    circles[:, 1] = 0.5 + r * np.sin(theta)
    circles[:, 2] = np.minimum(np.minimum(circles[:, 0], 1 - circles[:, 0]),
                              np.minimum(circles[:, 1], 1 - circles[:, 1])) * 0.1
    
    # Particle swarm-inspired optimization
    for iteration in range(10000):
        temperature = 0.5 * (1 + np.cos(np.pi * iteration / 10000))
        reflect_prob = 0.3 * (1 - iteration / 10000)
        
        # Build Delaunay triangulation for neighbor relationships
        try:
            tri = Delaunay(circles[:, :2])
            neighbors = [[] for _ in range(n)]
            for simplex in tri.simplices:
                for i in simplex:
                    for j in simplex:
                        if i != j and j not in neighbors[i]:
                            neighbors[i].append(j)
        except:
            neighbors = [[j for j in range(n) if j != i] for i in range(n)]
        
        for i in range(n):
            x, y, r = circles[i]
            
            # Radius expansion with Delaunay neighbor constraints
            max_r = min(x, 1-x, y, 1-y)
            for j in neighbors[i]:
                dist = np.sqrt((circles[j,0]-x)**2 + (circles[j,1]-y)**2)
                max_r = min(max_r, dist - circles[j,2])
            
            best_pos = None
            best_r = 0
            for _ in range(12):
                if np.random.random() < reflect_prob:
                    step_size = 0.1 * temperature
                    new_x = x + np.random.uniform(-step_size, step_size)
                    new_y = y + np.random.uniform(-step_size, step_size)
                    if new_x < 0 or new_x > 1:
                        new_x = np.clip(new_x, 0, 1)
                        new_y = 1 - new_y if np.random.random() < 0.5 else new_y
                    if new_y < 0 or new_y > 1:
                        new_y = np.clip(new_y, 0, 1)
                        new_x = 1 - new_x if np.random.random() < 0.5 else new_x
                else:
                    step_size = 0.05 * temperature
                    new_x = np.clip(x + np.random.uniform(-step_size, step_size), 0, 1)
                    new_y = np.clip(y + np.random.uniform(-step_size, step_size), 0, 1)
                
                current_r = min(new_x, 1-new_x, new_y, 1-new_y)
                for j in neighbors[i]:
                    dist = np.sqrt((circles[j,0]-new_x)**2 + (circles[j,1]-new_y)**2)
                    current_r = min(current_r, dist - circles[j,2])
                
                if current_r > best_r:
                    best_r = current_r
                    best_pos = (new_x, new_y, current_r)
            
            # Acceptance with cosine-annealed probability
            if best_r > r or np.random.random() < (0.5 + 0.5 * np.cos(np.pi * (best_r - r) / (temperature + 1e-8))):
                if best_pos is not None:
                    circles[i] = best_pos
    
    return circles
