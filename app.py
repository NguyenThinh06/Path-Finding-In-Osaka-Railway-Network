import math, os, pickle, time
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

def _download_graph():
    print("Downloading Osaka railway network…")
    G = ox.graph_from_place(
        "Osaka, Japan",
        custom_filter=RAILWAY_FILTER,
        retain_all=True,
        simplify=False,
    )
    print(f"Nodes: {G.number_of_nodes():,} | Edges: {G.number_of_edges():,}")
    return G

def _build_state(G):
    node_coords = {}
    adjacency = {}
    station_nodes = {}

    for nid, data in G.nodes(data=True):
        node_coords[nid] = (float(data["y"]), float(data["x"]))
        adjacency[nid] = {}
        
        railway = data.get("railway", "")
        pt = data.get("public_transport", "")
        is_station = (
            railway in ["station", "halt", "tram_stop", "subway_entrance", "railway_station", "stop"]
            or pt in ["station", "stop_position", "stop_area"]
            or data.get("amenity") == "bus_station"
        )
        
        if is_station:
            name = (data.get("name") or "").strip()
            station_nodes[nid] = name if name else f"Stop {nid}"

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

        if v not in adjacency[u] or w < adjacency[u][v]:
            adjacency[u][v] = w

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

    walking_drawn = set()
    walking_geoms = []
    walking_edges = set()

    for i, sta1 in enumerate(station_nodes.keys()):
        lat1, lon1 = node_coords[sta1]
        for sta2 in list(station_nodes.keys())[i+1:]:
            lat2, lon2 = node_coords[sta2]
            dist = haversine(lat1, lon1, lat2, lon2)
            
            if dist < 600:
                weight = dist + 180
                
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
    G = _download_graph()
    state = _build_state(G)
    with open(CACHE_FILE, "wb") as f:
        pickle.dump(state, f)
    print("Graph cached")
    return state

NODE_COORDS, ADJACENCY, RAILWAY_EDGES, WALKING_EDGES, STATION_NODES, RAILWAY_EDGE_SET, WALKING_EDGE_SET = load_state()

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

@app.route("/")
def index():
    edges = serialise_edges()
    return render_template("map.html",
        node_coords=serialise_nodes(),
        railway_coords=edges["railway"],
        walking_coords=edges["walking"],
        station_labels=serialise_station_labels())

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
    
    railway_segments = []
    walking_segments = []
    
    for i in range(len(path) - 1):
        u, v = path[i], path[i + 1]
        pair = (min(u, v), max(u, v))
        seg = [[NODE_COORDS[u][0], NODE_COORDS[u][1]], [NODE_COORDS[v][0], NODE_COORDS[v][1]]]
        
        if pair in WALKING_EDGE_SET:
            walking_segments.append(seg)
        else:
            railway_segments.append(seg)

    waypoints = [{"name": STATION_NODES[n], "lat": NODE_COORDS[n][0], "lon": NODE_COORDS[n][1]}
                 for n in path if n in STATION_NODES]

    return jsonify({
        "path_coords": path_coords,
        "railway_segments": railway_segments,
        "walking_segments": walking_segments,
        "start_path": [data["start"], [NODE_COORDS[src][0], NODE_COORDS[src][1]]],
        "end_path": [data["end"], [NODE_COORDS[tgt][0], NODE_COORDS[tgt][1]]],
        "cost_km": round(cost / 1000, 3),
        "nodes_in_path": len(path),
        "nodes_expanded": expanded,
        "elapsed_ms": round(elapsed, 1),
        "algorithm": data.get("algorithm", "A Star"),
        "waypoints": waypoints,
    })

@app.route("/setup_path", methods=["POST"])
def setup_path():
    data = request.get_json()
    src = nearest_node(*data["start"])
    tgt = nearest_node(*data["end"])
    action = data["action"]

    if action == "DeletePath":
        ADJACENCY[src].pop(tgt, None)
    elif action == "DeletePathBoth":
        ADJACENCY[src].pop(tgt, None)
        ADJACENCY[tgt].pop(src, None)
    elif action == "SetTraficjam":
        for a, b in [(src, tgt), (tgt, src)]:
            if b in ADJACENCY.get(a, {}):
                ADJACENCY[a][b] *= 5
    else:
        return jsonify({"error": f"Unknown action"}), 400

    rebuild_kdtree()
    edges = serialise_edges()
    return jsonify({
        "nodes": serialise_nodes(),
        "railway": edges["railway"],
        "walking": edges["walking"]
    })

if __name__ == "__main__":
    app.run(debug=True, port=5000)