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
    
    circles = np.zeros((n, 3))
    quadtree = {'bounds': [0, 0, 1, 1], 'children': [], 'density': 0}
    
    def split_node(node):
        x0, y0, x1, y1 = node['bounds']
        mid_x, mid_y = (x0 + x1)/2, (y0 + y1)/2
        node['children'] = [
            {'bounds': [x0, y0, mid_x, mid_y], 'children': [], 'density': 0},
            {'bounds': [mid_x, y0, x1, mid_y], 'children': [], 'density': 0},
            {'bounds': [x0, mid_y, mid_x, y1], 'children': [], 'density': 0},
            {'bounds': [mid_x, mid_y, x1, y1], 'children': [], 'density': 0}
        ]
    
    def update_density(node, point):
        x, y = point
        x0, y0, x1, y1 = node['bounds']
        if not (x0 <= x <= x1 and y0 <= y <= y1):
            return
        
        if node['children']:
            for child in node['children']:
                update_density(child, point)
        else:
            node['density'] += 1
            if node['density'] > 2 and (x1 - x0) > 0.05:
                split_node(node)
    
    for i in range(n):
        candidates = []
        
        def sample_from_node(node):
            if node['children']:
                for child in node['children']:
                    sample_from_node(child)
            else:
                x0, y0, x1, y1 = node['bounds']
                samples = min(3, 1 + node['density'])
                for _ in range(samples):
                    candidates.append([
                        np.random.uniform(x0, x1),
                        np.random.uniform(y0, y1)
                    ])
        
        sample_from_node(quadtree)
        candidates.extend([[0,0], [0,1], [1,0], [1,1]])
        
        best_pos = [0.5, 0.5]
        best_r = 0
        
        for candidate in candidates:
            min_dist = min(
                candidate[0], candidate[1],
                1 - candidate[0], 1 - candidate[1]
            )
            
            if i > 0:
                dists = np.sqrt(
                    (circles[:i, 0] - candidate[0])**2 +
                    (circles[:i, 1] - candidate[1])**2
                ) - circles[:i, 2]
                min_dist = min(min_dist, dists.min())
            
            if min_dist > best_r:
                best_r = min_dist
                best_pos = candidate
        
        circles[i] = [best_pos[0], best_pos[1], best_r * 0.95]
        update_density(quadtree, best_pos)
    
    return circles
