"""Einsätze: Alarmierung, beteiligte Wehren, Personen, Drohnen, Verlauf.

Ein Einsatz wird von einer Wehr geführt; weitere Wehren können beteiligt
werden. Sehen dürfen ihn alle mit einer Rolle in der führenden oder einer
beteiligten Wehr (Rollen vererben sich im Baum nach unten, eine Rolle auf
Kreisebene sieht also alle Einsätze). Während ein Einsatz läuft, sehen alle
Beteiligten auch die Livebilder der eingesetzten Drohnen – auch wenn diese
einer anderen Wehr gehören.
"""

from __future__ import annotations

import json
import re
import threading
from datetime import datetime, timedelta

from sqlalchemy import delete, insert, select, update

from open_bos_stream.db.schema import (
    INCIDENT_ROLES,
    INCIDENT_STATUS,
    incident_log,
    incident_organizations,
    incident_participants,
    incident_drones,
    incident_sources,
    incidents,
    organizations,
)
from open_bos_stream.org.service import OrgService

MEDIA_NAME = re.compile(
    r"^(?P<kind>recording|snapshot)_(?P<source>.+)_(?P<stamp>\d{8}_\d{6})\.(?:mp4|jpg)$"
)

# Felder, die sich nach dem Anlegen ändern lassen.
EDITABLE_FIELDS = {
    "title": 120,
    "keyword": 80,
    "address": 200,
    "alarm_text": 4000,
    "alerted_units": 300,
    "dispatch_number": 40,
    "summary": 8000,
}


class IncidentError(ValueError):
    """Ungültige Änderung an einem Einsatz."""


class IncidentAccessError(PermissionError):
    """Keine Berechtigung für diesen Einsatz."""


def local_now() -> datetime:
    # Der Prozess läuft in deutscher Zeit (core/timezone.py).
    return datetime.now().astimezone().replace(microsecond=0)


def iso(value: datetime) -> str:
    return value.isoformat(timespec="seconds")


def parse_time(value) -> datetime:
    """Zeitangabe aus der Oberfläche (lokal, ggf. ohne Zeitzone)."""

    if isinstance(value, datetime):
        moment = value
    else:
        text = str(value or "").strip()
        if not text:
            raise IncidentError("Zeitangabe fehlt.")
        try:
            moment = datetime.fromisoformat(text)
        except ValueError as exc:
            raise IncidentError(f"Ungültige Zeitangabe: {text}") from exc
    if moment.tzinfo is None:
        moment = moment.astimezone()
    return moment.astimezone().replace(microsecond=0)


def _unrestricted(user: dict) -> bool:
    """Superadmin bzw. vereinfachte Konten ohne Organisationsdaten."""

    if user.get("role") == "guest":
        return False
    return bool(user.get("platform_admin")) or "org_view" not in user


def _weather_history(stored: str | None) -> list[dict]:
    """Gespeicherte Erfassungen; bis 0.25.4 stand dort nur eine einzelne."""

    try:
        value = json.loads(stored) if stored else []
    except ValueError:
        return []
    if isinstance(value, dict):
        value = [value]
    return [entry for entry in value if isinstance(entry, dict)]


def _weather_log_text(snapshot: dict) -> str:
    """Verlaufseintrag mit den Messwerten zum Zeitpunkt der Erfassung."""

    current = snapshot.get("current") or {}
    values = [
        f"{label} {str(current[key]).replace('.', ',')} {unit}"
        for label, key, unit in (
            ("Wind", "wind_speed_ms", "m/s"),
            ("Böen", "wind_gust_ms", "m/s"),
            ("Temperatur", "temperature_c", "°C"),
            ("Niederschlag", "precipitation_mm_h", "mm/h"),
        )
        if current.get(key) is not None
    ]
    if current.get("visibility_m") is not None:
        values.append(f"Sicht {current['visibility_m'] / 1000:.1f} km".replace(".", ","))
    kp = (snapshot.get("kp") or {}).get("kp")
    if kp is not None:
        values.append(f"Kp-Index {str(kp).replace('.', ',')}")
    level = (snapshot.get("assessment") or {}).get("summary")
    text = "Wetter erfasst" + (f": {level}" if level else "")
    if values:
        text += " · " + ", ".join(values)
    return text


class IncidentService:
    def __init__(self, org: OrgService) -> None:
        self.org = org
        self._lock = threading.RLock()

    @property
    def _engine(self):
        return self.org.db.engine

    # -----------------------------------------------------
    # Lesen
    # -----------------------------------------------------

    def _organizations_of(self, connection, incident_ids: list[int]) -> dict[int, list[dict]]:
        result: dict[int, list[dict]] = {incident_id: [] for incident_id in incident_ids}
        if not incident_ids:
            return result
        rows = connection.execute(
            select(incident_organizations).where(
                incident_organizations.c.incident_id.in_(incident_ids)
            ).order_by(incident_organizations.c.added_at)
        ).all()
        for row in rows:
            result[row.incident_id].append(dict(row._mapping))
        return result

    @staticmethod
    def _decorate(item: dict, involved: list[dict]) -> dict:
        item["organization_ids"] = [item["lead_organization_id"]] + [
            entry["organization_id"] for entry in involved
            if entry["organization_id"] != item["lead_organization_id"]
        ]
        item["involved"] = involved
        item["status_label"] = INCIDENT_STATUS.get(item["status"], item["status"])
        # "weather" bleibt der Stand vom Einsatzbeginn, "weather_history"
        # enthält alle Erfassungen in zeitlicher Reihenfolge.
        history = _weather_history(item.get("weather"))
        item["weather"] = history[0] if history else None
        item["weather_history"] = history
        return item

    def get(self, incident_id: int) -> dict | None:
        with self._engine.connect() as connection:
            row = connection.execute(
                select(incidents).where(incidents.c.id == incident_id)
            ).first()
            if row is None:
                return None
            involved = self._organizations_of(connection, [incident_id])[incident_id]
        return self._decorate(dict(row._mapping), involved)

    def list(self, *, status: str | None = None) -> list[dict]:
        query = select(incidents).order_by(incidents.c.alarm_at.desc())
        if status:
            query = query.where(incidents.c.status == status)
        with self._engine.connect() as connection:
            rows = [dict(row._mapping) for row in connection.execute(query)]
            involved = self._organizations_of(connection, [row["id"] for row in rows])
        return [self._decorate(row, involved[row["id"]]) for row in rows]

    # -----------------------------------------------------
    # Rechte
    # -----------------------------------------------------

    @staticmethod
    def can_view(user: dict | None, incident: dict) -> bool:
        if not user or user.get("role") == "guest":
            return False
        if _unrestricted(user):
            return True
        return bool(set(incident["organization_ids"]) & set(user.get("org_view") or []))

    @staticmethod
    def can_edit(user: dict | None, incident: dict) -> bool:
        """Drohnenteam der führenden oder einer beteiligten Wehr.

        Abgeschlossene Einsätze bearbeiten nur Admins der führenden Wehr.
        """

        if not user or user.get("role") == "guest":
            return False
        if _unrestricted(user) or user.get("server_admin"):
            return True
        if incident["status"] == "closed":
            return incident["lead_organization_id"] in set(user.get("org_admin") or [])
        return bool(set(incident["organization_ids"]) & set(user.get("org_operate") or []))

    @staticmethod
    def can_administer(user: dict | None, incident: dict) -> bool:
        """Abschließen, wieder öffnen, löschen: Admins der führenden Wehr."""

        if not user or user.get("role") == "guest":
            return False
        if _unrestricted(user) or user.get("server_admin"):
            return True
        return incident["lead_organization_id"] in set(user.get("org_admin") or [])

    def visible(self, user: dict, *, status: str | None = None) -> list[dict]:
        return [item for item in self.list(status=status) if self.can_view(user, item)]

    def require(self, user: dict, incident_id: int, *, edit: bool = False) -> dict:
        incident = self.get(incident_id)
        if incident is None or not self.can_view(user, incident):
            raise LookupError("Einsatz nicht gefunden.")
        if edit and not self.can_edit(user, incident):
            raise IncidentAccessError(
                "Bearbeiten dürfen Drohnenteams der beteiligten Wehren"
                + (
                    "; abgeschlossene Einsätze nur Admins der führenden Wehr."
                    if incident["status"] == "closed"
                    else "."
                )
            )
        return incident

    def running_source_ids(self, scope: dict) -> list[str]:
        """Drohnen laufender Einsätze, die dieses Konto sehen darf."""

        view = set(scope.get("org_view") or [])
        if not view:
            return []
        with self._engine.connect() as connection:
            running = connection.execute(
                select(incidents.c.id, incidents.c.lead_organization_id).where(
                    incidents.c.status == "running"
                )
            ).all()
            if not running:
                return []
            ids = [row.id for row in running]
            involved = self._organizations_of(connection, ids)
            visible = [
                row.id for row in running
                if view & ({row.lead_organization_id} | {
                    entry["organization_id"] for entry in involved[row.id]
                })
            ]
            if not visible:
                return []
            rows = connection.execute(
                select(incident_sources.c.source_id).where(
                    incident_sources.c.incident_id.in_(visible),
                    incident_sources.c.removed_at.is_(None),
                )
            ).all()
        return sorted({row.source_id for row in rows})

    # -----------------------------------------------------
    # Kennung
    # -----------------------------------------------------

    def _code(self, connection, alarm_at: datetime, exclude: int | None = None) -> str:
        base = alarm_at.strftime("%Y-%m-%d-%H%M")
        query = select(incidents.c.code).where(incidents.c.code.like(f"{base}%"))
        if exclude is not None:
            query = query.where(incidents.c.id != exclude)
        taken = {row.code for row in connection.execute(query)}
        if base not in taken:
            return base
        number = 2
        while f"{base}-{number}" in taken:
            number += 1
        return f"{base}-{number}"

    # -----------------------------------------------------
    # Anlegen und ändern
    # -----------------------------------------------------

    def _log(self, connection, incident_id: int, actor: str, kind: str, text: str, at: datetime | None = None) -> None:
        # Jede Einsatzänderung kann Rechte berühren (z. B. Drohnen im Einsatz).
        self.org.bump()
        connection.execute(
            insert(incident_log).values(
                incident_id=incident_id,
                at=iso(at or local_now()),
                actor=actor,
                kind=kind,
                text=text[:2000],
            )
        )

    def _touch(self, connection, incident_id: int) -> None:
        connection.execute(
            update(incidents)
            .where(incidents.c.id == incident_id)
            .values(updated_at=iso(local_now()))
        )

    def organization_label(self, organization_id: int | None) -> str:
        """Kurzname bzw. Name einer Wehr („?“, wenn unbekannt)."""

        return self._org_name(organization_id)

    def _org_name(self, organization_id: int | None) -> str:
        org = self.org.organization(organization_id) if organization_id else None
        if not org:
            return "?"
        return org.get("short_name") or org["name"]

    def create(
        self,
        user: dict,
        *,
        lead_organization_id: int,
        alarm_at=None,
        latitude: float | None = None,
        longitude: float | None = None,
        exercise: bool = False,
        **fields,
    ) -> dict:
        if not _unrestricted(user) and lead_organization_id not in set(user.get("org_operate") or []):
            raise IncidentAccessError(
                "Einsätze legt das Drohnenteam der führenden Wehr an."
            )
        lead = self.org.organization(lead_organization_id)
        if lead is None or lead["archived"]:
            raise IncidentError("Führende Wehr nicht gefunden.")
        alarm = parse_time(alarm_at) if alarm_at else local_now()
        now = iso(local_now())
        values = self._clean_fields(fields)
        values.update(self._clean_position(latitude, longitude))
        actor = user.get("display_name") or user["username"]
        # Namen vor der Transaktion lesen: Eine zweite Verbindung innerhalb
        # der Transaktion würde bei SQLite blockieren bzw. zurückrollen.
        lead_name = self._org_name(lead_organization_id)
        with self._lock, self._engine.begin() as connection:
            code = self._code(connection, alarm)
            incident_id = connection.execute(
                insert(incidents).values(
                    code=code,
                    alarm_at=iso(alarm),
                    status="running",
                    exercise=bool(exercise),
                    lead_organization_id=lead_organization_id,
                    created_by=actor,
                    created_at=now,
                    updated_at=now,
                    **values,
                )
            ).inserted_primary_key[0]
            self._log(
                connection,
                incident_id,
                actor,
                "created",
                ("Übung angelegt" if exercise else "Einsatz angelegt")
                + (f" · {values['keyword']}" if values.get("keyword") else "")
                + f" · führende Wehr: {lead_name}",
            )
        return self.get(incident_id)

    @staticmethod
    def _clean_fields(fields: dict) -> dict:
        values = {}
        for key, limit in EDITABLE_FIELDS.items():
            if key in fields and fields[key] is not None:
                text = str(fields[key]).strip()
                if len(text) > limit:
                    raise IncidentError(f"Das Feld „{key}“ ist zu lang (max. {limit} Zeichen).")
                values[key] = text
        return values

    @staticmethod
    def _clean_position(latitude, longitude) -> dict:
        if latitude is None and longitude is None:
            return {}
        if latitude is None or longitude is None:
            raise IncidentError("Breite und Länge gemeinsam angeben.")
        if not (-90 <= float(latitude) <= 90 and -180 <= float(longitude) <= 180):
            raise IncidentError("Ungültige Koordinate.")
        return {"latitude": round(float(latitude), 6), "longitude": round(float(longitude), 6)}

    def update(self, user: dict, incident_id: int, **changes) -> dict:
        incident = self.require(user, incident_id, edit=True)
        actor = user.get("display_name") or user["username"]
        values = self._clean_fields(changes)
        if "latitude" in changes or "longitude" in changes:
            if changes.get("latitude") is None and changes.get("longitude") is None:
                values.update({"latitude": None, "longitude": None})
            else:
                values.update(self._clean_position(changes.get("latitude"), changes.get("longitude")))
        notes = []
        if changes.get("exercise") is not None and bool(changes["exercise"]) != bool(incident.get("exercise")):
            values["exercise"] = bool(changes["exercise"])
            notes.append("Als Übung gekennzeichnet" if values["exercise"] else "Als Realeinsatz gekennzeichnet")
        new_lead = None
        if changes.get("lead_organization_id") and changes["lead_organization_id"] != incident["lead_organization_id"]:
            new_lead = int(changes["lead_organization_id"])
            # Nur Admins der führenden Wehr geben die Führung ab; sonst könnte
            # eine beteiligte Wehr den Einsatz übernehmen und löschen.
            if not self.can_administer(user, incident):
                raise IncidentAccessError("Die Führung übergeben nur Admins der führenden Wehr.")
            if self.org.organization(new_lead) is None:
                raise IncidentError("Wehr nicht gefunden.")
            new_lead_name = self._org_name(new_lead)
        with self._lock, self._engine.begin() as connection:
            if changes.get("alarm_at"):
                alarm = parse_time(changes["alarm_at"])
                if iso(alarm) != incident["alarm_at"]:
                    values["alarm_at"] = iso(alarm)
                    values["code"] = self._code(connection, alarm, exclude=incident_id)
                    notes.append(f"Alarmzeit auf {alarm.strftime('%d.%m.%Y %H:%M')} geändert")
            if new_lead is not None:
                # Bisherige Führung bleibt als beteiligte Wehr erhalten.
                self._add_org(connection, incident_id, incident["lead_organization_id"], actor)
                connection.execute(
                    delete(incident_organizations).where(
                        incident_organizations.c.incident_id == incident_id,
                        incident_organizations.c.organization_id == new_lead,
                    )
                )
                values["lead_organization_id"] = new_lead
                notes.append(f"Führung an {new_lead_name} übergeben")
            changed = [
                key for key, value in values.items()
                if key in EDITABLE_FIELDS and value != incident.get(key)
            ]
            if not values:
                return incident
            values["updated_at"] = iso(local_now())
            if "latitude" in values:
                values["map_revision"] = incidents.c.map_revision + 1
            connection.execute(update(incidents).where(incidents.c.id == incident_id).values(**values))
            if "latitude" in values and values.get("latitude") != incident.get("latitude"):
                notes.append("Einsatzort auf der Karte gesetzt" if values.get("latitude") is not None else "Einsatzort entfernt")
            if changed:
                labels = {
                    "title": "Titel", "keyword": "Alarmstichwort", "address": "Adresse",
                    "alarm_text": "Alarmierungstext", "alerted_units": "Alarmierte Einheiten",
                    "dispatch_number": "Leitstellen-Nummer", "summary": "Lagebericht",
                }
                notes.append("Geändert: " + ", ".join(labels[key] for key in changed))
            for note in notes:
                self._log(connection, incident_id, actor, "edit", note)
        return self.get(incident_id)

    def set_status(self, user: dict, incident_id: int, status: str, *, ended_at=None) -> dict:
        if status not in INCIDENT_STATUS:
            raise IncidentError("Unbekannter Status.")
        incident = self.require(user, incident_id, edit=True)
        if status == incident["status"]:
            return incident
        if status == "closed" or incident["status"] == "closed":
            if not self.can_administer(user, incident):
                raise IncidentAccessError("Abschließen und wieder öffnen dürfen Admins der führenden Wehr.")
        actor = user.get("display_name") or user["username"]
        values = {"status": status, "updated_at": iso(local_now())}
        if status == "ended" and not incident["ended_at"]:
            values["ended_at"] = iso(parse_time(ended_at) if ended_at else local_now())
        if status == "running":
            values["ended_at"] = None
        if status == "closed" and not incident["ended_at"]:
            values["ended_at"] = iso(local_now())
        texts = {
            "running": "Einsatz wieder aufgenommen",
            "ended": "Einsatz beendet",
            "closed": "Einsatz abgeschlossen (Nachbearbeitung fertig)",
        }
        with self._lock, self._engine.begin() as connection:
            connection.execute(update(incidents).where(incidents.c.id == incident_id).values(**values))
            if status != "running":
                # Drohnen sind ab Einsatzende nicht mehr im Einsatz.
                connection.execute(
                    update(incident_sources)
                    .where(
                        incident_sources.c.incident_id == incident_id,
                        incident_sources.c.removed_at.is_(None),
                    )
                    .values(removed_at=values.get("ended_at") or incident["ended_at"] or iso(local_now()))
                )
            if status != "running":
                connection.execute(
                    update(incident_drones)
                    .where(
                        incident_drones.c.incident_id == incident_id,
                        incident_drones.c.removed_at.is_(None),
                    )
                    .values(removed_at=values.get("ended_at") or incident["ended_at"] or iso(local_now()))
                )
            self._log(connection, incident_id, actor, "status", texts[status])
        return self.get(incident_id)

    def delete(self, user: dict, incident_id: int) -> dict:
        incident = self.require(user, incident_id)
        if not self.can_administer(user, incident):
            raise IncidentAccessError("Löschen dürfen nur Admins der führenden Wehr.")
        with self._lock, self._engine.begin() as connection:
            connection.execute(delete(incidents).where(incidents.c.id == incident_id))
        self.org.audit(
            user.get("display_name") or user["username"],
            "Einsatz gelöscht",
            f"{incident['code']} {incident['keyword']}".strip(),
            incident["lead_organization_id"],
        )
        return incident

    def set_weather(self, incident_id: int, snapshot: dict, actor: str = "") -> None:
        """Wetter anhängen; frühere Erfassungen bleiben erhalten."""

        with self._lock, self._engine.begin() as connection:
            stored = connection.execute(
                select(incidents.c.weather).where(incidents.c.id == incident_id)
            ).scalar_one_or_none()
            history = _weather_history(stored) + [snapshot]
            connection.execute(
                update(incidents)
                .where(incidents.c.id == incident_id)
                .values(weather=json.dumps(history, ensure_ascii=False))
            )
            self._log(
                connection,
                incident_id,
                actor or "System",
                "weather",
                _weather_log_text(snapshot),
            )

    # -----------------------------------------------------
    # Beteiligte Wehren
    # -----------------------------------------------------

    def _add_org(self, connection, incident_id: int, organization_id: int, actor: str) -> bool:
        exists = connection.execute(
            select(incident_organizations.c.organization_id).where(
                incident_organizations.c.incident_id == incident_id,
                incident_organizations.c.organization_id == organization_id,
            )
        ).first()
        if exists:
            return False
        connection.execute(
            insert(incident_organizations).values(
                incident_id=incident_id,
                organization_id=organization_id,
                added_at=iso(local_now()),
                added_by=actor,
            )
        )
        return True

    def add_organization(self, user: dict, incident_id: int, organization_id: int) -> dict:
        incident = self.require(user, incident_id, edit=True)
        org = self.org.organization(organization_id)
        if org is None or org["archived"]:
            raise IncidentError("Wehr nicht gefunden.")
        if organization_id == incident["lead_organization_id"]:
            raise IncidentError("Diese Wehr führt den Einsatz bereits.")
        actor = user.get("display_name") or user["username"]
        name = self._org_name(organization_id)
        with self._lock, self._engine.begin() as connection:
            if self._add_org(connection, incident_id, organization_id, actor):
                self._log(connection, incident_id, actor, "org", f"{name} beteiligt")
                self._touch(connection, incident_id)
        return self.get(incident_id)

    def remove_organization(self, user: dict, incident_id: int, organization_id: int) -> dict:
        incident = self.require(user, incident_id, edit=True)
        actor = user.get("display_name") or user["username"]
        name = self._org_name(organization_id)
        with self._lock, self._engine.begin() as connection:
            removed = connection.execute(
                delete(incident_organizations).where(
                    incident_organizations.c.incident_id == incident_id,
                    incident_organizations.c.organization_id == organization_id,
                )
            ).rowcount
            if removed:
                self._log(connection, incident_id, actor, "org", f"{name} nicht mehr beteiligt")
                self._touch(connection, incident_id)
        return self.get(incident["id"])

    # -----------------------------------------------------
    # Personen
    # -----------------------------------------------------

    def participants(self, incident_id: int) -> list[dict]:
        with self._engine.connect() as connection:
            rows = connection.execute(
                select(incident_participants)
                .where(incident_participants.c.incident_id == incident_id)
                .order_by(incident_participants.c.id)
            ).all()
        result = []
        for row in rows:
            item = dict(row._mapping)
            item["role_label"] = INCIDENT_ROLES.get(item["role"], item["role"])
            item["organization_name"] = self._org_name(item["organization_id"]) if item["organization_id"] else ""
            item["warning"] = ""
            if item["role"] == "fernpilot":
                if item["user_id"] is None:
                    item["warning"] = "Ohne Konto: Fernpilotennachweis nicht hinterlegt."
                elif not any(q["valid"] for q in self.org.qualifications(item["user_id"])):
                    item["warning"] = "Kein gültiger Fernpilotennachweis hinterlegt."
            result.append(item)
        return result

    def candidates(self, incident: dict) -> list[dict]:
        """Konten der beteiligten Wehren (inkl. Untereinheiten)."""

        org_ids = self.org.descendants(incident["organization_ids"])
        members = [item for item in self.org.memberships() if item["organization_id"] in org_ids]
        by_user: dict[int, int] = {}
        for item in members:
            by_user.setdefault(item["user_id"], item["organization_id"])
        result = []
        for user_id, organization_id in by_user.items():
            account = self.org.user_by_id(user_id)
            if not account or not account["active"]:
                continue
            result.append({
                "user_id": user_id,
                "name": account["display_name"] or account["username"],
                "organization_id": organization_id,
                "organization_name": self._org_name(organization_id),
                "pilot": any(q["valid"] for q in self.org.qualifications(user_id)),
            })
        return sorted(result, key=lambda item: item["name"].lower())

    def add_participant(
        self,
        user: dict,
        incident_id: int,
        *,
        role: str,
        user_id: int | None = None,
        name: str = "",
        organization_id: int | None = None,
        from_at=None,
        until_at=None,
        note: str = "",
    ) -> dict:
        incident = self.require(user, incident_id, edit=True)
        if role not in INCIDENT_ROLES:
            raise IncidentError("Unbekannte Einsatzrolle.")
        name = " ".join(str(name or "").split())[:80]
        if user_id is not None:
            candidate = next((item for item in self.candidates(incident) if item["user_id"] == user_id), None)
            if candidate is None:
                raise IncidentError("Das Konto gehört zu keiner beteiligten Wehr.")
            name = candidate["name"]
            organization_id = organization_id or candidate["organization_id"]
        elif not name:
            raise IncidentError("Bitte ein Konto wählen oder einen Namen eintragen.")
        if organization_id is not None and self.org.organization(organization_id) is None:
            raise IncidentError("Wehr nicht gefunden.")
        actor = user.get("display_name") or user["username"]
        start = parse_time(from_at) if from_at else local_now()
        values = {
            "incident_id": incident_id,
            "user_id": user_id,
            "name": name,
            "organization_id": organization_id,
            "role": role,
            "from_at": iso(start),
            "until_at": iso(parse_time(until_at)) if until_at else None,
            "note": str(note or "").strip()[:200],
        }
        with self._lock, self._engine.begin() as connection:
            participant_id = connection.execute(insert(incident_participants).values(**values)).inserted_primary_key[0]
            self._log(connection, incident_id, actor, "person", f"{name} als {INCIDENT_ROLES[role]} eingetragen")
            self._touch(connection, incident_id)
        return next(item for item in self.participants(incident_id) if item["id"] == participant_id)

    def update_participant(self, user: dict, incident_id: int, participant_id: int, **changes) -> dict:
        self.require(user, incident_id, edit=True)
        current = next((item for item in self.participants(incident_id) if item["id"] == participant_id), None)
        if current is None:
            raise LookupError("Person nicht gefunden.")
        values = {}
        if changes.get("role"):
            if changes["role"] not in INCIDENT_ROLES:
                raise IncidentError("Unbekannte Einsatzrolle.")
            values["role"] = changes["role"]
        for key in ("from_at", "until_at"):
            if key in changes:
                values[key] = iso(parse_time(changes[key])) if changes[key] else None
        if "note" in changes:
            values["note"] = str(changes["note"] or "").strip()[:200]
        if not values:
            return current
        actor = user.get("display_name") or user["username"]
        with self._lock, self._engine.begin() as connection:
            connection.execute(
                update(incident_participants)
                .where(incident_participants.c.id == participant_id)
                .values(**values)
            )
            if "until_at" in values and values["until_at"]:
                self._log(connection, incident_id, actor, "person", f"{current['name']} aus dem Einsatz ausgetragen")
            elif "role" in values and values["role"] != current["role"]:
                self._log(connection, incident_id, actor, "person", f"{current['name']} jetzt {INCIDENT_ROLES[values['role']]}")
            self._touch(connection, incident_id)
        return next(item for item in self.participants(incident_id) if item["id"] == participant_id)

    def remove_participant(self, user: dict, incident_id: int, participant_id: int) -> None:
        self.require(user, incident_id, edit=True)
        current = next((item for item in self.participants(incident_id) if item["id"] == participant_id), None)
        if current is None:
            raise LookupError("Person nicht gefunden.")
        actor = user.get("display_name") or user["username"]
        with self._lock, self._engine.begin() as connection:
            connection.execute(delete(incident_participants).where(incident_participants.c.id == participant_id))
            self._log(connection, incident_id, actor, "person", f"{current['name']} ({current['role_label']}) entfernt")
            self._touch(connection, incident_id)

    # -----------------------------------------------------
    # Drohnen (Quellen)
    # -----------------------------------------------------

    def sources(self, incident_id: int) -> list[dict]:
        with self._engine.connect() as connection:
            rows = connection.execute(
                select(incident_sources)
                .where(incident_sources.c.incident_id == incident_id)
                .order_by(incident_sources.c.added_at)
            ).all()
        return [dict(row._mapping) | {"active": row.removed_at is None} for row in rows]

    def active_source_ids(self, incident_id: int) -> list[str]:
        return [item["source_id"] for item in self.sources(incident_id) if item["active"]]

    def add_source(self, user: dict, incident_id: int, source) -> dict:
        incident = self.require(user, incident_id, edit=True)
        if incident["status"] != "running":
            raise IncidentError("Drohnen lassen sich nur laufenden Einsätzen zuordnen.")
        if source.id in self.active_source_ids(incident_id):
            raise IncidentError("Diese Drohne ist dem Einsatz bereits zugeordnet.")
        actor = user.get("display_name") or user["username"]
        with self._lock, self._engine.begin() as connection:
            connection.execute(
                insert(incident_sources).values(
                    incident_id=incident_id,
                    source_id=source.id,
                    source_name=source.name,
                    added_at=iso(local_now()),
                )
            )
            self._log(connection, incident_id, actor, "source", f"Drohne „{source.name}“ im Einsatz")
            self._touch(connection, incident_id)
        return self.get(incident_id)

    def remove_source(self, user: dict, incident_id: int, source_id: str) -> dict:
        self.require(user, incident_id, edit=True)
        actor = user.get("display_name") or user["username"]
        with self._lock, self._engine.begin() as connection:
            row = connection.execute(
                select(incident_sources).where(
                    incident_sources.c.incident_id == incident_id,
                    incident_sources.c.source_id == source_id,
                    incident_sources.c.removed_at.is_(None),
                )
            ).first()
            if row is None:
                raise LookupError("Drohne ist diesem Einsatz nicht zugeordnet.")
            connection.execute(
                update(incident_sources)
                .where(incident_sources.c.id == row.id)
                .values(removed_at=iso(local_now()))
            )
            self._log(connection, incident_id, actor, "source", f"Drohne „{row.source_name}“ aus dem Einsatz genommen")
            self._touch(connection, incident_id)
        return self.get(incident_id)

    # -----------------------------------------------------
    # Verlauf und Aufnahmen
    # -----------------------------------------------------

    def log(self, incident_id: int) -> list[dict]:
        with self._engine.connect() as connection:
            rows = connection.execute(
                select(incident_log)
                .where(incident_log.c.incident_id == incident_id)
                .order_by(incident_log.c.at, incident_log.c.id)
            ).all()
        return [dict(row._mapping) for row in rows]

    def add_note(self, user: dict, incident_id: int, text: str, kind: str = "note") -> None:
        self.require(user, incident_id, edit=True)
        text = str(text or "").strip()
        if not text:
            raise IncidentError("Bitte einen Text eingeben.")
        if len(text) > 2000:
            raise IncidentError("Die Notiz ist zu lang (max. 2000 Zeichen).")
        with self._lock, self._engine.begin() as connection:
            self._log(connection, incident_id, user.get("display_name") or user["username"], kind, text)
            self._touch(connection, incident_id)

    def record(self, incident_id: int, text: str, *, actor: str = "System", kind: str = "system") -> None:
        """Eintrag ohne Rechteprüfung (z. B. Gastlink geöffnet)."""

        with self._engine.begin() as connection:
            self._log(connection, incident_id, actor, kind, text)

    def media(self, incident: dict, items: list[dict]) -> list[dict]:
        """Aufnahmen und Snapshots der Einsatzdrohnen im Einsatzzeitraum."""

        windows: dict[str, list[tuple[datetime, datetime]]] = {}
        end_of_incident = parse_time(incident["ended_at"]) if incident.get("ended_at") else None
        for entry in self.sources(incident["id"]):
            start = parse_time(entry["added_at"])
            end = (
                parse_time(entry["removed_at"]) if entry["removed_at"]
                else end_of_incident or local_now() + timedelta(minutes=1)
            )
            windows.setdefault(entry["source_id"], []).append((start - timedelta(minutes=1), end + timedelta(minutes=1)))
        result = []
        for item in items:
            match = MEDIA_NAME.match(item.get("name") or "")
            if not match or match["source"] not in windows:
                continue
            taken = datetime.strptime(match["stamp"], "%Y%m%d_%H%M%S").astimezone()
            if any(start <= taken <= end for start, end in windows[match["source"]]):
                result.append({
                    **item,
                    "source_id": match["source"],
                    "taken_at": iso(taken),
                })
        return sorted(result, key=lambda item: item["taken_at"])

    def all_organizations(self) -> list[dict]:
        """Alle aktiven Wehren (Namen sind im Landkreis nicht geheim)."""

        with self._engine.connect() as connection:
            rows = connection.execute(
                select(
                    organizations.c.id,
                    organizations.c.name,
                    organizations.c.short_name,
                    organizations.c.kind,
                    organizations.c.parent_id,
                ).where(organizations.c.archived.is_(False)).order_by(organizations.c.name)
            ).all()
        return [dict(row._mapping) for row in rows]
