/*
 * Open BOS Stream
 *
 * Drohnen-Geozonen der Digitalen Plattform Unbemannte Luftfahrt (dipul).
 *
 * Die Kartenbilder werden über /api/map/dipul vom eigenen Server geladen,
 * der sie eine Stunde zwischenspeichert. Die Daten stehen unter
 * CC BY-ND 4.0 und werden unverändert angezeigt.
 */

"use strict";

const DIPUL_SOURCE_PREFIX = "dipul-";

let dipulConfig = null;
let dipulUnavailable = false;

function dipulLayerId(group) {
    return `${DIPUL_SOURCE_PREFIX}${group.id}`;
}

function dipulVisibleGroups(mapInstance) {
    if (!dipulConfig) {
        return [];
    }
    return dipulConfig.groups.filter(group => {
        const id = dipulLayerId(group);
        return mapInstance.getLayer(id) &&
            mapInstance.getLayoutProperty(id, "visibility") !== "none";
    });
}

function setDipulStatus(message) {
    const status = document.getElementById("map-dipul-status");
    if (!status) {
        return;
    }
    status.textContent = message || "";
    status.hidden = !message;
}

function renderDipulAttribution(config) {
    const element = document.getElementById("map-dipul-attribution");
    if (!element) {
        return;
    }
    element.hidden = false;
    element.querySelector("[data-dipul='attribution']").textContent =
        config.attribution;
    element.querySelector("[data-dipul='license']").href =
        config.license_url;
    element.querySelector("[data-dipul='maptool']").href =
        config.map_tool_url;
}

function renderDipulControls(mapInstance, config) {
    const container = document.getElementById("map-dipul-list");
    if (!container) {
        return;
    }

    container.innerHTML = `
        <div class="map-dipul-heading">
            <label>
                <input id="dipul-toggle-all" type="checkbox">
                <strong>Drohnen-Geozonen (dipul)</strong>
            </label>
        </div>
        <div class="map-dipul-groups"></div>
    `;

    const groups = container.querySelector(".map-dipul-groups");
    const master = container.querySelector("#dipul-toggle-all");

    for (const group of config.groups) {
        const label = document.createElement("label");
        const checkbox = document.createElement("input");
        checkbox.type = "checkbox";
        checkbox.id = `dipul-toggle-${group.id}`;
        checkbox.checked = group.visible;
        checkbox.dataset.group = group.id;
        label.appendChild(checkbox);
        label.appendChild(document.createTextNode(" " + group.title));
        groups.appendChild(label);

        checkbox.addEventListener("change", () => {
            setDipulGroupVisible(mapInstance, group, checkbox.checked);
            updateDipulMaster(container);
        });
    }

    master.addEventListener("change", () => {
        for (const group of config.groups) {
            const checkbox = document.getElementById(
                `dipul-toggle-${group.id}`
            );
            checkbox.checked = master.checked;
            setDipulGroupVisible(mapInstance, group, master.checked);
        }
        updateDipulMaster(container);
    });

    updateDipulMaster(container);
}

function updateDipulMaster(container) {
    const master = container.querySelector("#dipul-toggle-all");
    const boxes = [
        ...container.querySelectorAll(".map-dipul-groups input"),
    ];
    const checked = boxes.filter(box => box.checked).length;
    master.checked = checked === boxes.length;
    master.indeterminate = checked > 0 && checked < boxes.length;
}

function setDipulGroupVisible(mapInstance, group, visible) {
    const id = dipulLayerId(group);
    if (!mapInstance.getLayer(id)) {
        return;
    }
    mapInstance.setLayoutProperty(
        id,
        "visibility",
        visible ? "visible" : "none"
    );
}

function formatDipulZones(zones) {
    if (zones.length === 0) {
        return "<p>Keine Geozone der eingeblendeten Ebenen an dieser Stelle.</p>";
    }

    const items = zones.map(zone => {
        const limits = [zone.lower_limit, zone.upper_limit]
            .filter(Boolean);
        const height = limits.length === 2
            ? `${limits[0]} bis ${limits[1]}`
            : limits.length === 1
                ? `ab ${limits[0]}`
                : "";
        return `
            <li>
                <strong>${escapeHTML(zone.name)}</strong>
                <span>${escapeHTML(zone.type)}</span>
                ${height ? `<small>Höhe: ${escapeHTML(height)}</small>` : ""}
                ${zone.legal_ref
                    ? `<small>Grundlage: ${escapeHTML(zone.legal_ref)}</small>`
                    : ""}
            </li>
        `;
    });
    return `<ul class="map-dipul-zones">${items.join("")}</ul>`;
}

function bindDipulClick(mapInstance) {
    mapInstance.on("click", async event => {
        const groups = dipulVisibleGroups(mapInstance);
        if (groups.length === 0) {
            return;
        }

        // Klicks auf Wasserentnahmestellen öffnen deren eigenes Popup.
        const overlayLayers = (window.OpenBosStream?.mapOverlays || [])
            .map(overlay => overlay.id)
            .filter(id => mapInstance.getLayer(id));
        if (
            overlayLayers.length > 0 &&
            mapInstance.queryRenderedFeatures(
                event.point,
                {layers: overlayLayers}
            ).length > 0
        ) {
            return;
        }

        const popup = new maplibregl.Popup({maxWidth: "320px"})
            .setLngLat(event.lngLat)
            .setHTML(
                "<strong>Drohnen-Geozonen</strong>" +
                "<p>Wird abgefragt …</p>"
            )
            .addTo(mapInstance);

        const params = new URLSearchParams({
            lng: event.lngLat.lng.toFixed(6),
            lat: event.lngLat.lat.toFixed(6),
            zoom: mapInstance.getZoom().toFixed(1),
            groups: groups.map(group => group.id).join(","),
        });

        let body;
        try {
            const response = await fetch(`/api/map/dipul/info?${params}`);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            const result = await response.json();
            body = formatDipulZones(result.zones || []);
        } catch (error) {
            console.warn("dipul-Abfrage fehlgeschlagen:", error);
            body = "<p>dipul ist derzeit nicht erreichbar.</p>";
        }

        popup.setHTML(
            "<strong>Drohnen-Geozonen</strong>" +
            body +
            '<p class="map-dipul-popup-note">' +
            "Nur zur Orientierung, nicht rechtsverbindlich. " +
            `${escapeHTML(dipulConfig.attribution)}</p>`
        );
    });
}

function bindDipulErrors(mapInstance) {
    mapInstance.on("error", event => {
        if (!String(event.sourceId || "").startsWith(DIPUL_SOURCE_PREFIX)) {
            return;
        }
        if (!dipulUnavailable) {
            dipulUnavailable = true;
            setDipulStatus(
                "dipul ist derzeit nicht erreichbar – " +
                "Geozonen werden nicht oder unvollständig angezeigt."
            );
        }
    });
    mapInstance.on("data", event => {
        if (
            dipulUnavailable &&
            event.dataType === "source" &&
            event.tile &&
            String(event.sourceId || "").startsWith(DIPUL_SOURCE_PREFIX)
        ) {
            dipulUnavailable = false;
            setDipulStatus("");
        }
    });
}

async function addDipulLayers(mapInstance, beforeLayerId = undefined) {
    const response = await fetch("/api/map/dipul/layers");
    if (!response.ok) {
        throw new Error(
            `Geozonen konnten nicht geladen werden: HTTP ${response.status}`
        );
    }
    dipulConfig = await response.json();

    for (const group of dipulConfig.groups) {
        const id = dipulLayerId(group);
        mapInstance.addSource(id, {
            type: "raster",
            tiles: [`/api/map/dipul/tiles/${group.id}/{z}/{x}/{y}.png`],
            tileSize: 256,
            minzoom: 6,
            maxzoom: 19,
            attribution: dipulConfig.attribution,
        });
        mapInstance.addLayer(
            {
                id,
                type: "raster",
                source: id,
                layout: {
                    visibility: group.visible ? "visible" : "none",
                },
            },
            beforeLayerId && mapInstance.getLayer(beforeLayerId)
                ? beforeLayerId
                : undefined
        );
    }

    renderDipulControls(mapInstance, dipulConfig);
    renderDipulAttribution(dipulConfig);
    bindDipulErrors(mapInstance);
    bindDipulClick(mapInstance);
}
