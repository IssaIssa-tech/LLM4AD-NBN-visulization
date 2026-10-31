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
    
    # Sobol sequence initialization
    sampler = qmc.Sobol(d=2, seed=2025)
    points = sampler.random(n)
    circles = np.zeros((n, 3))
    circles[:, :2] = points
    circles[:, 2] = np.minimum(np.minimum(circles[:, 0], 1 - circles[:, 0]),
                              np.minimum(circles[:, 1], 1 - circles[:, 1])) * 0.2
    
    # Genetic algorithm with tournament selection and uniform crossover
    for iteration in range(40000):
        # Tournament selection
        parents = np.random.choice(n, size=(n//2, 2), replace=False)
        selected = np.array([circles[p[0]] if circles[p[0], 2] > circles[p[1], 2] else circles[p[1]] for p in parents])
        
        # Uniform crossover
        offspring = np.zeros((n, 3))
        for i in range(n):
            if np.random.random() < 0.7:
                parent1, parent2 = selected[np.random.choice(len(selected), 2, replace=False)]
                offspring[i, :2] = (parent1[:2] + parent2[:2]) / 2
                offspring[i, 2] = (parent1[2] + parent2[2]) / 2
            else:
                offspring[i] = selected[np.random.choice(len(selected))]
        
        # Mutation
        for i in range(n):
            if np.random.random() < 0.01:
                offspring[i, :2] += np.random.normal(0, 0.05, 2)
                offspring[i, :2] = np.clip(offspring[i, :2], 0, 1)
                offspring[i, 2] += np.random.normal(0, 0.01)
                offspring[i, 2] = max(0, min(offspring[i, 2], min(offspring[i, 0], 1-offspring[i, 0], offspring[i, 1], 1-offspring[i, 1]))))
        
        # Non-overlap constraint
        for i in range(n):
            for j in range(i+1, n):
                dist = np.sqrt((offspring[i,0]-offspring[j,0])**2 + (offspring[i,1]-offspring[j,1])**2)
                if dist < offspring[i,2] + offspring[j,2]:
                    offspring[i,2] = (dist - offspring[j,2]) / 2
                    offspring[j,2] = (dist - offspring[i,2]) / 2
        
        circles = offspring
    
    return circles
