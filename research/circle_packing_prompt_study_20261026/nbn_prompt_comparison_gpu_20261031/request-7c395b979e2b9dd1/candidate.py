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
    
    # Genetic Algorithm with Elitism
    population_size = 50
    generations = 1000
    mutation_rate = 0.01
    
    for generation in range(generations):
        fitness = np.sum(circles[:, 2], axis=1)
        sorted_indices = np.argsort(fitness)[::-1]
        population = circles[sorted_indices][:population_size]
        
        for i in range(population_size):
            if i < population_size // 2:
                parent1 = population[i]
                parent2 = population[np.random.randint(population_size // 2, population_size)]
                child = np.zeros((n, 3))
                child[:n//2, :] = parent1[:n//2, :]
                child[n//2:, :] = parent2[n//2:, :]
                child = mutate(child, mutation_rate)
                circles[i] = child
            else:
                circles[i] = population[np.random.randint(population_size)]
    
    return circles

def mutate(circles: np.ndarray, mutation_rate: float) -> np.ndarray:
    for i in range(circles.shape[0]):
        if np.random.random() < mutation_rate:
            circles[i, 0] = np.clip(circles[i, 0] + np.random.normal(0, 0.05), 0, 1)
            circles[i, 1] = np.clip(circles[i, 1] + np.random.normal(0, 0.05), 0, 1)
            circles[i, 2] = np.clip(circles[i, 2] + np.random.normal(0, 0.05), 0, 1)
    return circles
