/*
 * Open BOS Stream
 *
 * Grundkarten: basemap.de (online), Luftbild Niedersachsen (online) und
 * die Offline-Karte aus MBTiles. Alle Online-Abrufe laufen über den Server.
 * Ist der Online-Dienst nicht erreichbar, wird auf die Offline-Karte
 * zurückgegriffen, sofern eine installiert ist.
 */

"use strict";

const BASE_MAP_STORAGE_KEY = "openBosBaseMap";
const AERIAL_SOURCE_ID = "aerial-photo";

let baseMapsInfo = null;

function maplibreReady() {
    if (window.maplibregl) {
        return Promise.resolve(window.maplibregl);
    }
    return new Promise((resolve, reject) => {
        const timeout = window.setTimeout(
            () => reject(new Error("MapLibre GL JS wurde nicht geladen.")),
            15000
        );
        document.addEventListener(
            "open-bos:maplibre-ready",
            () => {
                window.clearTimeout(timeout);
                resolve(window.maplibregl);
            },
            {once: true}
        );
    });
}

function readBaseMapChoice() {
    try {
        return localStorage.getItem(BASE_MAP_STORAGE_KEY);
    } catch (error) {
        return null;
    }
}

function storeBaseMapChoice(id) {
    try {
        localStorage.setItem(BASE_MAP_STORAGE_KEY, id);
    } catch (error) {
        // Ohne Speicher gilt die Wahl nur bis zum Neuladen.
    }
}

async function loadBaseMaps() {
    if (baseMapsInfo) {
        return baseMapsInfo;
    }
    const response = await fetch("/api/map/basemaps", {cache: "no-store"});
    if (!response.ok) {
        throw new Error(`Grundkarten nicht verfügbar: HTTP ${response.status}`);
    }
    baseMapsInfo = await response.json();
    return baseMapsInfo;
}

function baseMapOption(info, id) {
    return info.options.find(option => option.id === id) ?? null;
}

function preferredBaseMap(info) {
    const stored = readBaseMapChoice();
    if (stored && baseMapOption(info, stored)) {
        return stored;
    }
    return info.default;
}

/*
 * Der Server liefert relative Pfade (oder ältere absolute mit http://).
 * MapLibre braucht vollständige Adressen; Protokoll und Host kommen daher
 * aus der Seite selbst, damit es auch hinter HTTPS passt.
 */
function absolutizeMapUrl(url) {
    if (typeof url !== "string") {
        return url;
    }
    if (url.startsWith("/")) {
        return `${window.location.origin}${url}`;
    }
    try {
        const parsed = new URL(url);
        if (
            parsed.host === window.location.host &&
            parsed.protocol !== window.location.protocol
        ) {
            parsed.protocol = window.location.protocol;
            return parsed.toString()
                .replaceAll("%7B", "{")
                .replaceAll("%7D", "}");
        }
    } catch (error) {
        // Keine gültige URL: unverändert lassen.
    }
    return url;
}

function absolutizeStyle(style) {
    if (style.glyphs) {
        style.glyphs = absolutizeMapUrl(style.glyphs);
    }
    if (typeof style.sprite === "string") {
        style.sprite = absolutizeMapUrl(style.sprite);
    } else if (Array.isArray(style.sprite)) {
        style.sprite = style.sprite.map(item => ({
            ...item,
            url: absolutizeMapUrl(item.url),
        }));
    }
    for (const source of Object.values(style.sources ?? {})) {
        if (Array.isArray(source.tiles)) {
            source.tiles = source.tiles.map(absolutizeMapUrl);
        }
        if (source.url) {
            source.url = absolutizeMapUrl(source.url);
        }
    }
    return style;
}

async function fetchStyle(url) {
    const response = await fetch(url, {cache: "no-store"});
    if (!response.ok) {
        throw new Error(`Kartenstil nicht verfügbar: HTTP ${response.status}`);
    }
    return await response.json();
}

function prefersDarkMap() {
    return document.documentElement.dataset.colorScheme === "dark";
}

async function buildBaseStyle(id, info) {
    if (id === "offline") {
        return await fetchStyle("/api/map/style");
    }
    const variant = id === "online" && prefersDarkMap() ? "drk" : "col";
    const style = await fetchStyle(`/api/map/basemap/style/${variant}.json`);
    if (id === "aerial") {
        const option = baseMapOption(info, "aerial") ?? {};
        style.sources[AERIAL_SOURCE_ID] = {
            type: "raster",
            tiles: ["/api/map/aerial/tiles/{z}/{x}/{y}.webp"],
            tileSize: 256,
            minzoom: option.min_zoom ?? 8,
            maxzoom: option.max_zoom ?? 19,
            bounds: option.bounds,
            attribution: option.attribution,
        };
        // Luftbild über den Flächen, Beschriftungen bleiben lesbar darüber.
        const firstLabel = style.layers.findIndex(layer => layer.type === "symbol");
        style.layers.splice(
            firstLabel >= 0 ? firstLabel : style.layers.length,
            0,
            {
                id: AERIAL_SOURCE_ID,
                type: "raster",
                source: AERIAL_SOURCE_ID,
                paint: {"raster-fade-duration": 0},
            }
        );
    }
    return style;
}

/*
 * Lädt die gewünschte Grundkarte. Schlägt eine Online-Karte fehl, folgt
 * die Offline-Karte (falls vorhanden) mit einem Hinweis.
 */
async function loadBaseStyle(id) {
    const info = await loadBaseMaps();
    try {
        return {
            id,
            style: absolutizeStyle(await buildBaseStyle(id, info)),
            fallback: false,
        };
    } catch (error) {
        if (id !== "offline" && baseMapOption(info, "offline")) {
            console.warn("Online-Karte nicht erreichbar, nutze Offline-Karte:", error);
            return {
                id: "offline",
                style: absolutizeStyle(await buildBaseStyle("offline", info)),
                fallback: true,
                error,
            };
        }
        throw error;
    }
}

/* Merkt sich, welche Quellen und Ebenen zur Grundkarte gehören. */
function baseStyleIds(style) {
    return {
        sources: new Set(Object.keys(style.sources ?? {})),
        layers: new Set((style.layers ?? []).map(layer => layer.id)),
    };
}

/*
 * Grundkarte wechseln, ohne eigene Ebenen (Wasserstellen, Geozonen, Radar)
 * zu verlieren: Sie werden aus dem bisherigen Stil übernommen.
 */
function applyBaseStyle(mapInstance, base, previousIds) {
    mapInstance.setStyle(base.style, {
        diff: false,
        transformStyle: (previous, next) => {
            if (!previous) {
                return next;
            }
            const sources = {...next.sources};
            for (const [key, source] of Object.entries(previous.sources)) {
                if (!previousIds.sources.has(key) && !(key in sources)) {
                    sources[key] = source;
                }
            }
            const layers = [
                ...next.layers,
                ...previous.layers.filter(layer => !previousIds.layers.has(layer.id)),
            ];
            return {...next, sources, layers};
        },
    });
    return baseStyleIds(base.style);
}

function applyBaseZoomRange(mapInstance, info, id) {
    const option = baseMapOption(info, id) ?? {};
    const minZoom = id === "offline" ? Number(option.min_zoom ?? 0) : 0;
    const maxZoom = Math.max(18, Number(option.max_zoom ?? 19));
    mapInstance.setMinZoom(minZoom);
    mapInstance.setMaxZoom(maxZoom);
}

/*
 * Die Quellenangaben sind lang (Grundkarte, Luftbild, Geozonen, OSM) und
 * würden die Karte unten verdecken. Eingeklappt bleiben sie über das
 * i-Symbol erreichbar.
 */
function collapseMapAttribution(mapInstance) {
    const attribution = mapInstance
        .getContainer()
        .querySelector(".maplibregl-ctrl-attrib");
    if (attribution) {
        attribution.classList.remove("maplibregl-compact-show");
        attribution.removeAttribute("open");
    }
}
