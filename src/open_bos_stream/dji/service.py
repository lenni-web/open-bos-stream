"""Geräte, Live-Zustand, Einsatzzuordnung und Aufzeichnung.

Jede Nachricht einer Drohne und ihrer Fernsteuerung wird unverändert
gespeichert. Gehört die Drohne zu einem laufenden Einsatz, bleiben die
Daten mit dem Einsatz erhalten. Ohne Einsatz werden sie nach
``BUFFER_HOURS`` gelöscht; bis dahin lassen sie sich bei einer späteren
Zuordnung nachtragen (ab Alarmzeit).
"""

from __future__ import annotations

import csv
import io
import json
import logging
import threading
from collections.abc import Iterator
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, insert, select, update

from open_bos_stream.db.schema import dji_devices, drone_records, incident_drones, incidents
from open_bos_stream.dji.telemetry import extract, model_name, parse_topic
from open_bos_stream.incidents.service import (
    IncidentAccessError,
    IncidentError,
    IncidentService,
    iso,
    local_now,
    parse_time,
)


logger = logging.getLogger(__name__)

BUFFER_HOURS = 24
ONLINE_SECONDS = 30
PERSON_SECONDS = 120
MAX_PAYLOAD = 256 * 1024
TRACK_LIMIT = 2000
SEEN_INTERVAL = timedelta(seconds=10)
CSV_COLUMNS = (
    "zeit", "seriennummer", "drohne", "breite", "laenge", "hoehe_ueber_start_m",
    "akku_prozent", "abstand_startpunkt_m", "flugzustand",
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def stamp(value: datetime) -> str:
    """Einheitlich in UTC, damit Zeitangaben als Text vergleichbar sind."""

    return value.astimezone(timezone.utc).isoformat(timespec="milliseconds")


def _sees_all(user: dict) -> bool:
    return bool(user.get("platform_admin") or user.get("server_admin")) or "org_view" not in user


class DroneService:
    def __init__(self, incident_service: IncidentService, clock=utc_now) -> None:
        self.incidents = incident_service
        self.org = incident_service.org
        self.clock = clock
        self._lock = threading.RLock()
        self._live: dict[str, dict] = {}
        self._persons: dict[int, dict[str, dict]] = {}
        self._seen: dict[str, datetime] = {}
        self._purged: datetime | None = None

    @property
    def _engine(self):
        return self.org.db.engine

    # -----------------------------------------------------
    # Nachrichten
    # -----------------------------------------------------

    def handle(self, topic: str, payload: bytes | str) -> list[tuple[str, str]]:
        """Eine Broker-Nachricht verarbeiten; Rückgabe sind Antworten."""

        parsed = parse_topic(topic)
        if parsed is None or len(payload) > MAX_PAYLOAD:
            return []
        try:
            text = payload.decode("utf-8") if isinstance(payload, bytes) else payload
            message = json.loads(text)
        except (UnicodeDecodeError, ValueError, RecursionError):
            return []
        if not isinstance(message, dict):
            return []
        serial, channel = parsed
        data = message.get("data")
        data = data if isinstance(data, dict) else {}
        now = self.clock()
        with self._lock:
            self._purge(now)
            replies = self._replies(serial, channel, message)
            if channel == "status":
                self._topology(serial, message, data, now)
                device = self.device(serial)
            else:
                device = self._ensure(serial, message.get("gateway"), now)
            if device is None or device["blocked"]:
                return replies
            values = extract(data) if channel in ("osd", "state") else {}
            self._remember(serial, values, now)
            incident_id = self._incident_for(device)
            if incident_id is None and channel == "osd" and device["kind"] == "aircraft":
                incident_id = self._auto_assign(device)
            self._record(incident_id, serial, topic, text, values, now)
        return replies

    def _replies(self, serial: str, channel: str, message: dict) -> list[tuple[str, str]]:
        envelope = {
            key: message.get(key) for key in ("tid", "bid", "method") if message.get(key) is not None
        } | {"timestamp": int(self.clock().timestamp() * 1000)}
        if channel == "status":
            return [(f"sys/product/{serial}/status_reply", json.dumps(envelope | {"data": {"result": 0}}))]
        if channel == "events" and message.get("need_reply") == 1:
            return [(f"thing/product/{serial}/events_reply", json.dumps(envelope | {"data": {"result": 0}}))]
        return []

    def _topology(self, serial: str, message: dict, data: dict, now: datetime) -> None:
        if message.get("method") != "update_topo":
            return
        self._upsert(serial, "controller", data, None, now)
        children = data.get("sub_devices")
        present = set()
        for child in children if isinstance(children, list) else []:
            if not isinstance(child, dict):
                continue
            parsed = parse_topic(f"thing/product/{child.get('sn')}/osd")
            if parsed is None or child.get("sn") is None:
                continue
            present.add(parsed[0])
            self._upsert(parsed[0], "aircraft", child, serial, now)
        # Abgemeldete Drohnen dieser Fernsteuerung sofort als offline führen.
        for device in self._all_devices():
            if device["gateway_serial"] == serial and device["serial"] not in present:
                self._live.pop(device["serial"], None)

    def _upsert(self, serial: str, kind: str, data: dict, gateway: str | None, now: datetime) -> None:
        values = {"kind": kind, "last_seen": stamp(now)}
        if isinstance(data.get("type"), int):
            values["model_type"] = data["type"]
            values["model_sub_type"] = data.get("sub_type") if isinstance(data.get("sub_type"), int) else 0
        if gateway:
            values["gateway_serial"] = gateway
        with self._engine.begin() as connection:
            exists = connection.execute(
                select(dji_devices.c.serial).where(dji_devices.c.serial == serial)
            ).first()
            if exists:
                connection.execute(update(dji_devices).where(dji_devices.c.serial == serial).values(**values))
            else:
                connection.execute(insert(dji_devices).values(serial=serial, first_seen=stamp(now), **values))

    def _ensure(self, serial: str, gateway, now: datetime) -> dict | None:
        gateway = gateway if isinstance(gateway, str) and gateway != serial else None
        device = self.device(serial)
        if device is None:
            kind = "aircraft" if gateway else "controller"
            self._upsert(serial, kind, {}, gateway[:64] if gateway else None, now)
        elif now - self._seen.get(serial, datetime.min.replace(tzinfo=timezone.utc)) >= SEEN_INTERVAL:
            self._upsert(serial, device["kind"], {}, gateway[:64] if gateway else None, now)
            self._seen[serial] = now
        else:
            return device
        return self.device(serial)

    def _remember(self, serial: str, values: dict, now: datetime) -> None:
        entry = self._live.get(serial)
        if entry is None or now - entry["at"] > timedelta(seconds=ONLINE_SECONDS):
            entry = self._live[serial] = {"values": {}, "at": now}
        entry["values"].update(values)
        entry["at"] = now

    def _record(self, incident_id, serial, topic, text, values, now) -> None:
        with self._engine.begin() as connection:
            connection.execute(
                insert(drone_records).values(
                    incident_id=incident_id,
                    serial=serial,
                    received_at=stamp(now),
                    topic=topic[:160],
                    latitude=values.get("latitude"),
                    longitude=values.get("longitude"),
                    elevation=values.get("elevation"),
                    battery=values.get("battery"),
                    home_distance=values.get("home_distance"),
                    payload=text,
                )
            )

    def _purge(self, now: datetime) -> None:
        if self._purged and now - self._purged < timedelta(hours=1):
            return
        self._purged = now
        with self._engine.begin() as connection:
            connection.execute(
                delete(drone_records).where(
                    drone_records.c.incident_id.is_(None),
                    drone_records.c.received_at < stamp(now - timedelta(hours=BUFFER_HOURS)),
                )
            )

    def purge(self) -> None:
        with self._lock:
            self._purge(self.clock())

    # -----------------------------------------------------
    # Zuordnung zum Einsatz
    # -----------------------------------------------------

    def _active(self, connection, serials: list[str] | None = None) -> list:
        query = (
            select(incident_drones)
            .join(incidents, incidents.c.id == incident_drones.c.incident_id)
            .where(incident_drones.c.removed_at.is_(None), incidents.c.status == "running")
            .order_by(incident_drones.c.id)
        )
        if serials is not None:
            query = query.where(incident_drones.c.serial.in_(serials))
        return connection.execute(query).all()

    def _incident_for(self, device: dict) -> int | None:
        """Laufender Einsatz der Drohne bzw. der Drohne dieser Fernsteuerung."""

        with self._engine.connect() as connection:
            serials = [device["serial"]]
            if device["kind"] == "controller":
                serials = [
                    row.serial for row in connection.execute(
                        select(dji_devices.c.serial).where(dji_devices.c.gateway_serial == device["serial"])
                    )
                ]
            rows = self._active(connection, serials)
        return rows[-1].incident_id if rows else None

    def _auto_assign(self, device: dict) -> int | None:
        """Nur eindeutig: genau ein laufender Einsatz der Wehr."""

        organization_id = device["organization_id"]
        if not organization_id:
            return None
        running = [
            item for item in self.incidents.list(status="running")
            if organization_id in item["organization_ids"]
        ]
        if len(running) != 1:
            return None
        incident = running[0]
        with self._engine.connect() as connection:
            # Von Hand herausgenommene Drohnen nicht erneut zuordnen.
            earlier = connection.execute(
                select(incident_drones.c.id).where(
                    incident_drones.c.incident_id == incident["id"],
                    incident_drones.c.serial == device["serial"],
                )
            ).first()
        if earlier:
            return None
        self._add(incident, device, "System")
        return incident["id"]

    def _add(self, incident: dict, device: dict, actor: str) -> None:
        serials = [device["serial"]] + ([device["gateway_serial"]] if device["gateway_serial"] else [])
        name = device["name"] or device["model"]
        since = stamp(parse_time(incident["alarm_at"]))
        with self._engine.begin() as connection:
            removed = connection.execute(
                select(func.max(incident_drones.c.removed_at)).where(
                    incident_drones.c.incident_id == incident["id"],
                    incident_drones.c.serial == device["serial"],
                )
            ).scalar_one()
            if removed:
                since = max(since, stamp(parse_time(removed)))
            connection.execute(
                insert(incident_drones).values(
                    incident_id=incident["id"],
                    serial=device["serial"],
                    name=name,
                    added_at=iso(local_now()),
                )
            )
            # Schon empfangene Daten dieses Einsatzes nachtragen.
            connection.execute(
                update(drone_records)
                .where(
                    drone_records.c.incident_id.is_(None),
                    drone_records.c.serial.in_(serials),
                    drone_records.c.received_at >= since,
                )
                .values(incident_id=incident["id"])
            )
        self.incidents.record(
            incident["id"], f"Drohnendaten von „{name}“ werden aufgezeichnet",
            actor=actor, kind="source",
        )

    def assign(self, user: dict, incident_id: int, serial: str) -> None:
        incident = self.incidents.require(user, incident_id, edit=True)
        if incident["status"] != "running":
            raise IncidentError("Drohnen lassen sich nur laufenden Einsätzen zuordnen.")
        device = self.device(serial)
        if device is None or device["kind"] != "aircraft" or not self.can_see(user, device):
            raise LookupError("Drohne nicht gefunden.")
        if device["blocked"]:
            raise IncidentError("Diese Drohne ist gesperrt.")
        if not device["organization_id"]:
            raise IncidentError("Bitte die Drohne zuerst einer Wehr zuordnen.")
        if not (_sees_all(user) or device["organization_id"] in set(user.get("org_operate") or [])):
            raise IncidentAccessError("Zuordnen darf das Drohnenteam der Wehr dieser Drohne.")
        with self._lock:
            with self._engine.connect() as connection:
                if self._active(connection, [serial]):
                    raise IncidentError("Diese Drohne ist bereits in einem laufenden Einsatz.")
            self._add(incident, device, user.get("display_name") or user["username"])

    def release(self, user: dict, incident_id: int, serial: str) -> None:
        self.incidents.require(user, incident_id, edit=True)
        with self._lock:
            with self._engine.begin() as connection:
                row = connection.execute(
                    select(incident_drones).where(
                        incident_drones.c.incident_id == incident_id,
                        incident_drones.c.serial == serial,
                        incident_drones.c.removed_at.is_(None),
                    )
                ).first()
                if row is None:
                    raise LookupError("Drohne ist diesem Einsatz nicht zugeordnet.")
                connection.execute(
                    update(incident_drones)
                    .where(incident_drones.c.id == row.id)
                    .values(removed_at=iso(local_now()))
                )
        self.incidents.record(
            incident_id, f"Aufzeichnung der Drohnendaten von „{row.name}“ beendet",
            actor=user.get("display_name") or user["username"], kind="source",
        )

    # -----------------------------------------------------
    # Geräte
    # -----------------------------------------------------

    @staticmethod
    def _decorate(row) -> dict:
        item = dict(row._mapping)
        item["model"] = model_name(item["model_type"], item["model_sub_type"])
        return item

    def _all_devices(self) -> list[dict]:
        with self._engine.connect() as connection:
            rows = connection.execute(
                select(dji_devices).order_by(dji_devices.c.kind, dji_devices.c.name, dji_devices.c.serial)
            ).all()
        return [self._decorate(row) for row in rows]

    def device(self, serial: str) -> dict | None:
        with self._engine.connect() as connection:
            row = connection.execute(select(dji_devices).where(dji_devices.c.serial == serial)).first()
        return self._decorate(row) if row else None

    @staticmethod
    def can_see(user: dict | None, device: dict) -> bool:
        if not user or user.get("role") == "guest":
            return False
        if _sees_all(user):
            return True
        if device["organization_id"] is None:
            # Neue Geräte übernimmt ein Admin in seine Wehr.
            return bool(user.get("org_admin"))
        return device["organization_id"] in set(user.get("org_view") or [])

    @staticmethod
    def can_manage(user: dict, device: dict) -> bool:
        if _sees_all(user):
            return user.get("role") in ("admin", "superadmin") or bool(user.get("server_admin"))
        administered = set(user.get("org_admin") or [])
        if device["organization_id"] is None:
            return bool(administered)
        return device["organization_id"] in administered

    def _state(self, serial: str, now: datetime) -> dict:
        entry = self._live.get(serial)
        if entry is None or now - entry["at"] > timedelta(seconds=ONLINE_SECONDS):
            return {"online": False}
        return dict(entry["values"]) | {"online": True, "updated_at": stamp(entry["at"])}

    def devices(self, user: dict) -> list[dict]:
        now = self.clock()
        with self._lock:
            return [
                device | {"state": self._state(device["serial"], now), "can_manage": self.can_manage(user, device)}
                for device in self._all_devices() if self.can_see(user, device)
            ]

    def update_device(self, user: dict, serial: str, **changes) -> None:
        device = self.device(serial)
        if device is None or not self.can_see(user, device):
            raise LookupError("Gerät nicht gefunden.")
        if not self.can_manage(user, device):
            raise IncidentAccessError("Geräte verwalten Admins der Wehr.")
        values = {}
        if changes.get("name") is not None:
            values["name"] = " ".join(str(changes["name"]).split())[:80]
        if "organization_id" in changes:
            organization_id = changes["organization_id"]
            if organization_id is not None:
                organization = self.org.organization(organization_id)
                if organization is None or organization["archived"]:
                    raise IncidentError("Wehr nicht gefunden.")
            if not _sees_all(user) and organization_id not in set(user.get("org_admin") or []):
                raise IncidentAccessError("Zuordnen geht nur zu selbst verwalteten Wehren.")
            values["organization_id"] = organization_id
        if changes.get("blocked") is not None:
            values["blocked"] = bool(changes["blocked"])
        if not values:
            return
        with self._lock:
            with self._engine.begin() as connection:
                connection.execute(update(dji_devices).where(dji_devices.c.serial == serial).values(**values))
            if values.get("blocked"):
                self._live.pop(serial, None)
        self.org.audit(
            user.get("display_name") or user["username"], "DJI-Gerät geändert",
            f"{values.get('name') or device['name'] or device['model']} ({serial})",
            values.get("organization_id", device["organization_id"]),
        )

    def delete_device(self, user: dict, serial: str) -> None:
        """Gerät vergessen; Aufzeichnungen der Einsätze bleiben erhalten."""

        device = self.device(serial)
        if device is None or not self.can_see(user, device):
            raise LookupError("Gerät nicht gefunden.")
        if not self.can_manage(user, device):
            raise IncidentAccessError("Geräte verwalten Admins der Wehr.")
        with self._lock:
            with self._engine.begin() as connection:
                if self._active(connection, [serial]):
                    raise IncidentError("Die Drohne ist gerade in einem Einsatz.")
                connection.execute(delete(dji_devices).where(dji_devices.c.serial == serial))
            self._live.pop(serial, None)
        self.org.audit(
            user.get("display_name") or user["username"], "DJI-Gerät entfernt",
            f"{device['name'] or device['model']} ({serial})", device["organization_id"],
        )

    # -----------------------------------------------------
    # Standorte von Personen (nur im Speicher, ohne Spur)
    # -----------------------------------------------------

    def share_location(self, user: dict, incident_id: int, latitude: float, longitude: float,
                       accuracy: float | None = None) -> None:
        incident = self.incidents.require(user, incident_id)
        if incident["status"] != "running":
            raise IncidentError("Standorte lassen sich nur in laufenden Einsätzen teilen.")
        if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
            raise IncidentError("Ungültige Koordinate.")
        with self._lock:
            self._persons.setdefault(incident_id, {})[user["username"]] = {
                "name": user.get("display_name") or user["username"],
                "latitude": round(latitude, 6),
                "longitude": round(longitude, 6),
                "accuracy": round(accuracy) if accuracy is not None and 0 <= accuracy < 100_000 else None,
                "at": self.clock(),
            }

    def stop_sharing(self, user: dict, incident_id: int) -> None:
        with self._lock:
            self._persons.get(incident_id, {}).pop(user["username"], None)

    def persons(self, incident_id: int) -> list[dict]:
        limit = self.clock() - timedelta(seconds=PERSON_SECONDS)
        with self._lock:
            entries = self._persons.get(incident_id, {})
            for key in [key for key, entry in entries.items() if entry["at"] < limit]:
                del entries[key]
            return [entry | {"at": stamp(entry["at"])} for entry in entries.values()]

    # -----------------------------------------------------
    # Auswertung
    # -----------------------------------------------------

    def assignments(self, incident_id: int) -> list[dict]:
        with self._engine.connect() as connection:
            rows = connection.execute(
                select(incident_drones)
                .where(incident_drones.c.incident_id == incident_id)
                .order_by(incident_drones.c.id)
            ).all()
        return [dict(row._mapping) | {"active": row.removed_at is None} for row in rows]

    def positions(self, incident: dict, *, after: int = 0) -> dict:
        """Drohnen des Einsatzes mit Live-Werten und Flugspur ab ``after``."""

        now = self.clock()
        drones: dict[str, dict] = {}
        for entry in self.assignments(incident["id"]):
            active = entry["active"] and incident["status"] == "running"
            drones[entry["serial"]] = {
                "serial": entry["serial"], "name": entry["name"], "active": active,
                "track": [], "state": {"online": False}, "controller": None,
            }
        last = after
        with self._engine.connect() as connection:
            for serial, drone in drones.items():
                rows = connection.execute(
                    select(drone_records.c.id, drone_records.c.longitude, drone_records.c.latitude)
                    .where(
                        drone_records.c.incident_id == incident["id"],
                        drone_records.c.serial == serial,
                        drone_records.c.latitude.is_not(None),
                        drone_records.c.id > after,
                    )
                    .order_by(drone_records.c.id)
                ).all()
                if not rows:
                    continue
                last = max(last, rows[-1].id)
                step = max(1, -(-len(rows) // TRACK_LIMIT))
                points = rows[::step]
                if points[-1].id != rows[-1].id:
                    points.append(rows[-1])
                drone["track"] = [[row.longitude, row.latitude] for row in points]
        for serial, drone in drones.items():
            if not drone["active"]:
                continue
            device = self.device(serial)
            if device is None:
                continue
            drone["name"] = device["name"] or drone["name"]
            with self._lock:
                drone["state"] = self._state(serial, now)
                if device["gateway_serial"]:
                    state = self._state(device["gateway_serial"], now)
                    if "latitude" in state:
                        drone["controller"] = {key: state.get(key) for key in ("latitude", "longitude", "battery")}
        return {"drones": list(drones.values()), "persons": self.persons(incident["id"]), "last": last}

    def summary(self, incident_id: int) -> list[dict]:
        """Kennzahlen je Gerät aus der Aufzeichnung."""

        names = {item["serial"]: item["name"] for item in self.assignments(incident_id)}
        with self._engine.connect() as connection:
            rows = connection.execute(
                select(
                    drone_records.c.serial,
                    func.count().label("records"),
                    func.min(drone_records.c.received_at).label("first"),
                    func.max(drone_records.c.received_at).label("last"),
                    func.max(drone_records.c.elevation).label("max_elevation"),
                    func.max(drone_records.c.home_distance).label("max_home_distance"),
                    func.min(drone_records.c.battery).label("min_battery"),
                )
                .where(drone_records.c.incident_id == incident_id)
                .group_by(drone_records.c.serial)
            ).all()
        result = []
        for row in rows:
            item = dict(row._mapping)
            device = self.device(row.serial)
            item["aircraft"] = row.serial in names
            item["name"] = names.get(row.serial) or (
                (device["name"] or device["model"]) if device else row.serial
            )
            result.append(item)
        return sorted(result, key=lambda item: (not item["aircraft"], item["name"]))

    def _rows(self, incident_id: int) -> Iterator:
        last = 0
        while True:
            with self._engine.connect() as connection:
                rows = connection.execute(
                    select(drone_records)
                    .where(drone_records.c.incident_id == incident_id, drone_records.c.id > last)
                    .order_by(drone_records.c.id)
                    .limit(500)
                ).all()
            if not rows:
                return
            last = rows[-1].id
            yield from rows

    def export_jsonl(self, incident_id: int) -> Iterator[str]:
        """Vollständige Aufzeichnung, eine Nachricht je Zeile."""

        for row in self._rows(incident_id):
            yield json.dumps({
                "received_at": row.received_at,
                "serial": row.serial,
                "topic": row.topic,
                "payload": json.loads(row.payload),
            }, ensure_ascii=False) + "\n"

    def export_csv(self, incident_id: int) -> Iterator[str]:
        """Flugwerte der Drohnen als Tabelle (Semikolon, für Excel)."""

        names = {item["serial"]: item["name"] for item in self.assignments(incident_id)}

        def line(values) -> str:
            buffer = io.StringIO()
            csv.writer(buffer, delimiter=";").writerow(values)
            return buffer.getvalue()

        def cell(text: str) -> str:
            # Keine Formeln aus Gerätenamen in der Tabellenkalkulation.
            return f"'{text}" if text[:1] in ("=", "+", "-", "@") else text

        yield "﻿" + line(CSV_COLUMNS)
        for row in self._rows(incident_id):
            if row.serial not in names or row.latitude is None:
                continue
            message = json.loads(row.payload)
            yield line((
                parse_time(row.received_at).strftime("%d.%m.%Y %H:%M:%S"),
                cell(row.serial), cell(names[row.serial]), row.latitude, row.longitude,
                row.elevation, row.battery, row.home_distance,
                extract(message.get("data") or {}).get("mode", ""),
            ))
