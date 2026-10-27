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
    
    # Differential evolution with cooling schedule
    for iteration in range(10000):
        temperature = 0.4 * np.exp(-iteration / 3000)
        step_size = 0.1 * (1 - iteration/10000)**1.5
        
        for i in range(n):
            x, y, r = circles[i]
            
            # Generate candidate positions
            candidates = []
            for _ in range(8):
                # Gaussian perturbation with reflection at boundaries
                new_x = x + np.random.normal(0, step_size)
                new_y = y + np.random.normal(0, step_size)
                
                # Reflect if out of bounds
                new_x = np.abs(new_x) if new_x < 0 else 2 - new_x if new_x > 1 else new_x
                new_y = np.abs(new_y) if new_y < 0 else 2 - new_y if new_y > 1 else new_y
                new_x = np.clip(new_x, 0, 1)
                new_y = np.clip(new_y, 0, 1)
                
                # Calculate maximum possible radius
                current_r = min(new_x, 1-new_x, new_y, 1-new_y)
                for j in range(n):
                    if i == j:
                        continue
                    dist = np.sqrt((circles[j,0]-new_x)**2 + (circles[j,1]-new_y)**2)
                    current_r = min(current_r, dist - circles[j,2])
                
                candidates.append((new_x, new_y, current_r))
            
            # Select best candidate with Metropolis criterion
            best_idx = np.argmax([c[2] for c in candidates])
            best_x, best_y, best_r = candidates[best_idx]
            
            if best_r > r or np.random.random() < np.exp((best_r - r)/temperature):
                circles[i] = (best_x, best_y, best_r)
    
    return circles
