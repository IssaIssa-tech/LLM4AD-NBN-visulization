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
    from scipy.spatial import Voronoi
    from scipy.spatial.distance import cdist
    
    np.random.seed(2025)
    if n == 0:
        return np.zeros((0, 3))
    
    # Initialize with random points and small radii
    points = np.random.rand(n, 2)
    radii = np.full(n, 0.01)
    
    for iteration in range(100):
        # Create periodic Voronoi diagram by mirroring points
        mirrored = np.vstack([
            points,
            points + [1, 0],
            points - [1, 0],
            points + [0, 1],
            points - [0, 1],
            points + [1, 1],
            points + [1, -1],
            points + [-1, 1],
            points + [-1, -1]
        ])
        
        vor = Voronoi(mirrored)
        
        # Move points to centroids of their Voronoi cells
        new_points = np.zeros_like(points)
        for i in range(n):
            region = vor.regions[vor.point_region[i]]
            if -1 in region or len(region) == 0:
                continue
            
            vertices = vor.vertices[region]
            centroid = vertices.mean(axis=0)
            new_points[i] = np.clip(centroid, 0, 1)
        
        points = new_points
        
        # Expand radii based on nearest neighbor distances
        dist_matrix = cdist(points, points) + np.diag(np.full(n, np.inf))
        min_dists = dist_matrix.min(axis=1)
        radii = np.minimum(min_dists / 2, np.minimum(np.minimum(points[:, 0], 1 - points[:, 0]), 
                                                   np.minimum(points[:, 1], 1 - points[:, 1])))
    
    # Combine results
    circles = np.column_stack((points, radii))
    return circles
