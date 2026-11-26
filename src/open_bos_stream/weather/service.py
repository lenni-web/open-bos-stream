"""Wetterdaten für Drohneneinsätze.

Alle Abrufe laufen über den eigenen Server, damit Browser keine Verbindung zu
externen Diensten aufbauen und Ergebnisse für alle Nutzer zwischengespeichert
werden. Jede Quelle ist für sich optional: Fällt eine aus, liefern die
übrigen weiter Daten.

Quellen:
* Bright Sky – Messwerte der nächsten DWD-Station und amtliche DWD-Warnungen
  (Daten: Deutscher Wetterdienst).
* Open-Meteo – Vorhersage nach dem DWD-Modell ICON, auch Wind in 80 und
  120 m Höhe.
* NOAA SWPC – planetarer Kp-Index (Störungen der Satellitennavigation).
"""

from __future__ import annotations

import json
import logging
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import OrderedDict
from typing import Any, Callable

from open_bos_stream.core.models import WeatherConfig
from open_bos_stream.weather.assessment import assess


logger = logging.getLogger(__name__)

BRIGHTSKY_URL = "https://api.brightsky.dev"
OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
KP_URL = "https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json"

ATTRIBUTION = (
    "Wetterdaten: Deutscher Wetterdienst (über Bright Sky und Open-Meteo), "
    "Kp-Index: NOAA SWPC"
)

REQUEST_TIMEOUT_SECONDS = 8
CACHE_MAX_ENTRIES = 400
# Messwerte und Warnungen ändern sich häufiger als die Modellvorhersage.
TTL_SECONDS = {
    "current": 10 * 60,
    "alerts": 10 * 60,
    "forecast": 30 * 60,
    "kp": 60 * 60,
}
# Fehlgeschlagene Abrufe nicht bei jeder Anfrage wiederholen.
ERROR_TTL_SECONDS = 2 * 60
FORECAST_HOURS = 7
# Etwa 5 km Raster: Nachbarorte teilen sich Zwischenspeicher und Abrufe.
COORDINATE_PRECISION = 2

KMH_PER_MS = 3.6


class WeatherUnavailableError(RuntimeError):
    """Eine Wetterquelle ist nicht erreichbar oder lieferte Unsinn."""


def _ms(value: Any) -> float | None:
    """km/h (DWD-Einheit bei Bright Sky) in m/s umrechnen."""

    if value is None:
        return None
    return round(float(value) / KMH_PER_MS, 1)


def _number(value: Any, digits: int = 1) -> float | None:
    if value is None:
        return None
    try:
        return round(float(value), digits)
    except (TypeError, ValueError):
        return None


def parse_current(data: dict) -> dict:
    weather = data.get("weather") or {}
    sources = data.get("sources") or []
    station = next(
        (
            source
            for source in sources
            if source.get("id") == weather.get("source_id")
        ),
        sources[0] if sources else {},
    )
    return {
        "time": weather.get("timestamp"),
        "temperature_c": _number(weather.get("temperature")),
        "wind_speed_ms": _ms(weather.get("wind_speed_10")),
        "wind_gust_ms": _ms(weather.get("wind_gust_speed_10")),
        "wind_direction_deg": weather.get("wind_direction_10"),
        # Niederschlag der letzten Stunde entspricht mm/h.
        "precipitation_mm_h": _number(weather.get("precipitation_60")),
        "visibility_m": weather.get("visibility"),
        "cloud_cover_percent": weather.get("cloud_cover"),
        "humidity_percent": weather.get("relative_humidity"),
        "condition": weather.get("condition"),
        "icon": weather.get("icon"),
        "station": station.get("station_name"),
        "station_distance_km": (
            round(station["distance"] / 1000, 1)
            if station.get("distance") is not None
            else None
        ),
    }


def parse_forecast(data: dict) -> list[dict]:
    hourly = data.get("hourly") or {}
    times = hourly.get("time") or []

    def series(name: str, index: int) -> Any:
        values = hourly.get(name) or []
        return values[index] if index < len(values) else None

    return [
        {
            "time": time_value,
            "temperature_c": _number(series("temperature_2m", index)),
            "precipitation_mm_h": _number(series("precipitation", index)),
            "precipitation_probability": series(
                "precipitation_probability", index
            ),
            "wind_speed_ms": _number(series("wind_speed_10m", index)),
            "wind_speed_80m_ms": _number(series("wind_speed_80m", index)),
            "wind_speed_120m_ms": _number(series("wind_speed_120m", index)),
            "wind_gust_ms": _number(series("wind_gusts_10m", index)),
            "wind_direction_deg": series("wind_direction_10m", index),
            "weather_code": series("weather_code", index),
            "visibility_m": series("visibility", index),
        }
        for index, time_value in enumerate(times)
    ]


def parse_alerts(data: dict) -> dict:
    location = data.get("location") or {}
    alerts = [
        {
            "event": alert.get("event_de") or alert.get("event_en"),
            "headline": alert.get("headline_de") or alert.get("headline_en"),
            "description": alert.get("description_de")
            or alert.get("description_en"),
            "severity": alert.get("severity"),
            "onset": alert.get("onset"),
            "expires": alert.get("expires"),
        }
        for alert in data.get("alerts") or []
        if alert.get("status", "actual") == "actual"
    ]
    return {
        "area": location.get("name"),
        "alerts": alerts,
    }


def parse_kp(data: list) -> dict | None:
    """Letzten Kp-Wert lesen (neues Objekt- oder altes Tabellenformat)."""

    rows = [row for row in data if row]
    if not rows:
        return None
    last = rows[-1]
    if isinstance(last, dict):
        time_value, value = last.get("time_tag"), last.get("Kp")
    else:
        header = rows[0]
        if len(rows) < 2 or not isinstance(header, list):
            return None
        time_value = last[header.index("time_tag")]
        value = last[header.index("Kp")]
    kp = _number(value, 2)
    if kp is None:
        return None
    return {"time": time_value, "kp": kp}


class WeatherService:
    def __init__(
        self,
        *,
        fetch_json: Callable[[str], Any] | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._fetch_json = fetch_json or self._http_json
        self._clock = clock
        self._cache: OrderedDict[str, tuple[float, Any, str | None]] = (
            OrderedDict()
        )
        self._lock = threading.Lock()

    def report(
        self,
        config: WeatherConfig,
        latitude: float,
        longitude: float,
    ) -> dict:
        lat = round(latitude, COORDINATE_PRECISION)
        lon = round(longitude, COORDINATE_PRECISION)
        errors: dict[str, str] = {}

        def load(kind: str, url: str, parser):
            data, error = self._cached(kind, f"{kind}:{lat}:{lon}", url)
            if error:
                errors[kind] = error
                return None
            try:
                return parser(data)
            except (KeyError, TypeError, ValueError, IndexError) as exc:
                errors[kind] = f"Unerwartete Antwort: {exc}"
                return None

        query = urllib.parse.urlencode({"lat": lat, "lon": lon})
        current = load(
            "current",
            f"{BRIGHTSKY_URL}/current_weather?{query}",
            parse_current,
        )
        alerts = load(
            "alerts",
            f"{BRIGHTSKY_URL}/alerts?{query}",
            parse_alerts,
        )
        forecast = load(
            "forecast",
            f"{OPEN_METEO_URL}?"
            + urllib.parse.urlencode(
                {
                    "latitude": lat,
                    "longitude": lon,
                    "models": "icon_seamless",
                    "hourly": ",".join(
                        (
                            "temperature_2m",
                            "precipitation",
                            "precipitation_probability",
                            "wind_speed_10m",
                            "wind_speed_80m",
                            "wind_speed_120m",
                            "wind_gusts_10m",
                            "wind_direction_10m",
                            "weather_code",
                            "visibility",
                        )
                    ),
                    "wind_speed_unit": "ms",
                    "timezone": "Europe/Berlin",
                    "forecast_hours": FORECAST_HOURS,
                }
            ),
            parse_forecast,
        )
        kp = load("kp", KP_URL, parse_kp)

        report = {
            "coordinates": {"latitude": lat, "longitude": lon},
            "current": current,
            "forecast": forecast or [],
            "alerts": (alerts or {}).get("alerts", []),
            "alert_area": (alerts or {}).get("area"),
            "kp": kp,
            "errors": errors,
            "attribution": ATTRIBUTION,
        }
        report["assessment"] = assess(report, config)
        return report

    def _cached(self, kind: str, key: str, url: str) -> tuple[Any, str | None]:
        now = self._clock()
        with self._lock:
            entry = self._cache.get(key)
            if entry is not None:
                stored_at, data, error = entry
                ttl = ERROR_TTL_SECONDS if error else TTL_SECONDS[kind]
                if now - stored_at < ttl:
                    self._cache.move_to_end(key)
                    return data, error

        try:
            data, error = self._fetch_json(url), None
        except WeatherUnavailableError as exc:
            logger.warning("Wetterquelle %s nicht verfügbar: %s", kind, exc)
            data, error = None, str(exc)

        with self._lock:
            self._cache[key] = (now, data, error)
            self._cache.move_to_end(key)
            while len(self._cache) > CACHE_MAX_ENTRIES:
                self._cache.popitem(last=False)
        return data, error

    @staticmethod
    def _http_json(url: str) -> Any:
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Open-BOS-Stream",
                "Accept": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(
                request,
                timeout=REQUEST_TIMEOUT_SECONDS,
            ) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            raise WeatherUnavailableError(f"HTTP {exc.code}") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise WeatherUnavailableError("nicht erreichbar") from exc
        except ValueError as exc:
            raise WeatherUnavailableError("keine gültige Antwort") from exc
