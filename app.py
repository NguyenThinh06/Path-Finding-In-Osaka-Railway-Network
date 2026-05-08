import math, os, pickle, time
from collections import defaultdict
import numpy as np
from scipy.spatial import KDTree

import osmnx as ox
from flask import Flask, jsonify, render_template, request
from algorithms import find_path, haversine

app = Flask(__name__)

CACHE_FILE = "osaka_railway_full.pkl"
RAILWAY_FILTER = (
    '["railway"~"subway|rail|tram|light_rail|monorail|'
    'narrow_gauge|miniature|funicular|cable_car"]'
)
SUBWAY_SPEED_KMH = 35.0  # average subway/rail speed for time estimation

def _download_graph():
    print("Downloading Osaka railway network…")
    G = ox.graph_from_place(
        "Osaka, Japan",
        custom_filter=RAILWAY_FILTER,
        retain_all=True,
        simplify=False,
    )
    print(f"Nodes: {G.number_of_nodes():,} | Edges: {G.number_of_edges():,}")

    print("Fetching station names from OSM…")
    station_tags = {
        "railway": ["station", "halt", "tram_stop", "subway_entrance", "stop"],
        "public_transport": ["station", "stop_position"],
    }
    try:
        features = ox.features_from_place("Osaka, Japan", tags=station_tags)
        name_points = []
        for _, row in features.iterrows():
            best = (
                str(row.get("name:en") or "").strip()
                or str(row.get("name:ja-Latn") or "").strip()
                or str(row.get("name:ja") or "").strip()
                or str(row.get("name") or "").strip()
            )
            if not best or best == "nan":
                continue
            geom = row.get("geometry")
            if geom is None:
                continue
            pt = geom.centroid
            name_points.append((pt.y, pt.x, best))
        print(f"  Named OSM features: {len(name_points)}")
    except Exception as e:
        print(f"  Warning: could not fetch station features: {e}")
        name_points = []
    return G, name_points

def _build_state(G, name_points):
    node_coords = {}
    adjacency = {}
    station_nodes = {}

    # ── Pass 1: coordinates + station detection by OSM node tags ─────────────
    raw_stations = []
    for nid, data in G.nodes(data=True):
        node_coords[nid] = (float(data["y"]), float(data["x"]))
        adjacency[nid] = {}
        railway = data.get("railway", "")
        pt      = data.get("public_transport", "")
        is_station = (
            railway in ["station", "halt", "tram_stop", "subway_entrance",
                        "railway_station", "stop"]
            or pt in ["station", "stop_position", "stop_area"]
            or data.get("amenity") == "bus_station"
        )
        if is_station:
            raw_stations.append(nid)

    # ── Pass 2: name lookup via nearest OSM feature ───────────────────────────
    if name_points and raw_stations:
        feat_coords = np.array([(lat, lon) for lat, lon, _ in name_points])
        feat_names  = [name for _, _, name in name_points]
        feat_tree   = KDTree(feat_coords)
        MAX_DIST_DEG = 300 / 111_000

        for nid in raw_stations:
            lat, lon = node_coords[nid]
            dist, idx = feat_tree.query([lat, lon])
            if dist <= MAX_DIST_DEG:
                station_nodes[nid] = feat_names[idx]
    else:
        for nid in raw_stations:
            station_nodes[nid] = f"Stop {nid}"

    # ── Pass 3: build adjacency from edges ────────────────────────────────────
    drawn = set()
    railway_geoms = []
    railway_edges = set()

    for u, v, data in G.edges(data=True):
        w = data.get("length")
        if w is None:
            lat1, lon1 = node_coords[u]
            lat2, lon2 = node_coords[v]
            w = haversine(lat1, lon1, lat2, lon2)
        w = float(w)

        # Make graph undirected in adjacency (take min weight)
        if v not in adjacency[u] or w < adjacency[u][v]:
            adjacency[u][v] = w
        if u not in adjacency[v] or w < adjacency[v][u]:
            adjacency[v][u] = w

        pair = (min(u, v), max(u, v))
        railway_edges.add(pair)

        if pair not in drawn:
            drawn.add(pair)
            geom = data.get("geometry")
            if geom:
                coords = [[y, x] for x, y in geom.coords]
            else:
                coords = [[node_coords[u][0], node_coords[u][1]],
                          [node_coords[v][0], node_coords[v][1]]]
            railway_geoms.append(coords)

    # ── Pass 4: walking edges between nearby stations ─────────────────────────
    walking_drawn = set()
    walking_geoms = []
    walking_edges = set()

    sta_list = list(station_nodes.keys())
    for i, sta1 in enumerate(sta_list):
        lat1, lon1 = node_coords[sta1]
        for sta2 in sta_list[i+1:]:
            lat2, lon2 = node_coords[sta2]
            dist = haversine(lat1, lon1, lat2, lon2)
            if dist < 300:
                weight = dist + 500
                if sta2 not in adjacency[sta1] or weight < adjacency[sta1][sta2]:
                    adjacency[sta1][sta2] = weight
                if sta1 not in adjacency[sta2] or weight < adjacency[sta2][sta1]:
                    adjacency[sta2][sta1] = weight
                pair = (min(sta1, sta2), max(sta1, sta2))
                walking_edges.add(pair)
                if pair not in walking_drawn:
                    walking_drawn.add(pair)
                    walking_geoms.append([[lat1, lon1], [lat2, lon2]])

    print(f"Stations: {len(station_nodes):,} | Railway edges: {len(railway_geoms):,} | Walking: {len(walking_geoms):,}")
    return node_coords, adjacency, railway_geoms, walking_geoms, station_nodes, railway_edges, walking_edges

def load_state():
    if os.path.exists(CACHE_FILE):
        print("Loading cached graph…")
        with open(CACHE_FILE, "rb") as f:
            return pickle.load(f)
    G, name_points = _download_graph()
    state = _build_state(G, name_points)
    with open(CACHE_FILE, "wb") as f:
        pickle.dump(state, f)
    print("Graph cached")
    return state

NODE_COORDS, ADJACENCY, RAILWAY_EDGES, WALKING_EDGES, STATION_NODES, RAILWAY_EDGE_SET, WALKING_EDGE_SET = load_state()

# Store original adjacency for full reset
import copy
_ORIGINAL_ADJACENCY = copy.deepcopy(ADJACENCY)

TRAFFIC_JAMS = []

def _public_jams():
    return [{"start": j["start"], "end": j["end"], "label": j.get("label", ""),
             "coords": j.get("coords", [])} for j in TRAFFIC_JAMS]

_station_ids = list(STATION_NODES.keys())
if _station_ids:
    _station_array = np.array([(NODE_COORDS[nid][0], NODE_COORDS[nid][1]) for nid in _station_ids])
    _station_kdtree = KDTree(_station_array)
else:
    _station_kdtree = None

def nearest_node(lat, lon):
    if _station_kdtree:
        _, idx = _station_kdtree.query([lat, lon])
        return _station_ids[idx]
    return None

def adj_as_lists():
    return {u: list(nbrs.items()) for u, nbrs in ADJACENCY.items()}

def serialise_nodes():
    return [[NODE_COORDS[nid][0], NODE_COORDS[nid][1]] for nid in STATION_NODES]

def serialise_station_labels():
    return [{"lat": NODE_COORDS[nid][0], "lon": NODE_COORDS[nid][1], "name": name}
            for nid, name in STATION_NODES.items()]

def serialise_edges():
    return {"railway": RAILWAY_EDGES, "walking": WALKING_EDGES}

def rebuild_kdtree():
    global _station_ids, _station_array, _station_kdtree
    _station_ids = list(STATION_NODES.keys())
    if _station_ids:
        _station_array = np.array([(NODE_COORDS[nid][0], NODE_COORDS[nid][1]) for nid in _station_ids])
        _station_kdtree = KDTree(_station_array)

def path_segments(path):
    """Split a path into railway and walking coordinate segments."""
    railway_segs, walking_segs = [], []
    for i in range(len(path) - 1):
        u, v = path[i], path[i + 1]
        seg = [[NODE_COORDS[u][0], NODE_COORDS[u][1]],
               [NODE_COORDS[v][0], NODE_COORDS[v][1]]]
        if (min(u, v), max(u, v)) in WALKING_EDGE_SET:
            walking_segs.append(seg)
        else:
            railway_segs.append(seg)
    return railway_segs, walking_segs

@app.route("/")
def index():
    edges = serialise_edges()
    return render_template("map.html",
        node_coords=serialise_nodes(),
        railway_coords=edges["railway"],
        walking_coords=edges["walking"],
        station_labels=serialise_station_labels(),
        traffic_jams=_public_jams())

@app.route("/stations")
def stations():
    return jsonify([{"name": name, "lat": NODE_COORDS[nid][0], "lon": NODE_COORDS[nid][1]}
                    for nid, name in sorted(STATION_NODES.items(), key=lambda x: x[1])])

@app.route("/find_shortest_path", methods=["POST"])
def find_shortest_path():
    data = request.get_json()
    src = nearest_node(*data["start"])
    tgt = nearest_node(*data["end"])

    if src == tgt:
        return jsonify({"error": "Same start/end point"}), 400

    try:
        t0 = time.perf_counter()
        path, cost, expanded = find_path(data.get("algorithm", "A Star"),
                                         adj_as_lists(), NODE_COORDS, src, tgt)
        elapsed = (time.perf_counter() - t0) * 1000
    except ValueError as e:
        return jsonify({"error": str(e)}), 404

    path_coords = [[NODE_COORDS[n][0], NODE_COORDS[n][1]] for n in path]
    railway_segs, walking_segs = path_segments(path)
    waypoints = [{"name": STATION_NODES[n], "lat": NODE_COORDS[n][0], "lon": NODE_COORDS[n][1]}
                 for n in path if n in STATION_NODES]
    cost_km = round(cost / 1000, 3)
    travel_min = round(cost_km / SUBWAY_SPEED_KMH * 60, 1)

    return jsonify({
        "path_coords": path_coords,
        "railway_segments": railway_segs,
        "walking_segments": walking_segs,
        "start_path": [data["start"], [NODE_COORDS[src][0], NODE_COORDS[src][1]]],
        "end_path":   [data["end"],   [NODE_COORDS[tgt][0], NODE_COORDS[tgt][1]]],
        "cost_km": cost_km,
        "travel_min": travel_min,
        "nodes_in_path": len(path),
        "nodes_expanded": expanded,
        "elapsed_ms": round(elapsed, 1),
        "algorithm": data.get("algorithm", "A Star"),
        "waypoints": waypoints,
    })

@app.route("/compare_path", methods=["POST"])
def compare_path():
    data = request.get_json()
    src = nearest_node(*data["start"])
    tgt = nearest_node(*data["end"])
    if src == tgt:
        return jsonify({"error": "Same start/end point"}), 400

    results = []
    adj = adj_as_lists()
    for algo in ["A Star", "Dijkstra", "UCS", "Greedy BFS"]:
        try:
            t0 = time.perf_counter()
            _, cost, expanded = find_path(algo, adj, NODE_COORDS, src, tgt)
            elapsed = (time.perf_counter() - t0) * 1000
            results.append({
                "algorithm": algo,
                "cost_km": round(cost / 1000, 3),
                "travel_min": round(cost / 1000 / SUBWAY_SPEED_KMH * 60, 1),
                "nodes_expanded": expanded,
                "elapsed_ms": round(elapsed, 1),
            })
        except ValueError:
            results.append({"algorithm": algo, "error": "No path"})
    return jsonify(results)

@app.route("/setup_path", methods=["POST"])
def setup_path():
    data = request.get_json()
    src = nearest_node(*data["start"])
    tgt = nearest_node(*data["end"])
    action = data["action"]
    severity = int(data.get("severity", 100))  # multiplier: 2, 10, or 100

    if action == "SetTraficjam":
        try:
            path, _, _ = find_path("A Star", adj_as_lists(), NODE_COORDS, src, tgt)
        except ValueError as e:
            return jsonify({"error": f"No path found: {e}"}), 404

        saved_edges = []
        jammed_coords = []
        railway_only = True

        for i in range(len(path) - 1):
            u, v = path[i], path[i + 1]
            pair = (min(u, v), max(u, v))
            if pair in WALKING_EDGE_SET:
                railway_only = False
                continue
            for a, b in [(u, v), (v, u)]:
                if b in ADJACENCY.get(a, {}):
                    saved_edges.append((a, b, ADJACENCY[a][b]))
                    ADJACENCY[a][b] *= severity
            jammed_coords.append([[NODE_COORDS[u][0], NODE_COORDS[u][1]],
                                   [NODE_COORDS[v][0], NODE_COORDS[v][1]]])

        if not saved_edges:
            return jsonify({
                "error": "❌ Cannot set traffic jam: the path is a walking transfer only. "
                         "Traffic jams only apply to real train tracks."
            }), 400

        start_name = STATION_NODES.get(src, f"Stop {src}")
        end_name   = STATION_NODES.get(tgt, f"Stop {tgt}")
        sev_label  = {2: "Mild ×2", 10: "Heavy ×10", 100: "Blocked ×100"}.get(severity, f"×{severity}")
        label = f"{start_name} ↔ {end_name} [{sev_label}]"
        if not railway_only:
            label += " (walking skipped)"
        TRAFFIC_JAMS.append({
            "start": start_name, "end": end_name, "label": label,
            "edges": saved_edges, "coords": jammed_coords
        })
    else:
        return jsonify({"error": "Unknown action"}), 400

    rebuild_kdtree()
    edges = serialise_edges()
    return jsonify({
        "nodes": serialise_nodes(),
        "railway": edges["railway"],
        "walking": edges["walking"],
        "traffic_jams": _public_jams()
    })

@app.route("/delete_jam", methods=["POST"])
def delete_jam():
    idx = request.get_json().get("index")
    if idx is None or idx < 0 or idx >= len(TRAFFIC_JAMS):
        return jsonify({"error": "Invalid index"}), 400
    jam = TRAFFIC_JAMS.pop(idx)
    for a, b, original_w in jam["edges"]:
        if b in ADJACENCY.get(a, {}):
            ADJACENCY[a][b] = original_w
    rebuild_kdtree()
    edges = serialise_edges()
    return jsonify({
        "nodes": serialise_nodes(),
        "railway": edges["railway"],
        "walking": edges["walking"],
        "traffic_jams": _public_jams()
    })

@app.route("/reset_jams", methods=["POST"])
def reset_jams():
    global TRAFFIC_JAMS
    for jam in TRAFFIC_JAMS:
        for a, b, original_w in jam["edges"]:
            if b in ADJACENCY.get(a, {}):
                ADJACENCY[a][b] = original_w
    TRAFFIC_JAMS = []
    rebuild_kdtree()
    edges = serialise_edges()
    return jsonify({
        "nodes": serialise_nodes(),
        "railway": edges["railway"],
        "walking": edges["walking"],
        "traffic_jams": []
    })

if __name__ == "__main__":
    app.run(debug=True, port=5000)