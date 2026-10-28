import numpy as np
from scipy.optimize import minimize

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
    
    # Latin Hypercube Sampling initialization
    sampler = qmc.LatinHypercube(d=2, seed=2025)
    points = sampler.random(n)
    circles = np.zeros((n, 3))
    circles[:, :2] = points
    
    # Modified simulated annealing with cosine annealing
    for iteration in range(40000):
        temperature = 0.4 * (1 + np.cos(iteration * np.pi / 40000))
        
        def objective(circles, i):
            x, y, r = circles[i]
            best_pos = None
            best_r = 0
            
            for _ in range(30):
                if np.random.rand() < 0.15:
                    step_size = 0.25 * temperature
                    new_x = np.clip(x + np.random.normal(0, 1) * step_size, 0, 1)
                    new_y = np.clip(y + np.random.normal(0, 1) * step_size, 0, 1)
                else:
                    step_size = 0.05 * (1 - iteration / 40000)**2
                    new_x = np.clip(x + np.random.uniform(-step_size, step_size), 0, 1)
                    new_y = np.clip(y + np.random.uniform(-step_size, step_size), 0, 1)
                
                current_r = min(new_x, 1-new_x, new_y, 1-new_y)
                for j in range(n):
                    if i == j:
                        continue
                    dist = np.sqrt((circles[j,0]-new_x)**2 + (circles[j,1]-new_y)**2)
                    current_r = min(current_r, dist - circles[j,2])
                
                if current_r > best_r:
                    best_r = current_r
                    best_pos = (new_x, new_y, current_r)
            
            return best_r
    
        for i in range(n):
            x, y, r = circles[i]
            min_radius = np.minimum(np.minimum(x, 1-x), np.minimum(y, 1-y))
            for j in range(n):
                if i == j:
                    continue
                dist = np.sqrt((circles[j,0]-x)**2 + (circles[j,1]-y)**2)
                min_radius = min(min_radius, dist - circles[j,2])
            
            best_r = objective(circles, i)
            if best_r > r or np.random.rand() < np.exp((best_r - r) / max(temperature, 1e-8)):
                x, y, r = best_pos
                circles[i] = (x, y, r)
    
    return circles

# Example usage:
result = pack_circles(26)
print(result)
