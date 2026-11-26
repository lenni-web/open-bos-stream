// ==========================================================
// Wetterseite: Niederschlagsradar mit Zeitleiste
//
// Jeder Zeitpunkt der Zeitleiste ist eine eigene Radarebene. Alle Ebenen
// laden im Hintergrund; sichtbar ist nur die gewählte. So läuft die
// Animation ohne Nachladen und Flackern.
// ==========================================================

"use strict";

const WEATHER_RADAR_FRAME_PREFIX = "weather-radar-frame-";
const WEATHER_RADAR_OPACITY = 0.75;
const WEATHER_RADAR_FRAME_MS = 650;
const WEATHER_RADAR_END_PAUSE_MS = 1500;
const WEATHER_RADAR_REFRESH_MS = 5 * 60 * 1000;
const WEATHER_RADAR_MAX_ZOOM = 11;

// Farbskala des DWD-Produkts RV (mm/h).
const WEATHER_RADAR_LEGEND = [
    ["#33ffff", "0,1"],
    ["#1acc9a", "0,2"],
    ["#019934", "0,4"],
    ["#4db31b", "1"],
    ["#99cc01", "2"],
    ["#cce601", "3"],
    ["#ffff01", "5"],
    ["#ffc401", "7,5"],
    ["#ff8901", "10"],
    ["#ff4501", "15"],
    ["#fe0000", "30"],
    ["#e5004c", "45"],
    ["#cc0098", "75"],
    ["#6600cb", "100"],
    ["#0000fe", "150"],
];

const weatherRadar = {
    map: null,
    frames: [],
    index: 0,
    playing: false,
    timer: null,
    refreshTimer: null,
    active: false,
    loadedAt: 0,
};

function radarElement(id) {
    return document.getElementById(`weather-radar-${id}`);
}

function radarFrameId(index) {
    return `${WEATHER_RADAR_FRAME_PREFIX}${index}`;
}

function radarRelative(offset) {
    if (offset === 0) {
        return "Jetzt";
    }
    const sign = offset > 0 ? "+" : "−";
    const minutes = Math.abs(offset);
    // Bis 90 Minuten in Minuten, darüber in Stunden (kurz für die Achse).
    const text = minutes <= 90 && minutes % 60 !== 0
        ? `${minutes} min`
        : minutes % 60 === 0
            ? `${minutes / 60} h`
            : `${Math.floor(minutes / 60)} h ${minutes % 60} min`;
    return `${sign}${text}`;
}

function radarFrameLabel(frame) {
    const clock = new Date(frame.time).toLocaleTimeString("de-DE", {
        hour: "2-digit",
        minute: "2-digit",
    });
    const kind = frame.offset > 0 ? " · Vorhersage" : "";
    return `${clock} Uhr · ${radarRelative(frame.offset)}${kind}`;
}

function renderRadarLegend() {
    const list = radarElement("legend");
    if (!list || list.childElementCount) {
        return;
    }
    list.innerHTML = WEATHER_RADAR_LEGEND
        .map(([color, label]) => `
            <li><span style="background:${color}"></span>${escapeHTML(label)}</li>
        `)
        .join("");
}

function setRadarStatus(text) {
    const status = radarElement("status");
    if (status) {
        status.textContent = text;
    }
}

function loadedRadarFrames() {
    const map = weatherRadar.map;
    return weatherRadar.frames.filter((_, index) => {
        const id = radarFrameId(index);
        return map.getSource(id) && map.isSourceLoaded(id);
    }).length;
}

function updateRadarProgress() {
    const total = weatherRadar.frames.length;
    const done = loadedRadarFrames();
    setRadarStatus(
        done >= total
            ? `${total} Radarbilder · alle ${weatherRadar.stepMinutes ?? 10} Minuten`
            : `Radarbilder werden geladen … ${done} von ${total}`
    );
}

function showRadarFrame(index) {
    const map = weatherRadar.map;
    if (!map || !weatherRadar.frames.length) {
        return;
    }
    const next = Math.max(0, Math.min(index, weatherRadar.frames.length - 1));
    const previousId = radarFrameId(weatherRadar.index);
    if (map.getLayer(previousId)) {
        map.setPaintProperty(previousId, "raster-opacity", 0);
    }
    weatherRadar.index = next;
    const id = radarFrameId(next);
    if (map.getLayer(id)) {
        map.setPaintProperty(id, "raster-opacity", WEATHER_RADAR_OPACITY);
    } else {
        // Noch nicht angelegt: sofort und sichtbar hinzufügen.
        weatherRadar.addFrame?.(next);
    }
    const frame = weatherRadar.frames[next];
    radarElement("slider").value = String(next);
    const output = radarElement("time");
    output.textContent = radarFrameLabel(frame);
    output.dataset.kind = frame.offset > 0
        ? "forecast"
        : frame.offset === 0 ? "now" : "past";
}

function positionRadarTicks() {
    const frames = weatherRadar.frames;
    const ticks = document.querySelector(".weather-radar-ticks");
    if (!ticks || frames.length < 2) {
        return;
    }
    const nowIndex = frames.findIndex(frame => frame.offset === 0);
    const nowTick = ticks.querySelector('[data-tick="now"]');
    nowTick.style.left = `${(nowIndex / (frames.length - 1)) * 100}%`;
    ticks.querySelector('[data-tick="start"]').textContent =
        radarRelative(frames[0].offset);
    ticks.querySelector('[data-tick="end"]').textContent =
        radarRelative(frames[frames.length - 1].offset);
}

function removeRadarFrames() {
    const map = weatherRadar.map;
    weatherRadar.frames.forEach((_, index) => {
        const id = radarFrameId(index);
        if (map.getLayer(id)) {
            map.removeLayer(id);
        }
        if (map.getSource(id)) {
            map.removeSource(id);
        }
    });
}

function addRadarFrames(data) {
    const map = weatherRadar.map;
    const keepOffset = weatherRadar.frames[weatherRadar.index]?.offset ?? 0;
    removeRadarFrames();
    weatherRadar.frames = data.frames;
    weatherRadar.stepMinutes = data.step_minutes;

    const addFrame = index => {
        const frame = data.frames[index];
        const id = radarFrameId(index);
        if (map.getSource(id)) {
            return;
        }
        map.addSource(id, {
            type: "raster",
            tiles: [
                `/api/weather/radar/time/${frame.stamp}/{z}/{x}/{y}.png`,
            ],
            tileSize: 256,
            minzoom: data.min_zoom,
            maxzoom: data.max_zoom,
        });
        // Spätere Zeitpunkte über frühere legen, Reihenfolge bleibt stabil.
        const before = data.frames
            .map((_, other) => radarFrameId(other))
            .slice(index + 1)
            .find(other => map.getLayer(other));
        map.addLayer({
            id,
            type: "raster",
            source: id,
            paint: {
                "raster-opacity": index === weatherRadar.index
                    ? WEATHER_RADAR_OPACITY
                    : 0,
                "raster-fade-duration": 0,
            },
        }, before);
    };

    weatherRadar.addFrame = addFrame;

    // Zuerst das aktuelle Bild, danach die übrigen von „jetzt“ nach außen.
    const nowIndex = Math.max(
        0,
        data.frames.findIndex(frame => frame.offset === 0)
    );
    const sameOffset = data.frames.findIndex(frame => frame.offset === keepOffset);
    weatherRadar.index = sameOffset >= 0 ? sameOffset : nowIndex;
    addFrame(weatherRadar.index);
    const order = data.frames
        .map((_, index) => index)
        .filter(index => index !== weatherRadar.index)
        .sort((a, b) => Math.abs(a - nowIndex) - Math.abs(b - nowIndex));
    map.once("idle", () => order.forEach(addFrame));

    const slider = radarElement("slider");
    slider.max = String(data.frames.length - 1);
    slider.disabled = false;
    radarElement("play").disabled = false;
    positionRadarTicks();

    showRadarFrame(weatherRadar.index);
    weatherRadar.loadedAt = Date.now();
    updateRadarProgress();
}

async function loadRadarFrames() {
    const response = await fetch("/api/weather/radar/frames", {cache: "no-store"});
    if (response.status === 404) {
        throw new Error("Das Wettermodul ist ausgeschaltet.");
    }
    if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
    }
    return await response.json();
}

function stopRadarAnimation() {
    weatherRadar.playing = false;
    window.clearTimeout(weatherRadar.timer);
    const button = radarElement("play");
    if (button) {
        button.setAttribute("aria-pressed", "false");
        button.querySelector("[data-play-label]").textContent = "▶ Abspielen";
    }
}

function radarAnimationStep() {
    if (!weatherRadar.playing) {
        return;
    }
    const last = weatherRadar.frames.length - 1;
    const next = weatherRadar.index >= last ? 0 : weatherRadar.index + 1;
    showRadarFrame(next);
    weatherRadar.timer = window.setTimeout(
        radarAnimationStep,
        next === last ? WEATHER_RADAR_END_PAUSE_MS : WEATHER_RADAR_FRAME_MS
    );
}

function startRadarAnimation() {
    if (!weatherRadar.frames.length) {
        return;
    }
    weatherRadar.playing = true;
    const button = radarElement("play");
    button.setAttribute("aria-pressed", "true");
    button.querySelector("[data-play-label]").textContent = "❚❚ Anhalten";
    // Am Ende angekommen: von vorn beginnen.
    if (weatherRadar.index >= weatherRadar.frames.length - 1) {
        showRadarFrame(0);
    }
    weatherRadar.timer = window.setTimeout(
        radarAnimationStep,
        WEATHER_RADAR_FRAME_MS
    );
}

function bindRadarControls() {
    radarElement("slider").addEventListener("input", event => {
        stopRadarAnimation();
        showRadarFrame(Number(event.target.value));
    });
    radarElement("play").addEventListener("click", () => {
        if (weatherRadar.playing) {
            stopRadarAnimation();
        } else {
            startRadarAnimation();
        }
    });
}

async function createRadarMap() {
    const container = radarElement("map");
    if (!container) {
        return;
    }
    await maplibreReady();
    renderRadarLegend();
    bindRadarControls();

    const data = await loadRadarFrames();
    let style;
    try {
        // Für das Radar die Straßenkarte statt des Luftbilds verwenden.
        const info = await loadBaseMaps();
        const preferred = baseMapOption(info, "online") ? "online" : info.default;
        if (!preferred) {
            throw new Error("Keine Grundkarte verfügbar.");
        }
        style = (await loadBaseStyle(preferred)).style;
    } catch (error) {
        // Ohne Grundkarte bleibt das Radar auf neutralem Hintergrund nutzbar.
        style = {
            version: 8,
            sources: {},
            layers: [{
                id: "background",
                type: "background",
                paint: {"background-color": "#dfe5ec"},
            }],
        };
    }

    const location = data.location ?? {};
    const map = new maplibregl.Map({
        container,
        style,
        center: [location.longitude ?? 9.53, location.latitude ?? 53.56],
        zoom: 8,
        minZoom: 5,
        maxZoom: WEATHER_RADAR_MAX_ZOOM,
        attributionControl: false,
    });
    weatherRadar.map = map;
    map.addControl(new maplibregl.NavigationControl({showCompass: false}), "top-right");
    map.addControl(
        new maplibregl.AttributionControl({
            compact: true,
            customAttribution: "Niederschlagsradar: Deutscher Wetterdienst",
        })
    );

    let progressPending = false;
    const scheduleProgress = () => {
        if (progressPending) {
            return;
        }
        progressPending = true;
        window.setTimeout(() => {
            progressPending = false;
            updateRadarProgress();
        }, 250);
    };
    map.on("sourcedata", event => {
        if (event.sourceId?.startsWith(WEATHER_RADAR_FRAME_PREFIX)) {
            scheduleProgress();
        }
    });
    map.on("idle", scheduleProgress);

    await new Promise(resolve => map.once("load", resolve));
    collapseMapAttribution(map);

    if (location.latitude !== undefined) {
        const marker = document.createElement("div");
        marker.className = "weather-radar-marker";
        marker.title = location.name ?? "Wetter-Standort";
        new maplibregl.Marker({element: marker})
            .setLngLat([location.longitude, location.latitude])
            .addTo(map);
    }

    addRadarFrames(data);
}

async function refreshRadarIfStale() {
    if (
        !weatherRadar.map ||
        Date.now() - weatherRadar.loadedAt < WEATHER_RADAR_REFRESH_MS
    ) {
        return;
    }
    try {
        const data = await loadRadarFrames();
        if (data.frames[0]?.stamp !== weatherRadar.frames[0]?.stamp) {
            const wasPlaying = weatherRadar.playing;
            stopRadarAnimation();
            addRadarFrames(data);
            if (wasPlaying) {
                startRadarAnimation();
            }
        } else {
            weatherRadar.loadedAt = Date.now();
        }
    } catch (error) {
        console.warn("Radar konnte nicht aktualisiert werden:", error);
    }
}

async function setWeatherPageActive(active) {
    weatherRadar.active = active;
    if (!active) {
        stopRadarAnimation();
        window.clearInterval(weatherRadar.refreshTimer);
        return;
    }
    if (typeof loadWeatherCard === "function") {
        loadWeatherCard();
    }
    try {
        if (!weatherRadar.map) {
            await createRadarMap();
        } else {
            weatherRadar.map.resize();
            await refreshRadarIfStale();
        }
    } catch (error) {
        setRadarStatus(`Radar nicht verfügbar: ${error.message}`);
        console.warn("Radar nicht verfügbar:", error);
    }
    window.clearInterval(weatherRadar.refreshTimer);
    weatherRadar.refreshTimer = window.setInterval(() => {
        if (weatherRadar.active && !document.hidden) {
            refreshRadarIfStale();
        }
    }, 60 * 1000);
}

document.addEventListener("visibilitychange", () => {
    if (document.hidden) {
        stopRadarAnimation();
    }
});
