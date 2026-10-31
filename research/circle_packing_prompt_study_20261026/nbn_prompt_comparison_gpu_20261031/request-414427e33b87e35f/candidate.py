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
                              np.minimum(circles[:, 1], 1 - circles[:, 1])) * 0.1
    
    # Genetic algorithm with tournament selection and uniform crossover
    population_size = 50
    population = np.zeros((population_size, n, 3))
    for i in range(population_size):
        population[i] = pack_circles(n)
    
    for generation in range(100):
        fitness = np.sum(population[:, :, 2], axis=1)
        parents = np.argsort(fitness)[-2:]
        offspring = np.zeros((population_size, n, 3))
        offspring[:2] = population[parents]
        
        for i in range(2, population_size):
            parent1, parent2 = np.random.choice(parents, 2, replace=False)
            child = np.zeros((n, 3))
            for j in range(n):
                if np.random.rand() < 0.5:
                    child[j] = population[parent1, j]
                else:
                    child[j] = population[parent2, j]
            offspring[i] = child
        
        population = offspring
    
    best_circle = population[np.argmax(np.sum(population[:, :, 2], axis=1))]
    return best_circle
