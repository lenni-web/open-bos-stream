/*
 * Open BOS Stream
 *
 * Karten-Overlay-Registry und Verwaltung
 *
 * Jedes Overlay definiert:
 * - Datenquelle
 * - Darstellung
 * - Sichtbarkeit
 * - UI-Bezeichnung
 *
 * Neue BOS-Kartenebenen werden hier registriert.
 *
 * Zoomstufen: Hydranten ab 14 (sehr viele Punkte), alle übrigen
 * Wasserentnahmestellen einheitlich ab 13.
 */

"use strict";


window.OpenBosStream =
    window.OpenBosStream || {};

const UNKNOWN_TANK_LABEL = "Lagertank (Inhalt unbekannt)";

window.OpenBosStream.mapOverlays = [

        {
            id: "hydranten",

            group: "abhaengig",

            title: "Hydranten",

            category: "infrastructure",

            type: "circle",

            icon: "🚒",

            endpoint: "/api/map/layers/hydranten",

            defaultVisible: true,

            minzoom: 14,

            paint: {
                "circle-radius": 5,
                "circle-color": "#d32f2f",
                "circle-stroke-width": 1.5,
                "circle-stroke-color": "#ffffff"
            }
        },

        {
            id: "brunnen",

            group: "unabhaengig",

            title: "Brunnen",

            category: "infrastructure",

            type: "circle",

            icon: "🪣",

            endpoint: "/api/map/layers/brunnen",

            defaultVisible: true,

            minzoom: 13,

            paint: {
                "circle-radius": [
                    "interpolate",
                    ["linear"],
                    ["zoom"],
                    13, 2,
                    16, 4,
                    18, 7
                ],
                "circle-color": "#8d6e63",
                "circle-stroke-width": 1.5,
                "circle-stroke-color": "#ffffff"
            }
        },

        {
            id: "saugstellen",

            group: "unabhaengig",

            title: "Saugstellen",

            category: "infrastructure",

            type: "circle",

            icon: "🌊",

            endpoint: "/api/map/layers/saugstellen",

            defaultVisible: true,

            minzoom: 13,

            paint: {
                "circle-radius": [
                    "interpolate",
                    ["linear"],
                    ["zoom"],
                    13, 2,
                    16, 4,
                    18, 7
                ],
                "circle-color": "#009688",
                "circle-stroke-width": 1.5,
                "circle-stroke-color": "#ffffff"
            }
        },

        {
            id: "offene_wasserentnahmestellen",

            group: "unabhaengig",

            title: "Offene Wasserentnahmestellen",

            category: "infrastructure",

            type: "circle",

            icon: "🏞",

            endpoint: "/api/map/layers/offene_wasserentnahmestellen",

            defaultVisible: true,

            minzoom: 13,

            paint: {
                "circle-radius": [
                    "interpolate",
                    ["linear"],
                    ["zoom"],
                    13, 3,
                    16, 5,
                    18, 8
                ],
                "circle-color": "#2196f3",
                "circle-stroke-width": 1.5,
                "circle-stroke-color": "#ffffff"
            }
        },

        {
            id: "loeschwasserbehaelter_teiche",

            group: "unabhaengig",

            title: "Behälter / Teiche",

            category: "infrastructure",

            type: "circle",

            icon: "🏞",

            endpoint: "/api/map/layers/loeschwasserbehaelter_teiche",

            defaultVisible: true,

            minzoom: 13,

            paint: {
                "circle-radius": [
                    "interpolate",
                    ["linear"],
                    ["zoom"],
                    13, 3,
                    16, 5,
                    18, 8
                ],
                "circle-color": "#3f51b5",
                "circle-stroke-width": 1.5,
                "circle-stroke-color": "#ffffff"
            }
        },

        {
            id: "sonstige_wasserstellen",

            group: "unabhaengig",

            title: "Sonstige Wasserstellen",

            category: "infrastructure",

            type: "circle",

            icon: "💦",

            endpoint: "/api/map/layers/sonstige_wasserstellen",

            defaultVisible: true,

            minzoom: 13,

            paint: {
                "circle-radius": [
                    "interpolate",
                    ["linear"],
                    ["zoom"],
                    13, 2,
                    16, 4,
                    18, 7
                ],
                "circle-color": "#9c27b0",
                // Lagertanks ohne Inhaltsangabe nur als Ring: erkennbar,
                // aber nicht gleichwertig zu verlässlichen Wasserstellen.
                "circle-opacity": [
                    "case",
                    ["==", ["get", "type_de"], UNKNOWN_TANK_LABEL],
                    0.12,
                    1
                ],
                "circle-stroke-width": 1.5,
                "circle-stroke-color": [
                    "case",
                    ["==", ["get", "type_de"], UNKNOWN_TANK_LABEL],
                    "#9c27b0",
                    "#ffffff"
                ]
            },

            legendHint: "Ring: Lagertank, Inhalt unbekannt"
        },

];

/*
 * Kartenmenü: Gruppen nach der feuerwehrüblichen Einteilung der
 * Löschwasserversorgung. Ein Schalter blendet alle Ebenen der Gruppe ein
 * oder aus; die Farben unterscheiden die Arten innerhalb der Gruppe.
 */
window.OpenBosStream.mapOverlayGroups = [

        {
            id: "abhaengig",

            title: "Hydranten",

            description: "Abhängige Löschwasserversorgung (Trinkwassernetz)"
        },

        {
            id: "unabhaengig",

            title: "Unabhängige Löschwasserstellen",

            description: "Saugstellen, Behälter/Teiche, Brunnen und weitere"
        },

];

function formatPopupLabel(key) {

    const labels = {

        type: "Typ",
        type_de: "Typ",

        ref: "Bezeichnung",

        operator: "Betreiber",

        fire_hydrant_diameter: "Nennweite",

        fire_hydrant_position: "Kennzeichnung",

        fire_hydrant_type: "Hydrantentyp",

        access: "Zugang",

        note: "Hinweis"

    };

    return labels[key] ?? key;
}

function formatPopupValue(key, value) {

    if (value === null || value === undefined) {
        return "";
    }

    switch (key) {

        case "fire_hydrant_diameter":
            return `DN ${value}`;

        case "fire_hydrant_position":

            return ({
                green: "Grün",
                blue: "Blau",
                yellow: "Gelb",
                red: "Rot"
            })[value] ?? value;

        case "fire_hydrant_type":

            return ({
                pillar: "Überflurhydrant",
                underground: "Unterflurhydrant",
                wall: "Wandhydrant"
            })[value] ?? value;

        case "access":

            return ({
                yes: "Ja",
                no: "Nein",
                private: "Privat",
                permissive: "Eingeschränkt"
            })[value] ?? value;

        case "diameter":
            return `DN ${value}`;

        case "capacity": {

            const number =
                Number(value);

            if (Number.isFinite(number)) {
                return `${number.toLocaleString("de-DE")} l`;
            }

            return value;
        }

        default:
            return value;
    }
}

async function addOverlayLayer(
    mapInstance,
    overlay
) {
    if (
        mapInstance.getLayer(
            overlay.id
        )
    ) {

        console.warn(
            "Overlay existiert bereits:",
            overlay.id
        );

        return;

    }

    const response = await fetch(
        overlay.endpoint,
        {
            cache: "no-store"
        }
    );


    if (!response.ok) {

        throw new Error(
            `Overlay ${overlay.id} konnte nicht geladen werden`
        );

    }


    const data =
        await response.json();


    // Ebenen ohne Daten erscheinen nicht in der Legende.
    if (!data.features?.length) {
        document.getElementById(`layer-legend-${overlay.id}`)?.remove();
        return;
    }



    mapInstance.addSource(
        overlay.id,
        {
            type: "geojson",
            data: data
        }
    );


    const layerDefinition = {

        id:
            overlay.id,

        type:
            overlay.type || "circle",

        source:
            overlay.id,

        paint:
            overlay.paint || {}

    };


    if (overlay.layout) {

        layerDefinition.layout =
            overlay.layout;

    }


    if (overlay.minzoom) {

        layerDefinition.minzoom =
            overlay.minzoom;

    }


    if (overlay.maxzoom) {

        layerDefinition.maxzoom =
            overlay.maxzoom;

    }

    mapInstance.addLayer(
        layerDefinition
    );

    mapInstance.on("mouseenter", overlay.id, () => {
        mapInstance.getCanvas().style.cursor = "pointer";
    });

    mapInstance.on("mouseleave", overlay.id, () => {
        mapInstance.getCanvas().style.cursor = "";
    });

    mapInstance.on("click", overlay.id, event => {
        // Beim Zeichnen auf der Einsatzkarte kein Popup öffnen.
        if (typeof incidentMapDrawing === "function" && incidentMapDrawing()) {
            return;
        }

        const feature = event.features?.[0];

        if (!feature) {
            return;
        }

    const p = feature.properties;

    const labels = {

        type: "Typ",
        type_de: "Typ",

        ref: "Bezeichnung",

        operator: "Betreiber",

        diameter: "Durchmesser",

        fire_hydrant_diameter: "Nennweite",

        fire_hydrant_position: "Kennzeichnung",

        fire_hydrant_type: "Hydrantentyp",

        access: "Zugang",

        diameter: "Durchmesser",

        capacity: "Volumen",

        access_status: "Zugänglichkeit",

        water_source: "Wasserquelle",

        capacity: "Volumen",

        note: "Hinweis"

    };

    const ignored = new Set([
        "all_tags",
        "lat",
        "lon",
        "osm_id",
        "osm_type"
    ]);

    // Werte stammen aus OpenStreetMap und werden nie als HTML eingesetzt.
    let html = `<strong>${escapeHTML(overlay.title)}</strong><table>`;

    for (const [key, value] of Object.entries(p)) {

        if (ignored.has(key)) {
            continue;
        }

        if (value === null || value === "") {
            continue;
        }

    const displayValue =
        formatPopupValue(key, value);

    html += `
        <tr>
            <td><strong>${escapeHTML(formatPopupLabel(key))}</strong></td>
            <td>${escapeHTML(displayValue)}</td>
        </tr>
    `;
    }

    html += "</table>";

    new maplibregl.Popup()
        .setLngLat(event.lngLat)
        .setHTML(html)
        .addTo(mapInstance);

    });
}
