/*
 * Open BOS Stream
 *
 * Wetter auf der Karte: DWD-Niederschlagsradar als Ebene (mit Vorhersage
 * bis 90 Minuten) und das Wetter der Kartenmitte in einem Feld unter der Karte.
 */

"use strict";

const RADAR_SOURCE_ID = "weather-radar";
const RADAR_REFRESH_MS = 5 * 60 * 1000;
const MAP_WEATHER_MIN_ZOOM = 7;
const MAP_WEATHER_DEBOUNCE_MS = 1200;

let radarConfig = null;
let radarOffset = 0;
let radarRefreshTimer = null;
let mapWeatherTimer = null;
let mapWeatherRequest = 0;

function radarTileUrl(offset) {
    // Fünf-Minuten-Takt im Pfad, damit Browser neue Radarbilder laden.
    const bucket = Math.floor(Date.now() / RADAR_REFRESH_MS);
    return `/api/weather/radar/tiles/${offset}/{z}/{x}/{y}.png?t=${bucket}`;
}

function setRadarTiles(mapInstance) {
    const source = mapInstance.getSource(RADAR_SOURCE_ID);
    if (source?.setTiles) {
        source.setTiles([radarTileUrl(radarOffset)]);
    }
}

function renderRadarControls(mapInstance) {
    const list = document.getElementById("map-layer-list");
    if (!list || document.getElementById("weather-radar-controls")) {
        return;
    }
    const box = document.createElement("div");
    box.id = "weather-radar-controls";
    box.className = "map-weather-controls";
    box.innerHTML = `
        <label>
            <input id="weather-radar-toggle" type="checkbox">
            <strong>Niederschlagsradar (DWD)</strong>
        </label>
        <div class="map-weather-radar-options" hidden>
            <label>
                Zeitpunkt
                <select id="weather-radar-offset" class="bos-input">
                    ${radarConfig.offsets.map(item => `
                        <option value="${Number(item.minutes)}">
                            ${escapeHTML(item.label)}
                        </option>
                    `).join("")}
                </select>
            </label>
            <label>
                Deckkraft
                <input id="weather-radar-opacity" type="range"
                    min="20" max="100" step="10" value="70">
            </label>
            <small>${escapeHTML(radarConfig.attribution)} ·
                Vorhersage aus dem Radarbild, ohne Gewähr.</small>
        </div>
    `;
    list.after(box);

    const toggle = box.querySelector("#weather-radar-toggle");
    const options = box.querySelector(".map-weather-radar-options");
    toggle.addEventListener("change", () => {
        options.hidden = !toggle.checked;
        mapInstance.setLayoutProperty(
            RADAR_SOURCE_ID,
            "visibility",
            toggle.checked ? "visible" : "none"
        );
        if (toggle.checked) {
            setRadarTiles(mapInstance);
        }
    });
    box.querySelector("#weather-radar-offset").addEventListener(
        "change",
        event => {
            radarOffset = Number(event.target.value);
            setRadarTiles(mapInstance);
        }
    );
    box.querySelector("#weather-radar-opacity").addEventListener(
        "input",
        event => {
            mapInstance.setPaintProperty(
                RADAR_SOURCE_ID,
                "raster-opacity",
                Number(event.target.value) / 100
            );
        }
    );
}

async function addWeatherLayers(mapInstance, beforeLayerId = undefined) {
    const response = await fetch("/api/weather/radar", {cache: "no-store"});
    if (!response.ok) {
        throw new Error(`Radar nicht verfügbar: HTTP ${response.status}`);
    }
    radarConfig = await response.json();
    if (!radarConfig.enabled) {
        return;
    }

    mapInstance.addSource(RADAR_SOURCE_ID, {
        type: "raster",
        tiles: [radarTileUrl(radarOffset)],
        tileSize: 256,
        minzoom: radarConfig.min_zoom,
        maxzoom: radarConfig.max_zoom,
        attribution: radarConfig.attribution,
    });
    mapInstance.addLayer(
        {
            id: RADAR_SOURCE_ID,
            type: "raster",
            source: RADAR_SOURCE_ID,
            layout: {visibility: "none"},
            paint: {"raster-opacity": 0.7, "raster-fade-duration": 0},
        },
        beforeLayerId && mapInstance.getLayer(beforeLayerId)
            ? beforeLayerId
            : undefined
    );

    renderRadarControls(mapInstance);
    window.clearInterval(radarRefreshTimer);
    radarRefreshTimer = window.setInterval(() => {
        if (
            !document.hidden &&
            mapInstance.getLayoutProperty(RADAR_SOURCE_ID, "visibility") === "visible"
        ) {
            setRadarTiles(mapInstance);
        }
    }, RADAR_REFRESH_MS);

    startMapWeather(mapInstance);
}

// ----------------------------------------------------------
// Wetteranzeige für die Kartenmitte
// ----------------------------------------------------------

// Das Feld bleibt nach dem Start sichtbar, damit die Karte darüber nicht
// bei jedem Zoomen ihre Höhe ändert.
function showMapWeatherNote(chip, text) {
    chip.dataset.level = "unknown";
    chip.title = "";
    chip.innerHTML = `
        <span class="map-weather-dot" aria-hidden="true"></span>
        <span><small>${escapeHTML(text)}</small></span>
    `;
    chip.hidden = false;
}

function formatMapWeather(report) {
    const current = report.current ?? {};
    const now = report.forecast?.[0] ?? {};
    const number = value => (
        value === null || value === undefined
            ? "–"
            : Number(value).toLocaleString("de-DE", {maximumFractionDigits: 1})
    );
    const wind = number(now.wind_speed_120m_ms ?? current.wind_speed_ms);
    const gust = number(current.wind_gust_ms ?? now.wind_gust_ms);
    const rain = number(current.precipitation_mm_h ?? now.precipitation_mm_h);
    const temperature = number(current.temperature_c ?? now.temperature_c);
    return `
        <span class="map-weather-dot" aria-hidden="true"></span>
        <span>
            <strong>Wind 120 m ${escapeHTML(wind)} m/s · Böen ${escapeHTML(gust)} m/s</strong>
            <small>${escapeHTML(temperature)} °C · ${escapeHTML(rain)} mm/h ·
                ${escapeHTML(report.assessment?.summary ?? "")}</small>
        </span>
    `;
}

async function updateMapWeather(mapInstance) {
    const chip = document.getElementById("map-weather-chip");
    if (!chip) {
        return;
    }
    if (mapInstance.getZoom() < MAP_WEATHER_MIN_ZOOM) {
        // Auch eine noch laufende Abfrage verwerfen.
        mapWeatherRequest += 1;
        showMapWeatherNote(chip, "Für das Wetter näher heranzoomen.");
        return;
    }
    const center = mapInstance.getCenter();
    const request = ++mapWeatherRequest;
    try {
        const params = new URLSearchParams({
            lat: center.lat.toFixed(2),
            lon: center.lng.toFixed(2),
        });
        const response = await fetch(`/api/weather?${params}`);
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        const report = await response.json();
        if (request !== mapWeatherRequest) {
            return;
        }
        chip.dataset.level = report.assessment?.level ?? "unknown";
        chip.title = (report.assessment?.reasons ?? [])
            .map(reason => reason.text)
            .join("\n") || "Wetter für die Kartenmitte";
        chip.innerHTML = formatMapWeather(report);
        chip.hidden = false;
    } catch (error) {
        console.warn("Wetter für die Kartenmitte nicht verfügbar:", error);
        if (request === mapWeatherRequest) {
            showMapWeatherNote(chip, "Wetter derzeit nicht verfügbar.");
        }
    }
}

function startMapWeather(mapInstance) {
    updateMapWeather(mapInstance);
    mapInstance.on("moveend", () => {
        window.clearTimeout(mapWeatherTimer);
        mapWeatherTimer = window.setTimeout(
            () => updateMapWeather(mapInstance),
            MAP_WEATHER_DEBOUNCE_MS
        );
    });
}
