# 🚇 Osaka Railway Pathfinder — Flask Web App

Interactive map application applying pathfinding algorithms to Osaka's real railway network.

## Project Structure

```
osaka_webapp/
├── app.py              # Flask backend + API routes
├── algorithms.py       # A*, Dijkstra, UCS, Greedy BFS (all from scratch)
├── templates/
│   └── map.html        # Leaflet.js interactive map
├── requirements.txt
└── README.md
```

## How to Run

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Start the Flask server
python app.py

# 3. Open browser
http://localhost:5000
```

> ⚠️ First launch downloads Osaka railway data from OpenStreetMap (~30s).
> Subsequent launches use the local cache (`osaka_graph.pkl`).

## Features

| Feature | Detail |
|---------|--------|
| **Click to find path** | Click start → end on the map |
| **4 algorithms** | A*, Dijkstra, UCS, Greedy BFS |
| **Path stats** | Distance, nodes expanded, time (ms) |
| **Toggle layers** | Show/hide nodes and edges |
| **Setup mode** | Delete edges or add traffic jam weight |
| **Dark theme** | CartoDB dark basemap + railway aesthetic |

## API Endpoints

### `POST /find_shortest_path`
```json
{ "start": [lat, lon], "end": [lat, lon], "algorithm": "A Star" }
```
**Returns:** path coordinates, cost (km), nodes expanded, elapsed ms

### `POST /setup_path`
```json
{ "start": [lat, lon], "end": [lat, lon], "action": "DeletePath" }
```
Actions: `DeletePath` | `DeletePathBoth` | `SetTraficjam`

## Algorithms (all from scratch, no built-ins)

| Algorithm | Strategy | Optimal? |
|-----------|----------|----------|
| **A\*** | f = g + h (haversine) | ✅ Yes |
| **Dijkstra** | f = g (uniform cost) | ✅ Yes |
| **UCS** | f = g (explicit frontier) | ✅ Yes |
| **Greedy BFS** | f = h only | ❌ No |
