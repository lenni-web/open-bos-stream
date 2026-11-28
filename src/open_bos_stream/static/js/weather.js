// ==========================================================
// Wetter für den Flugbetrieb (Übersicht und Einstellungen)
// ==========================================================

const WEATHER_REFRESH_MS = 5 * 60 * 1000;
const WEATHER_LEVEL_TEXT = {
    green: "Grün",
    yellow: "Gelb",
    red: "Rot",
    unknown: "Keine Daten",
};
const WEATHER_ALERT_SEVERITY = {
    minor: "Wetterwarnung",
    moderate: "Markante Wetterwarnung",
    severe: "Unwetterwarnung",
    extreme: "Extreme Unwetterwarnung",
};

// Gewählter Wetter-Ort dieses Geräts: "auto", "device" oder ein Schlüssel
// aus der Ortsliste des Servers.
const WEATHER_PLACE_KEY = "obs-weather-place";

let weatherTimer = null;
let weatherRequest = 0;
let weatherDevicePosition = null;
let weatherPlaceChoice = null;
let weatherPlaceNote = "";

function weatherNumber(value, digits = 1) {
    if (value === null || value === undefined || Number.isNaN(Number(value))) {
        return "–";
    }
    return Number(value).toLocaleString("de-DE", {
        minimumFractionDigits: digits,
        maximumFractionDigits: digits,
    });
}

function weatherCompass(degrees) {
    if (degrees === null || degrees === undefined) {
        return "";
    }
    const names = ["N", "NO", "O", "SO", "S", "SW", "W", "NW"];
    return names[Math.round(Number(degrees) / 45) % 8];
}

function weatherClock(value) {
    if (!value) {
        return "";
    }
    // Vorhersagezeiten kommen ohne Zeitzone bereits in deutscher Zeit.
    if (/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/.test(value)) {
        return value.slice(11, 16);
    }
    const date = new Date(value);
    return Number.isNaN(date.getTime())
        ? value
        : date.toLocaleTimeString("de-DE", {hour: "2-digit", minute: "2-digit"});
}

function weatherVisibility(meters) {
    if (meters === null || meters === undefined) {
        return "–";
    }
    return meters >= 10000
        ? `${weatherNumber(meters / 1000, 0)} km`
        : meters >= 1000
            ? `${weatherNumber(meters / 1000, 1)} km`
            : `${Math.round(meters)} m`;
}

// Kurze Erklärungen: beim Darüberfahren als Hinweis, beim Antippen in der
// Kachel, auf der Wetterseite zusätzlich als Liste.
const WEATHER_HELP = {
    "Wind 10 m":
        "Gemessener Dauerwind in 10 m Höhe an der nächsten DWD-Station.",
    "Wind 120 m":
        "Vorhergesagter Wind in 120 m Höhe – meist deutlich stärker als am " +
        "Boden und maßgeblich für die übliche Flughöhe.",
    "Böen":
        "Kurze Windspitzen. Sie fordern Stabilität und Akku stärker als der " +
        "Dauerwind; Herstellergrenze beachten.",
    "Temperatur":
        "Kälte senkt die Akkuleistung und Flugzeit deutlich; Akkus vor dem " +
        "Start warm halten.",
    "Niederschlag":
        "Regenmenge der letzten Stunde. Nur Geräte mit Schutzart (z. B. IP55, " +
        "Matrice 30/350) vertragen Regen.",
    "Sicht":
        "Horizontale Sichtweite. Wichtig für Flüge in Sichtweite (VLOS) und " +
        "für Luftraumbeobachter.",
    "Taupunkt":
        "Temperatur, bei der die Luft gesättigt ist. Liegt sie nahe an der " +
        "Lufttemperatur (Differenz ≤ 2 °C), bilden sich leicht Nebel, Beschlag " +
        "an der Kamera und bei Frost Eis.",
    "Wolkenbasis":
        "Geschätzte Wolkenuntergrenze: etwa 125 m je Grad Taupunktdifferenz. " +
        "Liegt sie nahe der Flughöhe, kann die Drohne in Wolken verschwinden.",
    "Satellitennavigation":
        "Kp-Index der Sonnenaktivität (0–9). Ab 4 kann die GPS-Position " +
        "ungenauer werden, ab 5 (geomagnetischer Sturm) sind Drift, " +
        "Kompassfehler und Ausfall der Positionshaltung möglich.",
    "Sonnenaufgang":
        "Vor Beginn der bürgerlichen Dämmerung (Sonne 6° unter dem Horizont) " +
        "gilt es als Nacht; dann gelten Regeln für Nachtflüge, z. B. zur " +
        "Beleuchtung.",
    "Sonnenuntergang":
        "Nach Ende der bürgerlichen Dämmerung gilt es als Nacht; dann gelten " +
        "Regeln für Nachtflüge, z. B. zur Beleuchtung.",
};

function weatherKpLabel(kp) {
    if (kp === null || kp === undefined) {
        return "–";
    }
    const value = Number(kp);
    const state = value >= 7
        ? "starker Sturm"
        : value >= 5
            ? "Sturm"
            : value >= 4 ? "unruhig" : "ruhig";
    return state;
}

function weatherTile(label, value, detail = "") {
    const help = WEATHER_HELP[label] ?? "";
    return `
        <div class="weather-value${help ? " has-help" : ""}"
            ${help ? `tabindex="0" role="button" aria-expanded="false"
                title="${escapeHTML(help)}"` : ""}>
            <span>${escapeHTML(label)}${help ? ' <i aria-hidden="true">ⓘ</i>' : ""}</span>
            <strong>${escapeHTML(value)}</strong>
            ${detail ? `<small>${escapeHTML(detail)}</small>` : ""}
            ${help ? `<small class="weather-help" hidden>${escapeHTML(help)}</small>` : ""}
        </div>
    `;
}

function toggleWeatherHelp(tile) {
    const help = tile?.querySelector(".weather-help");
    if (!help) {
        return;
    }
    help.hidden = !help.hidden;
    tile.setAttribute("aria-expanded", String(!help.hidden));
}

function bindWeatherHelp(card) {
    const values = weatherPart(card, "values");
    if (!values || values.dataset.helpBound) {
        return;
    }
    values.dataset.helpBound = "true";
    values.addEventListener("click", event => {
        toggleWeatherHelp(event.target.closest(".weather-value.has-help"));
    });
    values.addEventListener("keydown", event => {
        if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            toggleWeatherHelp(event.target.closest(".weather-value.has-help"));
        }
    });
}

function renderWeatherHelpList(card) {
    const list = weatherPart(card, "help");
    if (!list || list.childElementCount) {
        return;
    }
    list.innerHTML = Object.entries(WEATHER_HELP)
        .filter(([label]) => label !== "Sonnenaufgang")
        .map(([label, text]) => `
            <dt>${escapeHTML(label === "Sonnenuntergang" ? "Sonnenauf- und -untergang" : label)}</dt>
            <dd>${escapeHTML(text)}</dd>
        `)
        .join("");
}

function weatherPart(card, name) {
    return card.querySelector(`[data-weather="${name}"]`);
}

function renderWeatherCard(card, report) {
    card.hidden = false;

    const current = report.current ?? {};
    const now = report.forecast?.[0] ?? {};
    const level = report.assessment?.level ?? "unknown";

    const location = report.location ?? {};
    const station = current.station
        ? ` · Messung ${current.station}` +
          (current.time ? `, ${weatherClock(current.time)} Uhr` : "")
        : "";
    weatherPart(card, "location").textContent =
        `${location.name ?? "Standort"}${station}` +
        (weatherPlaceNote ? ` · ${weatherPlaceNote}` : "");
    renderWeatherPlaces(card, report);

    weatherPart(card, "level").dataset.level = level;
    weatherPart(card, "level-text").textContent =
        `${WEATHER_LEVEL_TEXT[level] ?? level} – ` +
        (report.assessment?.summary ?? "");

    const direction = weatherCompass(
        current.wind_direction_deg ?? now.wind_direction_deg
    );
    bindWeatherHelp(card);
    renderWeatherHelpList(card);
    weatherPart(card, "values").innerHTML = [
        weatherTile(
            "Wind 10 m",
            `${weatherNumber(current.wind_speed_ms ?? now.wind_speed_ms)} m/s`,
            direction ? `aus ${direction}` : ""
        ),
        weatherTile(
            "Wind 120 m",
            `${weatherNumber(now.wind_speed_120m_ms)} m/s`,
            "Vorhersage"
        ),
        weatherTile(
            "Böen",
            `${weatherNumber(current.wind_gust_ms ?? now.wind_gust_ms)} m/s`
        ),
        weatherTile(
            "Temperatur",
            `${weatherNumber(current.temperature_c ?? now.temperature_c)} °C`
        ),
        weatherTile(
            "Niederschlag",
            `${weatherNumber(current.precipitation_mm_h ?? now.precipitation_mm_h)} mm/h`
        ),
        weatherTile(
            "Sicht",
            weatherVisibility(current.visibility_m ?? now.visibility_m)
        ),
        weatherTile(
            "Taupunkt",
            `${weatherNumber(report.derived?.dew_point_c)} °C`,
            report.derived?.dew_point_spread_c !== null &&
            report.derived?.dew_point_spread_c !== undefined
                ? `Differenz ${weatherNumber(report.derived.dew_point_spread_c)} °C`
                : ""
        ),
        weatherTile(
            "Wolkenbasis",
            report.derived?.cloud_base_m !== null &&
            report.derived?.cloud_base_m !== undefined
                ? `ca. ${report.derived.cloud_base_m.toLocaleString("de-DE")} m`
                : "–",
            "geschätzt aus Taupunkt"
        ),
        weatherTile(
            "Satellitennavigation",
            weatherKpLabel(report.kp?.kp),
            report.kp?.kp !== null && report.kp?.kp !== undefined
                ? `Kp-Index ${weatherNumber(report.kp.kp)}`
                : "Kp-Index"
        ),
        weatherTile(
            "Sonnenaufgang",
            report.sun?.sunrise ? `${weatherClock(report.sun.sunrise)} Uhr` : "–",
            report.sun?.civil_dawn
                ? `Dämmerung ab ${weatherClock(report.sun.civil_dawn)}`
                : ""
        ),
        weatherTile(
            "Sonnenuntergang",
            report.sun?.sunset ? `${weatherClock(report.sun.sunset)} Uhr` : "–",
            report.sun?.civil_dusk
                ? `Dämmerung bis ${weatherClock(report.sun.civil_dusk)}`
                : ""
        ),
    ].join("");

    const reasons = report.assessment?.reasons ?? [];
    const errors = Object.keys(report.errors ?? {});
    weatherPart(card, "reasons").innerHTML = [
        ...reasons.map(reason => `
            <li data-level="${escapeHTML(reason.level)}">${escapeHTML(reason.text)}</li>
        `),
        ...(errors.length
            ? [`<li data-level="unknown">Teilweise ohne Daten: ${
                escapeHTML(errors.map(weatherSourceName).join(", "))
            }</li>`]
            : []),
    ].join("");

    const alerts = report.alerts ?? [];
    weatherPart(card, "alerts").hidden = alerts.length === 0;
    weatherPart(card, "alerts-summary").textContent =
        `DWD-Warnungen (${alerts.length})` +
        (report.alert_area ? ` · ${report.alert_area}` : "");
    weatherPart(card, "alert-list").innerHTML = alerts
        .map(alert => `
            <li data-severity="${escapeHTML(alert.severity ?? "")}">
                <strong>${escapeHTML(alert.headline ?? alert.event ?? "Warnung")}</strong>
                <small>${escapeHTML(WEATHER_ALERT_SEVERITY[alert.severity] ?? "")}
                    · ${escapeHTML(weatherClock(alert.onset))} bis
                    ${escapeHTML(weatherClock(alert.expires))} Uhr</small>
                ${alert.description ? `<p>${escapeHTML(alert.description)}</p>` : ""}
            </li>
        `)
        .join("");

    renderWeatherForecast(card, report);

    weatherPart(card, "attribution").textContent =
        `${report.attribution ?? ""}.`;
}

function renderWeatherForecast(container, report) {
    const body = weatherPart(container, "forecast");
    if (!body) {
        return;
    }
    const hours = Number(container.dataset.forecastHours) || 7;
    body.innerHTML =
        (report.forecast ?? [])
            .slice(0, hours)
            .map(hour => `
                <tr>
                    <td>${escapeHTML(weatherClock(hour.time))}</td>
                    <td>${escapeHTML(weatherNumber(hour.wind_speed_ms))} m/s
                        ${escapeHTML(weatherCompass(hour.wind_direction_deg))}</td>
                    <td>${escapeHTML(weatherNumber(hour.wind_speed_120m_ms))} m/s</td>
                    <td>${escapeHTML(weatherNumber(hour.wind_gust_ms))} m/s</td>
                    <td>${escapeHTML(weatherNumber(hour.precipitation_mm_h))} mm/h
                        ${hour.precipitation_probability !== null && hour.precipitation_probability !== undefined
                            ? `(${escapeHTML(String(hour.precipitation_probability))} %)`
                            : ""}</td>
                    <td>${escapeHTML(weatherNumber(hour.temperature_c))} °C</td>
                </tr>
            `)
            .join("");

}

function weatherSourceName(kind) {
    return {
        current: "Messwerte",
        alerts: "DWD-Warnungen",
        forecast: "Vorhersage",
        kp: "Kp-Index",
    }[kind] ?? kind;
}

function weatherCards() {
    return [...document.querySelectorAll("[data-weather-card]")];
}

// ----------------------------------------------------------
// Ortswahl
// ----------------------------------------------------------

function readWeatherPlace() {
    if (weatherPlaceChoice === null) {
        try {
            weatherPlaceChoice = localStorage.getItem(WEATHER_PLACE_KEY);
        } catch {
            // Ohne Speicher gilt die Wahl nur bis zum Neuladen.
        }
        weatherPlaceChoice ||= "auto";
    }
    return weatherPlaceChoice;
}

function storeWeatherPlace(choice) {
    weatherPlaceChoice = choice;
    try {
        localStorage.setItem(WEATHER_PLACE_KEY, choice);
    } catch {
        // Siehe oben.
    }
}

function requestDevicePosition() {
    return new Promise((resolve, reject) => {
        if (!navigator.geolocation) {
            reject(new Error("unsupported"));
            return;
        }
        navigator.geolocation.getCurrentPosition(
            result => resolve(result.coords),
            reject,
            {enableHighAccuracy: false, maximumAge: 5 * 60 * 1000, timeout: 15000}
        );
    });
}

// Beim Laden nie ungefragt nach dem Standort fragen: Nur wenn die Freigabe
// schon erteilt ist, wird er ohne Antippen abgerufen.
async function devicePositionAllowed() {
    try {
        const status = await navigator.permissions.query({name: "geolocation"});
        return status.state === "granted";
    } catch {
        return false;
    }
}

async function weatherQuery() {
    const choice = readWeatherPlace();
    weatherPlaceNote = "";
    if (choice !== "device") {
        return choice === "auto" ? "" : `?${new URLSearchParams({place: choice})}`;
    }
    if (weatherDevicePosition || await devicePositionAllowed()) {
        try {
            weatherDevicePosition = await requestDevicePosition();
        } catch (error) {
            console.debug("Standort:", error);
        }
    }
    if (!weatherDevicePosition) {
        weatherPlaceNote = "Gerätestandort nicht verfügbar";
        return "";
    }
    // Auf rund 1 km gerundet – genauer rechnet der Server ohnehin nicht.
    return `?${new URLSearchParams({
        lat: weatherDevicePosition.latitude.toFixed(2),
        lon: weatherDevicePosition.longitude.toFixed(2),
        choices: "true",
    })}`;
}

function renderWeatherPlaces(card, report) {
    const select = weatherPart(card, "place");
    if (!select || !report.places) {
        return;
    }
    const automatic = report.places.find(item => item.key === report.automatic_place);
    const options = [
        ["auto", `Automatisch${automatic ? ` (${automatic.name})` : ""}`],
        ["device", "Mein Standort"],
        ...report.places.map(item => [item.key, item.name]),
    ];
    select.replaceChildren(...options.map(([value, text]) => new Option(text, value)));
    const choice = readWeatherPlace();
    // Verschwundene Orte (beendeter Einsatz) zeigen wieder „Automatisch“.
    select.value = options.some(([value]) => value === choice) ? choice : "auto";
    weatherPart(card, "place-label").hidden = false;
    if (!select.dataset.bound) {
        select.dataset.bound = "true";
        select.addEventListener("change", () => chooseWeatherPlace(select.value));
    }
}

async function chooseWeatherPlace(choice) {
    storeWeatherPlace(choice);
    if (choice === "device") {
        weatherCards().forEach(card => {
            weatherPart(card, "location").textContent = "Standort wird ermittelt …";
        });
        try {
            // Direkt nach dem Antippen: Hier darf der Browser nachfragen.
            weatherDevicePosition = await requestDevicePosition();
        } catch (error) {
            console.debug("Standort:", error);
            weatherDevicePosition = null;
        }
    }
    // Ein neuer Ort kann einige Sekunden dauern, bis der DWD geantwortet hat.
    weatherCards().forEach(card => {
        weatherPart(card, "location").textContent = "Wetter wird geladen …";
    });
    await loadWeatherCard();
}

async function loadWeatherCard() {
    const cards = weatherCards();
    if (!cards.length) {
        return;
    }
    const request = ++weatherRequest;
    try {
        const query = await weatherQuery();
        const response = await fetch(`/api/weather${query}`, {cache: "no-store"});
        if (response.status === 404) {
            // Wettermodul ausgeschaltet.
            cards.forEach(card => {
                card.hidden = true;
            });
            document.getElementById("nav-weather")?.setAttribute("hidden", "");
            return;
        }
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        const report = await response.json();
        if (request !== weatherRequest) {
            return;
        }
        if (report.location?.origin === "query") {
            report.location.name = "Mein Standort";
        }
        if (typeof setWeatherRadarLocation === "function") {
            setWeatherRadarLocation(report.location);
        }
        document.getElementById("nav-weather")?.removeAttribute("hidden");
        cards.forEach(card => renderWeatherCard(card, report));
        document.querySelectorAll("[data-weather-forecast-card]").forEach(card => {
            card.hidden = !(report.forecast ?? []).length;
            renderWeatherForecast(card, report);
        });
    } catch (error) {
        cards.forEach(card => {
            card.hidden = false;
            weatherPart(card, "level").dataset.level = "unknown";
            weatherPart(card, "level-text").textContent =
                "Wetterdaten derzeit nicht abrufbar";
        });
        console.warn("Wetter konnte nicht geladen werden:", error);
    }
}

function startWeatherCard() {
    if (!weatherCards().length) {
        return;
    }
    loadWeatherCard();
    window.clearInterval(weatherTimer);
    weatherTimer = window.setInterval(() => {
        if (!document.hidden) {
            loadWeatherCard();
        }
    }, WEATHER_REFRESH_MS);
    document.addEventListener("visibilitychange", () => {
        if (!document.hidden) {
            loadWeatherCard();
        }
    });
}

// ----------------------------------------------------------
// Einstellungen (Admins)
// ----------------------------------------------------------

const WEATHER_SETTING_FIELDS = {
    "cfg-weather-location-name": "location_name",
    "cfg-weather-latitude": "latitude",
    "cfg-weather-longitude": "longitude",
    "cfg-weather-wind": "wind_limit_ms",
    "cfg-weather-gust": "gust_limit_ms",
    "cfg-weather-temp-min": "min_temperature_c",
    "cfg-weather-temp-max": "max_temperature_c",
    "cfg-weather-rain": "rain_limit_mm_h",
    "cfg-weather-visibility": "visibility_min_m",
};

function renderWeatherSettings(settings) {
    const enabled = document.getElementById("cfg-weather-enabled");
    if (!enabled) {
        return;
    }
    enabled.checked = Boolean(settings.enabled);
    for (const [id, key] of Object.entries(WEATHER_SETTING_FIELDS)) {
        const input = document.getElementById(id);
        if (input) {
            input.value = settings[key] ?? "";
        }
    }
}

async function loadWeatherSettings() {
    if (!document.getElementById("cfg-weather-enabled")) {
        return;
    }
    try {
        const result = await api.get("/api/weather/settings");
        renderWeatherSettings(result.weather);
    } catch (error) {
        document.getElementById("cfg-weather-status").textContent =
            "Wettereinstellungen konnten nicht geladen werden: " + error.message;
    }
}

function collectWeatherSettings() {
    const value = id => document.getElementById(id).value.trim();
    const number = id => (value(id) === "" ? null : Number(value(id).replace(",", ".")));
    return {
        enabled: document.getElementById("cfg-weather-enabled").checked,
        location_name: value("cfg-weather-location-name"),
        latitude: number("cfg-weather-latitude"),
        longitude: number("cfg-weather-longitude"),
        wind_limit_ms: number("cfg-weather-wind"),
        gust_limit_ms: number("cfg-weather-gust"),
        min_temperature_c: number("cfg-weather-temp-min"),
        max_temperature_c: number("cfg-weather-temp-max"),
        rain_limit_mm_h: number("cfg-weather-rain"),
        visibility_min_m: number("cfg-weather-visibility"),
    };
}

async function saveWeatherSettings() {
    const button = document.getElementById("cfg-weather-save");
    const status = document.getElementById("cfg-weather-status");
    if (button) button.disabled = true;
    status.textContent = "Wird gespeichert …";
    try {
        const result = await api.put(
            "/api/weather/settings",
            collectWeatherSettings()
        );
        renderWeatherSettings(result.weather);
        status.textContent = "Gespeichert. Die Übersicht nutzt die neuen Werte.";
        loadWeatherCard();
    } catch (error) {
        const message = String(error.message || "").replace(/^Value error,\s*/i, "");
        status.textContent = "Speichern fehlgeschlagen: " + message;
    } finally {
        if (button) button.disabled = false;
    }
}

document.addEventListener("DOMContentLoaded", () => {
    startWeatherCard();
    loadWeatherSettings();
});
