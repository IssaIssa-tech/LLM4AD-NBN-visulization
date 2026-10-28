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
    
    # Latin Hypercube initialization
    sampler = qmc.LatinHypercube(d=2, seed=2025)
    points = sampler.random(n)
    circles = np.zeros((n, 3))
    circles[:, :2] = points
    
    # Simulated annealing with cosine annealing for local search
    for iteration in range(1000):
        temperature = 0.4 * (1 + np.cos(iteration * np.pi / 500))
        
        for i in range(n):
            x, y = circles[i, :2]
            
            # Radius expansion
            max_r = min(x, 1-x, y, 1-y)
            for j in range(n):
                if i == j:
                    continue
                dist = np.sqrt((circles[j,0]-x)**2 + (circles[j,1]-y)**2)
                max_r = min(max_r, dist - circles[j,2])
            
            # Local search with simulated annealing
            for _ in range(4):
                if np.random.random() < 0.5:
                    step_size = 0.07 * (1 - iteration/1000)**3
                    new_x = np.clip(x + np.random.uniform(-step_size, step_size), 0, 1)
                    new_y = np.clip(y + np.random.uniform(-step_size, step_size), 0, 1)
                else:
                    step_size = temperature * (np.random.rand()**2 - 0.5) / 10
                    new_x = x + step_size * np.sign(np.random.randn())
                    new_y = y + step_size * np.sign(np.random.randn())
                
                current_r = min(new_x, 1-new_x, new_y, 1-new_y)
                for j in range(n):
                    if i == j:
                        continue
                    dist = np.sqrt((circles[j,0]-new_x)**2 + (circles[j,1]-new_y)**2)
                    current_r = min(current_r, dist - circles[j,2])
                
                # Acceptance with Metropolis criterion
                if current_r > max_r or np.random.random() < np.exp((current_r - max_r)/temperature):
                    max_r = current_r
                    x, y = new_x, new_y
    
    return circles
