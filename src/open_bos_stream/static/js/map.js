"use strict";

let map = null;
let mapInitPromise = null;
// Aktive Grundkarte und die zu ihr gehörenden Quellen und Ebenen.
let mapBase = null;

function setBaseMapStatus(text) {
    const status = document.getElementById("map-basemap-status");
    if (status) {
        status.textContent = text;
        status.hidden = !text;
    }
}

const AERIAL_STATUS_MS = 20000;

// Hinweis unter der Karte, solange das Luftbild gewählt ist und der
// Landesdienst nicht antwortet.
async function updateAerialNotice() {
    const notice = document.getElementById("map-aerial-notice");
    if (!notice) {
        return;
    }
    if (mapBase?.id !== "aerial") {
        notice.hidden = true;
        return;
    }
    if (document.hidden) {
        return;
    }
    try {
        const response = await fetch("/api/map/aerial/status", {cache: "no-store"});
        if (response.ok) {
            const status = await response.json();
            notice.hidden = status.available || mapBase?.id !== "aerial";
        }
    } catch (error) {
        console.warn("Status des Luftbilds nicht abrufbar:", error);
    }
}

function renderBaseMapControls(info, base) {
    const box = document.getElementById("map-basemap-list");
    if (!box) {
        return;
    }
    if (info.options.length < 2) {
        box.hidden = true;
        return;
    }
    box.hidden = false;
    box.innerHTML = `
        <strong class="map-basemap-title">Grundkarte</strong>
        ${info.options.map(option => `
            <label>
                <input type="radio" name="map-basemap"
                    value="${escapeHTML(option.id)}"
                    ${option.id === base.id ? "checked" : ""}>
                ${escapeHTML(option.label)}
            </label>
        `).join("")}
        <small id="map-basemap-status" class="map-basemap-status" hidden></small>
    `;
    if (base.fallback) {
        setBaseMapStatus(
            "Online-Karte nicht erreichbar – die Offline-Karte wird angezeigt."
        );
    }
    box.querySelectorAll('input[name="map-basemap"]').forEach(input => {
        input.addEventListener("change", () => switchBaseMap(input.value));
    });
}

async function switchBaseMap(id) {
    if (!map || !mapBase || id === mapBase.id) {
        return;
    }
    const info = await loadBaseMaps();
    setBaseMapStatus("Grundkarte wird geladen …");
    try {
        const base = await loadBaseStyle(id);
        mapBase.ids = applyBaseStyle(map, base, mapBase.ids);
        mapBase.id = base.id;
        applyBaseZoomRange(map, info, base.id);
        storeBaseMapChoice(id);
        updateAerialNotice();
        setBaseMapStatus(
            base.fallback
                ? "Online-Karte nicht erreichbar – die Offline-Karte wird angezeigt."
                : ""
        );
        const checked = document.querySelector(
            `input[name="map-basemap"][value="${base.id}"]`
        );
        if (checked) {
            checked.checked = true;
        }
    } catch (error) {
        console.error("Grundkarte konnte nicht geladen werden:", error);
        setBaseMapStatus(`Grundkarte nicht verfügbar: ${error.message}`);
        const previous = document.querySelector(
            `input[name="map-basemap"][value="${mapBase.id}"]`
        );
        if (previous) {
            previous.checked = true;
        }
    }
}

function showMissingMap(mapDirectory) {
    const emptyState =
        document.getElementById("map-empty-state");
    const path =
        document.getElementById("map-empty-path");
    const mapElement =
        document.getElementById("map");
    const toolbar =
        document.querySelector("#map-container .map-toolbar");
    const layerControl =
        document.getElementById("map-layer-control");

    if (path) {
        const directory = String(
            mapDirectory || "/opt/open-bos-stream/mapdata"
        ).replace(/\/+$/, "");
        path.textContent = `${directory}/stade.mbtiles`;
    }
    if (emptyState) {
        emptyState.hidden = false;
    }
    if (mapElement) {
        mapElement.hidden = true;
    }
    if (toolbar) {
        toolbar.hidden = true;
    }
    if (layerControl) {
        layerControl.hidden = true;
    }
}



function overlayGroups(overlays) {
    const groups = window.OpenBosStream?.mapOverlayGroups ?? [];
    // Ebenen ohne Gruppe erscheinen als eigene Gruppe mit ihrem Titel.
    const known = new Set(groups.map(group => group.id));
    const extra = overlays
        .filter(overlay => !known.has(overlay.group))
        .map(overlay => ({id: overlay.id, title: overlay.title, members: [overlay]}));
    return [
        ...groups.map(group => ({
            ...group,
            members: overlays.filter(overlay => overlay.group === group.id),
        })),
        ...extra,
    ].filter(group => group.members.length);
}

function overlayLegendColor(overlay) {
    const color = overlay.paint?.["circle-color"];
    return typeof color === "string" ? color : "#888888";
}

function bindOverlayGroupToggle(group) {
    const toggle = document.getElementById(`layer-group-${group.id}`);
    if (!toggle) {
        return;
    }
    toggle.addEventListener("change", () => {
        for (const overlay of group.members) {
            if (map?.getLayer(overlay.id)) {
                map.setLayoutProperty(
                    overlay.id,
                    "visibility",
                    toggle.checked ? "visible" : "none"
                );
            }
        }
    });
}

function createOverlayControls(overlays) {
    const container = document.getElementById("map-layer-list");
    if (!container) {
        console.warn("Layer-Control Container fehlt.");
        return [];
    }

    const groups = overlayGroups(overlays);
    container.innerHTML = groups.map(group => {
        const legend = group.members.length > 1
            ? `<ul class="map-layer-legend">
                ${group.members.map(overlay => `
                    <li id="layer-legend-${escapeHTML(overlay.id)}">
                        <span class="map-layer-swatch"
                            style="--swatch: ${escapeHTML(overlayLegendColor(overlay))}"></span>
                        ${escapeHTML(overlay.title)}
                        ${overlay.legendHint
                            ? `<small>${escapeHTML(overlay.legendHint)}</small>`
                            : ""}
                    </li>
                `).join("")}
               </ul>`
            : "";
        return `
            <div class="map-layer-group">
                <label>
                    <input id="layer-group-${escapeHTML(group.id)}" type="checkbox" checked>
                    <span>
                        ${escapeHTML(group.title)}
                        ${group.description
                            ? `<small>${escapeHTML(group.description)}</small>`
                            : ""}
                    </span>
                </label>
                ${legend}
            </div>
        `;
    }).join("");
    return groups;
}

async function createMap() {
    const container = document.getElementById("map-container");

    if (!container) {
        throw new Error(
            "Der Kartencontainer #map-container wurde nicht gefunden."
        );
    }

    await maplibreReady();

    const info = await loadBaseMaps();
    if (!info.options.length) {
        // Weder Online-Karten noch eine Offline-Karte verfügbar.
        showMissingMap(info.offline_path);
        return;
    }

    const base = await loadBaseStyle(preferredBaseMap(info));
    const center = info.center;

    map = new maplibregl.Map({
        container: "map",
        style: base.style,
        center: center.slice(0, 2),
        zoom: center[2] ?? 12,
        maxZoom: 19,
        attributionControl: false
    });
    applyBaseZoomRange(map, info, base.id);
    mapBase = {id: base.id, ids: baseStyleIds(base.style)};
    renderBaseMapControls(info, base);
    window.setInterval(updateAerialNotice, AERIAL_STATUS_MS);
    // Auch kurz nach dem Nachladen von Kacheln prüfen.
    let aerialNoticeTimer = null;
    map.on("moveend", () => {
        window.clearTimeout(aerialNoticeTimer);
        aerialNoticeTimer = window.setTimeout(updateAerialNotice, 3000);
    });
    map.once("load", () => window.setTimeout(updateAerialNotice, 3000));

    bindFullscreenButton();

    map.addControl(
        new maplibregl.NavigationControl(),
        "top-right"
    );

    map.addControl(
        new maplibregl.AttributionControl({
            compact: true,
            customAttribution:
                "Wasserentnahmestellen: © OpenStreetMap-Mitwirkende"
        })
    );

    map.on("error", event => {
        console.error(
            "MapLibre-Fehler:",
            event.error ?? event
        );
    });

    map.once("load", async () => {
        collapseMapAttribution(map);
        try {

            const overlays =
                window.OpenBosStream?.mapOverlays;


            if (!Array.isArray(overlays)) {
                throw new Error(
                    "Die Overlay-Registry wurde nicht geladen."
                );
            }


            const overlayGroupList = createOverlayControls(
                overlays
            );


            for (const overlay of overlays) {

                await addOverlayLayer(
                    map,
                    overlay
                );

            }


            for (const group of overlayGroupList) {
                bindOverlayGroupToggle(group);
            }


            // Drohnen-Geozonen liegen unter den Wasserentnahmestellen.
            try {
                await addDipulLayers(
                    map,
                    overlays[0]?.id
                );
            } catch (error) {
                console.error(
                    "Drohnen-Geozonen konnten nicht geladen werden:",
                    error
                );
            }


            // Regenradar über den Geozonen, unter den Wasserentnahmestellen.
            if (typeof addWeatherLayers === "function") {
                try {
                    await addWeatherLayers(
                        map,
                        overlays[0]?.id
                    );
                } catch (error) {
                    console.warn(
                        "Wetter auf der Karte nicht verfügbar:",
                        error
                    );
                }
            }


            // Einsatzkarte (Einsatzort, Quadranten) liegt über allem.
            if (typeof initIncidentMap === "function") {
                try {
                    initIncidentMap(map);
                } catch (error) {
                    console.error("Einsatzkarte nicht verfügbar:", error);
                }
            }


            requestAnimationFrame(() => {
                map.resize();
            });


        } catch (error) {

            console.error(
                "Kartenlayer konnten nicht geladen werden:",
                error
            );

        }
    });
}

function resizeMap() {
    if (!map) {
        return;
    }

    /*
     * Der Kartenbereich wurde von showPage() gerade erst sichtbar gemacht.
     * Zwei Render-Zyklen geben dem Browser Zeit, das Layout vollständig
     * zu berechnen, bevor MapLibre seine Größe neu bestimmt.
     */
    requestAnimationFrame(() => {
        requestAnimationFrame(() => {
            map.resize();
        });
    });
}


async function initMapPage() {
    const container = document.getElementById("map-container");

    if (!container) {
        console.error(
            "Karte konnte nicht initialisiert werden: " +
            "#map-container wurde nicht gefunden."
        );
        return;
    }

    /*
     * Die Karte existiert bereits. Bei einem erneuten Aufruf der
     * Kartenseite darf keine zweite MapLibre-Instanz entstehen.
     */
    if (map) {
        resizeMap();
        return;
    }

    /*
     * Eine Initialisierung läuft bereits. Das kann beispielsweise
     * durch schnelle Seitenwechsel oder mehrere Aufrufe von showPage()
     * passieren.
     */
    if (mapInitPromise) {
        try {
            await mapInitPromise;
            resizeMap();
        } catch (error) {
            console.error(
                "Die laufende Karteninitialisierung ist fehlgeschlagen:",
                error
            );
        }

        return;
    }

    mapInitPromise = createMap();

    try {
        await mapInitPromise;
        resizeMap();
    } catch (error) {
        console.error(
            "Karte konnte nicht initialisiert werden:",
            error
        );

        /*
         * Nach einem Fehler darf ein späterer Aufruf erneut versuchen,
         * die Karte zu initialisieren.
         */
        map = null;
    } finally {
        mapInitPromise = null;
    }
}
