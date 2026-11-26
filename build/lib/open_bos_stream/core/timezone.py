"""Einheitliche Zeitzone für Anzeigen, Mails und Dateinamen.

Server laufen häufig in UTC. Ohne Anpassung stünden in E-Mails,
Gastlink-Meldungen, Aufnahme- und Snapshot-Dateinamen sowie im Journal
Uhrzeiten, die im Winter eine und im Sommer zwei Stunden hinter der
deutschen Zeit liegen. Die Anwendung setzt deshalb beim Start die
Zeitzone ihres eigenen Prozesses (und damit auch der von ihr gestarteten
FFmpeg-Prozesse). Die Systemzeit des Servers bleibt unverändert.

Standard ist Europe/Berlin mit automatischer Sommer-/Winterzeit; eine
andere Zone lässt sich über die Umgebungsvariable OPEN_BOS_TIMEZONE setzen.
"""

from __future__ import annotations

import logging
import os
import time
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

DEFAULT_TIMEZONE = "Europe/Berlin"

logger = logging.getLogger(__name__)


def configured_timezone() -> str:
    return (os.environ.get("OPEN_BOS_TIMEZONE") or DEFAULT_TIMEZONE).strip()


def apply_timezone() -> str | None:
    """Setzt TZ für diesen Prozess; liefert die aktive Zone oder None."""

    name = configured_timezone()
    try:
        ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        logger.warning(
            "Zeitzone %r ist unbekannt; die Systemzeitzone bleibt aktiv.",
            name,
        )
        return None
    os.environ["TZ"] = name
    if hasattr(time, "tzset"):
        time.tzset()
    return name
