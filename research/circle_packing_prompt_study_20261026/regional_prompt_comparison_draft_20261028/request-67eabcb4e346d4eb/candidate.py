import numpy as np
from scipy.stats import qmc

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
    
    # Halton sequence initialization
    sampler = qmc.Halton(d=2, seed=2025)
    points = sampler.random(n)
    circles = np.zeros((n, 3))
    circles[:, :2] = points
    
    # Initial placement of circles using a simple greedy algorithm
    for i in range(n):
        x, y = circles[i]
        r = min(x, 1-x, y, 1-y) * 0.1
        
        # Find the circle that is closest to (x, y)
        distances = np.sqrt((circles[:, 0] - x)**2 + (circles[:, 1] - y)**2)
        nearest_circle_index = np.argmin(distances)
        
        # Update position and radius
        circles[i, 2] = r
        if i != nearest_circle_index:
            circles[nearest_circle_index, 2] += r
        
    # Local search to improve the placement of circles
    for _ in range(10):
        for i in range(n):
            x, y, r = circles[i]
            
            # Radius expansion
            max_r = min(x, 1-x, y, 1-y)
            for j in range(n):
                if i == j:
                    continue
                dist = np.sqrt((circles[j,0]-x)**2 + (circles[j,1]-y)**2)
                max_r = min(max_r, dist - circles[j,2])
            
            # Update position and radius
            circles[i] = [x, y, r]
            if i != j:
                circles[j] += r
        
        # Check for overlap and adjust positions accordingly
        for i in range(n):
            x, y, r = circles[i]
            for j in range(i+1, n):
                dx, dy, dr = circles[j] - [x, y, r]
                if np.sqrt(dx**2 + dy**2) < r + dr:
                    # Adjust positions to avoid overlap
                    min_r = min(r, dr)
                    max_r = min(max(x, 1-x), max(y, 1-y))
                    circles[i] = [x - (r - min_r), y - (r - min_r), r]
                    circles[j] = [x + (dr - max_r), y + (dr - max_r), dr]
    
    return circles
