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
    from scipy.spatial import Delaunay
    
    np.random.seed(2025)
    if n == 0:
        return np.zeros((0, 3))
    
    # Latin Hypercube initialization
    sampler = qmc.LatinHypercube(d=2, seed=2025)
    points = sampler.random(n)
    circles = np.zeros((n, 3))
    circles[:, :2] = points
    circles[:, 2] = np.minimum(np.minimum(circles[:, 0], 1 - circles[:, 0]),
                              np.minimum(circles[:, 1], 1 - circles[:, 1])) * 0.1
    
    # Differential evolution optimization with polynomial cooling
    for iteration in range(20000):
        temperature = 0.5 * (1 - iteration/20000)**3
        
        # Build Delaunay triangulation for neighborhood
        if n > 3:
            tri = Delaunay(circles[:, :2])
            neighbors = [[] for _ in range(n)]
            for simplex in tri.simplices:
                for i in simplex:
                    for j in simplex:
                        if i != j and j not in neighbors[i]:
                            neighbors[i].append(j)
        
        for i in range(n):
            x, y, r = circles[i]
            
            # Radius expansion constrained by Delaunay neighbors
            max_r = min(x, 1-x, y, 1-y)
            if n > 3:
                for j in neighbors[i]:
                    dist = np.sqrt((circles[j,0]-x)**2 + (circles[j,1]-y)**2)
                    max_r = min(max_r, dist - circles[j,2])
            else:
                for j in range(n):
                    if i == j:
                        continue
                    dist = np.sqrt((circles[j,0]-x)**2 + (circles[j,1]-y)**2)
                    max_r = min(max_r, dist - circles[j,2])
            
            # Differential evolution moves
            best_pos = None
            best_r = 0
            for _ in range(20):
                if np.random.random() < 0.5:
                    # Mutation based on neighbors
                    if n > 3 and len(neighbors[i]) >= 2:
                        a, b = np.random.choice(neighbors[i], 2, replace=False)
                        new_x = np.clip(x + 0.5 * (circles[a,0] - circles[b,0]) * temperature, 0, 1)
                        new_y = np.clip(y + 0.5 * (circles[a,1] - circles[b,1]) * temperature, 0, 1)
                    else:
                        new_x = np.clip(x + np.random.uniform(-0.1, 0.1) * temperature, 0, 1)
                        new_y = np.clip(y + np.random.uniform(-0.1, 0.1) * temperature, 0, 1)
                else:
                    # Random jump
                    new_x = np.clip(x + np.random.normal(0, 0.1 * temperature), 0, 1)
                    new_y = np.clip(y + np.random.normal(0, 0.1 * temperature), 0, 1)
                
                current_r = min(new_x, 1-new_x, new_y, 1-new_y)
                for j in range(n):
                    if i == j:
                        continue
                    dist = np.sqrt((circles[j,0]-new_x)**2 + (circles[j,1]-new_y)**2)
                    current_r = min(current_r, dist - circles[j,2])
                
                if current_r > best_r:
                    best_r = current_r
                    best_pos = (new_x, new_y, current_r)
            
            # Acceptance with polynomial cooling
            if best_r > r or np.random.random() < (temperature**0.5):
                if best_pos is not None:
                    circles[i] = best_pos
    
    return circles
