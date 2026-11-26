"""Ampel für Drohnenflüge aus Messwerten, Vorhersage und Warnungen.

Die Bewertung ist eine Orientierungshilfe. Maßgeblich bleiben die Grenzwerte
des Herstellers und die Entscheidung der Fernpilotin oder des Fernpiloten.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from open_bos_stream.core.models import WeatherConfig


LEVELS = ("green", "yellow", "red")
# Anteil des Grenzwerts, ab dem die Ampel gelb wird.
CAUTION_SHARE = 0.75
KP_CAUTION = 4
KP_LIMIT = 5
TEMPERATURE_MARGIN_C = 3
# Taupunktdifferenz, ab der Nebel und Beschlag wahrscheinlich werden.
DEW_POINT_SPREAD_CAUTION = 2.0
CLOUD_BASE_CAUTION_M = 200
# Vereisung: um den Gefrierpunkt bei feuchter Luft oder Niederschlag.
ICING_MIN_C = -10
ICING_MAX_C = 3
ICING_HUMIDITY = 90
# Der Ausblick der Ampel reicht nur über die nächsten Stunden.
OUTLOOK_HOURS = 6

ALERT_LEVELS = {
    "minor": None,
    "moderate": "yellow",
    "severe": "red",
    "extreme": "red",
}


def _max(*values: Any) -> float | None:
    numbers = [float(value) for value in values if value is not None]
    return max(numbers) if numbers else None


def _fmt(value: float, digits: int = 1) -> str:
    return f"{value:.{digits}f}".replace(".", ",")


def _hour(value: str | None) -> str:
    try:
        return datetime.fromisoformat(value).strftime("%H:%M")
    except (TypeError, ValueError):
        return value or ""


def assess(report: dict, config: WeatherConfig) -> dict:
    reasons: list[dict] = []

    def add(level: str, text: str) -> None:
        reasons.append({"level": level, "text": text})

    current = report.get("current") or {}
    forecast = report.get("forecast") or []
    now = forecast[0] if forecast else {}

    # Wind: Messung am Boden (10 m) und Modellwert in Flughöhe (120 m).
    wind = _max(
        current.get("wind_speed_ms"),
        now.get("wind_speed_ms"),
        now.get("wind_speed_120m_ms"),
    )
    if wind is not None:
        if wind > config.wind_limit_ms:
            add("red", f"Wind {_fmt(wind)} m/s über dem Grenzwert "
                f"von {_fmt(config.wind_limit_ms)} m/s")
        elif wind > config.wind_limit_ms * CAUTION_SHARE:
            add("yellow", f"Wind {_fmt(wind)} m/s nahe am Grenzwert")

    gust = _max(current.get("wind_gust_ms"), now.get("wind_gust_ms"))
    if gust is not None:
        if gust > config.gust_limit_ms:
            add("red", f"Böen {_fmt(gust)} m/s über dem Grenzwert "
                f"von {_fmt(config.gust_limit_ms)} m/s")
        elif gust > config.gust_limit_ms * CAUTION_SHARE:
            add("yellow", f"Böen {_fmt(gust)} m/s nahe am Grenzwert")

    rain = _max(
        current.get("precipitation_mm_h"),
        now.get("precipitation_mm_h"),
    )
    if rain is not None and rain > 0:
        if rain >= config.rain_limit_mm_h:
            add("red", f"Niederschlag {_fmt(rain)} mm/h")
        else:
            add("yellow", f"Leichter Niederschlag {_fmt(rain)} mm/h")

    temperature = current.get("temperature_c")
    if temperature is None:
        temperature = now.get("temperature_c")
    if temperature is not None:
        if not (
            config.min_temperature_c
            <= temperature
            <= config.max_temperature_c
        ):
            add("red", f"Temperatur {_fmt(temperature)} °C außerhalb "
                f"von {_fmt(config.min_temperature_c, 0)} bis "
                f"{_fmt(config.max_temperature_c, 0)} °C")
        elif (
            temperature < config.min_temperature_c + TEMPERATURE_MARGIN_C
            or temperature > config.max_temperature_c - TEMPERATURE_MARGIN_C
        ):
            add("yellow", f"Temperatur {_fmt(temperature)} °C nahe am "
                "Grenzwert (Akkuleistung beachten)")

    visibility = current.get("visibility_m")
    if visibility is None:
        visibility = now.get("visibility_m")
    if visibility is not None:
        if visibility < config.visibility_min_m:
            add("red", f"Sicht nur {int(visibility)} m")
        elif visibility < config.visibility_min_m * 2:
            add("yellow", f"Eingeschränkte Sicht ({int(visibility)} m)")

    derived = report.get("derived") or {}
    spread = derived.get("dew_point_spread_c")
    if spread is not None and spread <= DEW_POINT_SPREAD_CAUTION:
        add("yellow", f"Taupunktdifferenz {_fmt(spread)} °C: Nebel und "
            "beschlagene Optik möglich")
    cloud_base = derived.get("cloud_base_m")
    if cloud_base is not None and cloud_base < CLOUD_BASE_CAUTION_M:
        add("yellow", f"Tiefe Wolkenuntergrenze (geschätzt {cloud_base} m)")
    humidity = current.get("humidity_percent")
    if (
        temperature is not None
        and ICING_MIN_C <= temperature <= ICING_MAX_C
        and (
            (spread is not None and spread <= DEW_POINT_SPREAD_CAUTION)
            or (humidity is not None and humidity >= ICING_HUMIDITY)
            or (rain is not None and rain > 0)
        )
    ):
        add("yellow", "Vereisungsgefahr an Propellern und Sensoren")

    if (report.get("sun") or {}).get("dark"):
        add("yellow", "Dunkelheit nach Ende der bürgerlichen Dämmerung: "
            "Regeln für Nachtflüge beachten")

    kp = (report.get("kp") or {}).get("kp")
    if kp is not None:
        if kp >= KP_LIMIT:
            add("red", f"Geomagnetischer Sturm (Kp {_fmt(kp)}): "
                "GNSS-Störungen möglich")
        elif kp >= KP_CAUTION:
            add("yellow", f"Erhöhter Kp-Index ({_fmt(kp)})")

    for alert in report.get("alerts") or []:
        level = ALERT_LEVELS.get(alert.get("severity"))
        if level:
            add(level, f"DWD: {alert.get('headline') or alert.get('event')}")

    # Ausblick: erste kommende Stunde, die einen Grenzwert überschreitet.
    for hour in forecast[1:OUTLOOK_HOURS + 1]:
        problems = []
        hour_wind = _max(hour.get("wind_speed_ms"), hour.get("wind_speed_120m_ms"))
        if hour_wind is not None and hour_wind > config.wind_limit_ms:
            problems.append(f"Wind {_fmt(hour_wind)} m/s")
        if (
            hour.get("wind_gust_ms") is not None
            and hour["wind_gust_ms"] > config.gust_limit_ms
        ):
            problems.append(f"Böen {_fmt(hour['wind_gust_ms'])} m/s")
        if (
            hour.get("precipitation_mm_h") is not None
            and hour["precipitation_mm_h"] >= config.rain_limit_mm_h
        ):
            problems.append(f"Niederschlag {_fmt(hour['precipitation_mm_h'])} mm/h")
        if problems:
            add("yellow", f"Vorhersage ab {_hour(hour.get('time'))} Uhr: "
                + ", ".join(problems))
            break

    level = "green"
    for reason in reasons:
        if LEVELS.index(reason["level"]) > LEVELS.index(level):
            level = reason["level"]

    has_data = bool(current) or bool(forecast)
    return {
        "level": level if has_data else "unknown",
        "summary": {
            "green": "Keine Einschränkungen erkannt",
            "yellow": "Mit Einschränkungen fliegbar – Hinweise beachten",
            "red": "Grenzwerte überschritten",
            "unknown": "Keine Wetterdaten verfügbar",
        }[level if has_data else "unknown"],
        "reasons": sorted(
            reasons,
            key=lambda reason: -LEVELS.index(reason["level"]),
        ),
    }
