"""Aufbereitung der Wasserentnahme-Ebenen für die Karte.

Die GeoJSON-Dateien stammen aus OpenStreetMap. Zwei Dinge werden beim
Ausliefern korrigiert:

* Lagertanks mit einem Inhalt, der kein Wasser ist (Gülle, Gas,
  Abwasser, Silage, Kraftstoff …), sind keine Wasserentnahmestellen
  und werden entfernt. Tanks ohne Inhaltsangabe bleiben sichtbar,
  werden aber als „Inhalt unbekannt“ gekennzeichnet.
* Als Umriss erfasste Objekte (Linien, Flächen) werden auf einen Punkt
  in ihrer Mitte reduziert. Sonst zeichnet die Karte an jedem Eckpunkt
  einen eigenen Kreis.
"""

from __future__ import annotations

from typing import Any


WATER_CONTENTS = {"water", "fire_water", "firewater"}

UNKNOWN_TANK_LABEL = "Lagertank (Inhalt unbekannt)"
WATER_TANK_LABEL = "Wasserbehälter"
DRINKING_WATER_LABEL = "Trinkwasserstelle"


def _flatten(coordinates: Any) -> list[tuple[float, float]]:
    if (
        isinstance(coordinates, (list, tuple))
        and len(coordinates) >= 2
        and all(isinstance(value, (int, float)) for value in coordinates[:2])
    ):
        return [(float(coordinates[0]), float(coordinates[1]))]
    points: list[tuple[float, float]] = []
    if isinstance(coordinates, (list, tuple)):
        for item in coordinates:
            points.extend(_flatten(item))
    return points


def _center_point(geometry: dict) -> dict | None:
    geometry_type = geometry.get("type")
    coordinates = geometry.get("coordinates")
    if geometry_type == "Polygon" and coordinates:
        # Nur der Außenring bestimmt die Mitte.
        coordinates = coordinates[0]
    points = _flatten(coordinates)
    if len(points) > 1 and points[0] == points[-1]:
        # Geschlossene Ringe nennen den Startpunkt doppelt.
        points = points[:-1]
    if not points:
        return None
    lon = sum(point[0] for point in points) / len(points)
    lat = sum(point[1] for point in points) / len(points)
    return {"type": "Point", "coordinates": [round(lon, 7), round(lat, 7)]}


def _tags(feature: dict) -> dict:
    tags = (feature.get("properties") or {}).get("all_tags")
    return tags if isinstance(tags, dict) else {}


def is_water_source(feature: dict) -> bool:
    content = _tags(feature).get("content")
    return content is None or str(content).strip().lower() in WATER_CONTENTS


def _label(feature: dict) -> str | None:
    # Nur die Sammelkategorie „Sonstige“ bekommt neue Bezeichnungen;
    # Löschwasserbehälter, Brunnen usw. behalten ihre eigene.
    if (feature.get("properties") or {}).get("category") != "other":
        return None
    tags = _tags(feature)
    if tags.get("man_made") == "storage_tank":
        return WATER_TANK_LABEL if tags.get("content") else UNKNOWN_TANK_LABEL
    if tags.get("amenity") == "drinking_water":
        return DRINKING_WATER_LABEL
    return None


def normalize_feature(feature: dict) -> dict | None:
    if not is_water_source(feature):
        return None
    geometry = feature.get("geometry") or {}
    if geometry.get("type") != "Point":
        point = _center_point(geometry)
        if point is None:
            return None
        properties = dict(feature.get("properties") or {})
        properties["lon"], properties["lat"] = point["coordinates"]
        feature = {**feature, "geometry": point, "properties": properties}
    label = _label(feature)
    if label:
        feature = {
            **feature,
            "properties": {**feature.get("properties", {}), "type_de": label},
        }
    return feature


def normalize_layer(data: dict) -> dict:
    features = []
    for feature in data.get("features") or []:
        normalized = normalize_feature(feature)
        if normalized is not None:
            # Rohe OSM-Tags werden nur für die Filterung gebraucht. MapLibre 6
            # kodiert verschachtelte Werte gesondert; ausgeliefert werden sie
            # deshalb nicht.
            properties = dict(normalized.get("properties") or {})
            properties.pop("all_tags", None)
            features.append({**normalized, "properties": properties})
    return {**data, "features": features}
