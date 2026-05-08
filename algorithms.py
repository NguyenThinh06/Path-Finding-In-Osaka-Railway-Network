"""
algorithms.py
─────────────
Các thuật toán tìm đường và TSP cốt lõi được cài đặt từ đầu (from scratch).
Đã được tối ưu hóa cho hệ thống định tuyến của Mạng lưới Đường sắt Osaka.
"""

import math
import heapq
from itertools import permutations

# ──────────────────────────────────────────────────────────────
#  1. CÁC HÀM HỖ TRỢ (HELPER FUNCTIONS)
# ──────────────────────────────────────────────────────────────

def haversine(lat1, lon1, lat2, lon2) -> float:
    """Tính khoảng cách đường chim bay (Great-circle distance) giữa hai điểm trên Trái Đất (đơn vị: mét)."""
    R = 6_371_000  # Bán kính Trái Đất tính bằng mét
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    
    a = (math.sin(dphi / 2) ** 2 + 
         math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

def _reconstruct_path(came_from, current):
    """Truy vết ngược qua từ điển came_from để tái tạo lại đường đi."""
    path = [current]
    while current in came_from:
        current = came_from[current]
        path.append(current)
    path.reverse()
    return path

# ──────────────────────────────────────────────────────────────
#  2. TÌM ĐƯỜNG CỐT LÕI (A*, Dijkstra, UCS, Greedy BFS)
# ──────────────────────────────────────────────────────────────

def astar(adjacency, node_coords, source, target, use_heuristic=True, greedy_only=False):
    """
    Hàm tìm kiếm tổng quát xử lý chung cho cả A*, Dijkstra, UCS, và Greedy BFS.
    - A*: use_heuristic=True, greedy_only=False
    - Dijkstra / UCS: use_heuristic=False, greedy_only=False
    - Greedy BFS: use_heuristic=True, greedy_only=True
    """
    def h(n):
        if not use_heuristic:
            return 0.0
        lat1, lon1 = node_coords[n]
        lat2, lon2 = node_coords[target]
        return haversine(lat1, lon1, lat2, lon2)

    g_score = {source: 0.0}
    came_from = {}
    
    # Các phần tử trong Hàng đợi ưu tiên (Priority Queue): (priority_cost, node)
    # Nếu là Greedy, độ ưu tiên chỉ là h(n). Ngược lại, nó là g(n) + h(n).
    initial_priority = h(source) if use_heuristic else 0.0
    heap = [(initial_priority, source)]
    expanded_nodes = 0

    while heap:
        current_priority, current_node = heapq.heappop(heap)
        
        # Tối ưu hóa: Bỏ qua các phần tử cũ/lỗi thời trong hàng đợi
        actual_cost = g_score.get(current_node, math.inf)
        if not greedy_only and current_priority > actual_cost + h(current_node):
            continue

        expanded_nodes += 1

        if current_node == target:
            path = _reconstruct_path(came_from, current_node)
            return path, g_score[target], expanded_nodes

        for neighbor, weight in adjacency.get(current_node, []):
            tentative_g = actual_cost + weight
            
            if tentative_g < g_score.get(neighbor, math.inf):
                g_score[neighbor] = tentative_g
                came_from[neighbor] = current_node
                
                # Xác định độ ưu tiên dựa trên loại thuật toán
                if greedy_only:
                    priority = h(neighbor)
                else:
                    priority = tentative_g + h(neighbor)
                    
                heapq.heappush(heap, (priority, neighbor))

    raise ValueError(f"Không tìm thấy đường đi giữa {source} và {target}")

# Các hàm bọc (Wrappers) để giữ đúng định dạng (signature) hàm ban đầu
def dijkstra(adjacency, node_coords, source, target):
    return astar(adjacency, node_coords, source, target, use_heuristic=False)

def ucs(adjacency, node_coords, source, target):
    # UCS về mặt toán học hoàn toàn giống với Dijkstra trong ngữ cảnh đồ thị này
    return dijkstra(adjacency, node_coords, source, target)

def greedy_bfs(adjacency, node_coords, source, target):
    return astar(adjacency, node_coords, source, target, use_heuristic=True, greedy_only=True)

# ──────────────────────────────────────────────────────────────
#  3. THUẬT TOÁN TSP & MA TRẬN KHOẢNG CÁCH
# ──────────────────────────────────────────────────────────────

def _build_distance_matrix(adjacency, node_coords, important_nodes):
    """Xây dựng đồ thị liên thông hoàn toàn chứa khoảng cách ngắn nhất giữa tất cả các điểm quan trọng."""
    dist_matrix = {}
    for node_a in important_nodes:
        for node_b in important_nodes:
            if node_a == node_b:
                continue
            try:
                # Sử dụng A* làm thuật toán mặc định nhanh nhất để xây dựng ma trận
                path, cost, _ = astar(adjacency, node_coords, node_a, node_b)
                dist_matrix[(node_a, node_b)] = (cost, path)
            except ValueError:
                dist_matrix[(node_a, node_b)] = (math.inf, None)
    return dist_matrix

def _tsp_brute_force(dist_matrix, nodes):
    """Thử tất cả các hoán vị. Chỉ phù hợp khi số lượng điểm trung gian nhỏ."""
    start_node = nodes[0]
    waypoints = nodes[1:]
    
    best_tour, best_cost = None, math.inf
    
    for perm in permutations(waypoints):
        tour = [start_node] + list(perm)
        # Tính toán chi phí chu trình trong 1 dòng Pythonic duy nhất
        cost = sum(dist_matrix.get((tour[i], tour[(i + 1) % len(tour)]), (math.inf, None))[0] 
                   for i in range(len(tour)))
        
        if cost < best_cost:
            best_cost = cost
            best_tour = tour
            
    return best_tour, best_cost

def _tsp_greedy(dist_matrix, nodes):
    """Heuristic Láng giềng gần nhất (Nearest Neighbor). Nhanh nhưng không đảm bảo tối ưu 100%."""
    current = nodes[0]
    unvisited = set(nodes[1:])
    tour = [current]
    total_cost = 0.0
    
    while unvisited:
        nearest = min(unvisited, key=lambda n: dist_matrix.get((current, n), (math.inf, None))[0])
        total_cost += dist_matrix[(current, nearest)][0]
        tour.append(nearest)
        unvisited.remove(nearest)
        current = nearest
        
    # Quay trở lại điểm xuất phát để khép kín chu trình
    total_cost += dist_matrix.get((current, nodes[0]), (math.inf, None))[0]
    return tour, total_cost

# ──────────────────────────────────────────────────────────────
#  4. HỆ THỐNG ĐỊNH TUYẾN CHÍNH (Xử lý Waypoint & Trạm ảo)
# ──────────────────────────────────────────────────────────────

def find_path_via_waypoints(adjacency, node_coords, source, target, mandatory_waypoints, tsp_method="greedy"):
    """
    Tìm lộ trình tối ưu đi qua tất cả các điểm trung gian bắt buộc bằng kỹ thuật Trạm Ảo (Dummy Node).
    """
    if not mandatory_waypoints:
        return astar(adjacency, node_coords, source, target)
    
    # 1. Loại bỏ các điểm trùng lặp nhưng vẫn giữ nguyên thứ tự (Deduplicate)
    important_nodes = list(dict.fromkeys([source] + list(mandatory_waypoints) + [target]))
    
    # 2. Xây dựng Ma trận Khoảng cách
    dist_matrix = _build_distance_matrix(adjacency, node_coords, important_nodes)
    for (u, v), (cost, _) in dist_matrix.items():
        if cost == math.inf:
            raise ValueError(f"Đồ thị bị ngắt kết nối. Không có đường đi giữa {u} và {v}")
            
    # 3. Tiêm Trạm Ảo (Dummy Node) để biến bài toán Tìm đường thẳng thành bài toán Chu trình (TSP)
    DUMMY = "DUMMY_END_NODE"
    dist_matrix[(target, DUMMY)] = (0.0, [])  # Chi phí từ Đích đến Trạm ảo = 0
    dist_matrix[(DUMMY, source)] = (0.0, [])  # Chi phí từ Trạm ảo quay về Xuất phát = 0
    
    nodes_for_tsp = important_nodes + [DUMMY]
    
    # 4. Giải bài toán TSP
    if tsp_method == "brute_force":
        tsp_tour, _ = _tsp_brute_force(dist_matrix, nodes_for_tsp)
    else:
        tsp_tour, _ = _tsp_greedy(dist_matrix, nodes_for_tsp)
        
    # 5. Trích xuất đường thẳng bằng cách cắt bỏ Trạm ảo DUMMY khỏi chu trình
    dummy_idx = tsp_tour.index(DUMMY)
    ordered_nodes = tsp_tour[dummy_idx + 1:] + tsp_tour[:dummy_idx]
    
    # 6. Tái tạo lại lộ trình vật lý cuối cùng
    full_path = [ordered_nodes[0]]
    total_cost = 0.0
    
    for i in range(len(ordered_nodes) - 1):
        u, v = ordered_nodes[i], ordered_nodes[i + 1]
        cost, segment_path = dist_matrix[(u, v)]
        
        # Mở rộng đường đi (bỏ qua điểm đầu tiên của mỗi đoạn để tránh trùng lặp điểm nối)
        full_path.extend(segment_path[1:])
        total_cost += cost
        
    return full_path, total_cost, len(full_path)

# ──────────────────────────────────────────────────────────────
#  XUẤT CÁC HÀM ĐỊNH TUYẾN (ROUTER EXPORTS)
# ──────────────────────────────────────────────────────────────

ALGORITHMS = {
    "A Star": astar,
    "Dijkstra": dijkstra,
    "UCS": ucs,
    "Greedy BFS": greedy_bfs,
}

def find_path(algorithm_name, adjacency, node_coords, source, target):
    fn = ALGORITHMS.get(algorithm_name, astar)
    return fn(adjacency, node_coords, source, target)