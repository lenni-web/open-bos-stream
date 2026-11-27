"""Einsatznachweis je Drohne: Einsatzdatum und beteiligte Personen.

Grundlage sind die ohnehin gespeicherten Zuordnungen (Video-Quelle bzw.
DJI-Gerät im Einsatz) und die Personen des Einsatzes. Je Drohne und Einsatz
entsteht ein Eintrag; Übungen zählen mit. Beteiligt ist, wessen Zeitraum
sich mit dem der Drohne überschneidet.

Gezählt werden alle Einsätze der Drohne. Datum, Stichwort und Namen sieht
nur, wer den jeweiligen Einsatz sehen darf.
"""

from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import select

from open_bos_stream.db.schema import (
    INCIDENT_ROLES,
    incident_drones,
    incident_participants,
    incident_sources,
)
from open_bos_stream.incidents.service import IncidentService, parse_time


def _moment(value: str | None):
    return parse_time(value) if value else None


def _took_part(person: dict, windows: list[tuple], ended) -> bool:
    start, until = _moment(person["from_at"]), _moment(person["until_at"])
    # Nach Einsatzende nachgetragen: Der Beginn ist dann nur der Zeitpunkt
    # der Eingabe und sagt nichts über die Anwesenheit.
    if ended and start and not until and start >= ended:
        start = None
    return any(
        (start is None or end is None or start <= end)
        and (until is None or until >= begin)
        for begin, end in windows
    )


def _persons(people: list[dict], windows: list[tuple], ended, org_name) -> list[dict]:
    result: dict = {}
    for person in people:
        if not _took_part(person, windows, ended):
            continue
        key = person["user_id"] or (person["name"].casefold(), person["organization_id"])
        entry = result.setdefault(key, {
            "name": person["name"],
            "organization_name": org_name(person["organization_id"]),
            "roles": [],
        })
        role = INCIDENT_ROLES.get(person["role"], person["role"])
        if role not in entry["roles"]:
            entry["roles"].append(role)
    return list(result.values())


def drone_history(
    service: IncidentService,
    user: dict,
    *,
    source_ids: Iterable[str] = (),
    serials: Iterable[str] = (),
) -> dict:
    """``{"sources": {id: …}, "devices": {seriennummer: …}}``.

    Die Aufrufer übergeben nur Drohnen, die das Konto sehen darf.
    """

    tables = {
        "sources": (incident_sources, incident_sources.c.source_id, list(source_ids)),
        "devices": (incident_drones, incident_drones.c.serial, list(serials)),
    }
    with service.org.db.engine.connect() as connection:
        assignments = {
            kind: connection.execute(
                select(
                    column.label("key"), table.c.incident_id,
                    table.c.added_at, table.c.removed_at,
                ).where(column.in_(keys))
            ).all() if keys else []
            for kind, (table, column, keys) in tables.items()
        }
        used = {row.incident_id for rows in assignments.values() for row in rows}
        participants = [
            dict(row._mapping)
            for row in connection.execute(
                select(incident_participants)
                .where(incident_participants.c.incident_id.in_(used))
                .order_by(incident_participants.c.id)
            )
        ] if used else []

    visible = {item["id"]: item for item in service.visible(user) if item["id"] in used}
    people: dict[int, list[dict]] = {}
    for person in participants:
        people.setdefault(person["incident_id"], []).append(person)
    names: dict = {None: ""}

    def org_name(organization_id):
        if organization_id not in names:
            names[organization_id] = service.organization_label(organization_id)
        return names[organization_id]

    result: dict = {}
    for kind, (_, _, keys) in tables.items():
        drones: dict[str, dict[int, list]] = {key: {} for key in keys}
        for row in assignments[kind]:
            drones[row.key].setdefault(row.incident_id, []).append(row)
        result[kind] = {}
        for key, flown in drones.items():
            entries = []
            for incident_id, rows in flown.items():
                incident = visible.get(incident_id)
                if incident is None:
                    continue
                ended = _moment(incident["ended_at"])
                windows = [
                    (_moment(row.added_at), _moment(row.removed_at) or ended) for row in rows
                ]
                entries.append({
                    "incident_id": incident_id,
                    "code": incident["code"],
                    "title": incident["keyword"] or incident["title"] or "Einsatz",
                    "alarm_at": incident["alarm_at"],
                    "exercise": bool(incident["exercise"]),
                    "running": incident["status"] == "running",
                    "persons": _persons(people.get(incident_id, []), windows, ended, org_name),
                })
            entries.sort(key=lambda item: parse_time(item["alarm_at"]), reverse=True)
            result[kind][key] = {
                "count": len(flown),
                "hidden": len(flown) - len(entries),
                "incidents": entries,
            }
    return result
