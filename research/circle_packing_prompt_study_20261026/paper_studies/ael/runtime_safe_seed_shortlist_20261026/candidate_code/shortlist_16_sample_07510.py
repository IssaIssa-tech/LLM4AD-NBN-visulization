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
    from scipy.optimize import minimize
    from scipy.spatial.distance import cdist
    
    np.random.seed(2025)
    if n == 0:
        return np.zeros((0, 3))
    
    # Hexagonal grid initialization for perfect hexagonal numbers
    def is_hexagonal(k):
        return ((8*k + 1)**0.5 - 1) % 2 == 0
    
    if is_hexagonal(n):
        k = int(((8*n + 1)**0.5 - 1) // 2)
        circles = np.zeros((n, 3))
        idx = 0
        spacing = 1.0 / (k + 1)
        for i in range(k):
            for j in range(i + 1):
                circles[idx, 0] = 0.5 + (j - i/2) * spacing
                circles[idx, 1] = (i + 1) * spacing * 0.8660254037844386
                idx += 1
    else:
        # Greedy placement for non-hexagonal numbers
        circles = np.zeros((n, 3))
        circles[0] = [0.5, 0.5, 0.5]
        for i in range(1, n):
            best_score = -1
            best_pos = None
            for _ in range(100):
                x, y = np.random.rand(2)
                min_dist = min(np.sqrt((x-c[0])**2 + (y-c[1])**2) - c[2] for c in circles[:i])
                if min_dist > best_score:
                    best_score = min_dist
                    best_pos = (x, y, best_score)
            circles[i] = best_pos
    
    # Optimization function
    def objective(x):
        centers = x.reshape(-1, 2)
        radii = np.minimum(np.minimum(centers[:,0], 1-centers[:,0]),
                          np.minimum(centers[:,1], 1-centers[:,1]))
        dists = cdist(centers, centers) + np.eye(len(centers))
        radii = np.minimum(radii, (dists - radii).min(axis=1))
        return -radii.sum()
    
    # L-BFGS-B optimization
    bounds = [(0, 1)] * (2 * n)
    res = minimize(objective, circles[:,:2].flatten(), method='L-BFGS-B',
                   bounds=bounds, options={'maxiter': 1000})
    
    centers = res.x.reshape(-1, 2)
    radii = np.minimum(np.minimum(centers[:,0], 1-centers[:,0]),
                      np.minimum(centers[:,1], 1-centers[:,1]))
    dists = cdist(centers, centers) + np.eye(len(centers))
    radii = np.minimum(radii, (dists - radii).min(axis=1))
    
    # Final greedy radius maximization
    for i in range(n):
        x, y = centers[i]
        max_r = min(x, 1-x, y, 1-y)
        for j in range(n):
            if i == j:
                continue
            dist = np.sqrt((centers[j,0]-x)**2 + (centers[j,1]-y)**2)
            max_r = min(max_r, dist - radii[j])
        radii[i] = max_r
    
    return np.column_stack((centers, radii))
