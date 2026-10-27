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
        best_pos = (0.5, 0.5)
        best_r = 0
        
        candidates = []
        if circles:
            existing = np.array([c[:2] for c in circles])
            radii = np.array([c[2] for c in circles])
            
            # Generate tangent points around existing circles
            for i in range(len(existing)):
                theta = np.linspace(0, 2*np.pi, 24, endpoint=False)
                offset = radii[i] * 1.2
                new_points = existing[i] + offset * np.column_stack([np.cos(theta), np.sin(theta)])
                candidates.extend(new_points.clip(0, 1))
                
            # Project existing points to boundaries
            boundary_projections = []
            for pt in existing:
                dists = np.array([pt[0], pt[1], 1-pt[0], 1-pt[1]])
                min_idx = np.argmin(dists)
                if min_idx == 0:
                    boundary_projections.append([0, pt[1]])
                elif min_idx == 1:
                    boundary_projections.append([pt[0], 0])
                elif min_idx == 2:
                    boundary_projections.append([1, pt[1]])
                else:
                    boundary_projections.append([pt[0], 1])
            candidates.extend(boundary_projections)
            
            # Stratified random sampling
            grid_size = min(20, max(5, int(np.sqrt(len(existing)) * 3)))
            for _ in range(10):
                x = np.random.uniform(0, 1, grid_size)
                y = np.random.uniform(0, 1, grid_size)
                candidates.extend(np.column_stack([x, y]))
        
        # Boundary-focused sampling
        boundary_samples = np.random.uniform(0, 1, (40, 2))
        boundary_samples[:, 0] = np.where(np.random.rand(40) < 0.5, 0, 1)
        boundary_samples[:, 1] = np.where(np.random.rand(40) < 0.5, 0, 1)
        candidates.extend(boundary_samples)
        
        for candidate in candidates:
            if len(circles) == 0:
                dist_to_boundary = min(candidate[0], candidate[1], 1 - candidate[0], 1 - candidate[1])
                current_r = dist_to_boundary
                boundary_weight = 1 / (1 + np.exp(-5 * (0.2 - dist_to_boundary)))
                score = current_r * (1 + boundary_weight)
            else:
                existing = np.array([c[:2] for c in circles])
                radii = np.array([c[2] for c in circles])
                dists = np.sqrt(((existing - candidate)**2).sum(axis=1)) - radii
                dist_to_boundary = min(candidate[0], candidate[1], 1 - candidate[0], 1 - candidate[1])
                current_r = min(dists.min(), dist_to_boundary)
                
                density = len(circles) / n
                boundary_weight = 1 / (1 + np.exp(-5 * (0.2 - dist_to_boundary))) * (1 + 0.3 * density)
                score = current_r * (1 + boundary_weight)
            
            if score > best_score and current_r > 0:
                best_score = score
                best_r = current_r
                best_pos = candidate
        
        circles.append([best_pos[0], best_pos[1], best_r])
    
    return np.array(circles)
