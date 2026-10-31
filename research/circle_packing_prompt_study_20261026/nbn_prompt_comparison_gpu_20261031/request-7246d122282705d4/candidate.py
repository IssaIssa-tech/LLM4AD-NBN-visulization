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
    circles[:, 2] = np.minimum(np.minimum(circles[:, 0], 1 - circles[:, 0]),
                              np.minimum(circles[:, 1], 1 - circles[:, 1])) * 0.15
    
    # Particle Swarm Optimization (PSO) for placement and local search
    num_particles = 50
    max_iterations = 1000
    w = 0.7  # inertia weight
    c1 = 1.4  # cognitive coefficient
    c2 = 1.4  # social coefficient
    
    velocities = np.zeros((num_particles, n, 3))
    personal_best = np.copy(circles)
    global_best = np.copy(circles)
    personal_best_scores = np.zeros(num_particles)
    global_best_score = np.sum(np.max(personal_best[:, 2]))
    
    for iteration in range(max_iterations):
        for i in range(num_particles):
            for j in range(n):
                r1 = np.random.rand()
                r2 = np.random.rand()
                velocities[i, j] = w * velocities[i, j] + \
                                   c1 * r1 * (personal_best[i, j] - circles[i, j]) + \
                                   c2 * r2 * (global_best[j] - circles[i, j])
                circles[i, j] += velocities[i, j]
                circles[i, j, :2] = np.clip(circles[i, j, :2], 0, 1)
                circles[i, j, 2] = min(circles[i, j, 2], min(circles[i, j, 0], 1 - circles[i, j, 0], circles[i, j, 1], 1 - circles[i, j, 1]))
                
                if np.sum(circles[i, j, 2]) > personal_best_scores[i]:
                    personal_best[i, j] = circles[i, j]
                    personal_best_scores[i] = np.sum(circles[i, j, 2])
                    if np.sum(circles[i, j, 2]) > global_best_score:
                        global_best[j] = circles[i, j]
                        global_best_score = np.sum(circles[i, j, 2])
    
    return global_best
