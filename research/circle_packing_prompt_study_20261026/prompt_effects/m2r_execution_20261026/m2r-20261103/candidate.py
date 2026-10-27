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
    circles[:, 2] = np.minimum(np.minimum(circles[:, 0], 1 - circles[:, 0]),
                              np.minimum(circles[:, 1], 1 - circles[:, 1])) * 0.2
    
    # Deterministic initialization and local refinement
    for i in range(n):
        x, y = circles[i, :2]
        max_r = min(x, 1-x, y, 1-y)
        
        for _ in range(50):  # Bounded number of iterations to avoid infinite loops
            new_x = np.clip(x + np.random.uniform(-0.05, 0.05), 0, 1)
            new_y = np.clip(y + np.random.uniform(-0.05, 0.05), 0, 1)
            
            current_r = min(new_x, 1-new_x, new_y, 1-new_y)
            for j in range(n):
                if i == j:
                    continue
                dist = np.sqrt((circles[j,0]-new_x)**2 + (circles[j,1]-new_y)**2)
                current_r = min(current_r, dist - circles[j,2])
            
            if current_r > max_r:
                max_r = current_r
                x, y = new_x, new_y
        
        circles[i] = np.array([x, y, max_r])
    
    # All-pairs boundary and overlap repair
    for i in range(n):
        for j in range(i+1, n):
            dist = np.sqrt((circles[i,0]-circles[j,0])**2 + (circles[i,1]-circles[j,1])**2)
            max_r = min(circles[i,2], circles[j,2])
            
            if dist < 2*max_r:
                # Repair by moving the smaller circle closer to the larger one
                if circles[i,2] > circles[j,2]:
                    circles[j] = np.array([circles[j,0]+(circles[i,0]-circles[j,0]), 
                                            circles[j,1]+(circles[i,1]-circles[j,1]), 
                                            max_r])
                else:
                    circles[i] = np.array([circles[i,0]+(circles[j,0]-circles[i,0]), 
                                            circles[i,1]+(circles[j,1]-circles[i,1]), 
                                            max_r])
    
    return circles
