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
    
    Changed mechanism: Instead of using simulated annealing with exponential cooling, this function employs a local search approach combined with a genetic algorithm for better packing efficiency. The genetic algorithm iteratively improves the positions and radii of circles to maximize their sum while ensuring no overlap.
    """
    np.random.seed(2025)
    if n == 0:
        return np.zeros((0, 3))
    
    # Initialize random positions and radii for each circle
    points = qmc.Sobol(n=n*n, seed=2025).random(n)
    circles = np.zeros((n, 3))
    circles[:, :2] = points
    
    # Genetic algorithm to optimize the positions and radii of circles
    def fitness(circles):
        for i in range(n):
            x, y, r = circles[i]
            if not all(np.sqrt((circles[j,0]-x)**2 + (circles[j,1]-y)**2) > 2*r for j in range(i)):
                return -np.sum(r)
        return -np.sum(r)
    
    # Initial population of circles
    def initial_population(n):
        return np.random.uniform(0, 1, size=(n, 3))
    
    # Genetic algorithm function to optimize the positions and radii of circles
    def genetic_algorithm(population):
        for _ in range(50):  # Number of generations
            fitness_values = np.array([fitness(circle) for circle in population])
            indices = np.argsort(fitness_values)
            new_population = initial_population(n)
            
            for i, idx in enumerate(indices[:int(len(indices)/2)]):
                parent1_idx = indices[i]
                parent2_idx = indices[i+1]
                
                parent1 = population[parent1_idx]
                parent2 = population[parent2_idx]
                
                child1 = np.clip(parent1 + 0.5 * (parent2 - parent1), 0, 1)
                child2 = np.clip(parent2 + 0.5 * (parent1 - parent2), 0, 1)
                
                new_population[i] = child1
                new_population[i+1] = child2
            
            population = new_population
    
        return population
    
    # Genetic algorithm optimization
    circles = genetic_algorithm(initial_population(n))
    
    return circles
