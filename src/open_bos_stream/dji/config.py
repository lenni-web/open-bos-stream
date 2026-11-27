"""Zugangsdaten der DJI-Anbindung aus ``config/dji.yaml``.

Die Datei liegt neben ``stream.yaml``, ist nicht Teil des Repositorys und
wird nie protokolliert. Ohne sie ist die Anbindung abgeschaltet.
"""

from __future__ import annotations

import logging
import os
import uuid
from dataclasses import dataclass
from pathlib import Path

import yaml


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DjiConfig:
    app_id: str = ""
    app_key: str = ""
    license: str = ""
    platform_name: str = "Open BOS Drohnen"
    workspace_id: str = ""
    # Verbindung der Fernsteuerungen (öffentlich).
    public_scheme: str = "ssl"
    public_host: str = ""
    public_port: int = 8883
    pilot_username: str = ""
    pilot_password: str = ""
    # Verbindung der Anwendung zum Broker auf demselben Server.
    broker_host: str = "127.0.0.1"
    broker_port: int = 1883
    server_username: str = ""
    server_password: str = ""

    @property
    def enabled(self) -> bool:
        """Broker-Zugang vorhanden: Nachrichten empfangen."""

        return bool(self.server_username and self.server_password)

    @property
    def licensed(self) -> bool:
        """DJI-Daten vorhanden: Fernsteuerungen können sich anmelden."""

        return bool(self.app_id and self.app_key and self.license
                    and self.pilot_username and self.pilot_password)

    def public_address(self, request_host: str) -> str:
        return f"{self.public_scheme}://{self.public_host or request_host}:{self.public_port}"

    def workspace(self) -> str:
        """Pilot 2 verlangt eine UUID; ohne Vorgabe aus dem Namen gebildet."""

        return self.workspace_id or str(
            uuid.uuid5(uuid.NAMESPACE_URL, f"open-bos:{self.app_id}")
        )


def config_path() -> Path:
    stream = Path(os.environ.get("OPEN_BOS_STREAM_CONFIG", "config/stream.yaml"))
    return stream.with_name("dji.yaml")


def load_config(path: Path | None = None) -> DjiConfig:
    path = path or config_path()
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except FileNotFoundError:
        return DjiConfig()
    except (OSError, yaml.YAMLError) as exc:
        # Ohne Dateiinhalt melden: Er enthält Zugangsdaten.
        logger.error("DJI-Konfiguration %s nicht lesbar (%s).", path, type(exc).__name__)
        return DjiConfig()
    if not isinstance(data, dict):
        return DjiConfig()
    values = {}
    for name, field in DjiConfig.__dataclass_fields__.items():
        if data.get(name) in (None, ""):
            continue
        try:
            values[name] = int(data[name]) if field.type == "int" else str(data[name]).strip()
        except (TypeError, ValueError):
            logger.error("DJI-Konfiguration: ungültiger Wert für %s.", name)
    return DjiConfig(**values)
