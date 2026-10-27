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
    for _ in range(n):
        best_score = -1
        best_pos = (0, 0)
        best_r = 0
        
        candidates = []
        if circles:
            existing = np.array([c[:2] for c in circles])
            candidates.extend(existing)
            for _ in range(50):
                offset = np.random.uniform(-0.1, 0.1, size=(len(existing), 2))
                candidates.extend(existing + offset)
        
        boundary_samples = np.random.uniform(0, 1, (50, 2))
        boundary_samples = np.vstack([
            boundary_samples,
            np.column_stack([np.random.uniform(0, 1, 10), np.zeros(10)]),
            np.column_stack([np.random.uniform(0, 1, 10), np.ones(10)]),
            np.column_stack([np.zeros(10), np.random.uniform(0, 1, 10)]),
            np.column_stack([np.ones(10), np.random.uniform(0, 1, 10)])
        ])
        candidates.extend(boundary_samples)
        
        for candidate in candidates:
            if len(circles) == 0:
                dist_to_boundary = min(candidate[0], candidate[1], 1 - candidate[0], 1 - candidate[1])
                current_r = dist_to_boundary
                boundary_weight = 1.2
                score = current_r * boundary_weight
            else:
                existing = np.array([c[:2] for c in circles])
                radii = np.array([c[2] for c in circles])
                dists = np.sqrt(((existing - candidate)**2).sum(axis=1)) - radii
                dist_to_boundary = min(candidate[0], candidate[1], 1 - candidate[0], 1 - candidate[1])
                current_r = min(dists.min(), dist_to_boundary)
                boundary_weight = 1.0 + (1.2 - min(dist_to_boundary * 1.2, 1.2))
                score = current_r * boundary_weight
            
            if score > best_score:
                best_score = score
                best_r = current_r
                best_pos = candidate
        
        circles.append([best_pos[0], best_pos[1], best_r])
    
    return np.array(circles)
