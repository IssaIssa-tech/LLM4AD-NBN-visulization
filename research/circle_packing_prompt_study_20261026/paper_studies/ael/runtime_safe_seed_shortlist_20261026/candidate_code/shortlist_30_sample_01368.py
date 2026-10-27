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
    
    for iteration in range(n):
        best_score = -1
        best_pos = (0.5, 0.5)
        best_r = 0
        
        # Generate candidate positions
        candidates = []
        if circles:
            existing = np.array([c[:2] for c in circles])
            radii = np.array([c[2] for c in circles])
            
            # Points near existing circles
            for i in range(len(circles)):
                angle = np.linspace(0, 2*np.pi, 20, endpoint=False)
                dist = radii[i] + np.random.uniform(0.01, 0.2, 20)
                x = existing[i,0] + dist * np.cos(angle)
                y = existing[i,1] + dist * np.sin(angle)
                candidates.extend(np.column_stack([x, y]))
            
            # Grid points
            grid_size = int(np.sqrt(n) * 2)
            x_grid = np.linspace(0, 1, grid_size)
            y_grid = np.linspace(0, 1, grid_size)
            xx, yy = np.meshgrid(x_grid, y_grid)
            candidates.extend(np.column_stack([xx.ravel(), yy.ravel()]))
            
            # Boundary points
            boundary = np.random.uniform(0, 1, (80, 2))
            boundary = np.vstack([
                boundary,
                np.column_stack([np.random.uniform(0, 1, 20), np.zeros(20)]),
                np.column_stack([np.random.uniform(0, 1, 20), np.ones(20)]),
                np.column_stack([np.zeros(20), np.random.uniform(0, 1, 20)]),
                np.column_stack([np.ones(20), np.random.uniform(0, 1, 20)])
            ])
            candidates.extend(boundary)
        else:
            candidates = np.random.uniform(0, 1, (100, 2))
        
        # Evaluate candidates
        for candidate in candidates:
            if not (0 <= candidate[0] <= 1 and 0 <= candidate[1] <= 1):
                continue
                
            if len(circles) == 0:
                dist_to_boundary = min(candidate[0], candidate[1], 1 - candidate[0], 1 - candidate[1])
                current_r = dist_to_boundary
                boundary_weight = 1.5
                density_weight = 1.0
                score = current_r * boundary_weight * density_weight
            else:
                existing = np.array([c[:2] for c in circles])
                radii = np.array([c[2] for c in circles])
                dists = np.sqrt(((existing - candidate)**2).sum(axis=1)) - radii
                dist_to_boundary = min(candidate[0], candidate[1], 1 - candidate[0], 1 - candidate[1])
                current_r = min(dists.min(), dist_to_boundary)
                
                # Adaptive parameters
                progress = iteration / n
                boundary_weight = 1.5 - 0.8 * progress
                density_penalty = 1.0 + 0.3 * np.exp(-4.0 * (dists.min() / (1.0 + progress)))
                score = (current_r * boundary_weight) / density_penalty
            
            if score > best_score:
                best_score = score
                best_r = current_r
                best_pos = candidate
        
        circles.append([best_pos[0], best_pos[1], best_r])
    
    return np.array(circles)
