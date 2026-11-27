"""Serverseitiges, dauerhaftes Ereignisprotokoll.

Alle wichtigen Ereignisse (Drohnen, Aufnahmen, Weiterleitungen, Speicher,
Konfiguration, Gastlinks, Benachrichtigungen, Serverstart) werden auf dem
Server erfasst – auch ohne geöffnete Oberfläche – und in
``config/event_log.jsonl`` gespeichert. Einträge bleiben 30 Tage erhalten und
überstehen Neustarts und Updates. Admins und Superadmins erhalten sie mit dem
Dashboard-Status; der Browser lädt nur neue Einträge nach.
"""

from __future__ import annotations

import json
import logging
import secrets
import threading
import time
from collections import deque
from pathlib import Path

RETENTION_SECONDS = 30 * 24 * 60 * 60
MAX_EVENTS = 20000
INITIAL_EVENTS = 200
MAX_BATCH = 500
PRUNE_INTERVAL_SECONDS = 60 * 60
LEVELS = {"info", "success", "warning", "error"}

logger = logging.getLogger(__name__)


class ServerEventLog:
    def __init__(
        self,
        path: str | Path | None = "config/event_log.jsonl",
        *,
        retention_seconds: float = RETENTION_SECONDS,
        max_events: int = MAX_EVENTS,
    ) -> None:
        self._path = Path(path) if path else None
        self._retention = retention_seconds
        self._events: deque[dict] = deque(maxlen=max_events)
        self._lock = threading.Lock()
        self._next_id = 1
        self._last_prune = 0.0
        # Kennung des Protokolls: ändert sich nur, wenn die Datei neu
        # angelegt wird. Der Browser setzt dann seine Zählung zurück.
        self.instance = secrets.token_hex(4)
        self._load()

    # ------------------------------------------------------------------
    # Datei
    # ------------------------------------------------------------------

    def _load(self) -> None:
        if self._path is None or not self._path.exists():
            self._write_all()
            return
        now = time.time()
        try:
            lines = self._path.read_text(encoding="utf-8").splitlines()
        except OSError:
            logger.exception("Ereignisprotokoll konnte nicht gelesen werden.")
            return
        for line in lines:
            try:
                item = json.loads(line)
            except ValueError:
                continue
            if "instance" in item and "id" not in item:
                self.instance = str(item["instance"])
                continue
            if now - float(item.get("at", 0)) >= self._retention:
                continue
            self._events.append(item)
            self._next_id = max(self._next_id, int(item["id"]) + 1)
        self._write_all()

    def _write_all(self) -> None:
        """Datei ohne abgelaufene Einträge neu schreiben."""

        if self._path is None:
            return
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self._path.with_name(f".{self._path.name}.tmp")
            with temporary.open("w", encoding="utf-8") as handle:
                handle.write(json.dumps({"instance": self.instance}) + "\n")
                for event in self._events:
                    handle.write(json.dumps(event, ensure_ascii=False) + "\n")
            temporary.replace(self._path)
        except OSError:
            logger.exception("Ereignisprotokoll konnte nicht gespeichert werden.")
        self._last_prune = time.time()

    def _append(self, event: dict) -> None:
        if self._path is None:
            return
        try:
            with self._path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(event, ensure_ascii=False) + "\n")
        except OSError:
            logger.exception("Ereignis konnte nicht gespeichert werden.")

    def _prune_locked(self, now: float) -> None:
        if now - self._last_prune < PRUNE_INTERVAL_SECONDS:
            return
        removed = False
        while self._events and now - self._events[0]["at"] >= self._retention:
            self._events.popleft()
            removed = True
        if removed:
            self._write_all()
        else:
            self._last_prune = now

    # ------------------------------------------------------------------
    # Schnittstelle
    # ------------------------------------------------------------------

    def record(
        self,
        level: str,
        message: str,
        *,
        actor: str | None = None,
        organization_id: int | None = None,
    ) -> dict:
        """Ereignis erfassen; ``actor`` nennt den auslösenden Benutzer.

        Mit ``organization_id`` sehen auch Admins dieser Organisation den
        Eintrag; ohne ist er eine Systemmeldung für Kreis-Admins und
        Superadmins.
        """

        if actor:
            message = f"{message} · {actor}"
        with self._lock:
            now = time.time()
            event = {
                "id": self._next_id,
                "at": now,
                "level": level if level in LEVELS else "info",
                "message": message,
            }
            if organization_id is not None:
                event["org"] = organization_id
            self._next_id += 1
            self._events.append(event)
            self._append(event)
            self._prune_locked(now)
        logger.info("Ereignis: %s", message)
        return dict(event)

    def since(
        self,
        after_id: int | None = None,
        organization_ids: set[int] | None = None,
    ) -> dict:
        """Neue Einträge seit ``after_id`` (ohne: die letzten Einträge).

        ``organization_ids`` beschränkt auf Einträge dieser Organisationen
        (None: alle Einträge).
        """

        with self._lock:
            visible = [
                event for event in self._events
                if organization_ids is None or event.get("org") in organization_ids
            ]
            if after_id is None:
                events = visible[-INITIAL_EVENTS:]
            else:
                events = [
                    event for event in visible if event["id"] > after_id
                ][:MAX_BATCH]
            return {
                "instance": self.instance,
                "events": [dict(event) for event in events],
            }

    def recent(self) -> dict:
        """Kompatibel zu älteren Aufrufen: letzte Einträge."""

        return self.since(None)
