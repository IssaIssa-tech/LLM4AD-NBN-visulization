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
    from scipy.optimize import minimize
    
    np.random.seed(2025)
    if n == 0:
        return np.zeros((0, 3))
    
    # Initialize circles in grid pattern
    grid_size = int(np.ceil(np.sqrt(n)))
    circles = np.zeros((n, 3))
    idx = 0
    for i in range(grid_size):
        for j in range(grid_size):
            if idx >= n:
                break
            circles[idx, 0] = (i + 0.5) / grid_size
            circles[idx, 1] = (j + 0.5) / grid_size
            circles[idx, 2] = 0.5 / grid_size
            idx += 1
    
    def collision_objective(x, i):
        circles[i, :2] = x
        penalty = 0
        # Boundary penalty
        penalty += max(0, -x[0]) * 1000
        penalty += max(0, x[0] - 1) * 1000
        penalty += max(0, -x[1]) * 1000
        penalty += max(0, x[1] - 1) * 1000
        
        # Collision penalty
        for j in range(n):
            if i == j:
                continue
            dx = circles[j, 0] - x[0]
            dy = circles[j, 1] - x[1]
            dist = np.sqrt(dx**2 + dy**2)
            min_dist = circles[i, 2] + circles[j, 2]
            if dist < min_dist:
                penalty += (min_dist - dist) * 1000
        return penalty
    
    # Gradient-based position optimization
    for _ in range(20):
        for i in range(n):
            res = minimize(collision_objective, circles[i, :2], args=(i,), method='L-BFGS-B')
            circles[i, :2] = res.x
    
    # Greedy radius expansion
    for i in range(n):
        max_r = min(circles[i, 0], 1 - circles[i, 0],
                   circles[i, 1], 1 - circles[i, 1])
        for j in range(n):
            if i == j:
                continue
            dx = circles[j, 0] - circles[i, 0]
            dy = circles[j, 1] - circles[i, 1]
            dist = np.sqrt(dx**2 + dy**2)
            max_r = min(max_r, dist - circles[j, 2])
        circles[i, 2] = max(0, max_r * 0.99)
    
    return circles
