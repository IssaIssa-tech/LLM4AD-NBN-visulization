import numpy as np
from scipy.stats import qmc

def pack_circles(n: int) -> np.ndarray:
    """
    Pack n circles in a unit square to maximize sum of radii using Sobol sequence for initialization and simulated annealing with Gaussian perturbations.

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
    
    # Sobol sequence initialization
    sampler = qmc.Sobol(d=2, seed=2025)
    points = sampler.random(n)
    circles = np.zeros((n, 3))
    circles[:, :2] = points
    
    # Simulated annealing with Gaussian perturbations and exponential cooling
    for iteration in range(4000):
        temperature = 0.9 * (iteration / 1000) + 0.1
        
        for i in range(n):
            x, y, r = circles[i]
            
            # Radius expansion
            max_r = min(x, 1-x, y, 1-y)
            for j in range(n):
                if i == j:
                    continue
                dist = np.sqrt((circles[j,0]-x)**2 + (circles[j,1]-y)**2)
                max_r = min(max_r, dist - circles[j,2])
            
            # Gaussian perturbations
            for _ in range(3):
                step_size = 0.05 * np.random.randn()
                new_x = x + step_size if np.random.rand() < 0.5 else x - step_size
                new_y = y + step_size if np.random.rand() < 0.5 else y - step_size
                
                current_r = min(new_x, 1-new_x, new_y, 1-new_y)
                for j in range(n):
                    if i == j:
                        continue
                    dist = np.sqrt((circles[j,0]-new_x)**2 + (circles[j,1]-new_y)**2)
                    current_r = min(current_r, dist - circles[j,2])
                
                if current_r > r and np.random.rand() < np.exp((current_r - r) / temperature):
                    circles[i] = [new_x, new_y, current_r]
    
    # Ensure all circles are within the unit square
    for i in range(n):
        x, y, _ = circles[i]
        if not (0 <= x <= 1 and 0 <= y <= 1):
            circles[i] = np.random.rand(3) * 2 - 1
    
    # Ensure pairwise non-overlap
    def overlap(c1, c2):
        return np.sqrt((c1[0]-c2[0])**2 + (c1[1]-c2[1])**2) < c1[2] + c2[2]
    
    while any(overlap(circles[i], circles[j]) for i in range(n) for j in range(i+1, n)):
        for i in range(n):
            x, y, r = circles[i]
            min_overlap_x = max(x - r, 0)
            max_overlap_x = min(x + r, 1)
            min_overlap_y = max(y - r, 0)
            max_overlap_y = min(y + r, 1)
            
            for j in range(n):
                if i == j:
                    continue
                cx, cy, cr = circles[j]
                
                # Check if there is an overlap and adjust the position of circle i
                if (min_overlap_x <= cx < max_overlap_x and min_overlap_y <= cy < max_overlap_y) or \
                   (min_overlap_y <= cx < max_overlap_y and min_overlap_x <= cy < max_overlap_x):
                    dx = x - cx
                    dy = y - cy
                    
                    # Calculate the new position for circle i after perturbation
                    if np.random.rand() < 0.5:
                        x_new = x + (cx - x) * np.random.randn()
                    else:
                        x_new = x - (x - cx) * np.random.randn()
                    
                    if np.random.rand() < 0.5:
                        y_new = y + (cy - y) * np.random.randn()
                    else:
                        y_new = y - (y - cy) * np.random.randn()
                    
                    # Ensure the new position is within bounds
                    x_new = max(0, min(x_new, 1))
                    y_new = max(0, min(y_new, 1))
                    
                    circles[i] = [x_new, y_new, r]
    
    return circles
