"""Zeitlich begrenzte Gastlinks für ausgewählte Livebilder.

Der Link enthält einen zufälligen Code; gespeichert wird nur dessen
SHA-256-Hash. Ein Gastlink gilt höchstens 48 Stunden, nur für die beim
Erstellen gewählten Quellen und lässt sich jederzeit sperren. Abgelaufene
und gesperrte Links bleiben sieben Tage zur Nachvollziehbarkeit sichtbar.
"""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import tempfile
import threading
import time
from pathlib import Path

from pydantic import BaseModel, Field

MAX_HOURS = 48
RETENTION_SECONDS = 7 * 24 * 60 * 60
TOUCH_INTERVAL_SECONDS = 60


class GuestLinkError(ValueError):
    """Ungültige Angaben zu einem Gastlink."""


class GuestLink(BaseModel):
    id: str
    token_hash: str
    label: str = Field(max_length=80)
    source_ids: list[str]
    created_by: str
    created_at: float
    expires_at: float
    # Organisation, der der Link gehört (für Sichtbarkeit und Protokoll).
    organization_id: int | None = None
    revoked_at: float | None = None
    revoked_by: str | None = None
    last_used_at: float | None = None

    def active(self, now: float | None = None) -> bool:
        now = time.time() if now is None else now
        return self.revoked_at is None and now < self.expires_at

    def public(self, now: float | None = None) -> dict:
        """Darstellung ohne Hash für die Verwaltung."""

        data = self.model_dump(exclude={"token_hash"})
        data["active"] = self.active(now)
        return data


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class GuestLinkStore:
    def __init__(self, path: str | Path = "config/guest_links.json") -> None:
        self._path = Path(path)
        self._lock = threading.RLock()
        self._cache_key: tuple[int, int] | None = None
        self._cache: list[GuestLink] = []

    # ------------------------------------------------------------------
    # Datei
    # ------------------------------------------------------------------

    def _file_key(self) -> tuple[int, int] | None:
        try:
            stat = self._path.stat()
        except OSError:
            return None
        return (stat.st_mtime_ns, stat.st_size)

    def _read(self) -> list[GuestLink]:
        key = self._file_key()
        if key is None:
            self._cache_key, self._cache = None, []
            return []
        if key == self._cache_key:
            return self._cache
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            links = [GuestLink.model_validate(item) for item in raw]
        except (OSError, ValueError):
            links = []
        self._cache_key, self._cache = key, links
        return links

    def _write(self, links: list[GuestLink]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(
            prefix=f".{self._path.name}.",
            dir=self._path.parent,
        )
        try:
            os.chmod(temporary, 0o600)
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                json.dump(
                    [link.model_dump() for link in links],
                    handle,
                    indent=2,
                )
            os.replace(temporary, self._path)
        except BaseException:
            Path(temporary).unlink(missing_ok=True)
            raise
        self._cache_key, self._cache = self._file_key(), links

    @staticmethod
    def _purge(links: list[GuestLink], now: float) -> list[GuestLink]:
        return [
            link
            for link in links
            if now - (link.revoked_at or link.expires_at) < RETENTION_SECONDS
        ]

    # ------------------------------------------------------------------
    # Verwaltung
    # ------------------------------------------------------------------

    def create(
        self,
        *,
        label: str,
        source_ids: list[str],
        hours: float,
        created_by: str,
        organization_id: int | None = None,
    ) -> tuple[GuestLink, str]:
        label = " ".join(str(label or "").split())
        if not label:
            raise GuestLinkError("Bitte eine Bezeichnung angeben.")
        if len(label) > 80:
            raise GuestLinkError("Die Bezeichnung ist zu lang (max. 80 Zeichen).")
        source_ids = list(dict.fromkeys(source_ids))
        if not source_ids:
            raise GuestLinkError("Bitte mindestens eine Quelle auswählen.")
        if not 0 < hours <= MAX_HOURS:
            raise GuestLinkError(
                f"Ein Gastlink gilt höchstens {MAX_HOURS} Stunden."
            )
        now = time.time()
        token = secrets.token_urlsafe(24)
        link = GuestLink(
            id=secrets.token_hex(6),
            token_hash=token_hash(token),
            label=label,
            source_ids=source_ids,
            created_by=created_by,
            created_at=now,
            expires_at=now + hours * 3600,
            organization_id=organization_id,
        )
        with self._lock:
            links = self._purge(list(self._read()), now)
            links.append(link)
            self._write(links)
        return link, token

    def list(self) -> list[GuestLink]:
        with self._lock:
            now = time.time()
            return sorted(
                self._purge(list(self._read()), now),
                key=lambda link: link.created_at,
                reverse=True,
            )

    def assign_unowned(self, organization_id: int) -> int:
        """Ältere Links ohne Organisation einmalig zuordnen."""

        with self._lock:
            links = list(self._read())
            changed = 0
            for index, link in enumerate(links):
                if link.organization_id is None:
                    links[index] = link.model_copy(
                        update={"organization_id": organization_id}
                    )
                    changed += 1
            if changed:
                self._write(links)
            return changed

    def revoke(self, link_id: str, revoked_by: str) -> GuestLink:
        with self._lock:
            links = list(self._read())
            for index, link in enumerate(links):
                if link.id == link_id:
                    if link.revoked_at is None:
                        link = link.model_copy(
                            update={
                                "revoked_at": time.time(),
                                "revoked_by": revoked_by,
                            }
                        )
                        links[index] = link
                        self._write(links)
                    return link
        raise KeyError(link_id)

    # ------------------------------------------------------------------
    # Prüfung
    # ------------------------------------------------------------------

    def find_by_token(self, token: str | None) -> GuestLink | None:
        if not token or len(token) > 128:
            return None
        wanted = token_hash(token)
        with self._lock:
            for link in self._read():
                if secrets.compare_digest(link.token_hash, wanted):
                    return link if link.active() else None
        return None

    def active_link(self, link_id: str) -> GuestLink | None:
        with self._lock:
            for link in self._read():
                if link.id == link_id:
                    return link if link.active() else None
        return None

    def touch(self, link_id: str) -> None:
        """Letzten Zugriff vermerken (höchstens einmal pro Minute)."""

        with self._lock:
            links = list(self._read())
            now = time.time()
            for index, link in enumerate(links):
                if link.id != link_id:
                    continue
                if (
                    link.last_used_at
                    and now - link.last_used_at < TOUCH_INTERVAL_SECONDS
                ):
                    return
                links[index] = link.model_copy(update={"last_used_at": now})
                self._write(links)
                return
