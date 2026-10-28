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
    
    # Modified placement strategy with deterministic random seeds for local search
    def place_circle(circles):
        best_sum_r = 0
        best_circles = None
        
        for _ in range(10):  # Number of iterations to refine the placement
            new_circles = circles.copy()
            
            for i, (x, y) in enumerate(new_circles[:, :2]):
                max_radius = min(x, 1 - x, y, 1 - y)
                
                for j, (_, _, r) in enumerate(circles):
                    if i == j:
                        continue
                    dist = np.sqrt((new_circles[j,0]-x)**2 + (new_circles[j,1]-y)**2)
                    max_radius = min(max_radius, dist - r)
                
                new_x = x + 0.03 * (np.random.rand() - 0.5)  # Determistic random seed
                new_y = y + 0.03 * (np.random.rand() - 0.5)
                max_radius = min(max_radius, np.sqrt((new_x-x)**2 + (new_y-y)**2))
                
                if max_radius > r:
                    new_r = max_radius
                else:
                    new_r = r
                
                new_circles[i] = [new_x, new_y, new_r]
            
            current_sum_r = np.sum(new_circles[:, 2])
            if current_sum_r > best_sum_r:
                best_sum_r = current_sum_r
                best_circles = new_circles
        
        return best_circles
    
    circles = place_circle(circles)
    
    # Local search with deterministic random seeds for overlap detection and repair
    def local_search(circles):
        for _ in range(10):  # Number of iterations to refine the placement
            new_circles = circles.copy()
            
            for i, (x, y, r) in enumerate(new_circles):
                max_radius = min(x, 1 - x, y, 1 - y)
                
                for j, (_, _, rr) in enumerate(circles):
                    if i == j:
                        continue
                    dist = np.sqrt((new_circles[j,0]-x)**2 + (new_circles[j,1]-y)**2)
                    max_radius = min(max_radius, dist - rr)
                
                new_x = x + 0.03 * (np.random.rand() - 0.5)  # Determistic random seed
                new_y = y + 0.03 * (np.random.rand() - 0.5)
                max_radius = min(max_radius, np.sqrt((new_x-x)**2 + (new_y-y)**2))
                
                if max_radius > r:
                    new_r = max_radius
                else:
                    new_r = r
                
                new_circles[i] = [new_x, new_y, new_r]
            
            for i in range(n):
                for j in range(i+1, n):
                    dx, dy = circles[i][0]-circles[j][0], circles[i][1]-circles[j][1]
                    dist = np.sqrt(dx**2 + dy**2)
                    
                    if dist < (circles[i][2] + circles[j][2]):
                        # Repair by moving the circle with smaller radius closer to the other
                        if circles[i][2] > circles[j][2]:
                            new_x, new_y = circles[j][0], circles[j][1]
                            new_r = circles[j][2]
                        else:
                            new_x, new_y = circles[i][0], circles[i][1]
                            new_r = circles[i][2]
                        
                        new_circles[i] = [new_x, new_y, new_r]
            
            if np.sum(new_circles[:, 2]) > np.sum(circles[:, 2]):
                circles = new_circles
    
    local_search(circles)
    
    return circles
