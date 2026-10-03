"""Geheimes Ticket für die Anmeldung des lokalen Kiosk-Displays.

Der Display-Dienst erzeugt bei jedem Start ein zufälliges Ticket in seinem
privaten Laufzeitverzeichnis und übergibt es Chromium in der URL. Die
Webanwendung läuft unter demselben Dienstkonto und gewährt die
Display-Sitzung nur, wenn das übergebene Ticket mit dieser Datei
übereinstimmt. Eine Herkunft von 127.0.0.1 allein genügt nicht, weil auch
der Port-80-Proxy des lokalen Profils Anfragen von dort weiterleitet.
"""

from __future__ import annotations

import hmac
import os
import secrets
import tempfile
from pathlib import Path


TICKET_PARAMETER = "display_ticket"
DEFAULT_TICKET_FILE = "/run/open-bos-display/kiosk-ticket"


def ticket_file() -> Path:
    return Path(
        os.environ.get(
            "OPEN_BOS_DISPLAY_TICKET_FILE",
            DEFAULT_TICKET_FILE,
        )
    )


def issue_ticket(path: Path | None = None) -> str:
    """Neues Ticket erzeugen und nur für das Dienstkonto lesbar ablegen."""

    path = path or ticket_file()
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    ticket = secrets.token_urlsafe(32)
    descriptor, temporary = tempfile.mkstemp(
        prefix=".kiosk-ticket.",
        dir=path.parent,
    )
    temporary_path = Path(temporary)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as file:
            file.write(ticket)
        os.chmod(temporary_path, 0o600)
        os.replace(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)
    return ticket


def ticket_valid(candidate: str | None, path: Path | None = None) -> bool:
    """Übergebenes Ticket mit dem aktuell gültigen Ticket vergleichen."""

    if not candidate:
        return False
    try:
        expected = (path or ticket_file()).read_text(encoding="utf-8").strip()
    except OSError:
        return False
    if not expected:
        return False
    return hmac.compare_digest(candidate.encode(), expected.encode())
