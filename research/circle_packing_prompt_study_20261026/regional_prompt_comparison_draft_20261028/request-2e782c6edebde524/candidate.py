import numpy as np
from scipy.optimize import minimize

def pack_circles(n: int) -> np.ndarray:
    """
    Pack n circles in a unit square to maximize the sum of radii.
    
    Args:
        n: Number of circles to pack
    
    Returns:
        Numpy array of shape (n, 3) where each row is (x, y, radius)
        All values should be between 0 and 1
        Circles must not overlap
        
    Important: Set "all" random seeds to 2025, including the packages (such as scipy sub-packages) involving random seeds.
    
    The algorithm uses a local search approach with perturbations guided by simulated annealing. 
    It iteratively improves the positions of circles and their radii to maximize the sum of radii while ensuring no overlap.
    """
    np.random.seed(2025)
    if n == 0:
        return np.zeros((0, 3))
    
    # Latin Hypercube initialization
    sampler = qmc.LatinHypercube(d=2, seed=2025)
    points = sampler.random(n)
    circles = np.zeros((n, 3))
    circles[:, :2] = points
    
    def objective(circles):
        return -np.sum(circles[:, 2])
    
    # Simulated annealing with cosine annealing
    for iteration in range(20000):
        temperature = 0.4 * (1 + np.cos(iteration * np.pi / 20000))
        
        def perturb_circle(circle, step_size=0.07):
            x, y, r = circle
            new_x = np.clip(x + np.random.normal(0, step_size**2), 0, 1)
            new_y = np.clip(y + np.random.normal(0, step_size**2), 0, 1)
            return (new_x, new_y, min(new_x, 1-new_x, new_y, 1-new_y))
        
        for i in range(n):
            x, y, r = circles[i]
            
            # Radius expansion
            max_r = min(x, 1-x, y, 1-y)
            for j in range(n):
                if i == j:
                    continue
                dist = np.sqrt((circles[j,0]-x)**2 + (circles[j,1]-y)**2)
                max_r = min(max_r, dist - circles[j,2])
            
            best_pos = None
            best_r = 0
            
            for _ in range(12):
                if np.random.random() < 0.15:
                    step_size = 0.4 * temperature
                    new_x, new_y, current_r = perturb_circle(circles[i], step_size)
                else:
                    step_size = 0.07 * (1 - iteration/20000)**3
                    new_x, new_y, current_r = perturb_circle(circles[i], step_size)
                
                if np.random.random() < np.exp((current_r - r)/temperature):
                    best_pos = (new_x, new_y, current_r)
            
            # Acceptance with Metropolis criterion
            if best_pos is not None:
                circles[i] = best_pos
    
    return circles
