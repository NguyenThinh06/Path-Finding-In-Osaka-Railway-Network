/* ──────────────────────────────────────────────────────────────
   Map & Layer Setup
   ────────────────────────────────────────────────────────────── */

const map = L.map('map', { zoomControl: false }).setView([34.693, 135.502], 13);

L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
    attribution: '© Esri, DigitalGlobe, Earthstar Geographics',
    maxZoom: 18
}).addTo(map);

L.control.zoom({ position: 'bottomleft' }).addTo(map);

const pathLayer = L.layerGroup().addTo(map);
const stationLayer = L.layerGroup().addTo(map);
const resultLayer = L.layerGroup().addTo(map);

/* ──────────────────────────────────────────────────────────────
   Layer Management
   ────────────────────────────────────────────────────────────── */

function rebuildLayers(nodes, railway, stations) {
    pathLayer.clearLayers();
    stationLayer.clearLayers();

    railway.forEach(function(p) {
        L.polyline(p, { color: '#2a3550', weight: 2, opacity: 0.9 }).addTo(pathLayer);
    });

    if (stations) {
        stations.forEach(function(station) {
            L.marker([station.lat, station.lon], {
                icon: L.divIcon({
                    className: 'station-icon',
                    html: '<div style="width:10px;height:10px;background:#f5c842;border-radius:50%;box-shadow:0 1px 4px rgba(0,0,0,0.6);border:1px solid rgba(255,255,255,0.3)"></div>',
                    iconSize: [10, 10],
                    iconAnchor: [5, 5],
                    popupAnchor: [0, -5]
                })
            }).bindPopup('<b>' + station.name + '</b>').addTo(stationLayer);
        });
    }
}

rebuildLayers(node_coords, railway_coords, station_labels);

function pinIcon(color, label) {
    return L.divIcon({
        className: '',
        html: `<div style="width:28px;height:28px;border-radius:50% 50% 50% 0;background:${color};transform:rotate(-45deg);display:flex;align-items:center;justify-content:center;box-shadow:0 2px 8px rgba(0,0,0,0.5);border:2px solid rgba(255,255,255,0.2)"><span style="transform:rotate(45deg);font-size:11px">${label}</span></div>`,
        iconSize: [28, 28],
        iconAnchor: [14, 28],
        popupAnchor: [0, -30]
    });
}

/* ──────────────────────────────────────────────────────────────
   State Management
   ────────────────────────────────────────────────────────────── */

let clickCoords = [];
let startMarker, endMarker, resultPolyline, startLine, endLine;

function clearResult() {
    resultLayer.clearLayers();
    startMarker = endMarker = resultPolyline = startLine = endLine = null;
    document.getElementById('stats').style.display = 'none';
}

function setStatus(msg) {
    document.getElementById('status-text').textContent = msg;
}

/* ──────────────────────────────────────────────────────────────
   Event Listeners - Layer Toggles
   ────────────────────────────────────────────────────────────── */

document.getElementById('toggleNodes').addEventListener('click', function() {
    map.hasLayer(stationLayer) ? map.removeLayer(stationLayer) : map.addLayer(stationLayer);
});

document.getElementById('togglePaths').addEventListener('click', function() {
    map.hasLayer(pathLayer) ? map.removeLayer(pathLayer) : map.addLayer(pathLayer);
});

/* ──────────────────────────────────────────────────────────────
   Event Listeners - Panel Controls
   ────────────────────────────────────────────────────────────── */

['panel', 'stats', 'mode-badge', 'statusbar'].forEach(id =>
    L.DomEvent.disableClickPropagation(document.getElementById(id))
);

const modeBadge = document.getElementById('mode-badge');

document.getElementById('actionSelect').addEventListener('change', function() {
    const setup = this.value === 'SetupMap';
    document.getElementById('setup-section').style.display = setup ? 'block' : 'none';
    document.getElementById('algorithmSelect').closest('div').style.display = setup ? 'none' : 'block';
    modeBadge.className = setup ? 'find setup' : 'find';
    modeBadge.textContent = setup ? 'SETUP MODE' : 'FIND PATH';
    document.getElementById('hint-text').textContent = setup ? 'Select two nodes, then click Apply' : 'Click map twice: start → end';
    clickCoords = [];
    clearResult();
    setStatus('Mode switched — ' + (setup ? 'select two nodes for setup action' : 'click to set start point'));
});

/* ──────────────────────────────────────────────────────────────
   Event Listeners - Map Interactions
   ────────────────────────────────────────────────────────────── */

map.on('mousemove', function(e) {
    document.getElementById('coord-display').textContent = e.latlng.lat.toFixed(5) + ', ' + e.latlng.lng.toFixed(5);
});

document.getElementById('Setup').addEventListener('click', function() {
    if (document.getElementById('actionSelect').value !== 'SetupMap') return;
    if (clickCoords.length < 2) {
        setStatus('⚠  Select both start and end points first!');
        return;
    }
    const action = document.getElementById('setupActionSelect').value;
    setStatus('Applying: ' + action + ' …');

    fetch('/setup_path', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ start: clickCoords[0], end: clickCoords[1], action })
    })
        .then(r => r.json())
        .then(res => {
            clearResult();
            clickCoords = [];
            rebuildLayers(res.nodes, res.railway, station_labels);
            setStatus('✅  Action applied: ' + action);
        })
        .catch(e => setStatus('❌  Error: ' + e));
});

map.on('click', function(e) {
    const mode = document.getElementById('actionSelect').value;

    if (clickCoords.length >= 2) {
        clickCoords = [];
        clearResult();
    }

    const lat = e.latlng.lat, lng = e.latlng.lng;
    clickCoords.push([lat, lng]);

    if (clickCoords.length === 1) {
        startMarker = L.marker([lat, lng], { icon: pinIcon('#4caf7d', '🟢') })
            .addTo(resultLayer)
            .bindPopup('<b>Start</b>')
            .openPopup();
        setStatus('Start set — now click to set end point');
    }
    else if (clickCoords.length === 2) {
        endMarker = L.marker([lat, lng], { icon: pinIcon('#e8492a', '🔴') })
            .addTo(resultLayer)
            .bindPopup('<b>End</b>')
            .openPopup();

        if (mode === 'SetupMap') {
            setStatus('Both points set — click Apply Action');
            return;
        }

        const algorithm = document.getElementById('algorithmSelect').value;
        setStatus('🔍  Running ' + algorithm + ' …');

        fetch('/find_shortest_path', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                start: clickCoords[0],
                end: clickCoords[1],
                algorithm,
                max_depth: '0'
            })
        })
            .then(r => {
                if (!r.ok) return r.json().then(d => { throw new Error(d.error); });
                return r.json();
            })
            .then(res => {
                startLine = L.polyline(res.start_path, {
                    color: '#e8492a', weight: 2, dashArray: '5,6', opacity: 0.7
                }).addTo(resultLayer);

                endLine = L.polyline(res.end_path, {
                    color: '#e8492a', weight: 2, dashArray: '5,6', opacity: 0.7
                }).addTo(resultLayer);

                if (res.railway_segments && res.railway_segments.length > 0) {
                    res.railway_segments.forEach(function(seg) {
                        L.polyline(seg, {
                            color: '#f5c842', weight: 4, opacity: 0.95
                        }).addTo(resultLayer);
                    });
                }

                if (res.walking_segments && res.walking_segments.length > 0) {
                    res.walking_segments.forEach(function(seg) {
                        L.polyline(seg, {
                            color: '#ff7f50', weight: 5, opacity: 0.95, dashArray: '6,5'
                        }).addTo(resultLayer);
                    });
                }

                const allPathCoords = res.path_coords;
                if (allPathCoords.length > 0) {
                    map.fitBounds(L.polyline(allPathCoords).getBounds(), { padding: [60, 60] });
                }

                res.path_coords.forEach(function(c, i) {
                    if (i === 0 || i === res.path_coords.length - 1) return;
                    L.circleMarker(c, {
                        radius: 2.5, color: '#f5c842', fillColor: '#fff',
                        fillOpacity: 1, weight: 1.5
                    }).addTo(resultLayer);
                });

                document.getElementById('s-algo').textContent = res.algorithm;
                document.getElementById('s-dist').textContent = res.cost_km + ' km';
                document.getElementById('s-nodes').textContent = res.nodes_in_path;
                document.getElementById('s-expanded').textContent = res.nodes_expanded;
                document.getElementById('s-time').textContent = res.elapsed_ms + ' ms';
                document.getElementById('stats').style.display = 'block';

                setStatus('✅  Path found — ' + res.cost_km + ' km via ' + res.algorithm + '  (' + res.nodes_expanded + ' nodes expanded)');
            })
            .catch(e => {
                setStatus('❌  ' + e.message);
            });
    }
});
