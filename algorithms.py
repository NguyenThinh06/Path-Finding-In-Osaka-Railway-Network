"""
algorithms.py
─────────────
All pathfinding algorithms implemented from scratch.
No nx.shortest_path / nx.astar_path / any built-in pathfinder.

Each function has the same signature:
    fn(adjacency, node_coords, source, target) -> (path, cost, nodes_expanded)

Where:
    adjacency    : { node_id: [(neighbour_id, weight_m), ...] }
    node_coords  : { node_id: (lat, lon) }
    source/target: node ids
    path         : list of node ids source → target
    cost         : total edge weight (metres)
    nodes_expanded: int  (how many nodes were popped from the queue)
"""

import math
import heapq
from collections import deque


# ──────────────────────────────────────────────────────────────
#  Shared helpers
# ──────────────────────────────────────────────────────────────

def haversine(lat1, lon1, lat2, lon2) -> float:
    """Great-circle distance in metres."""
    R = 6_371_000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi    = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = (math.sin(dphi / 2) ** 2
         + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))






def _reconstruct(came_from, node):
    path = [node]
    while node in came_from:
        node = came_from[node]
        path.append(node)
    path.reverse()
    return path


def _path_cost(path, adjacency):
    """Sum of edge weights along a node-list path."""
    total = 0.0
    adj_dict = {u: dict(nbrs) for u, nbrs in adjacency.items()}
    for i in range(len(path) - 1):
        u, v = path[i], path[i + 1]
        total += adj_dict.get(u, {}).get(v, 0.0)
    return total


def _shortest_path_between(adjacency, node_coords, source, target):
    """Compute shortest path and cost between two nodes using A*."""
    try:
        path, cost, _ = astar(adjacency, node_coords, source, target)
        return path, cost
    except ValueError:
        return None, math.inf


def _build_distance_matrix(adjacency, node_coords, important_nodes):
    """
    Build a distance matrix between important nodes (gates).
    Returns: { (node_i, node_j): (cost, path) }
    """
    dist_matrix = {}
    for i, node_a in enumerate(important_nodes):
        for j, node_b in enumerate(important_nodes):
            if i != j:
                path, cost = _shortest_path_between(adjacency, node_coords, node_a, node_b)
                dist_matrix[(node_a, node_b)] = (cost, path)
    return dist_matrix



def astar(adjacency, node_coords, source, target):
    def h(n):
        lat1, lon1 = node_coords[n]
        lat2, lon2 = node_coords[target]
        return haversine(lat1, lon1, lat2, lon2)

    g = {source: 0.0}
    came_from = {}
    closed = set()
    heap = [(h(source), source)]
    expanded = 0

    while heap:
        f_cur, cur = heapq.heappop(heap)
        if cur in closed:
            continue
        closed.add(cur)
        expanded += 1

        if cur == target:
            path = _reconstruct(came_from, cur)
            return path, g[target], expanded

        for nb, w in adjacency.get(cur, []):
            if nb in closed:
                continue
            tg = g[cur] + w
            if tg < g.get(nb, math.inf):
                g[nb] = tg
                came_from[nb] = cur
                heapq.heappush(heap, (tg + h(nb), nb))

    raise ValueError("No path found")


def dijkstra(adjacency, node_coords, source, target):
    g = {source: 0.0}
    came_from = {}
    closed = set()
    heap = [(0.0, source)]
    expanded = 0

    while heap:
        g_cur, cur = heapq.heappop(heap)
        if cur in closed:
            continue
        closed.add(cur)
        expanded += 1

        if cur == target:
            path = _reconstruct(came_from, cur)
            return path, g[target], expanded

        for nb, w in adjacency.get(cur, []):
            if nb in closed:
                continue
            tg = g[cur] + w
            if tg < g.get(nb, math.inf):
                g[nb] = tg
                came_from[nb] = cur
                heapq.heappush(heap, (tg, nb))

    raise ValueError("No path found")






def ucs(adjacency, node_coords, source, target):
    """
    Uniform Cost Search — expands the node with lowest path cost so far.
    Equivalent to Dijkstra; kept separate for clarity.
    """
    frontier = [(0.0, source)]   # (cost, node)
    cost_so_far = {source: 0.0}
    came_from = {}
    expanded = 0

    while frontier:
        cost, cur = heapq.heappop(frontier)
        expanded += 1

        if cur == target:
            path = _reconstruct(came_from, cur)
            return path, cost_so_far[target], expanded

        if cost > cost_so_far.get(cur, math.inf):
            continue  # stale entry

        for nb, w in adjacency.get(cur, []):
            new_cost = cost_so_far[cur] + w
            if new_cost < cost_so_far.get(nb, math.inf):
                cost_so_far[nb] = new_cost
                came_from[nb] = cur
                heapq.heappush(frontier, (new_cost, nb))

    raise ValueError("No path found")





def greedy_bfs(adjacency, node_coords, source, target):
    def h(n):
        lat1, lon1 = node_coords[n]
        lat2, lon2 = node_coords[target]
        return haversine(lat1, lon1, lat2, lon2)

    came_from = {}
    visited = set()
    heap = [(h(source), source)]
    expanded = 0

    while heap:
        _, cur = heapq.heappop(heap)
        if cur in visited:
            continue
        visited.add(cur)
        expanded += 1

        if cur == target:
            path = _reconstruct(came_from, cur)
            cost = _path_cost(path, adjacency)
            return path, cost, expanded

        for nb, w in adjacency.get(cur, []):
            if nb not in visited:
                came_from[nb] = cur
                heapq.heappush(heap, (h(nb), nb))

    raise ValueError("No path found")


# ──────────────────────────────────────────────────────────────
#  TSP Algorithms (Travelling Salesman Problem)
# ──────────────────────────────────────────────────────────────

def _tsp_brute_force(dist_matrix, nodes):
    """
    Brute force TSP: try all permutations and find minimum cost cycle.
    nodes: list of nodes to visit (excluding start which is nodes[0])
    Returns: (best_tour, total_cost) where tour is ordered list of nodes
    """
    from itertools import permutations
    
    if len(nodes) <= 1:
        return nodes, 0.0
    
    start = nodes[0]
    remaining = nodes[1:]
    
    best_cost = math.inf
    best_tour = None
    
    for perm in permutations(remaining):
        tour = [start] + list(perm)
        cost = 0.0
        for i in range(len(tour)):
            u, v = tour[i], tour[(i + 1) % len(tour)]
            edge_cost = dist_matrix.get((u, v), (math.inf, None))[0]
            cost += edge_cost
        
        if cost < best_cost:
            best_cost = cost
            best_tour = tour
    
    return best_tour, best_cost


def _tsp_greedy(dist_matrix, nodes):
    """
    Greedy TSP: nearest neighbor heuristic.
    Start from first node, always go to nearest unvisited node.
    Returns: (tour, total_cost)
    """
    if len(nodes) <= 1:
        return nodes, 0.0
    
    current = nodes[0]
    unvisited = set(nodes[1:])
    tour = [current]
    total_cost = 0.0
    
    while unvisited:
        nearest = min(unvisited, 
                     key=lambda n: dist_matrix.get((current, n), (math.inf, None))[0])
        edge_cost = dist_matrix.get((current, nearest), (math.inf, None))[0]
        total_cost += edge_cost
        tour.append(nearest)
        unvisited.remove(nearest)
        current = nearest
    
    # Return to start
    edge_cost = dist_matrix.get((current, nodes[0]), (math.inf, None))[0]
    total_cost += edge_cost
    
    return tour, total_cost


def _tsp_branch_and_bound(dist_matrix, nodes):
    """
    Branch and bound TSP: more efficient than brute force.
    Prunes branches that exceed current best cost.
    Returns: (tour, total_cost)
    """
    if len(nodes) <= 1:
        return nodes, 0.0
    
    start = nodes[0]
    remaining = nodes[1:]
    
    best_cost = [math.inf]
    best_tour = [None]
    
    def lower_bound(current_path, unvisited):
        """Estimate minimum cost to complete tour from here."""
        cost = 0.0
        last = current_path[-1]
        
        if unvisited:
            # Cost to nearest in unvisited
            nearest_cost = min(dist_matrix.get((last, u), (math.inf, None))[0] 
                             for u in unvisited)
            cost += nearest_cost
            
            # Rough estimate: min edge between unvisited nodes
            if len(unvisited) > 1:
                min_edges = sorted([dist_matrix.get((u, v), (math.inf, None))[0]
                                   for u in unvisited for v in unvisited if u != v])
                cost += sum(min_edges[:len(unvisited)-1]) / 2
        else:
            # Return to start
            cost += dist_matrix.get((last, start), (math.inf, None))[0]
        
        return cost
    
    def branch_and_bound_helper(current_path, unvisited, current_cost):
        if current_cost >= best_cost[0]:
            return  # Prune
        
        if not unvisited:
            # Complete tour
            final_cost = current_cost + dist_matrix.get((current_path[-1], start), (math.inf, None))[0]
            if final_cost < best_cost[0]:
                best_cost[0] = final_cost
                best_tour[0] = current_path + [start]
            return
        
        for node in unvisited:
            edge_cost = dist_matrix.get((current_path[-1], node), (math.inf, None))[0]
            new_cost = current_cost + edge_cost
            
            # Estimate lower bound
            estimated = new_cost + lower_bound(current_path + [node], unvisited - {node})
            
            if estimated < best_cost[0]:
                branch_and_bound_helper(
                    current_path + [node],
                    unvisited - {node},
                    new_cost
                )
    
    branch_and_bound_helper([start], set(remaining), 0.0)
    
    if best_tour[0] is None:
        # Fallback to greedy
        return _tsp_greedy(dist_matrix, nodes)
    
    return best_tour[0], best_cost[0]


# ──────────────────────────────────────────────────────────────
#  Waypoint-constrained pathfinding
# ──────────────────────────────────────────────────────────────

def find_path_via_waypoints(adjacency, node_coords, source, target, 
                            mandatory_waypoints, tsp_method="greedy"):
    """
    Find shortest path from source to target passing through mandatory waypoints.
    
    Args:
        adjacency: { node_id: [(neighbour_id, weight_m), ...] }
        node_coords: { node_id: (lat, lon) }
        source: start node
        target: end node
        mandatory_waypoints: set/list of node ids that must be visited
        tsp_method: "brute_force", "greedy", or "branch_and_bound"
    
    Returns:
        (full_path, total_cost, nodes_expanded_info)
        where full_path is list of node ids visiting all waypoints in optimal order
    """
    
    # Validate inputs
    if not mandatory_waypoints:
        return astar(adjacency, node_coords, source, target)
    
    # Build list of important nodes: source + target + waypoints
    important_nodes = [source] + list(mandatory_waypoints) + [target]
    important_nodes = list(dict.fromkeys(important_nodes))  # Remove duplicates, preserve order
    
    # Step 1: Compute distance matrix between all important nodes
    dist_matrix = _build_distance_matrix(adjacency, node_coords, important_nodes)
    
    # Check for unreachable nodes
    for (u, v), (cost, _) in dist_matrix.items():
        if cost == math.inf:
            raise ValueError(f"No path exists between {u} and {v}")
    
    # Step 2: Create virtual node D for TSP conversion
    # D is dummy node: B → D (cost 0), D → A (cost 0)
    # This converts path-finding to cycle-finding
    nodes_for_tsp = [source] + list(mandatory_waypoints) + [target]
    
    # Add dummy node for cycle closure
    dummy = "DUMMY_END_NODE"
    
    # Extend distance matrix with dummy node edges
    dist_matrix[(target, dummy)] = (0.0, [])      # B → D (cost 0)
    dist_matrix[(dummy, source)] = (0.0, [])      # D → A (cost 0)
    
    nodes_with_dummy = nodes_for_tsp + [dummy]
    
    # Step 3: Solve TSP
    if tsp_method == "brute_force":
        tsp_tour, tsp_cost = _tsp_brute_force(dist_matrix, nodes_with_dummy)
    elif tsp_method == "branch_and_bound":
        tsp_tour, tsp_cost = _tsp_branch_and_bound(dist_matrix, nodes_with_dummy)
    else:  # greedy (default)
        tsp_tour, tsp_cost = _tsp_greedy(dist_matrix, nodes_with_dummy)
    
    # Step 4: Extract path from TSP tour (remove dummy node D)
    # Find where dummy is and extract source → ... → target path
    dummy_idx = tsp_tour.index(dummy)
    
    # Reorder to start from source, end at target
    path_nodes = tsp_tour[dummy_idx+1:] + tsp_tour[:dummy_idx]
    
    # Remove the dummy node
    path_nodes = [n for n in path_nodes if n != dummy]
    
    # Step 5: Reconstruct full path with actual edges
    full_path = [path_nodes[0]]
    total_cost = 0.0
    
    for i in range(len(path_nodes) - 1):
        u, v = path_nodes[i], path_nodes[i + 1]
        _, segment_path = dist_matrix.get((u, v), (math.inf, None))
        
        if segment_path:
            # Skip first node to avoid duplication
            full_path.extend(segment_path[1:])
            segment_cost = dist_matrix[(u, v)][0]
            total_cost += segment_cost
    
    return full_path, total_cost, len(full_path)


# ──────────────────────────────────────────────────────────────
#  Router
# ──────────────────────────────────────────────────────────────

ALGORITHMS = {
    "A Star":     astar,
    "Dijkstra":   dijkstra,
    "UCS":        ucs,
    "Greedy BFS": greedy_bfs,
}

TSP_ALGORITHMS = {
    "greedy": _tsp_greedy,
    "brute_force": _tsp_brute_force,
    "branch_and_bound": _tsp_branch_and_bound,
}

def find_path(algorithm_name, adjacency, node_coords, source, target):
    fn = ALGORITHMS.get(algorithm_name, astar)
    return fn(adjacency, node_coords, source, target)
