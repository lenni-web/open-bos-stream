"""Nachrichten der Cloud API lesen (ohne Netzwerk, ohne Datenbank).

Themen und Feldnamen laut DJI Cloud-API-Doc (Pilot to Cloud). Unbekannte
Felder bleiben in der aufgezeichneten Nachricht erhalten.
"""

from __future__ import annotations

import re


# (type, sub_type) laut „Product Support“ der Cloud API.
MODELS = {
    (77, 0): "DJI Mavic 3E",
    (77, 1): "DJI Mavic 3T",
    (60, 0): "DJI Matrice 300 RTK",
    (144, 0): "DJI RC Pro Enterprise",
    (119, 0): "DJI RC Plus",
    (56, 0): "DJI Smart Controller Enterprise",
}

# Flugzustand der Drohne (mode_code).
MODES = {
    0: "Bereit", 1: "Startvorbereitung", 2: "Startbereit", 3: "Manueller Flug",
    4: "Automatischer Start", 5: "Routenflug", 6: "Panoramaaufnahme",
    7: "Verfolgung", 8: "Ausweichen (ADS-B)", 9: "Rückkehr zum Startpunkt",
    10: "Automatische Landung", 11: "Erzwungene Landung", 12: "Landung auf drei Rotoren",
    13: "Aktualisierung", 14: "Nicht verbunden", 15: "APAS", 16: "Virtueller Steuerknüppel",
    17: "Ferngesteuerter Flug", 18: "RTK-Positionierung",
}

TOPIC = re.compile(r"^(?P<root>thing|sys)/product/(?P<serial>[A-Za-z0-9_-]{1,64})/(?P<channel>[a-z_/]{1,40})$")

# Was die Anwendung abonniert: alles, was Geräte senden.
SUBSCRIPTIONS = (
    "thing/product/+/osd",
    "thing/product/+/state",
    "thing/product/+/status",
    "thing/product/+/events",
    "thing/product/+/requests",
    "thing/product/+/services_reply",
    "thing/product/+/property/set_reply",
    "sys/product/+/status",
)


def parse_topic(topic: str) -> tuple[str, str] | None:
    """``(Seriennummer, Kanal)`` oder None."""

    match = TOPIC.match(topic or "")
    return (match["serial"], match["channel"]) if match else None


def model_name(model_type: int | None, sub_type: int | None) -> str:
    if model_type is None:
        return "unbekanntes Modell"
    return MODELS.get((model_type, sub_type or 0), f"unbekanntes Modell ({model_type}/{sub_type or 0})")


def _number(value, low: float, high: float) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value) if low <= value <= high else None


def extract(data: dict) -> dict:
    """Die für Karte und Auswertung benötigten Werte aus ``data``.

    Nur vorhandene Werte: ``state``-Nachrichten enthalten Teilmengen und
    ergänzen den letzten Stand.
    """

    values: dict = {}
    latitude = _number(data.get("latitude"), -90, 90)
    longitude = _number(data.get("longitude"), -180, 180)
    # 0/0 meldet DJI ohne Satellitenempfang.
    if latitude is not None and longitude is not None and (latitude, longitude) != (0.0, 0.0):
        values["latitude"] = latitude
        values["longitude"] = longitude
    for source, target, low, high in (
        ("elevation", "elevation", -2000, 20000),
        ("height", "height", -2000, 20000),
        ("attitude_head", "heading", -360, 360),
        ("horizontal_speed", "horizontal_speed", 0, 200),
        ("vertical_speed", "vertical_speed", -100, 100),
        ("wind_speed", "wind_speed", 0, 1000),
        ("home_distance", "home_distance", 0, 1_000_000),
    ):
        number = _number(data.get(source), low, high)
        if number is not None:
            values[target] = number
    battery = data.get("battery")
    if isinstance(battery, dict):
        percent = _number(battery.get("capacity_percent"), 0, 100)
        remaining = _number(battery.get("remain_flight_time"), 0, 86400)
        if remaining is not None:
            values["remain_flight_time"] = int(remaining)
    else:
        # Fernsteuerung: Akkustand steht direkt in data.
        percent = _number(data.get("capacity_percent"), 0, 100)
    if percent is not None:
        values["battery"] = int(percent)
    mode = data.get("mode_code")
    if isinstance(mode, int) and not isinstance(mode, bool):
        values["mode_code"] = mode
        values["mode"] = MODES.get(mode, f"Zustand {mode}")
    home_latitude = _number(data.get("home_latitude"), -90, 90)
    home_longitude = _number(data.get("home_longitude"), -180, 180)
    if home_latitude is not None and home_longitude is not None and (home_latitude, home_longitude) != (0.0, 0.0):
        values["home_latitude"] = home_latitude
        values["home_longitude"] = home_longitude
    return values
