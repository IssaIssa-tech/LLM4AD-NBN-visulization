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
    for i in range(n):
        best_score = -np.inf
        best_pos = (0.5, 0.5)
        best_r = 0
        
        partitions = []
        weights = []
        
        if circles:
            existing = np.array([c[:2] for c in circles])
            radii = np.array([c[2] for c in circles])
            
            for j in range(len(existing)):
                theta = np.linspace(0, 2*np.pi, 24, endpoint=False)
                offset = 1.7 * radii[j]
                region = existing[j] + offset * np.column_stack([np.cos(theta), np.sin(theta)])
                partitions.append(region.clip(0.01, 0.99))
                weights.append(1.0 / (radii[j] + 0.1))
            
            boundary_regions = np.random.uniform(0.01, 0.99, (16, 2))
            boundary_regions[:, np.random.randint(2, size=16)] = np.random.choice([0.01, 0.99], size=16)
            partitions.append(boundary_regions)
            weights.append(2.0)
            
            corner_regions = np.random.uniform(0.01, 0.2, (8, 2))
            partitions.append(np.vstack([corner_regions, 1 - corner_regions]))
            weights.append(1.5)
        else:
            partitions = [np.random.uniform(0.01, 0.99, (1, 2))]
            weights = [1.0]
        
        weights = np.array(weights)
        weights /= weights.sum()
        
        for _ in range(150):
            region_idx = np.random.choice(len(partitions), p=weights)
            region = partitions[region_idx]
            candidate = region[np.random.randint(len(region))]
            
            if len(circles) == 0:
                dist_to_boundary = min(candidate[0], candidate[1], 1 - candidate[0], 1 - candidate[1])
                current_r = dist_to_boundary
                score = current_r * (1.0 + 2.0 * np.exp(-3.0 * dist_to_boundary))
            else:
                existing = np.array([c[:2] for c in circles])
                radii = np.array([c[2] for c in circles])
                dists = np.sqrt(((existing - candidate)**2).sum(axis=1)) - radii
                dist_to_boundary = min(candidate[0], candidate[1], 1 - candidate[0], 1 - candidate[1])
                current_r = min(dists.min(), dist_to_boundary)
                
                boundary_attraction = 2.0 * np.exp(-3.5 * dist_to_boundary) * (1 - (i / n)**2)
                repulsion = np.exp(-5.0 * (dists.min() - current_r))
                score = current_r * (1.0 + boundary_attraction + repulsion)
            
            if score > best_score and current_r > 0.01:
                best_score = score
                best_r = current_r
                best_pos = candidate
        
        circles.append([best_pos[0], best_pos[1], best_r])
    
    return np.array(circles)
