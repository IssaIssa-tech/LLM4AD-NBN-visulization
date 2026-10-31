import numpy as np
from scipy.optimize import minimize
from scipy.spatial.distance import pdist, squareform

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
    
    # Latin Hypercube Sampling initialization
    sampler = qmc.LatinHypercube(d=2, seed=2025)
    points = sampler.random(n)
    circles = np.zeros((n, 3))
    circles[:, :2] = points
    circles[:, 2] = np.minimum(np.minimum(circles[:, 0], 1 - circles[:, 0]), 
                              np.minimum(circles[:, 1], 1 - circles[:, 1])) * 0.2
    
    def objective(x, idx):
        circles[idx, :2] = x
        r = min(x[0], 1-x[0], x[1], 1-x[1])
        for j in range(n):
            if j == idx:
                continue
            dist = np.sqrt((circles[j,0]-x[0])**2 + (circles[j,1]-x[1])**2)
            r = min(r, dist - circles[j,2])
        return -r
    
    for iteration in range(100):
        # Optimize each circle position
        for i in range(n):
            res = minimize(objective, circles[i, :2], args=(i,), 
                          method='Nelder-Mead', 
                          options={'maxiter': 50, 'xatol': 1e-4})
            circles[i, :2] = np.clip(res.x, 0, 1)
            circles[i, 2] = -res.fun
        
        # Global resampling of worst circles
        if iteration % 10 == 0 and iteration > 0:
            radii = circles[:, 2]
            worst = np.argsort(radii)[:max(1, n//5)]
            sampler = qmc.LatinHypercube(d=2, seed=2025+iteration)
            new_points = sampler.random(len(worst))
            for k, idx in enumerate(worst):
                circles[idx, :2] = new_points[k]
                circles[idx, 2] = min(new_points[k][0], 1-new_points[k][0], 
                                     new_points[k][1], 1-new_points[k][1]) * 0.2
        
        # Check for overlap
        distances = squareform(pdist(circles[:, :2]))
        np.fill_diagonal(distances, np.inf)
        if np.any(distances < (circles[:, 2][:, np.newaxis] + circles[:, 2][np.newaxis, :])):
            # If overlap, adjust positions slightly
            for i in range(n):
                for j in range(i+1, n):
                    if distances[i, j] < (circles[i, 2] + circles[j, 2]):
                        dx = circles[j, 0] - circles[i, 0]
                        dy = circles[j, 1] - circles[i, 1]
                        d = np.sqrt(dx**2 + dy**2)
                        circles[i, :2] += (circles[j, :2] - circles[i, :2]) * (circles[i, 2] + circles[j, 2] - d) / d
                        circles[j, :2] -= (circles[j, :2] - circles[i, :2]) * (circles[i, 2] + circles[j, 2] - d) / d
    
    return circles
