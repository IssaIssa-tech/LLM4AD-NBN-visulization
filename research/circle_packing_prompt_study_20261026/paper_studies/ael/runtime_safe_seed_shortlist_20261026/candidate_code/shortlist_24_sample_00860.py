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
    grid_size = 10
    
    for _ in range(n):
        best_score = -1
        best_pos = (0.5, 0.5)
        best_r = 0
        
        # Generate grid points
        x = np.linspace(0, 1, grid_size)
        y = np.linspace(0, 1, grid_size)
        xx, yy = np.meshgrid(x, y)
        candidates = np.column_stack([xx.ravel(), yy.ravel()])
        
        # Add random perturbations
        perturbations = np.random.uniform(-0.5/grid_size, 0.5/grid_size, (len(candidates), 2))
        candidates = np.clip(candidates + perturbations, 0, 1)
        
        # Evaluate candidates
        for candidate in candidates:
            if not (0 <= candidate[0] <= 1 and 0 <= candidate[1] <= 1):
                continue
                
            if len(circles) == 0:
                dist_to_boundary = min(candidate[0], candidate[1], 1 - candidate[0], 1 - candidate[1])
                current_r = dist_to_boundary
                score = current_r
            else:
                existing = np.array([c[:2] for c in circles])
                radii = np.array([c[2] for c in circles])
                dists = np.sqrt(((existing - candidate)**2).sum(axis=1)) - radii
                dist_to_boundary = min(candidate[0], candidate[1], 1 - candidate[0], 1 - candidate[1])
                current_r = min(dists.min(), dist_to_boundary)
                score = current_r
            
            if score > best_score:
                best_score = score
                best_r = current_r
                best_pos = candidate
        
        circles.append([best_pos[0], best_pos[1], best_r])
        
        # Adapt grid size based on remaining space
        grid_size = min(50, grid_size + 2)
    
    return np.array(circles)
