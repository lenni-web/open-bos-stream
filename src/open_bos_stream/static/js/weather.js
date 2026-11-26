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

let weatherTimer = null;

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

function weatherTile(label, value, detail = "") {
    return `
        <div class="weather-value">
            <span>${escapeHTML(label)}</span>
            <strong>${escapeHTML(value)}</strong>
            ${detail ? `<small>${escapeHTML(detail)}</small>` : ""}
        </div>
    `;
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
          (current.station_distance_km !== null && current.station_distance_km !== undefined
              ? ` (${weatherNumber(current.station_distance_km)} km)`
              : "") +
          (current.time ? `, ${weatherClock(current.time)} Uhr` : "")
        : "";
    weatherPart(card, "location").textContent =
        `${location.name ?? "Standort"}${station}`;

    weatherPart(card, "level").dataset.level = level;
    weatherPart(card, "level-text").textContent =
        `${WEATHER_LEVEL_TEXT[level] ?? level} – ` +
        (report.assessment?.summary ?? "");

    const direction = weatherCompass(
        current.wind_direction_deg ?? now.wind_direction_deg
    );
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
            "Kp-Index",
            weatherNumber(report.kp?.kp),
            "GNSS-Störungen ab 5"
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

    const hours = Number(card.dataset.forecastHours) || 7;
    weatherPart(card, "forecast").innerHTML =
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

    weatherPart(card, "attribution").textContent =
        `${report.attribution ?? ""}.`;
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

async function loadWeatherCard() {
    const cards = weatherCards();
    if (!cards.length) {
        return;
    }
    try {
        const response = await fetch("/api/weather", {cache: "no-store"});
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
        document.getElementById("nav-weather")?.removeAttribute("hidden");
        cards.forEach(card => renderWeatherCard(card, report));
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
