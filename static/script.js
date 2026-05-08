/* ──────────────────────────────────────────────────────────────
   Map & Base Layers
   ────────────────────────────────────────────────────────────── */

const map = L.map('map', { zoomControl: false }).setView([34.693, 135.502], 13);

L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
    attribution: '© Esri, DigitalGlobe, Earthstar Geographics',
    maxZoom: 18
}).addTo(map);

L.control.zoom({ position: 'bottomleft' }).addTo(map);

const pathLayer    = L.layerGroup().addTo(map);
const stationLayer = L.layerGroup().addTo(map);
const resultLayer  = L.layerGroup().addTo(map);
const jamLayer     = L.layerGroup().addTo(map);  // jammed edge overlays

/* ──────────────────────────────────────────────────────────────
   Layer Rendering
   ────────────────────────────────────────────────────────────── */

function rebuildLayers(nodes, railway, stations) {
    pathLayer.clearLayers();
    stationLayer.clearLayers();
    railway.forEach(p => L.polyline(p, { color: '#2a3550', weight: 2, opacity: 0.9 }).addTo(pathLayer));
    if (stations) {
        stations.forEach(s => {
            L.marker([s.lat, s.lon], {
                icon: L.divIcon({
                    className: 'station-icon',
                    html: '<div style="width:10px;height:10px;background:#f5c842;border-radius:50%;box-shadow:0 1px 4px rgba(0,0,0,0.6);border:1px solid rgba(255,255,255,0.3)"></div>',
                    iconSize: [10, 10], iconAnchor: [5, 5], popupAnchor: [0, -5]
                })
            }).bindPopup('<b>' + s.name + '</b>').addTo(stationLayer);
        });
    }
}

rebuildLayers(node_coords, railway_coords, station_labels);

/* ──────────────────────────────────────────────────────────────
   Traffic Jam Layer & Dashboard
   ────────────────────────────────────────────────────────────── */

function redrawJamLayer() {
    jamLayer.clearLayers();
    traffic_jams.forEach(tj => {
        if (tj.coords && tj.coords.length > 0) {
            tj.coords.forEach(seg => {
                L.polyline(seg, {
                    color: '#e8492a', weight: 5, opacity: 0.8,
                    dashArray: '6,4'
                }).bindTooltip('🚨 ' + tj.label, { sticky: true }).addTo(jamLayer);
            });
        }
    });
}

function renderTrafficJams() {
    const container = document.getElementById('tj-items');
    if (!container) return;
    container.innerHTML = '';
    if (!traffic_jams || traffic_jams.length === 0) {
        container.innerHTML = '<div style="color:rgba(255,255,255,0.4);font-style:italic">No traffic jams set.</div>';
        redrawJamLayer();
        return;
    }
    traffic_jams.forEach((tj, idx) => {
        const d = document.createElement('div');
        d.style.cssText = 'display:flex;align-items:center;justify-content:space-between;margin-bottom:4px;padding-bottom:4px;border-bottom:1px solid rgba(255,100,50,0.2)';
        d.innerHTML =
            `<span style="font-size:10px"><span style="color:#e8492a">⚠</span> ${tj.label || (tj.start + ' ↔ ' + tj.end)}</span>` +
            `<button data-idx="${idx}" style="background:rgba(232,73,42,0.15);border:1px solid #e8492a;color:#e8492a;border-radius:4px;cursor:pointer;padding:1px 6px;font-size:10px;flex-shrink:0;margin-left:6px" title="Remove">✕</button>`;
        d.querySelector('button').addEventListener('click', function() {
            deleteJam(parseInt(this.dataset.idx));
        });
        container.appendChild(d);
    });
    redrawJamLayer();
}

renderTrafficJams();

function deleteJam(idx) {
    fetch('/delete_jam', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ index: idx })
    }).then(r => r.json()).then(res => {
        if (res.error) { setStatus('❌ ' + res.error); return; }
        traffic_jams = res.traffic_jams;
        renderTrafficJams();
        rebuildLayers(res.nodes, res.railway, station_labels);
        setStatus('✅ Traffic jam removed.');
    }).catch(e => setStatus('❌ Error: ' + e));
}

document.getElementById('btnResetJams').addEventListener('click', () => {
    if (!traffic_jams.length) { setStatus('No traffic jams to reset.'); return; }
    fetch('/reset_jams', { method: 'POST' }).then(r => r.json()).then(res => {
        traffic_jams = res.traffic_jams;
        renderTrafficJams();
        rebuildLayers(res.nodes, res.railway, station_labels);
        setStatus('✅ All traffic jams cleared.');
    }).catch(e => setStatus('❌ Error: ' + e));
});

/* ──────────────────────────────────────────────────────────────
   Station Search
   ────────────────────────────────────────────────────────────── */

let allStations = [];
let searchPending = null; // 'start' | 'end'

fetch('/stations').then(r => r.json()).then(data => { allStations = data; });

const searchInput    = document.getElementById('stationSearch');
const searchDropdown = document.getElementById('searchDropdown');

searchInput.addEventListener('input', function() {
    const q = this.value.trim().toLowerCase();
    searchDropdown.innerHTML = '';
    if (q.length < 1) { searchDropdown.style.display = 'none'; return; }

    const matches = allStations.filter(s => s.name.toLowerCase().includes(q)).slice(0, 12);
    if (!matches.length) { searchDropdown.style.display = 'none'; return; }

    matches.forEach(s => {
        const div = document.createElement('div');
        div.className = 'sdi';
        div.innerHTML = `${s.name}<div class="sdi-sub">${s.lat.toFixed(4)}, ${s.lon.toFixed(4)}</div>`;
        div.addEventListener('click', () => {
            map.setView([s.lat, s.lon], 16);
            searchInput.value = '';
            searchDropdown.style.display = 'none';
            setSearchPoint([s.lat, s.lon], s.name);
        });
        searchDropdown.appendChild(div);
    });
    searchDropdown.style.display = 'block';
});

document.addEventListener('click', e => {
    if (!searchInput.contains(e.target) && !searchDropdown.contains(e.target)) {
        searchDropdown.style.display = 'none';
    }
});

function setSearchPoint(latlng, name) {
    if (clickCoords.length >= 2) { clickCoords = []; clearResult(); }
    const [lat, lng] = latlng;
    clickCoords.push([lat, lng]);
    if (clickCoords.length === 1) {
        startMarker = L.marker([lat, lng], { icon: pinIcon('#4caf7d', '🟢') })
            .addTo(resultLayer).bindPopup('<b>Start: ' + name + '</b>').openPopup();
        setStatus('Start set: ' + name + ' — select end station');
    } else {
        endMarker = L.marker([lat, lng], { icon: pinIcon('#e8492a', '🔴') })
            .addTo(resultLayer).bindPopup('<b>End: ' + name + '</b>').openPopup();
        if (currentMode === 'SetupMap') {
            previewSetupPath();
        } else {
            runPathfind();
        }
    }
}

/* ──────────────────────────────────────────────────────────────
   Icons & Helpers
   ────────────────────────────────────────────────────────────── */

function pinIcon(color, label) {
    return L.divIcon({
        className: '',
        html: `<div style="width:28px;height:28px;border-radius:50% 50% 50% 0;background:${color};transform:rotate(-45deg);display:flex;align-items:center;justify-content:center;box-shadow:0 2px 8px rgba(0,0,0,0.5);border:2px solid rgba(255,255,255,0.2)"><span style="transform:rotate(45deg);font-size:11px">${label}</span></div>`,
        iconSize: [28, 28], iconAnchor: [14, 28], popupAnchor: [0, -30]
    });
}

/* ──────────────────────────────────────────────────────────────
   State
   ────────────────────────────────────────────────────────────── */

let clickCoords = [];
let startMarker, endMarker, startLine, endLine;
let currentMode = 'FindPath';

function clearResult() {
    resultLayer.clearLayers();
    startMarker = endMarker = startLine = endLine = null;
    document.getElementById('stats').style.display = 'none';
    document.getElementById('compare-panel').style.display = 'none';
}

function setStatus(msg) {
    document.getElementById('status-text').textContent = msg;
}

['panel', 'stats', 'mode-badge', 'statusbar', 'compare-panel'].forEach(id => {
    const el = document.getElementById(id);
    if (el) L.DomEvent.disableClickPropagation(el);
});

/* ──────────────────────────────────────────────────────────────
   Mode Toggle
   ────────────────────────────────────────────────────────────── */

const modeBadge = document.getElementById('mode-badge');

document.getElementById('actionSelect').addEventListener('change', function() {
    currentMode = this.value;
    const isSetup = currentMode === 'SetupMap';
    document.getElementById('findpath-section').style.display = isSetup ? 'none' : 'block';
    document.getElementById('setup-section').style.display    = isSetup ? 'block' : 'none';
    modeBadge.className   = isSetup ? 'find setup' : 'find';
    modeBadge.textContent = isSetup ? 'SETUP MODE' : 'FIND PATH';
    document.getElementById('hint-text').textContent = isSetup
        ? 'Click 2 stations → Set Traffic Jam' : 'Click map twice: start → end';
    clickCoords = []; clearResult();
    setStatus(isSetup ? 'Setup mode — click first station' : 'Find path mode — click start point');
});

/* ──────────────────────────────────────────────────────────────
   Layer Toggles
   ────────────────────────────────────────────────────────────── */

document.getElementById('toggleNodes').addEventListener('click', () =>
    map.hasLayer(stationLayer) ? map.removeLayer(stationLayer) : map.addLayer(stationLayer));
document.getElementById('togglePaths').addEventListener('click', () =>
    map.hasLayer(pathLayer) ? map.removeLayer(pathLayer) : map.addLayer(pathLayer));

/* ──────────────────────────────────────────────────────────────
   Setup Mode — Preview & Apply Jam
   ────────────────────────────────────────────────────────────── */

function previewSetupPath() {
    setStatus('🔍 Previewing path between stations…');
    fetch('/find_shortest_path', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ start: clickCoords[0], end: clickCoords[1], algorithm: 'A Star', max_depth: '0' })
    })
    .then(r => r.ok ? r.json() : r.json().then(d => { throw new Error(d.error); }))
    .then(res => {
        (res.railway_segments || []).forEach(seg =>
            L.polyline(seg, { color: '#f5a623', weight: 4, opacity: 0.9, dashArray: '8,4' }).addTo(resultLayer));
        (res.walking_segments || []).forEach(seg =>
            L.polyline(seg, { color: '#aaa', weight: 3, opacity: 0.6, dashArray: '4,4' }).addTo(resultLayer));
        if (res.path_coords.length)
            map.fitBounds(L.polyline(res.path_coords).getBounds(), { padding: [60, 60] });
        setStatus('✅ Path previewed — walking segments (grey) will NOT be jammed. Click Set Traffic Jam to apply.');
    })
    .catch(e => setStatus('⚠ ' + e.message + ' — click Set Traffic Jam to jam direct edge'));
}

document.getElementById('btnSetJam').addEventListener('click', () => {
    if (clickCoords.length < 2) { setStatus('⚠ Click 2 stations first!'); return; }
    const severity = document.getElementById('severitySelect').value;
    setStatus('Applying traffic jam…');
    fetch('/setup_path', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ start: clickCoords[0], end: clickCoords[1], action: 'SetTraficjam', severity })
    })
    .then(r => r.json())
    .then(res => {
        if (res.error) { setStatus(res.error); return; }
        traffic_jams = res.traffic_jams;
        renderTrafficJams();
        rebuildLayers(res.nodes, res.railway, station_labels);
        clickCoords = []; clearResult();
        setStatus('✅ Traffic jam applied! Pick next stations or switch mode.');
    })
    .catch(e => setStatus('❌ Error: ' + e));
});

document.getElementById('btnClearSetup').addEventListener('click', () => {
    clickCoords = []; clearResult();
    setStatus('Selection cleared — click first station.');
});

/* ──────────────────────────────────────────────────────────────
   Pathfinding
   ────────────────────────────────────────────────────────────── */

function runPathfind() {
    const algorithm = document.getElementById('algorithmSelect').value;
    setStatus('🔍 Running ' + algorithm + ' …');

    fetch('/find_shortest_path', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ start: clickCoords[0], end: clickCoords[1], algorithm, max_depth: '0' })
    })
    .then(r => r.ok ? r.json() : r.json().then(d => { throw new Error(d.error); }))
    .then(res => {
        startLine = L.polyline(res.start_path, { color: '#e8492a', weight: 2, dashArray: '5,6', opacity: 0.7 }).addTo(resultLayer);
        endLine   = L.polyline(res.end_path,   { color: '#e8492a', weight: 2, dashArray: '5,6', opacity: 0.7 }).addTo(resultLayer);

        (res.railway_segments || []).forEach(seg =>
            L.polyline(seg, { color: '#f5c842', weight: 4, opacity: 0.95 }).addTo(resultLayer));
        (res.walking_segments || []).forEach(seg =>
            L.polyline(seg, { color: '#ff7f50', weight: 5, opacity: 0.95, dashArray: '6,5' }).addTo(resultLayer));

        if (res.path_coords.length)
            map.fitBounds(L.polyline(res.path_coords).getBounds(), { padding: [60, 60] });

        res.path_coords.forEach((c, i) => {
            if (i === 0 || i === res.path_coords.length - 1) return;
            L.circleMarker(c, { radius:2.5, color:'#f5c842', fillColor:'#fff', fillOpacity:1, weight:1.5 }).addTo(resultLayer);
        });

        // Stats
        document.getElementById('s-algo').textContent     = res.algorithm;
        document.getElementById('s-dist').textContent     = res.cost_km + ' km';
        document.getElementById('s-time-est').textContent = res.travel_min + ' min';
        document.getElementById('s-nodes').textContent    = res.nodes_in_path;
        document.getElementById('s-expanded').textContent = res.nodes_expanded;
        document.getElementById('s-time').textContent     = res.elapsed_ms + ' ms';
        document.getElementById('stats').style.display    = 'block';

        // Waypoints
        const wpList = document.getElementById('waypoints-list');
        wpList.innerHTML = '';
        (res.waypoints || []).forEach(wp => {
            const d = document.createElement('div');
            d.className = 'wp';
            d.innerHTML = `<div class="wp-dot"></div>${wp.name}`;
            wpList.appendChild(d);
        });
        document.getElementById('waypoints-section').style.display = res.waypoints && res.waypoints.length ? 'block' : 'none';

        setStatus('✅ Path found — ' + res.cost_km + ' km / ~' + res.travel_min + ' min via ' + res.algorithm);
    })
    .catch(e => setStatus('❌ ' + e.message));
}

/* ──────────────────────────────────────────────────────────────
   Algorithm Comparison
   ────────────────────────────────────────────────────────────── */

document.getElementById('btnCompare').addEventListener('click', () => {
    if (clickCoords.length < 2) {
        setStatus('⚠ Select start and end first, then click Compare.');
        return;
    }
    setStatus('📊 Comparing all algorithms…');
    fetch('/compare_path', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ start: clickCoords[0], end: clickCoords[1] })
    })
    .then(r => r.json())
    .then(results => {
        const panel = document.getElementById('compare-panel');
        const table = document.getElementById('compare-table');

        // Find best (shortest distance among successful runs)
        const best = results.reduce((b, r) => (!r.error && (!b || r.cost_km < b.cost_km)) ? r : b, null);

        table.innerHTML = `
            <table style="width:100%;border-collapse:collapse;font-size:10px">
            <thead><tr>
                <th style="text-align:left;color:var(--muted);font-size:9px;padding:4px 6px;border-bottom:1px solid var(--border)">Algorithm</th>
                <th style="text-align:right;color:var(--muted);font-size:9px;padding:4px 6px;border-bottom:1px solid var(--border)">Dist</th>
                <th style="text-align:right;color:var(--muted);font-size:9px;padding:4px 6px;border-bottom:1px solid var(--border)">Time</th>
                <th style="text-align:right;color:var(--muted);font-size:9px;padding:4px 6px;border-bottom:1px solid var(--border)">Expanded</th>
                <th style="text-align:right;color:var(--muted);font-size:9px;padding:4px 6px;border-bottom:1px solid var(--border)">ms</th>
            </tr></thead>
            <tbody>${results.map(r => {
                if (r.error) return `<tr><td style="padding:5px 6px">${r.algorithm}</td><td colspan="4" style="color:var(--accent);padding:5px 6px;text-align:center">No path</td></tr>`;
                const highlight = best && r.algorithm === best.algorithm ? 'color:var(--gold)' : '';
                const star = best && r.algorithm === best.algorithm ? ' ⭐' : '';
                return `<tr style="${highlight}">
                    <td style="padding:5px 6px">${r.algorithm}${star}</td>
                    <td style="text-align:right;padding:5px 6px">${r.cost_km}km</td>
                    <td style="text-align:right;padding:5px 6px">${r.travel_min}m</td>
                    <td style="text-align:right;padding:5px 6px">${r.nodes_expanded}</td>
                    <td style="text-align:right;padding:5px 6px">${r.elapsed_ms}</td>
                </tr>`;
            }).join('')}</tbody>
            </table>`;

        panel.style.display = 'block';
        setStatus('📊 Comparison done!');
    })
    .catch(e => setStatus('❌ Compare error: ' + e));
});

document.getElementById('btnCloseCompare').addEventListener('click', () => {
    document.getElementById('compare-panel').style.display = 'none';
});

/* ──────────────────────────────────────────────────────────────
   Map Click Handler
   ────────────────────────────────────────────────────────────── */

map.on('mousemove', e =>
    document.getElementById('coord-display').textContent =
        e.latlng.lat.toFixed(5) + ', ' + e.latlng.lng.toFixed(5));

map.on('click', function(e) {
    if (clickCoords.length >= 2) { clickCoords = []; clearResult(); }

    const lat = e.latlng.lat, lng = e.latlng.lng;
    clickCoords.push([lat, lng]);

    if (clickCoords.length === 1) {
        const color = currentMode === 'SetupMap' ? '#f5a623' : '#4caf7d';
        const label = currentMode === 'SetupMap' ? '①' : '🟢';
        startMarker = L.marker([lat, lng], { icon: pinIcon(color, label) })
            .addTo(resultLayer).bindPopup('<b>' + (currentMode === 'SetupMap' ? 'Station A' : 'Start') + '</b>').openPopup();
        setStatus(currentMode === 'SetupMap' ? 'Station A selected — click Station B' : 'Start set — click end point');
        return;
    }

    const color2 = '#e8492a';
    const label2 = currentMode === 'SetupMap' ? '②' : '🔴';
    endMarker = L.marker([lat, lng], { icon: pinIcon(color2, label2) })
        .addTo(resultLayer).bindPopup('<b>' + (currentMode === 'SetupMap' ? 'Station B' : 'End') + '</b>').openPopup();

    if (currentMode === 'SetupMap') {
        previewSetupPath();
    } else {
        runPathfind();
    }
});
