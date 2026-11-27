"use strict";

// ==========================================================
// Einsatzkarte: Einsatzort und Quadranten (Suchabschnitte)
// ==========================================================
// Alle, die einen Einsatz sehen dürfen, sehen seine Quadranten. Die Karte
// fragt alle zwei Sekunden nur den Änderungszähler ab und lädt bei einer
// Änderung neu – neue Quadranten erscheinen so bei allen fast sofort.

const INCIDENT_MAP_POLL_MS = 2000;
const INCIDENT_MAP_LIST_MS = 30000;
const INCIDENT_MAP_STORAGE = "openBosIncidentMap";

const INCIDENT_MAP_COLORS = {
    open: "#5b6b82",
    assigned: "#d99518",
    searching: "#e0700b",
    done: "#17845b",
    finding: "#c92835",
};

const incidentMap = {
    map: null,
    guest: false,
    incidents: [],
    selectedId: null,
    data: null,
    revision: null,
    canEdit: false,
    mode: null,          // "grid" | "polygon" | "position"
    draft: [],
    gridCorners: null,
    selectedItem: null,
    labels: [],
    positionMarker: null,
    fitted: null,
    pollTimer: null,
    pollGeneration: 0,
    listTimer: null,
    message: "",
    error: false,
};

function incidentMapStorage(value) {
    try {
        if (value === undefined) {
            return localStorage.getItem(INCIDENT_MAP_STORAGE);
        }
        if (value === null) {
            localStorage.removeItem(INCIDENT_MAP_STORAGE);
        } else {
            localStorage.setItem(INCIDENT_MAP_STORAGE, String(value));
        }
    } catch (error) {
        // Ohne Speicher wird die Auswahl nicht gemerkt.
    }
    return null;
}

function incidentMapVisible() {
    return document.visibilityState === "visible" &&
        Boolean(document.getElementById("page-map")?.classList.contains("active"));
}

function incidentMapUrl(path = "") {
    if (incidentMap.guest) {
        return "/guest/incident-map";
    }
    return `/api/incidents/${incidentMap.selectedId}/map${path}`;
}

async function incidentMapFetch(url, options = {}) {
    if (typeof api !== "undefined") {
        return options.method
            ? api.request(url, {
                ...options,
                headers: {"Content-Type": "application/json"},
                body: options.body ? JSON.stringify(options.body) : undefined,
            })
            : api.get(url);
    }
    const response = await fetch(url, {cache: "no-store", credentials: "same-origin"});
    if (!response.ok) {
        const error = new Error(`HTTP ${response.status}`);
        error.status = response.status;
        throw error;
    }
    return response.json();
}

// ----------------------------------------------------------
// Ebenen
// ----------------------------------------------------------

function incidentMapEnsureLayers() {
    try {
        incidentMapAddLayers();
    } catch (error) {
        // Stil wird gerade gewechselt; der nächste styledata-Aufruf ergänzt.
        console.debug("Einsatzebenen noch nicht bereit:", error);
    }
}

function incidentMapAddLayers() {
    const m = incidentMap.map;
    if (!m) {
        return;
    }
    if (!m.getSource("incident-items")) {
        m.addSource("incident-items", {type: "geojson", data: {type: "FeatureCollection", features: []}});
    }
    if (!m.getSource("incident-draft")) {
        m.addSource("incident-draft", {type: "geojson", data: {type: "FeatureCollection", features: []}});
    }
    const color = ["match", ["get", "status"],
        ...Object.entries(INCIDENT_MAP_COLORS).flat(), INCIDENT_MAP_COLORS.open];
    if (!m.getLayer("incident-items-fill")) {
        m.addLayer({
            id: "incident-items-fill",
            type: "fill",
            source: "incident-items",
            paint: {
                "fill-color": color,
                "fill-opacity": ["case", ["get", "selected"], 0.42, 0.2],
            },
        });
    }
    if (!m.getLayer("incident-items-line")) {
        m.addLayer({
            id: "incident-items-line",
            type: "line",
            source: "incident-items",
            paint: {
                "line-color": color,
                "line-width": ["case", ["get", "selected"], 4, 2],
            },
        });
    }
    if (!m.getLayer("incident-draft-fill")) {
        m.addLayer({
            id: "incident-draft-fill",
            type: "fill",
            source: "incident-draft",
            filter: ["==", ["geometry-type"], "Polygon"],
            paint: {"fill-color": "#246bce", "fill-opacity": 0.15},
        });
        m.addLayer({
            id: "incident-draft-line",
            type: "line",
            source: "incident-draft",
            paint: {"line-color": "#246bce", "line-width": 2, "line-dasharray": [2, 1]},
        });
        m.addLayer({
            id: "incident-draft-points",
            type: "circle",
            source: "incident-draft",
            filter: ["==", ["geometry-type"], "Point"],
            paint: {
                "circle-radius": 5,
                "circle-color": "#ffffff",
                "circle-stroke-color": "#246bce",
                "circle-stroke-width": 2,
            },
        });
    }
}

function incidentMapCenter(geometry) {
    const ring = geometry.coordinates[0].slice(0, -1);
    const sum = ring.reduce((acc, [lon, lat]) => [acc[0] + lon, acc[1] + lat], [0, 0]);
    return [sum[0] / ring.length, sum[1] / ring.length];
}

function incidentMapRenderItems() {
    const m = incidentMap.map;
    if (!m) {
        return;
    }
    incidentMapEnsureLayers();
    const items = incidentMap.data?.items ?? [];
    const selected = incidentMap.selectedItem;
    m.getSource("incident-items")?.setData({
        type: "FeatureCollection",
        features: items.map(item => ({
            type: "Feature",
            id: item.id,
            geometry: item.geometry,
            properties: {
                id: item.id,
                name: item.name,
                status: item.status,
                selected: item.id === selected,
            },
        })),
    });
    // Beschriftung als HTML-Marker: unabhängig von den Schriften der Grundkarte.
    incidentMap.labels.forEach(marker => marker.remove());
    incidentMap.labels = items.map(item => {
        const element = document.createElement("div");
        element.className = `incident-map-label is-${item.status}`;
        element.innerHTML = `<strong>${escapeHTML(item.name)}</strong>${item.assignee
            ? `<span>${escapeHTML(item.assignee)}</span>` : ""}`;
        element.addEventListener("click", event => {
            event.stopPropagation();
            if (!incidentMap.mode) {
                incidentMapSelectItem(item.id);
            }
        });
        return new maplibregl.Marker({element})
            .setLngLat(incidentMapCenter(item.geometry))
            .addTo(m);
    });
    incidentMapRenderPosition();
}

function incidentMapRenderPosition() {
    const position = incidentMap.data?.position;
    if (!position) {
        incidentMap.positionMarker?.remove();
        incidentMap.positionMarker = null;
        return;
    }
    const lngLat = [position.longitude, position.latitude];
    if (!incidentMap.positionMarker) {
        const element = document.createElement("div");
        element.className = "incident-map-position";
        element.title = "Einsatzort";
        incidentMap.positionMarker = new maplibregl.Marker({element, anchor: "bottom"})
            .setLngLat(lngLat)
            .addTo(incidentMap.map);
    } else {
        incidentMap.positionMarker.setLngLat(lngLat);
    }
}

function incidentMapRenderDraft(cursor = null) {
    const source = incidentMap.map?.getSource("incident-draft");
    if (!source) {
        return;
    }
    const features = [];
    if (incidentMap.mode === "polygon") {
        const points = cursor ? [...incidentMap.draft, cursor] : incidentMap.draft;
        points.forEach(point => features.push({type: "Feature", geometry: {type: "Point", coordinates: point}}));
        if (points.length >= 3) {
            features.push({type: "Feature", geometry: {type: "Polygon", coordinates: [[...points, points[0]]]}});
        } else if (points.length === 2) {
            features.push({type: "Feature", geometry: {type: "LineString", coordinates: points}});
        }
    }
    if (incidentMap.mode === "grid" && incidentMap.draft.length) {
        const first = incidentMap.draft[0];
        const second = incidentMap.gridCorners?.[1] ?? cursor;
        features.push({type: "Feature", geometry: {type: "Point", coordinates: first}});
        if (second) {
            const [west, east] = [Math.min(first[0], second[0]), Math.max(first[0], second[0])];
            const [south, north] = [Math.min(first[1], second[1]), Math.max(first[1], second[1])];
            const rows = Number(document.getElementById("incident-grid-rows")?.value) || 1;
            const columns = Number(document.getElementById("incident-grid-columns")?.value) || 1;
            features.push({type: "Feature", geometry: {type: "Polygon", coordinates: [[
                [west, north], [east, north], [east, south], [west, south], [west, north],
            ]]}});
            for (let index = 1; index < columns && incidentMap.gridCorners; index += 1) {
                const lon = west + (east - west) * index / columns;
                features.push({type: "Feature", geometry: {type: "LineString", coordinates: [[lon, north], [lon, south]]}});
            }
            for (let index = 1; index < rows && incidentMap.gridCorners; index += 1) {
                const lat = north - (north - south) * index / rows;
                features.push({type: "Feature", geometry: {type: "LineString", coordinates: [[west, lat], [east, lat]]}});
            }
        }
    }
    source.setData({type: "FeatureCollection", features});
}

function incidentMapFit() {
    const m = incidentMap.map;
    const data = incidentMap.data;
    if (!m || !data || incidentMap.fitted === data.incident_id) {
        return;
    }
    incidentMap.fitted = data.incident_id;
    const points = (data.items || []).flatMap(item => item.geometry.coordinates[0]);
    if (data.position) {
        points.push([data.position.longitude, data.position.latitude]);
    }
    if (!points.length) {
        return;
    }
    if (points.length === 1) {
        m.flyTo({center: points[0], zoom: Math.max(m.getZoom(), 15)});
        return;
    }
    const lons = points.map(point => point[0]);
    const lats = points.map(point => point[1]);
    m.fitBounds([[Math.min(...lons), Math.min(...lats)], [Math.max(...lons), Math.max(...lats)]],
        {padding: 60, maxZoom: 17, duration: 600});
}

// ----------------------------------------------------------
// Bedienfeld
// ----------------------------------------------------------

function incidentMapPanel() {
    let panel = document.getElementById("map-incident-panel");
    if (!panel) {
        const container = document.getElementById("map-container");
        if (!container) {
            return null;
        }
        panel = document.createElement("details");
        panel.id = "map-incident-panel";
        panel.className = "map-incident-panel";
        panel.open = window.innerWidth > 640;
        container.appendChild(panel);
    }
    return panel;
}

function incidentMapStatusOptions(selected) {
    const statuses = incidentMap.data?.statuses ?? {};
    return Object.entries(statuses).map(([key, label]) =>
        `<option value="${escapeHTML(key)}" ${key === selected ? "selected" : ""}>${escapeHTML(label)}</option>`
    ).join("");
}

function incidentMapSummary() {
    const items = incidentMap.data?.items ?? [];
    if (!items.length) {
        return "";
    }
    const counts = {};
    items.forEach(item => {
        counts[item.status] = (counts[item.status] || 0) + 1;
    });
    const statuses = incidentMap.data.statuses;
    return `<div class="incident-map-legend">
        ${Object.entries(counts).map(([status, count]) => `
            <span><i style="background:${INCIDENT_MAP_COLORS[status] ?? INCIDENT_MAP_COLORS.open}"></i>
                ${count} ${escapeHTML(statuses[status] ?? status)}</span>`).join("")}
    </div>`;
}

function incidentMapToolsHTML() {
    if (!incidentMap.canEdit) {
        return "";
    }
    if (incidentMap.mode === "grid") {
        return incidentMap.gridCorners
            ? `<form class="incident-map-form" onsubmit="incidentMapCreateGrid(event)">
                <p>Raster über das Rechteck legen:</p>
                <div class="incident-map-row">
                    <label>Zeilen <input id="incident-grid-rows" class="bos-input" type="number" min="1" max="12" value="3"
                        oninput="incidentMapRenderDraft()"></label>
                    <label>Spalten <input id="incident-grid-columns" class="bos-input" type="number" min="1" max="12" value="3"
                        oninput="incidentMapRenderDraft()"></label>
                    <label>Präfix <input id="incident-grid-prefix" class="bos-input" maxlength="10" placeholder="optional"></label>
                </div>
                <div class="incident-map-row">
                    <button class="bos-button bos-button-small bos-button-green" type="submit">Raster anlegen</button>
                    <button class="bos-button bos-button-small" type="button" onclick="incidentMapCancel()">Abbrechen</button>
                </div>
            </form>`
            : `<p class="incident-map-hint">${incidentMap.draft.length
                ? "Jetzt die gegenüberliegende Ecke antippen."
                : "Erste Ecke des Suchgebiets antippen."}</p>
               <button class="bos-button bos-button-small" type="button" onclick="incidentMapCancel()">Abbrechen</button>`;
    }
    if (incidentMap.mode === "polygon") {
        return `<form class="incident-map-form" onsubmit="incidentMapFinishPolygon(event)">
            <p class="incident-map-hint">Eckpunkte antippen (${incidentMap.draft.length} gesetzt).</p>
            <div class="incident-map-row">
                <input id="incident-polygon-name" class="bos-input" maxlength="40" placeholder="Name, z. B. Waldstück Nord" required>
            </div>
            <div class="incident-map-row">
                <button class="bos-button bos-button-small bos-button-green" type="submit"
                    ${incidentMap.draft.length < 3 ? "disabled" : ""}>Fertig</button>
                <button class="bos-button bos-button-small" type="button" onclick="incidentMapUndo()"
                    ${incidentMap.draft.length ? "" : "disabled"}>Zurück</button>
                <button class="bos-button bos-button-small" type="button" onclick="incidentMapCancel()">Abbrechen</button>
            </div>
        </form>`;
    }
    if (incidentMap.mode === "position") {
        return `<p class="incident-map-hint">Einsatzort auf der Karte antippen.</p>
            <button class="bos-button bos-button-small" type="button" onclick="incidentMapCancel()">Abbrechen</button>`;
    }
    return `<div class="incident-map-row incident-map-tools">
        <button class="bos-button bos-button-small" type="button" onclick="incidentMapStart('grid')"
            title="Rechteck aufziehen und in gleich große Quadranten teilen">▦ Raster</button>
        <button class="bos-button bos-button-small" type="button" onclick="incidentMapStart('polygon')"
            title="Fläche frei zeichnen">⬠ Fläche</button>
        <button class="bos-button bos-button-small" type="button" onclick="incidentMapStart('position')"
            title="Einsatzort setzen">⌖ Einsatzort</button>
    </div>`;
}

function incidentMapItemHTML() {
    const item = (incidentMap.data?.items ?? []).find(entry => entry.id === incidentMap.selectedItem);
    if (!item) {
        return "";
    }
    if (!incidentMap.canEdit) {
        return `<div class="incident-map-item">
            <strong>${escapeHTML(item.name)}</strong>
            <span>${escapeHTML(item.status_label)}${item.assignee ? ` · ${escapeHTML(item.assignee)}` : ""}</span>
            ${item.note ? `<p>${escapeHTML(item.note)}</p>` : ""}
            <button class="bos-button bos-button-small" type="button" onclick="incidentMapSelectItem(null)">Schließen</button>
        </div>`;
    }
    return `<form class="incident-map-form incident-map-item" onsubmit="incidentMapSaveItem(event, ${Number(item.id)})">
        <div class="incident-map-row">
            <label>Name <input class="bos-input" name="name" maxlength="40" value="${escapeHTML(item.name)}" required></label>
            <label>Status <select class="bos-input" name="status">${incidentMapStatusOptions(item.status)}</select></label>
        </div>
        <label>Zuständig (Drohne / Trupp)
            <input class="bos-input" name="assignee" maxlength="80" value="${escapeHTML(item.assignee)}" placeholder="z. B. Drohne 1">
        </label>
        <label>Notiz
            <input class="bos-input" name="note" maxlength="300" value="${escapeHTML(item.note)}">
        </label>
        <div class="incident-map-row">
            <button class="bos-button bos-button-small bos-button-green" type="submit">Speichern</button>
            <button class="bos-button bos-button-small" type="button" onclick="incidentMapSelectItem(null)">Schließen</button>
            <button class="bos-button bos-button-small app-logout" type="button"
                onclick="incidentMapDeleteItem(${Number(item.id)})">Löschen</button>
        </div>
        <small class="incident-map-hint">Zuletzt geändert von ${escapeHTML(item.updated_by)}</small>
    </form>`;
}

function renderIncidentMapPanel() {
    const panel = incidentMapPanel();
    if (!panel) {
        return;
    }
    if (incidentMap.guest) {
        panel.hidden = !incidentMap.data;
    } else {
        panel.hidden = false;
    }
    const running = [...incidentMap.incidents];
    if (incidentMap.data && !running.some(item => item.id === incidentMap.data.incident_id)) {
        // Gewählter Einsatz ist bereits beendet: trotzdem auswählbar lassen.
        running.push({id: incidentMap.data.incident_id, keyword: incidentMap.data.keyword, code: incidentMap.data.code});
    }
    const title = incidentMap.data
        ? `${incidentMap.data.exercise ? "ÜBUNG · " : ""}${escapeHTML(incidentMap.data.keyword || "Einsatz")} · ${escapeHTML(incidentMap.data.code)}`
        : "Kein Einsatz gewählt";
    const selector = incidentMap.guest ? "" : `
        <select class="bos-input" aria-label="Einsatz für die Karte" onchange="selectIncidentMap(this.value)">
            <option value="">– kein Einsatz –</option>
            ${running.map(item => `<option value="${Number(item.id)}" ${item.id === incidentMap.selectedId ? "selected" : ""}>
                ${escapeHTML(item.keyword || item.title || "Einsatz")} · ${escapeHTML(item.code)}</option>`).join("")}
        </select>`;
    const focused = panel.contains(document.activeElement) &&
        ["INPUT", "SELECT", "TEXTAREA"].includes(document.activeElement.tagName);
    if (focused && incidentMap.selectedItem && !incidentMap.forceRender) {
        // Laufende Eingabe nicht durch den Abgleich überschreiben.
        return;
    }
    incidentMap.forceRender = false;
    panel.innerHTML = `
        <summary><span class="incident-map-dot"></span>Einsatzkarte<small>${title}</small></summary>
        <div class="incident-map-body">
            ${selector}
            ${incidentMap.message ? `<p class="incident-map-message ${incidentMap.error ? "is-error" : ""}">${escapeHTML(incidentMap.message)}</p>` : ""}
            ${incidentMap.data ? incidentMapSummary() : (running.length || incidentMap.guest ? "" : '<p class="incident-map-hint">Kein laufender Einsatz.</p>')}
            ${incidentMap.data ? incidentMapItemHTML() || incidentMapToolsHTML() : ""}
            ${incidentMap.data && !incidentMap.canEdit && !incidentMap.selectedItem
                ? '<p class="incident-map-hint">Quadrant antippen für Details.</p>' : ""}
        </div>`;
}

function setIncidentMapMessage(message, error = false) {
    incidentMap.message = message;
    incidentMap.error = error;
    incidentMap.forceRender = true;
    renderIncidentMapPanel();
    if (message && !error) {
        window.setTimeout(() => {
            if (incidentMap.message === message) {
                setIncidentMapMessage("");
            }
        }, 4000);
    }
}

// ----------------------------------------------------------
// Laden und Abgleich
// ----------------------------------------------------------

async function loadIncidentMapList() {
    if (incidentMap.guest) {
        return;
    }
    try {
        const data = await incidentMapFetch("/api/incidents");
        incidentMap.incidents = data.incidents.filter(item => item.status === "running");
    } catch (error) {
        incidentMap.incidents = [];
    }
    const stored = Number(incidentMapStorage());
    if (!incidentMap.selectedId) {
        const known = incidentMap.incidents.find(item => item.id === stored);
        const only = incidentMap.incidents.length === 1 ? incidentMap.incidents[0] : null;
        const pick = known || only;
        if (pick) {
            await selectIncidentMap(pick.id);
            return;
        }
    }
    renderIncidentMapPanel();
}

function applyIncidentMapState(state) {
    incidentMap.revision = state.revision;
    if (state.changed === false) {
        return;
    }
    incidentMap.data = state;
    incidentMap.canEdit = Boolean(state.can_edit) && state.status !== "closed";
    if (incidentMap.selectedItem && !state.items.some(item => item.id === incidentMap.selectedItem)) {
        incidentMap.selectedItem = null;
    }
    incidentMapRenderItems();
    incidentMapFit();
    renderIncidentMapPanel();
}

async function pollIncidentMap() {
    window.clearTimeout(incidentMap.pollTimer);
    // Nur die jüngste Abfragekette läuft weiter (z. B. nach Einsatzwechsel).
    const generation = ++incidentMap.pollGeneration;
    if ((incidentMap.selectedId || incidentMap.guest) && incidentMapVisible()) {
        try {
            const since = incidentMap.revision === null ? "" : `?since=${incidentMap.revision}`;
            const state = await incidentMapFetch(incidentMapUrl() + since);
            if (generation !== incidentMap.pollGeneration) {
                return;
            }
            applyIncidentMapState(state);
        } catch (error) {
            if (generation !== incidentMap.pollGeneration) {
                return;
            }
            if (error.status === 404 || error.status === 403) {
                if (incidentMap.guest) {
                    incidentMap.data = null;
                    renderIncidentMapPanel();
                    return;
                }
                selectIncidentMap("");
            }
        }
    }
    incidentMap.pollTimer = window.setTimeout(pollIncidentMap, INCIDENT_MAP_POLL_MS);
}

async function selectIncidentMap(value) {
    const id = Number(value) || null;
    incidentMapCancel(false);
    incidentMap.selectedId = id;
    incidentMap.selectedItem = null;
    incidentMap.revision = null;
    incidentMap.data = null;
    incidentMap.fitted = null;
    incidentMapStorage(id);
    incidentMapRenderItems();
    incidentMap.forceRender = true;
    renderIncidentMapPanel();
    if (id) {
        await pollIncidentMap();
    }
}

// Aus der Einsatzseite: Karte mit diesem Einsatz öffnen.
function openIncidentMap(id) {
    incidentMapStorage(id);
    if (incidentMap.map) {
        selectIncidentMap(id);
    }
    if (typeof showPage === "function") {
        showPage("map");
    }
}

// ----------------------------------------------------------
// Zeichnen und Bearbeiten
// ----------------------------------------------------------

function incidentMapStart(mode) {
    incidentMap.mode = mode;
    incidentMap.draft = [];
    incidentMap.gridCorners = null;
    incidentMap.selectedItem = null;
    incidentMap.map.getCanvas().style.cursor = "crosshair";
    incidentMap.map.doubleClickZoom.disable();
    incidentMapRenderItems();
    incidentMapRenderDraft();
    incidentMap.forceRender = true;
    renderIncidentMapPanel();
}

function incidentMapCancel(render = true) {
    incidentMap.mode = null;
    incidentMap.draft = [];
    incidentMap.gridCorners = null;
    if (incidentMap.map) {
        incidentMap.map.getCanvas().style.cursor = "";
        incidentMap.map.doubleClickZoom.enable();
        incidentMapRenderDraft();
    }
    if (render) {
        incidentMap.forceRender = true;
        renderIncidentMapPanel();
    }
}

function incidentMapUndo() {
    incidentMap.draft.pop();
    incidentMapRenderDraft();
    incidentMap.forceRender = true;
    renderIncidentMapPanel();
}

async function incidentMapSend(path, method, body, message) {
    try {
        const state = await incidentMapFetch(incidentMapUrl(path), {method, body});
        applyIncidentMapState({...state, changed: true});
        setIncidentMapMessage(message);
        return true;
    } catch (error) {
        setIncidentMapMessage(error.message, true);
        return false;
    }
}

async function incidentMapClick(event) {
    const point = [event.lngLat.lng, event.lngLat.lat];
    if (incidentMap.mode === "position") {
        incidentMapCancel(false);
        await incidentMapSend("/position", "PUT",
            {latitude: point[1], longitude: point[0]}, "Einsatzort gesetzt.");
        return;
    }
    if (incidentMap.mode === "polygon") {
        incidentMap.draft.push(point);
        incidentMapRenderDraft();
        const name = document.getElementById("incident-polygon-name")?.value ?? "";
        incidentMap.forceRender = true;
        renderIncidentMapPanel();
        const input = document.getElementById("incident-polygon-name");
        if (input) {
            input.value = name;
        }
        return;
    }
    if (incidentMap.mode === "grid") {
        if (!incidentMap.draft.length) {
            incidentMap.draft = [point];
        } else if (!incidentMap.gridCorners) {
            incidentMap.gridCorners = [incidentMap.draft[0], point];
        }
        incidentMap.forceRender = true;
        renderIncidentMapPanel();
        incidentMapRenderDraft();
        return;
    }
    if (incidentMapHitsOverlay(event.point)) {
        // Wasserentnahmestelle angetippt: deren Popup hat Vorrang.
        return;
    }
    const hit = incidentMap.map.queryRenderedFeatures(event.point, {layers: ["incident-items-fill"]})[0];
    incidentMapSelectItem(hit ? Number(hit.properties.id) : null);
}

function incidentMapDrawing() {
    return Boolean(incidentMap.mode);
}

function incidentMapHitsOverlay(point) {
    const m = incidentMap.map;
    const layers = (window.OpenBosStream?.mapOverlays || [])
        .map(overlay => overlay.id)
        .filter(id => m.getLayer(id));
    return layers.length > 0 && m.queryRenderedFeatures(point, {layers}).length > 0;
}

// Gehört ein Klick der Einsatzkarte (Zeichnen oder Quadrant)?
function incidentMapClaimsClick(event) {
    if (incidentMap.mode) {
        return true;
    }
    const m = incidentMap.map;
    if (!m || !m.getLayer("incident-items-fill")) {
        return false;
    }
    return m.queryRenderedFeatures(event.point, {layers: ["incident-items-fill"]}).length > 0;
}

function incidentMapSelectItem(id) {
    incidentMap.selectedItem = id;
    incidentMapRenderItems();
    incidentMap.forceRender = true;
    renderIncidentMapPanel();
    if (id) {
        const panel = incidentMapPanel();
        if (panel) {
            panel.open = true;
        }
    }
}

async function incidentMapCreateGrid(event) {
    event.preventDefault();
    const [first, second] = incidentMap.gridCorners;
    const body = {
        west: Math.min(first[0], second[0]),
        east: Math.max(first[0], second[0]),
        south: Math.min(first[1], second[1]),
        north: Math.max(first[1], second[1]),
        rows: Number(document.getElementById("incident-grid-rows").value),
        columns: Number(document.getElementById("incident-grid-columns").value),
        prefix: document.getElementById("incident-grid-prefix").value,
    };
    if (await incidentMapSend("/grid", "POST", body, "Raster angelegt.")) {
        incidentMapCancel();
    }
}

async function incidentMapFinishPolygon(event) {
    event.preventDefault();
    if (incidentMap.draft.length < 3) {
        return;
    }
    const name = document.getElementById("incident-polygon-name").value;
    const ring = [...incidentMap.draft, incidentMap.draft[0]];
    if (await incidentMapSend("/items", "POST",
        {name, geometry: {type: "Polygon", coordinates: [ring]}}, `Quadrant ${name} angelegt.`)) {
        incidentMapCancel();
    }
}

async function incidentMapSaveItem(event, id) {
    event.preventDefault();
    const data = Object.fromEntries(new FormData(event.target));
    await incidentMapSend(`/items/${id}`, "PATCH", data, "Gespeichert.");
}

async function incidentMapDeleteItem(id) {
    const item = (incidentMap.data?.items ?? []).find(entry => entry.id === id);
    if (!window.confirm(`Quadrant ${item?.name ?? ""} löschen?`)) {
        return;
    }
    incidentMap.selectedItem = null;
    await incidentMapSend(`/items/${id}`, "DELETE", undefined, "Quadrant gelöscht.");
}

// ----------------------------------------------------------
// Start (wird von map.js nach dem Laden der Karte aufgerufen)
// ----------------------------------------------------------

function initIncidentMap(mapInstance) {
    incidentMap.map = mapInstance;
    incidentMap.guest = window.currentUser?.role === "guest";
    incidentMapEnsureLayers();
    // Nach einem Wechsel der Grundkarte fehlen ggf. die eigenen Quellen.
    mapInstance.on("styledata", () => {
        if (!mapInstance.getSource("incident-items")) {
            incidentMapEnsureLayers();
            incidentMapRenderItems();
        }
    });
    mapInstance.on("click", incidentMapClick);
    mapInstance.on("mousemove", event => {
        if (incidentMap.mode === "polygon" || (incidentMap.mode === "grid" && !incidentMap.gridCorners)) {
            incidentMapRenderDraft([event.lngLat.lng, event.lngLat.lat]);
        }
    });
    mapInstance.on("mouseenter", "incident-items-fill", () => {
        if (!incidentMap.mode) {
            mapInstance.getCanvas().style.cursor = "pointer";
        }
    });
    mapInstance.on("mouseleave", "incident-items-fill", () => {
        if (!incidentMap.mode) {
            mapInstance.getCanvas().style.cursor = "";
        }
    });
    renderIncidentMapPanel();
    if (incidentMap.guest) {
        pollIncidentMap();
        return;
    }
    const stored = Number(incidentMapStorage());
    if (stored) {
        incidentMap.selectedId = stored;
    }
    loadIncidentMapList().then(() => {
        if (incidentMap.selectedId && !incidentMap.data) {
            pollIncidentMap();
        }
    });
    incidentMap.listTimer = window.setInterval(() => {
        if (incidentMapVisible()) {
            loadIncidentMapList();
        }
    }, INCIDENT_MAP_LIST_MS);
}
