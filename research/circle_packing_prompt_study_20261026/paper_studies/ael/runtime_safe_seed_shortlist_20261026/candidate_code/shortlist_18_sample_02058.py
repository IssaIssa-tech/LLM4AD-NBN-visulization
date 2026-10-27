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
        
        # Generate candidate positions
        candidates = []
        if circles:
            existing = np.array([c[:2] for c in circles])
            radii = np.array([c[2] for c in circles])
            
            # Force-directed candidates
            for i in range(len(existing)):
                direction = np.random.randn(2)
                direction /= np.linalg.norm(direction)
                force_magnitude = 1.5 * radii[i]
                new_point = existing[i] + force_magnitude * direction
                candidates.append(new_point.clip(0, 1))
            
            # Boundary attraction points
            boundary_attractors = np.array([[0,0], [0,1], [1,0], [1,1], [0.5,0], [0.5,1], [0,0.5], [1,0.5]])
            for attractor in boundary_attractors:
                direction = attractor - np.mean(existing, axis=0)
                direction /= np.linalg.norm(direction)
                new_point = np.mean(existing, axis=0) + 0.5 * direction
                candidates.append(new_point.clip(0, 1))
        
        # Adaptive random sampling
        sample_size = min(100, 10 + 5 * len(circles)**2)
        candidates.extend(np.random.uniform(0, 1, (sample_size, 2)))
        
        for candidate in candidates:
            if len(circles) == 0:
                dist_to_boundary = min(candidate[0], candidate[1], 1 - candidate[0], 1 - candidate[1])
                current_r = dist_to_boundary
                boundary_weight = 1.0 + 0.5 * np.exp(-5 * dist_to_boundary)
                score = current_r * boundary_weight
            else:
                existing = np.array([c[:2] for c in circles])
                radii = np.array([c[2] for c in circles])
                dists = np.sqrt(((existing - candidate)**2).sum(axis=1)) - radii
                dist_to_boundary = min(candidate[0], candidate[1], 1 - candidate[0], 1 - candidate[1])
                current_r = min(dists.min(), dist_to_boundary)
                
                density_factor = 1.0 + len(circles)/n
                boundary_weight = 1.2 * np.exp(-3 * dist_to_boundary) * density_factor
                repulsion = np.exp(-0.5 * ((dists - current_r)**2).mean())
                score = current_r * boundary_weight * repulsion
            
            if score > best_score and current_r > 0:
                best_score = score
                best_r = current_r
                best_pos = candidate
        
        circles.append([best_pos[0], best_pos[1], best_r])
    
    return np.array(circles)
