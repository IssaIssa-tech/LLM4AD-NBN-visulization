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
    np.random.seed(2025)
    if n == 0:
        return np.zeros((0, 3))
    
    circles = []
    grid_resolution = 10
    
    for _ in range(n):
        best_score = -1
        best_pos = (0.5, 0.5)
        best_r = 0
        
        # Generate grid candidates
        x = np.linspace(0, 1, grid_resolution)
        y = np.linspace(0, 1, grid_resolution)
        xx, yy = np.meshgrid(x, y)
        candidates = np.column_stack([xx.ravel(), yy.ravel()])
        
        # Add random jitter to grid points
        jitter = np.random.uniform(-0.5/grid_resolution, 0.5/grid_resolution, candidates.shape)
        candidates = np.clip(candidates + jitter, 0, 1)
        
        # Add boundary candidates
        boundary_samples = np.vstack([
            np.column_stack([np.random.uniform(0, 1, 50), np.zeros(50)]),
            np.column_stack([np.random.uniform(0, 1, 50), np.ones(50)]),
            np.column_stack([np.zeros(50), np.random.uniform(0, 1, 50)]),
            np.column_stack([np.ones(50), np.random.uniform(0, 1, 50)])
        ])
        candidates = np.vstack([candidates, boundary_samples])
        
        if circles:
            existing = np.array([c[:2] for c in circles])
            radii = np.array([c[2] for c in circles])
            
            # Add samples near existing circles
            for c in circles:
                theta = np.random.uniform(0, 2*np.pi, 20)
                r = np.random.uniform(0, c[2]*2, 20)
                new_samples = np.column_stack([
                    c[0] + r * np.cos(theta),
                    c[1] + r * np.sin(theta)
                ])
                candidates = np.vstack([candidates, np.clip(new_samples, 0, 1)])
        
        for candidate in candidates:
            if len(circles) == 0:
                dist_to_boundary = min(candidate[0], candidate[1], 1 - candidate[0], 1 - candidate[1])
                current_r = dist_to_boundary
            else:
                existing = np.array([c[:2] for c in circles])
                radii = np.array([c[2] for c in circles])
                dists = np.sqrt(((existing - candidate)**2).sum(axis=1)) - radii
                dist_to_boundary = min(candidate[0], candidate[1], 1 - candidate[0], 1 - candidate[1])
                current_r = min(dists.min(), dist_to_boundary)
            
            score = current_r
            if score > best_score and current_r > 0:
                best_score = score
                best_r = current_r
                best_pos = candidate
        
        circles.append([best_pos[0], best_pos[1], best_r])
        grid_resolution = min(100, grid_resolution + 5)
    
    return np.array(circles)
