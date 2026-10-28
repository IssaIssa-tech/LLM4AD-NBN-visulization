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
    
    The algorithm uses a local search approach with perturbation and acceptance criteria. It iteratively improves the positions of circles by randomly perturbing their centers within a small radius around their current position and accepting better configurations based on simulated annealing.
    """
    np.random.seed(2025)
    if n == 0:
        return np.zeros((0, 3))
    
    # Initialize random positions for the circles
    points = qmc.LatinHypercube(d=2, seed=2025).random(n) * 2 - 1
    radii = np.random.uniform(0.05, 0.4, n)
    centers = np.column_stack((points[:, 0], points[:, 1]))
    
    # Local search with perturbation and acceptance criteria
    for _ in range(30000):
        temperature = 0.5 * (1 + np.cos(_ / 30000))
        
        for i in range(n):
            x, y = centers[i]
            
            # Radius expansion
            max_r = min(x, 1-x, y, 1-y)
            for j in range(n):
                if i == j:
                    continue
                dist = np.sqrt((centers[j][0]-x)**2 + (centers[j][1]-y)**2)
                max_r = min(max_r, dist - centers[j][2])
            
            # Perturbation and acceptance criteria
            perturbations = [(x + np.random.normal(0, 0.05), y + np.random.normal(0, 0.05))]
            for _ in range(10):
                new_x, new_y = perturbations[-1]
                if (new_x > -1 and new_x < 1) and (new_y > -1 and new_y < 1):
                    perturbations.append((new_x, new_y))
            
            best_pos = None
            for pos in perturbations:
                x, y = pos
                current_r = min(x, 1-x, y, 1-y)
                for j in range(n):
                    if i == j:
                        continue
                    dist = np.sqrt((centers[j][0]-x)**2 + (centers[j][1]-y)**2)
                    current_r = min(current_r, dist - centers[j][2])
                
                if best_pos is None or current_r > best_pos[3]:
                    best_pos = (pos[0], pos[1], radii[i], current_r)
            
            # Simulated annealing acceptance
            if best_pos is not None and np.random.random() < np.exp((best_pos[3] - radii[i]) / max(temperature, 1e-8)):
                centers[i] = best_pos[:2]
                radii[i] = best_pos[2]
    
    return np.column_stack((centers[:,0], centers[:,1], radii))
