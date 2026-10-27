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
        
        boundary_samples = np.random.uniform(0, 1, (300, 2))
        boundary_samples = np.vstack([
            boundary_samples,
            np.column_stack([np.random.uniform(0, 1, 150), np.zeros(150)]),
            np.column_stack([np.random.uniform(0, 1, 150), np.ones(150)]),
            np.column_stack([np.zeros(150), np.random.uniform(0, 1, 150)]),
            np.column_stack([np.ones(150), np.random.uniform(0, 1, 150)])
        ])
        candidates.extend(boundary_samples)
        
        for candidate in candidates:
            if len(circles) == 0:
                dist_to_boundary = min(candidate[0], candidate[1], 1 - candidate[0], 1 - candidate[1])
                current_r = dist_to_boundary
                corner_factor = 1.0 - min(candidate[0], 1 - candidate[0]) * min(candidate[1], 1 - candidate[1]) * 4
                boundary_weight = 1.0 + 2.0 * (1 - dist_to_boundary)**2 + corner_factor
                score = current_r * boundary_weight
            else:
                existing = np.array([c[:2] for c in circles])
                radii = np.array([c[2] for c in circles])
                dists = np.sqrt(((existing - candidate)**2).sum(axis=1)) - radii
                dist_to_boundary = min(candidate[0], candidate[1], 1 - candidate[0], 1 - candidate[1])
                current_r = min(dists.min(), dist_to_boundary)
                corner_factor = 1.0 - min(candidate[0], 1 - candidate[0]) * min(candidate[1], 1 - candidate[1]) * 4
                boundary_weight = 1.0 + (1 - dist_to_boundary)**2 + corner_factor
                score = current_r * boundary_weight
            
            if score > best_score:
                best_score = score
                best_r = current_r
                best_pos = candidate
        
        circles.append([best_pos[0], best_pos[1], best_r])
    
    return np.array(circles)
