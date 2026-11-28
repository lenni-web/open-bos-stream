"""Wer welche Aufnahmen und Snapshots sehen und verwalten darf.

Aufnahmen gehören zur Drohne, deren Kennung im Dateinamen steht
(``recording_<quelle>_<zeit>.mp4``, ``snapshot_<quelle>_<zeit>.jpg``):

* Drohnenteam der Wehr: ansehen, herunterladen, „Behalten“ setzen.
* Wehr-Admin: zusätzlich löschen.
* Kreis-Admins und Superadmins: alle Dateien, auch solche ohne
  erkennbare oder inzwischen entfernte Drohne.
"""

from __future__ import annotations

import re

from fastapi import HTTPException

from open_bos_stream.auth.guest_access import (
    can_admin_source,
    can_operate_source,
    is_guest,
    is_restricted,
)

MEDIA_NAME = re.compile(
    r"^(?:recording|snapshot)_(?P<source>.+)_\d{8}_\d{6}\.(?:mp4|jpg)$"
)

ACCESS_LEVELS = (None, "operate", "admin")


def media_source_id(filename: str) -> str | None:
    match = MEDIA_NAME.match(filename or "")
    return match["source"] if match else None


def media_access(user: dict | None, filename: str, config) -> str | None:
    """None (kein Zugriff), "operate" oder "admin"."""

    if not user or is_guest(user):
        return None
    if not is_restricted(user) or user.get("server_admin"):
        return "admin"
    source_id = media_source_id(filename)
    source = next((item for item in config.sources if item.id == source_id), None)
    if source is None:
        return None
    if can_admin_source(user, source):
        return "admin"
    if can_operate_source(user, source):
        return "operate"
    return None


def require_media_access(user: dict | None, filename: str, config, *, level: str = "operate") -> None:
    access = media_access(user, filename, config)
    if ACCESS_LEVELS.index(access) < ACCESS_LEVELS.index(level):
        if access is None:
            raise HTTPException(status_code=404, detail="Datei nicht gefunden.")
        raise HTTPException(
            status_code=403,
            detail="Löschen dürfen nur Admins der Wehr, der die Drohne gehört.",
        )


def require_capture_access(user: dict | None, source_id: str, config) -> None:
    """Aufnahme und Snapshot auslösen: Drohnenteam der Wehr der Drohne."""

    source = next((item for item in config.sources if item.id == source_id), None)
    if not is_guest(user) and user and (not is_restricted(user) or user.get("server_admin")):
        return
    if source is None or not can_operate_source(user, source):
        raise HTTPException(
            status_code=403,
            detail="Aufnahmen und Snapshots löst das Drohnenteam der Wehr dieser Drohne aus.",
        )


def visible_media(user: dict | None, items: list[dict], config) -> list[dict]:
    """Dateiliste mit Quelle, Wehr und Rechten für die Oberfläche."""

    sources = {item.id: item for item in config.sources}
    result = []
    for item in items:
        access = media_access(user, item.get("name", ""), config)
        if access is None:
            continue
        source = sources.get(media_source_id(item.get("name", "")) or "")
        result.append({
            **item,
            "source_id": source.id if source else None,
            "source_name": source.name if source else None,
            "organization_id": source.organization_id if source else None,
            "can_delete": access == "admin",
        })
    return result


def media_organization(filename: str, config) -> int | None:
    source_id = media_source_id(filename)
    source = next((item for item in config.sources if item.id == source_id), None)
    return source.organization_id if source else None
