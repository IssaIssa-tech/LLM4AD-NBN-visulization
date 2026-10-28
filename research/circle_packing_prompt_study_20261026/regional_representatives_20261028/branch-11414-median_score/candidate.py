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
    
    # Grid initialization with jitter
    grid_size = int(np.ceil(np.sqrt(n)))
    circles = np.zeros((n, 3))
    idx = 0
    for i in range(grid_size):
        for j in range(grid_size):
            if idx >= n:
                break
            x = (i + 0.5 + np.random.uniform(-0.2, 0.2)) / grid_size
            y = (j + 0.5 + np.random.uniform(-0.2, 0.2)) / grid_size
            circles[idx, :2] = np.clip([x, y], 0, 1)
            circles[idx, 2] = min(x, 1-x, y, 1-y) * 0.2
            idx += 1
    
    # Force-directed repulsion
    for _ in range(500):
        for i in range(n):
            x, y, r = circles[i]
            fx, fy = 0, 0
            
            for j in range(n):
                if i == j:
                    continue
                dx = circles[j, 0] - x
                dy = circles[j, 1] - y
                dist = np.sqrt(dx**2 + dy**2)
                min_dist = r + circles[j, 2]
                
                if dist < min_dist:
                    force = (min_dist - dist) * 0.1
                    fx -= force * dx / (dist + 1e-8)
                    fy -= force * dy / (dist + 1e-8)
            
            new_x = np.clip(x + fx, 0, 1)
            new_y = np.clip(y + fy, 0, 1)
            circles[i, :2] = [new_x, new_y]
    
    # Greedy radius expansion
    for _ in range(100):
        for i in range(n):
            x, y, r = circles[i]
            max_r = min(x, 1-x, y, 1-y)
            
            for j in range(n):
                if i == j:
                    continue
                dist = np.sqrt((circles[j,0]-x)**2 + (circles[j,1]-y)**2)
                max_r = min(max_r, dist - circles[j,2])
            
            if max_r > r:
                circles[i, 2] = max_r
    
    return circles