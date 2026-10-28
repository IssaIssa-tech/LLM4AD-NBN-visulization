import numpy as np
from scipy.stats import qmc

def pack_circles(n: int) -> np.ndarray:
    """
    Pack n circles in a unit square to maximize sum of radii using Latin Hypercube initialization and gradient ascent for local search.

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
    
    # Latin Hypercube initialization
    sampler = qmc.LatinHypercube(d=2, seed=2025)
    points = sampler.random(n)
    circles = np.zeros((n, 3))
    circles[:, :2] = points
    circles[:, 2] = np.minimum(np.minimum(circles[:, 0], 1 - circles[:, 0]),
                              np.minimum(circles[:, 1], 1 - circles[:, 1])) * 0.15
    
    # Gradient ascent for local search
    def gradient_ascent(circles):
        gradients = np.zeros((n, 2))
        
        for i in range(n):
            x, y, r = circles[i]
            
            # Radius expansion
            max_r = min(x, 1-x, y, 1-y)
            for j in range(n):
                if i == j:
                    continue
                dist = np.sqrt((circles[j,0]-x)**2 + (circles[j,1]-y)**2)
                max_r = min(max_r, dist - circles[j,2])
            
            # Compute gradients using the distance to other circles
            for j in range(n):
                if i == j:
                    continue
                dx, dy = circles[j,0] - x, circles[j,1] - y
                d_squared = dx**2 + dy**2
                gradients[i] += np.array([-dx / d_squared, -dy / d_squared])
        
        # Update positions using the gradient ascent step size
        for i in range(n):
            circles[i] += 0.05 * gradients[i]
    
    # Perform local search
    for _ in range(2000):
        gradient_ascent(circles)
    
    # Ensure all circles are within the unit square and non-overlapping
    for i, (x, y, r) in enumerate(circles):
        if x < 0 or x > 1:
            circles[i] = np.array([np.random.rand(), np.random.rand(), 0.1])
        if y < 0 or y > 1:
            circles[i] = np.array([np.random.rand(), np.random.rand(), 0.1])
    
    # Check containment and pairwise non-overlap
    for i in range(n):
        for j in range(i+1, n):
            dx, dy = circles[j,0] - circles[i,0], circles[j,1] - circles[i,1]
            dist_squared = dx**2 + dy**2
            if np.sqrt(dist_squared) < (circles[i, 2] + circles[j, 2]):
                return pack_circles(n)
    
    return circles
