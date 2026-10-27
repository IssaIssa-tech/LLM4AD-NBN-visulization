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
    from scipy.spatial import Voronoi
    
    np.random.seed(2025)
    if n == 0:
        return np.zeros((0, 3))
    
    # Poisson disk-like initialization
    points = np.zeros((n, 2))
    points[0] = np.random.rand(2)
    for i in range(1, n):
        valid = False
        attempts = 0
        while not valid and attempts < 1000:
            attempts += 1
            candidate = np.random.rand(2)
            min_dist = min(np.linalg.norm(candidate - p) for p in points[:i])
            if min_dist > 0.15 / np.sqrt(n):
                points[i] = candidate
                valid = True
        if not valid:
            points[i] = np.random.rand(2)
    
    circles = np.zeros((n, 3))
    circles[:, :2] = points
    circles[:, 2] = np.minimum(np.minimum(circles[:, 0], 1 - circles[:, 0]),
                              np.minimum(circles[:, 1], 1 - circles[:, 1])) * 0.2
    
    # Simulated annealing with Voronoi neighborhood
    for iteration in range(10000):
        temperature = 0.5 * (1 - iteration/10000)**3
        
        for i in range(n):
            x, y, r = circles[i]
            
            # Voronoi-based neighbor detection
            vor = Voronoi(circles[:, :2])
            neighbors = set()
            for simplex in vor.ridge_points:
                if i in simplex:
                    neighbors.add(simplex[0] if simplex[0] != i else simplex[1])
            neighbors = list(neighbors)
            
            # Gaussian perturbation
            best_pos = None
            best_r = 0
            for _ in range(20):
                step_size = 0.05 * temperature
                new_x = np.clip(x + np.random.normal(0, step_size), 0, 1)
                new_y = np.clip(y + np.random.normal(0, step_size), 0, 1)
                
                current_r = min(new_x, 1-new_x, new_y, 1-new_y)
                for j in neighbors:
                    dist = np.sqrt((circles[j,0]-new_x)**2 + (circles[j,1]-new_y)**2)
                    current_r = min(current_r, dist - circles[j,2])
                
                if current_r > best_r:
                    best_r = current_r
                    best_pos = (new_x, new_y, current_r)
            
            # Simulated annealing acceptance
            if best_r > r or np.random.random() < np.exp((best_r - r)/temperature):
                if best_pos is not None:
                    circles[i] = best_pos
    
    return circles
