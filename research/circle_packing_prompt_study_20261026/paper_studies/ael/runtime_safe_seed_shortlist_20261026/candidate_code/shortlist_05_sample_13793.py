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
    
    np.random.seed(2025)
    if n == 0:
        return np.zeros((0, 3))
    
    # Hexagonal grid initialization
    circles = np.zeros((n, 3))
    if n == 1:
        circles[0] = [0.5, 0.5, 0.5]
        return circles
    
    rows = int(np.ceil(np.sqrt(n / (2/np.sqrt(3)))))
    spacing = 1.0 / (rows + 1)
    index = 0
    for i in range(rows):
        for j in range(rows):
            if index >= n:
                break
            x = (j + 0.5 * (i % 2)) * spacing
            y = i * spacing * np.sqrt(3)/2
            if x <= 1 and y <= 1:
                circles[index, :2] = [x, y]
                index += 1
        if index >= n:
            break
    
    # Normalize to fit in unit square
    max_x = np.max(circles[:, 0])
    max_y = np.max(circles[:, 1])
    circles[:, 0] /= max_x
    circles[:, 1] /= max_y
    
    # Initial radii (small to avoid overlap)
    circles[:, 2] = 0.5 * np.minimum(np.minimum(circles[:, 0], 1 - circles[:, 0]),
                                    np.minimum(circles[:, 1], 1 - circles[:, 1]))
    
    # Optimization function
    def objective(params):
        positions = params.reshape(-1, 2)
        radii = np.zeros(n)
        for i in range(n):
            x, y = positions[i]
            radii[i] = min(x, 1-x, y, 1-y)
            for j in range(i):
                dist = np.sqrt((positions[j,0]-x)**2 + (positions[j,1]-y)**2)
                radii[i] = min(radii[i], dist - radii[j])
                radii[j] = min(radii[j], dist - radii[i])
        return -np.sum(radii)
    
    # Gradient-based optimization
    bounds = [(0, 1)] * (2 * n)
    x0 = circles[:, :2].flatten()
    result = minimize(objective, x0, method='L-BFGS-B', bounds=bounds, 
                      options={'maxiter': 10000, 'ftol': 1e-8})
    
    # Final radii calculation
    positions = result.x.reshape(-1, 2)
    radii = np.zeros(n)
    for i in range(n):
        x, y = positions[i]
        radii[i] = min(x, 1-x, y, 1-y)
        for j in range(i):
            dist = np.sqrt((positions[j,0]-x)**2 + (positions[j,1]-y)**2)
            radii[i] = min(radii[i], dist - radii[j])
            radii[j] = min(radii[j], dist - radii[i])
    
    circles = np.column_stack((positions, radii))
    return circles
