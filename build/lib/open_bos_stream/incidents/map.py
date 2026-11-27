"""Einsatzkarte: Einsatzort und Quadranten (Suchabschnitte).

Jede Änderung erhöht ``incidents.map_revision``. Geöffnete Karten fragen
alle paar Sekunden nur diesen Zähler ab und laden die Quadranten erst bei
einer Änderung neu – so sehen alle Beteiligten neue Quadranten sofort.
"""

from __future__ import annotations

import json
import math
import string

from sqlalchemy import delete, insert, select, update

from open_bos_stream.db.schema import MAP_ITEM_STATUS, incident_map_items, incidents
from open_bos_stream.incidents.service import (
    IncidentError,
    IncidentService,
    iso,
    local_now,
)

MAX_ITEMS = 300
MAX_GRID = 12
MAX_POINTS = 200
# Größtes zulässiges Raster bzw. größte Fläche (etwa 30 × 30 km).
MAX_SPAN_DEGREES = 0.3


def _point(value) -> tuple[float, float]:
    try:
        lon, lat = float(value[0]), float(value[1])
    except (TypeError, ValueError, IndexError) as exc:
        raise IncidentError("Ungültige Koordinate.") from exc
    if not (-180 <= lon <= 180 and -90 <= lat <= 90) or math.isnan(lon) or math.isnan(lat):
        raise IncidentError("Ungültige Koordinate.")
    return round(lon, 7), round(lat, 7)


def clean_polygon(geometry) -> dict:
    """Einfaches Polygon (ein Ring) prüfen und schließen."""

    if not isinstance(geometry, dict) or geometry.get("type") != "Polygon":
        raise IncidentError("Quadranten müssen Flächen (Polygone) sein.")
    rings = geometry.get("coordinates")
    if not isinstance(rings, list) or len(rings) != 1 or not isinstance(rings[0], list):
        raise IncidentError("Ungültige Fläche.")
    points = [_point(item) for item in rings[0]]
    if len(points) > 1 and points[0] == points[-1]:
        points = points[:-1]
    if len(points) < 3:
        raise IncidentError("Eine Fläche braucht mindestens drei Punkte.")
    if len(points) > MAX_POINTS:
        raise IncidentError(f"Höchstens {MAX_POINTS} Punkte je Fläche.")
    lons = [point[0] for point in points]
    lats = [point[1] for point in points]
    if max(lons) - min(lons) > MAX_SPAN_DEGREES or max(lats) - min(lats) > MAX_SPAN_DEGREES:
        raise IncidentError("Die Fläche ist zu groß (höchstens etwa 30 × 30 km).")
    return {"type": "Polygon", "coordinates": [[list(point) for point in [*points, points[0]]]]}


def column_label(index: int) -> str:
    letters = string.ascii_uppercase
    return letters[index] if index < 26 else letters[index // 26 - 1] + letters[index % 26]


class IncidentMap:
    def __init__(self, incidents_service: IncidentService) -> None:
        self.incidents = incidents_service

    @property
    def _engine(self):
        return self.incidents.org.db.engine

    # -----------------------------------------------------

    def revision(self, incident_id: int) -> int | None:
        with self._engine.connect() as connection:
            row = connection.execute(
                select(incidents.c.map_revision).where(incidents.c.id == incident_id)
            ).first()
        return None if row is None else int(row.map_revision or 0)

    def items(self, incident_id: int) -> list[dict]:
        with self._engine.connect() as connection:
            rows = connection.execute(
                select(incident_map_items)
                .where(incident_map_items.c.incident_id == incident_id)
                .order_by(incident_map_items.c.name, incident_map_items.c.id)
            ).all()
        result = []
        for row in rows:
            item = dict(row._mapping)
            item["geometry"] = json.loads(item["geometry"])
            item["status_label"] = MAP_ITEM_STATUS.get(item["status"], item["status"])
            result.append(item)
        return sorted(result, key=lambda item: _natural(item["name"]))

    def state(self, incident: dict) -> dict:
        return {
            "incident_id": incident["id"],
            "revision": self.revision(incident["id"]) or 0,
            "position": (
                {"latitude": incident["latitude"], "longitude": incident["longitude"]}
                if incident.get("latitude") is not None
                else None
            ),
            "items": self.items(incident["id"]),
            "statuses": MAP_ITEM_STATUS,
        }

    # -----------------------------------------------------

    @staticmethod
    def bump(connection, incident_id: int) -> None:
        connection.execute(
            update(incidents)
            .where(incidents.c.id == incident_id)
            .values(
                map_revision=incidents.c.map_revision + 1,
                updated_at=iso(local_now()),
            )
        )

    def _names(self, connection, incident_id: int) -> set[str]:
        return {
            row.name.casefold()
            for row in connection.execute(
                select(incident_map_items.c.name).where(
                    incident_map_items.c.incident_id == incident_id
                )
            )
        }

    def _count(self, connection, incident_id: int) -> int:
        return len(connection.execute(
            select(incident_map_items.c.id).where(incident_map_items.c.incident_id == incident_id)
        ).all())

    @staticmethod
    def _clean_text(value, limit: int) -> str:
        return " ".join(str(value or "").split())[:limit]

    def add_item(
        self,
        user: dict,
        incident_id: int,
        *,
        name: str,
        geometry: dict,
        status: str = "open",
        assignee: str = "",
        note: str = "",
    ) -> dict:
        self.incidents.require(user, incident_id, edit=True)
        name = self._clean_text(name, 40)
        if not name:
            raise IncidentError("Bitte einen Namen für den Quadranten angeben.")
        if status not in MAP_ITEM_STATUS:
            raise IncidentError("Unbekannter Status.")
        polygon = clean_polygon(geometry)
        actor = user.get("display_name") or user["username"]
        now = iso(local_now())
        with self.incidents._lock, self._engine.begin() as connection:
            if name.casefold() in self._names(connection, incident_id):
                raise IncidentError(f"Den Namen „{name}“ gibt es in diesem Einsatz schon.")
            if self._count(connection, incident_id) >= MAX_ITEMS:
                raise IncidentError(f"Höchstens {MAX_ITEMS} Quadranten je Einsatz.")
            item_id = connection.execute(
                insert(incident_map_items).values(
                    incident_id=incident_id,
                    name=name,
                    geometry=json.dumps(polygon),
                    status=status,
                    assignee=self._clean_text(assignee, 80),
                    note=str(note or "").strip()[:300],
                    created_by=actor,
                    created_at=now,
                    updated_by=actor,
                    updated_at=now,
                )
            ).inserted_primary_key[0]
            self.bump(connection, incident_id)
            self.incidents._log(connection, incident_id, actor, "map", f"Quadrant {name} gezeichnet")
        return next(item for item in self.items(incident_id) if item["id"] == item_id)

    def add_grid(
        self,
        user: dict,
        incident_id: int,
        *,
        west: float,
        south: float,
        east: float,
        north: float,
        rows: int,
        columns: int,
        prefix: str = "",
    ) -> list[dict]:
        """Rechteck in gleich große Quadranten teilen (A1 oben links)."""

        self.incidents.require(user, incident_id, edit=True)
        west, south = _point((min(west, east), min(south, north)))
        east, north = _point((max(west, east), max(south, north)))
        if not (1 <= rows <= MAX_GRID and 1 <= columns <= MAX_GRID):
            raise IncidentError(f"Raster mit 1 bis {MAX_GRID} Zeilen und Spalten.")
        if east - west < 1e-5 or north - south < 1e-5:
            raise IncidentError("Das Rechteck ist zu klein.")
        if east - west > MAX_SPAN_DEGREES or north - south > MAX_SPAN_DEGREES:
            raise IncidentError("Das Raster ist zu groß (höchstens etwa 30 × 30 km).")
        prefix = self._clean_text(prefix, 10)
        width = (east - west) / columns
        height = (north - south) / rows
        cells = []
        for row in range(rows):
            for column in range(columns):
                left = west + column * width
                top = north - row * height
                name = f"{prefix}{column_label(column)}{row + 1}"
                cells.append((name, {
                    "type": "Polygon",
                    "coordinates": [[
                        [left, top], [left + width, top], [left + width, top - height],
                        [left, top - height], [left, top],
                    ]],
                }))
        actor = user.get("display_name") or user["username"]
        now = iso(local_now())
        with self.incidents._lock, self._engine.begin() as connection:
            existing = self._names(connection, incident_id)
            clash = [name for name, _ in cells if name.casefold() in existing]
            if clash:
                raise IncidentError(
                    f"Namen wie „{clash[0]}“ gibt es schon. Bitte ein Präfix angeben "
                    "(z. B. „N-“ für ein zweites Raster)."
                )
            if self._count(connection, incident_id) + len(cells) > MAX_ITEMS:
                raise IncidentError(f"Höchstens {MAX_ITEMS} Quadranten je Einsatz.")
            for name, polygon in cells:
                connection.execute(
                    insert(incident_map_items).values(
                        incident_id=incident_id,
                        name=name,
                        geometry=json.dumps(clean_polygon(polygon)),
                        status="open",
                        created_by=actor,
                        created_at=now,
                        updated_by=actor,
                        updated_at=now,
                    )
                )
            self.bump(connection, incident_id)
            self.incidents._log(
                connection, incident_id, actor, "map",
                f"Raster {rows} × {columns} angelegt ({cells[0][0]} bis {cells[-1][0]})",
            )
        return self.items(incident_id)

    def update_item(self, user: dict, incident_id: int, item_id: int, **changes) -> dict:
        self.incidents.require(user, incident_id, edit=True)
        current = next((item for item in self.items(incident_id) if item["id"] == item_id), None)
        if current is None:
            raise LookupError("Quadrant nicht gefunden.")
        values = {}
        if changes.get("name") is not None:
            name = self._clean_text(changes["name"], 40)
            if not name:
                raise IncidentError("Der Name darf nicht leer sein.")
            values["name"] = name
        if changes.get("status") is not None:
            if changes["status"] not in MAP_ITEM_STATUS:
                raise IncidentError("Unbekannter Status.")
            values["status"] = changes["status"]
        if changes.get("assignee") is not None:
            values["assignee"] = self._clean_text(changes["assignee"], 80)
        if changes.get("note") is not None:
            values["note"] = str(changes["note"]).strip()[:300]
        if changes.get("geometry") is not None:
            values["geometry"] = json.dumps(clean_polygon(changes["geometry"]))
        if not values:
            return current
        actor = user.get("display_name") or user["username"]
        values.update(updated_by=actor, updated_at=iso(local_now()))
        with self.incidents._lock, self._engine.begin() as connection:
            if "name" in values and values["name"].casefold() != current["name"].casefold():
                if values["name"].casefold() in self._names(connection, incident_id):
                    raise IncidentError(f"Den Namen „{values['name']}“ gibt es in diesem Einsatz schon.")
            connection.execute(
                update(incident_map_items).where(incident_map_items.c.id == item_id).values(**values)
            )
            self.bump(connection, incident_id)
            label = values.get("name", current["name"])
            notes = []
            if "status" in values and values["status"] != current["status"]:
                notes.append(MAP_ITEM_STATUS[values["status"]])
            if "assignee" in values and values["assignee"] != current["assignee"]:
                notes.append(f"zuständig: {values['assignee'] or '–'}")
            if "name" in values and values["name"] != current["name"]:
                notes.append(f"umbenannt (vorher {current['name']})")
            if notes:
                self.incidents._log(connection, incident_id, actor, "map", f"Quadrant {label}: " + ", ".join(notes))
        return next(item for item in self.items(incident_id) if item["id"] == item_id)

    def delete_item(self, user: dict, incident_id: int, item_id: int) -> None:
        self.incidents.require(user, incident_id, edit=True)
        current = next((item for item in self.items(incident_id) if item["id"] == item_id), None)
        if current is None:
            raise LookupError("Quadrant nicht gefunden.")
        actor = user.get("display_name") or user["username"]
        with self.incidents._lock, self._engine.begin() as connection:
            connection.execute(delete(incident_map_items).where(incident_map_items.c.id == item_id))
            self.bump(connection, incident_id)
            self.incidents._log(connection, incident_id, actor, "map", f"Quadrant {current['name']} gelöscht")


def _natural(name: str) -> tuple:
    """A2 vor A10: Zahlen im Namen numerisch sortieren."""

    import re

    return tuple(
        (0, int(part), "") if part.isdigit() else (1, 0, part.casefold())
        for part in re.split(r"(\d+)", name)
        if part
    )
