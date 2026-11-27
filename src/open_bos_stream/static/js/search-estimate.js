/*
 * Open BOS Stream
 *
 * Einsatzkarte: Größe von Suchflächen und eine grobe Schätzung für
 * Flugzeit und Akkus. Rechnet nur im Browser, gespeichert werden
 * ausschließlich die eigenen Annahmen (je Gerät).
 */

"use strict";

const SEARCH_STORAGE = "openBosSearchEstimate";
// Wenden und Bahnwechsel, als Aufschlag auf die reine Bahnenzeit.
const SEARCH_TURN_FACTOR = 1.15;
// Start, Anflug und Rückflug je Akku in Minuten.
const SEARCH_TRANSIT_MINUTES = 3;

// hfov: waagerechter Bildwinkel aus den Herstellerangaben (Grad).
// minutes: vorsichtig angesetzte Flugzeit je Akku, nicht der Prospektwert.
const SEARCH_PROFILES = {
    thermal: {label: "Mavic 3T Wärmebild", hfov: 49.4, altitude: 50, speed: 5, overlap: 20, minutes: 28},
    wide: {label: "Mavic 3T Weitwinkel", hfov: 71.6, altitude: 60, speed: 7, overlap: 20, minutes: 28},
    mini3: {label: "Mini 3", hfov: 69.7, altitude: 50, speed: 5, overlap: 20, minutes: 22},
};

const SEARCH_FIELDS = {
    altitude: {label: "Höhe (m)", min: 10, max: 120},
    speed: {label: "Tempo (m/s)", min: 1, max: 15},
    overlap: {label: "Überlappung (%)", min: 0, max: 70},
    minutes: {label: "Min. je Akku", min: 5, max: 45},
};

let searchSettings = loadSearchSettings();
let searchSettingsOpen = false;

function searchDefaults(profile) {
    const key = Object.hasOwn(SEARCH_PROFILES, profile) ? profile : "thermal";
    const {altitude, speed, overlap, minutes} = SEARCH_PROFILES[key];
    return {profile: key, altitude, speed, overlap, minutes};
}

function searchClamp(field, value, fallback) {
    const {min, max} = SEARCH_FIELDS[field];
    const number = Number(value);
    return value === "" || !Number.isFinite(number) ? fallback : Math.min(max, Math.max(min, number));
}

function loadSearchSettings() {
    try {
        const stored = JSON.parse(localStorage.getItem(SEARCH_STORAGE) || "{}");
        const settings = searchDefaults(stored.profile);
        Object.keys(SEARCH_FIELDS).forEach(field => {
            settings[field] = searchClamp(field, stored[field] ?? "", settings[field]);
        });
        return settings;
    } catch (error) {
        return searchDefaults();
    }
}

function saveSearchSettings() {
    try {
        localStorage.setItem(SEARCH_STORAGE, JSON.stringify(searchSettings));
    } catch (error) {
        // Ohne Speicher gelten die Annahmen nur bis zum Neuladen.
    }
}

// Fläche eines Rings aus [Länge, Breite] in m². Ebene Näherung um die
// mittlere Breite; für Suchgebiete von wenigen Kilometern genau genug.
function searchAreaM2(ring) {
    if (!ring || ring.length < 3) {
        return 0;
    }
    const radians = Math.PI / 180;
    const radius = 6371008.8;
    const latitude = ring.reduce((sum, point) => sum + point[1], 0) / ring.length;
    const scale = Math.cos(latitude * radians);
    const [originLon, originLat] = ring[0];
    const points = ring.map(([lon, lat]) => [
        (lon - originLon) * radians * radius * scale,
        (lat - originLat) * radians * radius,
    ]);
    const twice = points.reduce((sum, [x, y], index) => {
        const [nextX, nextY] = points[(index + 1) % points.length];
        return sum + x * nextY - nextX * y;
    }, 0);
    return Math.abs(twice) / 2;
}

// Bahnenflug: Streifenbreite aus Höhe und Bildwinkel, abzüglich Überlappung.
function searchEstimate(area, settings = searchSettings) {
    const {hfov} = SEARCH_PROFILES[settings.profile];
    const swath = 2 * settings.altitude * Math.tan(hfov * Math.PI / 360);
    const spacing = swath * (1 - settings.overlap / 100);
    const minutes = area / spacing / settings.speed * SEARCH_TURN_FACTOR / 60;
    const perBattery = Math.max(1, settings.minutes - SEARCH_TRANSIT_MINUTES);
    return {swath, spacing, minutes, batteries: area > 0 ? Math.ceil(minutes / perBattery) : 0};
}

function formatSearchArea(area) {
    const format = (value, digits) => value.toLocaleString("de-DE", {maximumFractionDigits: digits});
    return area < 10000
        ? `${format(Math.round(area), 0)} m²`
        : `${format(area / 10000, area < 100000 ? 2 : 1)} ha`;
}

function formatSearchMinutes(minutes) {
    const total = Math.max(1, Math.ceil(minutes));
    return total < 60 ? `${total} min` : `${Math.floor(total / 60)} h ${total % 60} min`;
}

function searchEstimateText(area) {
    const {minutes, batteries} = searchEstimate(area);
    return `${formatSearchArea(area)} · ca. ${formatSearchMinutes(minutes)} · ` +
        `${batteries} ${batteries === 1 ? "Akku" : "Akkus"}`;
}

// Platzhalter, der sich bei geänderten Annahmen ohne Neuaufbau auffrischt.
function searchEstimateHTML(area, label = "") {
    return `<span class="incident-estimate" data-area="${Number(area)}" data-label="${escapeHTML(label)}">
        ${escapeHTML(label)}${escapeHTML(searchEstimateText(area))}</span>`;
}

function refreshSearchEstimates() {
    document.querySelectorAll(".incident-estimate[data-area]").forEach(element => {
        element.textContent = element.dataset.label + searchEstimateText(Number(element.dataset.area));
    });
    const hint = document.getElementById("incident-estimate-swath");
    if (hint) {
        hint.textContent = searchSwathText();
    }
}

function searchSwathText() {
    const {swath, spacing} = searchEstimate(0);
    return `Bildstreifen ${Math.round(swath)} m, Bahnabstand ${Math.round(spacing)} m.`;
}

function searchSettingsHTML() {
    return `<details class="incident-estimate-settings" ${searchSettingsOpen ? "open" : ""}
            ontoggle="searchSettingsOpen = this.open">
        <summary>Annahmen zur Schätzung</summary>
        <div class="incident-map-form">
            <label>Drohne / Kamera
                <select class="bos-input" onchange="chooseSearchProfile(this)">
                    ${Object.entries(SEARCH_PROFILES).map(([key, profile]) =>
                        `<option value="${key}" ${key === searchSettings.profile ? "selected" : ""}>${profile.label}</option>`
                    ).join("")}
                </select>
            </label>
            <div class="incident-map-row">
                ${Object.entries(SEARCH_FIELDS).map(([field, {label, min, max}]) =>
                    `<label>${label}<input class="bos-input" type="number" data-search-field="${field}"
                        min="${min}" max="${max}" value="${searchSettings[field]}"
                        oninput="changeSearchSetting(this)"></label>`
                ).join("")}
            </div>
            <p class="incident-map-hint"><span id="incident-estimate-swath">${searchSwathText()}</span>
                Mit 15 % für Wenden und ${SEARCH_TRANSIT_MINUTES} min je Akku für An- und Rückflug.
                Grobe Schätzung: Wind, Kälte, Bewuchs und Nachkontrollen verlängern die Suche.</p>
        </div>
    </details>`;
}

function chooseSearchProfile(select) {
    searchSettings = searchDefaults(select.value);
    select.closest("details").querySelectorAll("[data-search-field]").forEach(input => {
        input.value = searchSettings[input.dataset.searchField];
    });
    saveSearchSettings();
    refreshSearchEstimates();
}

// Während der Eingabe nicht in das Feld zurückschreiben.
function changeSearchSetting(input) {
    const field = input.dataset.searchField;
    searchSettings[field] = searchClamp(field, input.value, searchDefaults(searchSettings.profile)[field]);
    saveSearchSettings();
    refreshSearchEstimates();
}
