"use strict";

// ==========================================================
// Drohnen und Personen auf der Karte
// ==========================================================
// Mit gewähltem Einsatz: dessen Drohnen mit Flugspur und geteilte Standorte.
// Ohne Einsatz: alle gerade sendenden Drohnen, die das Konto sehen darf.

const DRONE_MAP_POLL_MS = 2000;
const LOCATION_SEND_MS = 10000;

const droneMap = {
    map: null,
    incidentId: null,
    after: 0,
    tracks: {},
    drones: [],
    persons: [],
    markers: {},
    sharing: null,   // {incidentId, watch, timer, position}
    message: "",
};

function droneMapEnsureLayers() {
    const m = droneMap.map;
    try {
        if (!m.getSource("drone-tracks")) {
            m.addSource("drone-tracks", {type: "geojson", data: {type: "FeatureCollection", features: []}});
        }
        if (!m.getLayer("drone-tracks-line")) {
            m.addLayer({
                id: "drone-tracks-line",
                type: "line",
                source: "drone-tracks",
                layout: {"line-cap": "round", "line-join": "round"},
                paint: {"line-color": "#c92835", "line-width": 3, "line-opacity": 0.75},
            });
        }
    } catch (error) {
        console.debug("Drohnenebene noch nicht bereit:", error);
    }
}

function droneMapRenderTracks() {
    droneMapEnsureLayers();
    droneMap.map.getSource("drone-tracks")?.setData({
        type: "FeatureCollection",
        features: Object.values(droneMap.tracks).filter(points => points.length > 1).map(points => ({
            type: "Feature",
            properties: {},
            geometry: {type: "LineString", coordinates: points},
        })),
    });
}

function droneValues(state) {
    return [
        state.elevation !== undefined ? `${Math.round(state.elevation)} m` : "",
        state.battery !== undefined ? `Akku ${state.battery} %` : "",
    ].filter(Boolean).join(" · ");
}

// Setzt, verschiebt und entfernt die Marker anhand eines Schlüssels.
function droneMapRenderMarkers() {
    const wanted = new Map();
    droneMap.drones.forEach(drone => {
        const state = drone.state || {};
        if (state.online && state.latitude !== undefined) {
            wanted.set(`drone:${drone.serial}`, {
                lngLat: [state.longitude, state.latitude],
                kind: "drone",
                heading: state.heading,
                label: drone.name,
                detail: droneValues(state),
            });
        }
        if (drone.controller) {
            wanted.set(`controller:${drone.serial}`, {
                lngLat: [drone.controller.longitude, drone.controller.latitude],
                kind: "controller",
                label: `Pilot · ${drone.name}`,
            });
        }
    });
    droneMap.persons.forEach(person => wanted.set(`person:${person.name}`, {
        lngLat: [person.longitude, person.latitude],
        kind: "person",
        label: person.name,
    }));
    Object.keys(droneMap.markers).filter(key => !wanted.has(key)).forEach(key => {
        droneMap.markers[key].remove();
        delete droneMap.markers[key];
    });
    wanted.forEach((item, key) => {
        let marker = droneMap.markers[key];
        if (!marker) {
            const element = document.createElement("div");
            element.className = `map-unit is-${item.kind}`;
            element.innerHTML = '<i aria-hidden="true"></i><span></span>';
            marker = droneMap.markers[key] = new maplibregl.Marker({element})
                .setLngLat(item.lngLat)
                .addTo(droneMap.map);
        }
        marker.setLngLat(item.lngLat);
        const element = marker.getElement();
        const icon = element.querySelector("i");
        icon.style.transform = item.kind === "drone" && item.heading !== undefined
            ? `rotate(${Number(item.heading)}deg)` : "";
        element.querySelector("span").textContent = item.detail ? `${item.label} · ${item.detail}` : item.label;
    });
}

function droneMapInfoHTML() {
    if (!droneMap.incidentId) {
        return "";
    }
    const rows = droneMap.drones.filter(drone => drone.active).map(drone => {
        const state = drone.state || {};
        const text = state.online
            ? [state.mode, droneValues(state)].filter(Boolean).join(" · ") || "sendet"
            : "keine Daten";
        return `<li><button class="map-unit-link" type="button" data-serial="${escapeHTML(drone.serial)}"
            onclick="droneMapFocus(this.dataset.serial)"><strong>${escapeHTML(drone.name)}</strong>
            <span>${escapeHTML(text)}</span></button></li>`;
    }).join("");
    const running = incidentMap.data?.status === "running" && !incidentMap.guest;
    const sharing = droneMap.sharing?.incidentId === droneMap.incidentId;
    return `
        ${rows ? `<ul class="map-unit-list">${rows}</ul>` : ""}
        ${running ? `<button class="bos-button bos-button-small ${sharing ? "bos-button-green" : ""}" type="button"
            onclick="toggleLocationSharing()" aria-pressed="${sharing}">
            ${sharing ? "● Standort wird geteilt – beenden" : "Meinen Standort teilen"}</button>
            ${sharing ? '<p class="incident-map-hint">Nur solange Open BOS offen und das Gerät entsperrt ist.</p>' : ""}` : ""}
        ${droneMap.message ? `<p class="incident-map-message is-error">${escapeHTML(droneMap.message)}</p>` : ""}`;
}

// Eigener Bereich im Bedienfeld der Einsatzkarte (nach jedem Neuaufbau).
function droneMapRenderInfo() {
    const root = document.getElementById("map-drone-info");
    if (root) {
        root.innerHTML = droneMapInfoHTML();
    }
}

function droneMapFocus(serial) {
    const state = droneMap.drones.find(drone => drone.serial === serial)?.state;
    const track = droneMap.tracks[serial];
    const center = state?.latitude !== undefined ? [state.longitude, state.latitude] : track?.[track.length - 1];
    if (center) {
        droneMap.map.flyTo({center, zoom: Math.max(droneMap.map.getZoom(), 16)});
    }
}

function droneMapReset(incidentId) {
    droneMap.incidentId = incidentId;
    droneMap.after = 0;
    droneMap.tracks = {};
    droneMap.drones = [];
    droneMap.persons = [];
    if (droneMap.sharing && droneMap.sharing.incidentId !== incidentId && incidentId) {
        stopLocationSharing();
    }
    droneMapRender();
}

function droneMapRender() {
    droneMapRenderTracks();
    droneMapRenderMarkers();
    droneMapRenderInfo();
}

async function droneMapPoll() {
    const incidentId = incidentMap.guest ? incidentMap.data?.incident_id ?? null : incidentMap.selectedId;
    if (incidentId !== droneMap.incidentId) {
        droneMapReset(incidentId);
    }
    if (incidentMapVisible()) {
        try {
            if (incidentId) {
                const url = incidentMap.guest ? "/guest/incident-positions" : `/api/incidents/${incidentId}/positions`;
                const data = await incidentMapFetch(`${url}?after=${droneMap.after}`);
                if (incidentId === droneMap.incidentId) {
                    droneMap.after = data.last;
                    data.drones.forEach(drone => {
                        droneMap.tracks[drone.serial] = (droneMap.tracks[drone.serial] || []).concat(drone.track);
                    });
                    droneMap.drones = data.drones;
                    droneMap.persons = data.persons;
                    droneMapRender();
                }
            } else if (!incidentMap.guest) {
                const data = await incidentMapFetch("/api/dji/live");
                if (!droneMap.incidentId) {
                    droneMap.drones = data.drones;
                    droneMapRender();
                }
            }
        } catch (error) {
            console.debug("Positionen:", error);
        }
    }
    window.setTimeout(droneMapPoll, DRONE_MAP_POLL_MS);
}

// ----------------------------------------------------------
// Eigenen Standort teilen
// ----------------------------------------------------------

function sendLocation() {
    const sharing = droneMap.sharing;
    if (!sharing?.position) {
        return;
    }
    const {latitude, longitude, accuracy} = sharing.position;
    incidentMapFetch(`/api/incidents/${sharing.incidentId}/location`,
        {method: "PUT", body: {latitude, longitude, accuracy}})
        .catch(error => {
            droneMap.message = `Standort nicht gesendet: ${error.message}`;
            droneMapRenderInfo();
        });
}

function stopLocationSharing() {
    const sharing = droneMap.sharing;
    if (!sharing) {
        return;
    }
    droneMap.sharing = null;
    navigator.geolocation.clearWatch(sharing.watch);
    window.clearInterval(sharing.timer);
    incidentMapFetch(`/api/incidents/${sharing.incidentId}/location`, {method: "DELETE"})
        .catch(error => console.debug("Standort beenden:", error));
    droneMapRenderInfo();
}

function toggleLocationSharing() {
    droneMap.message = "";
    if (droneMap.sharing) {
        stopLocationSharing();
        return;
    }
    if (!navigator.geolocation) {
        droneMap.message = "Dieses Gerät stellt keinen Standort bereit.";
        droneMapRenderInfo();
        return;
    }
    const sharing = droneMap.sharing = {incidentId: droneMap.incidentId, position: null};
    sharing.watch = navigator.geolocation.watchPosition(result => {
        const first = !sharing.position;
        sharing.position = result.coords;
        if (first) {
            sendLocation();
        }
    }, error => {
        droneMap.message = error.code === error.PERMISSION_DENIED
            ? "Standortzugriff wurde im Browser abgelehnt." : "Standort derzeit nicht verfügbar.";
        if (error.code === error.PERMISSION_DENIED) {
            stopLocationSharing();
        }
        droneMapRenderInfo();
    }, {enableHighAccuracy: true, maximumAge: 5000});
    sharing.timer = window.setInterval(sendLocation, LOCATION_SEND_MS);
    droneMapRenderInfo();
}

function initDroneMap(mapInstance) {
    droneMap.map = mapInstance;
    droneMapEnsureLayers();
    mapInstance.on("styledata", () => {
        if (!mapInstance.getSource("drone-tracks")) {
            droneMapRenderTracks();
        }
    });
    droneMapPoll();
}
