"""Serverseitige Ereignisse für das Ereignisprotokoll der Oberfläche.

Das Ereignisprotokoll im Browser zeigt sonst nur, was im eigenen Browser
passiert. Ereignisse, die auf dem Server entstehen (z. B. ein Gast öffnet
einen Gastlink), landen hier und werden mit dem Dashboard-Status an Admins
ausgeliefert. Der Speicher ist bewusst klein und flüchtig; dauerhaft
nachvollziehbar bleibt alles im Journal des Dienstes.
"""

from __future__ import annotations

import itertools
import secrets
import threading
import time
from collections import deque

MAX_EVENTS = 100
MAX_AGE_SECONDS = 24 * 60 * 60
LEVELS = {"info", "success", "warning", "error"}


class ServerEventLog:
    def __init__(self, max_events: int = MAX_EVENTS) -> None:
        self._events: deque[dict] = deque(maxlen=max_events)
        self._ids = itertools.count(1)
        self._lock = threading.Lock()
        # Neue Kennung pro Serverstart: Browser setzen ihre Zählung zurück.
        self.instance = secrets.token_hex(4)

    def record(self, level: str, message: str) -> dict:
        with self._lock:
            # Nummer und Reihenfolge gemeinsam vergeben.
            event = {
                "id": next(self._ids),
                "at": time.time(),
                "level": level if level in LEVELS else "info",
                "message": message,
            }
            self._events.append(event)
        return dict(event)

    def recent(self, now: float | None = None) -> dict:
        """Ereignisse der letzten 24 Stunden, älteste zuerst."""

        now = time.time() if now is None else now
        with self._lock:
            events = [
                dict(event)
                for event in self._events
                if now - event["at"] < MAX_AGE_SECONDS
            ]
        return {"instance": self.instance, "events": events}
