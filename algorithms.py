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
#  Router
# ──────────────────────────────────────────────────────────────

ALGORITHMS = {
    "A Star":     astar,
    "Dijkstra":   dijkstra,
    "UCS":        ucs,
    "Greedy BFS": greedy_bfs,
}

def find_path(algorithm_name, adjacency, node_coords, source, target):
    fn = ALGORITHMS.get(algorithm_name, astar)
    return fn(adjacency, node_coords, source, target)
