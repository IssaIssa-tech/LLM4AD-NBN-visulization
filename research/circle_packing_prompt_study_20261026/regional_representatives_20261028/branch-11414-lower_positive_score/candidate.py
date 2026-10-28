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
    sampler = qmc.Halton(d=2, scramble=False, seed=2025)
    points = sampler.random(n)
    circles = np.zeros((n, 3))
    circles[:, :2] = points
    circles[:, 2] = np.minimum(np.minimum(circles[:, 0], 1 - circles[:, 0]),
                              np.minimum(circles[:, 1], 1 - circles[:, 1])) * 0.2
    
    # Hybrid optimization
    for iteration in range(5000):
        learning_rate = 0.1 * np.exp(-iteration/1000)
        jitter_prob = 0.2 * np.exp(-iteration/2000)
        
        for i in range(n):
            if np.random.random() < jitter_prob:
                circles[i, :2] = np.random.uniform(0, 1, 2)
                circles[i, 2] = min(circles[i, 0], 1 - circles[i, 0],
                                   circles[i, 1], 1 - circles[i, 1]) * 0.2
                continue
                
            x, y, r = circles[i]
            grad_x, grad_y = 0.0, 0.0
            
            # Calculate gradient from boundaries
            grad_x += learning_rate * (1/(x + 1e-8) - 1/(1 - x + 1e-8))
            grad_y += learning_rate * (1/(y + 1e-8) - 1/(1 - y + 1e-8))
            
            # Calculate repulsive forces
            for j in range(n):
                if i == j:
                    continue
                dx = x - circles[j, 0]
                dy = y - circles[j, 1]
                dist = np.sqrt(dx*dx + dy*dy)
                min_dist = r + circles[j, 2]
                if dist < min_dist:
                    force = learning_rate * (min_dist - dist) / (dist + 1e-8)
                    grad_x += force * dx
                    grad_y += force * dy
            
            # Update position
            new_x = np.clip(x - grad_x, 0, 1)
            new_y = np.clip(y - grad_y, 0, 1)
            
            # Calculate new radius
            new_r = min(new_x, 1 - new_x, new_y, 1 - new_y)
            for j in range(n):
                if i == j:
                    continue
                dist = np.sqrt((circles[j, 0] - new_x)**2 + (circles[j, 1] - new_y)**2)
                new_r = min(new_r, dist - circles[j, 2])
            
            if new_r > 0:
                circles[i] = (new_x, new_y, new_r)
    
    return circles