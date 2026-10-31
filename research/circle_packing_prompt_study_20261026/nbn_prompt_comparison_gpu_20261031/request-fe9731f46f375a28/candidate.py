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
    import numpy as np
    from scipy.stats import qmc
    
    np.random.seed(2025)
    if n == 0:
        return np.zeros((0, 3))
    
    # Latin Hypercube Sampling initialization
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
    
    def fitness(circle):
        return np.sum(circle[:, 2])
    
    def crossover(parent1, parent2):
        child = np.copy(parent1)
        for i in range(n):
            if np.random.random() < 0.5:
                child[i] = parent2[i]
        return child
    
    def mutate(circle):
        for i in range(n):
            if np.random.random() < mutation_rate:
                x, y, r = circle[i]
                max_r = min(x, 1-x, y, 1-y)
                for j in range(n):
                    if i == j:
                        continue
                    dist = np.sqrt((circle[j,0]-x)**2 + (circle[j,1]-y)**2)
                    max_r = min(max_r, dist - circle[j,2])
                new_r = np.clip(np.random.normal(r, 0.05 * r), 0, max_r)
                circle[i, 2] = new_r
        return circle
    
    population = [circles.copy() for _ in range(population_size)]
    
    for generation in range(generations):
        population = sorted(population, key=fitness, reverse=True)
        new_population = population[:int(population_size * 0.2)]
        
        while len(new_population) < population_size:
            parent1, parent2 = np.random.choice(population, 2, replace=False)
            child = crossover(parent1, parent2)
            child = mutate(child)
            new_population.append(child)
        
        population = new_population
    
    return population[0]
